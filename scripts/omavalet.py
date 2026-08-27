"""OmaValet's small, testable config engine."""

import argparse
import configparser
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

PLUGIN_ID = "io.github.jcarcinogen.omavalet"
LOADER_REQUIRE = 'require("hypr.omavalet")'
LOADER_BLOCK = (
    "-- omavalet:begin\n"
    f"{LOADER_REQUIRE}\n"
    "-- omavalet:end\n"
)
DESKTOP_FIELD_CODE = re.compile(r"(?<!%)%[fFuUdDnNickvm]")
LAUNCH_PATTERN = re.compile(
    r'o\.(?:launch_on_start|exec_on_start)\(\s*"((?:\\.|[^"\\])*)"\s*\)'
)
WINDOW_PATTERN = re.compile(
    r'o\.window\(\s*"((?:\\.|[^"\\])*)"\s*,\s*\{[^{}]*?'
    r'workspace\s*=\s*"(\d+)(\s+silent)?"[^{}]*\}\s*\)'
)


def strip_exec(command: str) -> str:
    """Remove freedesktop field codes from a desktop Exec line."""
    return " ".join(DESKTOP_FIELD_CODE.sub("", command).split()).strip()


def desktop_catalog(directories) -> list[dict]:
    """Read launchable desktop entries, preferring earlier directories."""
    apps = []
    seen = set()
    for directory in map(Path, directories):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.desktop")):
            if path.name in seen:
                continue
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(path, encoding="utf-8")
                entry = parser["Desktop Entry"]
            except (OSError, KeyError, configparser.Error):
                continue
            name = entry.get("Name", "").strip()
            command = strip_exec(entry.get("Exec", ""))
            if entry.getboolean("NoDisplay", fallback=False) or entry.getboolean(
                "Hidden", fallback=False
            ):
                seen.add(path.name)
                continue
            if not name or not command:
                continue
            seen.add(path.name)
            apps.append(
                {
                    "desktopId": path.name,
                    "name": name,
                    "exec": command,
                    "icon": entry.get("Icon", "").strip(),
                    "class": entry.get("StartupWMClass", "").strip()
                    or path.stem,
                }
            )
    return sorted(apps, key=lambda app: app["name"].casefold())


def _unescape_lua(value: str) -> str:
    return value.replace('\\"', '"').replace("\\\\", "\\")


def _strip_lua_line_comments(text: str) -> str:
    """Remove Lua -- comments while preserving dashes inside quoted strings."""
    cleaned = []
    for line in text.splitlines():
        quote = None
        escaped = False
        kept = []
        index = 0
        while index < len(line):
            char = line[index]
            if escaped:
                kept.append(char)
                escaped = False
            elif quote and char == "\\":
                kept.append(char)
                escaped = True
            elif quote and char == quote:
                kept.append(char)
                quote = None
            elif not quote and char in ('"', "'"):
                kept.append(char)
                quote = char
            elif not quote and line[index : index + 2] == "--":
                break
            else:
                kept.append(char)
            index += 1
        cleaned.append("".join(kept))
    return "\n".join(cleaned)


def scan_existing(autostart_text: str, rule_texts: dict[str, str]) -> dict:
    """Return read-only launches and workspace parking found in user Lua."""
    active_autostart = _strip_lua_line_comments(autostart_text)
    launches = [
        {"exec": _unescape_lua(match.group(1)), "source": "autostart.lua"}
        for match in LAUNCH_PATTERN.finditer(active_autostart)
    ]
    parking = []
    for source, text in rule_texts.items():
        active_text = _strip_lua_line_comments(text)
        for match in WINDOW_PATTERN.finditer(active_text):
            parking.append(
                {
                    "class": _unescape_lua(match.group(1)),
                    "workspace": int(match.group(2)),
                    "silent": bool(match.group(3)),
                    "source": source,
                }
            )
    parking.sort(key=lambda item: (item["workspace"], item["class"].casefold()))
    return {"launches": launches, "parking": parking}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def load_state(config_home: Path) -> dict:
    state_path = Path(config_home) / "omarchy" / "omavalet.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if isinstance(state, dict) and isinstance(state.get("apps", []), list):
            return state
    except (OSError, ValueError):
        pass
    return {"version": 1, "apps": []}


