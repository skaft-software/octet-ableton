#!/usr/bin/env python3
"""Locate, but never open/copy, PDF/HTML docs in installed Ableton Live layouts.

Python 3.11+, stdlib only. No network, subprocesses, writes, caches, or Live API.
Defaults inspect only direct children of conventional application directories;
--installation replaces defaults and probes only fixed suffixes below each root.
Layout probes are heuristics, not proof that a release ships a manual. Filename
classification is not content verification, and no running version is inferred.
"""

import argparse
import json
import os
import plistlib
import stat
import sys
from pathlib import Path
from xml.parsers.expat import ExpatError


LIMITS = {
    "installations": 16,
    "entries_per_directory": 256,
    "entries_total": 4096,
    "files": 1024,
    "depth": 4,
    "candidates": 128,
    "warnings": 64,
    "plist_bytes": 65536,
    "metadata_chars": 256,
    "path_chars": 4096,
}
DOC_LAYOUTS = (
    "Contents/LegalAndDocs/Docs",
    "Contents/Resources/LegalAndDocs/Docs",
    "Resources/LegalAndDocs/Docs",
    "LegalAndDocs/Docs",
)
BUNDLE_KEYS = ("CFBundleName", "CFBundleIdentifier", "CFBundleShortVersionString", "CFBundleVersion")


def default_search_roots(platform, *, home=None, environ=None):
    """Pure, injectable conventional parent locations; never search home itself."""
    if platform == "darwin":
        return [Path("/Applications"), (Path.home() if home is None else Path(home)) / "Applications"]
    if platform == "win32":
        env = os.environ if environ is None else environ
        # Environment keys are case insensitive on Windows, including in fixtures.
        env = {key.casefold(): value for key, value in env.items()}
        parents = [env.get("programdata", "C:\\ProgramData"), env.get("programfiles", "C:\\Program Files")]
        if env.get("programfiles(x86)"):
            parents.append(env["programfiles(x86)"])
        return list(dict.fromkeys(Path(parent) / "Ableton" for parent in parents))
    return []


