import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stderr
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load(name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cards = load("build_cards")
assets = load("validate_assets")

try:
    import fontTools  # noqa: F401

    HAVE_FONTTOOLS = True
except ModuleNotFoundError:
    HAVE_FONTTOOLS = False

JAKARTA = ZoneInfo("Asia/Jakarta")


class LanguageTests(unittest.TestCase):
    def test_each_repository_counts_once_regardless_of_size(self):
        data = cards.language_shares({
            "kernel": {"C": 900_000_000},
            "app": {"Kotlin": 1_000},
        })
        self.assertEqual(dict(data.shares), {"C": 50.0, "Kotlin": 50.0})
        self.assertEqual(data.repositories, 2)

    def test_mixed_repository_splits_its_weight(self):
        data = cards.language_shares({"a": {"Kotlin": 3, "Dart": 1}, "b": {"Kotlin": 1}})
        self.assertAlmostEqual(dict(data.shares)["Kotlin"], 87.5)
        self.assertAlmostEqual(dict(data.shares)["Dart"], 12.5)

    def test_empty_repositories_are_ignored_and_tail_becomes_other(self):
        repos = {f"r{i}": {f"L{i}": 10} for i in range(9)}
        repos["empty"] = {}
        data = cards.language_shares(repos, top=7)
        self.assertEqual(data.repositories, 9)
        self.assertEqual(data.shares[-1][0], "Other")
        self.assertEqual(len(data.shares), 8)
        self.assertAlmostEqual(sum(percent for _, percent in data.shares), 100.0)

    def test_no_languages_at_all_is_an_error(self):
        with self.assertRaises(ValueError):
            cards.language_shares({"empty": {}})


class StreakTests(unittest.TestCase):
    def days(self, *spec):
        return {date.fromisoformat(day): count for day, count in spec}

    def test_commit_days_use_jakarta_time(self):
        days = cards.commit_days(["2026-10-11T18:30:00Z", "2026-10-11T16:00:00Z"], JAKARTA)
        self.assertEqual(days, {date(2026, 10, 12): 1, date(2026, 10, 11): 1})

    def test_streak_includes_today(self):
        streak = cards.compute_streak(self.days(("2026-10-10", 1), ("2026-10-11", 2), ("2026-10-12", 1)), date(2026, 10, 12))
        self.assertEqual((streak.current, streak.current_start), (3, date(2026, 10, 10)))

    def test_streak_survives_until_today_is_over(self):
        streak = cards.compute_streak(self.days(("2026-10-10", 1), ("2026-10-11", 1)), date(2026, 10, 12))
        self.assertEqual(streak.current, 2)

    def test_gap_resets_current_streak(self):
        streak = cards.compute_streak(self.days(("2026-10-09", 1)), date(2026, 10, 12))
        self.assertEqual((streak.current, streak.current_start), (0, None))

    def test_longest_streak_and_last_year(self):
        streak = cards.compute_streak(
            self.days(("2025-01-01", 1), ("2026-09-01", 1), ("2026-09-02", 4), ("2026-09-03", 1), ("2026-10-12", 2)),
            date(2026, 10, 12),
        )
        self.assertEqual((streak.longest, streak.longest_start, streak.longest_end), (3, date(2026, 9, 1), date(2026, 9, 3)))
        self.assertEqual(streak.last_year, 8)

    def test_fetch_streak_skips_empty_repos_and_tolerates_failures(self):
        requested = []

        def fake(url):
            requested.append(url)
            if "/broken/" in url:
                raise cards.GitHubAPIError("HTTP 500")
            return [{"commit": {"author": {"date": "2026-10-12T01:00:00Z"}}}]

        repos = [
            {"name": "app", "default_branch": "master", "size": 10},
            {"name": "broken", "default_branch": "main", "size": 10},
            {"name": "empty", "default_branch": "main", "size": 0},
        ]
        with patch.object(cards, "request_json", side_effect=fake), redirect_stderr(io.StringIO()):
            streak = cards.fetch_streak(repos, datetime(2026, 10, 12, 9, 0, tzinfo=JAKARTA))
        self.assertEqual(streak.current, 1)
        self.assertFalse(any("/empty/" in url for url in requested))
        self.assertTrue(any("/app/commits?" in url and "sha=master" in url for url in requested))

    def test_fetch_streak_fails_when_every_repository_fails(self):
        with patch.object(cards, "request_json", side_effect=cards.GitHubAPIError("HTTP 503")), redirect_stderr(io.StringIO()):
            with self.assertRaises(cards.GitHubAPIError):
                cards.fetch_streak([{"name": "app", "size": 1}], datetime(2026, 10, 12, tzinfo=JAKARTA))


class OutputBranchTests(unittest.TestCase):
    def test_readme_only_references_published_files(self):
        info = assets.check_output_references()
        self.assertTrue({"clock.svg", "languages.svg", "streak.svg"} <= set(info["output files referenced"]))

    def test_single_output_publisher(self):
        self.assertEqual(assets.output_publishers(), [assets.OUTPUT_PUBLISHER])

    def test_second_output_publisher_is_rejected(self):
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "profile-refresh.yml").write_text("run: git add README.md && git push\n", encoding="utf-8")
            (directory / "profile-cards.yml").write_text("publish_branch: output\n", encoding="utf-8")
            (directory / "snake.yml").write_text("publish_branch: output\n", encoding="utf-8")
            with self.assertRaisesRegex(assets.AssetError, "output branch"):
                assets.check_workflows(directory)


@unittest.skipIf(not HAVE_FONTTOOLS, "fontTools is not installed (pip install -r scripts/requirements-assets.txt)")
class CardRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outlines = load("assetkit").GlyphOutlines()

    def render(self, scene, name):
        with TemporaryDirectory() as temp:
            path = Path(temp) / name
            path.write_text(cards.build_svg(scene, self.outlines), encoding="utf-8")
            return assets.check_svg(path), path.read_text(encoding="utf-8")

    def test_clock_card(self):
        info, svg = self.render(cards.clock_card("Indonesia", datetime(2026, 10, 12, 14, 37, tzinfo=JAKARTA)), "clock.svg")
        self.assertEqual(info["width"], 1200)
        self.assertIn("14:37", svg)  # in the accessible title
        self.assertIn("rotate(78.50 ", svg)  # hour hand at 2:37 = (2 + 37/60) * 30 degrees

    def test_languages_card(self):
        data = cards.language_shares({"a": {"Kotlin": 3, "C": 1}, "b": {"Shell": 5}})
        _, svg = self.render(cards.languages_card(data), "languages.svg")
        self.assertIn("Kotlin 37.5%", svg)

    def test_streak_card(self):
        streak = cards.compute_streak({date(2026, 10, 11): 3, date(2026, 10, 12): 1}, date(2026, 10, 12))
        _, svg = self.render(cards.streak_card(streak), "streak.svg")
        self.assertIn("Current commit streak 2 days", svg)


if __name__ == "__main__":
    unittest.main()
