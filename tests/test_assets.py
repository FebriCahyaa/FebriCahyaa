import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


assets = load("validate_assets")
assetkit = load("assetkit")
builder = load("build_assets")

try:
    import fontTools  # noqa: F401

    HAVE_FONTTOOLS = True
except ModuleNotFoundError:
    HAVE_FONTTOOLS = False

EXPECTED_SCENES = ["flux-loop", "kernel-ci", "terminal-exit", "terminal-intro"]


def tiny_gif(frames=2, loop=0, delay_cs=10):
    """Hand-assembled 1x1 GIF with optional NETSCAPE2.0 loop block."""
    data = bytearray(b"GIF89a" + struct.pack("<HHBBB", 1, 1, 0x80, 0, 0) + b"\x00\x00\x00\xff\xff\xff")
    if loop is not None:
        data += b"\x21\xff\x0bNETSCAPE2.0\x03\x01" + struct.pack("<H", loop) + b"\x00"
    for _ in range(frames):
        data += b"\x21\xf9\x04\x04" + struct.pack("<H", delay_cs) + b"\x00\x00"
        data += b"\x2c" + struct.pack("<HHHHB", 0, 0, 1, 1, 0) + b"\x02\x02\x44\x01\x00"
    return bytes(data + b"\x3b")


def first_lottie():
    return assets.LOTTIE_DIR / f"{EXPECTED_SCENES[-1]}.json"


class CommittedAssetTests(unittest.TestCase):
    def test_every_scene_is_present(self):
        self.assertEqual(assets.scene_names(), EXPECTED_SCENES)
        self.assertEqual(sorted(scene.name for scene in builder.animated_scenes()), EXPECTED_SCENES)

    def test_each_scene_has_consistent_lottie_svg_and_gifs(self):
        for name in assets.scene_names():
            with self.subTest(scene=name):
                assets.check_scene(name)

    def test_gifs_are_animated_looping_and_within_budget(self):
        for name in assets.scene_names():
            lottie = assets.check_lottie(assets.LOTTIE_DIR / f"{name}.json")
            self.assertLess(lottie["seconds"], 15)
            for path in assets.gif_paths(name):
                with self.subTest(gif=path.name):
                    info = assets.check_gif(path, lottie["width"], lottie["height"])
                    self.assertGreater(info.frames, 10)
                    self.assertEqual(info.loop, 0)
                    self.assertLessEqual(info.size, assets.GIF_BUDGET_BYTES)

    def test_no_orphaned_generated_files(self):
        assets.check_orphans()

    def test_devices_card_is_valid_svg_with_reduced_motion_guard(self):
        path = assets.CARDS_DIR / "devices.svg"
        assets.check_svg(path)
        svg = path.read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion", svg)
        for name in ("Redmi Note 13 Pro 5G", "Redmi Note 7", "iPhone 12"):
            self.assertIn(name, svg)

    def test_readme_sections_are_collapsible(self):
        readme = assets.README.read_text(encoding="utf-8")
        self.assertEqual(readme.count("<details open>"), 1)
        self.assertEqual(readme.count("<details"), readme.count("</details>"))
        self.assertEqual(readme.count("<summary><h2>"), 7)

    def test_social_buttons_are_valid_svg(self):
        names = sorted(path.stem for path in assets.SOCIAL_DIR.glob("*.svg"))
        self.assertEqual(names, ["github", "instagram", "telegram"])
        for path in assets.SOCIAL_DIR.glob("*.svg"):
            assets.check_svg(path)

    def test_readme_references_resolve(self):
        info = assets.check_readme()
        self.assertGreaterEqual(info["local"], 10)
        self.assertEqual(info["anchors"], ["about", "activity", "contact", "devices", "now", "toolkit", "work"])

    def test_readme_animations_have_dark_variant_and_static_fallback(self):
        readme = assets.README.read_text(encoding="utf-8")
        self.assertNotIn("<script", readme.lower())
        for name in EXPECTED_SCENES:
            with self.subTest(scene=name):
                self.assertIn(f'src="assets/animations/{name}.gif"', readme)
                self.assertIn(f'srcset="assets/animations/{name}-dark.gif"', readme)
                self.assertIn(f'media="(prefers-reduced-motion: reduce)" srcset="assets/static/{name}.svg"', readme)

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
        data = json.loads(first_lottie().read_text(encoding="utf-8"))
        animated = next(layer["ks"]["o"] for layer in data["layers"] if layer["ks"]["o"].get("a") == 1)
        animated["k"][0]["t"], animated["k"][1]["t"] = animated["k"][1]["t"], animated["k"][0]["t"]
        with self.assertRaisesRegex(assets.AssetError, "increasing"):
            assets.check_lottie(self.write("bad.json", json.dumps(data)))

    def test_lottie_group_without_transform_is_rejected(self):
        data = json.loads(first_lottie().read_text(encoding="utf-8"))
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

    def test_terminal_style_headings_produce_plain_anchors(self):
        self.assertEqual(assets.github_anchor("~/about"), "about")
        self.assertEqual(assets.github_anchor("Featured work"), "featured-work")

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


