import unittest
from pathlib import Path


class QmlSecurityTest(unittest.TestCase):
    def test_overlay_never_builds_direct_file_url_from_catalog_icon(self):
        overlay = (Path(__file__).resolve().parents[1] / "Overlay.qml").read_text(
            encoding="utf-8"
        )

        self.assertNotIn('return "file://" + name', overlay)
        self.assertIn('name = "application-x-executable"', overlay)

    def test_untrusted_app_and_window_names_use_plain_text(self):
        overlay = (Path(__file__).resolve().parents[1] / "Overlay.qml").read_text(
            encoding="utf-8"
        )
        untrusted_text = (
            "text: appName",
            "text: parkedChip.modelData.name",
            "root.selectedApp.name",
        )
        blocks = []
        start = 0
        while True:
            index = overlay.find("Text {", start)
            if index < 0:
                break
            depth = 0
            end = index
            while end < len(overlay):
                if overlay.startswith("{", end):
                    depth += 1
                elif overlay.startswith("}", end):
                    depth -= 1
                    if depth == 0:
                        end += 1
                        break
                end += 1
            blocks.append(overlay[index:end])
            start = index + 1

        named_blocks = [
            block
            for block in blocks
            if any(token in block for token in untrusted_text)
        ]
        self.assertGreaterEqual(len(named_blocks), 3)
        for block in named_blocks:
            self.assertIn("textFormat: Text.PlainText", block)


if __name__ == "__main__":
    unittest.main()
