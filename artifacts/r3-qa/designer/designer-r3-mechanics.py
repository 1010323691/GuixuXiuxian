import sys,json,uuid
sys.path.insert(0,'/workspace/GuixuXiuxian')
from tests.r3_support import ClockHTTP
from datetime import datetime,timezone
s=ClockHTTP().start(); count=0; checkpoints=[]
def snap():return s.snapshot()
def w():return snap()['state']['world']
def do(a,**p):
 global count
 b=snap();status,r=s.request('POST','/api/action',dict(request_id=str(uuid.uuid4()),expected_revision=b['revision'],action=a,params=p));assert status==200,(a,p,status,r);count+=1;return r
def ensure(item,n):
 while w()['inventory'].get(item,0)<n:do('world_gather',item=item)
def craft(item,cost):
 for k,n in cost.items():ensure(k,n)
 do('world_craft',recipe=item,quantity=1)
def rest():
 for _ in range(50):
  acts=[a for p in snap()['view']['world']['pages'] for a in p['actions'] if a['id']=='world_rest']
  if not acts[0]['enabled']:return
  do('world_rest')
 raise AssertionError('restloop')
def boss(label):
 rest();do('world_boss_enter');moves=[]
 while w()['battle']:
  ww=w();b=ww['battle'];cmd='world_pill' if label.startswith('补给') and b['turn']%3==1 and ww['mp']<24 and ww['inventory'].get('pill',0) else ('world_power' if ww['mp']>=24 else 'world_attack')
  do(cmd);moves.append(cmd)
 day=datetime.fromtimestamp(s.clock(),timezone.utc).date().isoformat();p=w()['r3']['boss'][day];do('world_boss_claim',day=day);p=w()['r3']['boss'][day]
 checkpoints.append(dict(label=label,day=day,damage=p['best'],commands=len(moves),hp=w()['hp'],mp=w()['mp'],coin=p['paid_coin'],dust=p['paid_dust'],materials=w()['r3']['materials'].copy(),moves=moves))
 return p['best']
try:
 s.create(name='策划独立Boss路线')
 for n,reg,e,seq in [(6,'forest','ape','PPDPAA'),(8,'ruins','sentinel','PPDPADPA'),(10,None,'shadow','PPDPPDPAA')]:
  for _ in range(n):do('cultivate')
  do('breakthrough')
  if reg:do('travel',region=reg)
  do('challenge',enemy=e)
  for c in seq:do({'P':'power_attack','D':'defend','A':'attack'}[c])
 do('world_enter')
 for item,cost in [('blade',{'ore':6,'wood':2}),('armor',{'ore':8,'wood':3}),('pendant',{'ore':4,'crystal':2})]:
  before=set(w()['r3']['instances']);craft(item,cost);uid=(set(w()['r3']['instances'])-before).pop();do('world_loot_equip',uid=uid)
  for target in [1,2,3]:
   ensure('ore',4*target)
   while w()['r3']['materials']['enhance_material']<target:
    ensure('ore',4*target+4);ensure('wood',2);do('world_loot_exchange',item='enhance_material')
   do('world_loot_enhance',uid=uid)
 boss('凡品三器+3未培养')
 do('world_root',choice='fire')
 for _ in range(3):ensure('herb',6);ensure('crystal',1);do('world_root_train')
 for target in [2,3]:
  ensure('crystal',target)
  while w()['wallet']<20*target:
   ensure('herb',10);do('world_sell',item='herb',quantity=10)
  do('world_skill_upgrade',skill='origin')

 for _ in range(12):craft('pill',{'herb':3})
 for _ in range(8):craft('fire_talisman',{'wood':4,'crystal':1})
 def generic_win():
  for _ in range(60):
   ww=w();b=ww['battle']
   if not b:return
   cmd='world_pill' if ww['hp']<110 or ww['mp']<24 and b['turn']%3==1 else ('world_power' if ww['mp']>=24 else 'world_attack')
   do(cmd)
  raise AssertionError('battleloop')
 for stage in [0,1]:
  s.clock.advance(10*86400);rest();do('world_boss');generic_win();assert str(stage) in w()['guard_wins']
  if stage==0:craft('barrier_pill',{'herb':6,'crystal':2})
  else:craft('soul_talisman',{'wood':5,'crystal':2})
  do('world_advance')
 for dungeon,region in [('den','qinglan'),('forge','chisha'),('tower','xuanchao')]:
  if w()['region']!=region:do('world_travel',region=region)
  for difficulty in [1,2]:
   rest();do('world_dungeon_enter',dungeon=dungeon,difficulty=difficulty,chapter=0)
   observed=[]
   for fight in range(3):
    rest();do('world_dungeon_next')
    while w()['battle']:
     ww=w();b=ww['battle'];cmd='world_power' if ww['mp']>=24 else 'world_attack'
     if ww['hp']<100 or ww['mp']<24 and b['turn']%3==1:cmd='world_pill'
     if difficulty==2 and fight==2:
      observed.append(dict(turn=b['turn'],hp=ww['hp'],mp=ww['mp'],poison=b.get('poison_turns'),barrier=b.get('barrier')))
      if dungeon=='den' and b.get('poison_turns'):cmd='world_pill'
      elif dungeon=='den' and b['turn']%3==2:cmd='world_defend'
      elif dungeon=='forge' and b.get('barrier',0)>0:cmd='world_fire'
      elif dungeon=='tower' and b['turn']%3==0:cmd='world_defend'
     do(cmd)
    assert w()['hp']>1,('lost',dungeon,difficulty,fight)
   assert w()['dungeon'] is None,('notcleared',dungeon,difficulty)
   checkpoints.append(dict(dungeon=dungeon,difficulty=difficulty,observed=observed,hp=w()['hp'],mp=w()['mp']))
 out=dict(ok=True,actions=count,checkpoints=checkpoints,final=snap())
except Exception as e:
 out=dict(ok=False,error=repr(e),actions=count,checkpoints=checkpoints,state=snap())
finally:
 open('/tmp/designer-r3-mechanics.json','w').write(json.dumps(out,ensure_ascii=False,indent=2));s.close()
print(json.dumps({k:v for k,v in out.items() if k not in ['final','state','checkpoints']},ensure_ascii=False));print(json.dumps(checkpoints,ensure_ascii=False))
