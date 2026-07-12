"""Git range generation and local-equivalent comparison helpers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from upstream_monitor_common import (
    MonitorError,
    ReleaseSelection,
    api_json,
    run_cmd,
    validate_relative_path,
)


def parse_name_status_z(output: str) -> list[dict[str, str]]:
    """Parse Git's NUL-delimited name-status format, including rename/copy pairs."""

    if not output or not output.strip("\x00"):
        return []
    parts = output.split("\x00")
    changed: list[dict[str, str]] = []
    index = 0
    status_names = {
        "A": "added",
        "D": "deleted",
        "M": "modified",
        "T": "type-changed",
        "U": "unmerged",
        "X": "unknown",
    }
    while index < len(parts):
        status_token = parts[index]
        index += 1
        if not status_token:
            continue
        code = status_token[0]
        if code in {"R", "C"}:
            if index + 1 >= len(parts) or not parts[index] or not parts[index + 1]:
                raise MonitorError(
                    "Malformed rename/copy record from git diff --name-status -z"
                )
            old_path, new_path = parts[index], parts[index + 1]
            index += 2
            changed.append(
                {
                    "status": "renamed" if code == "R" else "copied",
                    "old_path": old_path,
                    "path": new_path,
                    "score": status_token[1:] or "",
                }
            )
            continue
        if index >= len(parts) or not parts[index]:
            raise MonitorError("Malformed path record from git diff --name-status -z")
        path = parts[index]
        index += 1
        changed.append({"status": status_names.get(code, "unknown"), "path": path})
    return changed


def generate_diffs(
    base_ref: str, head_ref: str
) -> tuple[str, str, list[dict[str, str]]]:
    """Generate stat, binary-capable patch, and changed-file records from one range."""

    common = [base_ref, head_ref, "--find-renames", "--find-copies-harder"]
    stat = run_cmd(["git", "diff", "--stat", *common])
    patch = run_cmd(["git", "diff", "--binary", "--patch", *common])
    names = run_cmd(["git", "diff", "--name-status", "-z", *common])
    return str(stat.stdout), str(patch.stdout), parse_name_status_z(str(names.stdout))


