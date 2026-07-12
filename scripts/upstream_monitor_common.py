"""Shared validation, API, release-selection, and ref-fetching primitives."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

DEFAULT_UPSTREAM = "droserasprout/io.drsr.hotspotadb"
EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
SCHEMA_VERSION = 2
RELEASE_PAGE_SIZE = 100
MAX_RELEASE_PAGES = 20
ISSUE_PAGE_SIZE = 100
MAX_ISSUE_PAGES = 50
ISSUE_BODY_LIMIT = 60_000
FINGERPRINT_RE = re.compile(r"<!-- upstream-monitor:fingerprint:([a-f0-9]{64}) -->")
REPO_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?/[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?$"
)


@dataclass(frozen=True)
class ReleaseSelection:
    """Requested and resolved release identity for one monitor run."""

    requested_head: str | None
    requested_base: str | None
    head_tag: str | None
    base_tag: str | None
    head_explicit: bool
    base_explicit: bool
    comparison_mode: str


@dataclass(frozen=True)
class FetchResult:
    """Effective fetched refs and peeled commit identifiers."""

    head_ref: str
    head_commit: str
    base_ref: str | None
    base_commit: str | None


@dataclass(frozen=True)
class IssueOutcome:
    """Result of exact tracking-issue lookup or mutation."""

    action: str
    number: int | None = None
    url: str | None = None


class MonitorError(RuntimeError):
    """Expected operational monitor failure with a user-facing explanation."""


def run_cmd(
    cmd: Sequence[str | Path],
    *,
    check: bool = True,
    timeout: float = 120.0,
    capture_output: bool = True,
    cwd: str | Path | None = None,
    ok_codes: set[int] | None = None,
    text: bool = True,
    input_data: str | bytes | None = None,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    """Run a bounded subprocess without a shell and report useful failure context."""

    if not cmd:
        raise ValueError("Command sequence cannot be empty")
    args = [str(value) for value in cmd]
    display = shlex.join(args)
    accepted = ok_codes or {0}
    try:
        result = subprocess.run(  # nosec B603 -- fixed argv and shell=False
            args,
            check=False,
            timeout=timeout,
            capture_output=capture_output,
            text=text,
            encoding="utf-8" if text else None,
            errors="replace" if text else None,
            cwd=cwd,
            shell=False,
            input=input_data,
        )
    except subprocess.TimeoutExpired as exc:
        print(f"::error::Command timed out after {timeout:g}s: {display}")
        raise MonitorError(f"Command timed out after {timeout:g}s: {display}") from exc

    if check and result.returncode not in accepted:
        print(f"::error::Command failed ({result.returncode}): {display}")
        if capture_output:
            stdout = result.stdout or b"" if not text else result.stdout or ""
            stderr = result.stderr or b"" if not text else result.stderr or ""
            if not text:
                stdout = bytes(stdout).decode("utf-8", "replace")
                stderr = bytes(stderr).decode("utf-8", "replace")
            if stdout:
                print(f"stdout:\n{str(stdout)[:2000]}")
            if stderr:
                print(f"stderr:\n{str(stderr)[:2000]}")
        raise MonitorError(f"Command failed ({result.returncode}): {display}")
    return result


def validate_repo_format(repo: str) -> None:
    """Validate a GitHub owner/repository identifier before using it anywhere."""

    if not isinstance(repo, str) or not REPO_RE.fullmatch(repo):
        raise ValueError(f"Invalid repository format: {repo!r}")


def validate_git_ref(ref: str) -> None:
    """Reject unsafe or invalid Git reference names before passing them to Git."""

    if not isinstance(ref, str) or not ref or len(ref) > 255:
        raise ValueError(f"Invalid git ref: {ref!r}")
    invalid_fragments = ("..", "@{", "//", "\\")
    invalid_chars = set(" ~^:?*[")
    if (
        ref.startswith(("-", "/", "."))
        or ref.endswith(("/", ".", ".lock"))
        or any(fragment in ref for fragment in invalid_fragments)
        or any(ord(ch) < 32 or ord(ch) == 127 or ch in invalid_chars for ch in ref)
    ):
        raise ValueError(f"Invalid git ref: {ref!r}")
    for component in ref.split("/"):
        if not component or component.startswith(".") or component.endswith(".lock"):
            raise ValueError(f"Invalid git ref: {ref!r}")


def validate_relative_path(value: str, *, label: str) -> str:
    """Validate a repository-relative POSIX path used in mappings and artifacts."""

    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError(f"Invalid {label}: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


def api_json(
    endpoint: str,
    *,
    method: str = "GET",
    input_path: Path | None = None,
    timeout: float = 60.0,
) -> Any:
    """Call GitHub through gh and decode a JSON response with strict error handling."""

    cmd = ["gh", "api", "--method", method, endpoint]
    if input_path is not None:
        cmd.extend(["--input", str(input_path)])
    result = run_cmd(cmd, timeout=timeout)
    try:
        return json.loads(str(result.stdout))
    except json.JSONDecodeError as exc:
        raise MonitorError(
            f"GitHub API returned invalid JSON for {method} {endpoint}"
        ) from exc


def normalize_release_payload(raw: Any) -> list[dict[str, Any]]:
    """Flatten supported release payload shapes and ignore malformed release entries."""

    if not isinstance(raw, list):
        return []
    releases: list[dict[str, Any]] = []
    for item in raw:
        candidates = item if isinstance(item, list) else [item]
        for candidate in candidates:
            if isinstance(candidate, dict) and isinstance(
                candidate.get("tag_name"), str
            ):
                releases.append(candidate)
    return releases


def eligible_release(release: dict[str, Any], include_prerelease: bool) -> bool:
    """Return whether a release participates in the requested ordering."""

    if release.get("draft") is True:
        return False
    if release.get("prerelease") is True and not include_prerelease:
        return False
    return isinstance(release.get("tag_name"), str) and bool(release["tag_name"])


def fetch_release_page(upstream_repo: str, page: int) -> list[dict[str, Any]]:
    """Fetch one releases API page and reject unexpected response types."""

    raw = api_json(
        f"repos/{upstream_repo}/releases?per_page={RELEASE_PAGE_SIZE}&page={page}"
    )
    if not isinstance(raw, list):
        raise MonitorError(
            f"Unexpected releases API response: expected list, got {type(raw).__name__}"
        )
    return normalize_release_payload(raw)


def latest_stable_release(upstream_repo: str) -> dict[str, Any] | None:
    """Resolve GitHub's documented latest stable release endpoint semantics."""

    try:
        raw = api_json(f"repos/{upstream_repo}/releases/latest")
    except MonitorError as exc:
        # A repository with no stable release returns 404. Scan only until either a
        # stable release is found or pagination ends. If a stable release exists,
        # the latest endpoint failure is operational and must remain visible.
        for page in range(1, MAX_RELEASE_PAGES + 1):
            releases = fetch_release_page(upstream_repo, page)
            if any(eligible_release(item, False) for item in releases):
                raise MonitorError(
                    "Latest stable release lookup failed despite an eligible stable release"
                ) from exc
            if len(releases) < RELEASE_PAGE_SIZE:
                return None
        raise MonitorError(
            "Unable to prove that the upstream repository has no stable releases "
            f"within {MAX_RELEASE_PAGES} pages"
        ) from exc
    if not isinstance(raw, dict):
        raise MonitorError(
            "Unexpected latest-release API response: "
            f"expected object, got {type(raw).__name__}"
        )
    if not eligible_release(raw, include_prerelease=False):
        raise MonitorError(
            "GitHub latest-release endpoint returned an ineligible release"
        )
    return raw


