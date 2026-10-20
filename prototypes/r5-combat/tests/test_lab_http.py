"""Public isolated-lab protocol, not production game APIs."""
import copy
import json
import unittest
from lab_support import LabServer

BASE={'scenario':'den','build':'sustain','strategy':'balanced'}

class LabHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.server=LabServer().start()
    @classmethod
    def tearDownClass(cls):cls.server.close()
    def post(self,payload):return self.server.request('POST','/api/simulate',payload)
    def test_all_scenarios_builds_strategies_are_deterministic_and_do_not_mutate_inputs(self):
        for scene in ['den','forge','tower','boss','dungeon']:
            for build in ['sustain','burst','guard']:
                for strategy in ['balanced','aggressive']:
                    with self.subTest(scene=scene,build=build,strategy=strategy):
                        payload=dict(scenario=scene,build=build,strategy=strategy);before=copy.deepcopy(payload)
                        status,first=self.post(payload);self.assertEqual(status,200,first)
                        self.assertEqual(self.post(payload),(200,first));self.assertEqual(payload,before)
                        self.assertTrue(first['experimental'])
                        self.assertTrue(first['frames']);self.assertTrue(first['events'])
                        self.assertIn('metrics',first);self.assertIn('nodes',first)
    def test_zero_defaults_match_explicit_zero_and_budget_edges_are_accepted(self):
        zero=dict(BASE,pill_budget=0,fire_budget=0,guard_budget=0,soul_budget=0,npc=False)
        self.assertEqual(self.post(BASE),self.post(zero))
        status,body=self.post(dict(BASE,pill_budget=3,fire_budget=2,guard_budget=2,soul_budget=2,npc=True))
        self.assertEqual(status,200,body)
    def test_unknown_missing_enums_and_exact_budget_types_rejected(self):
        bad=[None,[],42,{},dict(BASE,extra=0),dict(BASE,talisman_budget=1),dict(BASE,companion=True),dict(BASE,stats={}),dict(BASE,initial={'mp':0}),dict(BASE,time=1),dict(BASE,version=1),dict(BASE,scenario='../../game'),dict(BASE,build='god'),dict(BASE,strategy='infinite')]
        for key in BASE:
            p=dict(BASE);del p[key];bad.append(p)
        for key,max_value in [('pill_budget',3),('fire_budget',2),('guard_budget',2),('soul_budget',2)]:
            for value in [True,False,1.0,'1',None,-1,max_value+1]:bad.append(dict(BASE,**{key:value}))
        for value in [0,1,'true',None]:bad.append(dict(BASE,npc=value))
        for payload in bad:
            with self.subTest(payload=payload):self.assertEqual(self.post(payload)[0],400)
    def test_malformed_nonfinite_duplicate_keys_and_size_limit_rejected(self):
        for raw in [b'{',b'\xff',b'{"scenario":"den","scenario":"boss"}',b'{"pill_budget":NaN}',b'{"pill_budget":Infinity}',b'{"pill_budget":1e999}']:
            with self.subTest(raw=raw):self.assertEqual(self.server.request('POST','/api/simulate',raw=raw)[0],400)
        raw=json.dumps(BASE).encode();raw+=b' '*(16384-len(raw))
        self.assertEqual(self.server.request('POST','/api/simulate',raw=raw)[0],200)
        self.assertEqual(self.server.request('POST','/api/simulate',raw=b' '*16385)[0],413)
        self.assertEqual(self.server.request('POST','/api/simulate',BASE,content_type='text/plain')[0],400)
    def test_health_config_are_readonly_and_production_routes_absent(self):
        health=self.server.request('GET','/api/health');self.assertEqual(health[0],200)
        self.assertTrue(health[1]['experimental']);self.assertFalse(health[1]['persistent']);self.assertFalse(health[1]['rewards'])
        config=self.server.request('GET','/api/config');self.assertEqual(config[0],200)
        expected=dict(skill_mp=18,skill_cd=3,skill_damage=200,sustain_damage=40,sustain_cd=2,burst_damage=120,burst_cd=6,shield_hp=90,shield_cd=4,item_cd=3)
        for key,value in expected.items():self.assertEqual(config[1]['rules'][key],value)
        self.assertEqual(config[1]['rules']['burst_initial'],[2,4])
        self.assertEqual({x['value'] for x in config[1]['build_details']},{'sustain','burst','guard'})
        self.assertTrue(config[1]['preparation_rules']['common']);self.assertTrue(config[1]['preparation_rules']['consumables'])
        self.post(BASE);self.assertEqual(self.server.request('GET','/api/config'),config)
        for path in ['/api/state','/api/action','/api/save','/api/load','/api/new-game']:
            self.assertEqual(self.server.request('GET',path)[0],404)
            self.assertEqual(self.server.request('POST',path,{})[0],404)
        self.assertEqual(self.server.request('GET','/../server.py')[0],404)
