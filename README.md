# 🚀 mcScrapiscrape

**mcScrapiscrape** is a premium, multi-threaded video game scraper for [screenscraper.fr](https://www.screenscraper.fr/). Designed specifically for **EmulationStation Desktop Edition (ES-DE)** and other modern frontends, it combines lightning-fast performance with a sleek Terminal User Interface (TUI).

[![Latest Release](https://img.shields.io/github/v/release/ankimetho/mcScrapiscrape?style=flat-square&color=6200ea)](https://github.com/ankimetho/mcScrapiscrape/releases)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue?style=flat-square)](https://www.python.org/downloads/)

---

## ✨ Key Features

- **⚡ Blazing Fast**: Multi-threaded architecture scrapes multiple games simultaneously.
- **🧙 Config Wizard**: Interactive first-time setup guides you through your credentials and folder paths.
- **🔍 Auto-Audit**: At startup, it automatically scans your ROM folders and identifies exactly what media is missing.
- **🎮 Multi-System Support**: Select and scrape entire libraries across dozens of systems in one batch.
- **🛠️ "Fix" Mode**: Smart re-scraping that specifically targets games with missing descriptions, ratings, or media files.
- **📦 Standalone Executable**: No Python? No problem. Download the pre-built `.exe` and start scraping immediately.

---

## 🚀 Getting Started

### 1. The Easy Way (Standalone EXE)

The easiest way to get started on Windows is to download the standalone executable:

1.  Go to the [**Latest Releases**](https://github.com/ankimetho/mcScrapiscrape/releases) page.
2.  Download `mcscrapiscraper.exe`.
3.  Run it! The **Config Wizard** will help you set up your credentials on first launch.

### 2. The Developer Way (Python Source)

If you prefer running from source or are on Linux/macOS:

```bash
# Clone the repository
git clone https://github.com/ankimetho/mcScrapiscrape.git
cd mcScrapiscrape

# Install dependencies
pip install -r requirements.txt

# Launch the TUI
python mcscrapiscrape.py
```

---

## 🎨 TUI Overview

The Terminal User Interface is divided into three logical sections:

1.  **Sidebar (Config)**: Manage your Screenscraper credentials, folder paths, and thread counts.
2.  **Main Console**: Live logs and overall progress mapping across your current batch.
3.  **Audit Center**: Detailed metadata view and multi-system selection list.

### 💡 Pro Tips:

- **Auto-Detect**: Put your ROMs in folders named after ES-DE shortnames (e.g., `snes`, `psx`, `megadrive`). Click **DETECT** to automatically select them.
- **Check Media**: Use the **CHECK** button to perform a deep-scan of your local `gamelist.xml` and media folders to find gaps in your collection.
- **Select All**: Need to scrape everything? Use the **SELECT ALL** toggles in the sidebar for quick system/media selection.

---

## 🔧 CLI Power Usage

For advanced users or automation scripts, `scraper.py` can be used directly:

```bash
python scraper.py \
  --rom-dir "D:\ROMs\snes" \
  --scrape-dir "D:\ES-DE\downloaded_media" \
  --system "snes" \
  --user "my_username" \
  --password "my_password" \
  --devid "my_dev_id" \
  --devpassword "my_dev_password" \
  --systemeid "4" \
  --threads 6
```

---

## 📂 Expected Structure

**mcScrapiscrape** adheres to the standard ES-DE folder hierarchy:

```text
downloaded_media/
└── <system>/
    ├── 3dboxes/
    ├── covers/
    ├── marquees/
    ├── miximages/
    └── screenshots/
```

---

## ☁️ API Requirements

You will need a account on [screenscraper.fr](https://www.screenscraper.fr/).

- **Username/Password**: Your standard login.
- **Developer ID/Password**: Required to use the API at higher speeds. You can request these for free on the Screenscraper website.

---

## ⚖️ License & Disclaimer

Provided "as is" under the MIT License. This tool is not affiliated with Screenscraper.fr or the ES-DE team. Please respect Screenscraper's API limits and terms of service.
