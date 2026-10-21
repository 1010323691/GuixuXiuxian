"""“下一步”提示契约：只复用 _advance_reason 的条件顺序，指向真实可执行事项，不改变任何状态。"""
import unittest

from tests.support import Server, baseline_route


class WorldGuideTests(unittest.TestCase):
    def setUp(self):
        self.server = Server()
        self.addCleanup(self.server.close)
        self.server.start()
        self.server.write('/api/new-game', name='指引QA')
        baseline_route(self.server.snapshot, self.server.action)
        self.snap = self.server.action('world_enter')

    def world(self):
        return self.server.snapshot()['view']['world']

    def test_guide_text_matches_summary_and_targets_a_real_enabled_action(self):
        world = self.world()
        guide = world['guide']
        self.assertEqual(guide['text'], world['summary'])
        self.assertIn(guide['page'], [p['id'] for p in world['pages']])
        if guide['action_id']:
            page = next(p for p in world['pages'] if p['id'] == guide['page'])
            match = [a for a in page['actions'] if a['id'] == guide['action_id'] and a['label'] == guide['label']]
            self.assertTrue(match and match[0]['enabled'], guide)

    def test_reading_the_guide_never_mutates_progress(self):
        before = self.server.snapshot()
        self.world()
        self.assertEqual(self.server.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
