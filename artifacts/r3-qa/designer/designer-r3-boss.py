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
 for dayidx in range(1,16):
  s.clock.advance(86400);boss('采集Boss宝尘第%d日'%dayidx)
  while w()['r3']['materials']['boss_coin']>=2:do('world_loot_exchange',item='dust')
  if w()['r3']['materials']['dust']>=120:break
 for slot in ['main','guard']:
  for k in ['herb','ore','wood']:ensure(k,4)
  before=set(w()['r3']['instances']);do('world_loot_craft_treasure',slot=slot,effect_type='combat');uid=(set(w()['r3']['instances'])-before).pop()
  for q in [1,2,3,4]:ensure('crystal',q);do('world_loot_quality',uid=uid)
  do('world_loot_equip',uid=uid)
 craft('pill',{'herb':3});craft('pill',{'herb':3});s.clock.advance(86400);best=boss('补给：凡品三器+3火根3归元3双极品战力宝')
 assert best>=900, best
 out=dict(ok=True,actions=count,elapsed_days=(s.clock()-1800000000)/86400,checkpoints=checkpoints,final=snap())
except Exception as e:
 out=dict(ok=False,error=repr(e),actions=count,checkpoints=checkpoints,state=snap())
finally:
 open('/tmp/designer-r3-boss.json','w').write(json.dumps(out,ensure_ascii=False,indent=2));s.close()
print(json.dumps({k:v for k,v in out.items() if k not in ['final','state','checkpoints']},ensure_ascii=False));print(json.dumps(checkpoints,ensure_ascii=False))
