"""Capture native QML previews with fictional assignments; never change user config."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    omarchy = Path(os.environ.get('OMARCHY_PATH', '/usr/share/omarchy'))
    cache = Path(os.environ.get('XDG_CACHE_HOME', str(Path.home() / '.cache')))
    cache.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='omavalet-preview-', dir=cache) as temporary:
        base = Path(temporary)
        harness = base / 'harness'
        plugin = harness / 'plugin'
        plugin.mkdir(parents=True)
        for path in source.glob('*.qml'):
            shutil.copy2(path, plugin / path.name)
        shutil.copy2(source / 'Model.js', plugin / 'Model.js')
        shutil.copytree(source / 'assets', plugin / 'assets')
        shutil.copy2(source / 'tests/capture_preview.qml', harness / 'shell.qml')
        for name in ('Commons', 'Ui', 'services'):
            (harness / name).symlink_to(omarchy / 'shell' / name, target_is_directory=True)
        runtime = base / 'runtime'
        runtime.mkdir(mode=0o700)
        live = {}
        for line in subprocess.check_output(['systemctl', '--user', 'show-environment'], text=True).splitlines():
            key, _, value = line.partition('=')
            if key in {'DISPLAY', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS'}:
                live[key] = value
        for theme, filename in [('everforest', 'board-dark.png'), ('catppuccin-latte', 'board-light.png')]:
            home = base / theme
            theme_path = home / '.local/state/omarchy/current/theme'
            theme_path.mkdir(parents=True)
            for name in ('colors.toml', 'shell.toml'):
                original = omarchy / 'themes' / theme / name
                if original.exists():
                    shutil.copy2(original, theme_path / name)
            env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'),
                       XDG_DATA_HOME=str(home / '.local/share'), XDG_CACHE_HOME=str(home / '.cache'),
                       XDG_DATA_DIRS='/usr/local/share:/usr/share', XDG_RUNTIME_DIR=str(runtime),
                       QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', QT_QPA_PLATFORMTHEME='gtk3',
                       OMAVALET_PREVIEW_OUTPUT=str(args.output_dir.resolve() / filename))
            # GTK's icon-theme bridge needs a display even while Qt renders offscreen.
            env.update(live)
            env.pop('HYPRLAND_INSTANCE_SIGNATURE', None)
            result = subprocess.run(['quickshell', '-p', str(harness)], env=env, text=True,
                                    capture_output=True, timeout=25)
            log = result.stdout + result.stderr
            (args.output_dir / (filename + '.log')).write_text(log)
            print(log)
            if result.returncode or 'PREVIEW_CAPTURE_PASS' not in log or 'PREVIEW_FAIL' in log:
                raise RuntimeError('Capture failed: ' + theme)


if __name__ == '__main__':
    main()
