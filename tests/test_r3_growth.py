"""Independent R3 time/transaction checks over production real HTTP handlers."""
import concurrent.futures
import hashlib
import sqlite3
import unittest
import uuid

from tests.r3_support import ClockHTTP
from tests.support import baseline_route, open_db


class R3GrowthHTTPTests(unittest.TestCase):
    def setUp(self):
        self.server = ClockHTTP().start()
        self.addCleanup(self.server.close)

    def enter(self, mode=None):
        self.server.create(mode)
        baseline_route(self.server.snapshot, self.server.action)
        return self.server.action('world_enter')

    def db_dump(self):
        with open_db(self.server.data / 'game.db') as db:
            return tuple(db.iterdump())

    def test_before_world_entry_no_whole_day_pack_or_offline_world_progress(self):
        initial = self.server.create()
        self.server.clock.advance(30 * 86400)
        baseline_route(self.server.snapshot, self.server.action)
        entered = self.server.action('world_enter')
        self.assertEqual(entered['state']['world']['xp'], 0)
        self.assertEqual(entered['state']['world']['stage'], 0)

    def test_160_seconds_exact_growth_get_is_database_readonly_then_post_settles(self):
        entered = self.enter()
        before_db = self.db_dump()
        self.server.clock.advance(160)
        previews = [self.server.snapshot() for _ in range(3)]
        self.assertEqual(self.db_dump(), before_db)
        self.assertEqual(previews[0]['view']['growth']['available_micro'], '1000000')
        self.assertEqual(previews[0]['view']['growth']['settled_micro'], '0')
        self.assertEqual(previews[0]['view']['growth']['rate']['per_day'], 540)
        self.assertTrue(all(item['revision'] == entered['revision'] for item in previews))
        # A material action settles real elapsed XP, not action-based XP.
        settled = self.server.action('world_gather', item='ore')
        self.assertEqual(settled['state']['world']['xp'], 1)
        self.assertEqual(settled['state']['world']['tick'], entered['state']['world']['tick'] + 1)
        self.assertEqual(self.server.action('world_gather', item='herb')['state']['world']['xp'], 1)

    def test_long_offline_does_not_auto_breakthrough_or_run_economy_or_cap_xp(self):
        entered = self.enter()
        self.server.clock.advance(2000 * 86400)
        preview = self.server.snapshot()
        self.assertEqual(preview['state']['world']['stage'], 0)
        self.assertEqual(preview['state']['world']['tick'], entered['state']['world']['tick'])
        snap = self.server.action('world_gather', item='ore')
        self.assertEqual(snap['state']['world']['xp'], 1_080_000)
        self.assertFalse(snap['state']['world']['ending'])
        self.assertEqual(snap['state']['world']['stage'], 0)

    def test_repeated_request_after_elapsed_time_never_double_action_or_settle(self):
        entered = self.enter()
        self.server.clock.advance(160)
        payload = {'request_id': str(uuid.uuid4()), 'expected_revision': entered['revision'],
                   'action': 'world_gather', 'params': {'item': 'ore'}}
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.server.request('POST', '/api/action', payload), range(4)))
        self.assertTrue(all(status == 200 for status, _ in results), results)
        self.assertEqual(sum(not body['duplicate'] for _, body in results), 1)
        final = self.server.snapshot()
        self.assertEqual(final['revision'], entered['revision'] + 1)
        self.assertEqual(final['state']['world']['tick'], entered['state']['world']['tick'] + 1)
        self.assertEqual(final['state']['world']['xp'], 1)
        before_db = self.db_dump()
        self.server.clock.advance(160)
        status, duplicate = self.server.request('POST', '/api/action', payload)
        self.assertEqual(status, 200, duplicate)
        self.assertTrue(duplicate['duplicate'])
        self.assertEqual(self.db_dump(), before_db, 'duplicate replay must not commit a second time settlement')

    def test_restart_retains_watermark_and_rollback_clock_cannot_mint_xp(self):
        self.enter()
        self.server.clock.advance(320)
        self.assertEqual(self.server.action('world_gather', item='ore')['state']['world']['xp'], 2)
        self.server.stop()
        self.server.clock.advance(160)
        self.server.start()
        self.assertEqual(self.server.action('world_gather', item='wood')['state']['world']['xp'], 3)
        self.server.clock.advance(-320)
        snap = self.server.action('world_gather', item='herb')
        self.assertEqual(snap['state']['world']['xp'], 3)
        self.server.clock.advance(320)
        self.assertEqual(self.server.action('world_gather', item='ore')['state']['world']['xp'], 3)

    def test_material_actions_and_manual_cultivation_do_not_add_direct_xp(self):
        self.enter()
        for _ in range(3):
            for command, params in [('world_gather', {'item': 'herb'}),
                                    ('world_gather', {'item': 'ore'}),
                                    ('world_cultivate', {})]:
                before = self.server.snapshot()['state']['world']['xp']
                status, body = self.server.request('POST', '/api/action', {
                    'request_id': str(uuid.uuid4()), 'expected_revision': self.server.snapshot()['revision'],
                    'action': command, 'params': params})
                self.assertIn(status, (200, 422), body)
                self.assertEqual(self.server.snapshot()['state']['world']['xp'], before,
                                 'an action added XP with no elapsed real time')

    def test_fractional_time_survives_many_posts_instead_of_flooring_each_second(self):
        self.enter()
        for _ in range(160):
            self.server.clock.advance(1)
            self.server.action('world_gather', item='ore')
        self.assertEqual(self.server.snapshot()['state']['world']['xp'], 1)

    def test_failure_after_state_update_rolls_back_time_and_resources_and_request(self):
        entered = self.enter()
        before = self.db_dump()
        self.server.clock.advance(160)
        with open_db(self.server.data / 'game.db') as db:
            db.execute("CREATE TRIGGER r3_qa_fail BEFORE INSERT ON requests BEGIN SELECT RAISE(ABORT,'qa-after-update'); END")
        payload = {'request_id': 'r3-rollback-after-state', 'expected_revision': entered['revision'],
                   'action': 'world_gather', 'params': {'item': 'ore'}}
        status, body = self.server.request('POST', '/api/action', payload)
        self.assertEqual(status, 503, body)
        with open_db(self.server.data / 'game.db') as db:
            db.execute('DROP TRIGGER r3_qa_fail')
        self.assertEqual(self.db_dump(), before, 'failed commit advanced growth watermark or ownership')
        status, committed = self.server.request('POST', '/api/action', payload)
        self.assertEqual(status, 200, committed)
        self.assertFalse(committed['duplicate'])
        self.assertEqual(committed['state']['world']['xp'], 1)
        self.assertEqual(committed['state']['world']['tick'], entered['state']['world']['tick'] + 1)

    def test_two_distinct_requests_from_same_revision_only_one_commits(self):
        entered = self.enter()
        self.server.clock.advance(160)
        payloads = [{'request_id': str(uuid.uuid4()), 'expected_revision': entered['revision'],
                     'action': 'world_gather', 'params': {'item': item}} for item in ['ore', 'wood']]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda p: self.server.request('POST', '/api/action', p), payloads))
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        snap = self.server.snapshot()
        self.assertEqual(snap['revision'], entered['revision'] + 1)
        self.assertEqual(snap['state']['world']['tick'], entered['state']['world']['tick'] + 1)
        self.assertEqual(snap['state']['world']['xp'], 1)

    def test_corrupt_growth_rate_or_balance_refuses_without_overwriting_database(self):
        import json
        from game.storage import Store
        self.enter()
        self.server.stop()
        with open_db(self.server.data / 'game.db') as db:
            original = db.execute('SELECT state FROM current WHERE id=1').fetchone()[0]
        for field, value in [('rate_num', 10**60), ('balance_micro', 7_000_000)]:
            with self.subTest(field=field):
                state = json.loads(original)
                state['world']['r3']['growth'][field] = value
                with open_db(self.server.data / 'game.db') as db:
                    db.execute('UPDATE current SET state=? WHERE id=1', (json.dumps(state),))
                digest = hashlib.sha256((self.server.data / 'game.db').read_bytes()).hexdigest()
                with self.assertRaises(ValueError):
                    Store(self.server.data, clock=self.server.clock)
                self.assertEqual(hashlib.sha256((self.server.data / 'game.db').read_bytes()).hexdigest(), digest)
        # Restore fixture solely so cleanup never leaves a misleading corrupt test archive.
        with open_db(self.server.data / 'game.db') as db:
            db.execute('UPDATE current SET state=? WHERE id=1', (original,))

    def test_equipping_then_unequipping_treasure_settles_old_rate_without_retroactive_bonus(self):
        import json
        self.enter()
        # Boundary fixture grants an owned, unequipped item; public acquisition has a separate route.
        with open_db(self.server.data / 'game.db') as db:
            state=json.loads(db.execute('SELECT state FROM current WHERE id=1').fetchone()[0])
            uid='fixture-rate-main'
            state['world']['r3']['instances'][uid]=dict(uid=uid,template_id='main_treasure',
                chapter=0,quality=0,enhance=0,effect_type='cultivation',source_receipt='fixture-rate')
            db.execute('UPDATE current SET state=? WHERE id=1',(json.dumps(state),))
        self.server.clock.advance(86400)
        equipped=self.server.action('world_loot_equip',uid=uid)
        self.assertEqual(equipped['view']['growth']['available_micro'],'540000000')
        self.assertAlmostEqual(equipped['view']['growth']['rate']['per_day'],545.4)
        self.server.clock.advance(43200)
        removed=self.server.action('world_loot_unequip',slot='main')
        self.assertEqual(removed['view']['growth']['available_micro'],'812700000')
        self.assertEqual(removed['view']['growth']['rate']['per_day'],540)
        self.server.clock.advance(43200)
        final=self.server.action('world_gather',item='ore')
        self.assertEqual(final['view']['growth']['available_micro'],'1082700000')
