import importlib.util
import io
import unittest
from contextlib import redirect_stdout
from tempfile import TemporaryDirectory
from unittest.mock import patch
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "update_profile.py"
SPEC = importlib.util.spec_from_file_location("update_profile", SCRIPT)
assert SPEC and SPEC.loader
updater = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updater)

USER = {"login": "FebriCahyaa", "public_repos": 17, "followers": 9}
REPOS = [
    {"private": False, "fork": False, "stargazers_count": 5, "forks_count": 2},
    {"private": False, "fork": True, "stargazers_count": 100, "forks_count": 50},
]
COMMITS = [{
    "sha": "1234567890abcdef1234567890abcdef12345678",
    "commit": {
        "message": "feat: <new> & improved",
        "author": {"date": "2026-10-11T02:00:00Z"},
    },
}]


def fake_api(flux_branch="main", flux_error=None, requested=None):
    """Build a request_json replacement that serves canned GitHub API data."""

    def fake_request(url):
        if requested is not None:
            requested.append(url)
        if url == f"{updater.API_ROOT}/users/{updater.USERNAME}":
            return USER
        if url.startswith(f"{updater.API_ROOT}/users/{updater.USERNAME}/repos?"):
            return REPOS
        if url.startswith(f"{updater.API_ROOT}/repos/{updater.USERNAME}/Flux"):
            if flux_error:
                raise flux_error
            if url == f"{updater.API_ROOT}/repos/{updater.USERNAME}/Flux":
                return {"default_branch": flux_branch}
            return COMMITS
        raise AssertionError(f"Unexpected URL: {url}")

    return fake_request


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
        start, end = updater.REQUIRED_MARKERS["METRIC_FOLLOWERS"]
        value = updater.marker_value(self.readme, "METRIC_FOLLOWERS")
        broken = self.readme.replace(f"{start}{value}{end}", f"{end}{value}{start}")
        self.assertNotEqual(broken, self.readme)
        with self.assertRaises(ValueError):
            updater.validate_markers(broken)


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.readme = updater.README.read_text(encoding="utf-8")
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.temp_readme = Path(self.temp_dir.name) / "README.md"
        self.temp_readme.write_text(self.readme, encoding="utf-8")

    def refresh(self, **api_options):
        with patch.object(updater, "README", self.temp_readme), patch.object(
            updater, "request_json", side_effect=fake_api(**api_options)
        ), redirect_stdout(io.StringIO()):
            changed = updater.refresh()
        return changed, self.temp_readme.read_text(encoding="utf-8")

    def test_refresh_updates_metrics_and_escapes_commit_message(self):
        changed, updated = self.refresh()
        self.assertTrue(changed)
        self.assertIn("<!-- METRIC_REPOS_START -->17<!-- METRIC_REPOS_END -->", updated)
        self.assertIn("<!-- METRIC_STARS_START -->5<!-- METRIC_STARS_END -->", updated)
        self.assertIn("<!-- METRIC_FORKS_START -->2<!-- METRIC_FORKS_END -->", updated)
        self.assertIn("<!-- METRIC_FOLLOWERS_START -->9<!-- METRIC_FOLLOWERS_END -->", updated)
        self.assertIn("&lt;new&gt; &amp; improved", updated)
        self.assertNotIn("<new>", updated)
        self.assertIn("2026-10-11", updated)
        self.assertRegex(updater.marker_value(updated, "PROFILE_UPDATED"), r"^\d{2} \w{3} \d{4}, \d{2}:\d{2} WIB$")

    def test_refresh_is_idempotent_and_skips_timestamp_only_changes(self):
        self.refresh()
        first = self.temp_readme.read_text(encoding="utf-8")
        with patch.object(updater, "datetime") as fake_datetime:
            fake_datetime.now.return_value.strftime.return_value = "01 Jan 2030, 00:00 WIB"
            changed, second = self.refresh()
        self.assertFalse(changed)
        self.assertEqual(first, second)

    def test_flux_failure_keeps_last_known_commit(self):
        before = updater.marker_value(self.readme, "FLUX_LATEST")
        changed, updated = self.refresh(flux_error=updater.GitHubAPIError("HTTP 502"))
        self.assertTrue(changed)  # metrics still refresh
        self.assertEqual(updater.marker_value(updated, "FLUX_LATEST"), before)
        self.assertIn("<!-- METRIC_REPOS_START -->17<!-- METRIC_REPOS_END -->", updated)

    def test_flux_failure_with_empty_marker_uses_placeholder(self):
        empty = updater.replace_marker(self.readme, "FLUX_LATEST", "")
        self.temp_readme.write_text(empty, encoding="utf-8")
        _, updated = self.refresh(flux_error=updater.GitHubAPIError("HTTP 502"))
        self.assertEqual(updater.marker_value(updated, "FLUX_LATEST"), updater.FLUX_UNAVAILABLE_HTML)

    def test_flux_commit_uses_default_branch_from_api(self):
        requested = []
        self.refresh(flux_branch="master", requested=requested)
        commit_urls = [url for url in requested if "/Flux/commits?" in url]
        self.assertEqual(len(commit_urls), 1)
        self.assertIn("sha=master", commit_urls[0])

    def test_metrics_failure_leaves_readme_untouched(self):
        def failing(url):
            raise updater.GitHubAPIError("HTTP 503")

        with patch.object(updater, "README", self.temp_readme), patch.object(updater, "request_json", side_effect=failing):
            with self.assertRaises(updater.GitHubAPIError):
                updater.refresh()
        self.assertEqual(self.temp_readme.read_text(encoding="utf-8"), self.readme)


if __name__ == "__main__":
    unittest.main()
