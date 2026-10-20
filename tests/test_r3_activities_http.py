"""Real HTTP daily/weekly actions, no direct progress counter injection."""
import copy
import unittest
from datetime import datetime, timezone, date
from tests.r3_support import ClockHTTP
from tests.support import baseline_route
from tests.r3_route import R3Planner


class R3ActivityHTTPTests(unittest.TestCase):
    def setUp(self):
        self.server=ClockHTTP().start()
        self.addCleanup(self.server.close)
        self.server.create()
        baseline_route(self.server.snapshot,self.server.action)
        self.server.action('world_enter')
        self.p=R3Planner(self.server.snapshot,self.server.action)

    def entries(self):
        return self.p.world()['r3']['activities']['entries']

    def test_daily_two_objectives_after_accept_and_completed_right_survives_midnight_restart_load(self):
        import uuid
        self.p.perform('world_sect_join',sect='sword')
        self.p.perform('world_chat',npc='healer')
        self.p.perform('world_activity_accept',project='social')
        key=next(k for k in self.entries() if k.startswith('d:'))
        self.assertEqual([o['progress'] for o in self.entries()[key]['objectives']],[0,0])
        self.p.cost({'herb':3})
        self.p.perform('world_sect_daily',item='herb')
        self.assertFalse(self.entries()[key]['completed'])
        self.p.perform('world_chat',npc='healer')
        self.assertTrue(self.entries()[key]['completed'])
        self.server.write('/api/save')
        self.server.clock.advance(86400)
        self.server.stop();self.server.start()
        self.p.perform('world_activity_accept',project='artisan')
        self.server.write('/api/load')
        self.assertTrue(self.entries()[key]['completed'])
        before=copy.deepcopy(self.p.world())
        payload=dict(request_id='daily-claim-once',expected_revision=self.server.snapshot()['revision'],
                     action='world_activity_claim',params={'key':key})
        status,claimed=self.server.request('POST','/api/action',payload)
        self.assertEqual(status,200,claimed)
        w=claimed['state']['world']
        self.assertEqual(w['r3']['materials']['dust']-before['r3']['materials']['dust'],1)
        self.assertEqual(w['r3']['materials']['enhance_material']-before['r3']['materials']['enhance_material'],2)
        self.assertEqual(w['xp'],before['xp'])
        self.assertEqual(w['r3']['daily'],before['r3']['daily'])
        status,replay=self.server.request('POST','/api/action',payload)
        self.assertEqual(status,200,replay)
        self.assertTrue(replay['duplicate'])
        self.assertEqual(replay['state'],claimed['state'])
        self.server.write('/api/load')
        self.assertTrue(self.entries()[key]['claimed'])
        status,denied=self.server.request('POST','/api/action',dict(request_id=str(uuid.uuid4()),
            expected_revision=self.server.snapshot()['revision'],action='world_activity_claim',params={'key':key}))
        self.assertEqual(status,422,denied)

    def test_weekly_stars_needs_actual_array_and_valid_boss_then_claims_after_next_week(self):
        today=datetime.fromtimestamp(self.server.clock(),timezone.utc).date()
        anchor=date(1970,1,5)
        offset=next(n for n in range(21) if ((today.toordinal()+n-anchor.toordinal())//7)%3==2)
        self.server.clock.advance(offset*86400)
        # All formations are already maxed before accepting: actual disable/re-enable remains possible.
        for recipe in ['spirit_array','mountain_array','seal_array']:
            while self.p.world()['arrays'][recipe.removesuffix('_array')]<3:
                self.p.craft(recipe)
        self.p.perform('world_activity_week_accept')
        key=next(k for k in self.entries() if k.startswith('w:'))
        self.assertEqual(self.entries()[key]['project'],'stars')
        self.assertFalse(self.entries()[key]['completed'])
        self.p.perform('world_array_toggle',array='spirit')
        self.assertEqual(self.entries()[key]['objectives'][0]['progress'],0)
        self.p.perform('world_array_toggle',array='spirit')
        self.assertEqual(self.entries()[key]['objectives'][0]['progress'],1)
        self.assertFalse(self.entries()[key]['completed'])
        self.p.perform('world_boss_enter')
        self.p.perform('world_defend')
        self.p.perform('world_flee')
        self.assertTrue(self.entries()[key]['completed'])
        self.server.clock.advance(8*86400)
        self.p.perform('world_gather',item='ore')
        before=copy.deepcopy(self.p.world())
        self.p.perform('world_activity_claim',key=key)
        after=self.p.world()
        self.assertEqual(after['r3']['materials']['dust']-before['r3']['materials']['dust'],2)
        self.assertEqual(after['inventory']['wood']-before['inventory'].get('wood',0),6)
        self.assertEqual(after['xp'],before['xp'])
        self.assertEqual(after['r3']['daily'],before['r3']['daily'])
        self.p.perform('world_activity_week_accept')
        self.assertEqual(len([k for k in self.entries() if k.startswith('w:')]),2)

    def test_formal_sect_commission_counts_social_project_without_material_daily_substitute(self):
        self.p.perform('world_sect_join',sect='herb')
        self.p.perform('world_activity_accept',project='social')
        key=next(k for k in self.entries() if k.startswith('d:'))
        self.p.perform('world_sect_accept',type='craft')
        self.p.craft('pill')
        self.assertFalse(self.entries()[key]['completed'])
        self.p.perform('world_sect_claim')
        self.assertEqual(self.entries()[key]['objectives'][0]['progress'],1)
        self.p.perform('world_chat',npc='healer')
        self.assertTrue(self.entries()[key]['completed'])
        before=self.p.world()['xp']
        self.p.perform('world_activity_claim',key=key)
        self.assertEqual(self.p.world()['xp'],before)
        self.assertEqual(self.p.world()['r3']['materials']['dust'],1)
