import unittest
import sys
import os
import tempfile
import shutil

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

if __name__ == '__main__':
    unittest.main()
