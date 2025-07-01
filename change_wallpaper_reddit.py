#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import ctypes
import json
import os
import platform
import random
import re
import subprocess
import sys
from collections import defaultdict
from configparser import ConfigParser
from pathlib import Path

import praw
import requests


def load_config():
    default = defaultdict(str)
    default["subreddit"] = "wallpaper"
    default["nsfw"] = False
    default["time"] = "all"
    default["display"] = "0"
    default["output"] = "Pictures/Wallpapers"
    default["sort"] = "hot"
    default["limit"] = 20
    default["random"] = False

    # If Linux, use config_path_linux otherwise use config_path_windows
    config_path_linux = Path.home() / ".config" / "change_wallpaper_reddit.rc"
    config_path_windows = Path(sys.argv[0]).parent / "change_wallpaper_reddit.rc"

    if platform.system() == "Linux":
        config_path = config_path_linux
    else:
        config_path = config_path_windows
    section_name = "root"
    try:
        conf = ConfigParser(default)
        with open(config_path, "r") as stream:
            config_string = f"[{section_name}]\n{stream.read()}"
            conf.read_string(config_string)

            ret = {}

            # Add a value to ret, printing an error message if there is an error
            def add_to_ret(fun, name):
                try:
                    ret[name] = fun(section_name, name)
                except ValueError:
                    ret[name] = default[name]

            add_to_ret(conf.get, "subreddit")
            add_to_ret(conf.getboolean, "nsfw")
            add_to_ret(conf.getint, "display")
            add_to_ret(conf.get, "time")
            add_to_ret(conf.get, "output")
            add_to_ret(conf.get, "sort")
            add_to_ret(conf.get, "limit")
            add_to_ret(conf.getboolean, "random")

            return ret

    except IOError:
        return default


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
        help="Example: hour, day, week, month, year",
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
        "--sort", type=str, default=config["sort"], help="Can be one of: hot, top, new."
    )
    parser.add_argument(
        "-l",
        "--limit",
        type=str,
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
    parser.add_argument("--client-id", type=str, help="Reddit API client ID.")
    parser.add_argument(
        "--api-key", type=str, help="Reddit API client secret (api key)."
    )

    arguments = parser.parse_args()
    return arguments


def get_top_image(sub_reddit):
    """Get image link of most upvoted wallpaper of the day
    :sub_reddit: name of the sub reddit
    :return: the image link
    """
    if args.sort == "top":
        submissions = sub_reddit.top(time_filter=args.time, limit=int(args.limit))
    elif args.sort == "new":
        submissions = sub_reddit.new(limit=int(args.limit))
    else:
        submissions = sub_reddit.hot(limit=int(args.limit))

    if args.random:
        submissions = sorted(submissions, key=lambda k: random.random())

    for submission in submissions:
        ret = {"id": submission.id}
        ret["subreddit"] = submission.subreddit.display_name
        print(ret["subreddit"])
        if not args.nsfw and submission.over_18:
            continue
        url = submission.url
        print(f"url : {url}")
        # Strip trailing arguments (after a '?')
        url = re.sub(r"\?.*", "", url)
        ret["type"] = url.split(".")[-1]

        if url.endswith((".jpg", ".png", ".jpeg")):
            ret["url"] = url
        # Imgur support
        elif "imgur.com" in url and "/a/" not in url and "/gallery/" not in url:
            if url.endswith("/new"):
                url = url.rsplit("/", 1)[0]
            id_toget = url.rsplit("/", 1)[1].rsplit(".", 1)[0]
            ret["url"] = f"http://i.imgur.com/{id_toget}.jpg"
        else:
            continue

        return ret


def detect_desktop_environment():
    """Get current Desktop Environment
       http://stackoverflow.com
       /questions/2035657/what-is-my-current-desktop-environment
    :return: environment
    """
    environment = {}
    d_session = os.environ.get("DESKTOP_SESSION")
    xdg_current_desktop = os.environ.get("XDG_CURRENT_DESKTOP")
    if os.environ.get("KDE_FULL_SESSION") == "true":
        environment["name"] = "kde"
        environment["command"] = """
                    qdbus org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript '
                        var allDesktops = desktops();
                        print (allDesktops);
                        for (i=0;i<allDesktops.length;i++) {{
                            d = allDesktops[i];
                            d.wallpaperPlugin = "org.kde.image";
                            d.currentConfigGroup = Array("Wallpaper",
                                                   "org.kde.image",
                                                   "General");
                            d.writeConfig("Image", "file:///{save_location}")
                        }}
                    '
                """
    elif os.environ.get("GNOME_DESKTOP_SESSION_ID") or (
        xdg_current_desktop and "GNOME" in xdg_current_desktop.upper()
    ):
        environment["name"] = "gnome"
        environment["command"] = (
            "gsettings set org.gnome.desktop.background picture-uri file://{save_location} && gsettings set org.gnome.desktop.background picture-uri-dark file://{save_location}"
        )
    elif d_session == "Lubuntu":
        environment["name"] = "lubuntu"
        environment["command"] = "pcmanfm -w {save_location} --wallpaper-mode=fit"
    elif d_session == "mate":
        environment["name"] = "mate"
        environment["command"] = (
            "gsettings set org.mate.background picture-filename {save_location}"
        )
    elif d_session in ("i3", "leftwm", "dwm"):
        environment["name"] = "i3"
        environment["command"] = "feh --bg-scale {save_location}"
    else:
        try:
            info = subprocess.getoutput("xprop -root _DT_SAVE_MODE")
            if ' = "xfce4"' in info:
                environment["name"] = "xfce"
                environment["command"] = (
                    "xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor0/workspace0/last-image -s {save_location}"
                )
        except (OSError, RuntimeError):
            environment = None
            pass
    return environment


if __name__ == "__main__":
    args = parse_args()
    subreddit = args.subreddit
    save_dir = args.output

    supported_linux_desktop_envs = ["gnome", "mate", "kde", "lubuntu", "i3", "xfce"]

    client_id = args.client_id
    api_key = args.api_key

    if not all([client_id, api_key]):
        # Load credentials from credentials.json file
        credentials_path = Path(sys.argv[0]).parent / "credentials.json"
        try:
            with open(credentials_path) as f:
                params = json.load(f)
            client_id = client_id or params.get("client_id")
            api_key = api_key or params.get("api_key")
        except (IOError, json.JSONDecodeError):
            pass

    if not all([client_id, api_key]):
        sys.exit(
            "Error: client_id and api_key not provided. "
            "Please provide them as arguments (--client-id, --api-key) "
            "or in credentials.json."
        )

    # Python Reddit Api Wrapper
    r = praw.Reddit(
        client_id=client_id,
        client_secret=api_key,
        user_agent=f"Get top wallpaper from /r/{subreddit}",
    )

    # Get top image link
    image = get_top_image(r.subreddit(subreddit))
    try:
        if "url" not in image:
            sys.exit(
                "Error: No suitable images were found, the program is now exiting."
            )
    except TypeError:
        sys.exit("Error: No suitable images were found, the program is now exiting.")

    # Request image
    response = requests.get(image["url"], allow_redirects=False)
    # If image is available, proceed to save
    if response.status_code == requests.codes.ok:
        # Get home directory and location where image will be saved
        # (default location for Ubuntu is used)
        save_location = (
            Path.home() / save_dir / f"{subreddit}-{image['id']}.{image['type']}"
        )

        if not save_location.is_file():
            # Create folders if they don't exist
            save_location.parent.mkdir(parents=True, exist_ok=True)

            # Write to disk
            with open(save_location, "wb") as fo:
                for chunk in response.iter_content(4096):
                    fo.write(chunk)

        # Check OS and environments
        platform_name = platform.system()
        if platform_name.startswith("Lin"):
            # Check desktop environments for linux
            desktop_environment = detect_desktop_environment()
            if (
                desktop_environment
                and desktop_environment["name"] in supported_linux_desktop_envs
            ):
                os.system(
                    desktop_environment["command"].format(save_location=save_location)
                )
            else:
                print("Unsupported desktop environment")

        # Windows
        if platform_name.startswith("Win"):
            ctypes.windll.user32.SystemParametersInfoW(20, 0, str(save_location), 3)

        # OS X/macOS
        if platform_name.startswith("Darwin"):
            if args.display == 0:
                command = """
                        osascript -e 'tell application "System Events"
                            set desktopCount to count of desktops
                            repeat with desktopNumber from 1 to desktopCount
                                tell desktop desktopNumber
                                    set picture to "{save_location}"
                                end tell
                            end repeat
                        end tell'
                          """.format(save_location=save_location)
            else:
                command = """osascript -e 'tell application "System Events"
                                set desktopCount to count of desktops
                                tell desktop {display}
                                    set picture to "{save_location}"
                                end tell
                            end tell'""".format(
                    display=args.display, save_location=save_location
                )
            os.system(command)
    else:
        sys.exit("Error: Image url is not available, the program is now exiting.")
