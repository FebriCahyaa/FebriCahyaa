#!/usr/bin/env python3
"""Build the terminal hero assets from one scene description.

Outputs (all committed to the repository):

* ``assets/lottie/terminal-intro.json``  Lottie source of the animation
* ``assets/profile-hero.svg``            static frame, used as the reduced-motion fallback
* ``assets/animations/terminal-intro.gif`` and ``terminal-intro-dark.gif``
                                          GIFs rendered *from the Lottie file* with rlottie

Text is converted to vector outlines from the vendored JetBrains Mono NL
subset in ``assets/fonts/``, so the Lottie file and the SVG do not depend on
fonts installed on the viewer's machine.

Dependencies (asset tooling only; the profile updater stays stdlib-only):
``python3 -m pip install -r scripts/requirements-assets.txt``

    python3 scripts/build_terminal_assets.py            # Lottie + SVG + GIFs
    python3 scripts/build_terminal_assets.py --no-gif   # Lottie + SVG only (needs fontTools)
    python3 scripts/build_terminal_assets.py --check    # fail if Lottie/SVG are stale
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "assets" / "fonts"
FONTS = {
    "regular": FONT_DIR / "JetBrainsMonoNL-Regular.subset.ttf",
    "bold": FONT_DIR / "JetBrainsMonoNL-Bold.subset.ttf",
}
LOTTIE_PATH = ROOT / "assets" / "lottie" / "terminal-intro.json"
SVG_PATH = ROOT / "assets" / "profile-hero.svg"
GIF_PATHS = {
    # GitHub page backgrounds; the window's rounded corners are blended onto these.
    ROOT / "assets" / "animations" / "terminal-intro.gif": "#FFFFFF",
    ROOT / "assets" / "animations" / "terminal-intro-dark.gif": "#0D1117",
}

WIDTH, HEIGHT = 1200, 420
FPS = 25
RADIUS = 14
TITLE_H = 46
STATUS_H = 34
PAD_X = 36

TITLE = "Febri Cahya — Android, Linux and systems engineering"
DESCRIPTION = (
    "A dark macOS-style terminal window. An illustrative session runs whoami, which prints "
    "Febri Cahya, Android · Linux · Systems Engineering, and the line 'Building reliable tools "
    "for the layers beneath the interface.' It then lists ~/projects: flux, synthesiscore, hico "
    "and ci-build."
)

PALETTE = {
    "window": "#0E1013",
    "chrome": "#15171C",
    "status": "#121418",
    "border": "#272A31",
    "divider": "#22252B",
    "text": "#ECE9E2",
    "muted": "#8A8F98",
    "dim": "#5F646D",
    "soft": "#A4A8B0",
    "violet": "#B3A4FF",
    "violet_deep": "#8F7CF0",
    "mint": "#7DD3AE",
    "close": "#FF5F57",
    "minimize": "#FEBC2E",
    "zoom": "#28C840",
}


# --------------------------------------------------------------------------- scene


@dataclass(frozen=True)
class Run:
    text: str
    color: str
    size: float = 17
    weight: str = "regular"


@dataclass
class TextLine:
    name: str
    x: float
    baseline: float
    runs: list[Run]
    appear: int = 0  # frame where the whole line becomes visible
    clear: int | None = None  # frame where the line is removed (None = never)
    typed: list[int] | None = None  # per-character reveal frames (overrides ``appear``)

    @property
    def text(self) -> str:
        return "".join(run.text for run in self.runs)


@dataclass
class Scene:
    lines: list[TextLine] = field(default_factory=list)
    cursor: list[tuple[float, float, bool]] = field(default_factory=list)  # per frame
    total_frames: int = 0
    poster_frame: int = 0


PROMPT_SIZE = 17
ADVANCE = 0.6  # JetBrains Mono advance width in em
CURSOR_W = PROMPT_SIZE * ADVANCE
CURSOR_H = 22
BLINK_ON, BLINK_OFF = 13, 12
# Deterministic, slightly uneven keystroke rhythm (frames per character).
KEY_RHYTHM = (3, 2, 3, 4, 2, 3, 2, 3)

BASELINES = {
    "prompt1": 92,
    "name": 160,
    "role": 198,
    "statement": 232,
    "prompt2": 282,
    "listing": 314,
    "prompt3": 356,
}


def prompt_runs() -> list[Run]:
    return [Run("~ ", PALETTE["muted"], PROMPT_SIZE), Run("❯ ", PALETTE["violet"], PROMPT_SIZE)]


PROMPT_WIDTH = len("~ ❯ ") * PROMPT_SIZE * ADVANCE


def build_scene() -> Scene:
    scene = Scene()
    cursor = scene.cursor
    frame = 0

    def hold(frames: int, x: float, baseline: float, visible: bool) -> None:
        nonlocal frame
        cursor.extend([(x, baseline, visible)] * frames)
        frame += frames

    def blink(frames: int, x: float, baseline: float, first_on: int = BLINK_ON) -> None:
        on, remaining, phase = True, frames, first_on
        while remaining > 0:
            step = min(phase, remaining)
            hold(step, x, baseline, on)
            remaining -= step
            on = not on
            phase = BLINK_ON if on else BLINK_OFF

    def type_command(baseline: float, text: str) -> list[int]:
        reveals: list[int] = []
        x = PAD_X + PROMPT_WIDTH
        for index, _ in enumerate(text):
            reveals.append(frame)
            x += CURSOR_W
            hold(KEY_RHYTHM[index % len(KEY_RHYTHM)], x, baseline, True)
        return reveals

    def prompt_line(name: str, key: str, appear: int) -> TextLine:
        line = TextLine(name, PAD_X, BASELINES[key], prompt_runs(), appear=appear)
        scene.lines.append(line)
        return line

    def command_line(name: str, key: str, text: str) -> TextLine:
        line = TextLine(name, PAD_X + PROMPT_WIDTH, BASELINES[key], [Run(text, PALETTE["text"], PROMPT_SIZE)])
        line.typed = type_command(BASELINES[key], text)
        scene.lines.append(line)
        return line

    home = PAD_X + PROMPT_WIDTH
    # The loop starts on an idle prompt; the first on-phase is short because the
    # final frames after `clear` supply the rest of it (seamless loop).
    first_on = 7
    prompt_line("prompt 1", "prompt1", 0)
    blink(30, home, BASELINES["prompt1"], first_on=first_on)
    whoami = command_line("command whoami", "prompt1", "whoami")
    hold(8, home + CURSOR_W * 6, BASELINES["prompt1"], True)

    hold(2, 0, 0, False)
    outputs = [
        TextLine("output name", PAD_X, BASELINES["name"], [Run("Febri Cahya", PALETTE["text"], 52, "bold")]),
        TextLine(
            "output role",
            PAD_X,
            BASELINES["role"],
            [Run("Android · Linux · Systems Engineering", PALETTE["violet"], 22)],
        ),
        TextLine(
            "output statement",
            PAD_X,
            BASELINES["statement"],
            [Run("Building reliable tools for the layers beneath the interface.", PALETTE["soft"], 17)],
        ),
    ]
    for line in outputs:
        line.appear = frame
        scene.lines.append(line)
        hold(2, 0, 0, False)

    prompt2 = prompt_line("prompt 2", "prompt2", frame)
    blink(22, home, BASELINES["prompt2"])
    listing_cmd = command_line("command ls", "prompt2", "ls ~/projects")
    hold(7, home + CURSOR_W * len("ls ~/projects"), BASELINES["prompt2"], True)
    hold(2, 0, 0, False)
    listing = TextLine(
        "output listing",
        PAD_X,
        BASELINES["listing"],
        [Run("flux/    synthesiscore/    hico/    ci-build/", PALETTE["mint"], 17)],
        appear=frame,
    )
    scene.lines.append(listing)
    hold(2, 0, 0, False)

    prompt3 = prompt_line("prompt 3", "prompt3", frame)
    scene.poster_frame = frame
    blink(BLINK_ON * 4 + BLINK_OFF * 4, home, BASELINES["prompt3"])
    clear_cmd = command_line("command clear", "prompt3", "clear")
    hold(6, home + CURSOR_W * 5, BASELINES["prompt3"], True)

    clear_frame = frame
    for line in [whoami, *outputs, prompt2, listing_cmd, listing, prompt3, clear_cmd]:
        line.clear = clear_frame
    hold(BLINK_ON - first_on, home, BASELINES["prompt1"], True)

    scene.total_frames = frame
    assert len(cursor) == frame
    return scene


# --------------------------------------------------------------------------- glyphs


class GlyphOutlines:
    """Glyph contours in font units, as (start, [segments]) with cubic curves."""

    def __init__(self) -> None:
        from fontTools.pens.basePen import BasePen
        from fontTools.ttLib import TTFont

        class ContourPen(BasePen):
            def __init__(self, glyph_set):
                super().__init__(glyph_set)
                self.contours: list[tuple[tuple[float, float], list[tuple]]] = []
                self._start: tuple[float, float] | None = None
                self._segments: list[tuple] = []

            def _moveTo(self, point):
                self._start, self._segments = point, []

            def _lineTo(self, point):
                self._segments.append(("l", point))

            def _curveToOne(self, c1, c2, point):
                self._segments.append(("c", c1, c2, point))

            def _closePath(self):
                if self._start is not None and self._segments:
                    self.contours.append((self._start, self._segments))
                self._start, self._segments = None, []

            _endPath = _closePath

        self._pen_class = ContourPen
        self.fonts = {weight: TTFont(path) for weight, path in FONTS.items()}
        self.units_per_em = {weight: font["head"].unitsPerEm for weight, font in self.fonts.items()}
        self._cache: dict[tuple[str, str], list] = {}

    def contours(self, weight: str, char: str) -> list:
        key = (weight, char)
        if key not in self._cache:
            font = self.fonts[weight]
            glyph_name = font.getBestCmap().get(ord(char))
            if glyph_name is None:
                raise ValueError(f"Glyph {char!r} is missing from the {weight} subset font.")
            glyph_set = font.getGlyphSet()
            pen = self._pen_class(glyph_set)
            glyph_set[glyph_name].draw(pen)
            self._cache[key] = pen.contours
        return self._cache[key]

    def advance(self, weight: str, size: float) -> float:
        font = self.fonts[weight]
        width, _ = font["hmtx"][font.getBestCmap()[ord("a")]]
        return width / self.units_per_em[weight] * size


def placed_glyphs(line: TextLine, outlines: GlyphOutlines):
    """Yield (char_index, run, char, x) for each visible character of a line."""
    x = line.x
    index = 0
    for run in line.runs:
        step = outlines.advance(run.weight, run.size)
        for char in run.text:
            if char != " ":
                yield index, run, char, x
            x += step
            index += 1


def r2(value: float) -> float:
    rounded = round(value, 2)
    return 0.0 if rounded == 0 else rounded


# --------------------------------------------------------------------------- lottie


def hex_rgba(color: str) -> list[float]:
    color = color.lstrip("#")
    return [round(int(color[i : i + 2], 16) / 255, 4) for i in (0, 2, 4)] + [1]


def static(value) -> dict:
    return {"a": 0, "k": value}


def hold_keys(points: list[tuple[int, list[float]]]) -> dict:
    if len(points) == 1:
        return static(points[0][1])
    return {"a": 1, "k": [{"t": t, "s": value, "h": 1} for t, value in points]}


def group_transform(opacity=None) -> dict:
    return {
        "ty": "tr",
        "p": static([0, 0]),
        "a": static([0, 0]),
        "s": static([100, 100]),
        "r": static(0),
        "o": opacity if opacity is not None else static(100),
        "sk": static(0),
        "sa": static(0),
    }


def fill(color: str) -> dict:
    return {"ty": "fl", "c": static(hex_rgba(color)), "o": static(100), "r": 1, "bm": 0}


def stroke(color: str, width: float) -> dict:
    return {
        "ty": "st",
        "c": static(hex_rgba(color)),
        "o": static(100),
        "w": static(width),
        "lc": 2,
        "lj": 2,
        "ml": 4,
        "bm": 0,
    }


def lottie_path(vertices, in_tangents, out_tangents, closed=True) -> dict:
    return {
        "ty": "sh",
        "ks": static({"i": in_tangents, "o": out_tangents, "v": vertices, "c": closed}),
    }


def contour_to_lottie(start, segments, scale: float, ox: float, oy: float) -> dict:
    def px(point):
        return [r2(ox + point[0] * scale), r2(oy - point[1] * scale)]

    vertices = [px(start)]
    ins = [[0, 0]]
    outs = [[0, 0]]
    for segment in segments:
        if segment[0] == "l":
            vertices.append(px(segment[1]))
            ins.append([0, 0])
            outs.append([0, 0])
        else:
            _, c1, c2, end = segment
            prev = vertices[-1]
            c1p, c2p, endp = px(c1), px(c2), px(end)
            outs[-1] = [r2(c1p[0] - prev[0]), r2(c1p[1] - prev[1])]
            vertices.append(endp)
            ins.append([r2(c2p[0] - endp[0]), r2(c2p[1] - endp[1])])
            outs.append([0, 0])
    if len(vertices) > 1 and vertices[-1] == vertices[0]:
        ins[0] = ins[-1]
        vertices.pop(), ins.pop(), outs.pop()
    return lottie_path(vertices, ins, outs)


def rect_path(x, y, w, h) -> dict:
    return lottie_path(
        [[x, y], [x + w, y], [x + w, y + h], [x, y + h]], [[0, 0]] * 4, [[0, 0]] * 4
    )


def rounded_rect_path(x, y, w, h, top: float, bottom: float) -> dict:
    """Closed path for a rectangle with independent top/bottom corner radii."""
    k = 0.5523  # cubic circle approximation
    v, i, o = [], [], []

    def corner(px_, py_, in_t, out_t):
        v.append([r2(px_), r2(py_)])
        i.append([r2(in_t[0]), r2(in_t[1])])
        o.append([r2(out_t[0]), r2(out_t[1])])

    corner(x + top, y, (-top * k, 0), (0, 0))
    corner(x + w - top, y, (0, 0), (top * k, 0))
    corner(x + w, y + top, (0, -top * k), (0, 0))
    corner(x + w, y + h - bottom, (0, 0), (0, bottom * k))
    corner(x + w - bottom, y + h, (bottom * k, 0), (0, 0))
    corner(x + bottom, y + h, (0, 0), (-bottom * k, 0))
    corner(x, y + h - bottom, (0, bottom * k), (0, 0))
    corner(x, y + top, (0, 0), (0, -top * k))
    return lottie_path(v, i, o)


def ellipse(cx, cy, radius) -> dict:
    return {"ty": "el", "d": 1, "p": static([cx, cy]), "s": static([radius * 2, radius * 2])}


def group(name: str, items: list[dict], opacity=None) -> dict:
    return {"ty": "gr", "nm": name, "it": [*items, group_transform(opacity)]}


def shape_layer(index: int, name: str, shapes: list[dict], ip: int, op: int, opacity=None) -> dict:
    return {
        "ddd": 0,
        "ind": index,
        "ty": 4,
        "nm": name,
        "sr": 1,
        "ks": {
            "o": opacity if opacity is not None else static(100),
            "r": static(0),
            "p": static([0, 0, 0]),
            "a": static([0, 0, 0]),
            "s": static([100, 100, 100]),
        },
        "ao": 0,
        "shapes": shapes,
        "ip": ip,
        "op": op,
        "st": 0,
        "bm": 0,
    }


def chrome_text_lines(outlines: GlyphOutlines) -> list[TextLine]:
    """Title-bar and status-bar text, shared by the Lottie and SVG builders."""
    title = TextLine("title", 0, 29, [Run("febri@workbench: ~ — zsh", PALETTE["muted"], 13)])
    title.x = (WIDTH - len(title.text) * outlines.advance("regular", 13)) / 2
    right_text = "android · linux · kernel · ci"
    status_left = TextLine(
        "status left",
        PAD_X - 14,
        HEIGHT - 12,
        [Run("● ", PALETTE["mint"], 12), Run("main", PALETTE["muted"], 12), Run("   ~/workbench", PALETTE["dim"], 12)],
    )
    status_right = TextLine(
        "status right",
        WIDTH - PAD_X + 14 - len(right_text) * outlines.advance("regular", 12),
        HEIGHT - 12,
        [Run(right_text, PALETTE["dim"], 12)],
    )
    return [title, status_left, status_right]


def chrome_shapes(outlines: GlyphOutlines) -> list[tuple[str, list[dict]]]:
    """Static window chrome as (layer name, shapes), topmost first."""
    title, status_left, status_right = chrome_text_lines(outlines)
    status_y = HEIGHT - STATUS_H

    def text_group(line: TextLine) -> list[dict]:
        return [glyph_group(outlines, run, char, x, line.baseline) for _, run, char, x in placed_glyphs(line, outlines)]

    lights = []
    for cx, key in ((22, "close"), (42, "minimize"), (62, "zoom")):
        lights.append(group(f"window control {key}", [ellipse(cx, TITLE_H / 2, 6), fill(PALETTE[key])]))

    return [
        ("status text", text_group(status_left) + text_group(status_right)),
        ("title text", text_group(title)),
        ("window controls", lights),
        (
            "frame",
            [
                group("border", [rounded_rect_path(0.5, 0.5, WIDTH - 1, HEIGHT - 1, RADIUS - 0.5, RADIUS - 0.5), stroke(PALETTE["border"], 1)]),
                group("title divider", [rect_path(1, TITLE_H, WIDTH - 2, 1), fill(PALETTE["divider"])]),
                group("status divider", [rect_path(1, status_y, WIDTH - 2, 1), fill(PALETTE["divider"])]),
                group("title bar", [rounded_rect_path(0, 0, WIDTH, TITLE_H, RADIUS, 0), fill(PALETTE["chrome"])]),
                group("status bar", [rounded_rect_path(0, status_y, WIDTH, STATUS_H, 0, RADIUS), fill(PALETTE["status"])]),
                group("window", [rounded_rect_path(0, 0, WIDTH, HEIGHT, RADIUS, RADIUS), fill(PALETTE["window"])]),
            ],
        ),
    ]


def glyph_group(outlines: GlyphOutlines, run: Run, char: str, x: float, baseline: float, opacity=None) -> dict:
    scale = run.size / outlines.units_per_em[run.weight]
    paths = [contour_to_lottie(start, segs, scale, x, baseline) for start, segs in outlines.contours(run.weight, char)]
    return group(char, [*paths, fill(run.color)], opacity)


def build_lottie(scene: Scene, outlines: GlyphOutlines) -> dict:
    total = scene.total_frames
    layers: list[dict] = []

    # Cursor: hold keyframes for position and visibility.
    positions: list[tuple[int, list[float]]] = []
    visibility: list[tuple[int, list[float]]] = []
    for frame, (x, baseline, on) in enumerate(scene.cursor):
        position = [r2(x), r2(baseline - 16), 0] if on else None
        if on and (not positions or positions[-1][1] != position):
            positions.append((frame, position))
        value = [100] if on else [0]
        if not visibility or visibility[-1][1] != value:
            visibility.append((frame, value))
    cursor_shape = group("block", [rect_path(0, 0, r2(CURSOR_W), CURSOR_H), fill(PALETTE["violet_deep"])])
    cursor_layer = shape_layer(1, "cursor", [cursor_shape], 0, total, opacity=hold_keys(visibility))
    cursor_layer["ks"]["p"] = hold_keys(positions)
    layers.append(cursor_layer)

    for line in scene.lines:
        groups = []
        for index, run, char, x in placed_glyphs(line, outlines):
            opacity = None
            if line.typed is not None:
                reveal = line.typed[index]
                opacity = hold_keys([(0, [0]), (reveal, [100])]) if reveal > 0 else None
            groups.append(glyph_group(outlines, run, char, x, line.baseline, opacity))
        start = 0 if line.typed is not None else line.appear
        if line.clear is None:
            layers.append(shape_layer(len(layers) + 1, line.name, groups, start, total))
        else:
            # Renderers disagree on whether the out-point frame is drawn, so the
            # layer is hidden by an opacity hold key at `clear` as well.
            opacity = hold_keys([(0, [100]), (line.clear, [0])])
            layers.append(shape_layer(len(layers) + 1, line.name, groups, start, line.clear + 1, opacity))

    for name, shapes in chrome_shapes(outlines):
        layers.append(shape_layer(len(layers) + 1, name, shapes, 0, total))

    return {
        "v": "5.7.4",
        "fr": FPS,
        "ip": 0,
        "op": total,
        "w": WIDTH,
        "h": HEIGHT,
        "nm": "terminal-intro",
        "ddd": 0,
        "assets": [],
        "meta": {
            "g": "scripts/build_terminal_assets.py",
            "a": "FebriCahyaa",
            "d": "Illustrative terminal session for the FebriCahyaa GitHub profile. "
            "Glyphs outlined from JetBrains Mono NL (SIL OFL 1.1).",
        },
        "layers": layers,
    }


# --------------------------------------------------------------------------- svg


def svg_contour(start, segments) -> str:
    def fmt(point):
        return f"{round(point[0], 1):g} {round(point[1], 1):g}"

    parts = [f"M{fmt(start)}"]
    for segment in segments:
        if segment[0] == "l":
            parts.append(f"L{fmt(segment[1])}")
        else:
            parts.append(f"C{fmt(segment[1])} {fmt(segment[2])} {fmt(segment[3])}")
    parts.append("Z")
    return "".join(parts)


def svg_rounded_rect(x, y, w, h, top, bottom) -> str:
    return (
        f"M{x + top:g} {y:g}H{x + w - top:g}"
        + (f"A{top:g} {top:g} 0 0 1 {x + w:g} {y + top:g}" if top else "")
        + f"V{y + h - bottom:g}"
        + (f"A{bottom:g} {bottom:g} 0 0 1 {x + w - bottom:g} {y + h:g}" if bottom else "")
        + f"H{x + bottom:g}"
        + (f"A{bottom:g} {bottom:g} 0 0 1 {x:g} {y + h - bottom:g}" if bottom else "")
        + f"V{y + top:g}"
        + (f"A{top:g} {top:g} 0 0 1 {x + top:g} {y:g}" if top else "")
        + "Z"
    )


def build_svg(scene: Scene, outlines: GlyphOutlines) -> str:
    """Static poster frame: everything visible right before `clear` is typed."""
    frame = scene.poster_frame
    visible_lines = [
        line
        for line in scene.lines
        if (line.typed is not None and line.typed[0] <= frame or line.typed is None and line.appear <= frame)
        and (line.clear is None or line.clear > frame)
    ]

    glyph_ids: dict[tuple[str, str], str] = {}
    defs: list[str] = []
    uses: list[str] = []

    def place(run: Run, char: str, x: float, baseline: float) -> None:
        key = (run.weight, char)
        if key not in glyph_ids:
            glyph_ids[key] = f"{run.weight[0]}{ord(char):x}"
            d = "".join(svg_contour(start, segs) for start, segs in outlines.contours(run.weight, char))
            defs.append(f'<path id="{glyph_ids[key]}" d="{d}"/>')
        scale = run.size / outlines.units_per_em[run.weight]
        uses.append(
            f'<use href="#{glyph_ids[key]}" fill="{run.color}" '
            f'transform="matrix({scale:g} 0 0 {-scale:g} {round(x, 2):g} {round(baseline, 2):g})"/>'
        )

    for line in [*chrome_text_lines(outlines), *visible_lines]:
        for _, run, char, x in placed_glyphs(line, outlines):
            place(run, char, x, line.baseline)

    cursor_x, cursor_baseline, _ = scene.cursor[frame]
    status_y = HEIGHT - STATUS_H
    lights = "".join(
        f'<circle cx="{cx}" cy="{TITLE_H // 2}" r="6" fill="{PALETTE[key]}"/>'
        for cx, key in ((22, "close"), (42, "minimize"), (62, "zoom"))
    )
    body = "\n  ".join(
        [
            f'<path d="{svg_rounded_rect(0, 0, WIDTH, HEIGHT, RADIUS, RADIUS)}" fill="{PALETTE["window"]}"/>',
            f'<path d="{svg_rounded_rect(0, 0, WIDTH, TITLE_H, RADIUS, 0)}" fill="{PALETTE["chrome"]}"/>',
            f'<path d="{svg_rounded_rect(0, status_y, WIDTH, STATUS_H, 0, RADIUS)}" fill="{PALETTE["status"]}"/>',
            f'<path d="M1 {TITLE_H}H{WIDTH - 1}v1H1zM1 {status_y}H{WIDTH - 1}v1H1z" fill="{PALETTE["divider"]}"/>',
            f'<path d="{svg_rounded_rect(0.5, 0.5, WIDTH - 1, HEIGHT - 1, RADIUS - 0.5, RADIUS - 0.5)}" '
            f'stroke="{PALETTE["border"]}" fill="none"/>',
            lights,
            "\n  ".join(uses),
            f'<rect x="{round(cursor_x, 2):g}" y="{cursor_baseline - 16:g}" width="{round(CURSOR_W, 2):g}" '
            f'height="{CURSOR_H}" fill="{PALETTE["violet_deep"]}"/>',
        ]
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">\n'
        f'  <title id="title">{escape(TITLE)}</title>\n'
        f'  <desc id="desc">{escape(DESCRIPTION)}</desc>\n'
        f'  <!-- Generated by scripts/build_terminal_assets.py; glyphs outlined from JetBrains Mono NL (SIL OFL 1.1). -->\n'
        f"  <defs>\n    " + "\n    ".join(defs) + "\n  </defs>\n"
        f"  {body}\n"
        "</svg>\n"
    )


# --------------------------------------------------------------------------- gif


def render_gif(lottie_path: Path, gif_path: Path, matte: str) -> dict:
    """Render the Lottie file with rlottie and write an optimized looping GIF."""
    from PIL import Image
    from rlottie_python import LottieAnimation

    animation = LottieAnimation.from_file(str(lottie_path))
    width, height = animation.lottie_animation_get_size()
    total = round(animation.lottie_animation_get_duration() * animation.lottie_animation_get_framerate())
    frame_ms = round(1000 / animation.lottie_animation_get_framerate())

    background = Image.new("RGBA", (width, height), matte)
    rendered: list[tuple[Image.Image, int]] = []
    previous = None
    for index in range(total):
        frame = animation.render_pillow_frame(frame_num=index, width=width, height=height)
        composed = Image.alpha_composite(background, frame).convert("RGB")
        data = composed.tobytes()
        if data == previous:
            image, duration = rendered[-1]
            rendered[-1] = (image, duration + frame_ms)
        else:
            rendered.append((composed, frame_ms))
            previous = data

    # One shared palette, built from the fullest frame, keeps colors stable between frames.
    poster = max((image for image, _ in rendered), key=lambda image: len(image.getcolors(1 << 20) or []))
    palette = poster.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    frames = [image.quantize(palette=palette, dither=Image.Dither.NONE) for image, _ in rendered]
    durations = [duration for _, duration in rendered]
    gif_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        disposal=1,
        optimize=False,
        comment=b"Rendered from assets/lottie/terminal-intro.json by scripts/build_terminal_assets.py",
    )
    return {"frames": len(frames), "duration_ms": sum(durations), "bytes": gif_path.stat().st_size}


# --------------------------------------------------------------------------- cli


def serialize_lottie(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="Fail if the committed Lottie/SVG differ from a fresh build.")
    parser.add_argument("--no-gif", action="store_true", help="Skip GIF rendering (no rlottie/Pillow needed).")
    args = parser.parse_args()

    try:
        outlines = GlyphOutlines()
    except ModuleNotFoundError as exc:
        print(f"ERROR: {exc.name} is required; install scripts/requirements-assets.txt", file=sys.stderr)
        return 2

    scene = build_scene()
    outputs = {
        LOTTIE_PATH: serialize_lottie(build_lottie(scene, outlines)),
        SVG_PATH: build_svg(scene, outlines),
    }

    if args.check:
        stale = [path for path, text in outputs.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
        for path in stale:
            print(f"Stale generated asset: {path.relative_to(ROOT)}", file=sys.stderr)
        if stale:
            print("Run: python3 scripts/build_terminal_assets.py", file=sys.stderr)
            return 1
        print("Generated Lottie and SVG assets are up to date.")
        return 0

    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")

    if not args.no_gif:
        for gif_path, matte in GIF_PATHS.items():
            try:
                stats = render_gif(LOTTIE_PATH, gif_path, matte)
            except ModuleNotFoundError as exc:
                print(f"ERROR: {exc.name} is required for GIF rendering; install scripts/requirements-assets.txt", file=sys.stderr)
                return 2
            print(
                f"wrote {gif_path.relative_to(ROOT)} ({stats['bytes']:,} bytes, "
                f"{stats['frames']} frames, {stats['duration_ms'] / 1000:.2f}s loop)"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
