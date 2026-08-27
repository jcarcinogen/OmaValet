# OmaValet

**Park startup apps in the Omarchy workspaces where they belong.**

OmaValet is a minimal, theme-aware workspace launcher for Omarchy Quattro. It shows applications by their desktop name and icon, displays existing Hyprland workspace assignments, and lets you assign startup apps without hand-editing Lua.

![OmaValet on Omarchy Quattro](assets/omavalet.png)

## Features

- Search installed desktop applications by name.
- See five workspace parking lanes at a glance, matching Omarchy's default.
- Park more than one app in the same workspace.
- Add extra workspaces from the overlay when you need a lane that isn't shown yet.
- Click an app, then click a workspace to park it there.
- See existing Hyprland assignments as locked, read-only entries.
- Remove OmaValet-owned assignments with **×**.
- Follow the active Omarchy theme through its native `Color`, `Style`, and `Border` tokens.
- Generate deterministic Hyprland Lua without rewriting `autostart.lua`.
- Back up `hyprland.lua` before adding the reversible loader block.

## Requirements

- Omarchy Quattro (Omarchy 4)
- Python 3

OmaValet uses only the Python standard library. It does not require root and does not launch a second Quickshell process.

## Install

```bash
omarchy plugin add https://github.com/jcarcinogen/OmaValet.git --enable
```

The plugin appears on the right side of the Omarchy bar. Click its icon to open the parking board.

## Use

1. Open **OmaValet** from the bar.
2. Search for and select an application.
3. Click the workspace where the valet should park it. A lane can hold several apps.
4. Use **+ Workspace** if you need a lane past the five Omarchy shows by default.
5. Remove an OmaValet assignment by clicking its **×**.

Locked entries come from existing user-authored Hyprland rules. OmaValet shows them for context but does not overwrite or remove them.

## What OmaValet writes

OmaValet does not edit `~/.config/hypr/autostart.lua`. Startup and placement are generated together in a dedicated module:

- `~/.config/omarchy/omavalet.json` — OmaValet-owned assignments
- `~/.config/hypr/omavalet.lua` — generated `o.window(...)` and `o.launch_on_start(...)` calls
- `~/.config/hypr/hyprland.lua.omavalet.bak` — first-write backup
- a marked `require("hypr.omavalet")` block in `~/.config/hypr/hyprland.lua`

Generated applications launch at the next Hyprland session start. The matching window rule parks each application in its assigned workspace.

## Remove

Reset OmaValet first so its generated state and marked loader are removed safely:

```bash
PLUGIN_DIR="$HOME/.config/omarchy/plugins/io.github.jcarcinogen.omavalet"
python3 "$PLUGIN_DIR/scripts/omavalet.py" reset
omarchy plugin remove io.github.jcarcinogen.omavalet
```

If reset reports `"backupPreserved": true`, OmaValet detected that the current Hyprland configuration no longer matches its original backup. The backup is deliberately left at:

```text
~/.config/hypr/hyprland.lua.omavalet.bak
```

Review it before deleting it. Reset never replaces later user changes with the backup.

## Development

Run the Python tests:

```bash
python3 -m unittest discover -s tests -v
```

Validate the plugin on Omarchy:

```bash
omarchy plugin validate .
```

The plugin id is `io.github.jcarcinogen.omavalet`.

## Current scope

- Workspaces 1–5 are shown by default, matching Omarchy. Extra lanes appear if you already park there, or when you click **+ Workspace** (up to 10).
- Existing assignments found in `hyprland.lua` and `windows.lua` are read-only.
- Application identity comes from freedesktop desktop files, preferring `StartupWMClass` when available.

## License

MIT
