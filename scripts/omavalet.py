"""OmaValet's small, testable config engine."""

import argparse
import configparser
import errno
import json
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

PLUGIN_ID = "io.github.jcarcinogen.omavalet"
DEFAULT_WORKSPACE_COUNT = 5
MAX_WORKSPACE_COUNT = 10
MAX_STATE_BYTES = 1_048_576
LOADER_REQUIRE = 'require("hypr.omavalet")'
LOADER_BLOCK = (
    "-- omavalet:begin\n"
    f"{LOADER_REQUIRE}\n"
    "-- omavalet:end\n"
)
DESKTOP_FIELD_CODE = re.compile(r"(?<!%)%[fFuUdDnNickvm]")
FLATPAK_COMMAND = re.compile(r"--command=(\S+)")
EXEC_WRAPPERS = {
    "flatpak",
    "env",
    "sh",
    "bash",
    "uwsm-app",
    "gtk-launch",
    "setsid",
}
LAUNCH_PATTERN = re.compile(
    r'o\.(?:launch_on_start|exec_on_start)\(\s*"((?:\\.|[^"\\])*)"\s*\)'
)
WINDOW_PATTERN = re.compile(
    r'o\.window\(\s*"((?:\\.|[^"\\])*)"\s*,\s*\{[^{}]*?'
    r'workspace\s*=\s*"(\d+)(\s+silent)?"[^{}]*\}\s*\)'
)


def strip_exec(command: str) -> str:
    """Remove freedesktop field codes from a desktop Exec line."""
    cleaned = " ".join(DESKTOP_FIELD_CODE.sub("", command).split()).strip()
    if cleaned.endswith(" --"):
        cleaned = cleaned[:-3].rstrip()
    return cleaned


def _usable_wm_class(value: str) -> bool:
    value = (value or "").strip()
    return bool(value) and not value.startswith("@@") and "%" not in value


def window_class_for(
    startup_wm_class: str, desktop_stem: str, exec_line: str = ""
) -> str:
    """Build a Hyprland class match from every real identifier we can find."""
    classes = []

    def add(value: str) -> None:
        value = (value or "").strip()
        if _usable_wm_class(value) and value not in classes:
            classes.append(value)

    add(startup_wm_class)
    add(desktop_stem)
    if "." in (desktop_stem or ""):
        tail = desktop_stem.rsplit(".", 1)[-1]
        if tail.casefold() not in {"desktop", "application", "app", "org", "com", "io", "net"}:
            add(tail)
    for match in FLATPAK_COMMAND.finditer(exec_line or ""):
        add(match.group(1))
    tokens = (exec_line or "").split()
    if tokens:
        binary = Path(tokens[0]).name
        if binary not in EXEC_WRAPPERS:
            add(binary)
    if not classes:
        return desktop_stem
    if len(classes) == 1:
        return classes[0]
    return "(" + "|".join(classes) + ")"


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
                    "class": window_class_for(
                        entry.get("StartupWMClass", ""), path.stem, command
                    ),
                }
            )
    seen_ids = {app["desktopId"] for app in apps}
    for extra in _omarchy_extras():
        if extra["desktopId"] not in seen_ids:
            apps.append(extra)
    return sorted(apps, key=lambda app: app["name"].casefold())


def _omarchy_extras() -> list[dict]:
    return [
        {
            "desktopId": "org.omarchy.agent.desktop",
            "name": "Agent",
            "exec": "omarchy-agent --pick",
            "class": "org.omarchy.agent",
            "icon": "org.omarchy.agent",
        }
    ]


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
        state = json.loads(_read_text_nofollow(state_path, MAX_STATE_BYTES))
        if isinstance(state, dict) and isinstance(state.get("apps", []), list):
            return state
    except (OSError, ValueError):
        pass
    return {"version": 1, "apps": []}


def _used_workspace(value) -> Optional[int]:
    try:
        workspace = int(value)
    except (TypeError, ValueError):
        return None
    if 1 <= workspace <= MAX_WORKSPACE_COUNT:
        return workspace
    return None


