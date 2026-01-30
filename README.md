# Kitty theme selector

A small TUI to list and apply [kitty](https://sw.kovidgoyal.net/kitty/) themes from `~/.config/kitty` (or `$KITTY_CONFIG_DIRECTORY`).

Kitty is a high performance Terminal with really low CPU usage. 
The problem this plugin solves is to be able to select different color themes to different tabs, easily without having to tweak with a conf file everytime.

This is added under apache licence, so if anyone is interested to add any more features, do feel free to commit, I will review and confirm.

## Setup

On Debian/Ubuntu (and other PEP 668 systems) use a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

If `python3 -m venv` fails, install: `sudo apt install python3-venv` (or `python3-full`).

## Run

From a kitty tab:

```bash
.venv/bin/python theme_selector.py
```

Or use the helper script (creates `.venv` and installs deps if needed):

```bash
./changeKittyTheme.sh
```
### Usage Recommendation
Once setup, Add this script to your .bashrc file, so that its easier to call from any new tab.

```
export PATH=[path to your changeKittyTheme.sh]:${PATH}
```

After opening a new Kitty tab / reloading your shell - just use changeKittyTheme to set up new theme everytime

Enjoy !! 



## How to Navigate 

- **↑ / ↓** — move
- **Enter** — apply selected theme
- **/** — focus filter, type to narrow themes
- **q** — quit

Themes are loaded from all `.conf` files under your kitty config directory (including subdirs like `kitty-themes/`). Applying a theme runs `kitten @ set-colors -a <path>` (or `kitty @ set-colors`) so the current (and optionally all) windows update immediately.

If applying a theme fails, ensure **remote control** is enabled in kitty: add `allow_remote_control yes` to your `kitty.conf` (often in `~/.config/kitty/kitty.conf`), then restart kitty.
