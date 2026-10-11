# How this profile is built

This repository is the `FebriCahyaa` GitHub profile. It has two moving parts:

- **Generated hero assets**: a terminal animation built from a Lottie source and committed to the repository.
- **Profile automation**: GitHub Actions workflows that keep a few README values current.

Everything is regenerated or validated by scripts in `scripts/`.

## Workflows

There is one writer for `README.md`. Every other workflow is read-only or writes to a different branch.

| Workflow | Responsibility | Writes | Trigger |
| --- | --- | --- | --- |
| `profile-refresh.yml` | Refreshes profile metrics, the latest Flux commit, and the "data last changed" timestamp | `README.md` on `main`, only when the data changed | Every 6 hours, on pushes that touch the README or updater, or manually |
| `validate-profile.yml` | Compiles scripts, checks README markers, validates assets and workflow writers, checks generated assets for drift, and runs unit tests | Nothing (`contents: read`) | Push and pull request to `main`, or manually |
| `snake.yml` | Generates light and dark contribution-snake SVGs | The orphan `output` branch only, never `main` | Daily at 08:30 WIB, or manually |
| `.github/dependabot.yml` | Proposes GitHub Actions version updates | Pull requests | Weekly |

All workflows use the short-lived `github.token` with least-privilege `permissions`. No personal access token or `TOKEN_GITHUB` secret is needed. Each job has a `timeout-minutes` and a concurrency group.

`scripts/validate_assets.py` enforces this layout in CI. It fails if any workflow other than `profile-refresh.yml` can commit `README.md`, if a workflow targets a retired marker, or if a workflow is scheduled at minute-level frequency.

### README markers

`scripts/update_profile.py` owns these marker pairs. Each must appear exactly once, with its start marker before its end marker.

| Marker | Content |
| --- | --- |
| `METRIC_REPOS` | Public repository count from `GET /users/FebriCahyaa` |
| `METRIC_STARS`, `METRIC_FORKS` | Sums across original public repositories (forks excluded) |
| `METRIC_FOLLOWERS` | Follower count |
| `FLUX_LATEST` | Latest commit on Flux's default branch, as reported by the API; the commit message is HTML-escaped |
| `PROFILE_UPDATED` | Asia/Jakarta time of the last data change |

These are the updater's reliability rules:

- **Metrics failures write nothing.** If the profile or repository request fails, the script exits non-zero and leaves the README untouched, so real metrics are never replaced with zeros.
- **Flux failures keep the last known commit.** A placeholder is written only if the marker is empty.
- **Timestamp-only commits are skipped.** The timestamp changes only when a metric or the Flux commit changed. Unchanged data means no write and no commit.
- **Concurrent edits stop the run.** Before pushing, the workflow rebases onto `origin/main`. Because the updater only edits marker regions, a rebase conflict means someone edited the same lines, and the run fails instead of overwriting the edit.

The README does not show an "online/offline" status. A scheduled workflow only proves when data was refreshed, not whether anyone is available.

## Hero animation

| Asset | Role |
| --- | --- |
| `assets/lottie/terminal-intro.json` | Lottie (Bodymovin 5.7 schema) source: 1200×420, 25 fps, 258 frames (10.32 s), shape layers only |
| `assets/animations/terminal-intro.gif` | README animation for light themes (corners blended onto `#FFFFFF`) |
| `assets/animations/terminal-intro-dark.gif` | README animation for dark themes (corners blended onto `#0D1117`) |
| `assets/profile-hero.svg` | Static poster frame, shown when the viewer prefers reduced motion |
| `assets/fonts/` | JetBrains Mono NL Regular and Bold, subset to the glyphs needed (SIL OFL 1.1, see `OFL.txt`) |

The README chooses between these with a `<picture>` element:

1. `prefers-reduced-motion: reduce` gets the static SVG.
2. `prefers-color-scheme: dark` gets the dark GIF.
3. Everyone else gets the light GIF.

GitHub does not run JavaScript in READMEs, so the README never embeds a Lottie player.

### How the assets relate

`scripts/build_terminal_assets.py` holds one scene description: the window layout, the text, and a deterministic typing timeline. From that scene it:

