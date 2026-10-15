"""Run real Quickshell/Qt tests in an isolated cache directory. No installs.

Default: offscreen UI + real Python helper with explicit compositor/launcher doubles.
--wayland: also briefly opens the real layer-shell overlay in the current session.
The real user's config is never passed to the test helper.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--wayland',action='store_true')
    args=parser.parse_args()
    source=Path(__file__).resolve().parents[1]
    host=Path(os.environ.get('OMARCHY_PATH','/usr/share/omarchy'))/'shell'
    if not shutil.which('quickshell') or not (host/'Commons').is_dir():
        raise SystemExit('Requires installed Omarchy/Quickshell and QtTest; no packages are installed automatically.')
    cache=Path(os.environ.get('XDG_CACHE_HOME',str(Path.home()/'.cache')))
    cache.mkdir(parents=True,exist_ok=True)
    base=Path(tempfile.mkdtemp(prefix='omavalet-qa-',dir=cache))
    harness=base/'harness';harness.mkdir()
    plugin=harness/'plugin';plugin.mkdir()
    for file in source.glob('*.qml'):shutil.copy2(file,plugin/file.name)
    shutil.copy2(source/'Model.js',plugin/'Model.js')
    shutil.copytree(source/'assets',plugin/'assets')
    shutil.copytree(source/'scripts',plugin/'scripts',ignore=shutil.ignore_patterns('__pycache__'))
    for name in ['Commons','Ui','services']:(harness/name).symlink_to(host/name,target_is_directory=True)
    runtime=base/'runtime';runtime.mkdir(mode=0o700)
    fixture_env=dict(os.environ,OMAVALET_TEST_ROOT=str(base))
    subprocess.run([sys.executable,str(source/'tests/native_fixture.py')],env=fixture_env,check=True)
    env=dict(os.environ)
    for key in ['WAYLAND_DISPLAY','DISPLAY','HYPRLAND_INSTANCE_SIGNATURE']:env.pop(key,None)
    env.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',HOME=str(base/'integration-home'),
               XDG_CONFIG_HOME=str(base/'integration-home/.config'),XDG_DATA_HOME=str(base/'integration-home/.local/share'),
               XDG_DATA_DIRS=str(base/'empty'),XDG_RUNTIME_DIR=str(runtime),OMARCHY_PATH=str(host.parent),
               PATH=str(base/'bin')+':'+env['PATH'],OMAVALET_TEST_OUTPUT=str(base))
    print('Evidence:',base,flush=True)
    def run(name,marker,test_env):
        shutil.copy2(source/'tests'/name,harness/'shell.qml')
        result=subprocess.run(['quickshell','-p',str(harness)],env=test_env,text=True,capture_output=True,timeout=40)
        text=result.stdout+result.stderr
        (base/(name+'.log')).write_text(text)
        print(text,flush=True)
        if result.returncode or marker not in text or re.search(r'(?:NATIVE|INTEGRATION|WAYLAND_OVERLAY)_FAIL',text):
            raise RuntimeError('Native test failed: '+name)
        if name=='native_ui.qml':
            match=re.search(r'NATIVE_RESULT (\{[^\n]+\})',text)
            if not match or json.loads(match.group(1))['failed']!=0:raise RuntimeError('Missing/failed UI result')
    run('native_ui.qml','NATIVE_RESULT',env)
    run('native_integration.qml','INTEGRATION_PASS',env)
    launch=json.loads((base/'integration-home/launch-request.json').read_text())
    assert launch==['--','qa-alpha'],launch
    if args.wayland:
        live=dict(os.environ)
        for line in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines():
            key,_,value=line.partition('=')
            if key in {'WAYLAND_DISPLAY','DISPLAY','HYPRLAND_INSTANCE_SIGNATURE','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS'}:live[key]=value
        assert live.get('WAYLAND_DISPLAY') and live.get('HYPRLAND_INSTANCE_SIGNATURE'),'No live Wayland session'
        hypr=shutil.which('hyprctl')
        assert hypr, 'hyprctl is not installed'
        def layers():
            data=json.loads(subprocess.check_output([hypr,'-j','layers'],env=live,text=True))
            return sum(1 for mon in data.values() for group in mon.get('levels',{}).values() for layer in group if layer.get('namespace')=='omavalet')
        assert layers()==0,'Existing Workspace Pins overlay is open; refusing to overlap it'
        wayland=dict(env)
        for key in ['WAYLAND_DISPLAY','DISPLAY','HYPRLAND_INSTANCE_SIGNATURE','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS']:
            if key in live:wayland[key]=live[key]
        wayland.pop('QT_QPA_PLATFORM',None);wayland.pop('QT_QUICK_BACKEND',None)
        try:run('native_overlay.qml','WAYLAND_OVERLAY_PASS',wayland)
        finally:assert layers()==0,'Test left an exclusive keyboard layer'
        print('Wayland overlay input layer cleaned up: PASS')
    print('NATIVE_SUITE_PASS',base)


if __name__=='__main__':main()
