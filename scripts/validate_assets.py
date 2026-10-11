#!/usr/bin/env python3
"""Validate the profile's generated assets, README references, and workflow writers.

Standard library only, so it runs in CI and offline without installing anything.
It checks structure and metadata; it does not render anything in a browser.
"""
from __future__ import annotations

import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
WORKFLOWS = ROOT / ".github" / "workflows"
ASSETS = ROOT / "assets"
LOTTIE_DIR = ASSETS / "lottie"
GIF_DIR = ASSETS / "animations"
STATIC_DIR = ASSETS / "static"
SOCIAL_DIR = ASSETS / "social"
GIF_SUFFIXES = ("", "-dark")  # light and dark page backgrounds
GIF_BUDGET_BYTES = 2 * 1024 * 1024
# The only workflow allowed to commit README.md (see docs/profile-automation.md).
README_WRITER = "profile-refresh.yml"
# Marker schemes used by retired workflows; nothing may target them any more.
LEGACY_MARKERS = (
    "STATS_REPOS",
    "FLUX_COMMIT",
    "<!--TIME-->",
    "<!--STATUS",
    "LAST_UPDATED_START",
    "COMMIT_HASH",
    "readme-typing-svg",
)
SVG_NS = "{http://www.w3.org/2000/svg}"


class AssetError(ValueError):
    """Raised when an asset fails validation."""


# --------------------------------------------------------------------------- svg


def check_svg(path: Path) -> dict:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise AssetError(f"{path.name}: invalid XML: {exc}") from exc
    if root.tag != f"{SVG_NS}svg":
        raise AssetError(f"{path.name}: root element is not <svg>")
    width, height = root.get("width"), root.get("height")
    view_box = (root.get("viewBox") or "").split()
    if not (width and height and len(view_box) == 4):
        raise AssetError(f"{path.name}: width, height and viewBox are required")
    if [float(v) for v in view_box[2:]] != [float(width), float(height)]:
        raise AssetError(f"{path.name}: viewBox does not match width/height")
    if root.find(f"{SVG_NS}title") is None or root.find(f"{SVG_NS}desc") is None:
        raise AssetError(f"{path.name}: <title> and <desc> are required for accessibility")
    if root.get("role") != "img":
        raise AssetError(f'{path.name}: role="img" is required')
    ids = {element.get("id") for element in root.iter() if element.get("id")}
    for element in root.iter():
        tag = element.tag.removeprefix(SVG_NS)
        if tag in {"script", "image", "foreignObject"}:
            raise AssetError(f"{path.name}: <{tag}> is not allowed")
        for name, value in element.attrib.items():
            if name.endswith("href"):
                if not value.startswith("#"):
                    raise AssetError(f"{path.name}: external reference {value!r}")
                if value[1:] not in ids:
                    raise AssetError(f"{path.name}: dangling reference {value!r}")
    return {"width": int(float(width)), "height": int(float(height)), "elements": sum(1 for _ in root.iter())}


# --------------------------------------------------------------------------- lottie

SHAPE_TYPES = {"gr", "sh", "rc", "el", "fl", "st", "tr"}
SHAPE_PROPERTIES = {"rc": ("p", "s", "r"), "el": ("p", "s"), "fl": ("c", "o"), "st": ("c", "o", "w")}


def _check_property(prop: object, where: str, first: int, last: int) -> None:
    if not isinstance(prop, dict) or "k" not in prop:
        raise AssetError(f"{where}: property must be an object with 'k'")
    if prop.get("a") == 1:
        keys = prop["k"]
        if not isinstance(keys, list) or not keys:
            raise AssetError(f"{where}: animated property needs keyframes")
        times = [key.get("t") for key in keys]
        if any(not isinstance(t, (int, float)) for t in times):
            raise AssetError(f"{where}: keyframe without numeric 't'")
        if times != sorted(times) or len(set(times)) != len(times):
            raise AssetError(f"{where}: keyframes must be strictly increasing")
        if times[0] < first or times[-1] > last:
            raise AssetError(f"{where}: keyframe outside the composition timeline")
        for key in keys:
            if "s" not in key:
                raise AssetError(f"{where}: keyframe without a start value")