1. **Writes the Lottie file.** Text is converted to vector outlines from the vendored fonts, so the file does not depend on installed fonts. Typing uses hold keyframes on per-glyph group opacity. Cleared lines use layer opacity keyframes plus out-points. The cursor uses hold keyframes for position and visibility.
2. **Renders both GIFs from that Lottie file** with [rlottie](https://github.com/Samsung/rlottie), Samsung's C++ Lottie renderer, through the `rlottie-python` binding. Each frame is composited onto the theme background. Identical consecutive frames are merged, and every frame is quantized against one shared 255-colour palette with no dithering, so colours don't shimmer between frames. Pillow then writes a GIF that loops forever.
3. **Writes the static SVG directly from the same scene.** The SVG is not rasterized from the Lottie file: it is built from the same glyph outlines and positions, frozen at the poster frame just before `clear` is typed. When rasterized with resvg, it matched that GIF frame to within 2.3/255 mean difference; only 8 of 504,000 pixels differed noticeably.

The session is illustrative and the window says nothing about a live device. It shows `whoami`, then `ls ~/projects`, then `clear`. After `clear`, the screen is identical to the first frame, so the loop is seamless.

### Regenerating

```bash
python3 -m venv .venv && . .venv/bin/activate
python3 -m pip install -r scripts/requirements-assets.txt
python3 scripts/build_terminal_assets.py           # Lottie + SVG + both GIFs
python3 scripts/build_terminal_assets.py --no-gif  # Lottie + SVG only (fontTools)
python3 scripts/build_terminal_assets.py --check   # fail if Lottie/SVG are stale
python3 scripts/validate_assets.py                 # structure, budgets, references
```

The Lottie and SVG output is byte-for-byte deterministic, and CI's `--check` step confirms that. CI does not regenerate the GIFs: rlottie builds can differ slightly in anti-aliasing between platforms. Instead, `validate_assets.py` checks that each GIF:

- is animated and loops forever;
- matches the Lottie dimensions and duration;
- has no frame delay under 20 ms;
- is under the 2 MB budget.

The fonts were subset from the [JetBrains Mono 2.304 release](https://github.com/JetBrains/JetBrainsMono/releases/tag/v2.304) (`JetBrainsMono-2.304.zip`, SHA-256 `6f6376c6ed2960ea8a963cd7387ec9d76e3f629125bc33d1fdcd7eb7012f7bbf`) with:

```bash
pyftsubset JetBrainsMonoNL-<Weight>.ttf \
  --unicodes="U+0020-007E,U+00B7,U+2014,U+276F,U+2713,U+25CF,U+258D,U+2192" \
  --layout-features='' --no-hinting --desubroutinize --name-IDs='*' \
  --output-file=assets/fonts/JetBrainsMonoNL-<Weight>.subset.ttf
```

## One-time repository settings

1. Open **Settings → Actions → General** for `FebriCahyaa/FebriCahyaa`.
2. Under **Workflow permissions**, allow **Read and write permissions**. The refresh workflow needs this to commit `README.md`, and the snake workflow needs it to publish the `output` branch.
3. Run **Generate contribution snake** once if the `output` branch does not yet contain the SVG files.

## Manual refresh from a development machine

```bash
python3 scripts/update_profile.py --check   # offline marker validation
python3 scripts/update_profile.py           # calls the GitHub REST API
```

The second command uses `GH_TOKEN` or `GITHUB_TOKEN` if one is set. Never hard-code a token.

## Retired workflows

These workflows were removed because their responsibilities moved to `profile-refresh.yml` or were intentionally dropped. Their README markers no longer exist.

| Removed | Former role | Outcome |
| --- | --- | --- |
| `Build.yml` | Printed "Build OK" | Replaced by `validate-profile.yml` |
| `stats.yml` | `STATS_*` metrics via a `TOKEN_GITHUB` PAT | Migrated to `METRIC_*` in `profile-refresh.yml` |
| `sync-flux.yml` | `FLUX_COMMIT` every 30 minutes, hard-coded to `main` | Migrated to `FLUX_LATEST`, which uses the API's default branch |
| `update-time.yml` | Committed a timestamp every minute | Dropped; the timestamp now changes only with the data |
| `time.yml` | Clock-based "online/offline" status every 5 minutes | Dropped as misleading |
| `typing-svg.yml` | Rewrote a third-party typing-SVG URL | Replaced by the repository-local hero animation |
| `update-readme.yml` | Injected this repo's own commit hash | Dropped as noise |

## Design notes

- **Visual language:** a graphite macOS-style terminal, off-white text, a restrained violet accent, and mint used only for directory listings and the status dot.
- **Typography:** JetBrains Mono throughout the hero.
- **README layout:** native Markdown and HTML that GitHub keeps after sanitizing (`picture`, `table`, `sub`), with no custom CSS.
- **Third-party widgets:** the `github-readme-stats` and streak cards were removed. They duplicated the first-party metrics, depend on shared public instances, and "top languages by size" is dominated by full kernel source trees.
- **Kept external images:** skill icons (`skillicons.dev`, with alt text listing every icon) and the contribution snake (generated by this repository's own workflow).
