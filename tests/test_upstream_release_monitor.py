"""Focused regression suite for the deterministic upstream-release monitor."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import upstream_release_monitor as urm  # noqa: E402


class Args(argparse.Namespace):
    """Complete monitor argument namespace for tests."""

    def __init__(self, **overrides: object) -> None:
        values: dict[str, object] = {
            "repo": "cbkii/hotspotadb",
            "upstream_repo": urm.DEFAULT_UPSTREAM,
            "head_tag": None,
            "base_tag": None,
            "include_prerelease": False,
            "force": False,
            "dry_run": True,
            "out_dir": "artifacts",
            "max_pr_lookups": 20,
        }
        values.update(overrides)
        super().__init__(**values)


class IsolatedTest(unittest.TestCase):
    """Run each test in an isolated directory and environment."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_cwd = Path.cwd()
        self.old_summary = os.environ.pop("GITHUB_STEP_SUMMARY", None)
        os.chdir(self.root)

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        if self.old_summary is None:
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
        else:
            os.environ["GITHUB_STEP_SUMMARY"] = self.old_summary
        self.temp.cleanup()

    def init_repo(self, branch: str = "main") -> None:
        """Initialize Git deterministically for clean CI workers."""

        urm.run_cmd(["git", "init", "-b", branch])
        urm.run_cmd(["git", "config", "user.name", "Monitor Tests"])
        urm.run_cmd(["git", "config", "user.email", "monitor@example.invalid"])

    def commit(self, path: str, content: str | bytes, message: str) -> str:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content) if isinstance(
            content, bytes
        ) else target.write_text(content, encoding="utf-8")
        urm.run_cmd(["git", "add", "--", path])
        urm.run_cmd(["git", "commit", "-m", message])
        return str(urm.run_cmd(["git", "rev-parse", "HEAD"]).stdout).strip()


