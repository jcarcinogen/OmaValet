import json
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

        self.assertEqual(snapshot["catalog"][0]["name"], "Firefox")
        self.assertEqual(snapshot["valet"][0]["workspace"], 2)
        self.assertEqual(snapshot["existing"]["parking"][0]["workspace"], 3)
        self.assertEqual(snapshot["existing"]["parking"][0]["name"], "Firefox")
        self.assertEqual(snapshot["existing"]["parking"][0]["icon"], "firefox")
        self.assertEqual(snapshot["existing"]["launches"][0]["exec"], "syncthing")


if __name__ == "__main__":
    unittest.main()
