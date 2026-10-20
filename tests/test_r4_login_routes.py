"""Actual HTTP sweep receipts under half-open seven-day login schedules."""
import json
import unittest
from tests.r3_support import ClockHTTP
from tests.r3_route import R3Planner
from tests.support import baseline_route, ROOT

class R4LoginRouteTests(unittest.TestCase):
    def run_schedule(self,hours):
        s=ClockHTTP().start();self.addCleanup(s.close)
        s.create();baseline_route(s.snapshot,s.action);s.action('world_enter')
        p=R3Planner(s.snapshot,s.action);start=s.clock.value
        p.dungeon(difficulty=1)
        records=[]
        for hour in hours:
            s.clock.value=start+hour*3600
            before=s.snapshot();credits=before['view']['world']['loot']['credits']['available']
            for _ in range(credits):p.perform('world_dungeon_sweep',dungeon='den',chapter=0,difficulty=1)
            r=p.world()['r3']
            records.append(dict(hour=hour,available_before=credits,drop_seq=r['drop_seq'],stage=p.world()['stage'],xp=p.world()['xp']))
        r=p.world()['r3'];self.assertEqual(len([x for x in r['receipts'] if x.get('uid')]),r['drop_seq'])
        self.assertEqual(r['journey']['manual_clears'],['den:0:1'])
        return dict(logins=records,drops=r['drop_seq'],stage=p.world()['stage'],xp=p.world()['xp'])

    def test_once_thrice_and_missed_week_are_public_actions_not_quota_simulation(self):
        results={'once_daily':self.run_schedule(range(0,168,24)),
                 'three_daily':self.run_schedule(range(0,168,8)),
                 'missed_week':self.run_schedule([0,168])}
        self.assertEqual([results[k]['drops'] for k in results],[21,23,6])
        self.assertEqual(results['missed_week']['logins'][-1]['available_before'],3)
        self.assertTrue(all(x['stage']==0 for x in results.values()))
        self.assertGreater(results['missed_week']['xp'],results['once_daily']['xp'])
        out=ROOT/'artifacts/r4-qa/login-routes.json';out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps({'kind':'production HTTP, stage0 isolation, injected UTC; not human play duration','passed':True,'routes':results},ensure_ascii=False,indent=2), encoding='utf-8')