class TrackTests(unittest.TestCase):
    def test_hold_and_linear_interpolation(self):
        steps = assetkit.Track.steps([(0, 0), (10, 100)])
        self.assertEqual(steps.at(9), (0,))
        self.assertEqual(steps.at(10), (100,))
        ramp = assetkit.Track.ramp([(0, 0), (10, 100)])
        self.assertEqual(ramp.at(5), (50.0,))
        self.assertEqual(ramp.at(20), (100,))

    def test_lottie_keyframes(self):
        self.assertEqual(assetkit.Track.const(100).lottie(), {"a": 0, "k": 100})
        frames = assetkit.Track.ramp([(0, 0), (10, 100)]).lottie()["k"]
        self.assertEqual(frames[0]["o"], {"x": [0], "y": [0]})
        self.assertNotIn("h", frames[0])
        self.assertEqual(assetkit.Track.steps([(0, 0), (4, 1)]).lottie()["k"][0]["h"], 1)

    def test_presence_fades_and_wraps_cleanly(self):
        track = builder.presence([(0, 10), (50, 100)], total=100, fade=5)
        self.assertEqual(track.at(0), (100,))
        self.assertEqual(track.at(30)[0], 0)
        self.assertEqual(track.at(99)[0], 100)


def visible_opacity(element, frame):
    """Layer opacity, or 0 while a typed line has no revealed characters yet."""
    typed = getattr(element, "typed", None)
    if typed and min(typed) > frame:
        return (0,)
    return element.opacity.at(frame)


class SceneTests(unittest.TestCase):
    """Scene timelines; no fonts needed."""

    @classmethod
    def setUpClass(cls):
        cls.scenes = {scene.name: scene for scene in builder.animated_scenes()}

    def test_every_element_is_identical_on_first_and_last_frame_of_finite_motion(self):
        # Loops must return to their first frame, except continuously flowing packets.
        for scene in self.scenes.values():
            for element in scene.elements:
                if element.name.startswith("packet"):
                    continue
                with self.subTest(scene=scene.name, element=element.name):
                    last = scene.frames - 1
                    self.assertEqual(visible_opacity(element, 0), visible_opacity(element, last))
                    if visible_opacity(element, 0)[0] > 0:
                        self.assertEqual(element.offset.at(0), element.offset.at(last))

    def test_hero_typing_is_ordered_and_poster_shows_full_session(self):
        hero = self.scenes["terminal-intro"]
        for element in hero.elements:
            if getattr(element, "typed", None):
                self.assertEqual(element.typed, sorted(element.typed))
                self.assertEqual(len(element.typed), len(element.text))
        visible = {element.name for element in hero.elements if element.opacity.at(hero.poster)[0] > 0}
        self.assertTrue({"output name", "output listing", "prompt 3"} <= visible)
        clear = next(element for element in hero.elements if element.name == "command clear")
        self.assertGreater(clear.typed[0], hero.poster)

    def test_scenes_stay_inside_their_canvas(self):
        for scene in self.scenes.values():
            for element in scene.elements:
                if isinstance(element, assetkit.Text):
                    with self.subTest(scene=scene.name, element=element.name):
                        self.assertLessEqual(element.x + element.width, scene.width)
                        self.assertLessEqual(element.baseline, scene.height)


@unittest.skipIf(not HAVE_FONTTOOLS, "fontTools is not installed (pip install -r scripts/requirements-assets.txt)")
class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outlines = assetkit.GlyphOutlines()

    def test_committed_lottie_and_svg_match_a_fresh_build(self):
        scenes = builder.animated_scenes() + builder.static_scenes()
        for path, text in builder.text_outputs(scenes, self.outlines).items():
            with self.subTest(path=path.name):
                self.assertEqual(text, path.read_text(encoding="utf-8"), "run scripts/build_assets.py")

    def test_contour_conversion_closes_paths(self):
        contours = self.outlines.contours("regular", "o")
        self.assertGreaterEqual(len(contours), 2)  # outer ring and counter
        path = assetkit.contour_to_lottie(*contours[0], 0.017, 0, 0)["ks"]["k"]
        self.assertTrue(path["c"])
        self.assertEqual(len(path["v"]), len(path["i"]))
        self.assertNotEqual(path["v"][0], path["v"][-1])


if __name__ == "__main__":
    unittest.main()
