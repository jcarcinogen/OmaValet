import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from omavalet import build_snapshot


class SnapshotTest(unittest.TestCase):
    def test_builds_one_ui_snapshot_from_catalog_state_and_user_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            apps_dir = root / "applications"
            hypr_dir = root / "hypr"
            omarchy_dir = root / "omarchy"
            apps_dir.mkdir()
            hypr_dir.mkdir()
            omarchy_dir.mkdir()
            (apps_dir / "firefox.desktop").write_text(
                "[Desktop Entry]\nName=Firefox\nExec=firefox %U\nIcon=firefox\nStartupWMClass=firefox\n",
                encoding="utf-8",
            )
            (hypr_dir / "autostart.lua").write_text(
                'o.launch_on_start("syncthing")\n', encoding="utf-8"
            )
            (hypr_dir / "hyprland.lua").write_text(
                'o.window("brave-firefox.com__-Default", { workspace = "3 silent" })\n',
                encoding="utf-8",
            )
            (omarchy_dir / "omavalet.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "apps": [
                            {
                                "desktopId": "firefox.desktop",
                                "name": "Firefox",
                                "exec": "firefox",
                                "class": "firefox",
                                "workspace": 2,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            snapshot = build_snapshot(root, [apps_dir])

        firefox = next(app for app in snapshot["catalog"] if app["name"] == "Firefox")
        self.assertEqual(firefox["name"], "Firefox")
        self.assertEqual(snapshot["valet"][0]["workspace"], 2)
        self.assertEqual(snapshot["existing"]["parking"][0]["workspace"], 3)
        self.assertEqual(snapshot["existing"]["parking"][0]["name"], "Firefox")
        self.assertEqual(snapshot["existing"]["parking"][0]["icon"], "firefox")
        self.assertEqual(snapshot["existing"]["launches"][0]["exec"], "syncthing")
        self.assertEqual(snapshot["workspaceCount"], 5)

    def test_shows_extra_lanes_when_existing_parking_uses_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hypr = root / "hypr"
            hypr.mkdir()
            (root / "omarchy").mkdir()
            (hypr / "hyprland.lua").write_text(
                'o.window("qemu", { workspace = "7 silent" })\n',
                encoding="utf-8",
            )

            snapshot = build_snapshot(root, [])

        self.assertEqual(snapshot["workspaceCount"], 7)

    def test_snapshot_does_not_block_on_fifo_hyprland_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hypr = root / "hypr"
            data = root / "data"
            hypr.mkdir()
            data.mkdir()
            (root / "omarchy").mkdir()
            os.mkfifo(hypr / "autostart.lua")
            env = {
                **os.environ,
                "XDG_CONFIG_HOME": str(root),
                "XDG_DATA_HOME": str(data),
                "XDG_DATA_DIRS": ":",
            }
            command = [
                sys.executable,
                str(Path(__file__).resolve().parents[1] / "scripts" / "omavalet.py"),
                "snapshot",
            ]
            try:
                result = subprocess.run(
                    command,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                self.fail("snapshot blocked while reading a FIFO autostart.lua")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["existing"]["launches"], [])

    def test_snapshot_ignores_symlinked_and_oversized_hyprland_fragments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hypr = root / "hypr"
            hypr.mkdir()
            (root / "omarchy").mkdir()
            outside = root / "outside.lua"
            outside.write_text(
                'o.window("outside", { workspace = "9" })\n',
                encoding="utf-8",
            )
            (hypr / "hyprland.lua").symlink_to(outside)
            (hypr / "windows.lua").write_text(
                'o.window("oversized", { workspace = "8" })\n' + " " * 1_048_576,
                encoding="utf-8",
            )

            snapshot = build_snapshot(root, [])

        self.assertEqual(snapshot["existing"]["parking"], [])
        self.assertEqual(snapshot["workspaceCount"], 5)


if __name__ == "__main__":
    unittest.main()
