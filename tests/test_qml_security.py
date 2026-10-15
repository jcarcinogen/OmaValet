import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class QmlSecurityTest(unittest.TestCase):
    def test_icons_are_theme_names_only(self):
        model = (ROOT / "Model.js").read_text()
        tile = (ROOT / "AppTile.qml").read_text()
        self.assertIn('name.indexOf("/")', model)
        self.assertIn('name.indexOf(":")', model)
        self.assertIn('name = "application-x-executable"', model)
        self.assertIn('Quickshell.iconPath(Model.iconName(tile.appData.icon), true)', tile)
        self.assertNotIn('"file://" +', tile)

    def test_dynamic_text_is_plain(self):
        count = 0
        for name in ("Board.qml", "AppTile.qml", "ValetButton.qml", "Celebration.qml"):
            text = (ROOT / name).read_text()
            start = 0
            while True:
                start = text.find("Text {", start)
                if start < 0:
                    break
                depth, end = 0, start
                while end < len(text):
                    if text[end] == "{": depth += 1
                    elif text[end] == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    end += 1
                block = text[start:end]
                if any(token in block for token in ("root.", "tile.", "control.text")):
                    self.assertIn("textFormat: Text.PlainText", block, (name, block))
                    count += 1
                start += 1
        self.assertGreaterEqual(count, 10)

    def test_commands_use_argv_and_cameo_is_local(self):
        board = (ROOT / "Board.qml").read_text()
        cameo = (ROOT / "Celebration.qml").read_text()
        self.assertIn('["python3", scriptPath].concat(args)', board)
        self.assertNotIn('"bash"', board)
        self.assertNotIn("http", cameo)
        self.assertNotIn("MouseArea", cameo)
        self.assertNotIn("PanelWindow", cameo)
        self.assertIn("active: !cameo.reducedMotion", cameo)

if __name__ == "__main__":
    unittest.main()
