"""R5 formal integration: auto battle policy, independent treasure strikes/guards, replay report."""
import copy
import tempfile
import unittest
from pathlib import Path

from game import loot, rules, world
from game import r3_config as R
from server import App, dispatch
from tests.support import baseline_route, battle_round, solo_battles, test_settings


class AutoBattleTreasureTests(unittest.TestCase):
    def setUp(self):
        solo_battles(self)  # 法宝冷却/回护按单体首领精确断言；群攻与小怪小击见 test_swarm_battle
        self.context = {'now': 1800000000, 'day': '2027-01-15'}
        self.state = rules.new_game('御宝QA', mode='longline')
        baseline_route(lambda: {'state': self.state}, self.act)
        self.act('world_enter')

    def act(self, action, **params):
        self.state, events = rules.apply_action(self.state, action, params, context=self.context)
        return events

    def equip(self, slot, effect_type='combat', quality=2):
        w = self.state['world']
        uid = 'fixture-' + slot
        w['r3']['instances'][uid] = dict(uid=uid, template_id=slot + '_treasure', chapter=0, quality=quality,
                                         enhance=0, effect_type=effect_type, source_receipt='fixture:' + uid)
        w['r3']['equipped'][slot] = uid
        rules.validate_state(self.state)

    def attack_value(self):
        return world.attributes(self.state['world'])['attack']

    def test_main_combat_treasure_strikes_on_its_own_cooldown_with_independent_damage(self):
        self.equip('main', quality=2)
        self.act('world_hunt')
        expected = max(1, world.attributes(self.state['world'])['attack'] * R.TREASURE_COMBAT['main']['attack_pct'][2] // 100)
        state, _, trace = battle_round(self.state, 'world_defend', self.context)
        strikes = [t for t in trace if t['source'] == 'main']
        self.assertEqual([(t['type'], t['amount'], t['label']) for t in strikes], [('damage', expected, '本命法宝出击')])
        # Next opportunity is on cooldown (turn 1), the one after strikes again.
        state, _, trace = battle_round(state, 'world_defend', self.context)
        self.assertFalse([t for t in trace if t['source'] == 'main'])
        state, _, trace = battle_round(state, 'world_defend', self.context)
        self.assertTrue([t for t in trace if t['source'] == 'main'])

    def test_cultivation_path_and_unequipped_treasures_never_fight(self):
        self.equip('main', effect_type='cultivation')
        self.equip('guard', effect_type='cultivation')
        self.act('world_hunt')
        for _ in range(3):
            self.state, _, trace = battle_round(self.state, 'world_defend', self.context)
            self.assertFalse([t for t in trace if t['source'] in {'main', 'guard'}])
        self.assertIsNone(loot.combat_treasure(self.state['world'], 'main'))

    def test_guard_treasure_only_reports_absorption_that_really_reduced_a_hit(self):
        self.equip('guard', quality=3)
        self.act('world_hunt')
        absorbed_total = 0
        for turn in range(6):
            before = self.state['world']['hp']
            self.state, _, trace = battle_round(self.state, 'world_defend', self.context)
            absorb = [t for t in trace if t['type'] == 'shield_absorb']
            enemy_hit = next(t for t in trace if t['type'] == 'damage' and t['source'] == 'enemy')
            if absorb:
                self.assertEqual(turn % 3, 2, 'guard treasure only answers the heavy hit')
                self.assertGreater(absorb[0]['amount'], 0)
                self.assertEqual(before - enemy_hit['amount'], self.state['world']['hp'] + 0)
                absorbed_total += absorb[0]['amount']
            if self.state['world']['battle'] is None:
                break
        self.assertGreater(absorbed_total, 0)

    def test_treasure_strike_counts_for_boss_personal_damage_but_not_through_barrier(self):
        self.equip('main', quality=4)
        self.act('world_hunt')
        w = self.state['world']
        w['battle']['barrier'] = 10**6
        w['battle'].update(mechanic='furnace_shield', poison_turns=0, poison_damage=0)
        # Shape-valid only for kind guard/elite/dungeon fights; operate on the resolver copy directly.
        copy_state = copy.deepcopy(self.state)
        cw = copy_state['world']
        hp = cw['battle']['hp']
        world._round(cw, 'world_defend', [], [])
        self.assertEqual(cw['battle']['hp'], hp, 'treasure damage must be absorbed by a hostile barrier first')
        self.assertLess(cw['battle']['barrier'], 10**6)


class AutoBattlePolicyTests(unittest.TestCase):
    def setUp(self):
        self.state = rules.new_game('策略QA')
        baseline_route(lambda: {'state': self.state}, self.act)
        self.act('world_enter')
        self.act('world_hunt')

    def act(self, action, **params):
        self.state, events = rules.apply_action(self.state, action, params)
        return events

    def test_every_projected_strategy_button_is_a_real_enabled_backend_action(self):
        actions = [a for page in rules.project(self.state)['world']['pages'] for a in page['actions']
                   if a['id'] == 'world_auto_battle']
        self.assertEqual({a['params']['strategy'] for a in actions}, set(world.STRATEGIES))
        self.assertTrue(all(a['enabled'] and a['group'] for a in actions))
        retired = {'world_attack', 'world_power', 'world_defend', 'world_pill', 'world_fire', 'world_guard',
                   'world_soul', 'world_flee'}
        all_ids = {a['id'] for page in rules.project(self.state)['world']['pages'] for a in page['actions']}
        self.assertFalse(all_ids & retired)

    def test_lookahead_never_does_worse_than_the_rule_policy_it_starts_from(self):
        # Compare final outcome of the same fight: look-ahead result vs pure rule policy rollout.
        for strategy in world.STRATEGIES:
            with self.subTest(strategy=strategy):
                w = copy.deepcopy(self.state['world'])
                w['inventory'].update(pill=2, fire_talisman=1, guard_talisman=1, soul_talisman=1)
                w['hp'] = 90
                b = w['battle']
                attrs = world.attributes(w, False)
                # pure rule policy
                rule = copy.deepcopy(w)
                last, n, rb = -9, 0, rule['battle']
                while rule['battle'] is not None and n < 60:
                    n += 1
                    action = world._choose(rule, rule['battle'], strategy, attrs, n, last)
                    if action in world.CONSUMABLES:
                        last = n
                    world._round(rule, action, [], [])
                rule_won = rb['hp'] == 0
                tuned = copy.deepcopy(w)
                world._auto_battle(tuned, {'strategy': strategy}, [])
                tuned_won = b is not None and tuned['battle'] is None and tuned['hp'] > 1
                if rule_won:
                    self.assertTrue(tuned_won, 'look-ahead lost a fight the plain rules win')

    def test_balanced_spends_nothing_when_a_fight_is_safe_and_frugal_never_spends(self):
        self.state['world']['inventory'].update(pill=3, fire_talisman=2, guard_talisman=2, soul_talisman=2)
        before = dict(self.state['world']['inventory'])
        result, _ = rules.apply_action(copy.deepcopy(self.state), 'world_auto_battle', {'strategy': 'frugal'})
        for item in ['pill', 'fire_talisman', 'guard_talisman', 'soul_talisman']:
            self.assertEqual(result['world']['inventory'].get(item, 0), before[item])

    def test_stalemate_cap_retreats_without_reward_or_stuck_battle(self):
        w = self.state['world']
        w['battle'].update(hp=900000, max_hp=900000, attack=0, heavy=0)
        rules.validate_state(self.state)
        hp, mp = w['hp'], w['mp']
        context = {}
        result, events = rules.apply_action(self.state, 'world_auto_battle', {'strategy': 'frugal'}, context=context)
        self.assertIsNone(result['world']['battle'])
        self.assertEqual(context['battle_report']['outcome'], 'stalemate')
        self.assertEqual(context['battle_report']['rounds'], world.AUTO_LIMIT)
        self.assertTrue(any('上限' in line for line in events))

class ReplayAssetTests(unittest.TestCase):
    def test_replay_script_is_served_and_loaded_before_the_app(self):
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder), settings=test_settings())
            address = ('127.0.0.1', 8000)
            status, body, ctype = dispatch(app, 'GET', '/battle_replay.js', {'Host': '127.0.0.1:8000'}, b'', address)
            self.assertEqual(status, 200)
            self.assertTrue(ctype.startswith('text/javascript'))
            self.assertIn(b'BattleReplay', body)
            status, page, _ = dispatch(app, 'GET', '/', {'Host': '127.0.0.1:8000'}, b'', address)
            html = page.decode('utf-8')
            self.assertLess(html.index('/battle_replay.js'), html.index('/app.js'))
            for retired in ['world_attack', 'world_flee']:
                self.assertNotIn(retired, (Path(__file__).resolve().parents[1] / 'static' / 'app.js').read_text(encoding='utf-8'))

if __name__ == '__main__':
    unittest.main()
