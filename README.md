# Daily Reddit Wallpaper

Automated, scriptable, multi‑platform Reddit wallpaper fetcher.

[![Python](https://img.shields.io/badge/Python->=3.11-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Reddit API](https://img.shields.io/badge/API-Reddit-orange)](https://www.reddit.com/dev/api/)

Fetch and set a fresh wallpaper from any subreddit (default: [/r/wallpaper](https://www.reddit.com/r/wallpaper/)). Runs well as a cron/systemd/Task Scheduler job.

Supported desktops: GNOME, KDE Plasma, MATE, XFCE, LXDE/Lubuntu (pcmanfm), i3/other WM (via `feh`), macOS, Windows.

## Features

- Multiple sort modes: hot, top (with hour/day/week/month/year/all), new
- Flair filtering (`--flair "Desktop"`)
- Randomization within current listing (`--random`)
- NSFW opt‑in (`--nsfw`)
- Config file override (XDG config path on Linux)
- Imgur single‑image link support
- Download dedupe & resumable safe writes
- Works across common Linux DEs, macOS displays, Windows
- Lockfile (`uv.lock`) for reproducible env when using `uv`

## Install / Setup

Pick one method:

### 1. uv (fast, reproducible)

Install uv (one-time):

```bash
curl -Ls https://astral.sh/uv/install.sh | sh
```

Sync dependencies (creates `.venv`):

```bash
uv sync
```

Run:

```bash
uv run change_wallpaper_reddit.py --subreddit art
```

Upgrade (respecting version constraints):

```bash
uv lock --upgrade && uv sync
```

### 2. pip (classic)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python change_wallpaper_reddit.py
```

### 3. pipx (isolated, if published later)

Not yet on PyPI; for now clone & use method 1 or 2. (Future improvement: add console script entry point.)

## Credentials

Create `credentials.json` beside the script:

```jsonc
{
  "client_id": "YOUR_REDDIT_APP_CLIENT_ID",
  "api_key": "YOUR_REDDIT_APP_SECRET"
}
```

Or pass inline:

```bash
uv run change_wallpaper_reddit.py --client-id XXX --api-key YYY
```

Create a Reddit script app at <https://www.reddit.com/prefs/apps>.

## Usage

Basic:

```bash
python change_wallpaper_reddit.py
```

Top of the week from r/art, save somewhere else, random inside top 30:

```bash
python change_wallpaper_reddit.py -s art --sort top --time week -l 30 --random -o MyWallpapers
```

Filter by flair (case-insensitive contains):

```bash
python change_wallpaper_reddit.py --flair "Desktop"
```

macOS main display only:

```bash
python change_wallpaper_reddit.py --display 1
```

Allow NSFW:

```bash
python change_wallpaper_reddit.py --nsfw
```

### All CLI Options

| Flag | Long        | Type | Default    | Description                                          |
| ---- | ----------- | ---- | ---------- | ---------------------------------------------------- |
| -s   | --subreddit | str  | wallpaper  | Subreddit name                                       |
| -t   | --time      | str  | all        | Time filter (top only): hour/day/week/month/year/all |
| -n   | --nsfw      | flag | False      | Enable NSFW posts                                    |
| -d   | --display   | int  | 0          | macOS display (0 = all)                              |
| -o   | --output    | str  | Wallpapers | Relative directory inside home to store images       |
|      | --sort      | str  | hot        | hot/top/new                                          |
| -l   | --limit     | int  | 20         | Listing fetch limit                                  |
| -r   | --random    | flag | False      | Shuffle the fetched list before picking              |
| -f   | --flair     | str  | (empty)    | Filter by flair substring                            |
|      | --client-id | str  |            | Override Reddit client id                            |
|      | --api-key   | str  |            | Override Reddit client secret                        |

Exit codes: 0 success, non‑zero on failure (missing creds, no image, network error).

## Configuration File

Optional file (Linux): `~/.config/change_wallpaper_reddit.rc`  
On Windows/macOS (fallback): same directory as script.

Example:

```ini
subreddit=wallpaper
sort=top
time=day
limit=40
random=true
nsfw=false
flair=Desktop
output=Wallpapers
display=0
```

CLI flags override file values.

## Scheduling

### systemd user timer (recommended on modern Linux)

`~/.config/systemd/user/reddit-wallpaper.service`:

```ini
[Unit]
Description=Update Reddit wallpaper

[Service]
Type=oneshot
WorkingDirectory=%h/path/to/Daily-Reddit-Wallpaper
ExecStart=%h/path/to/Daily-Reddit-Wallpaper/.venv/bin/python change_wallpaper_reddit.py --sort top --time day
```

`~/.config/systemd/user/reddit-wallpaper.timer`:

```ini
[Unit]
Description=Run wallpaper updater daily

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

Enable:

```bash
systemctl --user daemon-reload
systemctl --user enable --now reddit-wallpaper.timer
```

### Cron (legacy)

Daily at 09:00:

```cron
0 9 * * * /usr/bin/env bash -lc 'cd "$HOME/path/to/Daily-Reddit-Wallpaper" && uv run change_wallpaper_reddit.py --sort top --time day'
```

Hourly:

```cron
0 * * * * /usr/bin/env bash -lc 'cd "$HOME/path/to/Daily-Reddit-Wallpaper" && uv run change_wallpaper_reddit.py'
```

### Windows Task Scheduler

Create a basic task -> trigger (daily / logon) -> Action: Start a Program:

Program/script:

```text
python
```

Arguments:

```text
"C:\\path\\to\\change_wallpaper_reddit.py" --sort top --time day
```

Or use a virtualenv's python path.

## Desktop Environment Notes

- KDE: requires `qdbus` (usually present)
- i3/WM: needs `feh` installed (`sudo apt install feh`)
- XFCE: uses `xfconf-query`
- macOS: uses AppleScript, per-display if `--display` set
- Windows: standard `SystemParametersInfoW`

## Troubleshooting

| Issue                          | Suggestion                                                            |
| ------------------------------ | --------------------------------------------------------------------- |
| No images found                | Increase `--limit`, relax flair, allow NSFW if appropriate            |
| Credentials error              | Regenerate Reddit app secret; confirm JSON keys                       |
| Wallpaper not changing (Linux) | Ensure DE supported & required tools installed (`feh`, `qdbus`, etc.) |
| Cron uses old Python           | Use full path to venv python or switch to systemd timer               |

Run verbose network test:

```bash
python - <<'PY'
import requests;print(requests.get('https://www.reddit.com/.json',headers={'User-Agent':'test'}).status_code)
PY
```

## Contributing

Small focused PRs welcome: docs, new DE support, packaging (entry point), tests. Open an issue first for bigger changes. Style: keep functions small & explicit.

## License

MIT. See `LICENSE`.

---

Made better with automation & reproducibility (`uv`).
