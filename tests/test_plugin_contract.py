import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PluginContractTest(unittest.TestCase):
    def test_shell_owns_the_menu_only_overlay(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["kinds"], ["overlay"])
        self.assertEqual(manifest["entryPoints"]["overlay"], "Overlay.qml")
        self.assertNotIn("barWidget", manifest)
        self.assertFalse((ROOT / "BarWidget.qml").exists())


if __name__ == "__main__":
    unittest.main()
