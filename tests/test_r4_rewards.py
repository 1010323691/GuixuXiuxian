"""Same dungeon reward comparison excludes intentional world.tick/NPC side effects."""
import copy
import unittest
from tests.r3_support import ClockHTTP
from tests.support import baseline_route
from tests.r3_route import R3Planner


class R4SweepRewardTests(unittest.TestCase):
    def arm(self,sweep):
        server=ClockHTTP().start();self.addCleanup(server.close)
        server.create();baseline_route(server.snapshot,server.action);server.action('world_enter')
        p=R3Planner(server.snapshot,server.action);p.dungeon(difficulty=1)
        before=copy.deepcopy(p.world())
        if sweep:p.perform('world_dungeon_sweep',dungeon='den',chapter=0,difficulty=1)
        else:p.dungeon(difficulty=1)
        after=p.world();r=after['r3'];br=before['r3']
        receipt=r['receipts'][-1];item=r['instances'][receipt['uid']]
        return {'wallet':after['wallet']-before['wallet'],
            'herb':after['inventory'].get('herb',0)-before['inventory'].get('herb',0),
            'materials':{k:r['materials'][k]-br['materials'][k] for k in r['materials']},
            'drop_seq':r['drop_seq']-br['drop_seq'],'pity':r['pity']['1']-br['pity']['1'],
            'credit_spent':br['cadence']['available']-r['cadence']['available'],
            'item':{k:item[k] for k in ['template_id','chapter','quality','enhance','effect_type']},
            'pills_before_after':[before['inventory'].get('pill',0),after['inventory'].get('pill',0)],
            'manual':r['journey']['manual_clears'],'tick_delta':after['tick']-before['tick']}

    def test_same_second_clear_rewards_and_credit_but_sweep_has_one_world_action(self):
        manual=self.arm(False);quick=self.arm(True)
        self.assertEqual({k:v for k,v in manual.items() if k!='tick_delta'},
                         {k:v for k,v in quick.items() if k!='tick_delta'})
        self.assertEqual(quick['item'],dict(template_id='armor',chapter=0,quality=0,enhance=0,effect_type='combat'))
        self.assertEqual(quick['wallet'],10)
        self.assertEqual(quick['herb'],3)
        self.assertEqual(quick['materials'],dict(dust=2,enhance_material=2,boss_coin=0))
        self.assertEqual(quick['credit_spent'],1)
        self.assertEqual(quick['manual'],['den:0:1'])
        self.assertEqual(quick['tick_delta'],1)
        self.assertGreater(manual['tick_delta'],quick['tick_delta'])
