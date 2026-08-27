import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from omavalet import apply_state, cleanup_state, park_app, unpark_app


class ApplyStateTest(unittest.TestCase):
    def test_writes_owned_files_and_backs_up_loader_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_home = Path(tmp)
            hypr = config_home / "hypr"
            hypr.mkdir()
            original = 'require("hypr.autostart")\n-- personal config\n'
            (hypr / "hyprland.lua").write_text(original, encoding="utf-8")
            state = {
                "version": 1,
                "apps": [
                    {
                        "name": "Firefox",
                        "class": "firefox",
                        "exec": "firefox",
                        "workspace": 2,
                    }
                ],
            }

            result = apply_state(state, config_home)

            self.assertEqual(
                json.loads((config_home / "omarchy" / "omavalet.json").read_text()),
                state,
            )
            self.assertIn(
                'o.window("firefox", { workspace = "2 silent" })',
                (hypr / "omavalet.lua").read_text(),
            )
            self.assertIn(
                'require("hypr.omavalet")', (hypr / "hyprland.lua").read_text()
            )
            self.assertEqual(
                (hypr / "hyprland.lua.omavalet.bak").read_text(), original
            )
            self.assertTrue(result["changed"])

    def test_parking_an_app_replaces_its_previous_workspace(self):
        state = {
            "version": 1,
            "apps": [
                {
                    "desktopId": "firefox.desktop",
                    "name": "Firefox",
                    "class": "firefox",
                    "exec": "firefox",
                    "workspace": 1,
                }
            ],
        }
        catalog_app = {
            "desktopId": "firefox.desktop",
            "name": "Firefox",
            "class": "firefox",
            "exec": "firefox",
            "icon": "firefox",
        }

        parked = park_app(state, catalog_app, 4)

        self.assertEqual(len(parked["apps"]), 1)
        self.assertEqual(parked["apps"][0]["workspace"], 4)
        self.assertTrue(parked["apps"][0]["silent"])
        self.assertTrue(parked["apps"][0]["enabled"])

    def test_valet_can_return_an_app_to_the_unassigned_list(self):
        state = {
            "version": 1,
            "apps": [
                {"desktopId": "firefox.desktop", "workspace": 4},
                {"desktopId": "foot.desktop", "workspace": 1},
            ],
        }

        returned = unpark_app(state, "firefox.desktop")

        self.assertEqual(
            [app["desktopId"] for app in returned["apps"]], ["foot.desktop"]
        )

    def test_cleanup_removes_only_omavalet_owned_files_and_loader(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            hypr = config / "hypr"
            hypr.mkdir()
            original = 'require("hypr.autostart")\n-- user rule\n'
            (hypr / "hyprland.lua").write_text(original, encoding="utf-8")
            apply_state(
                {
                    "version": 1,
                    "apps": [
                        {
                            "desktopId": "firefox.desktop",
                            "name": "Firefox",
                            "class": "firefox",
                            "exec": "firefox",
                            "workspace": 4,
                        }
                    ],
                },
                config,
            )

            result = cleanup_state(config)

            self.assertEqual((hypr / "hyprland.lua").read_text(), original)
            self.assertFalse((hypr / "omavalet.lua").exists())
            self.assertFalse((config / "omarchy" / "omavalet.json").exists())
            self.assertFalse((hypr / "hyprland.lua.omavalet.bak").exists())
            self.assertTrue(result["changed"])

    def test_cleanup_preserves_backup_after_user_changes_hyprland(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            hypr = config / "hypr"
            hypr.mkdir()
            original = 'require("hypr.autostart")\n'
            hyprland = hypr / "hyprland.lua"
            hyprland.write_text(original, encoding="utf-8")
            apply_state({"version": 1, "apps": []}, config)
            hyprland.write_text(
                hyprland.read_text(encoding="utf-8") + "-- later user rule\n",
                encoding="utf-8",
            )

            result = cleanup_state(config)

            self.assertTrue((hypr / "hyprland.lua.omavalet.bak").exists())
            self.assertTrue(result["backupPreserved"])
            self.assertIn("-- later user rule", hyprland.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
