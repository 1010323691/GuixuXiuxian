"""Public legal-action acquisition/challenge/full growth integration, no save injection."""
import copy
import json
import unittest
from tests.r3_support import ClockHTTP
from tests.support import ROOT, baseline_route
from tests.r3_route import R3Planner


class R3PublicProgressionTests(unittest.TestCase):
    def setUp(self):
        self.server = ClockHTTP().start()
        self.addCleanup(self.server.close)
        self.server.create()
        baseline_route(self.server.snapshot,self.server.action)
        self.server.action('world_enter')
        self.planner = R3Planner(self.server.snapshot,self.server.action)

    def test_low_difficulty_materials_and_crafted_enhancement_unlock_two_higher_difficulties(self):
        p = self.planner
        p.prepare()
        original = p.world()['xp']
        for difficulty in [1,2,3]:
            before = len(p.world()['r3']['receipts'])
            run = p.dungeon(difficulty=difficulty)
            self.assertEqual(len(p.world()['r3']['receipts']),before+1)
            self.assertTrue(p.world()['r3']['runs'][run]['eligible'])
        r = p.world()['r3']
        self.assertEqual(r['pity'], {'1':1,'2':1,'3':1})
        self.assertEqual(p.world()['xp'],original, 'three rewarded dungeons added direct XP')
        before = copy.deepcopy((r['drop_seq'],r['pity'],r['materials']))
        p.dungeon(difficulty=3)
        r = p.world()['r3']
        self.assertEqual((r['drop_seq'],r['pity'],r['materials']),before,
                         'fourth same UTC-day successful run bypassed shared three-drop quota')
        # Reward materials really make and equip a cultivation treasure, affecting future rate.
        p.cost({'herb':4,'ore':4,'wood':4})
        before_uids = set(r['instances'])
        p.perform('world_loot_craft_treasure',slot='main',effect_type='cultivation')
        uid = next(iter(set(p.world()['r3']['instances'])-before_uids))
        rate_before = self.server.snapshot()['view']['growth']['rate']['per_day']
        p.perform('world_loot_equip',uid=uid)
        rate_after = self.server.snapshot()['view']['growth']['rate']['per_day']
        self.assertAlmostEqual(rate_after-rate_before,5.4)

    def test_eight_stage_full_growth_and_final_spending_through_real_http(self):
        start = self.server.clock()
        checkpoints = self.planner.full_growth(self.server.clock,
            checkpoint=lambda operation:self.server.write('/api/'+operation))
        w = self.planner.world()
        self.assertTrue(w['ending'])
        self.assertEqual(len(checkpoints),8)
        # All three actual themed bosses at both enhanced difficulties, via legal unlocked routes.
        for dungeon,region in [('den','qinglan'),('forge','chisha'),('tower','xuanchao')]:
            for difficulty in [1,2,3]:
                self.planner.dungeon(dungeon,region,difficulty,chapter=0)
        self.assertEqual(len(self.planner.mechanics_seen),6)
        before_load = copy.deepcopy(w)
        self.server.write('/api/save')
        self.server.action('world_gather',item='wood')
        latest = self.server.snapshot()['state']['world']
        self.assertEqual(self.server.write('/api/load')['state']['world'], latest)
        evidence={'passed':True,'kind':'injected-clock legal HTTP, not real forty-day observation',
                  'elapsed_seconds':self.server.clock()-start,'checkpoints':checkpoints,
                  'actions':len(self.planner.trace),'ending':w['ending'],
                  'stage':w['stage'],'xp_remaining':w['xp'],
                  'themed_bosses':self.planner.mechanics_seen}
        folder=ROOT/'artifacts'/'r4-qa';folder.mkdir(parents=True,exist_ok=True)
        (folder/'retained-growth-route.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2), encoding='utf-8')
