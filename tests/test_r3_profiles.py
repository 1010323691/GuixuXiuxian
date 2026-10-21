"""R3 public HTTP mode contract. Old suites intentionally select free mode."""
import unittest
import uuid
from tests.support import Server


class R3ProfileHTTPTests(unittest.TestCase):
    def setUp(self):
        self.server = Server().start()
        self.addCleanup(self.server.close)

    def create(self, **extra):
        return self.server.request('POST', '/api/new-game', {
            'request_id': str(uuid.uuid4()),
            'expected_revision': self.server.snapshot()['revision'],
            'name': '长线独立QA', **extra})

    def test_unknown_modes_are_rejected_without_creating_or_overwriting(self):
        for mode in ['fast', '', None, 1, True, {}, []]:
            with self.subTest(mode=mode):
                before = self.server.snapshot()
                status, body = self.create(mode=mode)
                self.assertEqual(status, 400, body)
                self.assertEqual(self.server.snapshot(), before)

    def test_explicit_free_prologue_cultivates_over_time(self):
        status, created = self.create(mode='free')
        self.assertEqual(status, 200, created)
        self.server.clock.advance(30)
        snap = self.server.action('gather')
        self.assertEqual(snap['state']['cultivation'], 6, '自由档同样按时间自动吐纳')
        latest = self.server.action('gather')
        self.server.restart()
        self.assertEqual(self.server.snapshot()['state'], latest['state'])

    def test_http_default_and_explicit_longline_create_independent_profile_ids(self):
        ids = []
        for fields in [{}, {'mode': 'longline'}]:
            status, created = self.create(**fields)
            self.assertEqual(status, 200, created)
            r3 = created['state']['world']['r3']
            self.assertIsInstance(r3['profile_id'], str)
            self.assertTrue(r3['profile_id'])
            ids.append(r3['profile_id'])
            self.assertFalse(created['state']['world']['active'])
        self.assertNotEqual(ids[0], ids[1])
        status, free = self.create(mode='free')
        self.assertEqual(status, 200, free)
        self.assertNotIn('r3', free['state']['world'])