def _check_shapes(shapes: list, where: str, first: int, last: int) -> int:
    count = 0
    for index, shape in enumerate(shapes):
        here = f"{where}[{index}]"
        kind = shape.get("ty")
        if kind not in SHAPE_TYPES:
            raise AssetError(f"{here}: unsupported shape type {kind!r}")
        if kind == "gr":
            items = shape.get("it")
            if not isinstance(items, list) or not items or items[-1].get("ty") != "tr":
                raise AssetError(f"{here}: group must end with a transform")
            count += _check_shapes(items, f"{here}.it", first, last)
        elif kind == "sh":
            path = shape["ks"]["k"]
            lengths = {len(path[key]) for key in ("v", "i", "o")}
            if len(lengths) != 1 or not path["v"]:
                raise AssetError(f"{here}: path vertex/tangent arrays differ in length")
            count += 1
        elif kind in {"fl", "st"}:
            color = shape["c"]["k"]
            if len(color) != 4 or any(not 0 <= channel <= 1 for channel in color):
                raise AssetError(f"{here}: colour channels must be within 0..1")
        if kind in SHAPE_PROPERTIES:
            for name in SHAPE_PROPERTIES[kind]:
                _check_property(shape.get(name), f"{here}.{name}", first, last)
        elif kind == "tr":
            for name in ("p", "a", "s", "r", "o"):
                _check_property(shape.get(name), f"{here}.{name}", first, last)
    return count


