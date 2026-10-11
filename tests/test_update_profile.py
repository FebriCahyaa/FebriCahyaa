import importlib.util
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "update_profile.py"
SPEC = importlib.util.spec_from_file_location("update_profile", SCRIPT)
assert SPEC and SPEC.loader
updater = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updater)


class MarkerTests(unittest.TestCase):
    def setUp(self):
        self.readme = updater.README.read_text(encoding="utf-8")

    def test_readme_contains_each_required_marker_once(self):
        updater.validate_markers(self.readme)

    def test_replace_marker_changes_only_its_region(self):
        updated = updater.replace_marker(self.readme, "METRIC_REPOS", "123")
        self.assertIn("<!-- METRIC_REPOS_START -->123<!-- METRIC_REPOS_END -->", updated)
        self.assertIn("<!-- METRIC_STARS_START -->", updated)
        self.assertEqual(updated.count("<!-- METRIC_REPOS_START -->"), 1)

    def test_duplicate_marker_is_rejected(self):
        broken = self.readme + "\n<!-- METRIC_REPOS_START -->extra<!-- METRIC_REPOS_END -->\n"
        with self.assertRaises(ValueError):
            updater.validate_markers(broken)

    def test_reversed_marker_is_rejected(self):
        broken = self.readme.replace(
            "<!-- METRIC_FOLLOWERS_START -->—<!-- METRIC_FOLLOWERS_END -->",
            "<!-- METRIC_FOLLOWERS_END -->—<!-- METRIC_FOLLOWERS_START -->",
        )
        with self.assertRaises(ValueError):
            updater.validate_markers(broken)

    def test_refresh_updates_metrics_and_escapes_commit_message(self):
        with TemporaryDirectory() as temp_dir:
            temp_readme = Path(temp_dir) / "README.md"
            temp_readme.write_text(self.readme, encoding="utf-8")
            user = {"login": "FebriCahyaa", "public_repos": 17, "followers": 9}
            repos = [
                {"private": False, "fork": False, "stargazers_count": 5, "forks_count": 2},
                {"private": False, "fork": True, "stargazers_count": 100, "forks_count": 50},
            ]
            flux_repo = {"default_branch": "main"}
            commits = [{
                "sha": "1234567890abcdef1234567890abcdef12345678",
                "commit": {
                    "message": "feat: <new> & improved",
                    "author": {"date": "2026-10-11T02:00:00Z"},
                },
            }]

            def fake_request(url):
                if url == f"{updater.API_ROOT}/users/{updater.USERNAME}":
                    return user
                if url.startswith(f"{updater.API_ROOT}/users/{updater.USERNAME}/repos?"):
                    return repos
                if url == f"{updater.API_ROOT}/repos/{updater.USERNAME}/Flux":
                    return flux_repo
                if url.startswith(f"{updater.API_ROOT}/repos/{updater.USERNAME}/Flux/commits?"):
                    return commits
                raise AssertionError(f"Unexpected URL: {url}")

            with patch.object(updater, "README", temp_readme), patch.object(updater, "request_json", side_effect=fake_request):
                self.assertTrue(updater.refresh())
                updated = temp_readme.read_text(encoding="utf-8")

            self.assertIn("<!-- METRIC_REPOS_START -->17<!-- METRIC_REPOS_END -->", updated)
            self.assertIn("<!-- METRIC_STARS_START -->5<!-- METRIC_STARS_END -->", updated)
            self.assertIn("<!-- METRIC_FORKS_START -->2<!-- METRIC_FORKS_END -->", updated)
            self.assertIn("<!-- METRIC_FOLLOWERS_START -->9<!-- METRIC_FOLLOWERS_END -->", updated)
            self.assertIn("&lt;new&gt; &amp; improved", updated)
            self.assertIn("2026-10-11", updated)


if __name__ == "__main__":
    unittest.main()