def _resolve_catalog_app(window_class: str, catalog: list[dict], aliases: dict):
    exact = aliases.get(window_class.casefold())
    if exact:
        return exact
    needle = re.sub(r"[^a-z0-9]", "", window_class.casefold())
    if len(needle) < 3:
        return None
    for app in catalog:
        name = re.sub(r"[^a-z0-9]", "", app.get("name", "").casefold())
        if len(name) >= 3 and (name in needle or needle in name):
            return app
    for app in catalog:
        command = re.sub(r"[^a-z0-9]", "", app.get("exec", "").casefold())
        if needle in command:
            return app
    return None


def build_snapshot(config_home: Path, app_directories) -> dict:
    """Assemble the single JSON model consumed by OmaValet's overlay."""
    config_home = Path(config_home)
    hypr_dir = config_home / "hypr"
    state = load_state(config_home)
    catalog = desktop_catalog(app_directories)
    existing = scan_existing(
        _read_text(hypr_dir / "autostart.lua"),
        {
            name: _read_text(hypr_dir / name)
            for name in ("hyprland.lua", "windows.lua")
        },
    )
    aliases = {}
    for app in catalog:
        for alias in (app.get("class", ""), Path(app["desktopId"]).stem):
            if alias:
                aliases.setdefault(alias.casefold(), app)
    for parked in existing["parking"]:
        app = _resolve_catalog_app(parked["class"], catalog, aliases)
        parked["name"] = app["name"] if app else parked["class"]
        parked["icon"] = app["icon"] if app else ""
    return {
        "catalog": catalog,
        "valet": state.get("apps", []),
        "existing": existing,
    }


def install_loader(hyprland_lua: str) -> str:
    """Add OmaValet's marked loader after the user's autostart include."""
    if LOADER_REQUIRE in hyprland_lua:
        return hyprland_lua
    lines = hyprland_lua.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if 'require("hypr.autostart")' in line:
            lines.insert(index + 1, LOADER_BLOCK)
            return "".join(lines)
    separator = "" if not hyprland_lua or hyprland_lua.endswith("\n") else "\n"
    return hyprland_lua + separator + LOADER_BLOCK


def remove_loader(hyprland_lua: str) -> str:
    """Remove only the block explicitly owned by OmaValet."""
    return hyprland_lua.replace(LOADER_BLOCK, "")


def _write_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def apply_state(state: dict, config_home: Path) -> dict:
    """Write OmaValet-owned state/Lua and install its reversible loader."""
    config_home = Path(config_home)
    hypr_dir = config_home / "hypr"
    omarchy_dir = config_home / "omarchy"
    hyprland_path = hypr_dir / "hyprland.lua"
    backup_path = hypr_dir / "hyprland.lua.omavalet.bak"
    if not hyprland_path.exists():
        raise FileNotFoundError(f"Hyprland config not found: {hyprland_path}")

    original = hyprland_path.read_text(encoding="utf-8")
    installed = install_loader(original)
    if installed != original and not backup_path.exists():
        shutil.copy2(hyprland_path, backup_path)

    changed = False
    changed |= _write_if_changed(
        omarchy_dir / "omavalet.json", json.dumps(state, indent=2) + "\n"
    )
    changed |= _write_if_changed(hypr_dir / "omavalet.lua", render_lua(state))
    changed |= _write_if_changed(hyprland_path, installed)
    return {"changed": changed}


def cleanup_state(config_home: Path) -> dict:
    """Remove only OmaValet-owned state and the marked loader block."""
    config_home = Path(config_home)
    hypr_dir = config_home / "hypr"
    hyprland_path = hypr_dir / "hyprland.lua"
    backup_path = hypr_dir / "hyprland.lua.omavalet.bak"
    changed = False
    cleaned = None

    if hyprland_path.exists():
        current = hyprland_path.read_text(encoding="utf-8")
        cleaned = remove_loader(current)
        changed |= _write_if_changed(hyprland_path, cleaned)

    for owned_path in (
        hypr_dir / "omavalet.lua",
        config_home / "omarchy" / "omavalet.json",
    ):
        if owned_path.exists():
            owned_path.unlink()
            changed = True

    if backup_path.exists() and cleaned is not None:
        if backup_path.read_text(encoding="utf-8") == cleaned:
            backup_path.unlink()
            changed = True

    return {"changed": changed, "backupPreserved": backup_path.exists()}


