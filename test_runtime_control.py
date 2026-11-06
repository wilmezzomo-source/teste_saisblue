import json
import tempfile
import threading
import time
import unittest

from runtime_control import Runtime
from waitress import create_server


class RuntimeControlTest(unittest.TestCase):
    def test_stop_file_closes_real_waitress_listener_without_public_control_route(self):
        with tempfile.TemporaryDirectory() as folder:
            server=create_server(lambda env,start: (start('200 OK',[('Content-Type','text/plain')]),[b'OK'])[1],host='127.0.0.1',port=0,threads=1)
            runtime=Runtime(folder,'app')
            stop=threading.Event()
            runtime.watch(server.close,stop)
            thread=threading.Thread(target=server.run,daemon=True);thread.start()
            runtime.stop_file.write_text('update')
            thread.join(timeout=5)
            stop.set();runtime.close()
            self.assertFalse(thread.is_alive())
            self.assertEqual(json.loads(runtime.state_file.read_text())['status'],'stopped')


if __name__=='__main__':unittest.main()
