"""API driver for the local game server (stdlib only).
  python driver.py [--port 8123] state            -> phase/revision/action list
  python driver.py [--port 8123] new [name] [longline|free]
  python driver.py [--port 8123] act <action label substring>
"""
import argparse, json, sys, uuid, urllib.request, urllib.error
sys.stdout.reconfigure(encoding='utf-8')

ap = argparse.ArgumentParser()
ap.add_argument('--port', type=int, default=8123)
ap.add_argument('cmd', choices=['state', 'new', 'act'])
ap.add_argument('args', nargs='*')
a = ap.parse_args()
base = f'http://127.0.0.1:{a.port}'

def get():
    return json.load(urllib.request.urlopen(base + '/api/state'))

def post(path, body):
    req = urllib.request.Request(base + path, json.dumps(body, ensure_ascii=False).encode('utf-8'),
        {'Content-Type': 'application/json', 'X-Game-Client': 'guixu-web'})
    try:
        return json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as e:
        return json.load(e)

s = get()
if a.cmd == 'new':
    name = a.args[0] if a.args else '测试'
    mode = a.args[1] if len(a.args) > 1 else 'longline'
    s = post('/api/new-game', dict(request_id=uuid.uuid4().hex, expected_revision=s['revision'], name=name, mode=mode))
elif a.cmd == 'act':
    acts = s['view']['actions']
    hit = [x for x in acts if a.args[0] in json.dumps(x, ensure_ascii=False)]
    if not hit:
        sys.exit('no action matches; have: ' + ', '.join(x.get('label', x.get('id', '?')) for x in acts))
    s = post('/api/action', dict(request_id=uuid.uuid4().hex, expected_revision=s['revision'], action=hit[0]['id'], params=hit[0].get('params', {})))
v = s.get('view') or {}
print(json.dumps(dict(ok=s.get('ok'), error=s.get('error'), revision=s.get('revision'), phase=v.get('phase'),
    actions=[(x.get('id'), x.get('label')) for x in v.get('actions', [])][:12], log=v.get('logs', [])[:2]), ensure_ascii=False, indent=1))
