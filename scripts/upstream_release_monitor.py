"""Deterministic GitHub upstream-release monitor used by repository workflows."""

from __future__ import annotations

import argparse
import os
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Any

from upstream_monitor_common import (  # noqa: F401
    DEFAULT_UPSTREAM,
    EMPTY_TREE_SHA,
    SCHEMA_VERSION,
    FetchResult,
    IssueOutcome,
    MonitorError,
    ReleaseSelection,
    ensure_empty_tree,
    fetch_upstream,
    resolve_selection,
    run_cmd,
    validate_git_ref,
    validate_relative_path,
    validate_repo_format,
)
from upstream_monitor_git import (
    all_changes_integrated,
    atomic_write_json,
    atomic_write_text,
    compare_local_files,
    enrich_pull_requests,
    generate_diffs,
    generate_fingerprint,
    get_commits,
    safe_output_path,
)
from upstream_monitor_report import (
    build_markdown,
    escape_markdown,
    is_resolved_release,
    manage_issue,
    metadata_safe_comparisons,
)

# Re-export tested helpers from the focused implementation modules.
from upstream_monitor_common import (  # noqa: F401
    api_json,
    eligible_release,
    fetch_named_ref,
    fetch_release_page,
    latest_stable_release,
    normalize_release_payload,
    peel_commit,
    scan_release_order,
)
from upstream_monitor_git import (  # noqa: F401
    load_file_map,
    parse_name_status_z,
)
from upstream_monitor_report import (  # noqa: F401
    bounded_markdown,
    clean_fence,
    find_tracking_issue,
    issue_identity_marker,
    list_tracking_issues,
    load_resolved_entries,
    mutate_issue,
    neutralize_mentions,
    parse_resolved_entry,
    truncate_text,
)


def new_summary(args: argparse.Namespace) -> dict[str, Any]:
    """Create the stable metadata schema for every possible monitor outcome."""

    return {
        "schema_version": SCHEMA_VERSION,
        "result": "unknown",
        "exit_code": 1,
        "upstream_repo": args.upstream_repo,
        "requested_tags": {
            "head": args.head_tag,
            "base": args.base_tag,
        },
        "resolved_tags": {
            "head": None,
            "base": None,
        },
        "effective_refs": {
            "head": None,
            "base": None,
            "head_commit": None,
            "base_commit": None,
        },
        "comparison_mode": None,
        "local_commit": None,
        "changed_files_count": 0,
        "issue": {
            "action": None,
            "number": None,
            "url": None,
        },
        # Backward-compatible aliases used by existing summaries.
        "head_tag": args.head_tag,
        "base_tag": args.base_tag,
        "head_ref": None,
        "base_ref": None,
        "issue_action": None,
        "warnings": [],
        "errors": [],
        "skip_reason": None,
        "comparisons": [],
    }


def set_result(
    summary: dict[str, Any],
    result: str,
    *,
    exit_code: int = 0,
    skip_reason: str | None = None,
) -> None:
    """Set one explicit state-machine outcome in the stable summary."""

    summary["result"] = result
    summary["exit_code"] = exit_code
    summary["skip_reason"] = skip_reason


def issue_title(upstream_repo: str, selection: ReleaseSelection) -> str:
    """Build the canonical exact legacy-compatible issue title."""

    if selection.head_tag is None:
        raise MonitorError("Cannot create issue title without head tag")
    if selection.base_tag:
        return (
            f"Upstream release monitor: {upstream_repo} "
            f"{selection.base_tag}...{selection.head_tag}"
        )
    return f"Upstream release monitor: {upstream_repo} {selection.head_tag}"


def build_step_summary(summary: dict[str, Any]) -> str:
    """Render a concise stable Markdown summary for artifacts and GitHub UI."""

    lines = [
        "## Upstream monitor summary",
        "",
        f"- schema_version: {summary.get('schema_version')}",
        f"- result: {summary.get('result')}",
        f"- exit_code: {summary.get('exit_code')}",
        f"- upstream_repo: {summary.get('upstream_repo')}",
        f"- requested_head: {summary.get('requested_tags', {}).get('head')}",
        f"- requested_base: {summary.get('requested_tags', {}).get('base')}",
        f"- resolved_head: {summary.get('resolved_tags', {}).get('head')}",
        f"- resolved_base: {summary.get('resolved_tags', {}).get('base')}",
        f"- comparison_mode: {summary.get('comparison_mode')}",
        f"- changed_files_count: {summary.get('changed_files_count')}",
        f"- issue_action: {summary.get('issue', {}).get('action')}",
        f"- issue_number: {summary.get('issue', {}).get('number')}",
        f"- issue_url: {summary.get('issue', {}).get('url')}",
        f"- skip_reason: {summary.get('skip_reason')}",
    ]
    warnings = summary.get("warnings") or []
    errors = summary.get("errors") or []
    if warnings:
        lines.extend(["", "### Warnings", ""])
        lines.extend(f"- {escape_markdown(item)}" for item in warnings[:20])
        if len(warnings) > 20:
            lines.append(f"- ... and {len(warnings) - 20} additional warnings")
    if errors:
        lines.extend(["", "### Errors", ""])
        lines.extend(f"- {escape_markdown(item)}" for item in errors[:20])
        if len(errors) > 20:
            lines.append(f"- ... and {len(errors) - 20} additional errors")
    return "\n".join(lines) + "\n"


