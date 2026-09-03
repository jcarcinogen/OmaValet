import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PluginContractTest(unittest.TestCase):
    def test_bar_widget_proxies_to_the_shell_owned_overlay(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        bar_widget = (ROOT / "BarWidget.qml").read_text(encoding="utf-8")

        self.assertEqual(manifest["kinds"], ["bar-widget", "overlay"])
        self.assertEqual(manifest["entryPoints"]["barWidget"], "BarWidget.qml")
        self.assertEqual(manifest["entryPoints"]["overlay"], "Overlay.qml")
        self.assertEqual(manifest["barWidget"]["defaultSection"], "right")
        self.assertIn("root.bar.shell.toggle(root.moduleName", bar_widget)
        self.assertNotIn("Loader {", bar_widget)
        self.assertNotIn("IpcHandler {", bar_widget)

    def test_overlay_exposes_bar_and_menu_access_controls(self):
        overlay = (ROOT / "Overlay.qml").read_text(encoding="utf-8")

        self.assertIn('property string accessMode: "bar"', overlay)
        self.assertIn('["python3", scriptPath, "access", mode]', overlay)
        self.assertIn('text: "OPEN OmaValet FROM"', overlay)
        self.assertIn('text: "Bar"', overlay)
        self.assertIn('text: "Menu"', overlay)
        self.assertIn("snapshot.accessMode", overlay)


if __name__ == "__main__":
    unittest.main()