def check_lottie(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssetError(f"{path.name}: invalid JSON: {exc}") from exc
    for key in ("v", "fr", "ip", "op", "w", "h", "layers"):
        if key not in data:
            raise AssetError(f"{path.name}: missing top-level key {key!r}")
    if not (isinstance(data["fr"], (int, float)) and data["fr"] > 0):
        raise AssetError(f"{path.name}: frame rate must be positive")
    first, last = data["ip"], data["op"]
    if not last > first >= 0:
        raise AssetError(f"{path.name}: op must be greater than ip")
    layers = data["layers"]
    if not isinstance(layers, list) or not layers:
        raise AssetError(f"{path.name}: no layers")
    indices = [layer.get("ind") for layer in layers]
    if len(set(indices)) != len(indices):
        raise AssetError(f"{path.name}: layer indices must be unique")
    paths = 0
    for number, layer in enumerate(layers):
        where = f"{path.name}: layer {layer.get('nm', number)!r}"
        if layer.get("ty") != 4:
            raise AssetError(f"{where}: only shape layers are expected")
        if not first <= layer["ip"] < layer["op"] <= last + 1:
            raise AssetError(f"{where}: in/out points outside the timeline")
        for name in ("o", "r", "p", "a", "s"):
            _check_property(layer["ks"].get(name), f"{where}.ks.{name}", first, last)
        paths += _check_shapes(layer.get("shapes", []), where, first, last)
    return {
        "width": data["w"],
        "height": data["h"],
        "fps": data["fr"],
        "frames": last - first,
        "seconds": (last - first) / data["fr"],
        "layers": len(layers),
        "paths": paths,
    }


# --------------------------------------------------------------------------- gif


@dataclass
class GifInfo:
    width: int
    height: int
    frames: int = 0
    delays_cs: list[int] = field(default_factory=list)
    loop: int | None = None  # 0 = forever; None = no NETSCAPE2.0 block (plays once)
    size: int = 0

    @property
    def duration_ms(self) -> int:
        return sum(self.delays_cs) * 10

    def __str__(self) -> str:
        loop = "forever" if self.loop == 0 else self.loop
        return (
            f"{self.width}x{self.height}, {self.frames} frames, {self.duration_ms / 1000:.2f}s, "
            f"loop={loop}, {self.size:,} bytes"
        )


def _skip_sub_blocks(data: bytes, pos: int) -> int:
    while True:
        size = data[pos]
        pos += 1
        if size == 0:
            return pos
        pos += size


def parse_gif(path: Path) -> GifInfo:
    """Walk the GIF block structure; counts frames and reads delays and loop count."""
    data = path.read_bytes()
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        raise AssetError(f"{path.name}: not a GIF file")
    width, height, packed = struct.unpack("<HHB", data[6:11])
    info = GifInfo(width, height, size=len(data))
    pos = 13
    if packed & 0x80:
        pos += 3 * (2 ** ((packed & 0x07) + 1))
    pending_delay = 0
    try:
        while True:
            block = data[pos]
            if block == 0x3B:  # trailer
                break
            if block == 0x21:  # extension
                label = data[pos + 1]
                if label == 0xF9:  # graphic control extension
                    pending_delay = struct.unpack("<H", data[pos + 4 : pos + 6])[0]
                    pos = _skip_sub_blocks(data, pos + 2)
                elif label == 0xFF and data[pos + 3 : pos + 14] == b"NETSCAPE2.0":
                    info.loop = struct.unpack("<H", data[pos + 16 : pos + 18])[0]
                    pos = _skip_sub_blocks(data, pos + 2)
                else:
                    pos = _skip_sub_blocks(data, pos + 2)
            elif block == 0x2C:  # image descriptor
                local = data[pos + 9]
                pos += 10
                if local & 0x80:
                    pos += 3 * (2 ** ((local & 0x07) + 1))
                pos = _skip_sub_blocks(data, pos + 1)  # LZW minimum code size, then data
                info.frames += 1
                info.delays_cs.append(pending_delay)
                pending_delay = 0
            else:
                raise AssetError(f"{path.name}: unexpected block 0x{block:02x} at byte {pos}")
    except IndexError as exc:
        raise AssetError(f"{path.name}: truncated GIF") from exc
    return info


def check_gif(path: Path, width: int, height: int) -> GifInfo:
    info = parse_gif(path)
    if (info.width, info.height) != (width, height):
        raise AssetError(f"{path.name}: {info.width}x{info.height} does not match the Lottie size {width}x{height}")
    if info.frames < 2:
        raise AssetError(f"{path.name}: is not animated")
    if info.loop != 0:
        raise AssetError(f"{path.name}: must loop forever (NETSCAPE2.0 loop count 0)")
    if any(delay < 2 for delay in info.delays_cs):
        raise AssetError(f"{path.name}: frame delays under 20 ms are clamped by browsers")
    if info.size > GIF_BUDGET_BYTES:
        raise AssetError(f"{path.name}: {info.size:,} bytes exceeds the {GIF_BUDGET_BYTES:,} byte budget")
    return info


# --------------------------------------------------------------------------- readme


class _ReferenceCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []
        self.images_without_alt: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        for name in ("src", "href"):
            if attributes.get(name):
                self.references.append(attributes[name])
        if attributes.get("srcset"):
            self.references.extend(part.strip().split()[0] for part in attributes["srcset"].split(","))
        if tag == "img" and not (attributes.get("alt") or "").strip():
            self.images_without_alt.append(attributes.get("src", "?"))


def github_anchor(heading: str) -> str:
    text = re.sub(r"<[^>]+>", "", heading).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def check_readme(path: Path = README) -> dict:
    content = path.read_text(encoding="utf-8")
    collector = _ReferenceCollector()
    collector.feed(content)
    markdown_links = re.findall(r"\]\(([^)\s]+)\)", content)
    references = collector.references + markdown_links
    anchors = {github_anchor(match) for match in re.findall(r"^#{1,6}\s+(.+)$", content, flags=re.MULTILINE)}

    problems = []
    local = 0
    for reference in references:
        if reference.startswith(("http://", "https://", "mailto:")):
            continue
        if reference.startswith("#"):
            if reference[1:] not in anchors:
                problems.append(f"broken in-page link {reference}")
            continue
        local += 1
        target = (path.parent / reference.split("#", 1)[0]).resolve()
        if not target.exists():
            problems.append(f"missing local file {reference}")
        elif ROOT not in target.parents:
            problems.append(f"reference escapes the repository: {reference}")
    for source in collector.images_without_alt:
        problems.append(f"image without alt text: {source}")
    if problems:
        raise AssetError("README: " + "; ".join(problems))
    return {"references": len(references), "local": local, "anchors": sorted(anchors)}


# --------------------------------------------------------------------------- workflows


def readme_writers(directory: Path = WORKFLOWS) -> dict[str, bool]:
    """Map each workflow to whether it can commit README.md."""
    writers = {}
    for workflow in sorted(directory.glob("*.y*ml")):
        text = workflow.read_text(encoding="utf-8")
        commits = bool(re.search(r"git push|git commit|add-and-commit|git-auto-commit", text))
        writers[workflow.name] = commits and "README.md" in text
    return writers


def check_workflows(directory: Path = WORKFLOWS) -> dict:
    writers = [name for name, writes in readme_writers(directory).items() if writes]
    if writers != [README_WRITER]:
        raise AssetError(f"workflows: expected only {README_WRITER} to write README.md, found {writers or 'none'}")
    for workflow in directory.glob("*.y*ml"):
        text = workflow.read_text(encoding="utf-8")
        legacy = [marker for marker in LEGACY_MARKERS if marker in text]
        if legacy:
            raise AssetError(f"workflows: {workflow.name} targets retired README markers {legacy}")
        if re.search(r"cron:\s*['\"]\*/[1-9]\s", text) or "cron: \"* * * * *\"" in text:
            raise AssetError(f"workflows: {workflow.name} runs on a minute-level schedule")
    return {"writers": writers, "workflows": len(list(directory.glob("*.y*ml")))}


# --------------------------------------------------------------------------- cli


def scene_names() -> list[str]:
    return sorted(path.stem for path in LOTTIE_DIR.glob("*.json"))


def gif_paths(name: str) -> list[Path]:
    return [GIF_DIR / f"{name}{suffix}.gif" for suffix in GIF_SUFFIXES]


def check_scene(name: str) -> str:
    """A Lottie source, its static SVG poster, and its GIFs must agree with each other."""
    lottie = check_lottie(LOTTIE_DIR / f"{name}.json")
    svg = check_svg(STATIC_DIR / f"{name}.svg")
    if (svg["width"], svg["height"]) != (lottie["width"], lottie["height"]):
        raise AssetError(f"{name}: static SVG and Lottie composition sizes differ")
    gifs = []
    for path in gif_paths(name):
        info = check_gif(path, lottie["width"], lottie["height"])
        if abs(info.duration_ms - lottie["seconds"] * 1000) > 20:
            raise AssetError(f"{path.name}: loop is {info.duration_ms} ms but the Lottie timeline is {lottie['seconds'] * 1000:.0f} ms")
        gifs.append(info)
    sizes = " / ".join(f"{info.size / 1024:.0f} KiB" for info in gifs)
    return (
        f"{lottie['width']}x{lottie['height']}, {lottie['seconds']:.2f}s, {lottie['layers']} layers; "
        f"GIFs {gifs[0].frames} frames, loop forever, {sizes}"
    )


def check_orphans() -> str:
    """Every GIF and static SVG must belong to a Lottie source."""
    names = set(scene_names())
    expected = {path for name in names for path in gif_paths(name)} | {STATIC_DIR / f"{name}.svg" for name in names}
    found = set(GIF_DIR.glob("*.gif")) | set(STATIC_DIR.glob("*.svg"))
    orphans = sorted(str(path.relative_to(ROOT)) for path in found - expected)
    if orphans:
        raise AssetError(f"generated files without a Lottie source: {orphans}")
    return f"{len(names)} scenes, {len(found)} rendered files"


def main() -> int:
    failures = 0

    def run(label, func, *args):
        nonlocal failures
        try:
            result = func(*args)
        except (AssetError, OSError, KeyError, TypeError) as exc:
            failures += 1
            print(f"FAIL  {label}: {exc}")
            return None
        print(f"ok    {label}: {result}")
        return result

    if not scene_names():
        failures += 1
        print("FAIL  no Lottie sources found")
    for name in scene_names():
        run(f"scene {name}", check_scene, name)
    run("generated file set", check_orphans)
    for path in sorted(SOCIAL_DIR.glob("*.svg")):
        run(f"social {path.stem}", check_svg, path)
    run("README references", check_readme)
    run("workflow README writers", check_workflows)
    if failures:
        print(f"{failures} check(s) failed.")
        return 1
    print("All asset checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
