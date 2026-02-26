# mcScrapiscrape

`mcScrapiscrape` is a fast, multi-threaded command-line tool written in Python to scrape video game metadata and media from [screenscraper.fr](https://www.screenscraper.fr/). It's specifically designed to format downloaded media and generate `gamelist.xml` files compatible with **EmulationStation Desktop Edition (ES-DE)** and other similar retro gaming frontends.

## Features

- **Multi-threaded Scraping**: Uses concurrent threads to quickly download data and media.
- **Media Downloading**: Downloads various media types (2D boxes, 3D boxes, marquees, mix images, and screenshots) and organizes them into the correct ES-DE folder structure.
- **`gamelist.xml` Generation**: Automatically generates EmulationStation compatible XML files populated with game metadata (Name, Description, Release Date, Developer, Publisher, Genre, Players).
- **Smart Resume**: Scans your ROMs and skips items that already have all their media downloaded, making it perfect for incremental scrapes.

## Requirements

- Python 3.x
- A free account on [screenscraper.fr](https://www.screenscraper.fr/)
- Screenscraper Developer API Credentials (`devid` and `devpassword`)

## Usage

```bash
python scraper.py \
  --rom-dir "/path/to/roms/snes" \
  --scrape-dir "/path/to/ES-DE/downloaded_media" \
  --system "snes" \
  --user "your_screenscraper_username" \
  --password "your_screenscraper_password" \
  --devid "your_dev_id" \
  --devpassword "your_dev_password" \
  --systemeid "4" \
  --gamelist-dir "/path/to/ES-DE/gamelists" \
  --threads 6
```

### Arguments

| Argument         | Description                                                                           | Required | Default            |
| :--------------- | :------------------------------------------------------------------------------------ | :------: | :----------------- |
| `--rom-dir`      | Path to the directory containing your game ROMs.                                      |   Yes    | -                  |
| `--scrape-dir`   | Path to the `downloaded_media` directory for ES-DE.                                   |   Yes    | -                  |
| `--system`       | System name (e.g., `snes`, `megadrive`). Used for folder naming.                      |   Yes    | -                  |
| `--user`         | Your Screenscraper account username.                                                  |   Yes    | -                  |
| `--password`     | Your Screenscraper account password.                                                  |   Yes    | -                  |
| `--devid`        | Screenscraper Developer ID.                                                           |   Yes    | `""`               |
| `--devpassword`  | Screenscraper Developer Password.                                                     |   Yes    | `""`               |
| `--softname`     | Software name registered with Screenscraper.                                          |    No    | `"mcScrapiscrape"` |
| `--gamelist-dir` | Output directory to generate the `gamelist.xml` file.                                 |    No    | `None`             |
| `--systemeid`    | Screenscraper system ID (e.g., 4 for SNES). **Strongly recommended** to avoid errors. |    No    | `None`             |
| `--threads`      | Number of concurrent fetch/download threads.                                          |    No    | `6`                |

## Folder Structure Output

The tool expects and outputs the standard ES-DE directory layout:

```text
downloaded_media/
└── <system>/
    ├── 3dboxes/
    ├── covers/
    ├── marquees/
    ├── miximages/
    └── screenshots/
```

## Tips

- Always pass the `--systemeid` to avoid `HTTP 400 Bad Request` errors.
- Do not set the thread count excessively high; screenscraper.fr enforces rate limits. Usually, the default of `6` threads provides a good balance.

## License

This project is open-source and provided "as is".
