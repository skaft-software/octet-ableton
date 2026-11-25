"""Bundled-skill structure and documented examples, NOT real-Live qualification."""

import ast
import json
import re
import tempfile
import unittest
from pathlib import Path

from octet_ableton.presentation import compact_compose
from remote_script.OctetBridge.engine import ACTION_FIELDS, LiveEngine
from remote_script.OctetBridge.server import BridgeError
from test_live_bridge import Song, Track, application

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "ableton-live"
DOCS = ROOT / "docs" / "live-skill"
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def evidence_section_ids(value):
    """Evidence records vary by topic; collect their exact numbered-section IDs."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from evidence_section_ids(key)
            yield from evidence_section_ids(item)
    elif isinstance(value, list):
        for item in value:
            yield from evidence_section_ids(item)
    elif isinstance(value, str) and re.fullmatch(r"\d+(?:\.\d+)+", value):
        yield value


class LiveSkillTests(unittest.TestCase):
    def test_spec_frontmatter_and_size(self):
        text = (SKILL / "SKILL.md").read_text()
        self.assertTrue(text.startswith("---\n"))
        front = text.split("---", 2)[1]
        name = re.search(r"^name: (.+)$", front, re.M).group(1)
        description = re.search(r"^description: (.+)$", front, re.M).group(1)
        self.assertEqual(name, SKILL.name)
        self.assertRegex(name, r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        self.assertLessEqual(len(name), 64)
        self.assertTrue(1 <= len(description) <= 1024)
        self.assertLess(len(text.splitlines()), 500)
        fields = set(re.findall(r"^([a-z-]+):", front, re.M))
        self.assertLessEqual(fields, {"name", "description", "license", "compatibility", "metadata", "allowed-tools"})

    def test_references_and_helper_are_one_hop_and_portable(self):
        targets = set()
        for link in LINK.findall((SKILL / "SKILL.md").read_text()):
            target = link.split("#", 1)[0]
            self.assertFalse(target.startswith(("/", "http:", "https:")))
            path = (SKILL / target).resolve()
            self.assertTrue(path.is_relative_to(SKILL.resolve()))
            self.assertTrue(path.is_file(), target)
            targets.add(path)
        expected = set((SKILL / "references").glob("*.md"))
        expected |= set((SKILL / "scripts").glob("*.py"))
        self.assertTrue(expected)
        self.assertLessEqual({p.resolve() for p in expected}, targets)

    def test_no_source_document_or_private_paths_in_runtime_package(self):
        for path in SKILL.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            self.assertFalse(path.is_symlink(), path)
            self.assertNotIn(path.suffix.lower(), {".pdf", ".png", ".jpg", ".zip"}, path)
            if path.suffix in {".md", ".py", ".json"}:
                text = path.read_text()
                for forbidden in ("/Users/", "live12-manual-en.pdf", "manual-layout.txt", "=== PDF page", "/tmp/octet-live12-distill"):
                    self.assertNotIn(forbidden, text, path)

    def test_every_chapter_and_numbered_section_is_indexed(self):
        coverage = json.loads((DOCS / "coverage.json").read_text())
        self.assertEqual(coverage["source"]["pages"], 1039)
        chapters = coverage["chapters"]
        self.assertEqual([c["chapter"] for c in chapters], list(range(1, 44)))
        self.assertEqual(chapters[0]["start_page"], 23)
        self.assertEqual(chapters[-1]["end_page"], 1039)
        section_ids = []
        for i, chapter in enumerate(chapters):
            with self.subTest(chapter=chapter["chapter"]):
                self.assertTrue((SKILL / chapter["reference"]).is_file())
                evidence_path = DOCS / chapter["evidence"]
                self.assertTrue(evidence_path.is_file())
                evidence = json.loads(evidence_path.read_text())
                self.assertLessEqual(set(chapter["section_ids"]), set(evidence_section_ids(evidence)))
                self.assertLessEqual(chapter["start_page"], chapter["end_page"])
                if i:
                    self.assertEqual(chapters[i - 1]["end_page"] + 1, chapter["start_page"])
                self.assertTrue(all(s.startswith(str(chapter["chapter"]) + ".") for s in chapter["section_ids"]))
                section_ids.extend(chapter["section_ids"])
        self.assertEqual(len(section_ids), len(set(section_ids)))
        self.assertEqual(len(section_ids), 837)

    def test_evaluation_cases_have_real_checks_and_held_out_cases(self):
        data = json.loads((DOCS / "eval-cases.json").read_text())
        for split in ("development", "holdout"):
            cases = [c for c in data["cases"] if c["split"] == split]
            self.assertGreaterEqual(len(cases), 3)
            for case in cases:
                self.assertTrue(case["query"])
                self.assertTrue(case["inputs"])
                self.assertGreaterEqual(len(case["success_checks"]), 3)
                self.assertTrue(case["critical_failures"])
        self.assertLessEqual({"positive", "paraphrase", "ambiguous", "negative"}, {p["kind"] for p in data["trigger_probes"]})

    def test_documented_operations_match_current_extension(self):
        text = (SKILL / "references" / "octet-workflow.md").read_text()
        table = text.split("Supported operation names:", 1)[1].split("A MIDI-only preview", 1)[0]
        ops = set()
        for line in table.splitlines():
            if line.startswith("| `"):
                ops.update(re.findall(r"`([a-z_]+)`", line.split("|", 2)[1]))
        self.assertEqual(ops, set(ACTION_FIELDS))
        module = ast.parse((ROOT / "octet_ableton" / "extension.py").read_text())
        schema = next(ast.literal_eval(node.value) for node in module.body
                      if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "COMPOSE_SCHEMA" for t in node.targets))
        self.assertEqual(ops, set(schema["properties"]["actions"]["items"]["properties"]["op"]["enum"]))

    def test_documented_json_examples_with_fake_live(self):
        text = (SKILL / "references" / "octet-workflow.md").read_text()
        examples = [json.loads(block) for block in re.findall(r"```json\n(.*?)\n```", text, re.S)]
        self.assertTrue(examples)
        song = Song()
        engine = LiveEngine(song, application(song))
        modes = set()
        for example in examples:
            with self.subTest(example=example):
                method = "compose" if "actions" in example else "lom"
                result = engine.handle(method, example)  # Production validation + fake Live.
                if method == "compose":
                    modes.add("compose")
                    self.assertTrue(result["ok"], result)
                    self.assertEqual(result["status"], "dry_run")
                    with tempfile.TemporaryDirectory() as directory:
                        summary = compact_compose(result, Path(directory))
                        self.assertNotIn("receipts", summary)
                        self.assertEqual(json.loads(Path(summary["receipt_path"]).read_text()), result)
                        self.assertEqual(summary["total_actions"], len(example["actions"]))
                elif "queries" in example:
                    modes.add("queries")
                    self.assertTrue(result["ok"], result)
                    self.assertEqual(len(result["results"]), len(example["queries"]))
                    for query, entry in zip(example["queries"], result["results"]):
                        self.assertEqual(entry["result"]["view"], query["view"])
                elif example["view"] == "device":
                    modes.add("device")
                    self.assertEqual(result["columns"], ["index"] + example["fields"])
                    self.assertEqual(result["rows"], [[0, "Frequency", 20, 20000, False],
                                                       [1, "Dry/Wet", 0, 1, False]])
                else:
                    modes.add("session")
                    self.assertEqual(result["transport"]["bpm"], song.tempo)
                    self.assertEqual(result["tracks"][0]["devices"][0]["name"], "Filter")
        self.assertEqual(modes, {"session", "device", "queries", "compose"})
        self.assertEqual(len(song.tracks), 1)
        self.assertEqual(song.undo, [])
        self.assertEqual(song.tracks[0].arrangement_clips, [])

    def test_documented_batch_refreshes_values_and_indices(self):
        text = (SKILL / "references" / "octet-workflow.md").read_text()
        examples = [json.loads(block) for block in re.findall(r"```json\n(.*?)\n```", text, re.S)]
        batch = next(example for example in examples if "queries" in example)
        song = Song()
        engine = LiveEngine(song, application(song))
        first = engine.handle("lom", batch)
        target = song.tracks[0]
        target.devices[0].parameters[0].value = 1234
        song.tracks.insert(0, Track("Inserted"))
        session = engine.handle("lom", {"view": "session"})
        self.assertEqual([track["index"] for track in session["tracks"]], [0, 1])
        batch["queries"][0]["track_indices"] = [1]
        batch["queries"][1]["track_index"] = 1
        fresh = engine.handle("lom", batch)
        self.assertEqual(first["results"][1]["result"]["rows"][0], [0, 1000, True])
        self.assertEqual(fresh["results"][1]["result"]["rows"][0], [0, 1234, True])
        self.assertEqual(song.undo, [])

    def test_documented_inspection_boundaries_use_real_validation(self):
        engine = LiveEngine(Song(), None)
        query = {"view": "device", "track_index": 0, "device": "Filter"}
        result = engine.handle("lom", {"queries": [query] * 16})
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["results"]), 16)
        invalid = [
            {"queries": [query] * 17},
            {"queries": [query], "view": "session"},
            {"view": "session", "fields": ["name"]},
            dict(query, parameters=[0], offset=0),
            dict(query, fields=["name", "name"]),
            dict(query, parameters=["0"]),  # Name, not an integer selector.
        ]
        for arguments in invalid:
            with self.subTest(arguments=arguments), self.assertRaises(BridgeError):
                engine.handle("lom", arguments)

    def test_audio_trial_supplement_is_unrun_and_has_observable_checks(self):
        data = json.loads((SKILL / "assets" / "eval-cases.json").read_text())
        self.assertEqual(data["status"], "not-run")
        self.assertEqual(data["comparison_protocol"]["results"], [])
        self.assertEqual({case["split"] for case in data["cases"]},
                         {"development", "validation", "holdout"})
        for case in data["cases"]:
            self.assertTrue(case["inputs"])
            self.assertTrue(case["query"])
            self.assertTrue(case["success_checks"])
            self.assertTrue(case["critical_failures"])
        self.assertEqual(len({case["id"] for case in data["cases"]}), len(data["cases"]))

    def test_meter_example_against_fake_live_timing(self):
        song = Song()
        engine = LiveEngine(song, application(song))
        result = engine.handle("compose", {"dry_run": False, "actions": [
            {"op": "set_transport", "signature_numerator": 7, "signature_denominator": 8},
            {"op": "write_arrangement_midi_clip", "track_index": 0, "start_bar": 5,
             "length_bars": 1, "notes": []},
        ]})
        self.assertTrue(result["ok"], result)
        clip = song.tracks[0].arrangement_clips[0]
        self.assertEqual(clip.start_time, 14)
        self.assertEqual(clip.length, 3.5)
        self.assertEqual(clip.start_time * 60 / song.tempo, 7)


if __name__ == "__main__":
    unittest.main()
