"""Architect-owned exact integration tests; independent temporary states only."""
import copy
import unittest
from unittest.mock import patch
from game import growth


def state(active=True):
    return {'world':{'active':active,'stage':0,'xp':0,'region':'qinglan',
        'battle':None,'exploration':None,'dungeon':None,
        'r3':{'profile_id':'test-profile','growth':None}}}


class GrowthTests(unittest.TestCase):
    def setUp(self):
        self.rate=patch('game.growth.rate_num',side_effect=lambda s:540*growth.MICRO*growth.COEFFICIENTS[s['world']['stage']]*10000 if s['world']['active'] else 0)
        self.rate.start();self.addCleanup(self.rate.stop)

    def test_exact_day_and_split_remainders(self):
        s=growth.sync(state(),1000)
        once=growth.sync(s,87400)
        split=s
        for t in range(1001,87401):split=growth.sync(split,t)
        self.assertEqual(once,split)
        self.assertEqual(once['world']['xp'],540)
        self.assertEqual(once['world']['r3']['growth']['remainder'],0)

    def test_preview_no_mutation_and_160_seconds(self):
        s=growth.sync(state(),1000);original=copy.deepcopy(s)
        p,v=growth.preview(s,1160)
        self.assertEqual(s,original)
        self.assertEqual(p['world']['xp'],1)
        self.assertEqual(v['available_micro'],'1000000')
        self.assertEqual(v['rate']['per_day'],540)

    def test_old_rate_then_new_stage_and_spending(self):
        s=growth.sync(state(),0)
        before=growth.sync(s,86400*3)
        after=copy.deepcopy(before);after['world']['xp']-=1620;after['world']['stage']=1
        after=growth.finish(before,after,86400*3)
        result=growth.sync(after,86400*4)
        self.assertEqual(result['world']['xp'],810)
        self.assertEqual(result['world']['r3']['growth']['total_micro'],2430*growth.MICRO)

    def test_no_cap_and_waiting_for_breakthrough(self):
        s=growth.sync(state(),0)
        s=growth.sync(s,86400*10000)
        self.assertEqual(s['world']['xp'],5400000)

    def test_backward_clock_does_not_regrant(self):
        s=growth.sync(state(),1000);s=growth.sync(s,1160)
        self.assertEqual(growth.sync(s,1000),s)
        p,v=growth.preview(s,1000)
        self.assertEqual(v['server_now'],1160);self.assertTrue(v['clock_rewound'])
        self.assertEqual(growth.sync(p,1320)['world']['xp'],2)

    def test_pre_world_has_no_growth(self):
        s=growth.sync(state(False),1000)
        self.assertEqual(growth.sync(s,99999999)['world']['xp'],0)
        after=copy.deepcopy(s);after['world']['active']=True
        after=growth.finish(s,after,99999999)
        self.assertEqual(after['world']['r3']['growth']['last_settled'],99999999)

    def test_load_preserves_consumption_assets_and_progression(self):
        s=growth.sync(state(),0);slot=copy.deepcopy(s)
        s=growth.sync(s,86400*3);after=copy.deepcopy(s)
        after['world']['xp']-=1620;after['world']['stage']=1
        after['world']['region']='other';after['world']['r3']['owned']={'uid':'spent'}
        s=growth.finish(s,after,86400*3)
        restored,events=growth.load_checkpoint(s,slot)
        self.assertEqual(restored['world']['stage'],1)
        self.assertEqual(restored['world']['xp'],0)
        self.assertEqual(restored['world']['r3'],s['world']['r3'])
        self.assertEqual(restored['world']['region'],'qinglan')
        self.assertTrue(events)

    def test_stored_balance_and_rate_corruption_rejected(self):
        s=growth.sync(state(),1000)
        for field in ('rate_num','balance_micro'):
            broken=copy.deepcopy(s);broken['world']['r3']['growth'][field]+=growth.MICRO
            with self.assertRaises(ValueError):growth.validate(broken,check_balance=True)

    def test_no_action_xp_bypass(self):
        before=growth.sync(state(),1000);after=copy.deepcopy(before);after['world']['xp']=100
        with self.assertRaises(ValueError):growth.finish(before,after,1000)


if __name__=='__main__':unittest.main()