class SelectionTests(IsolatedTest):
    def test_repo_ref_and_path_validation(self) -> None:
        urm.validate_repo_format("owner/repo")
        urm.validate_git_ref("release/v1.2.3")
        self.assertEqual(urm.validate_relative_path("a/b.txt", label="path"), "a/b.txt")
        for value in ("repo", "owner/repo/extra", "-owner/repo"):
            with self.assertRaises(ValueError):
                urm.validate_repo_format(value)
        for value in ("-bad", "bad ref", "a..b", "a@{b", "refs//x"):
            with self.assertRaises(ValueError):
                urm.validate_git_ref(value)
        with self.assertRaises(ValueError):
            urm.validate_relative_path("../escape", label="path")

    def test_payload_shapes_and_non_list_page(self) -> None:
        payload = [
            [{"tag_name": "v2"}],
            "bad",
            {"tag_name": "v1"},
            {"message": "error"},
        ]
        self.assertEqual(
            [r["tag_name"] for r in urm.normalize_release_payload(payload)],
            ["v2", "v1"],
        )
        self.assertEqual(urm.normalize_release_payload({"message": "error"}), [])
        with patch(
            "upstream_monitor_common.api_json", return_value={"message": "rate limit"}
        ):
            with self.assertRaisesRegex(urm.MonitorError, "expected list"):
                urm.fetch_release_page("owner/repo", 1)

    def test_api_invalid_json_chains_decoder(self) -> None:
        result = SimpleNamespace(stdout="not-json", returncode=0)
        with patch("upstream_monitor_common.run_cmd", return_value=result):
            with self.assertRaises(urm.MonitorError) as raised:
                urm.api_json("repos/owner/repo/releases")
        self.assertIsInstance(raised.exception.__cause__, json.JSONDecodeError)

    def test_release_scan_stops_once_head_and_base_known(self) -> None:
        page = [
            {"tag_name": "v3", "draft": False, "prerelease": False},
            {"tag_name": "v2", "draft": False, "prerelease": False},
        ]
        with patch(
            "upstream_monitor_common.fetch_release_page", return_value=page
        ) as fetch:
            self.assertEqual(
                urm.scan_release_order(
                    "owner/repo", include_prerelease=False, head_tag="v3"
                ),
                ("v3", "v2"),
            )
        fetch.assert_called_once_with("owner/repo", 1)

    def test_prerelease_order_is_documented_api_order(self) -> None:
        page = [
            {"tag_name": "v3-rc1", "draft": False, "prerelease": True},
            {"tag_name": "v2", "draft": False, "prerelease": False},
        ]
        with patch("upstream_monitor_common.fetch_release_page", return_value=page):
            self.assertEqual(
                urm.scan_release_order(
                    "owner/repo", include_prerelease=True, head_tag=None
                ),
                ("v3-rc1", "v2"),
            )

    def test_stable_selection_uses_latest_and_explicit_pair_uses_no_api(self) -> None:
        with (
            patch(
                "upstream_monitor_common.latest_stable_release",
                return_value={"tag_name": "v2", "draft": False, "prerelease": False},
            ) as latest,
            patch(
                "upstream_monitor_common.scan_release_order", return_value=("v2", "v1")
            ) as scan,
        ):
            selected = urm.resolve_selection(Args(), [])
        self.assertEqual((selected.head_tag, selected.base_tag), ("v2", "v1"))
        latest.assert_called_once()
        scan.assert_called_once()
        with (
            patch("upstream_monitor_common.latest_stable_release") as latest,
            patch("upstream_monitor_common.scan_release_order") as scan,
        ):
            explicit = urm.resolve_selection(Args(head_tag="v2", base_tag="v1"), [])
        self.assertEqual((explicit.head_tag, explicit.base_tag), ("v2", "v1"))
        latest.assert_not_called()
        scan.assert_not_called()

    def test_no_stable_release_and_first_release_modes(self) -> None:
        with (
            patch(
                "upstream_monitor_common.api_json", side_effect=urm.MonitorError("404")
            ),
            patch(
                "upstream_monitor_common.fetch_release_page",
                return_value=[
                    {"tag_name": "v1-rc", "draft": False, "prerelease": True}
                ],
            ),
        ):
            self.assertIsNone(urm.latest_stable_release("owner/repo"))
        warnings: list[str] = []
        with patch(
            "upstream_monitor_common.scan_release_order", return_value=("v1", None)
        ):
            selected = urm.resolve_selection(Args(head_tag="v1"), warnings)
        self.assertEqual(selected.comparison_mode, "first_release_empty_tree")
        self.assertTrue(any("empty tree" in item for item in warnings))

    def test_selected_base_fetch_failures_never_downgrade(self) -> None:
        for explicit in (False, True):
            selection = urm.ReleaseSelection(
                "v2" if explicit else None,
                "v1" if explicit else None,
                "v2",
                "v1",
                explicit,
                explicit,
                "range",
            )
            with (
                patch("upstream_monitor_common.ensure_remote"),
                patch(
                    "upstream_monitor_common.fetch_named_ref", side_effect=[True, False]
                ),
                patch("upstream_monitor_common.peel_commit", return_value="a" * 40),
            ):
                with self.assertRaisesRegex(urm.MonitorError, "refusing a misleading"):
                    urm.fetch_upstream("owner/repo", selection)


