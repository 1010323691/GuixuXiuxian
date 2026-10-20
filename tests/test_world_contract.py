"""W1 black-box contract checks; require schema2 implementation, never skip it."""
import copy
import concurrent.futures
import sqlite3
import unittest
import uuid

from tests.support import Server, baseline_route


PAGE_IDS = ['world', 'character', 'sects', 'social', 'craft', 'exploration',
            'estate', 'market', 'quests', 'achievements', 'arena']


class WorldContractTests(unittest.TestCase):
    def setUp(self):
        self.server = Server()
        self.addCleanup(self.server.close)
        self.server.start()

    def reject(self, action, params=None, expected_status=None):
        before = self.server.snapshot()
        status, result = self.server.request('POST', '/api/action', {
            'request_id': str(uuid.uuid4()), 'expected_revision': before['revision'],
            'action': action, 'params': params if params is not None else {}})
        if expected_status is None:
            self.assertIn(status, (400, 422), result)
        else:
            self.assertEqual(status, expected_status, result)
        self.assertFalse(result['ok'])
        self.assertEqual(self.server.snapshot(), before, 'rejected operation changed authoritative state')

    def start_world(self):
        self.server.write('/api/new-game', name='九州QA')
        baseline_route(self.server.snapshot, self.server.action)
        snap = self.server.action('world_enter')
        self.assertTrue(snap['state']['world']['active'])
        return snap

    def assert_projection(self, snapshot):
        world = snapshot['view']['world']
        self.assertEqual(world['version'], 2)
        self.assertEqual([page['id'] for page in world['pages']], PAGE_IDS)
        for page in world['pages']:
            with self.subTest(page=page['id']):
                for key in ['label', 'title', 'description']:
                    self.assertIsInstance(page[key], str)
                    self.assertTrue(page[key])
                self.assertIsInstance(page['stats'], list)
                self.assertIsInstance(page['sections'], list)
                self.assertIsInstance(page['actions'], list)
                self.assertTrue(page['stats'] or page['sections'], 'page has only a title, no actual information')
                for stat in page['stats']:
                    self.assertIsInstance(stat['label'], str)
                    self.assertIsInstance(stat['value'], str)
                for section in page['sections']:
                    self.assertIsInstance(section['title'], str)
                    self.assertIsInstance(section.get('body', ''), str)
                    for row in section['rows']:
                        self.assertIsInstance(row['label'], str)
                        self.assertIsInstance(row['value'], str)
                self.assertLessEqual(sum(action['primary'] for action in page['actions']), 1)
                for action in page['actions']:
                    for key in ['id', 'label', 'detail', 'cost', 'effect', 'reason']:
                        self.assertIsInstance(action[key], str)
                    self.assertTrue(action['id'].startswith('world_'))
                    self.assertIs(type(action['enabled']), bool)
                    self.assertIsInstance(action['params'], dict)
                    if not action['enabled']:
                        self.assertTrue(action['reason'])
                    if 'confirm' in action:
                        self.assertIsInstance(action['confirm'], str)
                        self.assertTrue(action['confirm'])
                    names = []
                    for field in action.get('fields', []):
                        names.append(field['name'])
                        self.assertIsInstance(field['label'], str)
                        self.assertIn(field['type'], ['text', 'number', 'select'])
                        self.assertIs(type(field['required']), bool)
                        self.assertNotIn(field['name'], action['params'], 'field overwrites fixed action target')
                        if field['type'] == 'number':
                            self.assertIs(type(field['min']), int)
                            self.assertIs(type(field['max']), int)
                            self.assertLessEqual(field['min'], field['max'])
                        elif field['type'] == 'select':
                            self.assertTrue(field['options'])
                            values = [option['value'] for option in field['options']]
                            self.assertTrue(all(isinstance(value, str) for value in values))
                            self.assertEqual(len(values), len(set(values)))
                    self.assertEqual(len(names), len(set(names)))

    def test_schema2_inactive_world_and_legacy_actions_do_not_tick(self):
        status, health = self.server.request('GET', '/api/health')
        self.assertEqual((status, health['schema_version']), (200, 2))
        created = self.server.write('/api/new-game', name='序章兼容')
        world = copy.deepcopy(created['state']['world'])
        self.assertFalse(world['active'])
        for action in ['cultivate', 'gather', 'explore']:
            self.assertEqual(self.server.action(action)['state']['world'], world)
        before = self.server.snapshot()
        for _ in range(3):
            self.assertEqual(self.server.snapshot(), before)
        self.reject('world_enter', expected_status=422)
        self.reject('world_advance', expected_status=422)

    def test_all_eleven_pages_and_fields_match_frozen_contract(self):
        self.assert_projection(self.start_world())

    def test_world_activation_is_once_and_invalid_actions_are_atomic(self):
        self.start_world()
        self.reject('world_enter', expected_status=422)
        self.reject('world_not_a_real_action', expected_status=400)
        self.reject('world_enter', {'stones': 999999}, expected_status=400)

    def test_nested_world_checkpoint_restart_and_old_page_conflict(self):
        activated = self.start_world()
        saved = self.server.write('/api/save')
        advanced = self.server.action('world_gather', item='herb')
        self.assertEqual(advanced['state']['world']['tick'], activated['state']['world']['tick'] + 1)
        self.server.stop()
        self.server.start()
        self.assertEqual(self.server.snapshot()['state'], advanced['state'])
        loaded = self.server.write('/api/load')
        self.assertEqual(loaded['state'], saved['state'])
        self.assertGreater(loaded['revision'], advanced['revision'])
        status, body = self.server.request('POST', '/api/action', {
            'request_id': str(uuid.uuid4()), 'expected_revision': advanced['revision'],
            'action': 'gather', 'params': {}})
        self.assertEqual((status, body['error']['code']), (409, 'STALE_STATE'))
        self.assertEqual(self.server.snapshot()['state'], loaded['state'])

    def test_active_world_keeps_legacy_history_readonly(self):
        self.start_world()
        for legacy_action in ['gather', 'cultivate', 'explore', 'breakthrough']:
            self.reject(legacy_action, expected_status=422)

    def test_world_duplicate_request_latest_snapshot_and_ai_tick_exactly_once(self):
        before = self.start_world()
        payload = {'request_id': 'world-once', 'expected_revision': before['revision'],
                   'action': 'world_gather', 'params': {'item': 'herb'}}
        status, committed = self.server.request('POST', '/api/action', payload)
        self.assertEqual(status, 200, committed)
        self.assertEqual(committed['state']['world']['tick'], before['state']['world']['tick'] + 1)
        latest = self.server.action('world_gather', item='ore')
        self.server.stop()
        self.server.start()
        status, duplicate = self.server.request('POST', '/api/action', payload)
        self.assertEqual(status, 200, duplicate)
        self.assertTrue(duplicate['duplicate'])
        self.assertEqual(duplicate['events'], [])
        self.assertEqual(duplicate['state'], latest['state'])
        self.assertEqual(duplicate['revision'], latest['revision'])
        status, reused = self.server.request('POST', '/api/action', {**payload, 'params': {'item': 'wood'}})
        self.assertEqual((status, reused['error']['code']), (409, 'REQUEST_ID_REUSED'))
        self.assertEqual(self.server.snapshot()['state'], latest['state'])

    def test_world_concurrent_actions_and_mid_commit_failure_are_atomic(self):
        before = self.start_world()
        def write(index):
            return self.server.request('POST', '/api/action', {
                'request_id': f'world-concurrent-{index}', 'expected_revision': before['revision'],
                'action': 'world_gather', 'params': {'item': 'ore'}})
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(write, range(3)))
        self.assertEqual(sorted(status for status, _ in results), [200, 409, 409])
        after = self.server.snapshot()
        self.assertEqual(after['state']['world']['tick'], before['state']['world']['tick'] + 1)
        database = next(self.server.data.glob('*.db'))
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TRIGGER qa_fail_world BEFORE INSERT ON requests BEGIN SELECT RAISE(ABORT,'QA world commit failure'); END")
        payload = {'request_id': 'world-rollback', 'expected_revision': after['revision'],
                   'action': 'world_gather', 'params': {'item': 'wood'}}
        status, error = self.server.request('POST', '/api/action', payload)
        self.assertEqual((status, error['error']['code']), (503, 'SAVE_FAILED'))
        self.assertEqual(self.server.snapshot(), after, 'state/AI/orders changed after failed commit')
        with sqlite3.connect(database) as connection:
            connection.execute('DROP TRIGGER qa_fail_world')
        status, retry = self.server.request('POST', '/api/action', payload)
        self.assertEqual(status, 200, retry)
        self.assertFalse(retry['duplicate'])
        self.assertEqual(retry['state']['world']['tick'], after['state']['world']['tick'] + 1)


if __name__ == '__main__':
    unittest.main()