class _Discovery:
    def __init__(self, platform, explicit):
        self.limits = LIMITS.copy()
        self.result = {
            "schema_version": 1,
            "platform": platform,
            "search_mode": "explicit" if explicit else "default",
            "status": "no_candidates",
            "search_roots": [],
            "installations": [],
            "candidates": [],
            "warnings": [],
            "truncated": False,
            "limits": self.limits,
        }
        self.seen_roots = set()
        self.entries_seen = 0
        self.files_seen = 0
        self.entries_exhausted = False
        self.files_exhausted = False
        self.candidates_exhausted = False

    def warn(self, code, path, message, *, truncated=False):
        self.result["truncated"] |= truncated
        warnings = self.result["warnings"]
        warning = {"code": code, "path": str(path)[:self.limits["path_chars"]], "message": message[:256]}
        if len(warnings) < self.limits["warnings"]:
            warnings.append(warning)
        else:
            self.result["truncated"] = True
            warnings[-1] = {"code": "warning_limit", "path": "", "message": "Additional warnings omitted."}

    def path_allowed(self, path):
        text = str(path)
        if len(text) > self.limits["path_chars"]:
            self.warn("path_limit", text, "Path exceeds character limit; skipped.", truncated=True)
            return False
        if text.startswith(("//", "\\\\")):
            self.warn("network_path_skipped", text, "UNC/network paths are not searched.")
            return False
        return True

    def normalize(self, value, *, explicit=False):
        if not self.path_allowed(value):
            return None
        try:
            path = Path(value).expanduser()
            if not self.path_allowed(path):
                return None
            if not explicit and not path.is_absolute():
                self.warn("path_error", path, "Default search roots must be absolute paths.")
                return None
            # Only an explicitly authorized installation root may resolve links.
            path = path.resolve(strict=True) if explicit else path.absolute()
        except FileNotFoundError:
            self.warn("missing_installation", value, "Installation root does not exist.")
            return None
        except (OSError, ValueError, RuntimeError) as exc:
            self.warn("path_error", value, str(exc))
            return None
        return path if self.path_allowed(path) else None

    def safe_stat(self, path):
        """Check every component without following symlinks or Windows reparses."""
        if not self.path_allowed(path):
            return None
        try:
            for component in (*reversed(path.parents), path):
                info = component.lstat()
                if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    self.warn("symlink_skipped", component, "Symlink/reparse point skipped; only explicit roots may resolve links.")
                    return None
                if component != path and not stat.S_ISDIR(info.st_mode):
                    self.warn("path_error", component, "Expected a directory in the installation path.")
                    return None
            return info
        except (FileNotFoundError, NotADirectoryError):
            return None
        except (OSError, ValueError) as exc:
            self.warn("path_error", path, str(exc))
            return None

    def entries(self, path):
        if self.entries_exhausted:
            return []
        info = self.safe_stat(path)
        if info is None or not stat.S_ISDIR(info.st_mode):
            return []
        entries = []
        try:
            with os.scandir(path) as iterator:
                for entry in iterator:
                    if self.entries_seen >= self.limits["entries_total"]:
                        self.entries_exhausted = True
                        self.warn("entry_limit", path, "Total traversal entry limit reached.", truncated=True)
                        break
                    if len(entries) >= self.limits["entries_per_directory"]:
                        self.warn("entry_limit", path, "Per-directory entry limit reached.", truncated=True)
                        break
                    self.entries_seen += 1
                    entries.append(Path(entry.path))
        except OSError as exc:
            self.warn("path_error", path, str(exc))
        return sorted(entries, key=lambda entry: str(entry).casefold())

    def bundle_info(self, root):
        path = root / "Contents/Info.plist"
        info = self.safe_stat(path)
        if info is None or not stat.S_ISREG(info.st_mode):
            return {}
        if info.st_size > self.limits["plist_bytes"]:
            self.warn("plist_limit", path, "Info.plist exceeds byte limit; not read.", truncated=True)
            return {}
        try:
            # O_NOFOLLOW adds final-component protection on platforms providing it.
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
            fd = os.open(path, flags)
            with os.fdopen(fd, "rb") as stream:
                opened = os.fstat(stream.fileno())
                if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                    self.warn("path_changed", path, "Info.plist changed during discovery; skipped.")
                    return {}
                data = stream.read(self.limits["plist_bytes"] + 1)
            if len(data) > self.limits["plist_bytes"]:
                self.warn("plist_limit", path, "Info.plist exceeds byte limit; not parsed.", truncated=True)
                return {}
            values = plistlib.loads(data)
            if not isinstance(values, dict):
                self.warn("plist_error", path, "Info.plist is not a dictionary.")
                return {}
        except OSError as exc:
            self.warn("path_error", path, str(exc))
            return {}
        except (plistlib.InvalidFileException, ValueError, TypeError, OverflowError, RecursionError, ExpatError) as exc:
            self.warn("plist_error", path, str(exc))
            return {}
        result = {"source": str(path)}
        for key in BUNDLE_KEYS:
            value = values.get(key)
            if isinstance(value, str):
                if len(value) > self.limits["metadata_chars"]:
                    self.warn("metadata_limit", path, f"{key} exceeds character limit; omitted.", truncated=True)
                else:
                    result[key] = value
        return result

    def walk_docs(self, root, directory, path, depth=0):
        if self.files_exhausted or self.candidates_exhausted:
            return
        for child in self.entries(path):
            if self.files_exhausted or self.candidates_exhausted:
                break
            info = self.safe_stat(child)
            if info is None:
                continue
            if stat.S_ISDIR(info.st_mode):
                if depth >= self.limits["depth"]:
                    self.warn("depth_limit", child, "Documentation traversal depth limit reached.", truncated=True)
                else:
                    self.walk_docs(root, directory, child, depth + 1)
            elif stat.S_ISREG(info.st_mode):
                if self.files_seen >= self.limits["files"]:
                    self.files_exhausted = True
                    self.warn("file_limit", child, "Documentation file limit reached.", truncated=True)
                    break
                self.files_seen += 1
                extension = child.suffix.casefold()
                if extension not in (".pdf", ".html", ".htm"):
                    continue
                if len(self.result["candidates"]) >= self.limits["candidates"]:
                    self.candidates_exhausted = True
                    self.warn("candidate_limit", child, "Candidate result limit reached.", truncated=True)
                    break
                self.result["candidates"].append({
                    "path": str(child),
                    "installation": str(root),
                    "docs_directory": str(directory),
                    "format": "pdf" if extension == ".pdf" else "html",
                    "kind": "manual" if "manual" in child.name.casefold() else "documentation",
                })

    def inspect_installation(self, root):
        if root in self.seen_roots:
            return
        info = self.safe_stat(root)
        if info is None:
            return
        if not stat.S_ISDIR(info.st_mode):
            self.warn("path_error", root, "Installation root must be a directory.")
            return
        if len(self.result["installations"]) >= self.limits["installations"]:
            self.warn("installation_limit", root, "Installation result limit reached.", truncated=True)
            return
        self.seen_roots.add(root)
        installation = {"path": str(root), "name": root.name, "bundle_info": self.bundle_info(root), "docs_directories": []}
        self.result["installations"].append(installation)
        for layout in DOC_LAYOUTS:
            directory = root / layout
            info = self.safe_stat(directory)
            if info is not None and stat.S_ISDIR(info.st_mode):
                installation["docs_directories"].append(str(directory))
                self.walk_docs(root, directory, directory)


def discover_docs(installations=None, *, platform=None, search_roots=None):
    """Return bounded evidence; injected platform/search_roots are for tests.

    No candidate's contents are read. Only bounded Info.plist metadata is parsed.
    Symlink/reparse descendants and default roots are skipped. Explicit roots may
    resolve links once; this is a local discovery utility, not an adversarial
    filesystem sandbox against concurrent ancestor replacement or mounted shares.
    """
    platform = sys.platform if platform is None else platform
    explicit = installations is not None
    discovery = _Discovery(platform, explicit)
    if explicit:
        roots = installations
    else:
        roots = default_search_roots(platform) if search_roots is None else search_roots
        if platform not in ("darwin", "win32"):
            discovery.warn("unsupported_platform", "", "No default locations for this platform; supply --installation.")
            roots = []
    for index, value in enumerate(roots):
        if index >= discovery.limits["installations"]:
            discovery.warn("installation_limit", "", "Input root limit reached.", truncated=True)
            break
        root = discovery.normalize(value, explicit=explicit)
        if root is None:
            continue
        if str(root) not in discovery.result["search_roots"]:
            discovery.result["search_roots"].append(str(root))
        if explicit:
            discovery.inspect_installation(root)
            continue
        for child in discovery.entries(root):
            name = child.name.casefold()
            matches = (name.startswith("ableton live") and name.endswith(".app")) if platform == "darwin" else name.startswith(("live", "ableton live"))
            if matches:
                discovery.inspect_installation(child)
    result = discovery.result
    result["installations"].sort(key=lambda item: item["path"])
    result["candidates"].sort(key=lambda item: (item["installation"], item["path"]))
    result["status"] = "found" if result["candidates"] else "no_candidates"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installation", action="append", metavar="PATH", help="Installation root to inspect (repeatable; replaces all default locations).")
    args = parser.parse_args(argv)
    print(json.dumps(discover_docs(args.installation), indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
