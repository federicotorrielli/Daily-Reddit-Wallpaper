#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import platform
import random
import re
import subprocess
import sys
from configparser import ConfigParser
from pathlib import Path

import praw  # type: ignore
import requests  # type: ignore

# Platform detection constants
PLATFORM = platform.system()
IS_LINUX = PLATFORM == "Linux"
IS_WINDOWS = PLATFORM == "Windows"
IS_DARWIN = PLATFORM == "Darwin"

# Default configuration
DEFAULT_CONFIG = {
    "subreddit": "wallpaper",
    "nsfw": False,
    "time": "all",
    "display": "0",
    "output": "Wallpapers",
    "sort": "hot",
    "limit": 20,
    "random": False,
    "flair": "",
}

# URL regex pattern (compiled once for performance)
URL_STRIP_PATTERN = re.compile(r"\?.*")


def load_config():
    """Load configuration from file or return defaults"""
    config_path = (
        Path.home() / ".config" / "change_wallpaper_reddit.rc"
        if IS_LINUX
        else Path(sys.argv[0]).parent / "change_wallpaper_reddit.rc"
    )

    try:
        conf = ConfigParser(DEFAULT_CONFIG)
        with open(config_path, "r") as stream:
            config_string = f"[root]\n{stream.read()}"
            conf.read_string(config_string)

            # Build config dict with error handling
            config = {}
            config_mappings = [
                ("subreddit", conf.get),
                ("nsfw", conf.getboolean),
                ("display", conf.getint),
                ("time", conf.get),
                ("output", conf.get),
                ("sort", conf.get),
                ("limit", conf.getint),
                ("random", conf.getboolean),
                ("flair", conf.get),
            ]

            for key, getter in config_mappings:
                try:
                    config[key] = getter("root", key)
                except (ValueError, TypeError):
                    config[key] = DEFAULT_CONFIG[key]

            return config
    except IOError:
        return DEFAULT_CONFIG.copy()


config = load_config()


def parse_args():
    """parse args with argparse
    :returns: arguments
    """
    parser = argparse.ArgumentParser(description="Daily Reddit Wallpaper")
    parser.add_argument(
        "-s",
        "--subreddit",
        type=str,
        default=config["subreddit"],
        help="Example: art, getmotivated, wallpapers, ...",
    )
    parser.add_argument(
        "-t",
        "--time",
        type=str,
        default=config["time"],
        help="Time filter for 'top' sort only. Example: hour, day, week, month, year, all",
    )
    parser.add_argument(
        "-n",
        "--nsfw",
        action="store_true",
        default=config["nsfw"],
        help="Enables NSFW tagged posts.",
    )
    parser.add_argument(
        "-d",
        "--display",
        type=int,
        default=config["display"],
        help="Desktop display number on OS X (0: all displays, 1: main display, etc",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=config["output"],
        help="Set the outputfolder in the home directory to save the Wallpapers to.",
    )
    parser.add_argument(
        "--sort",
        type=str,
        default=config["sort"],
        help="Can be one of: hot, top, new. Note: --time only works with 'top'",
    )
    parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=config["limit"],
        help="Set a limit to pull posts",
    )
    parser.add_argument(
        "-r",
        "--random",
        action="store_true",
        default=config["random"],
        help="Randomize witin sort",
    )
    parser.add_argument(
        "-f",
        "--flair",
        type=str,
        default=config["flair"],
        help="Filter by flair text (e.g., 'Desktop', 'Mobile')",
    )
    parser.add_argument("--client-id", type=str, help="Reddit API client ID.")
    parser.add_argument(
        "--api-key", type=str, help="Reddit API client secret (api key)."
    )

    arguments = parser.parse_args()
    return arguments


def get_top_image(sub_reddit, args):
    """Get image link of most upvoted wallpaper of the day
    :sub_reddit: name of the sub reddit
    :args: parsed arguments
    :return: the image link
    """
    # Use generator dispatch for better performance
    if args.sort == "top":
        submissions = sub_reddit.top(time_filter=args.time, limit=args.limit)
    elif args.sort == "new":
        submissions = sub_reddit.new(limit=args.limit)
    else:
        submissions = sub_reddit.hot(limit=args.limit)

    if args.random:
        submissions = sorted(submissions, key=lambda k: random.random())

    for submission in submissions:
        if not args.nsfw and submission.over_18:
            continue

        # Filter by flair if specified
        if args.flair and (
            not submission.link_flair_text
            or args.flair.lower() not in submission.link_flair_text.lower()
        ):
            continue

        url = submission.url
        # Strip trailing arguments (after a '?')
        url = URL_STRIP_PATTERN.sub("", url)

        # Extract file extension
        file_extension = url.split(".")[-1].lower()

        if url.endswith((".jpg", ".png", ".jpeg")):
            return {
                "id": submission.id,
                "subreddit": submission.subreddit.display_name,
                "url": url,
                "type": file_extension,
            }
        # Imgur support
        elif "imgur.com" in url and "/a/" not in url and "/gallery/" not in url:
            if url.endswith("/new"):
                url = url.rsplit("/", 1)[0]
            id_toget = url.rsplit("/", 1)[1].rsplit(".", 1)[0]
            return {
                "id": submission.id,
                "subreddit": submission.subreddit.display_name,
                "url": f"http://i.imgur.com/{id_toget}.jpg",
                "type": "jpg",
            }

    return None