def workspace_count(state: dict, existing: Optional[dict] = None) -> int:
    """Show Omarchy's 5 lanes, then any extra slips already in use."""
    used = [DEFAULT_WORKSPACE_COUNT]
    requested = _used_workspace((state or {}).get("workspaceCount"))
    if requested:
        used.append(requested)
    for app in (state or {}).get("apps", []):
        workspace = _used_workspace(app.get("workspace"))
        if workspace:
            used.append(workspace)
    for parked in (existing or {}).get("parking", []):
        workspace = _used_workspace(parked.get("workspace"))
        if workspace:
            used.append(workspace)
    return max(used)


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
        "workspaceCount": workspace_count(state, existing),
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


def _is_symlink(path: Path) -> bool:
    try:
        return stat.S_ISLNK(path.lstat().st_mode)
    except FileNotFoundError:
        return False


def _is_regular_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except FileNotFoundError:
        return False


def _read_text_nofollow(path: Path, max_bytes: int = MAX_STATE_BYTES) -> str:
    """Read a regular file without following a symlink, FIFO, or unbounded size."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise
    if stat.S_ISLNK(info.st_mode):
        raise OSError(errno.ELOOP, "refusing to follow symlink", str(path))
    if not stat.S_ISREG(info.st_mode):
        raise OSError(errno.EINVAL, "refusing to read non-regular file", str(path))
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise OSError(errno.EINVAL, "refusing to read non-regular file", str(path))
        if info.st_size > max_bytes:
            raise OSError(errno.EFBIG, "file exceeds byte cap", str(path))
        chunks = []
        remaining = max_bytes + 1
        while remaining > 0:
            piece = os.read(fd, remaining)
            if not piece:
                break
            chunks.append(piece)
            remaining -= len(piece)
        data = b"".join(chunks)
        if len(data) > max_bytes:
            raise OSError(errno.EFBIG, "file exceeds byte cap", str(path))
    finally:
        os.close(fd)
    return data.decode("utf-8")


def _atomic_write(path: Path, content: str) -> None:
    """Replace path with content without following a dest symlink or truncating in place."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def _write_if_changed(path: Path, content: str) -> bool:
    path = Path(path)
    if _is_symlink(path):
        _atomic_write(path, content)
        return True
    try:
        if _read_text_nofollow(path) == content:
            return False
    except FileNotFoundError:
        pass
    except OSError:
        pass
    _atomic_write(path, content)
    return True


