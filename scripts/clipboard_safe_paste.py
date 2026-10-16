#!/usr/bin/env python3
"""Read an explicitly requested Wayland paste outside the shared shell.

The child output is capped before decoding and every wait shares one deadline.
No clipboard contents are logged or written to disk. stderr is discarded.
"""
import ctypes
import json
import os
import selectors
import signal
import subprocess
import sys
import time

MAX_BYTES = 4096
DEADLINE_SECONDS = 1.5


class ClipboardError(Exception):
    """A bounded paste could not be completed."""


def read_clipboard(command=None, *, deadline_seconds=DEADLINE_SECONDS):
    # command is injectable by unit tests only; the CLI accepts no commands/args.
    if command is None:
        command = ['/usr/bin/wl-paste', '--no-newline', '--type', 'text/plain']
    deadline = time.monotonic() + deadline_seconds
    proc = None
    # Quickshell kills a Process on component destruction with SIGKILL. Finally
    # cannot run then: bind the direct wl-paste child to this helper on Linux.
    # This CLI is deliberately single-threaded, so a preexec hook is appropriate.
    parent_pid = os.getpid()
    libc = ctypes.CDLL(None, use_errno=True) if sys.platform == 'linux' else None
    if libc is not None:
        libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
        libc.prctl.restype = ctypes.c_int
    def bind_parent_lifetime():
        assert libc is not None
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
            os._exit(126)
        if os.getppid() != parent_pid:  # parent could die before prctl
            os._exit(126)
    try:
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                close_fds=True,
                                preexec_fn=bind_parent_lifetime if libc is not None else None)
        assert proc.stdout is not None
        os.set_blocking(proc.stdout.fileno(), False)
        content = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise ClipboardError('Clipboard timed out.')
                chunk = os.read(proc.stdout.fileno(), min(1024, MAX_BYTES + 1 - len(content)))
                if not chunk:
                    break
                content.extend(chunk)
                if len(content) > MAX_BYTES:
                    raise ClipboardError('Clipboard exceeds 4 KiB.')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ClipboardError('Clipboard timed out.')
        if proc.wait(timeout=remaining) != 0:
            raise ClipboardError('Clipboard text is unavailable.')
        try:
            text = content.decode('utf-8', errors='strict')
        except UnicodeDecodeError as exc:
            raise ClipboardError('Clipboard is not valid UTF-8 text.') from exc
        # Single-line plain text; normalize whitespace and discard control bytes.
        text = ' '.join(text.split())
        return ''.join(char for char in text if ord(char) >= 32 and not 127 <= ord(char) < 160)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ClipboardError('Clipboard text is unavailable or timed out.') from exc
    finally:
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            if proc.stdout is not None:
                proc.stdout.close()


def main():
    try:
        result = {'ok': True, 'text': read_clipboard()}
    except ClipboardError as exc:
        result = {'ok': False, 'error': str(exc)}
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
