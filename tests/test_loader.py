import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from omavalet import install_loader, remove_loader


class LoaderTest(unittest.TestCase):
    def test_installs_loader_after_autostart_and_only_once(self):
        original = (
            'require("hypr.bindings")\n'
            'require("hypr.autostart")\n'
            'require("default.hypr.toggles")\n'
        )

        installed = install_loader(original)
        installed_again = install_loader(installed)

        self.assertEqual(installed, installed_again)
        self.assertEqual(installed.count('require("hypr.omavalet")'), 1)
        self.assertLess(
            installed.index('require("hypr.autostart")'),
            installed.index('require("hypr.omavalet")'),
        )
        self.assertLess(
            installed.index('require("hypr.omavalet")'),
            installed.index('require("default.hypr.toggles")'),
        )

    def test_removal_only_takes_the_marked_loader_block(self):
        installed = install_loader('require("hypr.autostart")\n-- keep me\n')

        self.assertEqual(
            remove_loader(installed), 'require("hypr.autostart")\n-- keep me\n'
        )


if __name__ == "__main__":
    unittest.main()