def scan_release_order(
    upstream_repo: str,
    *,
    include_prerelease: bool,
    head_tag: str | None,
    max_pages: int = MAX_RELEASE_PAGES,
) -> tuple[str | None, str | None]:
    """Scan API order only until the requested head and immediately preceding release are known."""

    resolved_head = head_tag
    found_head = False
    for page in range(1, max_pages + 1):
        releases = fetch_release_page(upstream_repo, page)
        for release in releases:
            if not eligible_release(release, include_prerelease):
                continue
            tag = release["tag_name"]
            if resolved_head is None:
                resolved_head = tag
                found_head = True
                continue
            if not found_head:
                if tag == resolved_head:
                    found_head = True
                continue
            if tag != resolved_head:
                return resolved_head, tag
        if len(releases) < RELEASE_PAGE_SIZE:
            break
    return resolved_head, None


def resolve_selection(
    args: argparse.Namespace, warnings: list[str]
) -> ReleaseSelection:
    """Resolve requested/automatic head and base tags into a deterministic identity."""

    requested_head = args.head_tag
    requested_base = args.base_tag
    if requested_head:
        validate_git_ref(requested_head)
    if requested_base:
        validate_git_ref(requested_base)

    head = requested_head
    base = requested_base
    if head is None:
        if args.include_prerelease:
            head, inferred = scan_release_order(
                args.upstream_repo,
                include_prerelease=True,
                head_tag=None,
            )
            if base is None:
                base = inferred
        else:
            latest = latest_stable_release(args.upstream_repo)
            if latest is None:
                return ReleaseSelection(
                    requested_head,
                    requested_base,
                    None,
                    base,
                    False,
                    requested_base is not None,
                    "no_releases",
                )
            head = latest["tag_name"]
            if base is None:
                _, base = scan_release_order(
                    args.upstream_repo,
                    include_prerelease=False,
                    head_tag=head,
                )
    elif base is None:
        _, base = scan_release_order(
            args.upstream_repo,
            include_prerelease=args.include_prerelease,
            head_tag=head,
        )
        if base is None:
            warnings.append(
                f"No preceding eligible release found for {head}; comparing the full head tree against an empty tree."
            )

    if head is not None:
        validate_git_ref(head)
    if base is not None:
        validate_git_ref(base)
    if head is not None and base == head:
        raise ValueError("Base and head refs must be different")
    return ReleaseSelection(
        requested_head,
        requested_base,
        head,
        base,
        requested_head is not None,
        requested_base is not None,
        "range" if base else "first_release_empty_tree",
    )


