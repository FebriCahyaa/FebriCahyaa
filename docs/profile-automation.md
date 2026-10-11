# How this profile is built

This repository is the `FebriCahyaa` GitHub profile. It has three moving parts:

- **Generated assets**: four terminal-style animations (each a Lottie source plus GIFs rendered from it), the devices card, and the social buttons, all committed to the repository.
- **Live cards**: clock and location, languages, and commit streak SVGs, regenerated every 30 minutes and published to the `output` branch.
- **Profile automation**: GitHub Actions workflows that keep a few README values current.

The README is organised as collapsible `<details>` sections, each with an `<h2>` heading inside its `<summary>`. Only the hero, the clock card, and `~/about` are visible on load. GitHub's stylesheet renders a heading inside a summary inline (`display: inline-block`), so each section reads as a single clickable line.

Everything is regenerated or validated by scripts in `scripts/`.

## Workflows

There is one writer for `README.md` and one publisher for the `output` branch. Every other workflow is read-only.

| Workflow | Responsibility | Writes | Trigger |
| --- | --- | --- | --- |
| `profile-refresh.yml` | Refreshes profile metrics, the latest Flux commit, and the "data last changed" timestamp | `README.md` on `main`, only when the data changed | Every 6 hours, on pushes that touch the README or updater, or manually |
| `validate-profile.yml` | Compiles scripts, checks README markers, validates assets and workflow writers, checks generated assets for drift, and runs unit tests | Nothing (`contents: read`) | Push and pull request to `main`, or manually |
| `profile-cards.yml` | Builds the clock, languages, and streak cards (`scripts/build_cards.py`) and the contribution snake | The orphan `output` branch only (force-replaced, so it keeps no history), never `main` | Cards every 30 minutes; snake daily at 08:30 WIB, or when missing; on pushes that touch the card code; or manually |
| `.github/dependabot.yml` | Proposes GitHub Actions version updates | Pull requests | Weekly |

All workflows use the short-lived `github.token` with least-privilege `permissions`. No personal access token or `TOKEN_GITHUB` secret is needed. Each job has a `timeout-minutes` and a concurrency group.

`scripts/validate_assets.py` enforces this layout in CI. It fails if:

- any workflow other than `profile-refresh.yml` can commit `README.md`;
- any workflow other than `profile-cards.yml` publishes the `output` branch;
- a workflow targets a retired marker;
- a workflow is scheduled more often than every 30 minutes;
- the README references an `output`-branch file that the workflow does not produce.

The `output` branch has a single publisher because it is force-replaced on every run. Two publishers would erase each other's files: the old `snake.yml` would have deleted the cards, and vice versa. That's why the snake moved into `profile-cards.yml`. Each run first restores the files already published, so the snake only regenerates once a day.

## Live cards

`scripts/build_cards.py` uses the same engine and type as the committed assets. It needs `fontTools` and only reads public GitHub API data.

| Card | Data | Notes |
| --- | --- | --- |
| `clock.svg` | Location from the GitHub profile (`Indonesia`) and the Asia/Jakarta local time at generation | GitHub cannot show a live clock: the card shows the time of the last refresh and says so |
| `languages.svg` | `GET /repos/{repo}/languages` for every original public repository | Each repository is weighted equally, so the 1.4 GB kernel trees don't drown out every other project the way a byte count would |
| `streak.svg` | Commits authored by `FebriCahyaa` on the default branch of each original repository, bucketed by day in WIB | Shows current and longest streak, commits in the last 365 days, and a 30-week activity grid |

The streak is a commit streak rather than GitHub's contribution streak for one reason. When this was built (12 Oct 2026), GitHub's contribution calendar reported **0 contributions in the last year** for this account, even though the commits are linked to it. That is also why the contribution snake looks nearly empty.

A card whose data cannot be fetched keeps its previously published copy. The run fails only when a card has neither fresh data nor a previous copy.

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

## Animations and generated assets

Four animated scenes appear in the README. Each is described once in `scripts/build_assets.py`:

| Scene | Where | What it shows |
| --- | --- | --- |
| `terminal-intro` | Hero | An illustrative session: `whoami`, then `ls ~/projects`, then `clear` |
| `kernel-ci` | `~/now` | An illustrative ci-build run of the real targets through resolve → patch → toolchain → compile → AnyKernel3 → release |
| `flux-loop` | `~/work` | A simulated Flux profile loop: device state → fluxd → applied profile, with profile switches driven by game and thermal events |
| `terminal-exit` | Footer | The session closing: `exit`, `logout`, `[Process completed]` |

None of these show a live device. Their window titles and status bars say "illustrative" or "simulated".

Each scene `<name>` produces four files:

| File | Role |
| --- | --- |
| `assets/lottie/<name>.json` | Lottie (Bodymovin 5.7 schema) source, built from shape layers only |
| `assets/animations/<name>.gif` | README animation for light themes (corners blended onto `#FFFFFF`) |
| `assets/animations/<name>-dark.gif` | README animation for dark themes (corners blended onto `#0D1117`) |
| `assets/static/<name>.svg` | Static poster frame, shown when the viewer prefers reduced motion |

The supporting files are:

