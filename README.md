# mcScrapiscrape

**mcScrapiscrape** is a multi-threaded video game metadata and media scraper for [ScreenScraper.fr](https://www.screenscraper.fr/), built for use with [EmulationStation Desktop Edition (ES-DE)](https://es-de.org/) and compatible frontends.

It provides a Terminal User Interface (TUI) powered by [Textual](https://github.com/Textualize/textual), as well as a standalone command-line scraper for scripted or headless workflows.

[![Latest Release](https://img.shields.io/github/v/release/ankimetho/mcScrapiscrape?style=flat-square&color=6200ea)](https://github.com/ankimetho/mcScrapiscrape/releases)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue?style=flat-square)](https://www.python.org/downloads/)

---

## Features

- **Multi-threaded scraping** — configurable thread count for parallel downloads of metadata and media assets.
- **Configuration wizard** — guided first-run setup for API credentials and directory paths.
- **Automatic system detection** — scans ROM directories and maps them to ScreenScraper system IDs via a definitive `system_mapping.json`.
- **Media audit** — inspects local `gamelist.xml` files and media folders to identify missing assets before scraping.
- **Fix mode** — selectively re-scrapes only games with incomplete metadata or missing media.
- **Save/load configuration** — persists all settings (credentials, paths, selected systems, media types) to `config.json`.
- **Directory picker** — built-in file browser for selecting ROM and media directories.
- **Standalone executable** — pre-built `.exe` available for Windows users who do not have a Python environment.

---

## Installation

### Standalone Executable (Windows)

1. Download the latest release from the [Releases](https://github.com/ankimetho/mcScrapiscrape/releases) page.
2. Run `mcscrapiscrape.exe`. The configuration wizard will launch on first startup.

### From Source

Requires Python 3.8 or later.

```bash
git clone https://github.com/ankimetho/mcScrapiscrape.git
cd mcScrapiscrape
pip install -r requirements.txt
python mcscrapiscrape.py
```

---

## User Interface

The TUI is organized into three panels:

| Panel | Purpose |
|-------|---------|
| **Config (left)** | API credentials, directory paths, thread count, and scrape/fix/stop controls. |
| **Console (center)** | Live log output, per-thread activity indicators, and overall progress bar. |
| **Selection (right)** | System selection list, media type selection, and utility actions (Detect, Check, Save, Load). |

### Workflow

1. Enter your ScreenScraper credentials and configure your ROM and media directories.
2. Click **DETECT** to automatically identify systems present in your ROM directory.
3. Select the desired media types (box art, screenshots, marquees, videos, etc.).
4. Click **CHECK** to audit existing media and identify gaps.
5. Click **START** to begin scraping, or **FIX** to re-scrape only incomplete entries.

---

## Command-Line Interface

The `scraper.py` module can be invoked directly for scripted or automated use:

```bash
python scraper.py \
  --rom-dir "/path/to/roms/snes" \
  --scrape-dir "/path/to/downloaded_media" \
  --system "snes" \
  --user "username" \
  --password "password" \
  --devid "dev_id" \
  --devpassword "dev_password" \
  --systemeid "4" \
  --threads 6
```

Run `python scraper.py --help` for a full list of available arguments.

---

## Directory Structure

mcScrapiscrape follows the standard ES-DE media directory layout:

```
downloaded_media/
└── <system>/
    ├── 3dboxes/
    ├── covers/
    ├── marquees/
    ├── miximages/
    ├── screenshots/
    └── videos/
```

ROM directories are expected to be organized by system shortname (e.g., `snes`, `megadrive`, `psx`), matching the ES-DE naming convention.

---

## API Requirements

A registered account on [ScreenScraper.fr](https://www.screenscraper.fr/) is required.

- **Username / Password** — standard ScreenScraper login credentials.
- **Developer ID / Password** — required for API access. These can be requested at no cost through the ScreenScraper website.

---

## License

This project is provided under the [MIT License](LICENSE).

mcScrapiscrape is not affiliated with ScreenScraper.fr or the ES-DE project. Please respect ScreenScraper's API usage limits and terms of service.
