"""Manual checkpoints are retired; progression and ownership stay current across restarts."""
import copy
import unittest
import uuid
from tests.r3_support import ClockHTTP
from tests.support import baseline_route, open_db


class R3CheckpointHTTPTests(unittest.TestCase):
    def setUp(self):
        self.server = ClockHTTP().start()
        self.addCleanup(self.server.close)
        self.server.create()

    def enter(self):
        baseline_route(self.server.snapshot, self.server.action)
        return self.server.action('world_enter')

    def slot_text(self):
        with open_db(self.server.data / 'game.db') as db:
            return db.execute('SELECT slot FROM current WHERE user_id=?', (self.server.user_id,)).fetchone()[0]

    def test_save_and_load_endpoints_and_merge_function_are_retired(self):
        from game import growth
        self.enter()
        before = self.server.snapshot()
        for path in ('/api/save', '/api/load'):
            status, body = self.server.request('POST', path, {
                'request_id': str(uuid.uuid4()), 'expected_revision': before['revision']})
            self.assertEqual((status, body['error']['code']), (404, 'NOT_FOUND'), path)
        self.assertFalse(hasattr(growth, 'load_checkpoint'))
        self.assertEqual(self.server.snapshot(), before)

    def test_slot_column_is_passed_through_untouched_by_ordinary_writes(self):
        slot_before = self.slot_text()
        self.enter()
        self.server.action('world_gather', item='ore')
        self.assertEqual(self.slot_text(), slot_before)

    def test_restart_retains_materials_growth_ai_tick_and_full_ownership_state(self):
        self.enter()
        self.server.clock.advance(86400)
        self.server.action('world_gather', item='ore')
        self.server.action('world_gather', item='herb')
        before = self.server.snapshot()
        self.assertEqual(before['state']['world']['xp'], 540)
        self.server.restart()
        again = self.server.snapshot()
        self.assertEqual(again['state']['world'], before['state']['world'],
                         'restart double credited growth or rewound economics')
        self.assertEqual(again['state']['world']['xp'], 540)
        self.server.restart()
        self.assertEqual(self.server.snapshot()['state'], again['state'])

    def test_restart_neither_swallows_new_equipment_nor_revives_dismantled_item(self):
        self.enter()
        crafted=self.server.action('world_craft',recipe='blade',quantity=1)
        r=crafted['state']['world']['r3']
        uid=next(uid for uid,item in r['instances'].items() if item['template_id']=='blade')
        owned=copy.deepcopy(crafted['state']['world'])
        self.server.restart()
        self.assertEqual(self.server.snapshot()['state']['world'],owned,
                         'restart swallowed already-owned equipment')
        self.server.action('world_loot_dismantle',uid=uid)
        consumed=copy.deepcopy(self.server.snapshot()['state']['world'])
        self.assertNotIn(uid,consumed['r3']['instances'])
        self.assertEqual(consumed['r3']['materials']['dust'],1)
        for _ in range(2):
            self.server.restart()
            restored=self.server.snapshot()['state']['world']
            self.assertEqual(restored,consumed,'restart revived item or refunded manufacturing inputs')
            self.assertNotIn(uid,restored['r3']['instances'])
