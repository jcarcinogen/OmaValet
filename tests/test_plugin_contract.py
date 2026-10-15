import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PluginContractTest(unittest.TestCase):
    def test_header_and_bar_use_the_pin_glyph(self):
        for filename in ("Board.qml", "BarWidget.qml"):
            source = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn('text: "\U000f0403"', source)
            self.assertNotIn("\U000f04c3", source)

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
        board = (ROOT / "Board.qml").read_text(encoding="utf-8")
        overlay = (ROOT / "Overlay.qml").read_text(encoding="utf-8")
        self.assertIn('source: "Board.qml"', overlay)
        self.assertIn('property string accessMode: "bar"', board)
        self.assertIn('["access", mode]', board)
        self.assertIn('["python3", scriptPath].concat(args)', board)
        self.assertIn('text: "OPEN Workspace Pins FROM"', board)
        self.assertIn('text: "Bar"', board)
        self.assertIn('text: "Menu"', board)
        self.assertIn("value.accessMode", board)


if __name__ == "__main__":
    unittest.main()
