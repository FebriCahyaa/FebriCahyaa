# Profile README automation

This repository uses GitHub Actions to keep the profile data current without requiring a third-party token.

## Workflows

| Workflow | Purpose | Trigger |
| --- | --- | --- |
| `profile-refresh.yml` | Reads public profile/repository data, updates the latest Flux commit, and refreshes the WIB timestamp in `README.md` | Push to `main`/`master`, every 6 hours, or manually |
| `validate-profile.yml` | Checks Python syntax, README replacement markers, and the banner SVG | Push, pull request, or manually |
| `snake.yml` | Generates light/dark contribution snake SVGs on the `output` branch | Daily or manually |
| `.github/dependabot.yml` | Proposes weekly updates for GitHub Actions dependencies | Weekly |

## One-time repository settings

1. Open **Settings → Actions → General** for `FebriCahyaa/FebriCahyaa`.
2. Under **Workflow permissions**, allow **Read and write permissions** so the refresh workflow can commit `README.md` and the snake workflow can publish its output branch.
3. Ensure Actions are enabled for the repository.
4. Run **Actions → Refresh Profile README → Run workflow** once to initialize the numbers and latest Flux commit.
5. Run **Generate contribution snake** once if the `output` branch does not yet contain the SVG files.

No `TOKEN_GITHUB` secret is required. The workflows use the short-lived `github.token` and restrict write permissions to repository contents only. The profile updater uses Python's standard library and does not install dependencies.

## Manual refresh from a development machine

```bash
python3 scripts/update_profile.py --check
python3 scripts/update_profile.py
```

The second command calls the GitHub REST API and updates the README. It uses `GH_TOKEN` or `GITHUB_TOKEN` if one is present in the environment; never hard-code a token in source files.

## Design notes

GitHub sanitizes or ignores arbitrary CSS in README files, so the Material 3 Expressive-inspired treatment is implemented with a custom SVG banner, expressive color accents, rounded visual groupings, tables, badges, and native Markdown. This keeps the design portable in GitHub's profile renderer rather than relying on unsupported embedded styles.

The updater does not manufacture an "online/offline" presence signal. A scheduled workflow only proves when data was refreshed, not whether the account owner is available.

## Migrating from the previous workflow set

When applying this redesign to an existing checkout, delete these superseded workflow files so they do not continue editing the same README fields:

- `.github/workflows/Build.yml`
- `.github/workflows/stats.yml`
- `.github/workflows/sync-flux.yml`
- `.github/workflows/time.yml`
- `.github/workflows/typing-svg.yml`
- `.github/workflows/update-readme.yml`
- `.github/workflows/update-time.yml`

The new `profile-refresh.yml` owns profile metrics, the Flux latest-commit row, and the refresh timestamp. `snake.yml` replaces the old snake workflow at the same path.
