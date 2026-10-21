import hashlib
import json
import math
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import zipfile

archive=Path(sys.argv[1]).resolve()
report_path=Path(sys.argv[2]).resolve()
report={'archive':archive.name,'passed':False,'checks':[]}
with tempfile.TemporaryDirectory(prefix='guixu-release-verify-') as temp:
    root=Path(temp)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        names=z.namelist()
        assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in names)
        assert not any(n.startswith(('data/','backups/','.git/','dist/')) or n.endswith(('.db','.pyc')) for n in names)
        z.extractall(root)
    report['archive_files']=len(names)
    runtime=[root/'server.py',root/'VERSION',*sorted((root/'game').glob('*.py')),*sorted((root/'static').glob('*'))]
    report['runtime_sha256']={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in runtime if p.is_file()}
    assert (root/'VERSION').read_text().strip()=='1.2.0'
    proc=None
    log=(root/'smoke-server.log').open('w+')
    def stop():
        global proc
        if proc is not None:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
            proc=None
    def start():
        global proc,url
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        url='http://127.0.0.1:'+str(port)
        proc=subprocess.Popen([sys.executable,str(root/'server.py'),'--port',str(port),'--data-dir',str(root/'isolated-data')],cwd=root,stdout=log,stderr=subprocess.STDOUT)
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            if proc.poll() is not None:log.seek(0);raise AssertionError(log.read())
            try:
                if get('/api/health')['ok']:return
            except (OSError,ValueError):pass
            time.sleep(.05)
        raise AssertionError('archive server did not become ready')
    def request(path,payload=None):
        data=None if payload is None else json.dumps(payload).encode()
        req=urllib.request.Request(url+path,data=data,headers={'Content-Type':'application/json','X-Game-Client':'guixu-web'})
        try:response=urllib.request.urlopen(req,timeout=15)
        except urllib.error.HTTPError as exc:
            raise AssertionError((path,exc.code,exc.read().decode())) from exc
        with response:
            body=response.read()
            return json.loads(body) if response.headers.get_content_type()=='application/json' else body
    def get(path='/api/state'):return request(path)
    def write(endpoint,**fields):
        return request('/api/'+endpoint,dict(request_id=str(uuid.uuid4()),expected_revision=get()['revision'],**fields))
    def action(name,**params):return write('action',action=name,params=params)
    try:
        start()
        assert b'longline' in get('/') and b'growth-panel' in get('/')
        assert len(get('/app.js'))>1000 and len(get('/styles.css'))>1000 and len(get('/battle_replay.js'))>1000
        created=write('new-game',name='归档验收')
        assert created['view']['profile']['mode']=='longline'
        sys.path.insert(0,str(root))
        # 序章吐纳随服务端时间自动累积；归档验收用注入时钟的同一 Store 预走序章，再交还真实服务器继续。
        stop()
        from game.storage import Store
        from tests.support import baseline_route, TestClock
        clock=TestClock(int(time.time())-3600);store=Store(root/'isolated-data',clock=clock)
        def store_action(name,**params):
            return store.write('action',dict(request_id=str(uuid.uuid4()),expected_revision=store.snapshot()['revision'],action=name,params=params))
        baseline_route(store.snapshot,store_action)
        start()
        entered=action('world_enter')
        assert entered['state']['world']['active']
        assert entered['state']['world']['r3']['growth']['curve_version']==2
        assert entered['view']['world']['loot']['credits']['available']==3
        assert len(entered['view']['world']['journey']['layers'])==7
        write('save')
        action('world_story_accept',story='first_forge')
        report['checks'].append('archive static assets, default longline, legal prologue and world entry')
        for item in ['ore','ore','ore','wood','wood','wood','herb']:
            action('world_gather',item=item)
        crafted=action('world_craft',recipe='blade',quantity=1)
        blade=next(uid for uid,item in crafted['state']['world']['r3']['instances'].items() if item['template_id']=='blade')
        action('world_loot_equip',uid=blade)
        action('world_boss_enter')
        finished=action('world_auto_battle',strategy='frugal')
        period=next(iter(finished['state']['world']['r3']['boss']))
        claimed=action('world_boss_claim',day=period)
        assert claimed['state']['world']['r3']['materials']['boss_coin']>=8
        for _ in range(4):action('world_loot_exchange',item='dust')
        made=action('world_loot_craft_treasure',slot='main',effect_type='cultivation')
        treasure=next(uid for uid,item in made['state']['world']['r3']['instances'].items() if item['template_id']=='main_treasure')
        equipped=action('world_loot_equip',uid=treasure)
        assert math.isclose(equipped['view']['growth']['rate']['per_day'],545.4,abs_tol=1e-8)
        loaded=write('load')
        assert loaded['state']['world']['r3']['equipped']['main']==treasure
        assert loaded['state']['world']['r3']['boss'][period]['paid_coin']>=8
        assert loaded['state']['world']['r3']['journey']['stories']['first_forge']['progress'][0]==1
        assert loaded['view']['world']['loot']['credits']['available']==3
        report['checks'].append('real materials -> instance equipment -> Boss score/delta -> dust -> cultivation treasure and 545.4/day')
        report['checks'].append('R4 curve2, seven real story layers, accepted craft progress and recoverable credits survive older checkpoint')
        prior=loaded['view']['growth']['available'];revision=loaded['revision']
        stop();time.sleep(1.1);start()
        resumed=get()
        assert resumed['revision']==revision
        assert resumed['state']['world']['r3']['equipped']['main']==treasure
        assert resumed['view']['growth']['available']>=prior
        assert get('/api/health')['schema_version']==2
        report['checks'].append('stop/restart restores real save and continuous entitlement without any injected HTTP time')
        free=write('new-game',name='旧制验收',mode='free')
        assert 'r3' not in free['state']['world']
        assert free['state'].get('qi_at') is not None
        try:action('cultivate');retired=False
        except AssertionError:retired=True
        assert retired
        report['checks'].append('explicit free profile also cultivates over time; click cultivation is retired')
        fixture_check=subprocess.run([sys.executable,'-m','unittest','tests.test_r4_architecture','-q'],
            cwd=root,capture_output=True,text=True,timeout=60)
        assert fixture_check.returncode==0, fixture_check.stdout+fixture_check.stderr
        report['checks'].append('packaged migration tests run with bundled old-save fixture and no dist directory')
        report['passed']=True
    finally:
        stop();log.close()
report_path.parent.mkdir(parents=True,exist_ok=True)
report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':report['passed'],'archive_files':report['archive_files'],'checks':report['checks']},ensure_ascii=False))
