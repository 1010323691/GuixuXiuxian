"""Independent deterministic reward/accounting boundaries; full battles are separate.

These tests invoke public domain settlement functions on controlled won-run
fixtures. They do not claim that a direct settlement proves dungeon reachability.
"""
import copy
from datetime import datetime, timezone
import unittest
from game import rules, loot
from tests.support import baseline_route


class R3RewardTests(unittest.TestCase):
    def setUp(self):
        self.state = rules.new_game('结算边界QA', mode='longline')
        def legacy(action, **params):
            self.state, _ = rules.apply_action(self.state, action, params, context={'now':1800000000,'day':'2027-01-15'})
            return {'state': self.state}
        baseline_route(lambda: {'state': self.state}, legacy)
        self.state, _ = rules.apply_action(self.state, 'world_enter', {}, context={'now': 1800000000, 'day': '2027-01-15'})
        self.w = self.state['world']

    def won_run(self, day, difficulty=1, now=None):
        # Complete-run is the domain's won-battle settlement entry point.
        # R4 recovery is elapsed UTC, not changing an old day label.
        now = int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp()) if now is None else now
        run = loot.begin_run(self.w, 'den', 0, difficulty, {'day': day, 'now': now})
        loot.complete_run(self.w, run, [])
        return run

    def test_boss_reward_edges_low_participation_caps_and_no_npc_rank_dependency(self):
        period = {'reference': 450, 'participated': True, 'best': 0}
        for damage, expected in [(0,(2,0)), (14,(2,0)), (15,(3,0)),
                                  (100,(8,0)), (113,(9,1)), (180,(14,1)),
                                  (225,(17,2)), (450,(32,4)), (675,(47,6)),
                                  (900,(62,8)), (1200,(62,8))]:
            with self.subTest(damage=damage):
                period['best'] = damage
                self.assertEqual(loot.boss_entitlement(period), expected)
        period['participated'] = False
        self.assertEqual(loot.boss_entitlement(period), (0,0), 'opening a run is not participation')

    def test_reward_recovery_uses_elapsed_time_not_a_fresh_day_label(self):
        # Replaces the approved old UTC-reset rule, retaining no-extra-reward/rewind assertions.
        for _ in range(3):
            self.won_run('2027-01-15',now=1800000000)
        r=self.w['r3']
        before=copy.deepcopy((r['drop_seq'],r['pity'],r['materials']))
        self.won_run('2027-01-16',now=1800000000)
        self.assertEqual((r['drop_seq'],r['pity'],r['materials']),before,
                         'changing only day label reset elapsed-time credit')
        self.won_run('2027-01-15',now=1800028800)
        self.assertEqual(r['drop_seq'],4)
        after=copy.deepcopy((r['drop_seq'],r['pity'],r['materials']))
        self.won_run('2027-01-14',now=1799913600)
        self.assertEqual((r['drop_seq'],r['pity'],r['materials']),after)
        self.assertEqual(r['runs'][next(reversed(r['runs']))]['day'],'2027-01-14',
                         'run snapshot retains its origin label; entitlement remains ledger-based')

    def test_deterministic_template_cycle_and_normal_difficulty_tenth_pity(self):
        obtained = []
        for n in range(1,11):
            self.won_run('2027-02-' + str((n-1)//3+1).zfill(2))
            receipt = self.w['r3']['receipts'][-1]
            obtained.append((receipt['template'],receipt['quality']))
        self.assertEqual([t for t,q in obtained],
                         ['blade','armor','pendant','main_treasure','guard_treasure']*2)
        self.assertEqual([q for t,q in obtained], [0,0,0,0,1,0,0,0,0,2])
        self.assertEqual(self.w['r3']['pity']['1'], 10)
        self.assertEqual(self.w['r3']['pity']['2'], 0)
        self.assertEqual(self.w['r3']['pity']['3'], 0)

    def test_completed_run_cannot_settle_twice_even_with_new_client_request(self):
        run = self.won_run('2027-01-15')
        before = copy.deepcopy(self.w)
        with self.assertRaises(rules.GameError):
            loot.complete_run(self.w, run, [])
        self.assertEqual(self.w, before)
