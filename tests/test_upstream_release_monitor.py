import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import tempfile
import shutil
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../scripts')))
import upstream_release_monitor as urm

class DummyArgs:
    def __init__(self, **kwargs):
        self.repo = "cbkii/hotspotadb"
        self.upstream_repo = "droserasprout/io.drsr.hotspotadb"
        self.head_tag = None
        self.base_tag = None
        self.include_prerelease = False
        self.force = False
        self.dry_run = True
        self.out_dir = "/tmp"
        for k, v in kwargs.items():
            setattr(self, k, v)

class TestUpstreamReleaseMonitor(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_truncate_text_no_truncation(self):
        text = "short text"
        result = urm.truncate_text(text, 100)
        self.assertEqual(result, text)

    def test_truncate_text_with_truncation(self):
        text = "a" * 105
        result = urm.truncate_text(text, 100)
        self.assertTrue(result.endswith("\n... (truncated)"))
        self.assertEqual(len(result), 100 + len("\n... (truncated)"))

    def test_markdown_building_keeps_urls(self):
        args = DummyArgs()
        comparisons = [{
            "upstream_path": "app/src/main/kotlin/Test.kt",
            "local_path": "app/src/main/kotlin/Test.kt",
            "upstream_status": "modified",
            "local_status": "identical",
            "diff": ""
        }]

        md = urm.build_markdown(
            args,
            "droserasprout/io.drsr.hotspotadb",
            "1.0.2",
            "1.1.0",
            "1 file changed",
            "diff --git a b",
            [{"status": "modified", "path": "app/src/main/kotlin/Test.kt"}],
            comparisons,
            [],
            [],
            "fakefingerprint123",
            "fakecommit",
            "main"
        )

        self.assertIn("1.0.2...1.1.0", md)
        self.assertIn("`app/src/main/kotlin/Test.kt`", md)
        self.assertIn("https://github.com/droserasprout/io.drsr.hotspotadb/blob/1.1.0/app/src/main/kotlin/Test.kt", md)
        self.assertIn("fakefingerprint123", md)
        self.assertIn("```diff\ndiff --git a b\n```", md)

    def test_fingerprint_stability(self):
        comparisons = [{"upstream_path": "a", "local_path": "a", "local_status": "identical", "diff": ""}]
        fp1 = urm.generate_fingerprint("upstream", "base", "head", "repo", "branch", "diffstat", comparisons)
        fp2 = urm.generate_fingerprint("upstream", "base", "head", "repo", "branch", "diffstat", comparisons)
        self.assertEqual(fp1, fp2)

        comparisons2 = [{"upstream_path": "a", "local_path": "a", "local_status": "differs", "diff": "diff"}]
        fp3 = urm.generate_fingerprint("upstream", "base", "head", "repo", "branch", "diffstat", comparisons2)
        self.assertNotEqual(fp1, fp3)

    def test_resolved_tag_normalization(self):
        os.makedirs(".github", exist_ok=True)
        with open(".github/upstream-release-resolved-tags.txt", "w") as f:
            f.write("# comment\n")
            f.write("1.0.0\n")
            f.write("v1.1.0\n")
            f.write("owner/repo@1.2.0\n")
            f.write("owner/repo@1.3.0..1.4.0\n")

        self.assertTrue(urm.check_resolved_tags("owner/repo", "1.0.0", "0.9.0"))
        self.assertTrue(urm.check_resolved_tags("owner/repo", "v1.0.0", "v0.9.0"))
        self.assertTrue(urm.check_resolved_tags("owner/repo", "1.1.0", "1.0.0"))
        self.assertTrue(urm.check_resolved_tags("owner/repo", "1.2.0", "1.1.0"))
        self.assertTrue(urm.check_resolved_tags("owner/repo", "1.4.0", "1.3.0"))
        self.assertFalse(urm.check_resolved_tags("owner/repo", "1.5.0", "1.4.0"))

    def test_file_mapping(self):
        with open('test.txt', 'w') as f:
            f.write('hi')
        comparisons = urm.compare_local_files([{"status": "modified", "path": "test.txt"}], "head", self.test_dir)
        self.assertEqual(comparisons[0]["local_path"], "test.txt")
        os.remove("test.txt")

    def test_normalize_release_payload_flat(self):
        payload = [{"tag_name": "1.1.0"}]
        result = urm.normalize_release_payload(payload)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["tag_name"], "1.1.0")

    def test_normalize_release_payload_slurped(self):
        payload = [[{"tag_name": "1.1.0"}], [{"tag_name": "1.0.2"}]]
        result = urm.normalize_release_payload(payload)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["tag_name"], "1.1.0")
        self.assertEqual(result[1]["tag_name"], "1.0.2")

    def test_normalize_release_payload_garbage(self):
        payload = [
            [{"tag_name": "1.1.0"}],
            "bad",
            {"message": "rate limit or API error"},
            {"tag_name": "unexpected-flat"}
        ]
        result = urm.normalize_release_payload(payload)
        self.assertEqual(len(result), 2)
        self.assertEqual([r["tag_name"] for r in result], ["1.1.0", "unexpected-flat"])

    def test_parse_name_status_z(self):
        output = "M\x00file1.txt\x00A\x00file2.txt\x00D\x00file3.txt\x00R100\x00old.txt\x00new.txt\x00C100\x00src.txt\x00dst.txt\x00\x00"
        result = urm.parse_name_status_z(output)

        self.assertEqual(len(result), 5)
        self.assertEqual(result[0], {"status": "modified", "path": "file1.txt"})
        self.assertEqual(result[1], {"status": "added", "path": "file2.txt"})
        self.assertEqual(result[2], {"status": "deleted", "path": "file3.txt"})
        self.assertEqual(result[3], {"status": "renamed", "old_path": "old.txt", "path": "new.txt"})
        self.assertEqual(result[4], {"status": "copied", "old_path": "src.txt", "path": "dst.txt"})

    def test_parse_name_status_z_malformed(self):
        output = "M\x00file1.txt\x00R100\x00old.txt\x00" # Missing new_path
        result = urm.parse_name_status_z(output)
        self.assertEqual(len(result), 1) # Should only parse the first valid entry

    @patch('upstream_release_monitor.run_cmd')
    def test_get_releases_slurped(self, mock_run_cmd):
        mock_result = MagicMock()
        mock_result.stdout = json.dumps([
            [{"tag_name": "1.1.0", "draft": False, "prerelease": False}],
            [{"tag_name": "1.1.0-beta", "draft": False, "prerelease": True}],
            [{"tag_name": "1.0.2", "draft": True, "prerelease": False}]
        ])
        mock_run_cmd.return_value = mock_result

        releases = urm.get_releases("dummy/repo", include_prerelease=False)
        self.assertEqual(len(releases), 1)
        self.assertEqual(releases[0]["tag_name"], "1.1.0")

        releases_pre = urm.get_releases("dummy/repo", include_prerelease=True)
        self.assertEqual(len(releases_pre), 2)
        self.assertEqual(releases_pre[0]["tag_name"], "1.1.0")
        self.assertEqual(releases_pre[1]["tag_name"], "1.1.0-beta")

    def test_normalize_release_payload_not_list(self):
        self.assertEqual(urm.normalize_release_payload({"message": "error"}), [])

    def test_resolve_tags_malformed_release(self):
        args = DummyArgs()
        with patch('upstream_release_monitor.get_releases') as mock_get:
            mock_get.return_value = [{"not_tag": "bad"}, {"tag_name": "1.1.0"}]
            head, base = urm.resolve_tags(args)
            self.assertEqual(head, "1.1.0")

    def test_run_cmd_empty(self):
        with self.assertRaises(ValueError):
            urm.run_cmd([])

if __name__ == '__main__':
    unittest.main()
