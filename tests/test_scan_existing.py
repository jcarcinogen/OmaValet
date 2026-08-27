import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from omavalet import scan_existing


class ExistingParkingTest(unittest.TestCase):
    def test_finds_launches_and_existing_workspace_parking(self):
        result = scan_existing(
            'o.launch_on_start("flatpak run app.openbubbles.OpenBubbles")\n'
            'o.launch_on_start("hyprpm reload -n")\n',
            {
                "hyprland.lua": (
                    'o.window("bluebubbles", { workspace = "5 silent" })\n'
                    'o.window("brave-grok.com__-Default", { workspace = "4" })\n'
                )
            },
        )

        self.assertEqual(
            result["launches"],
            [
                {
                    "exec": "flatpak run app.openbubbles.OpenBubbles",
                    "source": "autostart.lua",
                },
                {"exec": "hyprpm reload -n", "source": "autostart.lua"},
            ],
        )
        self.assertEqual(
            result["parking"],
            [
                {
                    "class": "brave-grok.com__-Default",
                    "workspace": 4,
                    "silent": False,
                    "source": "hyprland.lua",
                },
                {
                    "class": "bluebubbles",
                    "workspace": 5,
                    "silent": True,
                    "source": "hyprland.lua",
                },
            ],
        )

    def test_ignores_commented_valet_calls(self):
        result = scan_existing(
            '-- o.launch_on_start("not-running")\n'
            'o.launch_on_start("running")\n',
            {
                "hyprland.lua": (
                    '-- o.window("qemu", { workspace = "5" })\n'
                    'o.window("firefox", { workspace = "2 silent" }) -- keep\n'
                )
            },
        )

        self.assertEqual(
            result["launches"],
            [{"exec": "running", "source": "autostart.lua"}],
        )
        self.assertEqual(len(result["parking"]), 1)
        self.assertEqual(result["parking"][0]["class"], "firefox")

    def test_does_not_bind_workspace_from_a_later_window_rule(self):
        result = scan_existing(
            "",
            {
                "hyprland.lua": (
                    'o.window("foot", { opacity = 0.95 })\n'
                    'o.window("firefox", { workspace = "2 silent" })\n'
                )
            },
        )

        self.assertEqual(
            result["parking"],
            [
                {
                    "class": "firefox",
                    "workspace": 2,
                    "silent": True,
                    "source": "hyprland.lua",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
