#!/usr/bin/env python3
"""Build the profile's generated assets from scene descriptions.

Animated scenes produce, per scene ``<name>``:

* ``assets/lottie/<name>.json``             Lottie source
* ``assets/animations/<name>.gif``          rendered from the Lottie file (light page background)
* ``assets/animations/<name>-dark.gif``     rendered from the Lottie file (dark page background)
* ``assets/static/<name>.svg``              static poster frame (reduced-motion fallback)

Static scenes (the social buttons) produce ``assets/social/<name>.svg`` only.

    python3 -m pip install -r scripts/requirements-assets.txt
    python3 scripts/build_assets.py              # everything
    python3 scripts/build_assets.py --no-gif     # Lottie + SVG only (fontTools)
    python3 scripts/build_assets.py --check      # fail if Lottie/SVG output is stale
    python3 scripts/build_assets.py --only kernel-ci
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from assetkit import (  # noqa: E402
    ASSETS,
    MATTES,
    ROOT,
    Circle,
    Icon,
    Rect,
    RoundRect,
    Run,
    Scene,
    Text,
    Track,
    blink_steps,
    build_lottie,
    build_svg,
    icon_path,
    render_gif,
    serialize_lottie,
    text_width,
)

C = {
    "window": "#0E1013",
    "chrome": "#15171C",
    "status": "#121418",
    "panel": "#13161B",
    "border": "#272A31",
    "divider": "#22252B",
    "rail": "#1E2127",
    "ring": "#3A3E46",
    "text": "#ECE9E2",
    "muted": "#8A8F98",
    "dim": "#5F646D",
    "soft": "#A4A8B0",
    "violet": "#B3A4FF",
    "violet_deep": "#8F7CF0",
    "violet_wash": "#221D38",
    "mint": "#7DD3AE",
    "coral": "#F08A7E",
    "close": "#FF5F57",
    "minimize": "#FEBC2E",
    "zoom": "#28C840",
}
RADIUS = 14
PAD_X = 36


def window(scene: Scene, title: str, title_h: int = 46, status: tuple[list[Run], str] | None = None, status_h: int = 34) -> None:
    """macOS-style terminal window chrome filling the whole scene."""
    w, h = scene.width, scene.height
    scene.add(RoundRect(name="window", x=0, y=0, w=w, h=h, top=RADIUS, bottom=RADIUS, fill=C["window"]))
    scene.add(RoundRect(name="title bar", x=0, y=0, w=w, h=title_h, top=RADIUS, bottom=0, fill=C["chrome"]))
    scene.add(Rect(name="title divider", x=1, y=title_h, w=w - 2, h=1, fill=C["divider"]))
    if status:
        top = h - status_h
        scene.add(RoundRect(name="status bar", x=0, y=top, w=w, h=status_h, top=0, bottom=RADIUS, fill=C["status"]))
        scene.add(Rect(name="status divider", x=1, y=top, w=w - 2, h=1, fill=C["divider"]))
    scene.add(
        RoundRect(name="border", x=0.5, y=0.5, w=w - 1, h=h - 1, top=RADIUS - 0.5, bottom=RADIUS - 0.5, stroke=C["border"])
    )
    for cx, key in ((22, "close"), (42, "minimize"), (62, "zoom")):
        scene.add(Circle(name=f"window control {key}", cx=cx, cy=title_h / 2, r=6, fill=C[key]))
    size = 13
    scene.add(Text(name="title", runs=[Run(title, C["muted"], size)], x=(w - text_width(title, size)) / 2, baseline=title_h / 2 + 5))
    if status:
        left, right = status
        baseline = h - 12
        scene.add(Text(name="status left", runs=left, x=PAD_X - 14, baseline=baseline))
        scene.add(Text(name="status right", runs=[Run(right, C["dim"], 12)], x=w - PAD_X + 14 - text_width(right, 12), baseline=baseline))


def presence(intervals: list[tuple[int, int]], total: int, fade: int = 5) -> Track:
    """Opacity that fades in at each interval start and out at its end."""
    points: list[tuple[int, int]] = []
    for start, end in intervals:
        points += [(0, 100)] if start == 0 else [(start, 0), (start + fade, 100)]
        points += [(total - 1, 100)] if end >= total else [(end, 100), (end + fade, 0)]
    if points[0][0] != 0:
        points.insert(0, (0, 0))
    return Track.ramp(sorted(points))


def shown(start: int, end: int | None = None) -> Track:
    """Opacity hold steps: visible from `start` until `end` (exclusive)."""
    points = [(0, 0), (start, 100)] if start > 0 else [(0, 100)]
    if end is not None:
        points.append((end, 0))
    return Track.steps(points)


def prompt(size: float = 17) -> list[Run]:
    return [Run("~ ", C["muted"], size), Run("❯ ", C["violet"], size)]


class Typist:
    """Records a terminal cursor frame by frame and the reveal frame of typed characters."""

    KEY_RHYTHM = (3, 2, 3, 4, 2, 3, 2, 3)

    def __init__(self, size: float = 17, height: float = 22, rise: float = 16):
        self.frame = 0
        self.size = size
        self.cell = size * 0.6
        self.height, self.rise = height, rise
        self.states: list[tuple[float, float, bool]] = []

    def hold(self, frames: int, x: float = 0, baseline: float = 0, visible: bool = False) -> None:
        self.states.extend([(x, baseline, visible)] * frames)
        self.frame += frames

    def blink(self, frames: int, x: float, baseline: float, first_on: int = 13) -> None:
        on, remaining, phase = True, frames, first_on
        while remaining > 0:
            step = min(phase, remaining)
            self.hold(step, x, baseline, on)
            remaining -= step
            on = not on
            phase = 13 if on else 12

    def type(self, text: str, x: float, baseline: float) -> list[int]:
        reveals = []
        for index, _ in enumerate(text):
            reveals.append(self.frame)
            x += self.cell
            self.hold(self.KEY_RHYTHM[index % len(self.KEY_RHYTHM)], x, baseline, True)
        return reveals

    def cursor(self, color: str) -> Rect:
        positions, visibility = [], []
        for frame, (x, baseline, on) in enumerate(self.states):
            if on:
                position = (round(x, 2), round(baseline - self.rise, 2))
                if not positions or positions[-1][1] != position:
                    positions.append((frame, position))
            value = 100 if on else 0
            if not visibility or visibility[-1][1] != value:
                visibility.append((frame, value))
        return Rect(
            name="cursor", x=0, y=0, w=round(self.cell, 2), h=self.height, fill=color,
            offset=Track.steps(positions), opacity=Track.steps(visibility),
        )


# --------------------------------------------------------------------------- hero


def terminal_intro() -> Scene:
    scene = Scene(
        name="terminal-intro",
        width=1200,
        height=420,
        title="Febri Cahya — Android, Linux and systems engineering",
        description=(
            "A dark macOS-style terminal window. An illustrative session runs whoami, which prints Febri Cahya, "
            "Android · Linux · Systems Engineering, and the line 'Building reliable tools for the layers beneath "
            "the interface.' It then lists ~/projects: flux, synthesiscore, hico and ci-build."
        ),
    )
    window(
        scene,
        "febri@workbench: ~ — zsh",
        status=([Run("● ", C["mint"], 12), Run("main", C["muted"], 12), Run("   ~/workbench", C["dim"], 12)], "android · linux · kernel · ci"),
    )
    base = {"prompt1": 92, "name": 160, "role": 198, "statement": 232, "prompt2": 282, "listing": 314, "prompt3": 356}
    home = PAD_X + text_width("~ ❯ ", 17)
    t = Typist()
    first_on = 7  # the rest of this blink phase plays after `clear`, closing the loop

    lines: list[Text] = []
    scene.add(Text(name="prompt 1", runs=prompt(), x=PAD_X, baseline=base["prompt1"]))
    t.blink(30, home, base["prompt1"], first_on=first_on)
    whoami = Text(name="command whoami", runs=[Run("whoami", C["text"])], x=home, baseline=base["prompt1"])
    whoami.typed = t.type("whoami", home, base["prompt1"])
    t.hold(8, home + t.cell * 6, base["prompt1"], True)
    t.hold(2)
    outputs = [
        ("output name", base["name"], [Run("Febri Cahya", C["text"], 52, "bold")]),
        ("output role", base["role"], [Run("Android · Linux · Systems Engineering", C["violet"], 22)]),
        ("output statement", base["statement"], [Run("Building reliable tools for the layers beneath the interface.", C["soft"], 17)]),
    ]
    appear = {}
    for name, baseline, runs in outputs:
        appear[name] = t.frame
        lines.append(Text(name=name, runs=runs, x=PAD_X, baseline=baseline))
        t.hold(2)
    appear["prompt 2"] = t.frame
    t.blink(22, home, base["prompt2"])
    listing_cmd = Text(name="command ls", runs=[Run("ls ~/projects", C["text"])], x=home, baseline=base["prompt2"])
    listing_cmd.typed = t.type("ls ~/projects", home, base["prompt2"])
    t.hold(7, home + t.cell * 13, base["prompt2"], True)
    t.hold(2)
    appear["output listing"] = t.frame
    t.hold(2)
    appear["prompt 3"] = t.frame
    scene.poster = t.frame
    t.blink(13 * 4 + 12 * 4, home, base["prompt3"])
    clear_cmd = Text(name="command clear", runs=[Run("clear", C["text"])], x=home, baseline=base["prompt3"])
    clear_cmd.typed = t.type("clear", home, base["prompt3"])
    t.hold(6, home + t.cell * 5, base["prompt3"], True)
    clear = t.frame
    t.hold(13 - first_on, home, base["prompt1"], True)
    scene.frames = t.frame

    for line in lines:
        line.opacity = shown(appear[line.name], clear)
    for command in (whoami, listing_cmd, clear_cmd):
        command.opacity = shown(0, clear)
    prompt2 = Text(name="prompt 2", runs=prompt(), x=PAD_X, baseline=base["prompt2"], opacity=shown(appear["prompt 2"], clear))
    listing = Text(
        name="output listing",
        runs=[Run("flux/    synthesiscore/    hico/    ci-build/", C["mint"])],
        x=PAD_X,
        baseline=base["listing"],
        opacity=shown(appear["output listing"], clear),
    )
    prompt3 = Text(name="prompt 3", runs=prompt(), x=PAD_X, baseline=base["prompt3"], opacity=shown(appear["prompt 3"], clear))
    scene.add(whoami, *lines, prompt2, listing_cmd, listing, prompt3, clear_cmd)
    scene.add(t.cursor(C["violet_deep"]))
    return scene


# --------------------------------------------------------------------------- flux loop


def flux_loop() -> Scene:
    total = 300  # 12 s at 25 fps
    scene = Scene(
        name="flux-loop",
        width=1200,
        height=400,
        frames=total,
        poster=120,
        title="Flux profile loop — simulated",
        description=(
            "A simulated view of Flux: device state flows from the binder monitor (with SynthesisCore as fallback) "
            "into fluxd, which applies a profile through flux_profiler while HiCo Thermal follows it. The active "
            "profile moves from Balance to Performance when a game is in the foreground, to Performance Lite when "
            "thermal headroom runs low, and back to Balance when the game exits."
        ),
    )
    window(
        scene,
        "fluxd — profile loop (simulated)",
        status=([Run("● ", C["mint"], 12), Run("fluxd", C["muted"], 12), Run("   illustrative values", C["dim"], 12)], "not a live device"),
    )

    # Pipeline nodes.
    node_y, node_h, node_w = 74, 78, 330
    nodes = [
        (PAD_X, "device state", "binder monitor · SynthesisCore"),
        ((scene.width - node_w) / 2, "fluxd", "game list · thermal · config"),
        (scene.width - PAD_X - node_w, "profile applied", "flux_profiler · HiCo Thermal"),
    ]
    events = {75: "Performance", 160: "Performance Lite", 225: "Balance"}
    for index, (x, title, sub) in enumerate(nodes):
        scene.add(Rect(name=f"node {title}", x=x, y=node_y, w=node_w, h=node_h, radius=10, fill=C["panel"], stroke=C["border"]))
        if index == 1:
            pulse = [(0, 0)]
            for frame in events:
                pulse += [(frame - 1, 0), (frame + 3, 100), (frame + 28, 0)]
            scene.add(
                Rect(name="fluxd pulse", x=x, y=node_y, w=node_w, h=node_h, radius=10, stroke=C["violet_deep"], stroke_width=1.5,
                     opacity=Track.ramp(pulse))
            )
        scene.add(Text(name=f"{title} title", runs=[Run(title, C["text"], 17, "bold")], x=x + 20, baseline=node_y + 33))
        scene.add(Text(name=f"{title} detail", runs=[Run(sub, C["muted"], 13)], x=x + 20, baseline=node_y + 58))

    # Connectors with packets travelling left to right, one per second.
    cy = node_y + node_h / 2
    period = 25
    for index in range(2):
        start = nodes[index][0] + node_w
        end = nodes[index + 1][0]
        scene.add(Rect(name=f"connector {index}", x=start, y=cy - 0.5, w=end - start, h=1, fill=C["ring"]))
        scene.add(Circle(name=f"port {index}", cx=end - 3, cy=cy, r=3, fill=C["ring"]))
        span = end - start - 16
        phase = index * 12
        offsets, opacities = [], []
        for frame in range(0, total, 2):  # 12.5 fps motion keeps the GIF small
            step = (frame - phase) % period
            offsets.append((frame, (round(span * step / (period - 1), 2), 0)))
            opacities.append((frame, 0 if step < 2 or step > period - 4 else 100))
        scene.add(Circle(name=f"packet {index}", cx=start + 8, cy=cy, r=4, fill=C["violet"],
                         offset=Track.steps(offsets), opacity=Track.steps(opacities)))

    # Rows: label column + content column.
    label_x, content_x = PAD_X, 220
    profile_y = 186
    scene.add(Text(name="label profile", runs=[Run("profile", C["muted"], 13)], x=label_x, baseline=profile_y + 22))
    active = {
        "Balance": [(0, 75), (225, total)],
        "Performance": [(75, 160)],
        "Performance Lite": [(160, 225)],
        "Powersave": [],
    }
    x = content_x
    for name, intervals in active.items():
        width = text_width(name, 15) + 32
        scene.add(Rect(name=f"chip {name}", x=x, y=profile_y, w=width, h=34, radius=17, stroke=C["ring"]))
        if intervals:
            scene.add(
                Rect(name=f"chip {name} active", x=x, y=profile_y, w=width, h=34, radius=17, fill=C["violet_wash"],
                     stroke=C["violet_deep"], opacity=presence(intervals, total))
            )
        scene.add(Text(name=f"chip {name} label", runs=[Run(name, C["text"], 15)], x=x + 16, baseline=profile_y + 22))
        x += width + 12

    event_y = 268
    scene.add(Text(name="label event", runs=[Run("event", C["muted"], 13)], x=label_x, baseline=event_y))
    log = [
        ("idle · no game in foreground", "Balance", [(0, 75), (285, total)]),
        ("game in foreground", "Performance", [(75, 160)]),
        ("thermal headroom low", "Performance Lite", [(160, 225)]),
        ("game exited · stock values restored", "Balance", [(225, 285)]),
    ]
    for message, profile, intervals in log:
        scene.add(
            Text(name=f"event {message}", runs=[Run(message, C["text"], 16), Run("  →  ", C["dim"], 16), Run(profile, C["violet"], 16)],
                 x=content_x, baseline=event_y, opacity=presence(intervals, total, fade=6))
        )

    bar_y, bar_w = 312, 520
    scene.add(Text(name="label headroom", runs=[Run("thermal headroom", C["muted"], 13)], x=label_x, baseline=bar_y + 9))
    scene.add(Rect(name="headroom rail", x=content_x, y=bar_y, w=bar_w, h=8, radius=4, fill=C["rail"]))
    level = [(0, 0.86), (75, 0.86), (160, 0.34), (190, 0.30), (225, 0.44), (285, 0.86), (total - 1, 0.86)]
    curve = Track.ramp([(f, v * bar_w) for f, v in level])
    # Sampled like a polled metric (every 12 frames) instead of a continuous sweep, on odd
    # frames so bar updates never coincide with packet steps (smaller GIF frame deltas).
    width = Track.steps([(0, round(curve.at(0)[0], 2))] + [(f, round(curve.at(f)[0], 2)) for f in range(1, total, 12)])
    scene.add(Rect(name="headroom", x=content_x, y=bar_y, w=bar_w, h=8, radius=4, fill=C["violet_deep"], width=width))
    scene.add(Rect(name="headroom low", x=content_x, y=bar_y, w=bar_w, h=8, radius=4, fill=C["coral"], width=width,
                   opacity=presence([(160, 225)], total, fade=8)))
    scene.add(Text(name="headroom scale", runs=[Run("1.0 = cool", C["dim"], 12)], x=content_x + bar_w + 18, baseline=bar_y + 9))
    return scene


# --------------------------------------------------------------------------- kernel ci


def kernel_ci() -> Scene:
    scene = Scene(
        name="kernel-ci",
        width=1200,
        height=340,
        title="ci-build kernel pipeline — illustrative run",
        description=(
            "An illustrative ci-build run. Three targets — garnet-gki (5.10 GKI), lavender-4.4 and lavender-4.19 — "
            "move through the stages resolve, patch, toolchain, compile, AnyKernel3 and release, each turning green "
            "when complete, ending with a kernel image and an AnyKernel3 zip per variant."
        ),
    )
    window(
        scene,
        "ci-build — Build Kernel (illustrative run)",
        status=([Run("● ", C["mint"], 12), Run("kernel.yml", C["muted"], 12), Run("   one script layer", C["dim"], 12)],
                "github actions · harness · local"),
    )
    stages = ["resolve", "patch", "toolchain", "compile", "anykernel3", "release"]
    columns = [360 + 150 * index for index in range(len(stages))]
    for name, cx in zip(stages, columns):
        scene.add(Text(name=f"stage {name}", runs=[Run(name, C["muted"], 13)], x=cx - text_width(name, 13) / 2, baseline=88))

    targets = [
        ("garnet-gki", "5.10 GKI", [8, 12, 10, 46, 10, 8]),
        ("lavender-4.4", "4.4", [8, 10, 10, 36, 10, 8]),
        ("lavender-4.19", "4.19", [8, 14, 10, 40, 10, 8]),
    ]
    rows = []
    finish_all = 0
    for row, (name, version, durations) in enumerate(targets):
        baseline = 140 + 50 * row
        cy = baseline - 5
        start = 14 + row * 10
        timeline = []
        frame = start
        for duration in durations:
            timeline.append((frame, frame + duration))
            frame += duration
        finish_all = max(finish_all, frame)
        rows.append((name, version, baseline, cy, timeline))

    reset = finish_all + 80
    total = reset + 24
    scene.frames = total
    scene.poster = finish_all + 10

    for name, version, baseline, cy, timeline in rows:
        scene.add(Text(name=f"target {name}", runs=[Run(name, C["text"], 16), Run(f"  {version}", C["dim"], 13)], x=PAD_X, baseline=baseline))
        for index, cx in enumerate(columns):
            if index:
                left, right = columns[index - 1] + 10, cx - 10
                scene.add(Rect(name=f"{name} link {index}", x=left, y=cy - 0.5, w=right - left, h=1, fill=C["border"]))
                done_at = timeline[index - 1][1]
                scene.add(Rect(name=f"{name} link {index} done", x=left, y=cy - 0.5, w=right - left, h=1, fill=C["mint"],
                               opacity=presence([(done_at, reset)], total, fade=4)))
            begin, end = timeline[index]
            scene.add(Circle(name=f"{name} {stages[index]}", cx=cx, cy=cy, r=7, stroke=C["ring"], stroke_width=1.5))
            # Running stages blink on a clock shared by all rows, so they change on the same frames.
            pulse = [(0, 0)] + [(f, 100 if (f // 6) % 2 == 0 else 35) for f in range(begin, end) if f == begin or f % 6 == 0] + [(end, 0)]
            scene.add(Circle(name=f"{name} {stages[index]} running", cx=cx, cy=cy, r=7, fill=C["violet_deep"], opacity=Track.steps(pulse)))
            scene.add(Circle(name=f"{name} {stages[index]} done", cx=cx, cy=cy, r=7, fill=C["mint"],
                             opacity=presence([(end, reset)], total, fade=3)))

    summary = [
        Run("✓ ", C["mint"], 15),
        Run("3 targets built", C["text"], 15),
        Run("  ·  kernel image + AnyKernel3 zip per variant", C["muted"], 15),
    ]
    scene.add(Text(name="summary", runs=summary, x=PAD_X, baseline=280, opacity=presence([(finish_all + 6, reset)], total, fade=6)))
    return scene


# --------------------------------------------------------------------------- footer


def terminal_exit() -> Scene:
    scene = Scene(
        name="terminal-exit",
        width=900,
        height=196,
        title="Terminal closing: exit",
        description="A terminal window types exit and prints logout, Saving session...completed., and [Process completed].",
    )
    window(scene, "febri@workbench: ~ — zsh", title_h=38)
    home = PAD_X + text_width("~ ❯ ", 17)
    baselines = [78, 106, 134, 170]
    t = Typist()
    first_on = 7
    scene.add(Text(name="prompt", runs=prompt(), x=PAD_X, baseline=baselines[0]))
    t.blink(25, home, baselines[0], first_on=first_on)
    command = Text(name="command exit", runs=[Run("exit", C["text"])], x=home, baseline=baselines[0])
    command.typed = t.type("exit", home, baselines[0])
    t.hold(8, home + t.cell * 4, baselines[0], True)
    t.hold(2)
    outputs = [
        ("logout", [Run("logout", C["soft"])]),
        ("saving", [Run("Saving session...", C["soft"]), Run("completed.", C["mint"])]),
        ("process", [Run("[Process completed]", C["dim"])]),
    ]
    appear = []
    for _ in outputs:
        appear.append(t.frame)
        t.hold(4)
    scene.poster = t.frame
    t.hold(80)
    fade_start = t.frame
    t.hold(10)
    t.hold(13 - first_on, home, baselines[0], True)
    scene.frames = t.frame

    def fading(start: int) -> Track:
        return Track.ramp([(0, 0), (start, 0), (start + 1, 100), (fade_start, 100), (fade_start + 10, 0)]) if start else Track.ramp(
            [(0, 100), (fade_start, 100), (fade_start + 10, 0)]
        )

    command.opacity = fading(0)
    scene.add(command)
    for (name, runs), start, baseline in zip(outputs, appear, baselines[1:]):
        scene.add(Text(name=f"output {name}", runs=runs, x=PAD_X, baseline=baseline, opacity=fading(start)))
    scene.add(t.cursor(C["violet_deep"]))
    return scene


# --------------------------------------------------------------------------- social


SOCIAL = [
    ("github", "GitHub", "@FebriCahyaa", C["text"]),
    ("telegram", "Telegram", "@FebriCahyaaaaa", "#26A5E4"),
    ("instagram", "Instagram", "@fbri.chy", "#FF0069"),
]


def social_button(icon: str, label: str, handle: str, color: str) -> Scene:
    scene = Scene(
        name=icon,
        width=232,
        height=60,
        title=f"{label} {handle}",
        description=f"{label} icon with the handle {handle}.",
        animated=False,
    )
    scene.add(Rect(name="pill", x=0.5, y=0.5, w=231, h=59, radius=12, fill=C["window"], stroke=C["border"]))
    scene.add(Icon(name="icon", d=icon_path(icon), x=18, y=18, size=24, fill=color))
    scene.add(Text(name="label", runs=[Run(label, C["text"], 15, "bold")], x=58, baseline=28))
    scene.add(Text(name="handle", runs=[Run(handle, C["muted"], 12)], x=58, baseline=46))
    return scene


# --------------------------------------------------------------------------- cli


def animated_scenes() -> list[Scene]:
    return [terminal_intro(), flux_loop(), kernel_ci(), terminal_exit()]


def static_scenes() -> list[Scene]:
    return [social_button(*entry) for entry in SOCIAL]


def lottie_path(scene: Scene) -> Path:
    return ASSETS / "lottie" / f"{scene.name}.json"


def svg_path(scene: Scene) -> Path:
    return ASSETS / ("static" if scene.animated else "social") / f"{scene.name}.svg"


def gif_paths(scene: Scene) -> dict[Path, str]:
    return {ASSETS / "animations" / f"{scene.name}{suffix}.gif": matte for suffix, matte in MATTES.items()}


def text_outputs(scenes: list[Scene], outlines) -> dict[Path, str]:
    outputs = {}
    for scene in scenes:
        if scene.animated:
            outputs[lottie_path(scene)] = serialize_lottie(build_lottie(scene, outlines))
        outputs[svg_path(scene)] = build_svg(scene, outlines)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="Fail if committed Lottie/SVG files differ from a fresh build.")
    parser.add_argument("--no-gif", action="store_true", help="Skip GIF rendering (no rlottie/Pillow needed).")
    parser.add_argument("--only", metavar="NAME", help="Build a single scene.")
    args = parser.parse_args()

    try:
        from assetkit import GlyphOutlines

        outlines = GlyphOutlines()
    except ModuleNotFoundError as exc:
        print(f"ERROR: {exc.name} is required; install scripts/requirements-assets.txt", file=sys.stderr)
        return 2

    scenes = animated_scenes() + static_scenes()
    if args.only:
        scenes = [scene for scene in scenes if scene.name == args.only]
        if not scenes:
            print(f"ERROR: unknown scene {args.only!r}", file=sys.stderr)
            return 2
    outputs = text_outputs(scenes, outlines)

    if args.check:
        stale = [path for path, text in outputs.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
        for path in stale:
            print(f"Stale generated asset: {path.relative_to(ROOT)}", file=sys.stderr)
        if stale:
            print("Run: python3 scripts/build_assets.py", file=sys.stderr)
            return 1
        print(f"{len(outputs)} generated Lottie/SVG assets are up to date.")
        return 0

    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")

    if not args.no_gif:
        for scene in scenes:
            if not scene.animated:
                continue
            for gif, matte in gif_paths(scene).items():
                try:
                    stats = render_gif(lottie_path(scene), gif, matte, f"Rendered from assets/lottie/{scene.name}.json by scripts/build_assets.py")
                except ModuleNotFoundError as exc:
                    print(f"ERROR: {exc.name} is required for GIF rendering; install scripts/requirements-assets.txt", file=sys.stderr)
                    return 2
                print(f"wrote {gif.relative_to(ROOT)} ({stats['bytes']:,} bytes, {stats['frames']} frames, {stats['duration_ms'] / 1000:.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
