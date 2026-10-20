"""Focused deterministic battle-order fixtures; public routes tested separately."""
import copy
import unittest

from game import rules
from tests.support import baseline_route


class WorldCombatTests(unittest.TestCase):
    def setUp(self):
        self.state = rules.new_game('战斗规则QA')
        baseline_route(lambda: {'state': self.state}, self.act)
        self.act('world_enter')

    def act(self, command, **params):
        self.state, _ = rules.apply_action(self.state, command, params)
        return {'state': self.state}

    def world(self):
        return self.state['world']

    def test_power_cost_24_and_free_killing_blow_has_no_retaliation(self):
        self.act('world_hunt')
        self.act('world_power')
        self.assertEqual((self.world()['mp'], self.world()['hp'], self.world()['battle']['hp']), (36, 180, 26))
        hp = self.world()['hp']
        self.act('world_attack')
        self.assertIsNone(self.world()['battle'])
        self.assertEqual(self.world()['hp'], hp)

    def test_defense_reductions_apply_before_half_damage(self):
        self.act('world_constitution', choice='sturdy')
        self.act('world_skill_learn', skill='mountain')
        self.act('world_skill_equip', skill='mountain')
        self.act('world_craft', recipe='mountain_array', quantity=1)
        self.act('world_hunt')
        self.act('world_defend')
        self.assertEqual(self.world()['hp'], 193, 'floor((20-sturdy2-array2-skill2)*0.5)=7')
        self.assertEqual(self.world()['mp'], 60, 'defense recovery clamps to max')

    def test_stun_advances_intent_and_guard_expires_after_two_opportunities(self):
        # Consumable fixture isolates exact order, not a fabricated full-game route.
        self.world()['inventory'].update(guard_talisman=1, soul_talisman=1)
        rules.validate_state(self.state)
        self.act('world_hunt')
        self.act('world_guard')
        self.assertEqual(self.world()['hp'], 185, 'guard floor20*0.75=15')
        self.act('world_soul')
        self.assertEqual(self.world()['hp'], 185)
        self.assertEqual(self.world()['battle']['turn'], 2)
        self.assertEqual(self.world()['battle']['shield'], 0)
        self.act('world_defend')
        self.assertEqual(self.world()['hp'], 168, 'guard expired, heavy floor35*0.5=17')

    def test_insufficient_mp_rejects_whole_battle_state(self):
        self.act('world_hunt')
        self.world()['mp'] = 23
        before = copy.deepcopy(self.state)
        with self.assertRaises(rules.GameError):
            rules.apply_action(self.state, 'world_power', {})
        self.assertEqual(self.state, before)

    def test_real_auction_delivery_during_simulated_combat_survives_flee(self):
        order = next(order for order in self.world()['auctions'] if order['seller'] != 'player')
        order_id, item, amount = order['id'], order['item'], order['quantity']
        self.act('world_auction_bid', auction=order_id, price=order['base'] + 4)
        before_item = self.world()['inventory'].get(item, 0)
        hp_mp = (self.world()['hp'], self.world()['mp'])
        self.act('world_arena', opponent='swordsman', mode='local')
        for _ in range(8):
            target = next(order for order in self.world()['auctions'] if order['id'] == order_id)
            if target['settled']:
                break
            self.act('world_defend')
        self.assertTrue(target['settled'])
        self.assertEqual(self.world()['inventory'].get(item, 0), before_item + amount)
        self.act('world_flee')
        self.assertEqual((self.world()['hp'], self.world()['mp']), hp_mp)
        self.assertEqual(self.world()['inventory'].get(item, 0), before_item + amount,
                         'restoring simulated inventory erased a real auction delivery')

    def test_delivering_spare_blade_keeps_the_equipped_copy_and_its_stats(self):
        self.act('world_gather', item='ore')
        self.act('world_gather', item='ore')
        self.act('world_craft', recipe='blade', quantity=2)
        self.act('world_equip', item='blade')
        self.act('world_quest_accept', quest='smith_help')
        projected = rules.project(self.state)['world']
        claim = [action for page in projected['pages'] for action in page['actions']
                 if action['id'] == 'world_quest_claim' and action['params'].get('quest') == 'smith_help']
        self.assertEqual(len(claim), 1)
        self.assertTrue(claim[0]['enabled'], claim)
        self.act('world_quest_claim', quest='smith_help')
        self.assertEqual(self.world()['inventory']['blade'], 1)
        self.assertEqual(self.world()['equipment']['weapon'], 'blade')
        self.assertEqual(self.world()['gear']['blade'], 1)
        self.act('world_hunt')
        self.act('world_attack')
        self.assertEqual(self.world()['battle']['hp'], 62, 'remaining equipped blade still adds8 attack')


if __name__ == '__main__':
    unittest.main()
