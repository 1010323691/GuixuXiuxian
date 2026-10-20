"""Black-box harness: each test owns its server and temporary save directory."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


class Server:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(prefix='guixu-qa-')
        self.data = Path(self.temp.name)
        self.proc = None

    def start(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.url = f'http://127.0.0.1:{port}'
        self.log = tempfile.TemporaryFile(mode='w+')
        self.proc = subprocess.Popen(
            [sys.executable, str(ROOT / 'server.py'), '--host', '127.0.0.1',
             '--port', str(port), '--data-dir', str(self.data)],
            cwd=ROOT, stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                self.log.seek(0)
                raise RuntimeError('server exited: ' + self.log.read())
            try:
                status, body = self.request('GET', '/api/health')
                if status == 200 and body['ok']:
                    return self
            except (OSError, ValueError):
                pass
            time.sleep(.05)
        raise RuntimeError('server readiness timeout')

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        if getattr(self, 'log', None):
            self.log.close()

    def close(self):
        self.stop()
        self.temp.cleanup()

    def request(self, method, path, payload=None, headers=None, raw=None):
        data = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
        request = urllib.request.Request(self.url + path, data=data, method=method,
            headers={'Content-Type': 'application/json', 'X-Game-Client': 'guixu-web', **(headers or {})})
        try:
            response = urllib.request.urlopen(request, timeout=12)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, json.loads(response.read())

    def snapshot(self):
        status, body = self.request('GET', '/api/state')
        assert status == 200, body
        return body

    def write(self, endpoint, **fields):
        # Existing W1 suites explicitly exercise the retained free-action profile.
        # R3 tests submit raw HTTP payloads to verify the new longline default.
        if endpoint == '/api/new-game':
            fields.setdefault('mode', 'free')
        payload = {'request_id': str(uuid.uuid4()), 'expected_revision': self.snapshot()['revision'], **fields}
        status, body = self.request('POST', endpoint, payload)
        assert status == 200, (endpoint, fields, status, body)
        return body

    def action(self, action, **params):
        return self.write('/api/action', action=action, params=params)


def route_to_ending(snapshot, action):
    """Public legal actions only; no internal rules, state injection, or save edits."""
    for _ in range(12):
        action('explore')
    action('upgrade')
    action('upgrade')
    for _ in range(6):
        action('gather')
    for _ in range(4):
        action('alchemy')
    for realm, threshold, region, enemy in [(0, 32, None, None), (1, 64, 'forest', 'ape'), (2, 96, 'ruins', 'sentinel')]:
        if enemy:
            action('travel', region=region)
            action('challenge', enemy=enemy)
            win_battle(snapshot, action)
        while snapshot()['state']['cultivation'] < threshold:
            action('cultivate')
        action('breakthrough')
    if snapshot()['state']['region'] != 'ruins':
        action('travel', region='ruins')
    action('challenge', enemy='shadow')
    win_battle(snapshot, action)
    assert snapshot()['state']['completed'], snapshot()


def win_battle(snapshot, action):
    for _ in range(80):
        snap = snapshot()
        state = snap['state']
        if state['battle'] is None:
            return
        max_hp = [60, 80, 100, 140][state['realm']]
        if state['pills'] and state['hp'] <= max_hp - 35:
            action('use_pill')
        elif state['mp'] >= 6:
            action('power_attack')
        else:
            action('defend')
    raise AssertionError('battle failed to terminate within 80 public actions')


def baseline_route(snapshot, action):
    """GDD's exact 53-action route, without upgrades, items, or injected state."""
    for count, region, enemy, sequence, hp, mp in [
        (6, 'forest', 'ape', ['power_attack', 'power_attack', 'defend', 'power_attack', 'attack', 'attack'], 46, 1),
        (8, 'ruins', 'sentinel', ['power_attack', 'power_attack', 'defend', 'power_attack', 'attack', 'defend', 'power_attack', 'attack'], 24, 2),
        (10, None, 'shadow', ['power_attack', 'power_attack', 'defend', 'power_attack', 'power_attack', 'defend', 'power_attack', 'attack', 'attack'], 36, 4),
    ]:
        for _ in range(count):
            action('cultivate')
        action('breakthrough')
        if region:
            action('travel', region=region)
        action('challenge', enemy=enemy)
        for command in sequence:
            action(command)
        state = snapshot()['state']
        assert state['battle'] is None, state
        assert (state['hp'], state['mp']) == (hp, mp), state
    state = snapshot()['state']
    assert state['completed'] and state['actions_taken'] == 53, state
