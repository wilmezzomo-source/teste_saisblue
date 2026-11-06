"""Local process lifecycle files; no network control endpoint or credentials."""
import json
import os
from pathlib import Path
import threading
import time


def runtime_path(root, role, suffix):
    if role not in ('app', 'https') or suffix not in ('json', 'stop'):
        raise ValueError('Controle local inválido.')
    folder = Path(root) / '.runtime'
    folder.mkdir(exist_ok=True)
    return folder / (role + '.' + suffix)


class Runtime:
    def __init__(self, root, role):
        self.root, self.role = Path(root), role
        self.stop_file = runtime_path(root, role, 'stop')
        self.state_file = runtime_path(root, role, 'json')
        self.stop_file.unlink(missing_ok=True)
        self.update('starting')

    def update(self, status, **extra):
        state = {'pid': os.getpid(), 'status': status, 'updated': time.time(), **extra}
        temp = self.state_file.with_suffix('.tmp')
        temp.write_text(json.dumps(state), encoding='utf-8')
        os.replace(temp, self.state_file)

    def stop_requested(self):
        return self.stop_file.exists()

    def close(self):
        self.update('stopped')
        self.stop_file.unlink(missing_ok=True)

    def watch(self, callback, stop):
        def monitor():
            while not stop.wait(.25):
                if self.stop_requested():
                    callback()
                    break
        thread = threading.Thread(target=monitor, daemon=True, name='saisblue-local-control')
        thread.start()
        return thread
