import io
import json
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import omavalet


class CliTest(unittest.TestCase):
    def test_menu_entry_is_marked_reversible_and_preserves_user_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            menu = config / "omarchy" / "extensions" / "omarchy-menu.jsonc"
            menu.parent.mkdir(parents=True)
            shell = config / "omarchy" / "shell.json"
            shell.write_text(
                json.dumps(
                    {
                        "plugins": [{"id": omavalet.PLUGIN_ID}],
                        "bar": {"layout": {"left": [], "center": [], "right": []}},
                    }
                ),
                encoding="utf-8",
            )
            original = '{\n  // keep this\n  "personal.notes": {"label": "Notes"},\n}\n'
            menu.write_text(original, encoding="utf-8")
            menu.chmod(0o644)

            first = omavalet.configure_menu_entry(config)
            second = omavalet.configure_menu_entry(config)
            installed = menu.read_text(encoding="utf-8")

            self.assertTrue(first["changed"])
            self.assertFalse(second["changed"])
            self.assertIn("// omavalet:menu-begin", installed)
            self.assertIn('"personal.notes"', installed)
            self.assertEqual(installed.count('"omavalet"'), 1)
            self.assertEqual(stat.S_IMODE(menu.stat().st_mode), 0o644)
            self.assertTrue(omavalet.cleanup_menu_entry(config))
            self.assertEqual(menu.read_text(encoding="utf-8"), original)
            self.assertFalse(
                menu.with_name("omarchy-menu.jsonc.omavalet.bak").exists()
            )

    def test_menu_install_does_not_replace_a_user_owned_entry(self):
        original = '{\n  "omavalet": {"label": "My Valet"}\n}\n'

        self.assertEqual(omavalet.install_menu_entry(original), original)

    def test_menu_entry_handles_leading_comments_and_removes_edited_owned_block(self):
        original = '// user heading\n{\n  "personal.notes": {},\n}\n'
        installed = omavalet.install_menu_entry(original)
        edited = installed.replace('"label": "OmaValet"', '"label": "My Valet"')

        self.assertTrue(installed.startswith("// user heading\n{"))
        self.assertEqual(omavalet.remove_menu_entry(edited), original)

    def test_menu_install_moves_bar_slot_to_overlay_list_without_losing_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            shell = config / "omarchy" / "shell.json"
            shell.parent.mkdir(parents=True)
            shell.write_text(
                json.dumps(
                    {
                        "plugins": [],
                        "bar": {
                            "layout": {
                                "left": [{"id": "omarchy.menu"}],
                                "center": [],
                                "right": [
                                    {"id": omavalet.PLUGIN_ID, "workspaceCount": 7},
                                    {"id": "omarchy.power"},
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            shell.chmod(0o640)

            self.assertTrue(omavalet.configure_shell_entry(config))
            migrated = json.loads(shell.read_text(encoding="utf-8"))
            self.assertEqual(
                migrated["plugins"],
                [{"id": omavalet.PLUGIN_ID, "workspaceCount": 7}],
            )
            self.assertEqual(
                migrated["bar"]["layout"]["right"], [{"id": "omarchy.power"}]
            )
            self.assertTrue(shell.with_name("shell.json.omavalet.bak").exists())
            self.assertEqual(stat.S_IMODE(shell.stat().st_mode), 0o640)
            self.assertFalse(omavalet.configure_shell_entry(config))
            self.assertTrue(omavalet.cleanup_shell_entry(config))
            cleaned = json.loads(shell.read_text(encoding="utf-8"))
            self.assertEqual(cleaned["plugins"], [])
            self.assertEqual(
                cleaned["bar"]["layout"]["right"], [{"id": "omarchy.power"}]
            )

    def test_access_toggle_moves_one_preserved_entry_between_bar_and_menu(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            omarchy_dir = config / "omarchy"
            menu = omarchy_dir / "extensions" / "omarchy-menu.jsonc"
            menu.parent.mkdir(parents=True)
            menu.write_text('{\n  "personal.notes": {},\n}\n', encoding="utf-8")
            shell = omarchy_dir / "shell.json"
            shell.write_text(
                json.dumps(
                    {
                        "plugins": [],
                        "bar": {
                            "layout": {
                                "left": [{"id": "omarchy.menu"}],
                                "center": [],
                                "right": [
                                    {"id": "omarchy.tray"},
                                    {"id": omavalet.PLUGIN_ID, "custom": "keep"},
                                    {"id": "omarchy.power"},
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            menu_result = omavalet.configure_access_mode(config, "menu")
            menu_config = json.loads(shell.read_text(encoding="utf-8"))

            self.assertEqual(menu_result["accessMode"], "menu")
            self.assertEqual(
                menu_config["plugins"],
                [{"id": omavalet.PLUGIN_ID, "custom": "keep"}],
            )
            self.assertFalse(
                any(
                    omavalet._entry_id(entry) == omavalet.PLUGIN_ID
                    for entries in menu_config["bar"]["layout"].values()
                    for entry in entries
                )
            )
            self.assertIn("// omavalet:menu-begin", menu.read_text(encoding="utf-8"))

            bar_result = omavalet.configure_access_mode(config, "bar")
            bar_config = json.loads(shell.read_text(encoding="utf-8"))
            right = bar_config["bar"]["layout"]["right"]

            self.assertEqual(bar_result["accessMode"], "bar")
            self.assertFalse(
                any(
                    omavalet._entry_id(entry) == omavalet.PLUGIN_ID
                    for entry in bar_config["plugins"]
                )
            )
            self.assertEqual(right[1], {"id": omavalet.PLUGIN_ID, "custom": "keep"})
            self.assertEqual(
                sum(
                    omavalet._entry_id(entry) == omavalet.PLUGIN_ID
                    for entries in bar_config["bar"]["layout"].values()
                    for entry in entries
                ),
                1,
            )
            self.assertNotIn("omavalet:menu-begin", menu.read_text(encoding="utf-8"))
            self.assertIn('"personal.notes"', menu.read_text(encoding="utf-8"))

    def test_access_toggle_rejects_unknown_mode_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            shell = config / "omarchy" / "shell.json"
            shell.parent.mkdir(parents=True)
            original = json.dumps({"plugins": [], "bar": {"layout": {}}})
            shell.write_text(original, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "access mode"):
                omavalet.configure_access_mode(config, "desktop")

            self.assertEqual(shell.read_text(encoding="utf-8"), original)

    def test_access_command_switches_to_menu_and_reports_the_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            omarchy = config / "omarchy"
            omarchy.mkdir()
            (omarchy / "shell.json").write_text(
                json.dumps(
                    {
                        "plugins": [],
                        "bar": {
                            "layout": {
                                "left": [],
                                "center": [],
                                "right": [{"id": omavalet.PLUGIN_ID}],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            output = io.StringIO()

            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp}), redirect_stdout(output):
                exit_code = omavalet.main(["access", "menu"])

            result = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(result["accessMode"], "menu")
            self.assertIn("omavalet:menu-begin", (omarchy / "extensions" / "omarchy-menu.jsonc").read_text())

    def test_reset_cleans_state_and_reports_backup_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            hypr = config / "hypr"
            hypr.mkdir()
            (hypr / "hyprland.lua").write_text(
                'require("hypr.autostart")\n', encoding="utf-8"
            )
            omavalet.apply_state({"version": 1, "apps": []}, config)
            output = io.StringIO()

            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp}), mock.patch.object(
                omavalet, "_reload_hyprland"
            ) as reload_hyprland, redirect_stdout(output):
                exit_code = omavalet.main(["reset"])

            result = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertTrue(result["changed"])
            self.assertFalse(result["backupPreserved"])
            reload_hyprland.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
