"""Independent designer HTTP journey route; explicit --run, isolated temp save.

Clock injection advances only server UTC. Never edits a save/state or grants assets.
R3Planner supplies projected-action/material helpers; combat decisions below are
independent of its win function and of the QA R4 route.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests.r3_support import ClockHTTP
from tests.r3_route import R3Planner


class Designer(R3Planner):
    def __init__(self, server):
        self.server = server
        self.events = []
        self.points = []
        self.combats = []
        self.started = server.clock()
        super().__init__(server.snapshot, server.action)

    def perform(self, action_id, **params):
        before = self.world()
        result = super().perform(action_id, **params)
        after = self.world()
        self.events.append({'action': action_id, 'params': params,
            'elapsed_hours': (self.server.clock()-self.started)/3600,
            'stage': after['stage'], 'xp': after['xp'], 'tick': after['tick'],
            'hp': after['hp'], 'mp': after['mp'],
            'inventory': dict(after['inventory']),
            'materials': dict(after['r3']['materials']),
            'cadence': dict(after['r3'].get('cadence',{})),
            'battle_before': before['battle'], 'battle_after': after['battle']})
        return result

    def win(self):
        initial = self.world()['battle']
        for _ in range(3):
            if self.world()['battle'] is None:
                break
            self.perform('world_auto_battle', strategy='balanced')
        w = self.world()
        assert w['battle'] is None and w['hp'] > 1, ('defeat is not victory', initial)
        if initial['kind'] == 'elite':
            assert initial['target'] in w['r3']['journey']['elite_wins']
        self.combats.append({'initial': initial, 'moves': ['world_auto_battle'],
                             'final_hp': w['hp'], 'final_mp': w['mp']})
    def point(self, story, item=None):
        before = set(self.world()['r3']['instances'])
        self.perform('world_story_claim', story=story, **({'item':item} if item else {}))
        w = self.world(); new = set(w['r3']['instances']) - before
        self.points.append({'story': story, 'elapsed_hours':
            (self.server.clock()-self.started)/3600, 'stage': w['stage'],
            'public_world_operations': len(self.events), 'world_tick':w['tick'], 'hp': w['hp'], 'mp':w['mp'],
            'choice':item, 'new_items':[w['r3']['instances'][uid] for uid in new],
            'inventory':dict(w['inventory']), 'materials':dict(w['r3']['materials'])})
        print(json.dumps({'checkpoint':story,'hours':self.points[-1]['elapsed_hours'],'operations':len(self.events)},ensure_ascii=False),flush=True)
        for uid in new:self.perform('world_loot_equip', uid=uid)

    def gear(self, recipe):
        before = set(self.world()['r3']['instances']);self.craft(recipe)
        uid = (set(self.world()['r3']['instances'])-before).pop()
        self.perform('world_loot_equip',uid=uid)
        for target in [1,2,3]:
            while self.world()['r3']['materials']['enhance_material'] < target:
                self.cost({'ore':4,'wood':2});self.perform('world_loot_exchange',item='enhance_material')
            self.ensure('ore',4*target);self.perform('world_loot_enhance',uid=uid)

    def advance_at(self, hours):
        self.server.clock.advance(int(hours*3600-(self.server.clock()-self.started)))
        self.rest();self.perform('world_boss');self.win()
        if self.world()['stage']==0:self.craft('barrier_pill')
        if self.world()['stage']==1:self.craft('soul_talisman')
        self.perform('world_advance')


def prologue(server):
    server.create(name='R4策划独立路线')
    for threshold,region,enemy in [(32,'forest','ape'),(64,'ruins','sentinel'),(96,None,'shadow')]:
        server.clock.advance(threshold*5)  # 序章吐纳随服务端时间自动累积
        server.action('breakthrough')
        if region:server.action('travel',region=region)
        server.action('challenge',enemy=enemy)
        server.action('auto_battle')
    assert server.snapshot()['state']['completed']
    server.action('world_enter')


def run(output, challenge_epilogue=False):
    server=ClockHTTP().start();p=None;epilogue=[]
    try:
        prologue(server);p=Designer(server)
        p.perform('world_root',choice='fire');p.perform('world_constitution',choice='sturdy')
        p.perform('world_story_accept',story='first_forge')
        for recipe in ['blade','armor','pendant']:p.gear(recipe)
        for _ in range(10):p.craft('pill')
        p.dungeon();p.point('first_forge')
        p.perform('world_story_accept',story='allied_roads')
        p.perform('world_sect_join',sect='sword')
        for npc,material in [('healer','herb'),('smith','ore')]:
            p.ensure(material,2);p.perform('world_gift',npc=npc)
        p.ensure('herb',3);p.perform('world_sect_daily',item='herb');p.point('allied_roads')
        # Exhaust opening loot, then return at 8h: new restored credit.
        for _ in range(2):p.perform('world_dungeon_sweep',dungeon='den',chapter=0,difficulty=1)
        server.clock.advance(8*3600)
        p.perform('world_dungeon_sweep',dungeon='den',chapter=0,difficulty=1)
        p.advance_at(12)
        p.perform('world_story_accept',story='caravan_rescue')
        for _ in range(4):p.craft('fire_talisman')
        p.secret('desert','chisha');p.rest();p.perform('world_elite_enter',elite='caravan_guard');p.win()
        p.point('caravan_rescue','blade')
        p.perform('world_story_accept',story='arts_in_concert')
        for _ in range(2):p.craft('fire_talisman')
        p.craft('spirit_array')
        p.perform('world_array_toggle',array='spirit');p.perform('world_array_toggle',array='spirit')
        p.point('arts_in_concert')
        server.clock.advance(int(16*3600-(server.clock()-p.started)))
        p.travel('qinglan')
        p.perform('world_dungeon_sweep',dungeon='den',chapter=0,difficulty=1)
        p.advance_at(48)
        p.perform('world_story_accept',story='venom_medicine')
        p.travel('xuanchao');p.rest();p.perform('world_elite_enter',elite='venom_keeper')
        p.win()
        p.point('venom_medicine','armor')
        p.perform('world_story_accept',story='dangerous_proof')
        p.craft('blade');p.dungeon(difficulty=2);p.point('dangerous_proof')
        p.advance_at(120)
        p.perform('world_story_accept',story='astral_bridge')
        p.travel('xuanchao');p.rest();p.perform('world_elite_enter',elite='astral_warden');p.win()
        p.rest();p.perform('world_boss_enter');p.perform('world_auto_battle',strategy='frugal')
        p.point('astral_bridge','pendant')
        if challenge_epilogue:
            p.challenge_epilogue=True
            w=p.world();before_materials=dict(w['r3']['materials'])
            for slot in ['weapon','armor','pendant']:
                uid=p.world()['r3']['equipped'][slot]
                for target in [1,2,3]:
                    p.ensure('ore',4*target)
                    p.perform('world_loot_enhance',uid=uid)
            epilogue.append({'step':'enhance_story_rewards','before':before_materials,
                'after':dict(p.world()['r3']['materials']),
                'equipment':{slot:p.world()['r3']['instances'][uid] for slot,uid in p.world()['r3']['equipped'].items() if uid}})
            while p.inventory('pill')<20:p.craft('pill')
            for difficulty in [1,2,3]:
                before=p.world();old=set(before['r3']['instances'])
                score=sum(2*before['r3']['instances'][before['r3']['equipped'][slot]]['chapter']+
                    before['r3']['instances'][before['r3']['equipped'][slot]]['quality']+1+
                    before['r3']['instances'][before['r3']['equipped'][slot]]['enhance']
                    for slot in ['weapon','armor','pendant'])
                p.dungeon(dungeon='den',region='qinglan',difficulty=difficulty,chapter=3)
                after=p.world();key='den:3:'+str(difficulty)
                assert key in after['dungeon_wins'] and after['dungeon'] is None and after['hp']>1
                epilogue.append({'step':'current_chapter_clear','chapter':3,'difficulty':difficulty,
                    'entry_score':score,'hp':after['hp'],'mp':after['mp'],
                    'materials_before':dict(before['r3']['materials']),
                    'materials_after':dict(after['r3']['materials']),
                    'pill_before':before['inventory'].get('pill',0),'pill_after':after['inventory'].get('pill',0),
                    'new_items':[after['r3']['instances'][uid] for uid in set(after['r3']['instances'])-old],
                    'cadence_after':after['r3']['cadence']})
        result={'ok':True,'clock_injected':True,'state_injected':False,'checkpoints':p.points,
                'actions':p.events,'combats':p.combats,'epilogue':epilogue,'final':server.snapshot()}
    except Exception as error:
        result={'ok':False,'error':repr(error),'checkpoints':p.points if p else [],
                'actions':p.events if p else [],'combats':p.combats if p else [],'epilogue':epilogue,'final':server.snapshot()}
    finally:server.close()
    output.mkdir(parents=True,exist_ok=True)
    (output/('route-epilogue.json' if challenge_epilogue else 'route.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({'ok':result['ok'],'error':result.get('error'),
        'completed_stories':len(result['checkpoints']),'actions':len(result['actions'])},ensure_ascii=False))
    return 0 if result['ok'] else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--challenge-epilogue',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/r4-design')
    args=parser.parse_args()
    if not args.run:print('Prepared only. Use --run after domain/projection are stable; no application data changed.')
    else:raise SystemExit(run(args.output,args.challenge_epilogue))