def detect_desktop_environment():
    """Get current Desktop Environment
    :return: environment dict or None
    """
    if not IS_LINUX:
        return None

    # Environment variables for detection
    d_session = os.environ.get("DESKTOP_SESSION")
    xdg_current_desktop = os.environ.get("XDG_CURRENT_DESKTOP")

    # KDE detection
    if os.environ.get("KDE_FULL_SESSION") == "true":
        return {
            "name": "kde",
            "command": (
                "qdbus org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '"
                "var allDesktops = desktops();"
                "for (i=0;i<allDesktops.length;i++) {"
                "    d = allDesktops[i];"
                '    d.wallpaperPlugin = "org.kde.image";'
                '    d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General");'
                '    d.writeConfig("Image", "file:///{save_location}");'
                "}"
                "'"
            ),
        }

    # GNOME detection
    elif os.environ.get("GNOME_DESKTOP_SESSION_ID") or (
        xdg_current_desktop and "GNOME" in xdg_current_desktop.upper()
    ):
        return {
            "name": "gnome",
            "command": (
                "gsettings set org.gnome.desktop.background picture-uri file://{save_location} && "
                "gsettings set org.gnome.desktop.background picture-uri-dark file://{save_location}"
            ),
        }

    # Other desktop environments
    desktop_configs = {
        "Lubuntu": {
            "name": "lubuntu",
            "command": "pcmanfm -w {save_location} --wallpaper-mode=fit",
        },
        "mate": {
            "name": "mate",
            "command": "gsettings set org.mate.background picture-filename {save_location}",
        },
    }

    if d_session in desktop_configs:
        return desktop_configs[d_session]

    # Window manager detection
    if d_session in ("i3", "leftwm", "dwm"):
        return {"name": "i3", "command": "feh --bg-scale {save_location}"}

    # XFCE detection
    try:
        info = subprocess.getoutput("xprop -root _DT_SAVE_MODE")
        if ' = "xfce4"' in info:
            return {
                "name": "xfce",
                "command": (
                    "xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor0/workspace0/last-image "
                    "-s {save_location}"
                ),
            }
    except (OSError, RuntimeError):
        pass

    return None


def set_wallpaper(save_location, args):
    """Set wallpaper based on the operating system"""
    if IS_LINUX:
        desktop_environment = detect_desktop_environment()
        if desktop_environment:
            os.system(
                desktop_environment["command"].format(save_location=save_location)
            )
        else:
            print("Unsupported desktop environment")

    elif IS_WINDOWS:
        try:
            import ctypes

            if hasattr(ctypes, "windll"):
                ctypes.windll.user32.SystemParametersInfoW(20, 0, str(save_location), 3)
            else:
                print("Windows wallpaper setting not available")
        except (ImportError, AttributeError):
            print("Windows wallpaper setting not available")

    elif IS_DARWIN:
        if args.display == 0:
            command = (
                'osascript -e \'tell application "System Events"'
                "set desktopCount to count of desktops"
                "repeat with desktopNumber from 1 to desktopCount"
                "    tell desktop desktopNumber"
                '        set picture to "{save_location}"'
                "    end tell"
                "end repeat"
                "end tell'"
            ).format(save_location=save_location)
        else:
            command = (
                'osascript -e \'tell application "System Events"'
                "set desktopCount to count of desktops"
                "tell desktop {display}"
                '    set picture to "{save_location}"'
                "end tell"
                "end tell'"
            ).format(display=args.display, save_location=save_location)
        os.system(command)


def load_credentials(client_id, api_key):
    """Load credentials from file or command line"""
    if client_id and api_key:
        return client_id, api_key

    # Load from file if not provided
    credentials_path = Path(sys.argv[0]).parent / "credentials.json"
    try:
        with open(credentials_path) as f:
            params = json.load(f)
        return (client_id or params.get("client_id"), api_key or params.get("api_key"))
    except (IOError, json.JSONDecodeError):
        return client_id, api_key


def download_image(url, save_location):
    """Download image with better error handling"""
    try:
        response = requests.get(url, allow_redirects=False, timeout=30)
        response.raise_for_status()

        if save_location.is_file():
            return True

        # Create directories if they don't exist
        save_location.parent.mkdir(parents=True, exist_ok=True)

        # Write to disk
        with open(save_location, "wb") as fo:
            for chunk in response.iter_content(4096):
                fo.write(chunk)

        return True
    except requests.RequestException as e:
        print(f"Error downloading image: {e}")
        return False


def main():
    args = parse_args()
    subreddit = args.subreddit
    save_dir = args.output

    # Load credentials
    client_id, api_key = load_credentials(args.client_id, args.api_key)

    if not (client_id and api_key):
        sys.exit(
            "Error: client_id and api_key not provided. "
            "Please provide them as arguments (--client-id, --api-key) "
            "or in credentials.json."
        )

    # Initialize Reddit API
    try:
        r = praw.Reddit(
            client_id=client_id,
            client_secret=api_key,
            user_agent=f"Get top wallpaper from /r/{subreddit}",
        )
    except Exception as e:
        sys.exit(f"Error initializing Reddit API: {e}")

    # Get top image link
    image = get_top_image(r.subreddit(subreddit), args)
    if not image:
        sys.exit("Error: No suitable images were found, the program is now exiting.")

    # Download and set wallpaper
    save_location = (
        Path.home() / save_dir / f"{subreddit}-{image['id']}.{image['type']}"
    )

    if download_image(image["url"], save_location):
        set_wallpaper(save_location, args)
    else:
        sys.exit("Error: Failed to download image.")


if __name__ == "__main__":
    main()
