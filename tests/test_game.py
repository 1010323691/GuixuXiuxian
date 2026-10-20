import concurrent.futures
import hashlib
import sqlite3
import subprocess
import sys
import unittest
import uuid

from tests.support import ROOT, Server, route_to_ending, baseline_route


class GameHTTPTests(unittest.TestCase):
    def setUp(self):
        self.server = Server()
        self.addCleanup(self.server.close)
        self.server.start()

    def new(self, name='测试散修'):
        return self.server.write('/api/new-game', name=name)

    def rejected(self, action, params=None):
        before = self.server.snapshot()
        status, body = self.server.request('POST', '/api/action', {
            'request_id': str(uuid.uuid4()), 'expected_revision': before['revision'],
            'action': action, 'params': params or {}})
        self.assertIn(status, (400, 422), body)
        self.assertFalse(body['ok'])
        self.assertEqual(before, self.server.snapshot())

    def test_initial_projection_and_growth(self):
        empty = self.server.snapshot()
        self.assertEqual(empty['revision'], 0)
        self.assertIsNone(empty['state'])
        self.assertEqual(empty['view']['phase'], 'creation')
        snap = self.new('  道友  ')
        state = snap['state']
        self.assertEqual(state['name'], '道友')
        self.assertEqual((state['hp'], state['mp'], state['realm']), (60, 12, 0))
        self.assertEqual(state['actions_taken'], 0)
        self.assertEqual(self.server.action('cultivate')['state']['cultivation'], 6)
        self.rejected('rest')
        self.rejected('alchemy')
        self.rejected('breakthrough')
        self.rejected('travel', {'region': 'ruins'})
        self.rejected('challenge', {'enemy': 'shadow'})
        self.rejected('attack')
        for entry in self.server.snapshot()['view']['actions']:
            self.assertTrue(entry['enabled'] or entry['reason'])
        self.assertLessEqual(sum(a['primary'] for a in snap['view']['actions']), 1)

    def test_alchemy_trade_and_techniques(self):
        self.new()
        self.server.action('gather')
        self.rejected('alchemy')
        self.server.action('gather')
        state = self.server.action('alchemy')['state']
        self.assertEqual((state['herbs'], state['pills']), (1, 1))
        self.server.action('gather')
        state = self.server.action('sell_herbs')['state']
        self.assertEqual((state['herbs'], state['stones']), (1, 3))
        self.rejected('buy_pill')
        for _ in range(11):
            self.server.action('explore')
        state = self.server.action('upgrade')['state']
        self.assertEqual((state['technique'], state['stones']), (1, 24))
        state = self.server.action('upgrade')['state']
        self.assertEqual((state['technique'], state['stones']), (2, 0))
        self.rejected('upgrade')

    def test_combat_order_cost_defense_and_free_recovery(self):
        self.new()
        self.server.action('challenge', enemy='wolf')
        self.rejected('cultivate')
        state = self.server.action('power_attack')['state']
        self.assertEqual((state['mp'], state['hp'], state['battle']['hp']), (6, 52, 20))
        state = self.server.action('power_attack')['state']
        self.assertEqual((state['mp'], state['hp'], state['battle']['hp']), (0, 52, 4))
        self.rejected('power_attack')
        state = self.server.action('defend')['state']
        self.assertEqual((state['mp'], state['hp']), (3, 45))
        state = self.server.action('attack')['state']
        self.assertIsNone(state['battle'])
        self.assertEqual((state['hp'], state['stones'], state['cultivation']), (45, 6, 4))
        self.assertIn('wolf', state['victories'])
        self.server.action('rest')
        self.server.action('rest')
        self.server.action('challenge', enemy='wolf')
        for _ in range(15):
            if self.server.snapshot()['state']['battle'] is None:
                break
            self.server.action('defend')
        # Extend without attacks to exercise actual defeat, then free recovery.
        for _ in range(40):
            if self.server.snapshot()['state']['battle'] is None:
                break
            self.server.action('defend')
        state = self.server.snapshot()['state']
        self.assertIsNone(state['battle'])
        self.assertEqual((state['hp'], state['region']), (1, 'village'))
        self.assertEqual(state['stones'], 6)
        state = self.server.action('rest')['state']
        self.assertEqual(state['hp'], 31)
        self.server.action('gather')
        self.server.action('cultivate')
        self.server.action('challenge', enemy='wolf')
        before = self.server.snapshot()['state']
        after = self.server.action('flee')['state']
        self.assertEqual(after['hp'], before['hp'])
        self.assertEqual(after['stones'], before['stones'])
        self.assertIsNone(after['battle'])

    def test_complete_legal_route_and_post_ending(self):
        self.new()
        route_to_ending(self.server.snapshot, self.server.action)
        snap = self.server.snapshot()
        self.assertEqual(snap['state']['realm'], 3)
        self.assertTrue({'ape', 'sentinel', 'shadow'}.issubset(snap['state']['victories']))
        self.assertIsNotNone(snap['view']['ending'])
        self.assertLessEqual(snap['state']['actions_taken'], 110)
        self.rejected('challenge', {'enemy': 'shadow'})
        self.rejected('breakthrough')
        self.assertTrue(self.server.action('gather')['state']['completed'])

    def test_exact_gdd_53_action_route_without_optional_resources(self):
        self.new()
        baseline_route(self.server.snapshot, self.server.action)
        state = self.server.snapshot()['state']
        self.assertEqual((state['technique'], state['herbs'], state['pills']), (0, 0, 0))
        self.assertEqual(state['cultivation'], 8)

    def test_slot_restart_and_monotonic_revision(self):
        self.new()
        self.server.action('challenge', enemy='wolf')
        saved = self.server.action('attack')['state']
        checkpoint = self.server.write('/api/save')
        self.assertTrue(checkpoint['save']['exists'])
        changed = self.server.action('defend')
        self.server.stop()
        self.server.start()
        self.assertEqual(self.server.snapshot()['state'], changed['state'])
        restored = self.server.write('/api/load')
        self.assertEqual(restored['state'], saved)
        self.assertGreater(restored['revision'], changed['revision'])
        self.assertTrue(restored['save']['exists'])
        new = self.new('新道友')
        self.assertFalse(new['save']['exists'])
        self.assertGreater(new['revision'], restored['revision'])

    def test_idempotency_latest_snapshot_conflicts_and_restart(self):
        self.new()
        payload = {'request_id': 'stable-id', 'expected_revision': 1, 'action': 'cultivate', 'params': {}}
        status, first = self.server.request('POST', '/api/action', payload)
        self.assertEqual(status, 200)
        latest = self.server.action('gather')
        self.server.stop()
        self.server.start()
        status, duplicate = self.server.request('POST', '/api/action', payload)
        self.assertEqual(status, 200)
        self.assertTrue(duplicate['duplicate'])
        self.assertEqual(duplicate['events'], [])
        self.assertEqual(duplicate['state'], latest['state'])
        self.assertEqual(duplicate['revision'], latest['revision'])
        status, error = self.server.request('POST', '/api/action', {**payload, 'action': 'rest'})
        self.assertEqual((status, error['error']['code']), (409, 'REQUEST_ID_REUSED'))
        status, error = self.server.request('POST', '/api/action', {**payload, 'request_id': 'stale-id'})
        self.assertEqual((status, error['error']['code']), (409, 'STALE_STATE'))
        self.assertEqual(self.server.snapshot()['state'], latest['state'])

    def test_parallel_stale_writes_commit_only_once(self):
        self.new()
        def send(index):
            return self.server.request('POST', '/api/action', {
                'request_id': f'parallel-{index}', 'expected_revision': 1, 'action': 'gather', 'params': {}})
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(send, range(4)))
        self.assertEqual(sorted(status for status, _ in results), [200, 409, 409, 409])
        snap = self.server.snapshot()
        self.assertEqual((snap['revision'], snap['state']['herbs'], snap['state']['actions_taken']), (2, 2, 1))

    def test_default_name_empty_slot_and_long_name(self):
        status, body = self.server.request('POST', '/api/load', {
            'request_id': 'empty-slot', 'expected_revision': 0})
        self.assertEqual((status, body['error']['code']), (422, 'NO_SAVE'))
        self.assertEqual(self.server.snapshot()['revision'], 0)
        state = self.new('   ')['state']
        self.assertEqual(state['name'], '归墟客')
        before = self.server.snapshot()
        status, body = self.server.request('POST', '/api/new-game', {
            'request_id': 'long-name', 'expected_revision': before['revision'], 'name': '道' * 13})
        self.assertEqual(status, 400, body)
        self.assertEqual(self.server.snapshot(), before)

    def test_new_game_retry_cannot_erase_progress_and_old_page_rejected_after_load(self):
        payload = {'request_id': 'new-once', 'expected_revision': 0, 'name': '幂等道友', 'mode': 'free'}
        self.assertEqual(self.server.request('POST', '/api/new-game', payload)[0], 200)
        self.server.action('gather')
        saved = self.server.write('/api/save')
        advanced = self.server.action('cultivate')
        loaded = self.server.write('/api/load')
        self.assertEqual(loaded['state'], saved['state'])
        status, body = self.server.request('POST', '/api/action', {
            'request_id': 'old-tab', 'expected_revision': advanced['revision'], 'action': 'gather', 'params': {}})
        self.assertEqual((status, body['error']['code']), (409, 'STALE_STATE'))
        status, duplicate = self.server.request('POST', '/api/new-game', payload)
        self.assertEqual(status, 200)
        self.assertTrue(duplicate['duplicate'])
        self.assertEqual(duplicate['state'], loaded['state'])
        self.assertEqual(duplicate['revision'], loaded['revision'])

    def test_invalid_inputs_and_origin_do_not_mutate(self):
        self.new()
        before = self.server.snapshot()
        for envelope in [
            {'request_id': 'bool', 'expected_revision': True, 'action': 'gather', 'params': {}},
            {'request_id': '', 'expected_revision': 1, 'action': 'gather', 'params': {}},
            {'request_id': 'missing', 'expected_revision': 1},
            {'request_id': 'bad-type', 'expected_revision': 1, 'action': 'gather', 'params': []},
        ]:
            status, body = self.server.request('POST', '/api/action', envelope)
            self.assertEqual(status, 400, body)
        status, _ = self.server.request('POST', '/api/action', raw=b'{')
        self.assertEqual(status, 400)
        status, _ = self.server.request('POST', '/api/action', {
            'request_id': 'external', 'expected_revision': 1, 'action': 'gather', 'params': {}},
            headers={'Origin': 'https://evil.example'})
        self.assertEqual(status, 403)
        self.rejected('nonexistent')
        self.assertEqual(self.server.snapshot(), before)

    def test_database_lock_rollback(self):
        self.new()
        databases = list(self.server.data.glob('*.sqlite*')) + list(self.server.data.glob('*.db'))
        self.assertEqual(len(set(databases)), 1, 'one documented SQLite database expected')
        before = self.server.snapshot()
        connection = sqlite3.connect(databases[0])
        try:
            connection.execute('BEGIN IMMEDIATE')
            status, body = self.server.request('POST', '/api/action', {
                'request_id': 'locked', 'expected_revision': before['revision'], 'action': 'gather', 'params': {}})
            self.assertEqual((status, body['error']['code']), (503, 'SAVE_FAILED'))
        finally:
            connection.rollback()
            connection.close()
        self.assertEqual(self.server.snapshot(), before)
        self.assertEqual(self.server.action('gather')['state']['herbs'], 2)

    def test_write_failure_after_state_update_rolls_back_entire_transaction(self):
        self.new()
        before = self.server.snapshot()
        database = next(self.server.data.glob('*.db'))
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TRIGGER qa_fail_requests BEFORE INSERT ON requests BEGIN SELECT RAISE(ABORT, 'QA injected write failure'); END")
        payload = {'request_id': 'rollback-once', 'expected_revision': before['revision'], 'action': 'gather', 'params': {}}
        status, body = self.server.request('POST', '/api/action', payload)
        self.assertEqual((status, body['error']['code']), (503, 'SAVE_FAILED'))
        self.assertEqual(self.server.snapshot(), before)
        with sqlite3.connect(database) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM requests WHERE request_id=?', ('rollback-once',)).fetchone()[0], 0)
            connection.execute('DROP TRIGGER qa_fail_requests')
        status, committed = self.server.request('POST', '/api/action', payload)
        self.assertEqual(status, 200)
        self.assertFalse(committed['duplicate'])
        self.assertEqual(committed['state']['herbs'], 2)

    def test_nonfinite_json_is_bad_request_not_storage_failure(self):
        self.new()
        before = self.server.snapshot()
        for raw in [
            b'{"request_id":"infinite-revision","expected_revision":1e999,"action":"gather","params":{}}',
            b'{"request_id":"infinite-param","expected_revision":1,"action":"gather","params":{"amount":1e999}}',
            b'{"request_id":"nan","expected_revision":1,"action":"gather","params":{"amount":NaN}}',
        ]:
            status, body = self.server.request('POST', '/api/action', raw=raw)
            self.assertEqual((status, body['error']['code']), (400, 'BAD_REQUEST'))
        self.assertEqual(self.server.snapshot(), before)

    def test_corrupt_database_refused_without_overwrite(self):
        self.new()
        self.server.stop()
        databases = list(self.server.data.glob('*.sqlite*')) + list(self.server.data.glob('*.db'))
        self.assertEqual(len(set(databases)), 1)
        database = databases[0]
        database.write_bytes(b'not a sqlite database\x00broken')
        original = hashlib.sha256(database.read_bytes()).hexdigest()
        result = subprocess.run([sys.executable, str(ROOT / 'server.py'), '--port', '0', '--data-dir', str(self.server.data)],
            cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(), original)


if __name__ == '__main__':
    unittest.main()
