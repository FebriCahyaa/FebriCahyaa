#!/usr/bin/env python3
"""Build the live profile cards published to the ``output`` branch.

Cards (SVG, same visual language as the committed assets):

* ``clock.svg``     location from the GitHub profile and local time at the last refresh
* ``languages.svg`` language mix across original public repositories, each repository weighted equally
* ``streak.svg``    commit streak from commits authored on the default branches of original repositories

The profile-cards workflow runs this every 30 minutes and publishes the result
to the ``output`` branch, so ``main`` gets no automated commits for it. A card
whose data cannot be fetched keeps its previously published file.

    GH_TOKEN=... python3 scripts/build_cards.py --out dist
"""
from __future__ import annotations

import argparse
import math
import sys
import urllib.parse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from assetkit import Circle, Raw, Rect, Run, Scene, Text, build_svg, text_width  # noqa: E402
from build_assets import C, PAD_X, window  # noqa: E402
from update_profile import API_ROOT, USERNAME, GitHubAPIError, paginated_owned_repositories, request_json  # noqa: E402

TIMEZONE = "Asia/Jakarta"
TIMEZONE_LABEL = "WIB (UTC+7)"
REFRESH_NOTE = "updated every 30 min by GitHub Actions"
CARD_FILES = ("clock.svg", "languages.svg", "streak.svg")
LANGUAGE_COLORS = ("#B3A4FF", "#7DD3AE", "#F08A7E", "#E9C46A", "#7FB7F0", "#E58FB3", "#9FD6D2")
OTHER_COLOR = "#5F646D"
STREAK_LEVELS = ("#1A1D23", "#3B3466", "#5B4DA8", "#8F7CF0", "#B3A4FF")


# --------------------------------------------------------------------------- data


@dataclass
class Languages:
    shares: list[tuple[str, float]]  # (language, percent), descending, top entries plus "Other"
    repositories: int


@dataclass
class Streak:
    current: int
    current_start: date | None
    longest: int
    longest_start: date | None
    longest_end: date | None
    last_year: int
    days: dict[date, int]
    today: date


def original_repositories() -> list[dict]:
    return [repo for repo in paginated_owned_repositories() if not repo.get("fork")]


def language_shares(per_repository: dict[str, dict[str, int]], top: int = 7) -> Languages:
    """Average each repository's language fractions so every repository counts once."""
    totals: dict[str, float] = defaultdict(float)
    counted = 0
    for languages in per_repository.values():
        size = sum(value for value in languages.values() if isinstance(value, int) and value > 0)
        if not size:
            continue
        counted += 1
        for language, value in languages.items():
            if isinstance(value, int) and value > 0:
                totals[language] += value / size
    if not counted:
        raise ValueError("no repository reported any languages")
    ranked = sorted(((name, 100 * weight / counted) for name, weight in totals.items()), key=lambda item: (-item[1], item[0]))
    shares = ranked[:top]
    rest = sum(percent for _, percent in ranked[top:])
    if rest >= 0.05:
        shares.append(("Other", rest))
    return Languages(shares, counted)


def fetch_languages(repos: list[dict]) -> Languages:
    def languages(repo):
        try:
            payload = request_json(f"{API_ROOT}/repos/{USERNAME}/{repo['name']}/languages")
        except GitHubAPIError as exc:
            print(f"Warning: languages for {repo['name']} unavailable: {exc}", file=sys.stderr)
            return repo["name"], {}
        return repo["name"], payload if isinstance(payload, dict) else {}

    with ThreadPoolExecutor(max_workers=8) as pool:
        return language_shares(dict(pool.map(languages, repos)))


def commit_days(timestamps: list[str], tz: ZoneInfo) -> dict[date, int]:
    days: dict[date, int] = defaultdict(int)
    for stamp in timestamps:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        days[moment.astimezone(tz).date()] += 1
    return dict(days)


