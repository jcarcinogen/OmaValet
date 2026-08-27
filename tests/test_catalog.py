import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from omavalet import desktop_catalog, strip_exec


class DesktopCatalogTest(unittest.TestCase):
    def test_strips_desktop_exec_field_codes_without_losing_arguments(self):
        self.assertEqual(
            strip_exec('brave --profile-directory="Default" %U'),
            'brave --profile-directory="Default"',
        )

    def test_strips_trailing_field_code_dashes_from_exec(self):
        self.assertEqual(strip_exec("Telegram -- %U"), "Telegram")

    def test_ignores_placeholder_startup_wm_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "chromium.desktop").write_text(
                "[Desktop Entry]\nName=Chromium\nExec=/usr/bin/chromium %U\n"
                "StartupWMClass=@@startup_wm_class\nIcon=chromium\n",
                encoding="utf-8",
            )

            apps = desktop_catalog([directory])

        chromium = next(app for app in apps if app["desktopId"] == "chromium.desktop")
        self.assertEqual(chromium["class"], "chromium")
        self.assertEqual(chromium["exec"], "/usr/bin/chromium")

    def test_matches_startup_class_and_desktop_stem(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "org.telegram.desktop.desktop").write_text(
                "[Desktop Entry]\nName=Telegram\nExec=Telegram -- %U\n"
                "StartupWMClass=TelegramDesktop\nIcon=org.telegram.desktop\n",
                encoding="utf-8",
            )

            apps = desktop_catalog([directory])

        telegram = next(
            app for app in apps if app["desktopId"] == "org.telegram.desktop.desktop"
        )
        self.assertEqual(telegram["exec"], "Telegram")
        self.assertEqual(
            telegram["class"], "(TelegramDesktop|org.telegram.desktop|Telegram)"
        )

    def test_includes_flatpak_command_as_window_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "app.openbubbles.OpenBubbles.desktop").write_text(
                "[Desktop Entry]\nName=OpenBubbles\n"
                "Exec=/usr/bin/flatpak run --command=bluebubbles "
                "app.openbubbles.OpenBubbles\n"
                "StartupWMClass=openbubbles\nIcon=app.openbubbles.OpenBubbles\n",
                encoding="utf-8",
            )

            apps = desktop_catalog([directory])

        bubbles = next(
            app for app in apps if "openbubbles" in app["desktopId"].casefold()
        )
        self.assertIn("bluebubbles", bubbles["class"])
        self.assertIn("openbubbles", bubbles["class"])

    def test_includes_omarchy_agent(self):
        apps = desktop_catalog([])
        agent = next(app for app in apps if app["desktopId"] == "org.omarchy.agent.desktop")
        self.assertEqual(agent["name"], "Agent")
        self.assertEqual(agent["exec"], "omarchy-agent --pick")
        self.assertEqual(agent["class"], "org.omarchy.agent")

    def test_user_desktop_file_overrides_system_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            user_dir = root / "user"
            system_dir = root / "system"
            user_dir.mkdir()
            system_dir.mkdir()
            (system_dir / "browser.desktop").write_text(
                "[Desktop Entry]\nName=System Browser\nExec=browser %U\nIcon=browser\n",
                encoding="utf-8",
            )
            (user_dir / "browser.desktop").write_text(
                "[Desktop Entry]\nName=My Browser\nExec=browser --private %U\n"
                "Icon=browser-private\nStartupWMClass=browser-private\n",
                encoding="utf-8",
            )

            apps = desktop_catalog([user_dir, system_dir])

        browser = next(app for app in apps if app["desktopId"] == "browser.desktop")
        self.assertEqual(browser["name"], "My Browser")
        self.assertEqual(browser["exec"], "browser --private")
        self.assertEqual(browser["class"], "(browser-private|browser)")

    def test_hides_desktop_entries_not_intended_for_launchers(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "hidden.desktop").write_text(
                "[Desktop Entry]\nName=Hidden Helper\nExec=hidden-helper\nNoDisplay=true\n",
                encoding="utf-8",
            )

            self.assertFalse(
                any(app["desktopId"] == "hidden.desktop" for app in desktop_catalog([directory]))
            )

    def test_does_not_follow_replaceable_desktop_entry_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            applications = root / "applications"
            applications.mkdir()
            target = root / "outside.desktop"
            target.write_text(
                "[Desktop Entry]\nName=Outside\nExec=outside\n",
                encoding="utf-8",
            )
            (applications / "planted.desktop").symlink_to(target)

            apps = desktop_catalog([applications])

        self.assertFalse(any(app["desktopId"] == "planted.desktop" for app in apps))

    def test_ignores_oversized_desktop_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "oversized.desktop").write_text(
                "[Desktop Entry]\nName=Oversized\nExec=oversized\n" + " " * 262_144,
                encoding="utf-8",
            )

            apps = desktop_catalog([directory])

        self.assertFalse(any(app["desktopId"] == "oversized.desktop" for app in apps))


if __name__ == "__main__":
    unittest.main()
