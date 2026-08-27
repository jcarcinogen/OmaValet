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

        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]["name"], "My Browser")
        self.assertEqual(apps[0]["exec"], "browser --private")
        self.assertEqual(apps[0]["class"], "browser-private")

    def test_hides_desktop_entries_not_intended_for_launchers(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "hidden.desktop").write_text(
                "[Desktop Entry]\nName=Hidden Helper\nExec=hidden-helper\nNoDisplay=true\n",
                encoding="utf-8",
            )

            self.assertEqual(desktop_catalog([directory]), [])


if __name__ == "__main__":
    unittest.main()
