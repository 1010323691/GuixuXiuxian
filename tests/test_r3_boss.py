"""Real HTTP fixed-window, personal-best world-Boss checks with legal actions."""
import unittest
from datetime import datetime, timezone
from tests.r3_support import ClockHTTP
from tests.support import baseline_route
from tests.r3_route import R3Planner


class R3BossHTTPTests(unittest.TestCase):
    def setUp(self):
        self.server=ClockHTTP().start()
        self.addCleanup(self.server.close)
        self.server.create()
        baseline_route(self.server.snapshot,self.server.action)
        self.server.action('world_enter')
        self.p=R3Planner(self.server.snapshot,self.server.action)
        self.day=datetime.fromtimestamp(self.server.clock(),timezone.utc).date().isoformat()

    def reject(self,action,**params):
        import uuid
        before=self.server.snapshot()
        status,body=self.server.request('POST','/api/action',dict(request_id=str(uuid.uuid4()),
            expected_revision=before['revision'],action=action,params=params))
        self.assertEqual(status,422,body)
        self.assertEqual(self.server.snapshot()['state'],before['state'])

    def test_twelve_round_zero_damage_participation_then_best_only_delta_and_three_attempts(self):
        self.p.perform('world_boss_enter')
        for turn in range(12):
            b=self.p.world()['battle']
            self.assertIsNotNone(b,'fixed window ended early without defeat')
            self.assertEqual(b['turn'],turn)
            self.p.perform('world_defend')
        self.assertIsNone(self.p.world()['battle'])
        period=self.p.world()['r3']['boss'][self.day]
        self.assertEqual((period['best'],period['attempts']), (0,1))
        self.p.perform('world_boss_claim',day=self.day)
        self.assertEqual(self.p.world()['r3']['materials']['boss_coin'],2)
        self.p.rest()
        self.p.perform('world_boss_enter')
        self.p.perform('world_attack')
        damage=self.p.world()['battle']['player_damage']
        self.assertEqual(damage,40)
        self.p.perform('world_flee')
        self.p.perform('world_boss_claim',day=self.day)
        self.assertEqual(self.p.world()['r3']['materials']['boss_coin'],4,
                         'best40 entitles4 total; participation must not pay twice')
        self.p.rest()
        self.p.perform('world_boss_enter')
        self.p.perform('world_defend')
        self.p.perform('world_flee')
        self.reject('world_boss_claim',day=self.day)
        self.assertEqual(self.p.world()['r3']['boss'][self.day]['best'],40)
        self.assertEqual(self.p.world()['r3']['materials']['boss_coin'],4)
        self.reject('world_boss_enter')

    def test_empty_exit_no_participation_and_restart_keeps_same_attempt_cursor(self):
        self.p.perform('world_boss_enter')
        self.p.perform('world_flee')
        self.reject('world_boss_claim',day=self.day)
        self.p.perform('world_boss_enter')
        self.p.perform('world_attack')
        cursor=self.p.world()['battle']
        self.server.stop();self.server.start()
        self.assertEqual(self.p.world()['battle'],cursor)
        self.server.write('/api/save')
        self.p.perform('world_defend')
        cursor=self.p.world()['battle']
        self.server.write('/api/load')
        self.assertEqual(self.p.world()['battle'],cursor,'checkpoint replayed an earlier formal boss turn')
        self.assertEqual(self.p.world()['r3']['boss'][self.day]['attempts'],2)

    def test_companion_damage_excluded_and_midnight_keeps_period_binding(self):
        # Legal social progression unlocks an actual NPC companion.
        for _ in range(6):
            self.p.cost({'herb':2})
            self.p.perform('world_gift',npc='healer')
        self.p.perform('world_friend',npc='healer')
        self.p.perform('world_companion',npc='healer')
        self.p.perform('world_boss_enter')
        self.server.clock.advance(86400)
        for _ in range(12):
            self.p.perform('world_defend')
        old=self.p.world()['r3']['boss'][self.day]
        self.assertEqual(old['best'],0,'NPC support damage counted as personal damage')
        self.assertEqual(old['last_damage'],0)
        self.p.perform('world_boss_claim',day=self.day)
        self.assertEqual(self.p.world()['r3']['materials']['boss_coin'],2)
        newday=datetime.fromtimestamp(self.server.clock(),timezone.utc).date().isoformat()
        self.assertNotIn(newday,self.p.world()['r3']['boss'])
        self.p.rest()
        self.p.perform('world_boss_enter')
        self.assertEqual(self.p.world()['r3']['boss'][newday]['attempts'],1)

    def test_clock_rewind_to_previously_unvisited_day_cannot_create_old_period(self):
        self.server.clock.advance(2*86400)
        self.p.perform('world_gather',item='ore')
        effective_day=datetime.fromtimestamp(self.server.clock(),timezone.utc).date().isoformat()
        self.server.clock.advance(-10*86400)
        self.p.perform('world_boss_enter')
        periods=self.p.world()['r3']['boss']
        self.assertEqual(list(periods),[effective_day],
                         'rewinding to an unseen past day minted an extra formal period')