def park_app(state: dict, app: dict, workspace: int) -> dict:
    """Return state with one desktop app parked in exactly one workspace."""
    workspace = int(workspace)
    if not 1 <= workspace <= 10:
        raise ValueError("workspace must be between 1 and 10")
    parked = {
        "desktopId": app["desktopId"],
        "name": app["name"],
        "exec": app["exec"],
        "class": app["class"],
        "icon": app.get("icon", ""),
        "workspace": workspace,
        "enabled": True,
        "silent": True,
    }
    apps = [
        dict(existing)
        for existing in state.get("apps", [])
        if existing.get("desktopId") != app["desktopId"]
    ]
    apps.append(parked)
    return {**state, "version": 1, "apps": apps}


def unpark_app(state: dict, desktop_id: str) -> dict:
    """Return state without the selected app's parking assignment."""
    return {
        **state,
        "version": 1,
        "apps": [
            dict(app)
            for app in state.get("apps", [])
            if app.get("desktopId") != desktop_id
        ],
    }


def _lua_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    return '"' + escaped + '"'


def render_lua(state: dict) -> str:
    """Render enabled parking assignments as deterministic Hyprland Lua."""
    lines = [
        f"-- Generated by {PLUGIN_ID}. Do not edit.",
        "-- Source: ~/.config/omarchy/omavalet.json",
    ]

    apps = sorted(
        state.get("apps", []),
        key=lambda app: (int(app.get("workspace", 0)), app.get("name", "").casefold()),
    )
    for app in apps:
        if not app.get("enabled", True):
            continue
        workspace = int(app["workspace"])
        if not 1 <= workspace <= 10:
            raise ValueError("workspace must be between 1 and 10")
        silent = " silent" if app.get("silent", True) else ""
        lines.append(
            f"o.window({_lua_string(app['class'])}, "
            f'{{ workspace = "{workspace}{silent}" }})'
        )
        lines.append(f"o.launch_on_start({_lua_string(app['exec'])})")

    return "\n".join(lines) + "\n"


def _config_home() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg).expanduser()
    return Path.home() / ".config"


def _application_dirs() -> list[Path]:
    data_home = os.environ.get("XDG_DATA_HOME")
    user_data = Path(data_home).expanduser() if data_home else Path.home() / ".local/share"
    dirs = [user_data / "applications"]
    for directory in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":"):
        if directory:
            dirs.append(Path(directory) / "applications")
    return dirs


def _reload_hyprland() -> None:
    subprocess.run(
        ["hyprctl", "reload"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="OmaValet workspace parking engine")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("snapshot")
    subparsers.add_parser("reset")
    park = subparsers.add_parser("park")
    park.add_argument("desktop_id")
    park.add_argument("workspace", type=int)
    unpark = subparsers.add_parser("unpark")
    unpark.add_argument("desktop_id")
    args = parser.parse_args(argv)

    config_home = _config_home()
    directories = _application_dirs()
    if args.command == "snapshot":
        print(json.dumps(build_snapshot(config_home, directories)))
        return 0
    if args.command == "reset":
        result = cleanup_state(config_home)
        if result["changed"]:
            _reload_hyprland()
        print(json.dumps(result))
        return 0

    state = load_state(config_home)
    if args.command == "park":
        catalog = desktop_catalog(directories)
        app = next(
            (item for item in catalog if item["desktopId"] == args.desktop_id), None
        )
        if app is None:
            parser.error(f"desktop app not found: {args.desktop_id}")
        state = park_app(state, app, args.workspace)
    else:
        state = unpark_app(state, args.desktop_id)

    result = apply_state(state, config_home)
    if result["changed"]:
        _reload_hyprland()
    print(json.dumps({**result, "snapshot": build_snapshot(config_home, directories)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
