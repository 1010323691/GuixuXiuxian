import sys,tempfile,json,uuid,datetime,hashlib
from pathlib import Path
sys.path.insert(0,'/workspace/GuixuXiuxian')
from game.storage import Store
from game.rules import GameError
from tests.support import baseline_route
from tests.r3_support import Clock
from tests.r3_route import R3Planner
root=Path('/workspace/GuixuXiuxian')
clock=Clock(int(datetime.datetime(2026,10,19,tzinfo=datetime.timezone.utc).timestamp()))
start=clock(); out={'kind':'read-only product audit with isolated temporary Store and injected UTC; not human playtime','logins':[],'attempts':[]}
with tempfile.TemporaryDirectory(prefix='guixu-first-week-audit-') as folder:
 store=Store(folder,clock=clock)
 def write(endpoint,**fields):return store.write(endpoint,dict(request_id=str(uuid.uuid4()),expected_revision=store.snapshot()['revision'],**fields))
 def action(command,**params):return write('action',action=command,params=params)
 write('new-game',name='首周审计')
 baseline_route(store.snapshot,action);action('world_enter')
 p=R3Planner(store.snapshot,action);p.prepare();p.craft('barrier_pill');p.craft('soul_talisman')
 p.perform('world_sect_join',sect='sword');p.perform('world_activity_accept',project='social')
 p.cost({'herb':3});p.perform('world_sect_daily',item='herb');p.perform('world_chat',npc='healer')
 key=next(k for k in p.world()['r3']['activities']['entries'] if k.startswith('d:'))
 p.perform('world_activity_claim',key=key)
 for difficulty in [1,2,3]:p.dungeon(difficulty=difficulty)
 def snapshot(label):
  s=store.snapshot();w=s['state']['world'];r=w['r3'];v=s['view']['world'];g=s['view']['growth']
  from game import world_config as C
  row={'label':label,'elapsed_hours':(clock()-start)/3600,'stage':w['stage'],'realm':v['stage'],
   'chapter_max':w['stage'],'regions_unlocked':[id for id,d in C.REGIONS.items() if d['stage']<=w['stage']],
   'xp_settled':w['xp'],'xp_available':g['available'],'rate_per_day':g['rate']['per_day'],
   'instance_receipts_total':len(r['receipts']),'dungeon_drop_receipts':sum(v['source'] in r['runs'] for v in r['receipts']),'daily_successes':dict(r['daily']),
   'pity':dict(r['pity']),'owned_instances':len(r['instances']),
   'activities_claimed':[k for k,v in r['activities']['entries'].items() if v['claimed']],
   'guard_first_wins':list(w['guard_wins']),'dungeon_first_wins':list(w['dungeon_wins']),
   'boss':{k:{field:v[field] for field in ['attempts','best','paid_coin','paid_dust']} for k,v in r['boss'].items()},
   'materials':dict(r['materials']),'world_tick':w['tick']}
  out['logins'].append(row);return row
 for hours in [0,8,16]:
  clock.advance(start+hours*3600-clock())
  if hours:
   p.perform('world_dungeon_enter',dungeon='den',chapter=0,difficulty=3)
   run=p.world()['dungeon']['run_id'];out['attempts'].append({'elapsed_hours':hours,'run_eligible':p.world()['r3']['runs'][run]['eligible']})
   p.perform('world_dungeon_leave')
  p.rest();p.perform('world_boss_enter');p.perform('world_defend');p.perform('world_flee')
  day=datetime.datetime.fromtimestamp(clock(),datetime.timezone.utc).date().isoformat()
  visible=any(a['id']=='world_boss_claim' and a['params']=={'day':day} for a in p.actions())
  if visible:
   p.perform('world_boss_claim',day=day);claim='paid'
  else:claim='no_claim_projection; entitlement_delta=0; no_write_attempted'
  out['attempts'].append({'elapsed_hours':hours,'boss_claim':claim})
  before=store.snapshot();status='not_submitted'
  try:action('world_activity_claim',key=key);status='unexpected_paid'
  except GameError as exc:
   assert exc.status==422,(exc.status,exc.code)
   status={'rejected_http_equivalent_status':exc.status,'code':exc.code}
  out['attempts'].append({'elapsed_hours':hours,'old_daily_claim':status})
  snapshot('day0 login'+str(hours//8+1))
 clock.advance(start+86400-clock())
 p.perform('world_dungeon_enter',dungeon='den',chapter=0,difficulty=3)
 run=p.world()['dungeon']['run_id'];out['attempts'].append({'elapsed_hours':24,'run_eligible':p.world()['r3']['runs'][run]['eligible']})
 p.perform('world_dungeon_leave');snapshot('day1 before optional play')
 for day in [3,7]:
  clock.advance(start+day*86400-clock())
  # Only real legal gates, materials and manual breakthrough; no save edits.
  while p.world()['stage']<2:
   stage=p.world()['stage'];cost=[1620,3240][stage]
   if store.snapshot()['view']['growth']['available']<cost:break
   if str(stage) not in p.world()['guard_wins']:
    p.rest();p.perform('world_boss');p.win()
   p.perform('world_advance')
  snapshot('day'+str(day)+' after manual eligible gates')
 out['public_world_actions']=len(p.trace)
 out['instance_receipts']=p.world()['r3']['receipts']
 out['run_ids']=list(p.world()['r3']['runs'])
 out['source_sha256']={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'game').glob('*.py')}
(root/'artifacts/r3-qa/first-week-audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False,indent=2))
