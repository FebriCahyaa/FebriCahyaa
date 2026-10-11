import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


assets = load("validate_assets")

try:
    import fontTools  # noqa: F401

    builder = load("build_terminal_assets")
except ModuleNotFoundError:
    builder = None


def tiny_gif(frames=2, loop=0, delay_cs=10):
    """Hand-assembled 1x1 GIF with optional NETSCAPE2.0 loop block."""
    data = bytearray(b"GIF89a" + struct.pack("<HHBBB", 1, 1, 0x80, 0, 0) + b"\x00\x00\x00\xff\xff\xff")
    if loop is not None:
        data += b"\x21\xff\x0bNETSCAPE2.0\x03\x01" + struct.pack("<H", loop) + b"\x00"
    for _ in range(frames):
        data += b"\x21\xf9\x04\x04" + struct.pack("<H", delay_cs) + b"\x00\x00"
        data += b"\x2c" + struct.pack("<HHHHB", 0, 0, 1, 1, 0) + b"\x02\x02\x44\x01\x00"
    return bytes(data + b"\x3b")


class CommittedAssetTests(unittest.TestCase):
    def test_hero_svg_is_valid_and_accessible(self):
        info = assets.check_svg(assets.SVG_PATH)
        self.assertEqual((info["width"], info["height"]), (1200, 420))

    def test_lottie_source_is_structurally_valid(self):
        info = assets.check_lottie(assets.LOTTIE_PATH)
        self.assertEqual((info["width"], info["height"]), (1200, 420))
        self.assertGreater(info["frames"], 1)
        self.assertLess(info["seconds"], 15)

    def test_gifs_are_animated_looping_and_match_lottie(self):
        lottie = assets.check_lottie(assets.LOTTIE_PATH)
        for path in assets.GIF_PATHS:
            with self.subTest(gif=path.name):
                info = assets.check_gif(path, lottie["width"], lottie["height"])
                self.assertGreater(info.frames, 10)
                self.assertEqual(info.loop, 0)
                self.assertLessEqual(info.size, assets.GIF_BUDGET_BYTES)
                self.assertAlmostEqual(info.duration_ms, lottie["seconds"] * 1000, delta=20)

    def test_readme_references_resolve(self):
        info = assets.check_readme()
        self.assertGreaterEqual(info["local"], 3)

    def test_readme_hero_uses_local_animation_with_static_fallback(self):
        readme = assets.README.read_text(encoding="utf-8")
        self.assertIn('src="assets/animations/terminal-intro.gif"', readme)
        self.assertIn('srcset="assets/animations/terminal-intro-dark.gif"', readme)
        self.assertIn('media="(prefers-reduced-motion: reduce)" srcset="assets/profile-hero.svg"', readme)
        self.assertNotIn("<script", readme.lower())

    def test_only_the_refresh_workflow_writes_readme(self):
        self.assertEqual(assets.check_workflows()["writers"], [assets.README_WRITER])

    def test_workflow_yaml_parses(self):
        try:
            import yaml
        except ModuleNotFoundError:
            self.skipTest("PyYAML is not installed")
        for workflow in assets.WORKFLOWS.glob("*.yml"):
            with self.subTest(workflow=workflow.name):
                document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
                self.assertIn("jobs", document)
                for job in document["jobs"].values():
                    self.assertIn("timeout-minutes", job)


class ValidatorNegativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)

    def write(self, name, content):
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def test_gif_parser_reads_frames_delays_and_loop(self):
        info = assets.parse_gif(self.write("ok.gif", tiny_gif(frames=3, delay_cs=7)))
        self.assertEqual((info.frames, info.delays_cs, info.loop), (3, [7, 7, 7], 0))
        assets.check_gif(self.dir / "ok.gif", 1, 1)

    def test_single_frame_gif_is_rejected(self):
        with self.assertRaisesRegex(assets.AssetError, "not animated"):
            assets.check_gif(self.write("still.gif", tiny_gif(frames=1)), 1, 1)

    def test_gif_without_loop_block_is_rejected(self):
        with self.assertRaisesRegex(assets.AssetError, "loop"):
            assets.check_gif(self.write("once.gif", tiny_gif(loop=None)), 1, 1)

    def test_truncated_gif_is_rejected(self):
        with self.assertRaises(assets.AssetError):
            assets.parse_gif(self.write("cut.gif", tiny_gif()[:-12]))

    def test_lottie_with_unordered_keyframes_is_rejected(self):
        data = json.loads(assets.LOTTIE_PATH.read_text(encoding="utf-8"))
        keys = data["layers"][0]["ks"]["o"]["k"]
        keys[0]["t"], keys[1]["t"] = keys[1]["t"], keys[0]["t"]
        with self.assertRaisesRegex(assets.AssetError, "increasing"):
            assets.check_lottie(self.write("bad.json", json.dumps(data)))

    def test_lottie_group_without_transform_is_rejected(self):
        data = json.loads(assets.LOTTIE_PATH.read_text(encoding="utf-8"))
        data["layers"][0]["shapes"][0]["it"].pop()
        with self.assertRaisesRegex(assets.AssetError, "transform"):
            assets.check_lottie(self.write("bad.json", json.dumps(data)))

    def test_svg_with_external_reference_is_rejected(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10" role="img">'
            '<title>t</title><desc>d</desc><use href="https://example.com/x.svg#a"/></svg>'
        )
        with self.assertRaisesRegex(assets.AssetError, "external"):
            assets.check_svg(self.write("bad.svg", svg))

    def test_readme_with_missing_asset_broken_anchor_and_no_alt_is_rejected(self):
        readme = self.write("README.md", '## Hello\n<img src="nope.gif" />\n<a href="#missing">x</a>\n')
        with self.assertRaises(assets.AssetError) as caught:
            assets.check_readme(readme)
        message = str(caught.exception)
        self.assertIn("missing local file nope.gif", message)
        self.assertIn("#missing", message)
        self.assertIn("without alt", message)

    def test_competing_readme_writer_is_rejected(self):
        self.write("workflows/profile-refresh.yml", "run: |\n  git add README.md\n  git push\n")
        self.write("workflows/legacy.yml", "run: |\n  sed -i s/x/y/ README.md\n  git commit -am x\n")
        with self.assertRaisesRegex(assets.AssetError, "legacy.yml"):
            assets.check_workflows(self.dir / "workflows")

    def test_legacy_markers_and_minute_schedules_are_rejected(self):
        self.write("a/profile-refresh.yml", "run: git add README.md && git push\n")
        self.write("a/time.yml", "on:\n  schedule:\n    - cron: \"*/5 * * * *\"\n")
        with self.assertRaisesRegex(assets.AssetError, "minute-level"):
            assets.check_workflows(self.dir / "a")
        self.write("b/profile-refresh.yml", "run: git add README.md && git push\n")
        self.write("b/stats.yml", "run: echo <!--STATS_REPOS-->\n")
        with self.assertRaisesRegex(assets.AssetError, "retired"):
            assets.check_workflows(self.dir / "b")


@unittest.skipIf(builder is None, "fontTools is not installed (pip install -r scripts/requirements-assets.txt)")
class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scene = builder.build_scene()
        cls.outlines = builder.GlyphOutlines()

    def test_loop_is_seamless(self):
        self.assertEqual(self.scene.cursor[0], self.scene.cursor[-1])
        self.assertEqual(len(self.scene.cursor), self.scene.total_frames)
        cleared = [line for line in self.scene.lines if line.clear is not None]
        persistent = [line for line in self.scene.lines if line.clear is None]
        self.assertEqual([line.name for line in persistent], ["prompt 1"])
        self.assertTrue(all(line.clear < self.scene.total_frames for line in cleared))

    def test_typed_characters_appear_in_order(self):
        for line in self.scene.lines:
            if line.typed:
                with self.subTest(line=line.name):
                    self.assertEqual(len(line.typed), len(line.text))
                    self.assertEqual(line.typed, sorted(line.typed))

    def test_committed_lottie_and_svg_match_a_fresh_build(self):
        lottie = builder.serialize_lottie(builder.build_lottie(self.scene, self.outlines))
        svg = builder.build_svg(self.scene, self.outlines)
        self.assertEqual(lottie, builder.LOTTIE_PATH.read_text(encoding="utf-8"), "run scripts/build_terminal_assets.py")
        self.assertEqual(svg, builder.SVG_PATH.read_text(encoding="utf-8"), "run scripts/build_terminal_assets.py")

    def test_svg_poster_shows_the_full_session(self):
        svg = builder.build_svg(self.scene, self.outlines)
        poster = self.scene.poster_frame
        visible = [
            line.name
            for line in self.scene.lines
            if (line.typed[0] if line.typed else line.appear) <= poster and (line.clear is None or line.clear > poster)
        ]
        self.assertIn("output name", visible)
        self.assertIn("output listing", visible)
        self.assertNotIn("command clear", visible)
        self.assertIn("<title", svg)

    def test_contour_conversion_closes_paths(self):
        contours = self.outlines.contours("regular", "o")
        self.assertGreaterEqual(len(contours), 2)  # outer ring and counter
        path = builder.contour_to_lottie(*contours[0], 0.017, 0, 0)["ks"]["k"]
        self.assertTrue(path["c"])
        self.assertEqual(len(path["v"]), len(path["i"]))
        self.assertNotEqual(path["v"][0], path["v"][-1])


if __name__ == "__main__":
    unittest.main()
