import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import omavalet


LEGACY_MENU = (
    '\n  // omavalet:menu-begin\n'
    '  "omavalet": {\n'
    '    "icon": "\U000f04c3",\n'
    '    "label": "OmaValet",\n'
    '    "description": "Park apps on workspaces",\n'
    '    "action": "omarchy-shell shell toggle io.github.jcarcinogen.omavalet"\n'
    '  },\n'
    '  // omavalet:menu-end\n'
)


class RebrandingTest(unittest.TestCase):
    def test_brand_changes_without_changing_install_identity(self):
        manifest = json.loads((ROOT / "manifest.json").read_text())
        self.assertEqual(manifest["name"], "Workspace Pins")
        self.assertEqual(manifest["barWidget"]["displayName"], "Workspace Pins")
        self.assertEqual(manifest["id"], "io.github.jcarcinogen.omavalet")
        self.assertEqual(omavalet.PLUGIN_ID, manifest["id"])
        self.assertEqual(omavalet.LOADER_REQUIRE, 'require("hypr.omavalet")')
        self.assertIn("https://github.com/jcarcinogen/OmaValet.git", (ROOT / "README.md").read_text())
        self.assertIn('"label": "Workspace Pins"', omavalet.MENU_BLOCK)
        self.assertIn('"icon": "\U000f0403"', omavalet.MENU_BLOCK)

    def test_exact_legacy_menu_upgrades_idempotently(self):
        original = '{' + LEGACY_MENU + '  "personal": {"label": "Keep me"}\n}\n'
        self.assertEqual(omavalet.LEGACY_MENU_BLOCK, LEGACY_MENU)
        updated = omavalet.install_menu_entry(original)
        self.assertEqual(updated, original.replace(LEGACY_MENU, omavalet.MENU_BLOCK))
        self.assertEqual(omavalet.install_menu_entry(updated), updated)
        self.assertEqual(omavalet.remove_menu_entry(updated), omavalet.remove_menu_entry(original))

    def test_customized_legacy_menu_is_not_rebranded(self):
        original = '{' + LEGACY_MENU.replace('"label": "OmaValet"', '"label": "My apps"') + '}\n'
        self.assertEqual(omavalet.install_menu_entry(original), original)

    def test_unmarked_legacy_menu_is_not_rebranded(self):
        original = '{\n  "omavalet": {"label": "OmaValet", "action": "my-command"}\n}\n'
        self.assertEqual(omavalet.install_menu_entry(original), original)


if __name__ == "__main__":
    unittest.main()