def write_run_outputs(
    args: argparse.Namespace,
    summary: dict[str, Any],
    *,
    report: str | None = None,
    patch: str | None = None,
) -> None:
    """Write the complete stable evidence package for every monitor outcome."""

    root = Path(args.out_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    metadata = dict(summary)
    metadata["requested_tags"] = dict(summary.get("requested_tags") or {})
    metadata["resolved_tags"] = dict(summary.get("resolved_tags") or {})
    metadata["effective_refs"] = dict(summary.get("effective_refs") or {})
    metadata["issue"] = dict(summary.get("issue") or {})
    metadata["warnings"] = list(summary.get("warnings") or [])
    metadata["errors"] = list(summary.get("errors") or [])
    metadata["comparisons"] = metadata_safe_comparisons(
        list(summary.get("comparisons") or [])
    )

    if report is None:
        if summary.get("errors"):
            report = (
                "## Upstream Release Monitor Failed\n\n"
                + "\n".join(f"- {escape_markdown(item)}" for item in summary["errors"])
                + "\n"
            )
        else:
            report = (
                "## Upstream Release Monitor\n\n"
                f"Result: `{summary.get('result')}`\n\n"
                f"Reason: `{summary.get('skip_reason') or 'none'}`\n"
            )

    step_summary = build_step_summary(summary)
    atomic_write_json(safe_output_path(root, "metadata.json"), metadata)
    atomic_write_text(
        safe_output_path(root, "upstream-monitor-report.md"),
        report.rstrip() + "\n",
    )
    atomic_write_text(
        safe_output_path(root, "upstream-release.diff"),
        patch or "",
    )
    atomic_write_text(safe_output_path(root, "step-summary.md"), step_summary)

    warnings = list(summary.get("warnings") or [])
    errors = list(summary.get("errors") or [])
    atomic_write_text(
        safe_output_path(root, "warnings.txt"),
        ("\n".join(warnings) + "\n") if warnings else "",
    )
    atomic_write_text(
        safe_output_path(root, "errors.txt"),
        ("\n".join(errors) + "\n") if errors else "",
    )

    github_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_summary:
        try:
            with Path(github_summary).open("a", encoding="utf-8") as handle:
                handle.write(step_summary)
        except OSError as exc:
            print(f"::warning::Could not append GITHUB_STEP_SUMMARY: {exc}")


def execute_monitor(args: argparse.Namespace) -> tuple[dict[str, Any], str | None, str]:
    """Execute the deterministic monitor state machine without losing evidence."""

    summary = new_summary(args)
    report: str | None = None
    patch = ""
    warnings: list[str] = summary["warnings"]

    try:
        validate_repo_format(args.repo)
        validate_repo_format(args.upstream_repo)
        if args.max_pr_lookups < 0:
            raise ValueError("--max-pr-lookups must be non-negative")
        Path(args.out_dir).resolve().mkdir(parents=True, exist_ok=True)

        selection = resolve_selection(args, warnings)
        summary["resolved_tags"] = {
            "head": selection.head_tag,
            "base": selection.base_tag,
        }
        summary["head_tag"] = selection.head_tag
        summary["base_tag"] = selection.base_tag
        summary["comparison_mode"] = selection.comparison_mode

        if selection.head_tag is None:
            set_result(
                summary,
                "skipped_no_releases",
                skip_reason="no_eligible_releases_found",
            )
            return summary, report, patch

        if (
            not args.dry_run
            and not args.force
            and is_resolved_release(
                args.upstream_repo,
                selection.head_tag,
                selection.base_tag,
            )
        ):
            set_result(
                summary,
                "skipped_resolved",
                skip_reason="resolved_in_file",
            )
            return summary, report, patch

        fetched = fetch_upstream(args.upstream_repo, selection)
        effective_base_ref = fetched.base_ref or ensure_empty_tree()
        effective_base_commit = fetched.base_commit or EMPTY_TREE_SHA
        summary["effective_refs"] = {
            "head": fetched.head_ref,
            "base": effective_base_ref,
            "head_commit": fetched.head_commit,
            "base_commit": effective_base_commit,
        }
        summary["head_ref"] = fetched.head_ref
        summary["base_ref"] = effective_base_ref

        stat, patch, changed_files = generate_diffs(
            effective_base_ref,
            fetched.head_ref,
        )
        summary["changed_files_count"] = len(changed_files)
        if not changed_files:
            set_result(
                summary,
                "skipped_no_changes",
                skip_reason="empty_upstream_delta",
            )
            return summary, report, patch

        comparisons = compare_local_files(changed_files, fetched.head_ref, args.out_dir)
        summary["comparisons"] = comparisons
        if not args.dry_run and not args.force and all_changes_integrated(comparisons):
            set_result(
                summary,
                "skipped_integrated",
                skip_reason="all_files_integrated",
            )
            return summary, report, patch

        local_commit_result = run_cmd(["git", "rev-parse", "HEAD"])
        local_commit = str(local_commit_result.stdout).strip()
        summary["local_commit"] = local_commit
        branch_result = run_cmd(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=False,
        )
        branch = (
            str(branch_result.stdout).strip()
            if branch_result.returncode == 0 and str(branch_result.stdout).strip()
            else os.environ.get("GITHUB_REF_NAME", "unknown")
        )

        commits = get_commits(
            fetched.base_commit,
            fetched.head_commit,
            limit=max(100, args.max_pr_lookups),
        )
        pull_requests = enrich_pull_requests(
            args.upstream_repo,
            commits,
            args.max_pr_lookups,
            warnings,
        )
        fingerprint = generate_fingerprint(
            args.upstream_repo,
            selection,
            local_commit,
            stat,
            comparisons,
        )
        summary["fingerprint"] = fingerprint
        report = build_markdown(
            args,
            selection,
            fetched,
            stat,
            patch,
            changed_files,
            comparisons,
            commits,
            pull_requests,
            fingerprint,
            local_commit,
            branch,
            warnings,
        )

        outcome = manage_issue(
            args,
            issue_title(args.upstream_repo, selection),
            report,
            fingerprint,
            selection.head_tag,
        )
        summary["issue"] = asdict(outcome)
        summary["issue_action"] = outcome.action
        if outcome.action in {
            "created",
            "updated",
            "reopened_updated",
            "dry_run",
            "skipped_closed",
            "skipped_duplicate",
        }:
            set_result(summary, outcome.action)
        else:
            raise MonitorError(f"Unexpected issue outcome: {outcome.action}")
        return summary, report, patch
    except (MonitorError, ValueError, OSError, UnicodeError) as exc:
        message = str(exc)
        print(f"::error::{message}")
        summary["errors"].append(message)
        set_result(summary, "failed", exit_code=1)
        return summary, report, patch


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for workflow and local execution."""

    parser = argparse.ArgumentParser(description="Upstream Release Monitor")
    parser.add_argument("--repo", required=True, help="Local repository owner/name")
    parser.add_argument("--upstream-repo", required=True, help="Upstream owner/name")
    parser.add_argument("--head-tag", help="Exact upstream head tag/ref")
    parser.add_argument("--base-tag", help="Exact upstream base tag/ref")
    parser.add_argument(
        "--include-prerelease",
        action="store_true",
        help="Include prereleases in automatic selection order",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass resolved/integrated/closed/duplicate suppression, never errors",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate a full report without issue mutation",
    )
    parser.add_argument(
        "--out-dir",
        default="artifacts",
        help="Directory for the complete evidence package",
    )
    parser.add_argument(
        "--max-pr-lookups",
        type=int,
        default=20,
        help="Maximum commit-to-PR enrichment requests",
    )
    return parser


def main() -> int:
    """Run the monitor and guarantee a stable evidence package on unexpected failures."""

    args = build_parser().parse_args()
    Path(args.out_dir).resolve().mkdir(parents=True, exist_ok=True)
    try:
        summary, report, patch = execute_monitor(args)
    except Exception as exc:  # noqa: BLE001 -- top-level evidence guarantee
        print(f"::error::Unexpected monitor failure: {exc}")
        traceback.print_exc()
        summary = new_summary(args)
        summary["errors"].append(f"Unexpected monitor failure: {exc}")
        set_result(summary, "failed", exit_code=1)
        report = None
        patch = ""
    try:
        write_run_outputs(args, summary, report=report, patch=patch)
    except Exception as exc:  # noqa: BLE001 -- last-resort process failure
        print(f"::error::Failed to write monitor evidence: {exc}")
        traceback.print_exc()
        return 1
    return int(summary.get("exit_code", 1))


if __name__ == "__main__":
    raise SystemExit(main())