def ensure_remote(upstream_repo: str) -> None:
    """Create or update the deterministic upstream remote URL."""

    url = f"https://github.com/{upstream_repo}.git"
    result = run_cmd(["git", "remote", "add", "upstream", url], check=False)
    if result.returncode != 0:
        run_cmd(["git", "remote", "set-url", "upstream", url])


def fetch_named_ref(ref: str, local_ref: str) -> bool:
    """Fetch an exact tag first, then a validated generic ref/commit fallback."""

    exact = run_cmd(
        ["git", "fetch", "--no-tags", "upstream", f"+refs/tags/{ref}:{local_ref}"],
        check=False,
        timeout=120.0,
    )
    if exact.returncode == 0:
        return True
    fallback = run_cmd(
        ["git", "fetch", "--no-tags", "upstream", f"+{ref}:{local_ref}"],
        check=False,
        timeout=120.0,
    )
    return fallback.returncode == 0


def peel_commit(ref: str) -> str:
    """Resolve a fetched annotated/lightweight ref to an exact commit SHA."""

    result = run_cmd(["git", "rev-parse", f"{ref}^{{commit}}"])
    commit = str(result.stdout).strip()
    if not re.fullmatch(r"[a-f0-9]{40,64}", commit):
        raise MonitorError(f"Fetched ref did not resolve to a commit: {ref}")
    return commit


def fetch_upstream(upstream_repo: str, selection: ReleaseSelection) -> FetchResult:
    """Fetch and peel the resolved release refs, failing on every selected-ref error."""

    if selection.head_tag is None:
        raise MonitorError("Cannot fetch an empty head ref")
    ensure_remote(upstream_repo)
    head_ref = "refs/upstream-monitor/head"
    base_ref = "refs/upstream-monitor/base" if selection.base_tag else None

    print(f"Fetching head ref {selection.head_tag}...")
    if not fetch_named_ref(selection.head_tag, head_ref):
        raise MonitorError(f"Failed to fetch head ref {selection.head_tag!r}")
    head_commit = peel_commit(head_ref)

    base_commit = None
    if selection.base_tag and base_ref:
        print(f"Fetching base ref {selection.base_tag}...")
        if not fetch_named_ref(selection.base_tag, base_ref):
            kind = "explicit" if selection.base_explicit else "automatically selected"
            raise MonitorError(
                f"Failed to fetch {kind} base ref {selection.base_tag!r}; refusing a misleading empty-tree downgrade"
            )
        base_commit = peel_commit(base_ref)

    return FetchResult(head_ref, head_commit, base_ref, base_commit)


def ensure_empty_tree() -> str:
    """Create Git's empty tree object locally and verify its canonical hash."""

    result = run_cmd(
        ["git", "hash-object", "-t", "tree", "-w", "--stdin"],
        input_data="",
    )
    value = str(result.stdout).strip()
    if value != EMPTY_TREE_SHA:
        raise MonitorError(f"Unexpected empty-tree hash: {value}")
    return value
