import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('clipboard_safe_paste', Path(__file__).resolve().parents[1] / 'scripts/clipboard_safe_paste.py')
assert SPEC is not None and SPEC.loader is not None
clipboard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(clipboard)


class ClipboardTest(unittest.TestCase):
    def read(self, code, deadline=0.4):
        return clipboard.read_clipboard([sys.executable, '-c', code], deadline_seconds=deadline)

    def test_text_normalized_without_interpreting_markup(self):
        self.assertEqual(self.read("print('  <b>café</b>\\n next\\tapp\\x00')"), '<b>café</b> next app')

    def test_empty_offer(self):
        self.assertEqual(self.read('pass'), '')

    def test_exact_byte_limit(self):
        self.assertEqual(len(self.read("import sys;sys.stdout.write('a'*4096)")), 4096)

    def test_oversize_rejected_not_truncated(self):
        with self.assertRaisesRegex(clipboard.ClipboardError, 'exceeds'):
            self.read("import sys;sys.stdout.write('a'*4097)")

    def test_utf8_limit_counts_bytes(self):
        with self.assertRaisesRegex(clipboard.ClipboardError, 'exceeds'):
            self.read("import sys;sys.stdout.buffer.write(('é'*2049).encode())")

    def test_invalid_utf8_rejected(self):
        with self.assertRaisesRegex(clipboard.ClipboardError, 'UTF-8'):
            self.read("import sys;sys.stdout.buffer.write(b'\\xff')")

    def test_nonzero_exit_discards_partial_text(self):
        with self.assertRaises(clipboard.ClipboardError):
            self.read("import sys;print('partial');sys.exit(7)")

    def test_missing_executable(self):
        with self.assertRaises(clipboard.ClipboardError):
            clipboard.read_clipboard(['/nonexistent/workspace-pins-wl-paste'])

    def test_silent_child_deadline_and_reaped(self):
        original = subprocess.Popen
        children = []
        def capture(*args, **kwargs):
            child = original(*args, **kwargs)
            children.append(child)
            return child
        start = time.monotonic()
        with patch.object(clipboard.subprocess, 'Popen', side_effect=capture):
            with self.assertRaises(clipboard.ClipboardError):
                self.read('import time;time.sleep(10)', 0.15)
        self.assertLess(time.monotonic() - start, 1.5)
        self.assertIsNotNone(children[0].returncode)
        self.assertTrue(children[0].stdout.closed)

    def test_slow_drip_has_overall_deadline(self):
        start = time.monotonic()
        with self.assertRaises(clipboard.ClipboardError):
            self.read("import os,time\nfor i in range(200):\n os.write(1,b'a');time.sleep(.04)", 0.2)
        self.assertLess(time.monotonic() - start, 1.5)

    def test_eof_without_exit_has_deadline(self):
        start = time.monotonic()
        with self.assertRaises(clipboard.ClipboardError):
            self.read('import os,time;os.close(1);time.sleep(10)', 0.15)
        self.assertLess(time.monotonic() - start, 1.5)

    def test_stderr_flood_does_not_block_or_accumulate(self):
        self.assertEqual(self.read("import os;os.write(2,b'e'*1000000);os.write(1,b'ok')"), 'ok')

    @unittest.skipUnless(sys.platform == 'linux', 'Linux parent-death signal')
    def test_child_dies_when_helper_is_killed(self):
        import os
        import signal
        with tempfile.TemporaryDirectory() as temp:
            pid_file = Path(temp) / 'child.pid'
            child_code = f"import os,time;from pathlib import Path;Path({str(pid_file)!r}).write_text(str(os.getpid()));time.sleep(10)"
            parent_code = (
                "import importlib.util,sys;"
                f"s=importlib.util.spec_from_file_location('clip',{clipboard.__file__!r});"
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                f"m.read_clipboard([sys.executable,'-c',{child_code!r}],deadline_seconds=8)"
            )
            parent = subprocess.Popen([sys.executable, '-c', parent_code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            child_pid = None
            try:
                end = time.monotonic() + 2
                while not pid_file.exists() and time.monotonic() < end:
                    time.sleep(.01)
                self.assertTrue(pid_file.exists(), 'Child did not start')
                child_pid = int(pid_file.read_text())
                parent.kill(); parent.wait(timeout=1)
                stat = Path(f'/proc/{child_pid}/stat')
                end = time.monotonic() + 1
                while stat.exists() and stat.read_text().split(') ')[1][0] != 'Z' and time.monotonic() < end:
                    time.sleep(.01)
                self.assertTrue(not stat.exists() or stat.read_text().split(') ')[1][0] == 'Z', 'Orphan child remains running')
            finally:
                if parent.poll() is None: parent.kill(); parent.wait()
                if child_pid:
                    try: os.kill(child_pid, signal.SIGKILL)
                    except ProcessLookupError: pass

    def test_large_stream_stopped_promptly(self):
        start = time.monotonic()
        with self.assertRaisesRegex(clipboard.ClipboardError, 'exceeds'):
            self.read("import os\nwhile True: os.write(1,b'a'*8192)")
        self.assertLess(time.monotonic() - start, 1.5)


if __name__ == '__main__':
    unittest.main()
