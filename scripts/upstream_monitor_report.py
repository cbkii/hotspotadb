"""Safe report rendering, resolved-tag parsing, and tracking-issue lifecycle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

from upstream_monitor_common import (
    DEFAULT_UPSTREAM,
    EMPTY_TREE_SHA,
    FINGERPRINT_RE,
    ISSUE_BODY_LIMIT,
    ISSUE_PAGE_SIZE,
    MAX_ISSUE_PAGES,
    FetchResult,
    IssueOutcome,
    MonitorError,
    ReleaseSelection,
    api_json,
    validate_git_ref,
    validate_repo_format,
)


def truncate_text(text: Any, max_len: int = 1000) -> str:
    """Return a deterministic bounded string with an explicit truncation marker."""

    value = "" if text is None else str(text)
    if len(value) <= max_len:
        return value
    return value[:max_len] + "\n... (truncated)"


def neutralize_mentions(text: Any) -> str:
    """Prevent untrusted upstream text from generating GitHub user/team mentions."""

    return str(text or "").replace("@", "@\u200b")


def escape_markdown(text: Any, *, table: bool = False) -> str:
    """Escape untrusted Markdown text for prose or table-cell use."""

    value = neutralize_mentions(text)
    value = value.replace("<", "&lt;").replace(">", "&gt;")
    if table:
        value = value.replace("|", "\\|").replace("\r", " ").replace("\n", "<br>")
    return value


def clean_fence(text: Any) -> str:
    """Prevent untrusted text from closing a generated fenced code block."""

    return neutralize_mentions(text).replace("```", "``\u200b`")


def encoded_ref(ref: str) -> str:
    """URL-encode a Git ref as one path component."""

    return urllib.parse.quote(ref, safe="")


def encoded_path(path: str) -> str:
    """URL-encode a repository path while preserving path separators."""

    return urllib.parse.quote(path, safe="/")


def fetch_release_notes(
    upstream_repo: str,
    head_tag: str,
    warnings: list[str],
) -> dict[str, Any] | None:
    """Best-effort release-note enrichment with recorded failures."""

    try:
        raw = api_json(f"repos/{upstream_repo}/releases/tags/{encoded_ref(head_tag)}")
    except MonitorError as exc:
        warnings.append(f"Optional release-note lookup failed: {exc}")
        return None
    if not isinstance(raw, dict):
        warnings.append(
            f"Optional release-note lookup returned {type(raw).__name__}, expected object"
        )
        return None
    return raw


def bounded_markdown(
    body: str, markers: list[str], limit: int = ISSUE_BODY_LIMIT
) -> str:
    """Enforce a conservative total issue-body budget while preserving machine markers."""

    marker_block = "\n\n" + "\n".join(markers) + "\n"
    candidate = body.rstrip() + marker_block
    if len(candidate) <= limit:
        return candidate
    notice = (
        "\n\n> Report truncated to fit GitHub's issue-body limit. "
        "Full patch, metadata, and per-file comparisons are available in workflow artifacts.\n"
    )
    allowance = limit - len(marker_block) - len(notice)
    if allowance <= 0:
        raise MonitorError("Issue-body limit is too small for required machine markers")
    prefix = body[:allowance]
    newline = prefix.rfind("\n")
    if newline > allowance // 2:
        prefix = prefix[:newline]
    if prefix.count("```") % 2:
        prefix += "\n```"
    result = prefix.rstrip() + notice + marker_block
    if len(result) > limit:
        raise MonitorError("Unable to fit issue body within configured budget")
    return result


def build_markdown(
    args: argparse.Namespace,
    selection: ReleaseSelection,
    fetch_result: FetchResult,
    stat: str,
    patch: str,
    changed_files: list[dict[str, str]],
    comparisons: list[dict[str, Any]],
    commits: list[dict[str, str]],
    pull_requests: list[dict[str, Any]],
    fingerprint: str,
    local_commit: str,
    branch: str,
    warnings: list[str],
) -> str:
    """Build a bounded, injection-safe issue/report summary backed by full artifacts."""

    if selection.head_tag is None:
        raise MonitorError("Cannot build a report without a head tag")
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    run_url = f"https://github.com/{args.repo}/actions/runs/{run_id}"
    head_url = f"https://github.com/{args.upstream_repo}/tree/{encoded_ref(selection.head_tag)}"
    lines = [
        "A new upstream release/change range was detected.",
        "",
        "## Summary",
        "",
        f"- Upstream repo: `{escape_markdown(args.upstream_repo)}`",
        f"- Requested head: `{escape_markdown(selection.requested_head or '<automatic>')}`",
        f"- Requested base: `{escape_markdown(selection.requested_base or '<automatic>')}`",
        f"- Resolved head: [`{escape_markdown(selection.head_tag)}`]({head_url})",
        f"- Resolved base: `{escape_markdown(selection.base_tag or '<empty tree>')}`",
        f"- Comparison mode: `{selection.comparison_mode}`",
        f"- Effective head commit: `{fetch_result.head_commit}`",
        f"- Effective base commit: `{fetch_result.base_commit or EMPTY_TREE_SHA}`",
        f"- Local branch/commit: `{escape_markdown(branch)}` / `{local_commit}`",
        f"- Workflow run: {run_url}",
        f"- Force mode: `{args.force}`",
        f"- Dry-run mode: `{args.dry_run}`",
        f"- Fingerprint: `{fingerprint}`",
        "",
    ]

    release = fetch_release_notes(args.upstream_repo, selection.head_tag, warnings)
    if release:
        release_url = release.get("html_url") or head_url
        lines.extend(
            [
                "## Release notes",
                "",
                f"**{escape_markdown(release.get('name') or selection.head_tag)}** "
                f"({escape_markdown(release.get('published_at') or '')})",
                f"[Release URL]({release_url})",
                "",
                "```text",
                clean_fence(truncate_text(release.get("body") or "", 2500)),
                "```",
                "",
            ]
        )

    lines.extend(["## Upstream commit context", ""])
    for commit in commits[:20]:
        commit_url = f"https://github.com/{args.upstream_repo}/commit/{commit['sha']}"
        lines.append(
            f"- [{commit['sha'][:12]}]({commit_url}) {escape_markdown(commit['msg'])}"
        )
    if len(commits) > 20:
        lines.append(
            f"- ... and {len(commits) - 20} additional commits in artifacts/range."
        )
    lines.append("")

    if pull_requests:
        lines.extend(["## Upstream PR context", ""])
        for pull_request in pull_requests[:10]:
            lines.append(
                f"- [#{pull_request['number']}]({pull_request['url']}) "
                f"**{escape_markdown(pull_request['title'])}** by "
                f"`{escape_markdown(pull_request['author'])}`"
            )
            if pull_request.get("body"):
                lines.extend(
                    [
                        "```text",
                        clean_fence(truncate_text(pull_request["body"], 300)),
                        "```",
                    ]
                )
        if len(pull_requests) > 10:
            lines.append(f"- ... and {len(pull_requests) - 10} additional PRs omitted.")
        lines.append("")

    lines.extend(
        [
            "## Changed upstream files",
            "",
            "| Status | Upstream file | Local equivalent | Upstream latest | Upstream previous | Local file |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    table_limit = 100
    for comparison in comparisons[:table_limit]:
        upstream_path = comparison["upstream_path"]
        local_path = comparison["local_path"]
        latest_url = (
            f"https://github.com/{args.upstream_repo}/blob/"
            f"{encoded_ref(selection.head_tag)}/{encoded_path(upstream_path)}"
        )
        previous_url = ""
        if selection.base_tag and comparison["upstream_status"] not in {
            "added",
            "copied",
        }:
            previous_path = comparison.get("old_upstream_path", upstream_path)
            previous_url = (
                f"https://github.com/{args.upstream_repo}/blob/"
                f"{encoded_ref(selection.base_tag)}/{encoded_path(previous_path)}"
            )
        local_url = f"https://github.com/{args.repo}/blob/{local_commit}/{encoded_path(local_path)}"
        lines.append(
            "| "
            f"{escape_markdown(comparison['upstream_status'], table=True)} | "
            f"`{escape_markdown(upstream_path, table=True)}` | "
            f"`{escape_markdown(local_path, table=True)}` | "
            f"{'[link](' + latest_url + ')' if comparison['upstream_status'] != 'deleted' else 'N/A'} | "
            f"{'[link](' + previous_url + ')' if previous_url else 'N/A'} | "
            f"[link]({local_url}) |"
        )
    if len(comparisons) > table_limit:
        lines.append(
            f"\n{len(comparisons) - table_limit} additional changed-file rows omitted; see metadata/artifacts."
        )

    lines.extend(
        [
            "",
            "## Upstream release-to-release diffstat",
            "",
            "```text",
            clean_fence(truncate_text(stat or "No stat available", 4000)),
            "```",
            "",
            "## Upstream release-to-release diff excerpt",
            "",
            "```diff",
            clean_fence(truncate_text(patch or "No diff available", 8000)),
            "```",
            "",
            "The complete patch is stored in `upstream-release.diff`.",
            "",
            "## Equivalent-file comparisons",
            "",
        ]
    )
    comparison_limit = 20
    for comparison in comparisons[:comparison_limit]:
        lines.extend(
            [
                f"### `{escape_markdown(comparison['upstream_path'])}`",
                f"- Local equivalent: `{escape_markdown(comparison['local_path'])}`",
                f"- Upstream status: `{escape_markdown(comparison['upstream_status'])}`",
                f"- Local status: `{escape_markdown(comparison['local_status'])}`",
                f"- Full comparison artifact: `{comparison['diff_artifact_name']}`",
                "",
            ]
        )
        if comparison.get("diff"):
            lines.extend(
                [
                    "```diff",
                    clean_fence(truncate_text(comparison["diff"], 1200)),
                    "```",
                    "",
                ]
            )
    if len(comparisons) > comparison_limit:
        lines.append(
            f"{len(comparisons) - comparison_limit} additional comparison sections omitted; see per-file artifacts."
        )
        lines.append("")

    clone_cmd = shlex.join(["git", "clone", f"https://github.com/{args.repo}.git"])
    remote_cmd = shlex.join(
        [
            "git",
            "remote",
            "add",
            "upstream",
            f"https://github.com/{args.upstream_repo}.git",
        ]
    )
    fetch_cmd = shlex.join(["git", "fetch", "upstream", "--tags"])
    diff_cmd = shlex.join(
        [
            "git",
            "diff",
            selection.base_tag or EMPTY_TREE_SHA,
            selection.head_tag,
        ]
    )
    lines.extend(
        [
            "## Reproduce locally",
            "",
            "```bash",
            clone_cmd,
            f"cd {shlex.quote(args.repo.split('/', 1)[1])}",
            remote_cmd,
            fetch_cmd,
            diff_cmd,
            "```",
            "",
            "## Checklist",
            "",
            "- [ ] Review release notes and commit/PR context",
            "- [ ] Inspect changed upstream files and full artifacts",
            "- [ ] Decide which changes should be ported",
            "- [ ] Add the exact resolved tag/range to `.github/upstream-release-resolved-tags.txt`",
            "- [ ] Close this tracking issue when triage is complete",
            "",
            f"<!-- upstream-monitor:fingerprint:{fingerprint} -->",
        ]
    )
    return "\n".join(lines)


def parse_resolved_entry(line: str) -> tuple[str | None, str | None, str]:
    """Parse one strict resolved-tag grammar entry into repo/base/head components."""

    repo: str | None = None
    identity = line
    if "@" in line:
        repo, identity = line.split("@", 1)
        validate_repo_format(repo)
    if ".." in identity:
        if identity.count("..") != 1:
            raise ValueError(f"Invalid resolved range entry: {line!r}")
        base, head = identity.split("..", 1)
        validate_git_ref(base)
        validate_git_ref(head)
        return repo, base, head
    validate_git_ref(identity)
    return repo, None, identity


def load_resolved_entries(path: Path) -> list[tuple[str | None, str | None, str]]:
    """Read strict resolved entries; malformed or non-UTF-8 content is an error."""

    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise MonitorError(f"Failed to read resolved-tags file {path}: {exc}") from exc
    entries: list[tuple[str | None, str | None, str]] = []
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            entries.append(parse_resolved_entry(line))
        except ValueError as exc:
            raise MonitorError(
                f"Malformed resolved-tags entry at {path}:{line_number}: {line!r}"
            ) from exc
    return entries


def is_resolved_release(
    upstream_repo: str,
    head_tag: str,
    base_tag: str | None,
    *,
    path: Path = Path(".github/upstream-release-resolved-tags.txt"),
    default_upstream: str = DEFAULT_UPSTREAM,
) -> bool:
    """Apply exact resolved-entry matching with default/override repository isolation."""

    for entry_repo, entry_base, entry_head in load_resolved_entries(path):
        effective_repo = entry_repo or default_upstream
        if effective_repo != upstream_repo or entry_head != head_tag:
            continue
        if entry_base is None:
            return True
        if base_tag is not None and entry_base == base_tag:
            return True
    return False


def issue_identity_marker(upstream_repo: str, head_tag: str) -> str:
    """Build a stable machine identity marker independent of report content."""

    key = hashlib.sha256(f"{upstream_repo}\0{head_tag}".encode("utf-8")).hexdigest()
    return f"<!-- upstream-monitor:identity:{key} -->"


def list_tracking_issues(repo: str) -> list[dict[str, Any]]:
    """Enumerate repository issues through paginated REST data, never search indexes."""

    issues: list[dict[str, Any]] = []
    for page in range(1, MAX_ISSUE_PAGES + 1):
        raw = api_json(
            f"repos/{repo}/issues?state=all&per_page={ISSUE_PAGE_SIZE}&page={page}"
        )
        if not isinstance(raw, list):
            raise MonitorError(
                "Unexpected issues API response: "
                f"expected list, got {type(raw).__name__}"
            )
        for item in raw:
            if not isinstance(item, dict) or "pull_request" in item:
                continue
            issues.append(item)
        if len(raw) < ISSUE_PAGE_SIZE:
            return issues
    raise MonitorError(
        f"Issue enumeration exceeded {MAX_ISSUE_PAGES * ISSUE_PAGE_SIZE} records; "
        "refusing an incomplete identity lookup"
    )


def find_tracking_issue(
    issues: list[dict[str, Any]],
    *,
    identity_marker: str,
    exact_title: str,
) -> dict[str, Any] | None:
    """Find exactly one canonical issue by marker, with unambiguous title migration."""

    marker_matches = [
        issue for issue in issues if identity_marker in str(issue.get("body") or "")
    ]
    if len(marker_matches) > 1:
        numbers = [issue.get("number") for issue in marker_matches]
        raise MonitorError(
            f"Multiple issues contain the same identity marker: {numbers}"
        )
    if marker_matches:
        return marker_matches[0]

    title_matches = [issue for issue in issues if issue.get("title") == exact_title]
    if len(title_matches) > 1:
        numbers = [issue.get("number") for issue in title_matches]
        raise MonitorError(
            f"Ambiguous legacy issue migration for title {exact_title!r}: {numbers}"
        )
    return title_matches[0] if title_matches else None


def write_api_payload(out_dir: Path, payload: dict[str, Any]) -> Path:
    """Write a temporary GitHub API request body inside the configured output directory."""

    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".json",
        delete=False,
        dir=out_dir,
    ) as handle:
        json.dump(payload, handle)
        return Path(handle.name)


def mutate_issue(
    repo: str,
    *,
    out_dir: Path,
    number: int | None,
    title: str,
    body: str,
    reopen: bool = False,
) -> dict[str, Any]:
    """Create or atomically update the canonical issue body through REST."""

    payload: dict[str, Any] = {"title": title, "body": body}
    method = "POST"
    endpoint = f"repos/{repo}/issues"
    if number is not None:
        method = "PATCH"
        endpoint = f"repos/{repo}/issues/{number}"
        if reopen:
            payload["state"] = "open"
    payload_path = write_api_payload(out_dir, payload)
    try:
        raw = api_json(endpoint, method=method, input_path=payload_path)
    finally:
        payload_path.unlink(missing_ok=True)
    if not isinstance(raw, dict):
        raise MonitorError(
            f"Issue mutation returned {type(raw).__name__}, expected object"
        )
    if not isinstance(raw.get("number"), int) or not isinstance(
        raw.get("html_url"), str
    ):
        raise MonitorError("Issue mutation response omitted number/html_url")
    return raw


def manage_issue(
    args: argparse.Namespace,
    title: str,
    report_body: str,
    fingerprint: str,
    head_tag: str,
) -> IssueOutcome:
    """Perform exact idempotent tracking-issue suppression, update, reopen, or create."""

    if args.dry_run:
        print("Dry run: issue mutation skipped after full report generation.")
        return IssueOutcome("dry_run")

    identity_marker = issue_identity_marker(args.upstream_repo, head_tag)
    fingerprint_marker = f"<!-- upstream-monitor:fingerprint:{fingerprint} -->"
    body_without_markers = FINGERPRINT_RE.sub("", report_body).rstrip()
    full_body = bounded_markdown(
        body_without_markers,
        [fingerprint_marker, identity_marker],
    )
    existing = find_tracking_issue(
        list_tracking_issues(args.repo),
        identity_marker=identity_marker,
        exact_title=title,
    )
    out_dir = Path(args.out_dir).resolve()

    if existing is None:
        created = mutate_issue(
            args.repo,
            out_dir=out_dir,
            number=None,
            title=title,
            body=full_body,
        )
        print(f"Created tracking issue #{created['number']}: {created['html_url']}")
        return IssueOutcome("created", created["number"], created["html_url"])

    number = existing.get("number")
    url = existing.get("html_url")
    state = str(existing.get("state") or "").lower()
    if not isinstance(number, int):
        raise MonitorError("Canonical issue record omitted an integer number")
    if not isinstance(url, str):
        url = f"https://github.com/{args.repo}/issues/{number}"

    if state == "closed" and not args.force:
        print(f"Issue #{number} is closed; treating the release as resolved.")
        return IssueOutcome("skipped_closed", number, url)

    current_body = str(existing.get("body") or "")
    fingerprint_match = FINGERPRINT_RE.search(current_body)
    if (
        fingerprint_match
        and fingerprint_match.group(1) == fingerprint
        and not args.force
    ):
        print(f"Issue #{number} already contains the current fingerprint.")
        return IssueOutcome("skipped_duplicate", number, url)

    updated = mutate_issue(
        args.repo,
        out_dir=out_dir,
        number=number,
        title=title,
        body=full_body,
        reopen=state == "closed",
    )
    action = "reopened_updated" if state == "closed" else "updated"
    print(f"{action.replace('_', ' ').title()} issue #{number}: {updated['html_url']}")
    return IssueOutcome(action, number, updated["html_url"])


def metadata_safe_comparisons(
    comparisons: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Copy comparisons for metadata without destructively retaining full diff bodies."""

    safe: list[dict[str, Any]] = []
    for comparison in comparisons:
        entry = dict(comparison)
        diff = str(entry.pop("diff", ""))
        entry["diff_excerpt"] = truncate_text(diff, 500)
        entry["diff_omitted"] = bool(diff)
        safe.append(entry)
    return safe
