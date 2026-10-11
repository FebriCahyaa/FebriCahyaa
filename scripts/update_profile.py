#!/usr/bin/env python3
"""Refresh the profile README from public GitHub API data.

No third-party Python packages are required. If the API cannot provide the
profile metrics, the script exits instead of replacing real data with zeros.
The refresh timestamp only changes when the data itself changed, so scheduled
runs do not produce timestamp-only commits.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
USERNAME = "FebriCahyaa"
API_ROOT = "https://api.github.com"
REQUIRED_MARKERS = {
    "METRIC_REPOS": ("<!-- METRIC_REPOS_START -->", "<!-- METRIC_REPOS_END -->"),
    "METRIC_STARS": ("<!-- METRIC_STARS_START -->", "<!-- METRIC_STARS_END -->"),
    "METRIC_FORKS": ("<!-- METRIC_FORKS_START -->", "<!-- METRIC_FORKS_END -->"),
    "METRIC_FOLLOWERS": ("<!-- METRIC_FOLLOWERS_START -->", "<!-- METRIC_FOLLOWERS_END -->"),
    "PROFILE_UPDATED": ("<!-- PROFILE_UPDATED_START -->", "<!-- PROFILE_UPDATED_END -->"),
    "FLUX_LATEST": ("<!-- FLUX_LATEST_START -->", "<!-- FLUX_LATEST_END -->"),
}


class GitHubAPIError(RuntimeError):
    """Raised for failed or malformed GitHub API responses."""


def request_json(url: str) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "FebriCahyaa-profile-readme-updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise GitHubAPIError(f"GitHub API returned HTTP {exc.code} for {url}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GitHubAPIError(f"Could not read valid GitHub API data from {url}: {exc}") from exc
    return payload


def validate_markers(content: str) -> None:
    missing: list[str] = []
    for name, (start, end) in REQUIRED_MARKERS.items():
        if content.count(start) != 1 or content.count(end) != 1:
            missing.append(name)
        elif content.index(start) > content.index(end):
            missing.append(f"{name} (markers out of order)")
    if missing:
        raise ValueError("README marker validation failed: " + ", ".join(missing))


def marker_value(content: str, name: str) -> str:
    start, end = REQUIRED_MARKERS[name]
    return content[content.index(start) + len(start) : content.index(end)]


def replace_marker(content: str, name: str, value: str) -> str:
    start, end = REQUIRED_MARKERS[name]
    pattern = re.escape(start) + r".*?" + re.escape(end)
    replacement = f"{start}{value}{end}"
    updated, count = re.subn(pattern, lambda _: replacement, content, count=1, flags=re.DOTALL)
    if count != 1:
        raise ValueError(f"Unable to update README marker: {name}")
    return updated


def paginated_owned_repositories() -> list[dict[str, object]]:
    repositories: list[dict[str, object]] = []
    page = 1
    while True:
        query = urllib.parse.urlencode({"type": "owner", "per_page": 100, "page": page, "sort": "updated"})
        payload = request_json(f"{API_ROOT}/users/{USERNAME}/repos?{query}")
        if not isinstance(payload, list):
            raise GitHubAPIError("Unexpected response when listing public repositories.")
        if not payload:
            break
        for item in payload:
            if isinstance(item, dict) and not item.get("private", False):
                repositories.append(item)
        if len(payload) < 100:
            break
        page += 1
        if page > 1000:
            raise GitHubAPIError("Repository pagination safety limit reached.")
    return repositories


def number(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


FLUX_UNAVAILABLE_HTML = (
    'Latest Flux commit is temporarily unavailable. '
    '<a href="https://github.com/FebriCahyaa/Flux/commits">Browse commit history</a>.'
)


def flux_latest_html() -> str | None:
    """Return the latest Flux commit as HTML, or None if it cannot be fetched."""
    try:
        repo = request_json(f"{API_ROOT}/repos/{USERNAME}/Flux")
        if not isinstance(repo, dict):
            raise GitHubAPIError("Unexpected Flux repository response.")
        branch = repo.get("default_branch")
        if not isinstance(branch, str) or not branch:
            raise GitHubAPIError("Flux default branch was not returned by the API.")
        query = urllib.parse.urlencode({"sha": branch, "per_page": 1})
        commits = request_json(f"{API_ROOT}/repos/{USERNAME}/Flux/commits?{query}")
        if not isinstance(commits, list) or not commits or not isinstance(commits[0], dict):
            raise GitHubAPIError("No latest commit was returned for Flux.")
        item = commits[0]
        sha_full = item.get("sha")
        commit = item.get("commit")
        if not isinstance(sha_full, str) or not re.fullmatch(r"[0-9a-fA-F]{7,40}", sha_full) or not isinstance(commit, dict):
            raise GitHubAPIError("Latest Flux commit has an invalid shape.")
        message = commit.get("message", "Latest commit")
        if not isinstance(message, str):
            message = "Latest commit"
        message = message.splitlines()[0][:100]
        author = commit.get("author")
        date = author.get("date", "") if isinstance(author, dict) else ""
        date_label = html.escape(date[:10] if isinstance(date, str) and date else "date unavailable")
        safe_message = html.escape(message, quote=True)
        short_sha = sha_full[:7]
        commit_url = f"https://github.com/{USERNAME}/Flux/commit/{sha_full}"
        return (
            f'<code>{short_sha}</code> · '
            f'<a href="{commit_url}">{safe_message}</a> · '
            f'<small>{date_label}</small>'
        )
    except (GitHubAPIError, ValueError) as exc:
        # Metrics can still be refreshed when a secondary project endpoint is unavailable.
        print(f"Warning: latest Flux commit could not be refreshed: {exc}", file=sys.stderr)
        return None


def refresh() -> bool:
    original = README.read_text(encoding="utf-8")
    validate_markers(original)
    content = original

    user = request_json(f"{API_ROOT}/users/{USERNAME}")
    if not isinstance(user, dict) or user.get("login", "").lower() != USERNAME.lower():
        raise GitHubAPIError("The GitHub API did not return the expected profile account.")

    repos = paginated_owned_repositories()
    original_repos = [repo for repo in repos if not bool(repo.get("fork", False))]
    totals = {
        "METRIC_REPOS": str(number(user.get("public_repos"))),
        "METRIC_STARS": str(sum(number(repo.get("stargazers_count")) for repo in original_repos)),
        "METRIC_FORKS": str(sum(number(repo.get("forks_count")) for repo in original_repos)),
        "METRIC_FOLLOWERS": str(number(user.get("followers"))),
    }
    for marker, value in totals.items():
        content = replace_marker(content, marker, value)

    flux_html = flux_latest_html()
    if flux_html is not None:
        content = replace_marker(content, "FLUX_LATEST", flux_html)
    elif not marker_value(content, "FLUX_LATEST").strip():
        content = replace_marker(content, "FLUX_LATEST", FLUX_UNAVAILABLE_HTML)
    # Otherwise keep the last known commit rather than replacing it with a placeholder.

    if content == original:
        print("README data is unchanged; timestamp left as is.")
        return False
    updated = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d %b %Y, %H:%M WIB")
    content = replace_marker(content, "PROFILE_UPDATED", updated)
    README.write_text(content, encoding="utf-8")
    print("README updated:")
    for marker, value in totals.items():
        print(f"  {marker.removeprefix('METRIC_').lower()}: {value}")
    print(f"  refreshed_at: {updated}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate README markers without making network requests.")
    args = parser.parse_args()
    try:
        content = README.read_text(encoding="utf-8")
        validate_markers(content)
        if args.check:
            print("README marker check passed.")
            return 0
        refresh()
        return 0
    except (OSError, ValueError, GitHubAPIError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
