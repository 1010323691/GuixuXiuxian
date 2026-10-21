"""序章吐纳改为服务端按时间自动结算：不能点击累加，也不能囤积离线时间突破。"""
import unittest

from tests.support import Server, QI_SECONDS


class PrologueQiTests(unittest.TestCase):
    def setUp(self):
        self.server = Server().start()
        self.addCleanup(self.server.close)
        self.server.write('/api/new-game', name='吐纳QA')

    def shown(self):
        return next(r['value'] for r in self.server.snapshot()['view']['resources'] if r['id'] == 'cultivation')

    def test_cultivate_click_is_retired_and_no_button_is_projected(self):
        before = self.server.snapshot()
        self.assertNotIn('cultivate', [a['id'] for a in before['view']['actions']])
        status, body = self.server.request('POST', '/api/action', {
            'request_id': 'click-qi', 'expected_revision': before['revision'], 'action': 'cultivate', 'params': {}})
        self.assertEqual(status, 400, body)
        self.assertEqual(self.server.snapshot(), before)

    def test_one_point_every_interval_and_reading_does_not_write(self):
        revision = self.server.snapshot()['revision']
        self.server.clock.advance(QI_SECONDS * 3 + 2)
        self.assertEqual(self.shown(), 3)
        self.assertEqual(self.server.snapshot()['revision'], revision)
        self.assertEqual(self.server.snapshot()['state']['cultivation'], 0)
        self.assertEqual(self.server.action('gather')['state']['cultivation'], 3)
        self.server.clock.advance(QI_SECONDS - 2)
        self.assertEqual(self.shown(), 4, '余下的 2 秒不会丢')

    def test_stops_at_realm_bottleneck_and_offline_time_is_not_banked(self):
        self.server.clock.advance(86400)
        self.assertEqual(self.shown(), 32)
        view = self.server.snapshot()['view']
        self.assertIn('可以突破', view['objective'])
        self.server.action('breakthrough')
        self.assertEqual(self.server.snapshot()['state']['cultivation'], 0)
        self.assertEqual(self.shown(), 0, '突破后从零计时，离线的一整天不会补发')
        self.server.clock.advance(QI_SECONDS)
        self.assertEqual(self.shown(), 1)

    def test_clock_rewind_never_grants_or_corrupts(self):
        self.server.clock.advance(QI_SECONDS * 2)
        self.server.action('gather')
        self.server.clock.advance(-QI_SECONDS * 5)
        self.assertEqual(self.shown(), 2)
        self.server.action('gather')
        self.assertEqual(self.server.snapshot()['state']['cultivation'], 2)

    def test_progress_survives_restart(self):
        self.server.clock.advance(QI_SECONDS * 4)
        self.server.action('gather')
        self.server.stop()
        self.server.start()
        self.server.clock.advance(QI_SECONDS)
        self.assertEqual(self.shown(), 5)


if __name__ == '__main__':
    unittest.main()
