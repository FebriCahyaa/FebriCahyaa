<div align="center">

<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="assets/static/terminal-intro.svg" />
  <source media="(prefers-color-scheme: dark)" srcset="assets/animations/terminal-intro-dark.gif" />
  <img src="assets/animations/terminal-intro.gif" width="100%" alt="A terminal window. An illustrative session runs whoami, which prints: Febri Cahya — Android · Linux · Systems Engineering — Building reliable tools for the layers beneath the interface. Then ls ~/projects lists flux, synthesiscore, hico and ci-build." />
</picture>

<img src="https://raw.githubusercontent.com/FebriCahyaa/FebriCahyaa/output/clock.svg" width="100%" alt="Location and local time in Indonesia (Asia/Jakarta, WIB), refreshed every 30 minutes by GitHub Actions" />

<sub>Sections below are collapsed: select a heading to open it.</sub>

</div>

<details open>
<summary><h2>~/about</h2></summary>

I'm **Febri Rahmad Cahya**, an independent developer from Indonesia working on the layers beneath the interface: Android system services, Linux, kernels, and the automation that builds and ships them.

I value engineering that is measurable, understandable, and safe to operate: changes that can be explained, verified, and reverted, not tweaks that only look good in a benchmark.

</details>

<details>
<summary><h2>~/now</h2> &nbsp;<sub>current focus · kernel CI</sub></summary>

- **Event-driven device state.** Following Android system state through binder and framework callbacks instead of polling `dumpsys`.
- **Kernel work.** Android kernels for Xiaomi garnet (5.10 GKI) and lavender (4.4 / 4.19), and the kernel framework behind [Zairenkai](https://github.com/FebriCahyaa/Zairenkai).
- **Supply-chain safety for root modules.** Checksums, pinned signing certificates, and provenance checks for anything that runs as root.
- **Reproducible CI.** One shared script layer for GitHub Actions, Harness, and local builds.

<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="assets/static/kernel-ci.svg" />
  <source media="(prefers-color-scheme: dark)" srcset="assets/animations/kernel-ci-dark.gif" />
  <img src="assets/animations/kernel-ci.gif" width="100%" alt="An illustrative ci-build run: garnet-gki (5.10 GKI), lavender-4.4 and lavender-4.19 move through resolve, patch, toolchain, compile, AnyKernel3 and release, ending with a kernel image and an AnyKernel3 zip per variant." />
</picture>

</details>

<details>
<summary><h2>~/work</h2> &nbsp;<sub>Flux · SynthesisCore · HiCo Thermal · ci-build</sub></summary>

<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="assets/static/flux-loop.svg" />
  <source media="(prefers-color-scheme: dark)" srcset="assets/animations/flux-loop-dark.gif" />
  <img src="assets/animations/flux-loop.gif" width="100%" alt="A simulated view of Flux: device state flows from the binder monitor, with SynthesisCore as fallback, into fluxd, which applies a profile through flux_profiler while HiCo Thermal follows it. The profile moves from Balance to Performance when a game is in the foreground, to Performance Lite when thermal headroom runs low, and back to Balance when the game exits." />
</picture>

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

</details>

<details>
<summary><h2>~/devices</h2> &nbsp;<sub>Redmi Note 13 Pro 5G · Redmi Note 7 · iPhone 12</sub></summary>

<img src="assets/cards/devices.svg" width="100%" alt="Devices: Redmi Note 13 Pro 5G (garnet) with Snapdragon 7s Gen 2, 6.67-inch 120 Hz AMOLED, 200 MP camera and 5100 mAh battery; Redmi Note 7 (lavender) with Snapdragon 660, 6.3-inch LCD, 48 MP camera and 4000 mAh battery; iPhone 12 with A14 Bionic, 6.1-inch Super Retina XDR OLED and dual 12 MP cameras." />

</details>

<details>
<summary><h2>~/toolkit</h2> &nbsp;<sub>languages · tools</sub></summary>

<img src="https://raw.githubusercontent.com/FebriCahyaa/FebriCahyaa/output/languages.svg" width="100%" alt="Language mix across original public repositories, each repository weighted equally, refreshed by GitHub Actions" />

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

</details>

<details>
<summary><h2>~/activity</h2> &nbsp;<sub>streak · metrics · latest commit · snake</sub></summary>

<img src="https://raw.githubusercontent.com/FebriCahyaa/FebriCahyaa/output/streak.svg" width="100%" alt="Commit streak: current and longest streak, commits in the last year, and a 30-week activity grid, refreshed by GitHub Actions" />

<table>
  <tr>
    <td align="center" width="25%"><b><!-- METRIC_REPOS_START -->26<!-- METRIC_REPOS_END --></b><br /><sub>public repositories</sub></td>
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

<sub>Cards and counts come from the GitHub REST API through this repository's own workflows. Stars and forks cover original public repositories, not forks; the streak counts commits I authored on their default branches. Metrics last changed <!-- PROFILE_UPDATED_START -->29 Oct 2026, 20:16 WIB<!-- PROFILE_UPDATED_END -->.</sub>

</details>

<details>
<summary><h2>~/contact</h2> &nbsp;<sub>Telegram · Instagram · GitHub</sub></summary>

The quickest way to reach me is Telegram.

<p>
  <a href="https://t.me/FebriCahyaaaaa"><img src="assets/social/telegram.svg" height="52" alt="Telegram @FebriCahyaaaaa" /></a>
  <a href="https://instagram.com/fbri.chy"><img src="assets/social/instagram.svg" height="52" alt="Instagram @fbri.chy" /></a>
  <a href="https://github.com/FebriCahyaa"><img src="assets/social/github.svg" height="52" alt="GitHub @FebriCahyaa" /></a>
</p>

</details>

<br />

<div align="center">

<picture>
  <source media="(prefers-reduced-motion: reduce)" srcset="assets/static/terminal-exit.svg" />
  <source media="(prefers-color-scheme: dark)" srcset="assets/animations/terminal-exit-dark.gif" />
  <img src="assets/animations/terminal-exit.gif" width="75%" alt="The terminal closes: exit, logout, Saving session...completed., [Process completed]." />
</picture>

<sub>Terminal animations are rendered from Lottie sources in this repository · <a href="docs/profile-automation.md">How this profile is built</a></sub>

</div>