def compute_streak(days: dict[date, int], today: date) -> Streak:
    active = {day for day, count in days.items() if count > 0}
    # A streak stays alive through today until the day is over.
    cursor = today if today in active else today - timedelta(days=1)
    current = 0
    while cursor in active:
        current += 1
        cursor -= timedelta(days=1)
    current_start = cursor + timedelta(days=1) if current else None

    longest, longest_start, longest_end = 0, None, None
    run_start, previous, run = None, None, 0
    for day in sorted(active):
        if previous is not None and day - previous == timedelta(days=1):
            run += 1
        else:
            run, run_start = 1, day
        if run > longest or (run == longest and day > (longest_end or day)):
            longest, longest_start, longest_end = run, run_start, day
        previous = day
    last_year = sum(count for day, count in days.items() if today - timedelta(days=365) < day <= today)
    return Streak(current, current_start, longest, longest_start, longest_end, last_year, days, today)


def fetch_streak(repos: list[dict], now: datetime) -> Streak:
    def commits(repo):
        stamps: list[str] = []
        page = 1
        while True:
            query = urllib.parse.urlencode(
                {"author": USERNAME, "sha": repo.get("default_branch") or "main", "per_page": 100, "page": page}
            )
            try:
                payload = request_json(f"{API_ROOT}/repos/{USERNAME}/{repo['name']}/commits?{query}")
            except GitHubAPIError as exc:  # empty repositories answer 409; huge kernel trees can time out
                print(f"Warning: commits for {repo['name']} unavailable: {exc}", file=sys.stderr)
                return None
            if not isinstance(payload, list):
                return None
            for item in payload:
                author = (item.get("commit") or {}).get("author") or {}
                if isinstance(author.get("date"), str):
                    stamps.append(author["date"])
            if len(payload) < 100 or page >= 50:
                return stamps
            page += 1

    with_history = [repo for repo in repos if repo.get("size", 1) > 0]  # empty repositories answer 409
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(commits, with_history))
    if all(result is None for result in results):
        raise GitHubAPIError("no repository returned its commit history")
    stamps = [stamp for result in results if result for stamp in result]
    return compute_streak(commit_days(stamps, now.tzinfo), now.date())


# --------------------------------------------------------------------------- cards


def short_date(day: date | None) -> str:
    return day.strftime("%d %b %Y").lstrip("0") if day else "—"


def clock_card(location: str, now: datetime) -> Scene:
    scene = Scene(
        name="clock",
        width=1200,
        height=170,
        title=f"{location} — {now:%H:%M} {TIMEZONE_LABEL}",
        description=f"Location {location}, time zone {TIMEZONE}. Local time at the last refresh: {now:%A %d %B %Y, %H:%M}.",
        animated=False,
    )
    window(scene, "date && echo $TZ", title_h=38)
    cx, cy, r = 92, 104, 42
    hour_angle = (now.hour % 12 + now.minute / 60) * 30
    minute_angle = now.minute * 6
    ticks = "".join(
        f'<line x1="{cx}" y1="{cy - r + 5}" x2="{cx}" y2="{cy - r + (11 if i % 3 == 0 else 8)}" '
        f'stroke="{C["muted"] if i % 3 == 0 else C["ring"]}" stroke-width="{2 if i % 3 == 0 else 1.2}" '
        f'stroke-linecap="round" transform="rotate({i * 30} {cx} {cy})"/>'
        for i in range(12)
    )
    scene.add(
        Raw(
            name="analog clock",
            markup=(
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{C["panel"]}" stroke="{C["border"]}" stroke-width="1.5"/>{ticks}'
                f'<line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy - r * 0.5:.1f}" stroke="{C["text"]}" stroke-width="3.2" '
                f'stroke-linecap="round" transform="rotate({hour_angle:.2f} {cx} {cy})"/>'
                f'<line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy - r * 0.78:.1f}" stroke="{C["violet"]}" stroke-width="2" '
                f'stroke-linecap="round" transform="rotate({minute_angle:.2f} {cx} {cy})"/>'
                f'<circle cx="{cx}" cy="{cy}" r="3.2" fill="{C["violet"]}"/>'
            ),
        )
    )
    scene.add(Text(name="location label", runs=[Run("location", C["dim"], 12)], x=168, baseline=82))
    scene.add(Text(name="location", runs=[Run(location, C["text"], 26, "bold")], x=168, baseline=114))
    scene.add(Text(name="zone", runs=[Run(f"{TIMEZONE} · {TIMEZONE_LABEL}", C["muted"], 14)], x=168, baseline=140))

    time_text = f"{now:%H:%M}"
    right = scene.width - PAD_X
    date_text = now.strftime("%A, %d %B %Y").replace(" 0", " ")
    scene.add(Text(name="time label", runs=[Run("local time", C["dim"], 12)], x=right - text_width("local time", 12), baseline=82))
    scene.add(Text(name="time", runs=[Run(time_text, C["text"], 40, "bold"), Run(" WIB", C["violet"], 18)],
                   x=right - text_width(time_text, 40) - text_width(" WIB", 18), baseline=118))
    scene.add(Text(name="date", runs=[Run(date_text, C["muted"], 14)], x=right - text_width(date_text, 14), baseline=142))
    note = f"as of last refresh · {REFRESH_NOTE}"
    scene.add(Text(name="note", runs=[Run(note, C["dim"], 11)], x=(scene.width - text_width(note, 11)) / 2, baseline=160))
    return scene


