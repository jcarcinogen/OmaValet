import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import omavalet


class CliTest(unittest.TestCase):
    def test_reset_cleans_state_and_reports_backup_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            hypr = config / "hypr"
            hypr.mkdir()
            (hypr / "hyprland.lua").write_text(
                'require("hypr.autostart")\n', encoding="utf-8"
            )
            omavalet.apply_state({"version": 1, "apps": []}, config)
            output = io.StringIO()

            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp}), mock.patch.object(
                omavalet, "_reload_hyprland"
            ) as reload_hyprland, redirect_stdout(output):
                exit_code = omavalet.main(["reset"])

            result = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertTrue(result["changed"])
            self.assertFalse(result["backupPreserved"])
            reload_hyprland.assert_called_once_with()


class RevealParkingTest(unittest.TestCase):
    def test_focuses_workspace_then_launches_the_parked_app(self):
        calls = []

        with mock.patch.object(omavalet, "_hyprctl_dispatch", calls.append):
            omavalet.reveal_parking({"workspace": 5, "exec": "telegram"})

        self.assertEqual(
            calls,
            [
                'hl.dsp.focus({ workspace = "5" })',
                'hl.dsp.exec_cmd("telegram")',
            ],
        )


if __name__ == "__main__":
    unittest.main()
