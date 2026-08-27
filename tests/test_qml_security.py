import unittest
from pathlib import Path


class QmlSecurityTest(unittest.TestCase):
    def test_overlay_never_builds_direct_file_url_from_catalog_icon(self):
        overlay = (Path(__file__).resolve().parents[1] / "Overlay.qml").read_text(
            encoding="utf-8"
        )

        self.assertNotIn('return "file://" + name', overlay)
        self.assertIn('name = "application-x-executable"', overlay)


if __name__ == "__main__":
    unittest.main()
