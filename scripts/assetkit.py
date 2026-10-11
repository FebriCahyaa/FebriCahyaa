"""A small vector scene kit for the profile's animated assets.

One ``Scene`` (a list of elements with keyframed opacity and offset) is turned into:

* a Lottie (Bodymovin 5.7) JSON file built from shape layers only,
* a static SVG poster frame (the reduced-motion fallback),
* GIFs rendered *from the Lottie file* with rlottie, one per page background.

Text is outlined from the vendored JetBrains Mono NL subset so neither output
depends on installed fonts. ``fontTools`` is needed for any text; ``rlottie-python``
and ``Pillow`` only for GIF rendering. See docs/profile-automation.md.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence, Union
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
FONTS = {
    "regular": ASSETS / "fonts" / "JetBrainsMonoNL-Regular.subset.ttf",
    "bold": ASSETS / "fonts" / "JetBrainsMonoNL-Bold.subset.ttf",
}
ADVANCE_EM = 0.6  # JetBrains Mono advance width
# GitHub page backgrounds that rounded corners are blended onto, by GIF file suffix.
MATTES = {"": "#FFFFFF", "-dark": "#0D1117"}
NOISE_THRESHOLD = 8  # per-channel change (0-255) treated as rlottie rendering jitter between GIF frames

Number = Union[int, float]


def r2(value: float) -> float:
    rounded = round(value, 2)
    return 0.0 if rounded == 0 else rounded


def text_width(text: str, size: float) -> float:
    return len(text) * size * ADVANCE_EM


# --------------------------------------------------------------------------- tracks


@dataclass(frozen=True)
class Key:
    t: int
    v: tuple[float, ...]
    hold: bool = True  # True: jump at the next key; False: interpolate linearly to it


class Track:
    """A keyframed value. Scalars are stored as 1-tuples."""

    def __init__(self, keys: Sequence[Key]):
        if not keys:
            raise ValueError("a track needs at least one key")
        merged: dict[int, Key] = {}
        for key in keys:
            merged[key.t] = key  # a later key at the same frame wins
        self.keys = [merged[t] for t in sorted(merged)]

    @staticmethod
    def _tuple(value) -> tuple[float, ...]:
        return tuple(value) if isinstance(value, (tuple, list)) else (value,)

    @classmethod
    def const(cls, value) -> "Track":
        return cls([Key(0, cls._tuple(value))])

    @classmethod
    def steps(cls, points: Sequence[tuple[int, object]]) -> "Track":
        """Hold keys: the value jumps at each listed frame."""
        return cls([Key(t, cls._tuple(v), True) for t, v in points])

    @classmethod
    def ramp(cls, points: Sequence[tuple[int, object]]) -> "Track":
        """Linear keys: the value moves smoothly between consecutive points."""
        return cls([Key(t, cls._tuple(v), False) for t, v in points])

    @property
    def animated(self) -> bool:
        return len(self.keys) > 1

    def at(self, frame: float) -> tuple[float, ...]:
        previous = self.keys[0]
        for index, key in enumerate(self.keys):
            if key.t > frame:
                if index == 0 or previous.hold:
                    return previous.v
                span = key.t - previous.t
                ratio = (frame - previous.t) / span
                return tuple(a + (b - a) * ratio for a, b in zip(previous.v, key.v))
            previous = key
        return previous.v

    def lottie(self, mapper=None) -> dict:
        def value(v):
            mapped = mapper(v) if mapper else list(v)
            return mapped

        if not self.animated:
            v = value(self.keys[0].v)
            return {"a": 0, "k": v[0] if len(v) == 1 and mapper is None else v}
        frames = []
        for index, key in enumerate(self.keys):
            entry: dict = {"t": key.t, "s": value(key.v)}
            if index < len(self.keys) - 1:
                if key.hold:
                    entry["h"] = 1
                else:
                    entry["o"] = {"x": [0], "y": [0]}
                    entry["i"] = {"x": [1], "y": [1]}
            frames.append(entry)
        return {"a": 1, "k": frames}


def blink_steps(start: int, length: int, first_on: int = 13, on: int = 13, off: int = 12) -> list[tuple[int, int]]:
    """Opacity steps for a blinking cursor over [start, start + length)."""
    points, frame, visible, phase = [], start, True, first_on
    while frame < start + length:
        points.append((frame, 100 if visible else 0))
        frame += phase
        visible = not visible
        phase = on if visible else off
    return points


# --------------------------------------------------------------------------- elements


@dataclass(frozen=True)
class Run:
    text: str
    color: str
    size: float = 17
    weight: str = "regular"


@dataclass
class Element:
    name: str = ""
    opacity: Track = field(default_factory=lambda: Track.const(100))
    offset: Track = field(default_factory=lambda: Track.const((0, 0)))


@dataclass
class Text(Element):
    runs: list[Run] = field(default_factory=list)
    x: float = 0
    baseline: float = 0
    typed: list[int] | None = None  # per-character reveal frame

    @property
    def text(self) -> str:
        return "".join(run.text for run in self.runs)

    @property
    def width(self) -> float:
        return sum(text_width(run.text, run.size) for run in self.runs)


@dataclass
class Rect(Element):
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0
    radius: float = 0
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float = 1
    width: Track | None = None  # animated width, growing from the left edge


@dataclass
class RoundRect(Element):
    """Rectangle with separate top and bottom corner radii (window chrome)."""

    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0
    top: float = 0
    bottom: float = 0
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float = 1


@dataclass
class Circle(Element):
    cx: float = 0
    cy: float = 0
    r: float = 0
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float = 1


@dataclass
class Icon(Element):
    """A 24×24 SVG path icon (Simple Icons). Static SVG output only."""

    d: str = ""
    x: float = 0
    y: float = 0
    size: float = 24
    fill: str = "#FFFFFF"


@dataclass
class Scene:
    name: str
    width: int
    height: int
    title: str
    description: str
    elements: list[Element] = field(default_factory=list)  # painted bottom to top
    fps: int = 25
    frames: int = 1
    poster: int = 0  # frame frozen into the static SVG
    animated: bool = True

    def add(self, *elements: Element) -> Element:
        self.elements.extend(elements)
        return elements[-1]


# --------------------------------------------------------------------------- glyphs


class GlyphOutlines:
    """Glyph contours in font units: (start, [segments]) with cubic curves only."""

    def __init__(self) -> None:
        from fontTools.pens.basePen import BasePen
        from fontTools.ttLib import TTFont

        class ContourPen(BasePen):
            def __init__(self, glyph_set):
                super().__init__(glyph_set)
                self.contours: list = []
                self._start = None
                self._segments: list = []

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
        self._cache: dict = {}

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

    def scale(self, run: Run) -> float:
        return run.size / self.units_per_em[run.weight]


def placed_glyphs(text: Text):
    """Yield (char_index, run, char, x) for each non-space character."""
    x, index = text.x, 0
    for run in text.runs:
        step = run.size * ADVANCE_EM
        for char in run.text:
            if char != " ":
                yield index, run, char, x
            x += step
            index += 1


# --------------------------------------------------------------------------- lottie


def hex_rgba(color: str) -> list[float]:
    color = color.lstrip("#")
    return [round(int(color[i : i + 2], 16) / 255, 4) for i in (0, 2, 4)] + [1]


def static(value) -> dict:
    return {"a": 0, "k": value}


def _transform(opacity: dict | None = None) -> dict:
    return {
        "ty": "tr",
        "p": static([0, 0]),
        "a": static([0, 0]),
        "s": static([100, 100]),
        "r": static(0),
        "o": opacity or static(100),
        "sk": static(0),
        "sa": static(0),
    }


def _group(name: str, items: list[dict], opacity: dict | None = None) -> dict:
    return {"ty": "gr", "nm": name, "it": [*items, _transform(opacity)]}


def _paint(fill: str | None, stroke: str | None, stroke_width: float) -> list[dict]:
    paint = []
    if stroke:
        paint.append(
            {"ty": "st", "c": static(hex_rgba(stroke)), "o": static(100), "w": static(stroke_width), "lc": 2, "lj": 2, "ml": 4, "bm": 0}
        )
    if fill:
        paint.append({"ty": "fl", "c": static(hex_rgba(fill)), "o": static(100), "r": 1, "bm": 0})
    return paint


def _path(vertices, ins, outs, closed=True) -> dict:
    return {"ty": "sh", "ks": static({"i": ins, "o": outs, "v": vertices, "c": closed})}


def contour_to_lottie(start, segments, scale: float, ox: float, oy: float) -> dict:
    def px(point):
        return [r2(ox + point[0] * scale), r2(oy - point[1] * scale)]

    vertices, ins, outs = [px(start)], [[0, 0]], [[0, 0]]
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
    return _path(vertices, ins, outs)


def _round_rect_path(x, y, w, h, top, bottom) -> dict:
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
    return _path(v, i, o)


def _glyph_group(outlines: GlyphOutlines, run: Run, char: str, x: float, baseline: float, opacity=None) -> dict:
    scale = outlines.scale(run)
    paths = [contour_to_lottie(start, segs, scale, x, baseline) for start, segs in outlines.contours(run.weight, char)]
    return _group(char, [*paths, *_paint(run.color, None, 0)], opacity)


def _element_shapes(element: Element, outlines: GlyphOutlines | None) -> list[dict]:
    if isinstance(element, Text):
        if outlines is None:
            raise ValueError("fontTools is required for text")
        groups = []
        for index, run, char, x in placed_glyphs(element):
            opacity = None
            if element.typed is not None and element.typed[index] > 0:
                opacity = Track.steps([(0, 0), (element.typed[index], 100)]).lottie()
            groups.append(_glyph_group(outlines, run, char, x, element.baseline, opacity))
        return groups
    if isinstance(element, Rect):
        paint = _paint(element.fill, element.stroke, element.stroke_width)
        cy = element.y + element.h / 2
        if element.width is None:
            size = static([r2(element.w), r2(element.h)])
            position = static([r2(element.x + element.w / 2), r2(cy)])
        else:
            size = element.width.lottie(lambda v: [r2(v[0]), r2(element.h)])
            position = element.width.lottie(lambda v: [r2(element.x + v[0] / 2), r2(cy)])
        rect = {"ty": "rc", "d": 1, "s": size, "p": position, "r": static(element.radius)}
        return [_group(element.name or "rect", [rect, *paint])]
    if isinstance(element, RoundRect):
        path = _round_rect_path(element.x, element.y, element.w, element.h, element.top, element.bottom)
        return [_group(element.name or "round rect", [path, *_paint(element.fill, element.stroke, element.stroke_width)])]
    if isinstance(element, Circle):
        ellipse = {"ty": "el", "d": 1, "p": static([element.cx, element.cy]), "s": static([element.r * 2, element.r * 2])}
        return [_group(element.name or "circle", [ellipse, *_paint(element.fill, element.stroke, element.stroke_width)])]
    raise ValueError(f"{type(element).__name__} cannot be exported to Lottie")


def build_lottie(scene: Scene, outlines: GlyphOutlines | None) -> dict:
    layers = []
    for index, element in enumerate(reversed(scene.elements), start=1):
        layers.append(
            {
                "ddd": 0,
                "ind": index,
                "ty": 4,
                "nm": element.name or type(element).__name__.lower(),
                "sr": 1,
                "ks": {
                    "o": element.opacity.lottie(),
                    "r": static(0),
                    "p": element.offset.lottie(lambda v: [r2(v[0]), r2(v[1]), 0]),
                    "a": static([0, 0, 0]),
                    "s": static([100, 100, 100]),
                },
                "ao": 0,
                "shapes": _element_shapes(element, outlines),
                "ip": 0,
                "op": scene.frames,
                "st": 0,
                "bm": 0,
            }
        )
    return {
        "v": "5.7.4",
        "fr": scene.fps,
        "ip": 0,
        "op": scene.frames,
        "w": scene.width,
        "h": scene.height,
        "nm": scene.name,
        "ddd": 0,
        "assets": [],
        "meta": {
            "g": "scripts/build_assets.py",
            "a": "FebriCahyaa",
            "d": f"{scene.title}. Glyphs outlined from JetBrains Mono NL (SIL OFL 1.1).",
        },
        "layers": layers,
    }


def serialize_lottie(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"


# --------------------------------------------------------------------------- svg


def _num(value: float) -> str:
    return f"{round(value, 2):g}"


def _svg_contour(start, segments) -> str:
    def fmt(point):
        return f"{round(point[0], 1):g} {round(point[1], 1):g}"

    parts = [f"M{fmt(start)}"]
    for segment in segments:
        if segment[0] == "l":
            parts.append(f"L{fmt(segment[1])}")
        else:
            parts.append(f"C{fmt(segment[1])} {fmt(segment[2])} {fmt(segment[3])}")
    return "".join(parts) + "Z"


def _svg_round_rect(x, y, w, h, top, bottom) -> str:
    n = _num
    return (
        f"M{n(x + top)} {n(y)}H{n(x + w - top)}"
        + (f"A{n(top)} {n(top)} 0 0 1 {n(x + w)} {n(y + top)}" if top else "")
        + f"V{n(y + h - bottom)}"
        + (f"A{n(bottom)} {n(bottom)} 0 0 1 {n(x + w - bottom)} {n(y + h)}" if bottom else "")
        + f"H{n(x + bottom)}"
        + (f"A{n(bottom)} {n(bottom)} 0 0 1 {n(x)} {n(y + h - bottom)}" if bottom else "")
        + f"V{n(y + top)}"
        + (f"A{n(top)} {n(top)} 0 0 1 {n(x + top)} {n(y)}" if top else "")
        + "Z"
    )


def _svg_paint(fill, stroke, stroke_width) -> str:
    attrs = f' fill="{fill}"' if fill else ' fill="none"'
    if stroke:
        attrs += f' stroke="{stroke}"' + (f' stroke-width="{_num(stroke_width)}"' if stroke_width != 1 else "")
    return attrs


def build_svg(scene: Scene, outlines: GlyphOutlines | None) -> str:
    """Static SVG of the scene at its poster frame."""
    frame = scene.poster
    glyph_ids: dict = {}
    defs: list[str] = []
    body: list[str] = []

    for element in scene.elements:
        opacity = element.opacity.at(frame)[0]
        if opacity <= 0:
            continue
        dx, dy = element.offset.at(frame)
        markup: list[str] = []
        if isinstance(element, Text):
            for index, run, char, x in placed_glyphs(element):
                if element.typed is not None and element.typed[index] > frame:
                    continue
                key = (run.weight, char)
                if key not in glyph_ids:
                    glyph_ids[key] = f"{run.weight[0]}{ord(char):x}"
                    d = "".join(_svg_contour(start, segs) for start, segs in outlines.contours(run.weight, char))
                    defs.append(f'<path id="{glyph_ids[key]}" d="{d}"/>')
                scale = outlines.scale(run)
                markup.append(
                    f'<use href="#{glyph_ids[key]}" fill="{run.color}" '
                    f'transform="matrix({scale:g} 0 0 {-scale:g} {_num(x)} {_num(element.baseline)})"/>'
                )
        elif isinstance(element, Rect):
            width = element.width.at(frame)[0] if element.width is not None else element.w
            if width <= 0:
                continue
            radius = f' rx="{_num(element.radius)}"' if element.radius else ""
            markup.append(
                f'<rect x="{_num(element.x)}" y="{_num(element.y)}" width="{_num(width)}" height="{_num(element.h)}"{radius}'
                f"{_svg_paint(element.fill, element.stroke, element.stroke_width)}/>"
            )
        elif isinstance(element, RoundRect):
            d = _svg_round_rect(element.x, element.y, element.w, element.h, element.top, element.bottom)
            markup.append(f'<path d="{d}"{_svg_paint(element.fill, element.stroke, element.stroke_width)}/>')
        elif isinstance(element, Circle):
            markup.append(
                f'<circle cx="{_num(element.cx)}" cy="{_num(element.cy)}" r="{_num(element.r)}"'
                f"{_svg_paint(element.fill, element.stroke, element.stroke_width)}/>"
            )
        elif isinstance(element, Icon):
            scale = element.size / 24
            markup.append(
                f'<path d="{element.d}" fill="{element.fill}" '
                f'transform="matrix({scale:g} 0 0 {scale:g} {_num(element.x)} {_num(element.y)})"/>'
            )
        else:
            raise ValueError(f"{type(element).__name__} cannot be exported to SVG")
        attrs = ""
        if opacity < 100:
            attrs += f' opacity="{opacity / 100:g}"'
        if (dx, dy) != (0, 0):
            attrs += f' transform="translate({_num(dx)} {_num(dy)})"'
        if attrs:
            body.append(f"<g{attrs}>" + "".join(markup) + "</g>")
        else:
            body.extend(markup)

    defs_block = ("  <defs>\n    " + "\n    ".join(defs) + "\n  </defs>\n") if defs else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{scene.width}" height="{scene.height}" '
        f'viewBox="0 0 {scene.width} {scene.height}" role="img" aria-labelledby="title desc">\n'
        f"  <title id=\"title\">{escape(scene.title)}</title>\n"
        f"  <desc id=\"desc\">{escape(scene.description)}</desc>\n"
        "  <!-- Generated by scripts/build_assets.py; glyphs outlined from JetBrains Mono NL (SIL OFL 1.1). -->\n"
        f"{defs_block}"
        "  " + "\n  ".join(body) + "\n"
        "</svg>\n"
    )


def icon_path(name: str) -> str:
    """Path data of a vendored Simple Icons SVG (CC0)."""
    svg = (ASSETS / "icons" / f"{name}.svg").read_text(encoding="utf-8")
    match = re.search(r'<path d="([^"]+)"', svg)
    if not match:
        raise ValueError(f"No path in assets/icons/{name}.svg")
    return match.group(1)


# --------------------------------------------------------------------------- gif


def render_gif(lottie_path: Path, gif_path: Path, matte: str, comment: str) -> dict:
    """Render a Lottie file with rlottie and write an optimized, forever-looping GIF."""
    from PIL import Image, ImageChops
    from rlottie_python import LottieAnimation

    animation = LottieAnimation.from_file(str(lottie_path))
    width, height = animation.lottie_animation_get_size()
    fps = animation.lottie_animation_get_framerate()
    total = round(animation.lottie_animation_get_duration() * fps)
    frame_ms = round(1000 / fps)

    background = Image.new("RGBA", (width, height), matte)
    rendered: list[list] = []
    previous = None
    previous_image = None
    for index in range(total):
        frame = animation.render_pillow_frame(frame_num=index, width=width, height=height)
        composed = Image.alpha_composite(background, frame).convert("RGB")
        if previous_image is not None:
            # rlottie shifts the whole canvas by ±1 on some frames; keep the previous
            # pixel where the change is imperceptible so frames encode as small deltas.
            channels = ImageChops.difference(composed, previous_image).split()
            changed = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
            mask = changed.point(lambda value: 255 if value > NOISE_THRESHOLD else 0)
            composed = Image.composite(composed, previous_image, mask)
        previous_image = composed
        data = composed.tobytes()
        if data == previous:
            rendered[-1][1] += frame_ms
        else:
            rendered.append([composed, frame_ms])
            previous = data

    # One palette shared by every frame (built from a sample of frames) keeps
    # colours stable; no dithering, so flat areas stay flat.
    sample = [image for image, _ in rendered[:: max(1, len(rendered) // 24)]]
    sheet = Image.new("RGB", (width, height * len(sample)))
    for row, image in enumerate(sample):
        sheet.paste(image, (0, row * height))
    palette = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
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
        comment=comment.encode("ascii"),
    )
    return {"frames": len(frames), "duration_ms": sum(durations), "bytes": gif_path.stat().st_size}