def load_file_map() -> dict[str, str]:
    """Load and strictly validate optional upstream-to-local path mappings."""

    path = Path(".github/upstream-file-map.json")
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MonitorError(f"Failed to parse {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise MonitorError(f"{path} must contain a JSON object")
    mapping: dict[str, str] = {}
    for upstream_path, local_path in raw.items():
        mapping[
            validate_relative_path(upstream_path, label="upstream mapping path")
        ] = validate_relative_path(local_path, label="local mapping path")
    return mapping


def safe_output_path(root: Path, relative: str) -> Path:
    """Resolve an artifact path and reject traversal outside the configured directory."""

    validate_relative_path(relative, label="artifact path")
    target = (root / relative).resolve()
    if root != target and root not in target.parents:
        raise MonitorError(f"Artifact path escapes output directory: {relative!r}")
    return target


def atomic_write_text(path: Path, content: str) -> None:
    """Atomically replace a UTF-8 text artifact."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
        dir=path.parent,
    ) as handle:
        handle.write(content)
        temp_name = handle.name
    os.replace(temp_name, path)


def atomic_write_json(path: Path, payload: Any) -> None:
    """Atomically replace a JSON artifact with deterministic formatting."""

    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def compare_local_files(
    changed_files: list[dict[str, str]],
    head_ref: str,
    out_dir: str | Path,
) -> list[dict[str, Any]]:
    """Compare every upstream changed item with its mapped local equivalent state."""

    root = Path(out_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    comparison_dir = safe_output_path(root, "equivalent-file-comparisons")
    comparison_dir.mkdir(parents=True, exist_ok=True)
    file_map = load_file_map()
    comparisons: list[dict[str, Any]] = []

    for index, changed in enumerate(changed_files):
        upstream_path = validate_relative_path(changed["path"], label="upstream path")
        local_path = file_map.get(upstream_path, upstream_path)
        validate_relative_path(local_path, label="local path")
        local_file = Path(local_path)
        status = changed["status"]
        comparison: dict[str, Any] = {
            "upstream_path": upstream_path,
            "local_path": local_path,
            "upstream_status": status,
            "local_status": "unknown",
            "diff": "",
        }
        if "old_path" in changed:
            comparison["old_upstream_path"] = changed["old_path"]

        if status == "deleted":
            comparison["local_status"] = (
                "missing"
                if not local_file.exists()
                else "present_after_upstream_deletion"
            )
        elif not local_file.exists():
            comparison["local_status"] = "missing"
        else:
            upstream = run_cmd(
                ["git", "show", f"{head_ref}:{upstream_path}"],
                check=False,
                text=False,
            )
            if upstream.returncode != 0:
                comparison["local_status"] = "upstream_missing"
            else:
                upstream_bytes = bytes(upstream.stdout)
                local_bytes = local_file.read_bytes()
                if upstream_bytes == local_bytes:
                    comparison["local_status"] = "identical"
                else:
                    comparison["local_status"] = "differs"
                    with tempfile.NamedTemporaryFile(
                        mode="wb",
                        delete=False,
                        dir=root,
                    ) as temp_file:
                        temp_file.write(upstream_bytes)
                        temp_name = temp_file.name
                    try:
                        diff = run_cmd(
                            [
                                "git",
                                "diff",
                                "--no-index",
                                "--binary",
                                "--",
                                temp_name,
                                local_path,
                            ],
                            check=False,
                            ok_codes={0, 1},
                        )
                        comparison["diff"] = str(diff.stdout)
                        if "Binary files" in str(diff.stdout):
                            comparison["local_status"] = "binary_differs"
                    finally:
                        Path(temp_name).unlink(missing_ok=True)

        digest = hashlib.sha256(upstream_path.encode("utf-8")).hexdigest()[:16]
        artifact_name = f"{index:04d}-{digest}.diff"
        comparison["diff_artifact_name"] = artifact_name
        if comparison["diff"]:
            atomic_write_text(comparison_dir / artifact_name, comparison["diff"])
        comparisons.append(comparison)
    return comparisons


def all_changes_integrated(comparisons: Iterable[dict[str, Any]]) -> bool:
    """Return true only when each upstream state has the exact required local state."""

    seen = False
    for comparison in comparisons:
        seen = True
        if comparison["upstream_status"] == "deleted":
            if comparison["local_status"] != "missing":
                return False
        elif comparison["local_status"] != "identical":
            return False
    return seen


def get_commits(
    base_commit: str | None,
    head_commit: str,
    *,
    limit: int = 100,
) -> list[dict[str, str]]:
    """Return bounded commit context from the same effective comparison identity."""

    revision = f"{base_commit}..{head_commit}" if base_commit else head_commit
    result = run_cmd(
        ["git", "log", f"--max-count={limit}", "--format=%H%x00%s", revision]
    )
    commits: list[dict[str, str]] = []
    for line in str(result.stdout).splitlines():
        if not line:
            continue
        sha, _, subject = line.partition("\x00")
        if sha:
            commits.append({"sha": sha, "msg": subject})
    return commits


def enrich_pull_requests(
    upstream_repo: str,
    commits: list[dict[str, str]],
    max_lookups: int,
    warnings: list[str],
) -> list[dict[str, Any]]:
    """Best-effort PR enrichment with defensive ghost-user and payload handling."""

    pull_requests: dict[int, dict[str, Any]] = {}
    for commit in commits[: max(0, max_lookups)]:
        endpoint = f"repos/{upstream_repo}/commits/{commit['sha']}/pulls"
        try:
            raw = api_json(endpoint)
        except MonitorError as exc:
            warnings.append(
                f"Optional PR lookup failed for {commit['sha'][:12]}: {exc}"
            )
            continue
        if not isinstance(raw, list):
            warnings.append(
                f"Optional PR lookup returned {type(raw).__name__} for {commit['sha'][:12]}"
            )
            continue
        for item in raw:
            if not isinstance(item, dict):
                continue
            number = item.get("number")
            title = item.get("title")
            url = item.get("html_url")
            if (
                not isinstance(number, int)
                or not isinstance(title, str)
                or not isinstance(url, str)
            ):
                continue
            user = item.get("user")
            author = user.get("login") if isinstance(user, dict) else None
            pull_requests[number] = {
                "number": number,
                "title": title,
                "url": url,
                "author": author if isinstance(author, str) and author else "ghost",
                "merged_at": item.get("merged_at") or "",
                "body": item.get("body") or "",
            }
    return list(pull_requests.values())


def generate_fingerprint(
    upstream_repo: str,
    selection: ReleaseSelection,
    local_commit: str,
    diffstat: str,
    comparisons: list[dict[str, Any]],
) -> str:
    """Create a deterministic content fingerprint separate from issue identity."""

    digest = hashlib.sha256()
    digest.update(
        json.dumps(
            {
                "upstream_repo": upstream_repo,
                "head": selection.head_tag,
                "base": selection.base_tag,
                "mode": selection.comparison_mode,
                "local_commit": local_commit,
                "diffstat": diffstat,
            },
            sort_keys=True,
        ).encode("utf-8")
    )
    for comparison in comparisons:
        digest.update(
            json.dumps(
                {
                    "upstream_path": comparison["upstream_path"],
                    "local_path": comparison["local_path"],
                    "upstream_status": comparison["upstream_status"],
                    "local_status": comparison["local_status"],
                    "diff_sha256": hashlib.sha256(
                        comparison.get("diff", "").encode("utf-8", "replace")
                    ).hexdigest(),
                },
                sort_keys=True,
            ).encode("utf-8")
        )
    return digest.hexdigest()
