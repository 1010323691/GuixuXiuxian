"""Independent arithmetic/oracles for the isolated candidate, not production balance."""
import sys
import copy
import unittest
from lab_support import LAB
sys.path.insert(0,str(LAB))
import engine

BASE=dict(scenario='boss',build='sustain',strategy='aggressive')

def damage(result,source=None,target='enemy'):
    return [e for e in result['events'] if e['type']=='damage' and e['target']==target and (source is None or e['source']==source)]

class LabEngineTests(unittest.TestCase):
    def test_boss_twelve_opportunities_cd_arithmetic_and_npc_exclusion(self):
        r=engine.simulate(dict(BASE,npc=True));m=r['metrics']
        self.assertEqual(r['result']['ticks'],12)
        skill=[e['tick'] for e in r['events'] if e['label']=='归元斩' and e['type']=='damage']
        self.assertEqual(skill,[1,4,7,10])
        self.assertEqual([next(c['remaining'] for c in f['cooldowns'] if c['id']=='skill') for f in r['frames']],[0,2,1,0,2,1,0,2,1,0,2,1,0])
        self.assertEqual([e['tick'] for e in damage(r,'main')],[1,3,5,7,9,11])
        self.assertEqual([e['tick'] for e in damage(r,'secondary')],[2,4,6,8,10,12])
        self.assertEqual([e['tick'] for e in damage(r,'npc')],[3,6,9,12])
        self.assertEqual(m['direct_damage'],4*200+8*100)
        self.assertEqual(m['treasure_damage'],12*40)
        self.assertEqual(m['npc_damage'],4*10)
        self.assertEqual(m['player_damage'],2080)
        self.assertEqual(m['boss_capped_score'],1980)
        self.assertLessEqual(max(e['tick'] for e in r['events']),12)
    def test_burst_first_delay_and_retrigger_do_not_carry_thirteenth_hit(self):
        r=engine.simulate(dict(BASE,build='burst'))
        self.assertEqual([e['tick'] for e in damage(r,'main')],[3,9])
        self.assertEqual([e['tick'] for e in damage(r,'secondary')],[5,11])
        self.assertEqual(r['metrics']['treasure_damage'],4*120)
    def test_zero_mp_has_free_fallback_and_later_legal_skill_without_negative_resources(self):
        r=engine.simulate(BASE,initial={'mp':0})
        self.assertEqual([e['tick'] for e in r['events'] if e['label']=='归元斩' and e['type']=='damage'],[10])
        self.assertEqual(r['metrics']['direct_damage'],11*100+200)
        for f in r['frames']:
            self.assertGreaterEqual(f['player']['mp'],0);self.assertLessEqual(f['player']['mp'],60)
        self.assertEqual(r['result']['ticks'],12)
    def test_frames_events_reconcile_damage_metrics_identity_and_budget_bounds(self):
        for scenario in ['den','forge','tower','boss','dungeon']:
            for build in ['sustain','burst','guard']:
                for strategy in ['balanced','aggressive']:
                    for budgets in [{},dict(pill_budget=3,fire_budget=2,guard_budget=2,soul_budget=2,npc=True)]:
                        with self.subTest(scenario=scenario,build=build,strategy=strategy,budgets=budgets):
                            payload=dict(scenario=scenario,build=build,strategy=strategy,**budgets);before=copy.deepcopy(payload)
                            r=engine.simulate(payload);m=r['metrics'];self.assertEqual(payload,before)
                            self.assertLessEqual(r['result']['ticks'],12 if scenario=='boss' else 120)
                            self.assertEqual(len({e['id'] for e in r['events']}),len(r['events']))
                            self.assertEqual([e for f in r['frames'] for e in f['events']],r['events'])
                            self.assertEqual(sum(e['amount'] for e in damage(r) if e['source']!='npc'),m['player_damage'])
                            self.assertEqual(m['player_damage'],m['direct_damage']+m['treasure_damage'])
                            taken=sum(e['amount'] for e in r['events'] if e['target']=='player' and e['type'] in ['damage','poison'])
                            self.assertEqual(taken,m['damage_taken'])
                            for f in r['frames']:
                                self.assertEqual(f['after']['player'],f['player']);self.assertEqual(f['after']['enemy'],f['enemy'])
                                self.assertTrue(0<=f['player']['hp']<=600);self.assertTrue(0<=f['player']['mp']<=60)
                                self.assertTrue(all(c['remaining']>=0 for c in f['cooldowns']))
                            for source,gap in [('main',6 if build=='burst' else 2),('secondary',6 if build=='burst' else 4 if build=='guard' else 2)]:
                                ticks=sorted({e['tick'] for e in r['events'] if e['source']==source and e['type'] in ['damage','shield']})
                                self.assertTrue(all(b-a>=gap for a,b in zip(ticks,ticks[1:])),(source,ticks))
                            for item in ['pill','fire','guard','soul']:self.assertLessEqual(m[item+'s_used' if item=='pill' else item+'_used'],budgets.get(item+'_budget',0))
    def test_furnace_fire_breaks_two_hundred_shield_without_body_overflow(self):
        r=engine.simulate(dict(scenario='forge',build='sustain',strategy='balanced',fire_budget=2))
        first=r['frames'][1]
        fire=[e for e in first['events'] if e['source']=='player']
        self.assertEqual([(e['type'],e['amount']) for e in fire],[('shield',200)])
        self.assertEqual(first['enemy']['barrier'],75) # 315 - fire200 - main40
        self.assertEqual(first['enemy']['hp'],1260)
    def test_poison_defense_counterplay_and_pill_clear_are_real(self):
        aggressive=engine.simulate(dict(scenario='den',build='sustain',strategy='aggressive'))
        balanced=engine.simulate(dict(scenario='den',build='sustain',strategy='balanced'))
        self.assertTrue(any(e['type']=='poison' for e in aggressive['events']))
        self.assertFalse(any(e['type']=='poison' for e in balanced['events']))
        with_pill=engine.simulate(dict(scenario='den',build='sustain',strategy='balanced',pill_budget=3),initial={'hp':230})
        self.assertGreater(with_pill['metrics']['pills_used'],0)
        self.assertEqual(with_pill['frames'][1]['decision'],'pill')
        self.assertEqual(next(s['value'] for s in with_pill['frames'][1]['statuses'] if s['label']=='残毒'),'0')
    def test_three_nodes_actual_order_no_reset_budget_and_early_loss_cannot_complete_later_nodes(self):
        r=engine.simulate(dict(scenario='dungeon',build='guard',strategy='balanced',pill_budget=3,fire_budget=2,guard_budget=2,soul_budget=2))
        win=engine.simulate(dict(scenario='dungeon',build='guard',strategy='balanced',pill_budget=3,fire_budget=1))
        self.assertEqual(win['result']['outcome'],'win')
        self.assertEqual([n['status'] for n in win['nodes']],['complete']*3)
        victories=[e['node'] for e in r['events'] if e['type']=='victory']
        self.assertEqual(victories,list(range(1,len(victories)+1)))
        self.assertEqual([n['id'] for n in r['nodes'] if n['status']=='complete'],victories)
        bad=engine.simulate(dict(scenario='dungeon',build='burst',strategy='aggressive'),initial={'hp':1,'mp':0})
        self.assertEqual(bad['result']['outcome'],'loss');self.assertEqual(bad['result']['ticks'],1)
        self.assertEqual([n['status'] for n in bad['nodes'][1:]],['locked','locked'])
        self.assertFalse(any(e['node']>1 for e in bad['events']))

    def test_tower_zero_mp_drain_is_capped_at_actual_mana_without_hp_conversion(self):
        r=engine.simulate(dict(scenario='tower',build='sustain',strategy='aggressive'),initial={'mp':0})
        first=r['frames'][1]
        self.assertEqual(first['player']['mp'],0)
        self.assertEqual(first['player']['hp'],501)
        self.assertEqual([e['amount'] for e in first['events'] if e['label']=='常击汲灵'],[-2])

    def test_guard_absorption_ledger_and_decision_reason_match_real_actions(self):
        r=engine.simulate(dict(scenario='boss',build='guard',strategy='balanced'))
        absorbed=[e for e in r['events'] if e['type']=='shield_absorb']
        self.assertEqual([(e['tick'],e['amount']) for e in absorbed],[(3,55),(4,35),(9,55),(10,35)])
        self.assertTrue(all(e['source']=='secondary' and e['target']=='player' and e['amount']>0 for e in absorbed))
        self.assertEqual(sum(e['amount'] for e in absorbed),180)
        self.assertEqual(r['metrics']['damage_prevented'],4*55+180)
        self.assertEqual(r['metrics']['damage_taken'],304)
        self.assertEqual(r['frames'][-1]['player']['hp'],296)
        for f in r['frames'][1:]:
            self.assertTrue(f['decision_reason'])
            events=f['events']
            for e in events:
                if e['type']=='shield_absorb':
                    enemy_hit=next(x for x in events if x['type']=='damage' and x['source']=='enemy')
                    self.assertLess(events.index(e),events.index(enemy_hit))
            if f['decision']=='defend':self.assertIn('防御',f['decision_reason'])
            elif f['decision']=='skill':self.assertIn('归元斩',f['decision_reason'])
            elif f['decision']=='attack':self.assertIn('普攻',f['decision_reason'])
