"""Longline checkpoints keep authoritative progression and ownership current."""
import copy
import unittest
import uuid
from tests.r3_support import ClockHTTP
from tests.support import baseline_route


class R3CheckpointHTTPTests(unittest.TestCase):
    def setUp(self):
        self.server = ClockHTTP().start()
        self.addCleanup(self.server.close)
        self.server.create()

    def enter(self):
        baseline_route(self.server.snapshot, self.server.action)
        return self.server.action('world_enter')

    def test_loading_pre_entry_slot_cannot_return_world_character_to_prologue(self):
        self.server.write('/api/save')
        self.enter()
        before = self.server.snapshot()
        status, body = self.server.request('POST', '/api/load', {
            'request_id': str(uuid.uuid4()), 'expected_revision': before['revision']})
        self.assertEqual(status, 422, body)
        self.assertEqual(self.server.snapshot(), before)

    def test_load_retains_materials_growth_ai_tick_and_full_ownership_state(self):
        self.enter()
        self.server.write('/api/save')
        self.server.clock.advance(86400)
        self.server.action('world_gather', item='ore')
        self.server.action('world_gather', item='herb')
        before = self.server.snapshot()
        loaded = self.server.write('/api/load')
        self.assertEqual(loaded['state']['world'], before['state']['world'])
        self.assertEqual(loaded['state']['world']['xp'], 540)
        again = self.server.write('/api/load')
        self.assertEqual(again['state']['world'], loaded['state']['world'],
                         'same checkpoint double credited post-save growth or rewound economics')
        self.server.stop()
        self.server.start()
        self.assertEqual(self.server.snapshot()['state'], again['state'],
                         'automatic persistence failed without a new manual save')

    def test_profile_mismatch_rejected_by_checkpoint_merge_without_mutating_inputs(self):
        from game import growth, rules
        current = self.enter()['state']
        other = rules.new_game('另一人', mode='longline')
        before_current, before_other = copy.deepcopy(current), copy.deepcopy(other)
        with self.assertRaises(rules.GameError):
            growth.load_checkpoint(current, other)
        self.assertEqual(current, before_current)
        self.assertEqual(other, before_other)

    def test_old_checkpoint_neither_swallows_new_equipment_nor_revives_dismantled_item(self):
        self.enter()
        self.server.write('/api/save')
        crafted=self.server.action('world_craft',recipe='blade',quantity=1)
        r=crafted['state']['world']['r3']
        uid=next(uid for uid,item in r['instances'].items() if item['template_id']=='blade')
        owned=copy.deepcopy(crafted['state']['world'])
        self.assertEqual(self.server.write('/api/load')['state']['world'],owned,
                         'slot saved before drop swallowed its already-owned equipment')
        self.server.action('world_loot_dismantle',uid=uid)
        consumed=copy.deepcopy(self.server.snapshot()['state']['world'])
        self.assertNotIn(uid,consumed['r3']['instances'])
        self.assertEqual(consumed['r3']['materials']['dust'],1)
        for _ in range(2):
            restored=self.server.write('/api/load')['state']['world']
            self.assertEqual(restored,consumed,'load revived item or refunded manufacturing inputs')
            self.assertNotIn(uid,restored['r3']['instances'])