def _unlink_nofollow(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    path.unlink()
    return True


def _sync_parked_apps_with_catalog(state: dict, catalog: list[dict]) -> dict:
    """Refresh class/exec from the live desktop catalog so parking still matches."""
    by_id = {app["desktopId"]: app for app in catalog}
    synced = []
    for parked in state.get("apps", []):
        catalog_app = by_id.get(parked.get("desktopId"))
        if catalog_app:
            parked = {
                **parked,
                "class": catalog_app["class"],
                "exec": catalog_app["exec"],
                "name": catalog_app.get("name", parked.get("name")),
                "icon": catalog_app.get("icon", parked.get("icon", "")),
                "silent": True,
            }
        synced.append(parked)
    return {**state, "apps": synced}


def apply_state(state: dict, config_home: Path, catalog=None) -> dict:
    """Write OmaValet-owned state/Lua and install its reversible loader."""
    config_home = Path(config_home)
    if catalog:
        state = _sync_parked_apps_with_catalog(state, catalog)
    hypr_dir = config_home / "hypr"
    omarchy_dir = config_home / "omarchy"
    hyprland_path = hypr_dir / "hyprland.lua"
    backup_path = hypr_dir / "hyprland.lua.omavalet.bak"
    if _is_symlink(hyprland_path):
        raise OSError(errno.ELOOP, "refusing to follow symlink", str(hyprland_path))
    try:
        original = _read_text_nofollow(hyprland_path)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Hyprland config not found: {hyprland_path}") from exc

    installed = install_loader(original)
    if installed != original and not _is_regular_file(backup_path):
        _atomic_write(backup_path, original)

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

    if _is_regular_file(hyprland_path):
        current = _read_text_nofollow(hyprland_path)
        cleaned = remove_loader(current)
        changed |= _write_if_changed(hyprland_path, cleaned)

    for owned_path in (
        hypr_dir / "omavalet.lua",
        config_home / "omarchy" / "omavalet.json",
    ):
        if _unlink_nofollow(owned_path):
            changed = True

    if cleaned is not None and _is_regular_file(backup_path):
        if _read_text_nofollow(backup_path) == cleaned:
            _unlink_nofollow(backup_path)
            changed = True

    return {"changed": changed, "backupPreserved": _is_regular_file(backup_path) or _is_symlink(backup_path)}


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
        "launchOnStart": False,
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


def set_launch_on_start(state: dict, desktop_id: str, enabled: bool) -> dict:
    """Opt a parked app into or out of session autostart."""
    apps = []
    for app in state.get("apps", []):
        updated = dict(app)
        if updated.get("desktopId") == desktop_id:
            updated["launchOnStart"] = bool(enabled)
        apps.append(updated)
    return {**state, "version": 1, "apps": apps}


def expand_lot(state: dict, existing: Optional[dict] = None) -> dict:
    """Open one more parking lane, up to Hyprland's ten workspaces."""
    current = workspace_count(state, existing)
    return {
        **state,
        "version": 1,
        "workspaceCount": min(MAX_WORKSPACE_COUNT, current + 1)
        if current < MAX_WORKSPACE_COUNT
        else current,
    }


def shrink_lot(state: dict, existing: Optional[dict] = None) -> dict:
    """Remove the last extra empty lane, never going below five."""
    current = workspace_count(state, existing)
    occupied = 0
    for app in (state or {}).get("apps", []):
        workspace = _used_workspace(app.get("workspace"))
        if workspace:
            occupied = max(occupied, workspace)
    for parked in (existing or {}).get("parking", []):
        workspace = _used_workspace(parked.get("workspace"))
        if workspace:
            occupied = max(occupied, workspace)
    if current <= DEFAULT_WORKSPACE_COUNT or occupied >= current:
        new_count = max(DEFAULT_WORKSPACE_COUNT, current)
    else:
        new_count = max(DEFAULT_WORKSPACE_COUNT, current - 1)
    return {**state, "version": 1, "workspaceCount": new_count}


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
        lines.append(
            f"o.window({_lua_string(app['class'])}, "
            f'{{ workspace = "{workspace}" }})'
        )
        if app.get("launchOnStart"):
            command = f"[workspace {workspace} silent] uwsm-app -- {app['exec']}"
            lines.append(f"o.exec_on_start({_lua_string(command)})")

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
    subparsers.add_parser("expand")
    subparsers.add_parser("shrink")
    park = subparsers.add_parser("park")
    park.add_argument("desktop_id")
    park.add_argument("workspace", type=int)
    unpark = subparsers.add_parser("unpark")
    unpark.add_argument("desktop_id")
    boot = subparsers.add_parser("boot")
    boot.add_argument("desktop_id")
    boot.add_argument("enabled", choices=("on", "off"))
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
    catalog = desktop_catalog(directories)
    if args.command == "park":
        app = next(
            (item for item in catalog if item["desktopId"] == args.desktop_id), None
        )
        if app is None:
            parser.error(f"desktop app not found: {args.desktop_id}")
        state = park_app(state, app, args.workspace)
    elif args.command == "expand":
        hypr_dir = config_home / "hypr"
        existing = scan_existing(
            _read_text(hypr_dir / "autostart.lua"),
            {
                name: _read_text(hypr_dir / name)
                for name in ("hyprland.lua", "windows.lua")
            },
        )
        state = expand_lot(state, existing)
    elif args.command == "shrink":
        hypr_dir = config_home / "hypr"
        existing = scan_existing(
            _read_text(hypr_dir / "autostart.lua"),
            {
                name: _read_text(hypr_dir / name)
                for name in ("hyprland.lua", "windows.lua")
            },
        )
        state = shrink_lot(state, existing)
    elif args.command == "boot":
        state = set_launch_on_start(state, args.desktop_id, args.enabled == "on")
    else:
        state = unpark_app(state, args.desktop_id)

    result = apply_state(state, config_home, catalog)
    if result["changed"]:
        _reload_hyprland()
    print(json.dumps({**result, "snapshot": build_snapshot(config_home, directories)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
