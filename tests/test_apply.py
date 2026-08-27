import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from omavalet import (
    apply_state,
    cleanup_state,
    expand_lot,
    park_app,
    set_launch_on_start,
    shrink_lot,
    unpark_app,
)


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
                'o.window("firefox", { workspace = "2" })',
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
        self.assertFalse(parked["apps"][0]["launchOnStart"])

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

    def test_parking_keeps_multiple_apps_in_the_same_workspace(self):
        firefox = {
            "desktopId": "firefox.desktop",
            "name": "Firefox",
            "class": "firefox",
            "exec": "firefox",
            "icon": "firefox",
        }
        foot = {
            "desktopId": "foot.desktop",
            "name": "Foot",
            "class": "foot",
            "exec": "foot",
            "icon": "foot",
        }

        state = park_app({"version": 1, "apps": []}, firefox, 2)
        state = park_app(state, foot, 2)

        self.assertEqual(
            sorted(app["desktopId"] for app in state["apps"]),
            ["firefox.desktop", "foot.desktop"],
        )
        self.assertEqual({app["workspace"] for app in state["apps"]}, {2})

    def test_launch_on_start_can_be_turned_on_for_a_parked_app(self):
        state = park_app(
            {"version": 1, "apps": []},
            {
                "desktopId": "firefox.desktop",
                "name": "Firefox",
                "class": "firefox",
                "exec": "firefox",
            },
            2,
        )

        booted = set_launch_on_start(state, "firefox.desktop", True)

        self.assertTrue(booted["apps"][0]["launchOnStart"])
        self.assertFalse(state["apps"][0].get("launchOnStart", False))

    def test_expand_lot_opens_the_next_workspace_slip(self):
        expanded = expand_lot({"version": 1, "apps": []})
        self.assertEqual(expanded["workspaceCount"], 6)

        full = expand_lot({"version": 1, "workspaceCount": 10, "apps": []})
        self.assertEqual(full["workspaceCount"], 10)

    def test_shrink_lot_removes_empty_extra_lane_but_keeps_five(self):
        shrunk = shrink_lot({"version": 1, "workspaceCount": 6, "apps": []})
        self.assertEqual(shrunk["workspaceCount"], 5)
        floor = shrink_lot({"version": 1, "workspaceCount": 5, "apps": []})
        self.assertEqual(floor["workspaceCount"], 5)

    def test_shrink_lot_keeps_lane_that_has_a_parked_app(self):
        kept = shrink_lot(
            {
                "version": 1,
                "workspaceCount": 6,
                "apps": [{"desktopId": "a.desktop", "workspace": 6}],
            }
        )
        self.assertEqual(kept["workspaceCount"], 6)

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

    def test_park_write_does_not_follow_planted_omavalet_json_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            hypr = config / "hypr"
            hypr.mkdir()
            (hypr / "hyprland.lua").write_text(
                'require("hypr.autostart")\n', encoding="utf-8"
            )
            omarchy = config / "omarchy"
            omarchy.mkdir()
            victim = config / "victim.txt"
            victim.write_text("keep me\n", encoding="utf-8")
            planted = omarchy / "omavalet.json"
            planted.symlink_to(victim)

            apply_state({"version": 1, "apps": []}, config)

            self.assertEqual(victim.read_text(encoding="utf-8"), "keep me\n")
            self.assertFalse(planted.is_symlink())
            self.assertTrue(planted.is_file())
            self.assertIn('"version": 1', planted.read_text(encoding="utf-8"))

    def test_park_write_does_not_follow_planted_omavalet_lua_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            hypr = config / "hypr"
            hypr.mkdir()
            (hypr / "hyprland.lua").write_text(
                'require("hypr.autostart")\n', encoding="utf-8"
            )
            victim = config / "victim.lua"
            victim.write_text("-- keep me\n", encoding="utf-8")
            planted = hypr / "omavalet.lua"
            planted.symlink_to(victim)

            apply_state({"version": 1, "apps": []}, config)

            self.assertEqual(victim.read_text(encoding="utf-8"), "-- keep me\n")
            self.assertFalse(planted.is_symlink())
            self.assertTrue(planted.is_file())
            self.assertIn("Generated by", planted.read_text(encoding="utf-8"))

    def test_park_write_does_not_follow_planted_hyprland_lua_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            hypr = config / "hypr"
            hypr.mkdir()
            victim = config / "real-hyprland.lua"
            victim.write_text('require("hypr.autostart")\n-- keep me\n', encoding="utf-8")
            planted = hypr / "hyprland.lua"
            planted.symlink_to(victim)

            with self.assertRaises(OSError):
                apply_state({"version": 1, "apps": []}, config)

            self.assertEqual(
                victim.read_text(encoding="utf-8"),
                'require("hypr.autostart")\n-- keep me\n',
            )
            self.assertTrue(planted.is_symlink())
            self.assertFalse((hypr / "omavalet.lua").exists())


if __name__ == "__main__":
    unittest.main()
