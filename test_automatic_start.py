import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from automatic_start import is_enabled, set_enabled, task_identity, task_prelude, task_status
from desktop_worker import UpdateError, WindowsOps, process_roles, update_lock
from update_windows import settings
from supervise_crm import Supervisor


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        (self.root/'.env').write_text('NGROK_AUTHTOKEN=private-fixture\n')
        self.now=1000
        self.owned={}
        self.ops=SimpleNamespace(root=self.root,values={},healthy=True,spawned=[],killed=[],stopped=0)
        self.ops.snapshot=lambda: {}
        self.ops.health=lambda:self.ops.healthy
        self.ops.spawn=lambda script,args,role:self.ops.spawned.append(role)
        self.ops.kill=lambda record:self.ops.killed.append(record)
        def reload():self.ops.values=settings(self.root/'.env')
        self.ops.reload=reload
        def stop():self.ops.stopped+=1
        self.ops.stop=stop
        self.roles=patch('supervise_crm.process_roles',side_effect=lambda *args:self.owned).start()
        self.monitor=Supervisor(self.ops,clock=lambda:self.now)

    def tearDown(self):
        patch.stopall();self.temp.cleanup()

    def state(self):return json.loads((self.root/'.runtime/supervisor.json').read_text())

    def test_manual_stop_survives_new_supervisor_and_reboot_until_explicit_start(self):
        set_enabled(self.root,False)
        self.assertFalse(is_enabled(self.root))
        Supervisor(self.ops).cycle()
        self.assertEqual(self.state()['status'],'paused')
        self.assertEqual(self.ops.spawned,[])
        set_enabled(self.root,True)
        self.monitor.cycle()
        self.assertEqual(self.ops.spawned,['https'])
        self.assertNotIn('private-fixture',str(self.state()))

    def test_crashed_app_restarts_and_internet_retry_backs_off_to_five_minutes(self):
        self.ops.healthy=False
        self.monitor.cycle()
        self.monitor.cycle()
        self.assertEqual(self.ops.spawned,['app'])
        delays=[]
        for _ in range(8):
            delays.append(self.monitor.next['app']-self.now)
            self.now=self.monitor.next['app']
            self.monitor.cycle()
        self.assertEqual(delays,[15,30,60,120,240,300,300,300])

    def test_slow_or_single_missed_health_does_not_spawn_duplicate_or_kill(self):
        self.ops.healthy=False
        self.owned={7:({'pid':7},'app')}
        for _ in range(2):
            self.monitor.cycle();self.now+=30
        self.assertEqual(self.ops.spawned,[])
        self.assertEqual(self.ops.stopped,0)
        self.monitor.cycle()
        self.assertEqual(self.ops.stopped,1)
        self.assertEqual(self.ops.spawned,['app'])

    def test_update_lock_prevents_restarts_during_copy_and_rollback(self):
        with update_lock(self.root):
            with self.assertRaises(UpdateError):self.monitor.cycle()
        self.assertEqual(self.ops.spawned,[])
        self.monitor.cycle()
        self.assertEqual(self.ops.spawned,['https'])

    def test_only_one_supervisor_can_run_per_installation(self):
        with update_lock(self.root,'supervisor'):
            with self.assertRaises(UpdateError):
                with update_lock(self.root,'supervisor'):pass
            with update_lock(self.root):pass

    def test_healthy_connection_not_duplicated_and_stuck_controller_recovered(self):
        self.owned={5:({'pid':5},'https'),6:({'pid':6},'ngrok')}
        (self.root/'.runtime').mkdir()
        marker=self.root/'.runtime/https.json'
        marker.write_text(json.dumps({'pid':5,'status':'ready'}))
        self.monitor.cycle()
        self.assertEqual(self.state()['status'],'running')
        self.assertEqual(self.ops.spawned,[])
        marker.write_text(json.dumps({'pid':5,'status':'starting'}))
        self.now+=121
        self.monitor.cycle()
        self.assertEqual(self.ops.killed,[{'pid':6},{'pid':5}])

    def test_orphan_agent_cleaned_before_creating_another_tunnel(self):
        self.owned={6:({'pid':6},'ngrok')}
        self.monitor.cycle()
        self.assertEqual(self.ops.killed,[{'pid':6}])
        self.assertEqual(self.ops.spawned,['https'])

    def test_damaged_stop_record_fails_closed_and_separate_proxy_is_untouched(self):
        set_enabled(self.root,False)
        (self.root/'.runtime/automatic-control.json').write_text('{broken')
        self.assertFalse(is_enabled(self.root))
        set_enabled(self.root,True)
        (self.root/'.env').write_text('CRM_LISTEN_HOST=127.0.0.1\n')
        self.monitor.cycle()
        self.assertEqual(self.ops.spawned,[])
        self.assertEqual(self.state()['connection'],'managed_separately')


class StartupScopeTest(unittest.TestCase):
    def test_monitor_reloads_local_address_without_querying_public_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            config=root/'.env'
            ops=WindowsOps(root,{'CRM_LISTEN_HOST':'127.0.0.1'})
            config.write_text('CRM_LISTEN_HOST=192.168.0.219\n')
            ops.reload()
            self.assertEqual(ops.base,'http://192.168.0.219:3000')
            config.write_text('CRM_LISTEN_HOST=8.8.8.8\n')
            with self.assertRaises(UpdateError):ops.reload()
            self.assertEqual(ops.base,'http://192.168.0.219:3000')

    def test_task_scoped_to_installation_and_requires_limited_noninteractive_identity(self):
        first=task_identity(Path('/tmp/CRM one'))
        second=task_identity(Path('/tmp/CRM two'))
        self.assertNotEqual(first[0],second[0])
        code=task_prelude(Path('/tmp/CRM one'))
        self.assertIn('$match=',code)
        self.assertIn('Arguments -ceq $crmArgs',code)
        ops=SimpleNamespace(root=Path('/tmp/CRM one'),powershell=lambda code:{'enabled':False,'running':False})
        self.assertFalse(task_status(ops)['enabled'])

    def test_orphan_requires_own_binary_exact_gateway_and_own_agent_config(self):
        root=r'C:\SaisBlue CRM'
        own={'pid':6,'parent':999,'exe':root+r'\tools\ngrok.exe','command':'"'+root+r'\tools\ngrok.exe" http http://127.0.0.1:3002 "--config='+root+r'\.runtime\ngrok.yml"'}
        self.assertEqual(process_roles({'processes':[own],'ports':[]},root)[6][1],'ngrok')
        for command in (own['command'].replace('3002','8000'),own['command'].replace('ngrok.yml','another.yml')):
            self.assertEqual(process_roles({'processes':[{**own,'command':command}],'ports':[]},root),{})


if __name__=='__main__':unittest.main()
