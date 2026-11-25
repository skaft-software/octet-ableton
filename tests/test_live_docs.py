import contextlib
import importlib.util
import io
import json
import os
import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "skills/ableton-live/scripts/find_live_docs.py"
SPEC = importlib.util.spec_from_file_location("find_live_docs", SCRIPT)
docs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(docs)


class LiveDocsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.apps = self.root / "Applications"
        self.apps.mkdir()

    def installation(self, name="Ableton Live 12 Suite.app", layout="Contents/LegalAndDocs/Docs", parent=None):
        root = (parent or self.apps) / name
        directory = root / layout
        directory.mkdir(parents=True)
        return root, directory

    def discover(self, **kwargs):
        return docs.discover_docs(platform="darwin", search_roots=[self.apps], **kwargs)

    def codes(self, result):
        return {warning["code"] for warning in result["warnings"]}

    def test_mac_manual_html_generic_and_version_evidence(self):
        root, directory = self.installation()
        (directory / "EN").mkdir()
        (directory / "EN/Live Manual.PDF").write_bytes(b"not read by discovery")
        (directory / "index.html").write_text("not read by discovery")
        (directory / "tutorial.htm").write_text("not read by discovery")
        (directory / "ignore.txt").write_text("irrelevant")
        info = root / "Contents/Info.plist"
        info.write_bytes(plistlib.dumps({"CFBundleShortVersionString": "12.3.2", "CFBundleVersion": "12345", "CFBundleName": "Live", "unrelated": "not exposed"}))
        result = self.discover()
        self.assertEqual(result["status"], "found")
        self.assertFalse(result["truncated"])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(len(result["candidates"]), 3)
        manual = next(item for item in result["candidates"] if item["kind"] == "manual")
        self.assertEqual(manual["format"], "pdf")
        self.assertEqual(manual["installation"], str(root))
        self.assertEqual(sum(item["kind"] == "documentation" for item in result["candidates"]), 2)
        evidence = result["installations"][0]["bundle_info"]
        self.assertEqual(evidence["source"], str(info))
        self.assertEqual(evidence["CFBundleShortVersionString"], "12.3.2")
        self.assertNotIn("unrelated", evidence)
        self.assertNotIn("running_version", result)

    def test_windows_primary_and_alternative_layouts(self):
        data = self.root / "ProgramData"
        programs = self.root / "Program Files"
        first, directory = self.installation("Live 12 Suite", "Resources/LegalAndDocs/Docs", data / "Ableton")
        (directory / "Manual.pdf").touch()
        second, directory = self.installation("Live 11 Standard", "LegalAndDocs/Docs", programs / "Ableton")
        (directory / "Manual.html").touch()
        roots = docs.default_search_roots("win32", environ={"PROGRAMDATA": str(data), "ProgramFiles": str(programs)})
        self.assertIn(data / "Ableton", roots)
        self.assertIn(programs / "Ableton", roots)
        result = docs.discover_docs(platform="win32", search_roots=roots)
        self.assertEqual({item["installation"] for item in result["candidates"]}, {str(first), str(second)})

    def test_multiple_installations_are_not_selected_or_collapsed(self):
        for version in (11, 12):
            _, directory = self.installation(f"Ableton Live {version} Suite.app")
            (directory / "Manual.pdf").touch()
        result = self.discover()
        self.assertEqual(len(result["installations"]), 2)
        self.assertEqual(len(result["candidates"]), 2)
        self.assertNotIn("selected_installation", result)

    def test_missing_and_empty_docs_are_honest(self):
        empty = self.discover()
        self.assertEqual(empty["status"], "no_candidates")
        self.assertEqual(empty["installations"], [])
        root, directory = self.installation()
        empty = self.discover()
        self.assertEqual(empty["status"], "no_candidates")
        self.assertEqual(empty["installations"][0]["docs_directories"], [str(directory)])
        self.assertEqual(empty["candidates"], [])
        directory.rmdir()
        missing = self.discover()
        self.assertEqual(missing["installations"][0]["path"], str(root))
        self.assertEqual(missing["installations"][0]["docs_directories"], [])

    def test_explicit_custom_root_replaces_defaults_even_on_unsupported_platform(self):
        _, directory = self.installation()
        (directory / "Default Manual.pdf").touch()
        root, directory = self.installation("Custom installation", parent=self.root)
        (directory / "Custom Manual.pdf").touch()
        with patch.object(docs, "default_search_roots", side_effect=AssertionError("must not use defaults")):
            result = docs.discover_docs([root, root], platform="linux")
        self.assertEqual(result["search_mode"], "explicit")
        self.assertEqual([item["installation"] for item in result["candidates"]], [str(root)])
        self.assertEqual(docs.discover_docs([], platform="linux")["installations"], [])

    def test_defaults_do_not_scan_home_downloads_or_other_app_directories(self):
        home = self.root / "home"
        user_apps = home / "Applications"
        user_apps.mkdir(parents=True)
        downloads = home / "Downloads"
        downloads.mkdir()
        (downloads / "Ableton Live Manual.pdf").touch()
        (home / "Manual.pdf").touch()
        unrelated, directory = self.installation("Unrelated.app")
        (directory / "Manual.pdf").touch()
        roots = docs.default_search_roots("darwin", home=home)
        self.assertEqual(roots, [Path("/Applications"), user_apps])
        scanned = []
        original = docs.os.scandir

        def record(path):
            scanned.append(Path(path))
            return original(path)

        with patch.object(docs.os, "scandir", side_effect=record):
            result = docs.discover_docs(platform="darwin", search_roots=[self.apps, user_apps])
        self.assertEqual(result["candidates"], [])
        self.assertNotIn(home, scanned)
        self.assertNotIn(downloads, scanned)
        self.assertNotIn(unrelated, scanned)

    def test_explicit_home_is_not_recursively_searched(self):
        (self.root / "Manual.pdf").touch()
        with patch.object(docs.os, "scandir", side_effect=AssertionError("must only probe fixed layouts")):
            result = docs.discover_docs([self.root])
        self.assertEqual(result["candidates"], [])

    def test_only_bounded_metadata_is_opened_read_only(self):
        root, directory = self.installation()
        (directory / "Manual.pdf").touch()
        info = root / "Contents/Info.plist"
        info.write_bytes(plistlib.dumps({"CFBundleName": "Live"}))
        opened = []
        original = docs.os.open

        def record(path, flags):
            opened.append(Path(path))
            self.assertEqual(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND), 0)
            return original(path, flags)

        with patch.object(docs.os, "open", side_effect=record):
            self.discover()
        self.assertEqual(opened, [info])

    def test_relative_default_root_is_rejected_without_scanning(self):
        with patch.object(docs.os, "scandir", side_effect=AssertionError("must not scan cwd")):
            result = docs.discover_docs(platform="win32", search_roots=[Path("Ableton")])
        self.assertIn("path_error", self.codes(result))
        self.assertEqual(result["search_roots"], [])

    def test_permission_error_is_reported(self):
        with patch.object(docs.os, "scandir", side_effect=PermissionError("denied")):
            result = self.discover()
        self.assertEqual(result["candidates"], [])
        self.assertIn("path_error", self.codes(result))

    def test_bounds_on_entries_depth_files_results_and_installations(self):
        root, directory = self.installation()
        for name in ("a.pdf", "b.pdf", "c.pdf"):
            (directory / name).touch()
        nested = directory / "nested"
        nested.mkdir()
        (nested / "Manual.pdf").touch()
        for limit, value, code in (("entries_per_directory", 1, "entry_limit"), ("entries_total", 1, "entry_limit"), ("depth", 0, "depth_limit"), ("files", 1, "file_limit"), ("candidates", 1, "candidate_limit")):
            with self.subTest(limit=limit), patch.dict(docs.LIMITS, {limit: value}):
                result = docs.discover_docs([root])
                self.assertTrue(result["truncated"])
                self.assertIn(code, self.codes(result))
        with patch.dict(docs.LIMITS, {"installations": 1}):
            result = docs.discover_docs([root, self.root / "other"])
            self.assertTrue(result["truncated"])
            self.assertIn("installation_limit", self.codes(result))

    def test_plist_invalid_oversize_and_metadata_bounds(self):
        root, _ = self.installation()
        info = root / "Contents/Info.plist"
        for content, code in ((b"not a plist", "plist_error"), (b"x" * (docs.LIMITS["plist_bytes"] + 1), "plist_limit"), (plistlib.dumps({"CFBundleName": "x" * (docs.LIMITS["metadata_chars"] + 1)}), "metadata_limit")):
            with self.subTest(code=code):
                info.write_bytes(content)
                result = self.discover()
                self.assertIn(code, self.codes(result))
        info.write_bytes(plistlib.dumps(["not a dictionary"]))
        self.assertIn("plist_error", self.codes(self.discover()))
        info.write_bytes(plistlib.dumps({"CFBundleVersion": "123"}, fmt=plistlib.FMT_BINARY))
        self.assertEqual(self.discover()["installations"][0]["bundle_info"]["CFBundleVersion"], "123")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlink_escapes_are_not_followed(self):
        root, directory = self.installation()
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "Manual.pdf").touch()
        (outside / "Info.plist").write_bytes(plistlib.dumps({"CFBundleName": "must not read"}))
        try:
            (directory / "linked").symlink_to(outside, target_is_directory=True)
            (directory / "Manual.pdf").symlink_to(outside / "Manual.pdf")
            (root / "Contents/Info.plist").symlink_to(outside / "Info.plist")
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        result = self.discover()
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["installations"][0]["bundle_info"], {})
        self.assertIn("symlink_skipped", self.codes(result))
        (directory / "linked").unlink()
        (directory / "Manual.pdf").unlink()
        directory.rmdir()
        directory.symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.discover()["candidates"], [])
        directory.unlink()
        directory.parent.rmdir()
        directory.parent.symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.discover()["candidates"], [])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_default_app_symlink_skipped_but_explicit_root_may_resolve(self):
        root, directory = self.installation("Actual", parent=self.root)
        (directory / "Manual.pdf").touch()
        link = self.apps / "Ableton Live 12 Suite.app"
        try:
            link.symlink_to(root, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        self.assertEqual(self.discover()["candidates"], [])
        result = docs.discover_docs([link])
        self.assertEqual(result["candidates"][0]["installation"], str(root))
        self.assertEqual(result["installations"][0]["path"], str(root))

    def test_invalid_paths_unsupported_platform_and_warning_cap(self):
        result = docs.discover_docs([self.root / "missing", "bad\x00path", "x" * (docs.LIMITS["path_chars"] + 1), "//server/share"])
        self.assertEqual(result["candidates"], [])
        self.assertTrue({"missing_installation", "path_error", "path_limit", "network_path_skipped"}.issubset(self.codes(result)))
        result = docs.discover_docs(platform="linux")
        self.assertEqual(result["search_roots"], [])
        self.assertIn("unsupported_platform", self.codes(result))
        with patch.dict(docs.LIMITS, {"warnings": 2}):
            result = docs.discover_docs([self.root / str(index) for index in range(4)])
            self.assertEqual(len(result["warnings"]), 2)
            self.assertIn("warning_limit", self.codes(result))
        json.dumps(result, allow_nan=False)

    def test_cli_repeatable_explicit_installations_emits_json(self):
        first, directory = self.installation()
        (directory / "Manual.pdf").touch()
        second, _ = self.installation("Ableton Live 11 Suite.app")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = docs.main(["--installation", str(first), "--installation", str(second)])
        self.assertEqual(status, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(len(result["installations"]), 2)
        self.assertEqual(len(result["candidates"]), 1)


if __name__ == "__main__":
    unittest.main()