class GitTests(IsolatedTest):
    def test_empty_tree_and_annotated_tag(self) -> None:
        self.init_repo()
        self.commit("alpha.txt", "alpha\n", "first")
        head = str(urm.run_cmd(["git", "rev-parse", "HEAD"]).stdout).strip()
        empty = urm.ensure_empty_tree()
        _stat, patch_text, changed = urm.generate_diffs(empty, head)
        self.assertIn("alpha.txt", patch_text)
        self.assertEqual(changed[0]["status"], "added")
        urm.run_cmd(["git", "tag", "-a", "v1", "-m", "annotated"])
        self.assertEqual(urm.peel_commit("v1"), head)

    def test_name_status_supports_rename_copy_and_unusual_paths(self) -> None:
        raw = (
            "R100\0old name.txt\0new name.txt\0C100\0a\tb.txt\0copy.txt\0D\0gone.txt\0"
        )
        parsed = urm.parse_name_status_z(raw)
        self.assertEqual(parsed[0]["status"], "renamed")
        self.assertEqual(parsed[1]["status"], "copied")
        self.assertEqual(parsed[1]["old_path"], "a\tb.txt")
        self.assertEqual(parsed[2], {"status": "deleted", "path": "gone.txt"})

    def test_real_file_map_comparison_and_deleted_state(self) -> None:
        self.init_repo()
        self.commit("app/local.txt", "local\n", "local")
        (self.root / ".github").mkdir(exist_ok=True)
        (self.root / ".github/upstream-file-map.json").write_text(
            '{"src/upstream.txt":"app/local.txt"}', encoding="utf-8"
        )
        urm.run_cmd(["git", "switch", "-c", "upstream"])
        self.commit("src/upstream.txt", "upstream\n", "upstream")
        urm.run_cmd(["git", "switch", "main"])
        comparisons = urm.compare_local_files(
            [{"status": "modified", "path": "src/upstream.txt"}],
            "upstream",
            self.root / "artifacts",
        )
        self.assertEqual(comparisons[0]["local_status"], "differs")
        deleted = urm.compare_local_files(
            [{"status": "deleted", "path": "absent.txt"}],
            "upstream",
            self.root / "artifacts2",
        )
        self.assertEqual(deleted[0]["local_status"], "missing")
        (self.root / "present.txt").write_text("still here", encoding="utf-8")
        present = urm.compare_local_files(
            [{"status": "deleted", "path": "present.txt"}],
            "upstream",
            self.root / "artifacts3",
        )
        self.assertEqual(present[0]["local_status"], "present_after_upstream_deletion")

    def test_binary_difference_and_integrated_logic(self) -> None:
        self.init_repo()
        self.commit("binary.dat", b"\x00upstream", "binary")
        (self.root / "binary.dat").write_bytes(b"\x00local")
        comparisons = urm.compare_local_files(
            [{"status": "modified", "path": "binary.dat"}],
            "HEAD",
            self.root / "artifacts",
        )
        self.assertIn(comparisons[0]["local_status"], {"differs", "binary_differs"})
        self.assertFalse(urm.all_changes_integrated(comparisons))
        self.assertTrue(
            urm.all_changes_integrated(
                [{"upstream_status": "deleted", "local_status": "missing"}]
            )
        )


