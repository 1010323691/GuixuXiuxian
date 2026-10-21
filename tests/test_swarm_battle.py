"""FB3 swarm battles: real minions in the rules (leader + minions, AoE, targets, scatter, report, validation)."""
import copy
import unittest
from unittest import mock

from game import rules, world, world_config as C
from game import r3_config as R
from tests.support import baseline_route, solo_battles


class SwarmBattleTests(unittest.TestCase):
    def setUp(self):
        self.context = {'now': 1800000000, 'day': '2027-01-15'}
        self.state = rules.new_game('群战QA', mode='longline')
        baseline_route(lambda: {'state': self.state}, self.act)
        self.act('world_enter')

    def act(self, action, **params):
        self.state, events = rules.apply_action(self.state, action, params, context=self.context)
        return events

    def hunt(self):
        self.act('world_hunt')
        return self.state['world']['battle']

    def equip_main(self, quality=2):
        w = self.state['world']
        w['r3']['instances']['fixture-main'] = dict(uid='fixture-main', template_id='main_treasure', chapter=0, quality=quality,
                                                    enhance=0, effect_type='combat', source_receipt='fixture:main')
        w['r3']['equipped']['main'] = 'fixture-main'

    def solo_enemy(self, kind='wild'):
        with mock.patch.dict(C.SWARMS['counts'], clear=True):
            return world._enemy(copy.deepcopy(self.state['world']), kind)

    # ------------------------------------------------------------------ the split
    def test_leader_keeps_original_hp_and_minions_carry_their_share_of_damage(self):
        solo = self.solo_enemy()
        b = self.hunt()
        lo, hi = C.SWARMS['counts']['wild']
        self.assertEqual(len(b['minions']), lo + min(hi - lo, b['stage'] // 2))
        n, share = len(b['minions']), C.SWARMS['minion_hit_pct']
        self.assertEqual((b['hp'], b['max_hp']), (solo['max_hp'], solo['max_hp']), 'leader keeps the full single-enemy hp')
        self.assertEqual((b['attack'], b['heavy']), (solo['attack'] * (100 - share) // 100, solo['heavy'] * (100 - share) // 100))
        chip = max(1, (solo['attack'] + solo['heavy']) * share // 100 // 3 // n)
        each = max(1, solo['max_hp'] * C.SWARMS['minion_hp_pct'] // 100)
        self.assertEqual([(m['id'], m['hp'], m['max_hp'], m['attack']) for m in b['minions']], [('m%d' % (i + 1), each, each, chip) for i in range(n)])
        self.assertEqual(b['minions'][0]['name'], C.SWARMS['names']['wild'] + '甲')
        rules.validate_state(self.state)

    def test_minion_count_grows_with_stage_and_dungeon_boss_has_its_own_band(self):
        w = self.state['world']
        for stage in range(8):
            w['stage'] = stage
            lo, hi = C.SWARMS['counts']['guard']
            self.assertEqual(len(world._enemy(w, 'guard')['minions']), lo + min(hi - lo, stage // 2))
        w['dungeon'] = {'id': 'den', 'difficulty': 1, 'stage': 0, 'round': 2, 'run_id': 'x'}
        self.assertEqual(len(world._enemy(w, 'dungeon', 'den')['minions']), C.SWARMS['counts']['dungeon_boss'][0] + min(2, w['stage'] // 2))

    def test_free_mode_world_boss_and_arena_stay_single(self):
        free = rules.new_game('单体QA')
        state = {'state': free}

        def act(action, **params):
            state['state'], _ = rules.apply_action(state['state'], action, params)
        baseline_route(lambda: {'state': state['state']}, act)
        act('world_enter')
        act('world_hunt')
        self.assertNotIn('minions', state['state']['world']['battle'])
        w = self.state['world']
        for kind, target in (('arena', next(iter(C.ARENA_OPPONENTS))), ('regional', next(iter(C.ARENA_OPPONENTS)))):
            self.assertNotIn('minions', world._enemy(w, kind, target))
        self.assertNotIn('world_boss', C.SWARMS['counts'])

    # ------------------------------------------------------------------ one round
    def round(self, action, target=None):
        w = self.state['world']
        events, trace = [], []
        world._round(w, action, events, trace, target)
        return trace

    def test_minions_chip_every_beat_halved_by_defence_and_stopped_by_the_soul_talisman(self):
        b = self.hunt()
        w = self.state['world']
        chips = [m['attack'] for m in b['minions']]
        hp = w['hp']
        trace = self.round('world_attack')
        minion_hits = [t for t in trace if t['source'] == 'enemy' and t.get('unit')]
        self.assertEqual([(t['unit'], t['amount']) for t in minion_hits], [('m%d' % (i + 1), c) for i, c in enumerate(chips)])
        leader_hit = next(t['amount'] for t in trace if t['source'] == 'enemy' and not t.get('unit'))
        self.assertEqual(hp - w['hp'], leader_hit + sum(chips))
        trace = self.round('world_defend')
        self.assertEqual([t['amount'] for t in trace if t['source'] == 'enemy' and t.get('unit')], [c // 2 for c in chips if c // 2 > 0])
        w['inventory']['soul_talisman'] = 1
        trace = self.round('world_soul')
        self.assertFalse([t for t in trace if t['source'] == 'enemy' and t.get('unit')], 'the soul talisman stops the whole pack')

    def test_single_target_hits_the_chosen_minion_and_a_dead_target_falls_back_to_the_leader(self):
        b = self.hunt()
        b['minions'][0]['hp'] = 1
        leader = b['hp']
        trace = self.round('world_attack', 'm1')
        hits = [t for t in trace if t['source'] == 'player']
        self.assertEqual([(t['type'], t.get('unit')) for t in hits], [('damage', 'm1'), ('fall', 'm1')])
        self.assertEqual((b['minions'][0]['hp'], b['hp']), (0, leader))
        trace = self.round('world_attack', 'm1')
        self.assertEqual([t.get('unit') for t in trace if t['source'] == 'player' and t['type'] == 'damage'], [None], 'a fallen minion is no target')
        self.assertLess(b['hp'], leader)

    def test_main_treasure_and_fire_talisman_hit_every_living_unit(self):
        self.equip_main()
        b = self.hunt()
        b['hp'] = b['max_hp'] = 10 ** 4  # keep every unit standing so each takes the uncapped hit
        for m in b['minions']:
            m['hp'] = m['max_hp'] = 10 ** 4
        trace = self.round('world_defend')
        strikes = [t for t in trace if t['source'] == 'main' and t['type'] == 'damage']
        self.assertEqual([t.get('unit') for t in strikes], [None] + [m['id'] for m in b['minions']])
        self.assertTrue(all(t['aoe'] for t in strikes))
        self.assertEqual(len({t['amount'] for t in strikes if t.get('unit')} | {strikes[0]['amount']}), 1, 'every unit takes the same treasure hit')
        self.state['world']['inventory']['fire_talisman'] = 1
        trace = self.round('world_fire')
        fire = [t for t in trace if t['source'] == 'player' and t['type'] == 'damage']
        self.assertEqual([t.get('unit') for t in fire], [None] + [m['id'] for m in b['minions']])
        self.assertTrue(all(t['aoe'] for t in fire))

    def test_guard_treasure_only_answers_the_leader_heavy_blow(self):
        w = self.state['world']
        w['r3']['instances']['fixture-guard'] = dict(uid='fixture-guard', template_id='guard_treasure', chapter=0, quality=3,
                                                     enhance=0, effect_type='combat', source_receipt='fixture:guard')
        w['r3']['equipped']['guard'] = 'fixture-guard'
        b = self.hunt()
        b['hp'] = b['max_hp'] = 10 ** 4
        for _ in range(3):
            trace = self.round('world_defend')
        absorb = [t for t in trace if t['type'] == 'shield_absorb']
        self.assertEqual(len(absorb), 1)
        self.assertTrue([t for t in trace if t['source'] == 'enemy' and t.get('unit')], 'minion chips still land on the heavy beat')

    def test_leader_fall_scatters_the_pack_and_pays_the_single_enemy_reward(self):
        b = self.hunt()
        b['hp'] = 1
        wallet = self.state['world']['wallet']
        trace = self.round('world_attack')
        types = [t['type'] for t in trace]
        self.assertEqual(types[-2:], ['scatter', 'victory'])
        self.assertEqual(trace[-2]['amount'], len(b['minions']))
        self.assertIsNone(self.state['world']['battle'])
        gained = self.state['world']['wallet'] - wallet
        solo_case = SwarmBattleTests('test_leader_fall_scatters_the_pack_and_pays_the_single_enemy_reward')
        solo_battles(solo_case)
        try:
            solo_case.setUp()
            sb = solo_case.hunt()
            sb['hp'] = 1
            before = solo_case.state['world']['wallet']
            solo_case.round('world_attack')
            self.assertEqual(solo_case.state['world']['wallet'] - before, gained, 'rewards follow the fight kind, not the pack')
        finally:
            solo_case.doCleanups()

    # ------------------------------------------------------------------ the report
    def test_report_lists_units_per_frame_and_tags_events(self):
        self.equip_main()
        self.hunt()
        context = dict(self.context)
        self.state, _ = rules.apply_action(self.state, 'world_auto_battle', {'strategy': 'balanced'}, context=context)
        report = context['battle_report']
        units = report['enemy']['units']
        self.assertEqual([u['id'] for u in units], ['m%d' % (i + 1) for i in range(len(units))])
        self.assertTrue(all(set(u) == {'id', 'name', 'max_hp'} for u in units))
        for frame in report['frames']:
            self.assertEqual([u['id'] for u in frame['units']], [u['id'] for u in units])
        events = [e for f in report['frames'] for e in f['events']]
        self.assertTrue(any(e.get('aoe') for e in events), 'the main treasure strikes the whole pack')
        self.assertEqual(report['outcome'], 'victory')
        survivors = [u for u in report['frames'][-1]['units'] if u['hp'] > 0]
        self.assertEqual('scatter' in [e['type'] for e in events], bool(survivors), 'the pack scatters exactly when some survive the leader')

    # ------------------------------------------------------------------ persistence and validation
    def test_validators_accept_a_live_pack_and_reject_tampering(self):
        self.hunt()
        rules.validate_state(self.state)
        for mutate in (lambda b: b['minions'][0].update(hp=b['minions'][0]['max_hp'] + 1),
                       lambda b: b['minions'][0].update(id='m9'),
                       lambda b: b['minions'][0].update(extra=1),
                       lambda b: b['minions'].extend(copy.deepcopy(b['minions']) * 3),
                       lambda b: b['minions'][0].update(attack=0),
                       lambda b: b.update(minions='many')):
            state = copy.deepcopy(self.state)
            mutate(state['world']['battle'])
            with self.assertRaises(ValueError):
                rules.validate_state(state)
        state = copy.deepcopy(self.state)
        state['world']['battle']['kind'] = 'arena'
        with self.assertRaises(ValueError):
            rules.validate_state(state)

    def test_a_battle_started_before_swarms_finishes_single(self):
        with mock.patch.dict(C.SWARMS['counts'], clear=True):
            b = self.hunt()
        self.assertNotIn('minions', b)
        rules.validate_state(self.state)
        context = dict(self.context)
        self.state, _ = rules.apply_action(self.state, 'world_auto_battle', {'strategy': 'balanced'}, context=context)
        self.assertNotIn('units', context['battle_report']['enemy'])
        self.assertIsNone(self.state['world']['battle'])

    def test_elite_split_passes_the_shape_check(self):
        w = self.state['world']
        leader, minions = world._split(420, 30, 50, 'elite', 1)
        self.assertEqual(leader, {'max_hp': 420, 'attack': 21, 'heavy': 35})
        self.assertEqual(len(minions), C.SWARMS['counts']['elite'][0])
        self.assertGreaterEqual(world._total_hp({'max_hp': 420, 'minions': minions}) // 4, 105, 'the 105 furnace barrier fits the pack bound')
        self.assertNotIn('elite', R.BOSS)  # world boss config stays separate

    def test_balance_against_single_enemy_fights_stays_in_band(self):
        import importlib.util
        from pathlib import Path
        path = Path(__file__).resolve().parents[1] / 'scripts' / 'swarm_balance.py'
        spec = importlib.util.spec_from_file_location('swarm_balance', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with mock.patch('sys.argv', ['swarm_balance.py', '--check']), mock.patch('builtins.print'):
            self.assertEqual(module.main(), 0, 'scripts/swarm_balance.py --check: beats ±15%, remaining hp ±10%, same outcome')


if __name__ == '__main__':
    unittest.main()
