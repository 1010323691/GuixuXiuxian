"""Focused boundary fixtures; full routes remain black-box HTTP/browser tests."""
import copy
import unittest

from game.rules import GameError, apply_action, new_game, validate_state


class RuleBoundaryTests(unittest.TestCase):
    def apply(self, state, action, params=None):
        original = copy.deepcopy(state)
        result, events = apply_action(state, action, params or {})
        self.assertEqual(state, original, 'pure rules must not mutate caller state')
        self.assertTrue(events)
        validate_state(result)
        return result

    def reject(self, state, action, params=None):
        original = copy.deepcopy(state)
        with self.assertRaises(GameError):
            apply_action(state, action, params or {})
        self.assertEqual(state, original)

    def test_resource_caps_and_full_action_rejection(self):
        for resource, action, initial in [('cultivation', 'cultivate', 9998), ('herbs', 'gather', 9998)]:
            with self.subTest(resource=resource):
                state = new_game('上限道友')
                state[resource] = initial
                result = self.apply(state, action)
                self.assertEqual(result[resource], 9999)
                self.reject(result, action)
        state = new_game('探索道友')
        state.update(stones=9999, herbs=9998)
        state = self.apply(state, 'explore')
        self.assertEqual((state['stones'], state['herbs']), (9999, 9999))
        self.reject(state, 'explore')
        state.update(pills=9999, herbs=10, stones=10)
        self.reject(state, 'alchemy')
        self.reject(state, 'buy_pill')
        state['stones'] = 9999
        self.reject(state, 'sell_herbs')

    def test_free_recovery_from_one_hp_and_no_resources(self):
        state = new_game('穷困道友')
        state.update(hp=1, mp=0)
        state = self.apply(state, 'rest')
        self.assertEqual((state['hp'], state['mp']), (31, 8))
        state = self.apply(state, 'rest')
        self.assertEqual((state['hp'], state['mp']), (60, 12))
        self.reject(state, 'rest')
        state = self.apply(state, 'gather')
        state = self.apply(state, 'cultivate')
        self.assertEqual((state['herbs'], state['cultivation'], state['stones']), (2, 6, 0))

    def test_pill_effect_precedes_enemy_and_clamps_independently(self):
        state = new_game('丹药道友')
        state.update(hp=50, mp=0, pills=1, battle={'enemy': 'wolf', 'hp': 36, 'turn': 0})
        result = self.apply(state, 'use_pill')
        self.assertEqual((result['hp'], result['mp'], result['pills']), (52, 6, 0))
        self.assertEqual(result['battle']['turn'], 1)
        self.reject(result, 'use_pill')
        state.update(hp=60, mp=12)
        self.reject(state, 'use_pill')

    def test_invalid_values_and_extra_parameters(self):
        state = new_game('边界道友')
        self.reject(state, 'gather', {'amount': 9999})
        self.reject(state, 'travel', {'region': 'village'})
        self.reject(state, 'challenge', {'enemy': 'not-real'})
        for key, value in [('stones', True), ('hp', -1), ('mp', 13), ('herbs', 10000)]:
            broken = copy.deepcopy(state)
            broken[key] = value
            with self.subTest(key=key), self.assertRaises((ValueError, GameError)):
                validate_state(broken)

    def test_log_retention_and_successful_action_counter(self):
        state = new_game('日志道友')
        for _ in range(110):
            state = self.apply(state, 'gather')
        self.assertEqual(state['actions_taken'], 110)
        self.assertEqual(len(state['logs']), 100)


if __name__ == '__main__':
    unittest.main()
