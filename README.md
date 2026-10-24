# Local Image Studio

Generate and edit images on your Apple Silicon Mac with **FLUX.2 Klein 4B**, **MFLUX**, and **MLX**. Use up to four reference images, add editable lettering (including Hebrew), and download A4 PNG/PDF prints. Inference stays on your Mac; no API key or cloud subscription.

## Quick start

Requires an **Apple Silicon Mac**, macOS with Metal support, and Git/Python 3 available from Apple's Command Line Tools. Tested on an **M5 Pro with 64 GB unified memory**. Allow **30 GB free disk space**. Other Apple Silicon machines may run more slowly; around 13 GB peak GPU allocation was measured here, which is not the total system memory requirement.

```bash
git clone https://github.com/adirothbuilds/local-image-studio.git
cd local-image-studio
./studio.sh setup
./studio.sh run
```

Open [localhost:7860](http://127.0.0.1:7860). Stop with **Ctrl+C**.

**After installation, launching takes seconds.** First setup downloads a local uv binary, Python 3.12, locked packages, and approximately **15 GiB of model weights**. That download cannot be promised in under a minute. Setup is resumable: rerun the same command after an interruption. Nothing is installed globally and shell profiles are untouched.

## Create and edit

1. Describe your picture. **English scene prompts are the reliable choice for this model.** Direct Hebrew prompting was inconsistent in testing; there is no automatic translation.
2. Optionally choose up to four PNG/JPEG/WebP references and explain what to use from each. Each file: up to 10 MB / 25 megapixels. References guide the result but do not guarantee an exact copy. Transparent references are composited on white.
3. Choose portrait, landscape, square, or quick draft. Square artwork selects a **20 × 20 cm square print**; you can also choose A4 separately. Four inference steps is the default. Leave the seed blank for a new result.
4. Add an optional message. **Styled exact text** uses real glyphs, decorative fills and outlines; this is the preferred mode for Hebrew. **Exact text** uses plain glyphs. **AI lettering** asks the model to paint words into the scene and may misspell them.
5. Drag exact lettering on the canvas. Under the canvas, choose **Writing style** (classic, rounded, or handwritten) and **Letter finish** (ice, ribbon, gold), set **Font size · points** (blank for automatic fitting), and choose **Outline thickness** (including None) and an optional outline color. The **Lettering & banner scale** slider scales the whole layer. Choose **Letter background** (decorative banner or transparent), enable **Custom letter color** to choose any color while retaining the style, then **Apply lettering changes**. Uncheck custom color to restore the theme palette. Layer scaling previews immediately; Apply updates the writing style, font size, outline, color, placement, and background to the downloadable files. Wording and lettering style can also be changed in the form without generating another picture.

AI lettering is baked into the original picture, so it cannot be dragged or spell-corrected afterward. Generate a clean picture and use exact lettering when wording must be correct. Hebrew mixed with numbers is supported; Arabic shaping is unavailable in the tested Pillow build. Classic text uses macOS fonts. Rounded and handwritten text use bundled Varela Round and Gveret Levin fonts, both with Hebrew/English support and their SIL Open Font License notices.

Each job saves its original, cleaned references, settings, model revision, logs, A4 exports, and editable layers under `outputs/<job-id>/`. One image generates at a time. Closing the browser does not stop generation; stopping the server does.

**Print:** The 20 × 20 cm option exports 2362 × 2362 pixels at approximately 300 DPI and an exact 200 × 200 mm PDF. Use zero margin for edge-to-edge artwork. A4 is 2480 × 3508 pixels (landscape swaps dimensions), with an exact 210 × 297 mm PDF page. Artwork fits without cropping. Resizing to 300 DPI does not add real detail. Print the PDF at **100% / actual size**. RGB output has no printer-specific color profile.

## Configuration and home Wi-Fi

Setup creates **`.env`** with owner-only permissions and a generated password. Available settings are documented in [.env.example](.env.example). Environment variables override the file; the file is parsed as data, never executed as shell commands. Restart after changing it.

```bash
./studio.sh run --lan
```

Open the address printed in Terminal on another device on the same home network. Username: **`studio`**. Password: **`STUDIO_PASSWORD` in `.env`**. Everyone signed in shares all image history and one generation slot. You can set `STUDIO_LAN=1` for LAN access by default, `STUDIO_IP=auto` or a specific private IPv4 address, and `STUDIO_PORT=7860` or another unprivileged port. LAN passwords require at least 16 characters.

Local mode binds to loopback; LAN mode binds to the chosen private interface. Keep your Mac awake. Allow Python incoming connections if macOS asks; guest Wi-Fi may block access between devices. This uses HTTP for trusted home networks. Do not expose it through router port forwarding. Sessions expire after 12 hours and on server restart.

## Terminal and background modes

```bash
# Website attached to your terminal
./studio.sh run

# Generate directly in the terminal; stop the website first
./studio.sh generate "A watercolor mountain landscape at sunrise" --seed 42
./studio.sh generate "A cheerful birthday illustration" --text "יום הולדת שמח"
# Optional: --preset draft|portrait|landscape|square, --steps 4, --reference /path/image.png
# Use --print-size square20 for an exact 20 × 20 cm print.
# Use --text-color "#E66CA6" for pink lettering with the icy style.

# macOS background website; reads the same .env
./studio.sh service start
./studio.sh service status
./studio.sh service stop
```

The background mode is a **launchd service for your current login session**. It survives closing Terminal, restarts after a failure, and stops at logout. It does not install a login item or write a plist outside this folder. Start it again after logging in. Stop terminal mode before starting service mode. Logs are `logs/service.log` and `logs/service-error.log`. Restart the service after changing `.env`; stop it before moving this folder or cleaning its runtime.

## Benchmarks

On the tested M5 Pro / 64 GB, **832 × 1184** generation took roughly **11 seconds per image**, including a new worker process, model loading and A4 exports. See [measured results and methodology](docs/BENCHMARKS.md), including raw machine-readable reports. These are measurements on one machine, not performance guarantees.

```bash
./studio.sh benchmark --runs 3 --preset portrait
```

Stop the website first. The command runs one warm-up and three measured images with a generic fixed prompt, records hardware/software versions, revision, seeds, wall time and peak MLX GPU memory, and writes `logs/benchmark-<timestamp>/report.json`. Images stay local. Compare the same preset, steps, model revision and package versions across machines.

## Maintenance

```bash
./studio.sh doctor
./studio.sh test
./studio.sh download        # Resume/repair the pinned model download
./studio.sh clean cache     # Preview only
./studio.sh clean outputs   # Preview deletion of all artwork and references
./studio.sh clean all       # Preview all runtime/model/output/cache data
./studio.sh clean all --yes # Permanently delete the previewed data
```

Stop terminal/service mode first. Cleanup refuses to run while an operation holds the project lock. Groups: `cache`, `models`, `outputs`, `runtime`, `all`. `runtime` keeps models and artwork. `all` also deletes `.env`, including the LAN password. Code and documentation remain; deleting the folder afterward removes the project completely. Cleanup never follows leaf symlinks or symlinked ancestors of deletion targets.

If an image fails, inspect its **Generation log** or `outputs/<job-id>/generation.log`. For memory pressure, close other heavy apps or use quick draft/fewer references. Generation never silently falls back to the cloud. After moving the project, recreate its environment with `./studio.sh clean runtime --yes` and `./studio.sh setup` (virtual environments are not relocatable).

## Project layout

```text
studio.sh             One command for setup, run, service, CLI, benchmark, cleanup
studio/               Python application and local browser assets in static/
scripts/              Bootstrap, environment, model downloader, cleanup helpers
tests/                API/authentication, print, lettering and cleanup regressions
docs/                 Benchmark methodology, results and dependency notices
.github/              CI and owner review policy
.env                  Local settings/password (ignored)
.runtime/ .venv/      Local uv, Python, service plist and packages (ignored)
.cache/ models/       Caches and model weights (ignored)
outputs/ logs/        Personal images, job records and diagnostics (ignored)
```

Inference uses local weights with Hugging Face offline mode. Downloads need internet during setup. The browser loads no external scripts/fonts; application telemetry is disabled. macOS and browsers may keep their own system caches/history independently.

## License and contributions

Application code is [MIT licensed](LICENSE). Model weights are downloaded separately under **Apache-2.0**; dependencies retain their own licenses, including python-bidi's LGPL terms. Model weights and proprietary system fonts are not included. Bundled open fonts retain their separate OFL licenses. See [third-party notices](docs/THIRD_PARTY.md).

Proposed changes go through pull requests and require the repository owner's review before merging to `main`. See [CONTRIBUTING.md](CONTRIBUTING.md). Public forks and pull requests remain possible; they do not grant write access to this repository.
