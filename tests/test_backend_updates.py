import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import omavalet as ov


class BackendUpdates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / 'config'
        (self.config / 'hypr').mkdir(parents=True)
        (self.config / 'hypr/hyprland.lua').write_text('require("hypr.autostart")\n-- personal\n')
        (self.config / 'hypr/autostart.lua').write_text('-- untouched\n')
        apps = self.root / 'data/applications'
        apps.mkdir(parents=True)
        for name in ('alpha','beta','gamma','delta'):
            (apps / (name+'.desktop')).write_text('[Desktop Entry]\nType=Application\nName='+name+'\nExec='+name+' --test\nStartupWMClass='+name+'\n')
        self.env = patch.dict(os.environ, {'XDG_CONFIG_HOME':str(self.config),'XDG_DATA_HOME':str(self.root/'data'),'XDG_DATA_DIRS':str(self.root/'none'),'HYPRLAND_INSTANCE_SIGNATURE':''})
        self.env.start(); self.addCleanup(self.env.stop)
        self.reload = patch.object(ov,'_reload_hyprland').start()
        self.addCleanup(patch.stopall)
        self.state_path = self.config/'omarchy/omavalet.json'

    def call(self,*args,ok=True):
        stream=io.StringIO()
        with redirect_stdout(stream): code=ov.main(list(args))
        result=json.loads(stream.getvalue())
        self.assertEqual(code,0 if ok else 1,result)
        return result

    def park(self,name='alpha',ws='1',**kw):
        return self.call('park',name+'.desktop',ws,**kw)

    def test_structured_success_and_no_implicit_launch(self):
        with patch.object(ov.subprocess,'Popen') as launch:
            result=self.park()
            launch.assert_not_called()
        self.assertTrue(result['saved']);self.assertTrue(result['applied'])
        self.assertFalse(result['celebrate'])
        self.assertTrue(result['snapshot']['undoAvailable'])
        self.assertFalse(result['snapshot']['valet'][0]['launchOnStart'])
        self.assertEqual((self.config/'hypr/autostart.lua').read_text(),'-- untouched\n')

    def test_reload_failure_retry_preserves_undo(self):
        self.reload.side_effect=RuntimeError('fixture reload failed')
        failed=self.park(ok=False)
        self.assertTrue(failed['saved']);self.assertFalse(failed['applied'])
        undo=json.loads(self.state_path.read_text())['undo']
        self.reload.side_effect=None
        good=self.call('retry')
        self.assertTrue(good['applied'])
        self.assertEqual(json.loads(self.state_path.read_text())['undo'],undo)
        self.assertFalse(good['snapshot']['applyPending'])

    def test_undo_is_single_level(self):
        self.park();self.park('beta','2')
        result=self.call('undo')
        self.assertEqual([a['desktopId'] for a in result['snapshot']['valet']],['alpha.desktop'])
        self.assertFalse(result['snapshot']['undoAvailable'])
        self.call('undo',ok=False)

    def test_settings_do_not_replace_undo_or_reload(self):
        self.park(); before=json.loads(self.state_path.read_text())['undo']
        self.reload.reset_mock()
        result=self.call('settings','reduced-motion','on')
        self.assertTrue(result['snapshot']['settings']['reducedMotion'])
        self.reload.assert_not_called()
        self.assertEqual(json.loads(self.state_path.read_text())['undo'],before)
        self.assertTrue(self.call('undo')['snapshot']['settings']['reducedMotion'])

    def test_celebration_once_not_on_failure_or_undo(self):
        self.park();self.park('beta','2')
        self.reload.side_effect=RuntimeError('no compositor')
        self.assertFalse(self.park('gamma','3',ok=False)['celebrate'])
        self.reload.side_effect=None
        self.assertTrue(self.call('retry')['celebrate'])
        self.call('undo')
        self.assertFalse(self.park('gamma','3')['celebrate'])
        self.assertTrue(json.loads(self.state_path.read_text())['celebratedThree'])

    def test_celebrations_disabled(self):
        self.call('settings','celebrations','off')
        self.park();self.park('beta','2')
        self.assertFalse(self.park('gamma','3')['celebrate'])

    def test_move_preserves_login_preference(self):
        self.park();self.call('boot','alpha.desktop','on')
        self.assertTrue(self.park('alpha','4')['snapshot']['valet'][0]['launchOnStart'])

    def test_corrupt_state_never_overwritten(self):
        self.state_path.parent.mkdir(parents=True)
        self.state_path.write_text('{bad json')
        for args in [('park','alpha.desktop','1'),('settings','celebrations','off'),('reset',),('snapshot',)]:
            self.call(*args,ok=False)
            self.assertEqual(self.state_path.read_text(),'{bad json')
        self.reload.assert_not_called()

    def test_invalid_state_structure(self):
        self.state_path.parent.mkdir(parents=True)
        self.state_path.write_text(json.dumps({'apps':[None]}))
        self.call('snapshot',ok=False)
        self.call('park','alpha.desktop','1',ok=False)
        self.assertEqual(json.loads(self.state_path.read_text()),{'apps':[None]})

    def test_bad_arguments_are_json(self):
        self.call('park','alpha.desktop','eleven',ok=False)
        self.call('park','alpha.desktop','11',ok=False)
        self.call('settings','unknown','on',ok=False)
        self.assertFalse(self.state_path.exists())

    def test_running_never_returns_titles(self):
        with patch.object(ov,'_hypr_command',return_value=json.dumps([{'address':'0xabc','class':'alpha','title':'SECRET','initialTitle':'SECRET'}])):
            result=self.call('running')
        self.assertEqual(result['windows'],[{'address':'0xabc','class':'alpha','name':'alpha'}])
        self.assertNotIn('SECRET',json.dumps(result))

    def test_identification_exact_and_persistent(self):
        self.park()
        with patch.object(ov,'running_windows',return_value=[{'address':'0xabc','class':'special.app+','name':'special.app+'}]):
            result=self.call('identify','alpha.desktop','0xabc','special.app+')
        self.assertEqual(result['snapshot']['valet'][0]['class'],r'^special\.app\+$')
        self.call('boot','alpha.desktop','on')
        result=self.park('alpha','4')
        self.assertEqual(result['snapshot']['valet'][0]['class'],r'^special\.app\+$')

    def test_identify_rejects_stale_window(self):
        self.park(); before=self.state_path.read_text()
        with patch.object(ov,'running_windows',return_value=[{'address':'0xabc','class':'changed','name':'changed'}]):
            self.call('identify','alpha.desktop','0xabc','alpha',ok=False)
        self.assertEqual(self.state_path.read_text(),before)

    def test_identify_rejects_user_and_other_app_conflicts(self):
        self.park();self.park('beta','2')
        with patch.object(ov,'running_windows',return_value=[{'address':'0xabc','class':'beta','name':'beta'}]):
            self.call('identify','alpha.desktop','0xabc','beta',ok=False)
        (self.config/'hypr/windows.lua').write_text('o.window("reserved", { workspace = "4" })\n')
        with patch.object(ov,'running_windows',return_value=[{'address':'0xabc','class':'reserved','name':'reserved'}]):
            self.call('identify','alpha.desktop','0xabc','reserved',ok=False)

    def test_undo_preserves_intervening_assignment_edit(self):
        self.park()
        state=json.loads(self.state_path.read_text())
        state["apps"][0]["workspace"]=4
        self.state_path.write_text(json.dumps(state))
        before=self.state_path.read_text()
        self.assertFalse(self.call("snapshot")["undoAvailable"])
        self.call("undo",ok=False)
        self.assertEqual(self.state_path.read_text(),before)

    def test_pending_noop_does_not_report_applied(self):
        self.reload.side_effect=RuntimeError('offline')
        self.park(ok=False)
        self.reload.reset_mock()
        result=self.park(ok=False)
        self.assertFalse(result['applied'])
        self.assertTrue(result['saved'])
        self.reload.assert_not_called()

    def test_undo_cannot_replace_preferences(self):
        self.park()
        state=json.loads(self.state_path.read_text())
        state['undo']['settings']={'celebrations':False}
        self.state_path.write_text(json.dumps(state))
        before=self.state_path.read_text()
        self.call('undo',ok=False)
        self.assertEqual(self.state_path.read_text(),before)

    def test_explicit_launch_argv(self):
        with patch.object(ov.subprocess,'Popen') as launch:
            self.call('test-launch','alpha.desktop')
        self.assertEqual(launch.call_args.args[0],['uwsm-app','--','alpha','--test'])
        self.assertFalse(self.state_path.exists())

    def test_reset_preserves_milestone_and_undo(self):
        self.park();self.park('beta','2');self.park('gamma','3')
        result=self.call('reset')
        self.assertEqual(result['snapshot']['valet'],[])
        self.assertTrue(json.loads(self.state_path.read_text())['celebratedThree'])
        self.assertEqual(len(self.call('undo')['snapshot']['valet']),3)

    def test_symlink_lock_fails_closed(self):
        self.state_path.parent.mkdir(parents=True)
        victim=self.root/'victim';victim.write_text('untouched')
        (self.state_path.parent/'omavalet.lock').symlink_to(victim)
        self.park(ok=False)
        self.assertEqual(victim.read_text(),'untouched')
        self.assertFalse(self.state_path.exists())

    def test_real_reload_checks_return_code_and_errors(self):
        # Unwrap the method patched by setUp, then exercise its subprocess seam.
        patch.stopall()
        with patch.object(ov.subprocess,'run',return_value=subprocess.CompletedProcess([],7,'','denied')):
            with self.assertRaisesRegex(RuntimeError,'denied'):ov._reload_hyprland()
        results=[subprocess.CompletedProcess([],0,'ok',''),subprocess.CompletedProcess([],0,'bad Lua','')]
        with patch.object(ov.subprocess,'run',side_effect=results):
            with self.assertRaisesRegex(RuntimeError,'bad Lua'):ov._reload_hyprland()

if __name__=='__main__':unittest.main()
