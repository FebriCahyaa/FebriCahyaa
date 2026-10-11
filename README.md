<div align="center">

<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="assets/profile-hero.svg" />
  <source media="(prefers-color-scheme: dark)" srcset="assets/animations/terminal-intro-dark.gif" />
  <img src="assets/animations/terminal-intro.gif" width="100%" alt="A terminal window. An illustrative session runs whoami, which prints: Febri Cahya — Android · Linux · Systems Engineering — Building reliable tools for the layers beneath the interface. Then ls ~/projects lists flux, synthesiscore, hico and ci-build." />
</picture>

<p>
  <a href="#about">About</a> &nbsp;·&nbsp;
  <a href="#featured-work">Work</a> &nbsp;·&nbsp;
  <a href="#toolkit">Toolkit</a> &nbsp;·&nbsp;
  <a href="#activity">Activity</a> &nbsp;·&nbsp;
  <a href="#contact">Contact</a>
</p>

</div>

## About

I'm **Febri Rahmad Cahya**, an independent developer from Indonesia working on the layers beneath the interface: Android system services, Linux, kernels, and the automation that builds and ships them.

I value engineering that is measurable, understandable, and safe to operate: changes that can be explained, verified, and reverted, not tweaks that only look good in a benchmark.

## Current focus

- **Event-driven device state.** Following Android system state through binder and framework callbacks instead of polling `dumpsys`.
- **Kernel work.** Android kernels for Xiaomi garnet (5.10 GKI) and lavender (4.4 / 4.19), and the kernel framework behind [Zairenkai](https://github.com/FebriCahyaa/Zairenkai).
- **Supply-chain safety for root modules.** Checksums, pinned signing certificates, and provenance checks for anything that runs as root.
- **Reproducible CI.** One shared script layer for GitHub Actions, Harness, and local builds.

## Featured work

```text
SynthesisCore ── binder codes, fallback monitor ──▶ Flux ── current profile ──▶ HiCo Thermal
ci-build ────── kernel builds ──▶ garnet (5.10 GKI) · lavender (4.4 / 4.19)
```

<table>
  <tr>
    <td width="50%" valign="top">
      <a href="https://github.com/FebriCahyaa/Flux"><b>Flux</b></a><br />
      Adaptive gaming and battery optimization module for rooted Android. A native C++ daemon follows device state over binder and applies coherent Performance, Performance Lite, Balance, and Powersave profiles.<br />
      <sub>C++ · Magisk, KernelSU, APatch · <a href="https://febricahyaa.github.io/Flux/">project site</a></sub>
    </td>
    <td width="50%" valign="top">
      <a href="https://github.com/FebriCahyaa/SynthesisCore"><b>SynthesisCore</b></a><br />
      Event-driven Android system monitor for root daemons. Runs through <code>app_process</code> and publishes foreground app, power, thermal, and battery state to an atomic, <code>inotify</code>-friendly file.<br />
      <sub>Kotlin · Android 9–17 · used by Flux</sub>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <a href="https://github.com/FebriCahyaa/HiCo"><b>HiCo Thermal</b></a><br />
      A Flux add-on that lifts thermal throttling only while a game runs, then restores the stock thermal stack, with a CPU and battery temperature guard.<br />
      <sub>Root module · thermal layer · requires Flux</sub>
    </td>
    <td width="50%" valign="top">
      <a href="https://github.com/FebriCahyaa/ci-build"><b>ci-build</b></a><br />
      Android kernel CI for the Zairenkai targets. One script layer drives GitHub Actions, Harness, and local builds, and packages each root variant with AnyKernel3.<br />
      <sub>Shell · GitHub Actions · garnet GKI, lavender</sub>
    </td>
  </tr>
</table>

## Toolkit

<table>
  <tr>
    <td><sub>LANGUAGES</sub></td>
    <td><img height="40" src="https://skillicons.dev/icons?i=kotlin,java,cpp,c,py,bash" alt="Kotlin, Java, C++, C, Python, Bash" /></td>
  </tr>
  <tr>
    <td><sub>PLATFORM &amp; BUILD</sub></td>
    <td><img height="40" src="https://skillicons.dev/icons?i=linux,androidstudio,gradle,cmake,ubuntu,docker" alt="Linux, Android Studio, Gradle, CMake, Ubuntu, Docker" /></td>
  </tr>
  <tr>
    <td><sub>WORKFLOW</sub></td>
    <td><img height="40" src="https://skillicons.dev/icons?i=git,github,githubactions,vscode" alt="Git, GitHub, GitHub Actions, VS Code" /></td>
  </tr>
</table>

## Activity

<table>
  <tr>
    <td align="center" width="25%"><b><!-- METRIC_REPOS_START -->23<!-- METRIC_REPOS_END --></b><br /><sub>public repositories</sub></td>
    <td align="center" width="25%"><b><!-- METRIC_STARS_START -->1<!-- METRIC_STARS_END --></b><br /><sub>stars earned</sub></td>
    <td align="center" width="25%"><b><!-- METRIC_FORKS_START -->4<!-- METRIC_FORKS_END --></b><br /><sub>forks received</sub></td>
    <td align="center" width="25%"><b><!-- METRIC_FOLLOWERS_START -->0<!-- METRIC_FOLLOWERS_END --></b><br /><sub>followers</sub></td>
  </tr>
</table>

**Latest in Flux:** <!-- FLUX_LATEST_START --><code>b75491c</code> · <a href="https://github.com/FebriCahyaa/Flux/commit/b75491c73121cc43025ca4df7c67a297db449423">Merge pull request #13 from FebriCahyaa/claude/webroot-native-evolution</a> · <small>2026-09-29</small><!-- FLUX_LATEST_END -->

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/FebriCahyaa/FebriCahyaa/output/github-contribution-grid-snake-dark.svg" />
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/FebriCahyaa/FebriCahyaa/output/github-contribution-grid-snake.svg" />
  <img alt="Contribution graph of the past year, traversed by an animated snake" src="https://raw.githubusercontent.com/FebriCahyaa/FebriCahyaa/output/github-contribution-grid-snake.svg" width="100%" />
</picture>

<sub>Counts come from the GitHub REST API through this repository's own workflow; stars and forks cover original public repositories, not forks. Data last changed <!-- PROFILE_UPDATED_START -->11 Oct 2026, 20:02 WIB<!-- PROFILE_UPDATED_END -->.</sub>

## Contact

The quickest way to reach me is Telegram, [@FebriCahyaaaaa](https://t.me/FebriCahyaaaaa). I'm also on Instagram as [@fbri.chy](https://instagram.com/fbri.chy).

<br />

<div align="center">
  <sub><code>~ ❯ exit</code> &nbsp;·&nbsp; Hero animation rendered from a Lottie source in this repository · <a href="docs/profile-automation.md">How this profile is built</a></sub>
</div>