def languages_card(data: Languages) -> Scene:
    scene = Scene(
        name="languages",
        width=1200,
        height=214,
        title="Languages across original repositories",
        description="Language mix with every original public repository weighted equally: "
        + ", ".join(f"{name} {percent:.1f}%" for name, percent in data.shares)
        + ".",
        animated=False,
    )
    window(scene, "languages — each repository weighted equally",
           status=([Run("● ", C["mint"], 12), Run(f"{data.repositories} repositories", C["muted"], 12)], REFRESH_NOTE))
    bar_x, bar_y, bar_w, bar_h = PAD_X, 70, scene.width - 2 * PAD_X, 12
    scene.add(Rect(name="rail", x=bar_x, y=bar_y, w=bar_w, h=bar_h, radius=6, fill=C["rail"]))
    colors = [OTHER_COLOR if name == "Other" else LANGUAGE_COLORS[index % len(LANGUAGE_COLORS)] for index, (name, _) in enumerate(data.shares)]
    total = sum(percent for _, percent in data.shares)
    x = bar_x
    segments = []
    for (name, percent), color in zip(data.shares, colors):
        width = bar_w * percent / total
        segments.append(f'<rect x="{x:.2f}" y="{bar_y}" width="{max(width - 2, 1):.2f}" height="{bar_h}" fill="{color}"/>')
        x += width
    scene.add(Raw(name="segments", markup=(
        f'<defs><clipPath id="bar"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="6"/></clipPath></defs>'
        f'<g clip-path="url(#bar)">{"".join(segments)}</g>'
    )))
    columns, column_w = 4, bar_w / 4
    for index, ((name, percent), color) in enumerate(zip(data.shares, colors)):
        col, row = index % columns, index // columns
        x = bar_x + col * column_w
        baseline = 120 + row * 30
        scene.add(Circle(name=f"dot {name}", cx=x + 6, cy=baseline - 5, r=5, fill=color))
        scene.add(Text(name=f"legend {name}", runs=[Run(name, C["text"], 15), Run(f"  {percent:.1f}%", C["muted"], 14)],
                       x=x + 20, baseline=baseline))
    return scene