class ReportingAndIssueTests(IsolatedTest):
    def test_resolved_grammar_is_exact_and_repo_isolated(self) -> None:
        path = self.root / "resolved.txt"
        path.write_text(
            "v1\nv1..v2\nother/repo@v3\nother/repo@v3..v4\n", encoding="utf-8"
        )
        self.assertTrue(
            urm.is_resolved_release(urm.DEFAULT_UPSTREAM, "v1", None, path=path)
        )
        self.assertTrue(
            urm.is_resolved_release(urm.DEFAULT_UPSTREAM, "v2", "v1", path=path)
        )
        self.assertFalse(urm.is_resolved_release("other/repo", "v1", None, path=path))
        self.assertTrue(urm.is_resolved_release("other/repo", "v4", "v3", path=path))
        self.assertFalse(
            urm.is_resolved_release(urm.DEFAULT_UPSTREAM, "vV1", None, path=path)
        )

    def test_malformed_and_non_utf8_resolved_files_fail(self) -> None:
        malformed = self.root / "malformed.txt"
        malformed.write_text("bad..range..entry\n", encoding="utf-8")
        with self.assertRaisesRegex(urm.MonitorError, "Malformed"):
            urm.load_resolved_entries(malformed)
        binary = self.root / "binary.txt"
        binary.write_bytes(b"\xff")
        with self.assertRaisesRegex(urm.MonitorError, "Failed to read"):
            urm.load_resolved_entries(binary)

    def test_markdown_safety_body_budget_and_metadata_copy(self) -> None:
        self.assertNotIn("@user", urm.neutralize_mentions("hello @user"))
        self.assertNotIn("```", urm.clean_fence("```break```"))
        marker = "<!-- marker -->"
        bounded = urm.bounded_markdown("x" * 1000, [marker], limit=300)
        self.assertLessEqual(len(bounded), 300)
        self.assertIn(marker, bounded)
        self.assertIn("truncated", bounded)
        source = [{"diff": "x" * 600, "local_path": "a"}]
        safe = urm.metadata_safe_comparisons(source)
        self.assertIn("diff", source[0])
        self.assertNotIn("diff", safe[0])
        self.assertTrue(safe[0]["diff_omitted"])

    def test_issue_listing_exact_identity_and_ambiguous_migration(self) -> None:
        with patch(
            "upstream_monitor_report.api_json",
            return_value=[{"number": 1, "title": "x", "body": "", "state": "open"}],
        ) as api:
            issues = urm.list_tracking_issues("owner/repo")
        self.assertEqual(len(issues), 1)
        self.assertNotIn("search", api.call_args.args[0])
        marker = urm.issue_identity_marker("owner/repo", "v2")
        marked = {"number": 1, "title": "old", "body": marker}
        self.assertEqual(
            urm.find_tracking_issue(
                [marked], identity_marker=marker, exact_title="target"
            ),
            marked,
        )
        with self.assertRaisesRegex(urm.MonitorError, "Ambiguous legacy"):
            urm.find_tracking_issue(
                [
                    {"number": 1, "title": "target", "body": ""},
                    {"number": 2, "title": "target", "body": ""},
                ],
                identity_marker=marker,
                exact_title="target",
            )
        with patch(
            "upstream_monitor_report.api_json", return_value={"message": "error"}
        ):
            with self.assertRaisesRegex(urm.MonitorError, "expected list"):
                urm.list_tracking_issues("owner/repo")

    @patch("upstream_monitor_report.mutate_issue")
    @patch("upstream_monitor_report.list_tracking_issues")
    def test_closed_duplicate_force_and_create_issue_states(
        self, listing: MagicMock, mutate: MagicMock
    ) -> None:
        args = Args(dry_run=False)
        identity = urm.issue_identity_marker(args.upstream_repo, "v2")
        listing.return_value = [
            {
                "number": 5,
                "title": "target",
                "body": identity,
                "state": "closed",
                "html_url": "https://example/5",
            }
        ]
        self.assertEqual(
            urm.manage_issue(args, "target", "body", "a" * 64, "v2").action,
            "skipped_closed",
        )
        listing.return_value[0]["state"] = "open"
        listing.return_value[0]["body"] = (
            f"<!-- upstream-monitor:fingerprint:{'a' * 64} -->\n{identity}"
        )
        self.assertEqual(
            urm.manage_issue(args, "target", "body", "a" * 64, "v2").action,
            "skipped_duplicate",
        )
        args.force = True
        listing.return_value[0]["state"] = "closed"
        mutate.return_value = {"number": 5, "html_url": "https://example/5"}
        self.assertEqual(
            urm.manage_issue(args, "target", "body", "b" * 64, "v2").action,
            "reopened_updated",
        )
        listing.return_value = []
        mutate.return_value = {"number": 7, "html_url": "https://example/7"}
        self.assertEqual(
            urm.manage_issue(Args(dry_run=False), "target", "body", "c" * 64, "v2"),
            urm.IssueOutcome("created", 7, "https://example/7"),
        )

    def test_dry_run_skips_all_issue_reads(self) -> None:
        with patch("upstream_monitor_report.list_tracking_issues") as listing:
            self.assertEqual(
                urm.manage_issue(Args(), "target", "body", "a" * 64, "v2").action,
                "dry_run",
            )
        listing.assert_not_called()

    def test_artifact_schema_is_stable_and_non_destructive(self) -> None:
        args = Args(out_dir=str(self.root / "artifacts"))
        summary = urm.new_summary(args)
        summary["comparisons"] = [{"diff": "secret", "local_path": "a"}]
        summary["result"] = "failed"
        summary["errors"] = ["failure"]
        urm.write_run_outputs(args, summary, patch="patch")
        metadata = json.loads(
            (self.root / "artifacts/metadata.json").read_text(encoding="utf-8")
        )
        self.assertEqual(metadata["schema_version"], urm.SCHEMA_VERSION)
        self.assertIn("requested_tags", metadata)
        self.assertIn("effective_refs", metadata)
        self.assertIn("diff", summary["comparisons"][0])
        for name in (
            "upstream-monitor-report.md",
            "upstream-release.diff",
            "step-summary.md",
            "warnings.txt",
            "errors.txt",
        ):
            self.assertTrue((self.root / "artifacts" / name).exists())


