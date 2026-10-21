"""FB3 swarm battles: real minions in the rules (leader + minions, AoE, targets, scatter, report, validation)."""
import copy
import json
from pathlib import Path
import unittest
from unittest import mock

from game import cadence, growth, journey, loot, rules, world, world_config as C
from game import gameplay_config as G
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

    def dungeon_boss(self, target, difficulty=2):
        """A round-2 dungeon boss (venom / mana_seal / furnace shield) carrying a real minion pack."""
        w = self.state['world']
        w['dungeon'] = {'id': target, 'difficulty': difficulty, 'stage': 0, 'round': 2, 'run_id': 'fixture'}
        b = world._enemy(w, 'dungeon', target, difficulty=difficulty)
        w['battle'] = b
        return b

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

    def test_balance_knobs_cannot_invalidate_a_battle_that_is_already_underway(self):
        """Validation reads SWARM_KINDS/MAX_MINIONS, never C.SWARMS: tuning the dials must not 503 live saves."""
        b = self.hunt()
        rules.validate_state(self.state)
        for counts in ({'wild': (len(b['minions']), len(b['minions']))}, {'wild': (1, 1)}, {'wild': (world.MAX_MINIONS, world.MAX_MINIONS)}):
            with mock.patch.dict(C.SWARMS['counts'], counts, clear=False):
                rules.validate_state(self.state)
        with mock.patch.dict(C.SWARMS, {'minion_hp_pct': 50, 'minion_hit_pct': 60}):
            rules.validate_state(self.state)

    def test_elite_validation_survives_balance_changes_and_still_rejects_tampering(self):
        """The elite branch checks invariants instead of recomputing _split from the live knobs."""
        source = json.loads((Path(__file__).parent / 'fixtures' / 'r4_v1_1_released_save.json').read_text(encoding='utf-8'))['current']['state']
        state = growth.upgrade_legacy(source, self.context['now'])
        state = cadence.migrate_legacy(state, self.context['now'])
        journey.migrate(state['world'])
        w = state['world']
        loot.release_run(w)
        w['battle'] = None
        w['dungeon'] = None
        w['stage'] = 1
        w['region'] = 'chisha'
        w['r3']['growth']['rate_num'] = growth.rate_num(state)
        stories = w['r3']['journey']['stories']
        for story in G.STORIES[:2]:
            stories[story['id']] = {'progress': [objective['amount'] for objective in story['objectives']], 'claimed': True}
        story = G.STORIES[2]
        stories[story['id']] = {'progress': [0, 0], 'claimed': False}
        state, _ = rules.apply_action(state, 'world_elite_enter', {'elite': 'caravan_guard'}, context=self.context)
        rules.validate_state(state)
        for counts, hp_pct, hit_pct in (((3, 4), 12, 30), ((1, 1), 40, 10), ((6, 6), 25, 75)):
            with mock.patch.dict(C.SWARMS['counts'], {'elite': counts}, clear=False):
                with mock.patch.dict(C.SWARMS, {'minion_hp_pct': hp_pct, 'minion_hit_pct': hit_pct}):
                    rules.validate_state(state)
        elite = G.ELITES['caravan_guard']
        for mutate in (lambda b: b.update(attack=elite['attack'] + 1),
                       lambda b: b.update(max_hp=elite['hp'] + 1),
                       lambda b: b['minions'][0].update(max_hp=10 ** 6)):
            tampered = copy.deepcopy(state)
            mutate(tampered['world']['battle'])
            with self.assertRaises(ValueError):
                rules.validate_state(tampered)

    def test_tampered_rosters_are_still_rejected(self):
        """Loosening the bound to MAX_MINIONS must not accept an empty, oversized or nonsensical pack."""
        self.hunt()
        mutations = (lambda b: b.update(minions=[]),
                     lambda b: b.update(minions=[dict(id='m%d' % (i + 1), name='x', hp=1, max_hp=1, attack=1) for i in range(world.MAX_MINIONS + 1)]),
                     lambda b: b['minions'][0].update(hp=b['minions'][0]['max_hp'] + 1),
                     lambda b: b['minions'][0].update(attack=-1),
                     lambda b: b['minions'][0].update(name=''))
        for mutation in mutations:
            state = copy.deepcopy(self.state)
            mutation(state['world']['battle'])
            with self.assertRaises(ValueError):
                rules.validate_state(state)

    # ------------------------------------------------------------------ the view
    def test_next_intent_previews_the_damage_the_beat_actually_deals(self):
        """The preview row must equal _incoming (leader + chips); showing the leader alone understates the beat."""
        b = self.hunt()
        w = self.state['world']
        view = world.project(self.state, context=self.context)
        rows = [row for page in view['pages'] for section in page['sections'] for row in section.get('rows', []) if row['label'] == '下一意图']
        self.assertEqual(len(rows), 1, 'the battle section shows exactly one intent row')
        shown = int(rows[0]['value'].rsplit('承伤', 1)[1])
        self.assertEqual(shown, world._incoming(w, b))
        self.assertGreater(shown, b['attack'], 'the pack adds damage the leader row alone does not explain')
        hp = w['hp']
        self.round('world_attack')
        self.assertEqual(hp - w['hp'], shown, 'the preview matches what the beat then deals')

    def test_charge_beat_preview_does_not_claim_zero_damage_while_the_pack_still_chips(self):
        """On the leader's charge beat the row says the leader holds back and still previews the pack's chips."""
        b = self.hunt()
        w = self.state['world']
        b['turn'] = 1
        view = world.project(self.state, context=self.context)
        row = [r for page in view['pages'] for section in page['sections'] for r in section.get('rows', []) if r['label'] == '下一意图'][0]
        self.assertNotIn('0伤害', row['value'])
        self.assertIn('首领不出手', row['value'])
        shown = int(row['value'].rsplit('承伤', 1)[1])
        self.assertEqual(shown, world._incoming(w, b))
        self.assertGreater(shown, 0, 'the pack alone still deals damage on the charge beat')

    # ------------------------------------------------------------------ mechanics crossed with the pack
    def test_venom_with_a_pack_poisons_on_the_heavy_beat_and_the_pack_keeps_chipping(self):
        b = self.dungeon_boss('den')
        chips = [m['attack'] for m in b['minions']]
        b['turn'] = 2  # heavy beat
        trace = self.round('world_attack')
        self.assertEqual(b['poison_turns'], G.DUNGEON_MECHANICS['den']['poison_turns'], 'the heavy blow still poisons with a pack present')
        self.assertEqual([t['amount'] for t in trace if t.get('unit')], chips, 'the pack still chips on the poison beat')
        w = self.state['world']
        hp = w['hp']
        b['turn'] = 0
        trace = self.round('world_attack')
        self.assertEqual([t['amount'] for t in trace if t['type'] == 'poison'], [b['poison_damage']], 'old poison settles on the next beat')
        self.assertEqual(hp - w['hp'], b['attack'] + sum(chips) + b['poison_damage'])
        fresh = self.dungeon_boss('den')
        fresh['turn'] = 2
        self.round('world_defend')
        self.assertEqual(fresh['poison_turns'], 0, 'defending the heavy blow still prevents the poison')

    def test_mana_seal_with_a_pack_drains_on_the_attack_beat_and_the_pack_keeps_chipping(self):
        b = self.dungeon_boss('tower')
        w = self.state['world']
        w['mp'] = 60
        chips = [m['attack'] for m in b['minions']]
        trace = self.round('world_attack')
        drained = min(G.DUNGEON_MECHANICS['tower']['mp_drain'], 60)
        self.assertEqual(w['mp'], 60 - drained, 'the ordinary blow still drains mp with a pack present')
        self.assertEqual([t['amount'] for t in trace if t.get('unit')], chips)
        fresh = self.dungeon_boss('tower')
        w['mp'] = 60
        self.round('world_defend')
        self.assertEqual(w['mp'], 60, 'defending the ordinary blow still avoids the drain')

    def test_furnace_barrier_absorbs_the_strike_and_the_pack_still_reaches_the_body(self):
        b = self.dungeon_boss('forge')
        w = self.state['world']
        barrier, hp, chips = b['barrier'], w['hp'], [m['attack'] for m in b['minions']]
        self.assertGreater(barrier, 0)
        trace = self.round('world_attack')
        absorbed = next(t['amount'] for t in trace if t['type'] == 'shield' and t['source'] == 'player')
        self.assertEqual(b['barrier'], barrier - absorbed, 'the leader strike is eaten by the barrier first')
        self.assertEqual(b['hp'], b['max_hp'], 'no strike damage reaches the leader body')
        leader = next(t['amount'] for t in trace if t['type'] == 'damage' and t['source'] == 'enemy' and not t.get('unit'))
        self.assertEqual(hp - w['hp'], leader + sum(chips), 'the player takes the leader blow plus the pack')
        self.assertEqual([t['amount'] for t in trace if t.get('unit')], chips, 'minion chips ignore the leader barrier')

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
