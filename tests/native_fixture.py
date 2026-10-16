"""Isolated Qt-to-real-backend fixture; compositor and app launcher are explicit doubles."""
import os
from pathlib import Path
base = Path(os.environ['OMAVALET_TEST_ROOT'])
home = base/'integration-home'
config = home/'.config'
(config/'hypr').mkdir(parents=True,exist_ok=True)
(config/'hypr/hyprland.lua').write_text('require("hypr.autostart")\n')
(config/'hypr/autostart.lua').write_text('-- fixture only\n')
(config/'omarchy').mkdir(exist_ok=True)
(config/'omarchy/shell.json').write_text('{"plugins":[],"bar":{"layout":{"left":[],"center":[],"right":[{"id":"io.github.jcarcinogen.omavalet"}]}}}')
state=config/'omarchy/omavalet.json'
if state.exists(): state.unlink()
data=home/'.local/share/applications';data.mkdir(parents=True,exist_ok=True)
for name in ['alpha','beta','gamma']:
    (data/f'qa-{name}.desktop').write_text(f'[Desktop Entry]\nType=Application\nName=QA {name.title()}\nExec=qa-{name}\nStartupWMClass=qa-{name}\n')
bin=base/'bin';bin.mkdir(exist_ok=True)
(bin/'hyprctl').write_text('#!/usr/bin/python3\nimport json,sys\nargs=sys.argv[1:]\nif args==["-j","clients"]: print(json.dumps([{"address":"0xabc","class":"qa-special","title":"NEVER RETURN THIS"}]))\nelif args==["reload"]: print("ok")\nelif args==["configerrors"]: pass\nelif args==["-j","getoption","animations:enabled"]: print("{\\"int\\":1}")\nelse: sys.exit(2)\n')
(bin/'uwsm-app').write_text('#!/usr/bin/python3\nimport json,os,sys\nfrom pathlib import Path\nPath(os.environ["HOME"],"launch-request.json").write_text(json.dumps(sys.argv[1:]))\n')
for file in bin.iterdir():file.chmod(0o700)
# Paste doubles exercise QML routing/stale results without reading any clipboard.
for name, delay, result, code in [
    ('paste-ok.py', 0, '{"ok":true,"text":"QA"}', 0),
    ('paste-slow.py', 0.25, '{"ok":true,"text":"QA"}', 0),
    ('paste-error.py', 0, '{"ok":false,"error":"fixture failure"}', 1),
]:
    (base/name).write_text(f'import time\ntime.sleep({delay})\nprint({result!r})\nraise SystemExit({code})\n')
print('Prepared isolated fixture:',home)