class StateMachineTests(IsolatedTest):
    def test_no_releases_and_early_resolved_states(self) -> None:
        with patch(
            "upstream_release_monitor.resolve_selection",
            return_value=urm.ReleaseSelection(
                None, None, None, None, False, False, "no_releases"
            ),
        ):
            summary, report, patch_text = urm.execute_monitor(
                Args(out_dir=str(self.root / "artifacts"))
            )
        self.assertEqual(
            (summary["result"], summary["exit_code"], report, patch_text),
            ("skipped_no_releases", 0, None, ""),
        )
        selection = urm.ReleaseSelection(None, None, "v2", "v1", False, False, "range")
        with (
            patch("upstream_release_monitor.resolve_selection", return_value=selection),
            patch("upstream_release_monitor.is_resolved_release", return_value=True),
            patch("upstream_release_monitor.fetch_upstream") as fetch,
        ):
            summary, _report, _patch = urm.execute_monitor(
                Args(dry_run=False, out_dir=str(self.root / "artifacts2"))
            )
        self.assertEqual(summary["result"], "skipped_resolved")
        fetch.assert_not_called()

    def test_integrated_and_issue_action_states(self) -> None:
        selection = urm.ReleaseSelection(None, None, "v2", "v1", False, False, "range")
        comparison = [
            {
                "upstream_path": "a",
                "local_path": "a",
                "upstream_status": "modified",
                "local_status": "identical",
                "diff": "",
                "diff_artifact_name": "a.diff",
            }
        ]
        with (
            patch("upstream_release_monitor.resolve_selection", return_value=selection),
            patch("upstream_release_monitor.is_resolved_release", return_value=False),
            patch(
                "upstream_release_monitor.fetch_upstream",
                return_value=urm.FetchResult("head", "a" * 40, "base", "b" * 40),
            ),
            patch(
                "upstream_release_monitor.generate_diffs",
                return_value=("stat", "patch", [{"status": "modified", "path": "a"}]),
            ),
            patch(
                "upstream_release_monitor.compare_local_files", return_value=comparison
            ),
        ):
            summary, _report, patch_text = urm.execute_monitor(
                Args(dry_run=False, out_dir=str(self.root / "artifacts"))
            )
        self.assertEqual(summary["result"], "skipped_integrated")
        self.assertEqual(patch_text, "patch")
        summary = urm.new_summary(Args())
        for state in (
            "created",
            "updated",
            "reopened_updated",
            "dry_run",
            "skipped_closed",
            "skipped_duplicate",
        ):
            urm.set_result(summary, state)
            self.assertEqual(summary["result"], state)
            self.assertEqual(summary["exit_code"], 0)

    def test_pr_enrichment_ghost_user_and_command_timeout(self) -> None:
        response = [
            {
                "number": 1,
                "title": "change",
                "html_url": "https://example/pr/1",
                "user": None,
                "body": "hello",
            }
        ]
        with patch("upstream_monitor_git.api_json", return_value=response):
            prs = urm.enrich_pull_requests(
                "owner/repo", [{"sha": "a" * 40, "msg": "x"}], 1, []
            )
        self.assertEqual(prs[0]["author"], "ghost")
        with patch(
            "upstream_monitor_common.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["gh", "api"], 1),
        ):
            with self.assertRaisesRegex(urm.MonitorError, "timed out"):
                urm.run_cmd(["gh", "api"], timeout=1)


if __name__ == "__main__":
    unittest.main()