def streak_card(data: Streak) -> Scene:
    scene = Scene(
        name="streak",
        width=1200,
        height=236,
        title="Commit streak",
        description=(
            f"Current commit streak {data.current} days, longest {data.longest} days, "
            f"{data.last_year} commits in the last year on default branches of original repositories."
        ),
        animated=False,
    )
    window(scene, "git log --author=FebriCahyaa — commit streak",
           status=([Run("● ", C["mint"], 12), Run("default branches", C["muted"], 12),
                    Run("   original repositories · days in WIB", C["dim"], 12)], REFRESH_NOTE))
    blocks = [
        ("current streak", f"{data.current}", "days" if data.current != 1 else "day",
         f"since {short_date(data.current_start)}" if data.current else "no commit yet today or yesterday", C["violet"]),
        ("longest streak", f"{data.longest}", "days" if data.longest != 1 else "day",
         f"{short_date(data.longest_start)} → {short_date(data.longest_end)}" if data.longest else "—", C["text"]),
        ("commits, last 365 days", f"{data.last_year}", "", "authored, default branches", C["text"]),
    ]
    for index, (label, value, unit, detail, color) in enumerate(blocks):
        x = PAD_X + index * 205
        scene.add(Text(name=f"{label} label", runs=[Run(label, C["dim"], 12)], x=x, baseline=82))
        runs = [Run(value, color, 38, "bold")] + ([Run(f" {unit}", C["muted"], 15)] if unit else [])
        scene.add(Text(name=f"{label} value", runs=runs, x=x, baseline=128))
        scene.add(Text(name=f"{label} detail", runs=[Run(detail, C["muted"], 11)], x=x, baseline=152))

    # Activity grid: the last 30 weeks, Monday-first columns, oldest on the left.
    weeks, cell, gap = 30, 12, 3
    grid_w = weeks * (cell + gap) - gap
    origin_x, origin_y = scene.width - PAD_X - grid_w, 66
    end = data.today + timedelta(days=6 - data.today.weekday())
    start = end - timedelta(days=weeks * 7 - 1)
    peak = max([count for day, count in data.days.items() if start <= day <= data.today] or [0])
    cells = []
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        if day > data.today:
            continue
        count = data.days.get(day, 0)
        level = 0 if not count else min(4, 1 + int(3 * math.log1p(count) / math.log1p(max(peak, 1))))
        col, row = offset // 7, offset % 7
        cells.append(
            f'<rect x="{origin_x + col * (cell + gap)}" y="{origin_y + row * (cell + gap)}" width="{cell}" height="{cell}" '
            f'rx="2.5" fill="{STREAK_LEVELS[level]}"/>'
        )
    scene.add(Raw(name="activity grid", markup="".join(cells)))
    legend_y = origin_y + 7 * (cell + gap) + 16
    scene.add(Text(name="grid caption", runs=[Run("last 30 weeks", C["dim"], 11)], x=origin_x, baseline=legend_y))
    legend = "".join(
        f'<rect x="{origin_x + grid_w - (5 - i) * (cell + gap) + gap}" y="{legend_y - 10}" width="{cell}" height="{cell}" rx="2.5" fill="{color}"/>'
        for i, color in enumerate(STREAK_LEVELS)
    )
    scene.add(Raw(name="grid legend", markup=legend))
    return scene


# --------------------------------------------------------------------------- cli


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=Path("dist"), help="Directory to write the cards into.")
    args = parser.parse_args()

    from assetkit import GlyphOutlines

    outlines = GlyphOutlines()
    now = datetime.now(ZoneInfo(TIMEZONE))
    args.out.mkdir(parents=True, exist_ok=True)

    location = "Indonesia"
    repos: list[dict] | None = None
    try:
        user = request_json(f"{API_ROOT}/users/{USERNAME}")
        if isinstance(user, dict) and isinstance(user.get("location"), str) and user["location"].strip():
            location = user["location"].strip()
        repos = original_repositories()
    except GitHubAPIError as exc:
        print(f"Warning: profile data unavailable: {exc}", file=sys.stderr)

    builders = {
        "clock.svg": lambda: clock_card(location, now),
        "languages.svg": lambda: languages_card(fetch_languages(repos or [])),
        "streak.svg": lambda: streak_card(fetch_streak(repos or [], now)),
    }
    missing = []
    for filename, build in builders.items():
        target = args.out / filename
        try:
            if filename != "clock.svg" and not repos:
                raise GitHubAPIError("repository list unavailable")
            target.write_text(build_svg(build(), outlines), encoding="utf-8")
            print(f"wrote {target}")
        except (GitHubAPIError, ValueError) as exc:
            if target.exists():
                print(f"Warning: kept previous {filename}: {exc}", file=sys.stderr)
            else:
                print(f"ERROR: {filename} could not be built and no previous copy exists: {exc}", file=sys.stderr)
                missing.append(filename)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