| Path | Contents |
| --- | --- |
| `assets/cards/devices.svg` | Devices card: original vector illustrations of the Redmi Note 13 Pro 5G, Redmi Note 7, and iPhone 12 with their specifications. A slow CSS light sweep animates the phones and is disabled under `prefers-reduced-motion` |
| `assets/social/*.svg` | Static contact buttons, generated the same way |
| `assets/fonts/` | JetBrains Mono NL Regular and Bold, subset to the glyphs needed (SIL OFL 1.1, see `OFL.txt`) |
| `assets/icons/` | Brand icons for Telegram, Instagram, and GitHub, copied unmodified from [Simple Icons](https://simpleicons.org) 16.31.0 (CC0 1.0) |

The README chooses between the files with a `<picture>` element:

1. `prefers-reduced-motion: reduce` gets the static SVG.
2. `prefers-color-scheme: dark` gets the dark GIF.
3. Everyone else gets the light GIF.

GitHub does not run JavaScript in READMEs, so the README never embeds a Lottie player.

### How the assets relate

The scripts are split in two:

- **`scripts/assetkit.py`** is the engine. A scene is a list of elements (text, rectangles, circles) whose opacity, offset, and width are keyframed tracks. Hold keys make discrete steps, such as typing or a cursor blink; linear keys make fades and motion.
- **`scripts/build_assets.py`** holds the scenes and the command-line interface.

From each scene the engine does three things:

1. **Writes the Lottie file.** Text is converted to vector outlines from the vendored fonts, so the file does not depend on installed fonts. Each element becomes one shape layer.
2. **Renders both GIFs from that Lottie file** with [rlottie](https://github.com/Samsung/rlottie), Samsung's C++ Lottie renderer, through the `rlottie-python` binding:
   - Each frame is composited onto the theme background.
   - rlottie sometimes shifts the whole canvas by a few colour levels between frames. Any pixel whose change is at most 8/255, compared with the previous output frame, keeps its previous value, so frames encode as small deltas instead of full canvases.
   - Identical consecutive frames are merged.
   - Every frame is quantized against one shared palette with no dithering, so colours don't shimmer.
   - Pillow writes a GIF that loops forever.
3. **Writes the static SVG directly from the same scene**, evaluated at the scene's poster frame. The SVG is not rasterized from the Lottie file. For the hero, a resvg rendering of the SVG matched the corresponding GIF frame to within 2.3/255 mean difference.

Some motion is deliberately sampled rather than continuous, to keep GIFs small:

- **`flux-loop`:** packets step at 12.5 fps, and the headroom bar updates every 0.48 s, like a polled metric.
- **`kernel-ci`:** running stages blink on a shared clock.

Every scene returns to its first frame at the end of the loop. The one exception is the flowing packets in `flux-loop`, which continue their motion across the loop boundary.

### Regenerating

```bash
python3 -m venv .venv && . .venv/bin/activate
python3 -m pip install -r scripts/requirements-assets.txt
python3 scripts/build_assets.py                  # Lottie + SVG + GIFs for every scene
python3 scripts/build_assets.py --only kernel-ci # one scene
python3 scripts/build_assets.py --no-gif         # Lottie + SVG only (fontTools)
python3 scripts/build_assets.py --check          # fail if Lottie/SVG are stale
python3 scripts/validate_assets.py               # structure, budgets, references
GH_TOKEN=... python3 scripts/build_cards.py --out dist  # live cards, as the workflow does
```

The Lottie and SVG output is byte-for-byte deterministic, and CI's `--check` step confirms that. CI does not regenerate the GIFs: rlottie builds can differ slightly in anti-aliasing between platforms. Instead, `validate_assets.py` checks every scene. For each one it checks that:

- the Lottie source, static SVG, and GIFs agree on dimensions;
- each GIF is animated, loops forever, and matches the Lottie duration;
- no GIF frame delay is under 20 ms;
- each GIF is under the 2 MB budget;
- no generated file exists without a Lottie source.

The fonts were subset from the [JetBrains Mono 2.304 release](https://github.com/JetBrains/JetBrainsMono/releases/tag/v2.304) (`JetBrainsMono-2.304.zip`, SHA-256 `6f6376c6ed2960ea8a963cd7387ec9d76e3f629125bc33d1fdcd7eb7012f7bbf`) with:

```bash
pyftsubset JetBrainsMonoNL-<Weight>.ttf \
  --unicodes="U+0020-007E,U+00B7,U+2014,U+276F,U+2713,U+25CF,U+258D,U+2192" \
  --layout-features='' --no-hinting --desubroutinize --name-IDs='*' \
  --output-file=assets/fonts/JetBrainsMonoNL-<Weight>.subset.ttf
```

## One-time repository settings

1. Open **Settings → Actions → General** for `FebriCahyaa/FebriCahyaa`.
2. Under **Workflow permissions**, allow **Read and write permissions**. The refresh workflow needs this to commit `README.md`, and the profile-cards workflow needs it to publish the `output` branch.
3. Run **Profile cards** once if the `output` branch does not yet contain the cards and snake.

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
| `snake.yml` | Published the snake with `force_orphan` | Merged into `profile-cards.yml`, which is now the only `output`-branch publisher |

## Design notes

- **Visual language:** graphite macOS-style terminal windows, off-white text, and a restrained violet accent. Mint marks success: directory listings, completed stages, and the status dot. Coral appears only when thermal headroom is low.
- **Typography:** JetBrains Mono in every generated asset.
- **Navigation:** section headings are terminal paths (`~/about`, `~/now`, …). GitHub turns them into plain `#about`-style anchors.
- **README layout:** native Markdown and HTML that GitHub keeps after sanitizing (`picture`, `table`, `sub`), with no custom CSS.
- **Third-party widgets:** the `github-readme-stats` and streak cards were removed. They duplicated the first-party metrics, depend on shared public instances, and "top languages by size" is dominated by full kernel source trees.
- **Kept external images:** skill icons (`skillicons.dev`, with alt text listing every icon) and the contribution snake (generated by this repository's own workflow).
