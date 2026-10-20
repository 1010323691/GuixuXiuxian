"""Real HTTP fixed-window, personal-best world-Boss checks with legal actions."""
import unittest
from datetime import datetime, timezone
from tests.r3_support import ClockHTTP
from tests.support import baseline_route
from tests.r3_route import R3Planner
from game import loot


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

    def personal_damage(self,response):
        frames=response['battle_report']['frames']
        return sum(e['amount'] for f in frames for e in f['events']
                   if e['type']=='damage' and e['target']=='enemy' and e['source']!='npc')

    def test_twelve_round_auto_window_best_only_delta_and_three_attempts(self):
        self.p.perform('world_boss_enter')
        response=self.p.perform('world_auto_battle',strategy='frugal')
        report=response['battle_report']
        self.assertIn(report['outcome'],('window','defeat'))
        self.assertTrue(loot.R.BOSS['minimum_valid_commands']<=report['rounds']<=12,'auto window never exceeds twelve opportunities')
        self.assertIsNone(self.p.world()['battle'])
        period=self.p.world()['r3']['boss'][self.day]
        damage=self.personal_damage(response)
        self.assertGreater(damage,0,'an auto-fighting avatar must deal personal damage')
        self.assertEqual((period['best'],period['attempts'],period['last_damage']),(damage,1,damage))
        coins,_=loot.boss_entitlement(period)
        self.p.perform('world_boss_claim',day=self.day)
        self.assertEqual(self.p.world()['r3']['materials']['boss_coin'],coins)
        self.p.rest()
        self.p.perform('world_boss_enter')
        self.p.perform('world_auto_battle',strategy='frugal')
        self.assertEqual(self.p.world()['r3']['boss'][self.day]['best'],damage,'identical build and strategy must not raise best')
        self.reject('world_boss_claim',day=self.day)
        self.assertEqual(self.p.world()['r3']['materials']['boss_coin'],coins,'participation or equal best must not pay twice')
        self.p.rest()
        self.p.perform('world_boss_enter')
        self.p.perform('world_auto_battle',strategy='frugal')
        self.assertEqual(self.p.world()['r3']['boss'][self.day]['attempts'],3)
        self.reject('world_boss_enter')

    def test_open_boss_cursor_survives_restart_and_checkpoint_never_replays_a_finished_attempt(self):
        self.p.perform('world_boss_enter')
        cursor=self.p.world()['battle']
        self.server.stop();self.server.start()
        self.assertEqual(self.p.world()['battle'],cursor)
        self.server.write('/api/save')
        self.p.perform('world_auto_battle',strategy='frugal')
        self.assertIsNone(self.p.world()['battle'])
        best=self.p.world()['r3']['boss'][self.day]['best']
        self.server.write('/api/load')
        self.assertIsNone(self.p.world()['battle'],'checkpoint resurrected an already settled formal boss attempt')
        self.assertEqual(self.p.world()['r3']['boss'][self.day]['attempts'],1)
        self.assertEqual(self.p.world()['r3']['boss'][self.day]['best'],best)

    def test_companion_damage_excluded_and_midnight_keeps_period_binding(self):
        # Legal social progression unlocks an actual NPC companion.
        for _ in range(6):
            self.p.cost({'herb':2})
            self.p.perform('world_gift',npc='healer')
        self.p.perform('world_friend',npc='healer')
        self.p.perform('world_companion',npc='healer')
        self.p.perform('world_boss_enter')
        self.server.clock.advance(86400)
        response=self.p.perform('world_auto_battle',strategy='frugal')
        frames=response['battle_report']['frames']
        npc=sum(e['amount'] for f in frames for e in f['events'] if e['source']=='npc')
        self.assertGreater(npc,0,'fixture must actually contain companion support damage')
        old=self.p.world()['r3']['boss'][self.day]
        self.assertEqual(old['best'],self.personal_damage(response),'NPC support damage counted as personal damage')
        self.assertEqual(old['last_damage'],old['best'])
        coins,_=loot.boss_entitlement(old)
        self.p.perform('world_boss_claim',day=self.day)
        self.assertEqual(self.p.world()['r3']['materials']['boss_coin'],coins)
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
