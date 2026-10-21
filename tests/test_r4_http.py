"""Production HTTP transaction tests for recovered quota and real sweep proofs."""
import concurrent.futures
import copy
import sqlite3
import unittest
import uuid
from tests.r3_support import ClockHTTP
from tests.support import baseline_route, open_db
from tests.r3_route import R3Planner


class R4HTTPTests(unittest.TestCase):
    def setUp(self):
        self.server=ClockHTTP().start()
        self.addCleanup(self.server.close)
        self.server.create();baseline_route(self.server.snapshot,self.server.action)
        self.server.action('world_enter')
        self.p=R3Planner(self.server.snapshot,self.server.action)

    def credits(self):return self.server.snapshot()['view']['world']['loot']['credits']

    def dump(self):
        # Progress rows of the default account only; session bookkeeping legitimately changes with the clock.
        with open_db(self.server.data/'game.db') as db:
            uid=self.server.user_id
            return (db.execute('SELECT * FROM current WHERE user_id=?',(uid,)).fetchall(),
                    db.execute('SELECT * FROM requests WHERE user_id=? ORDER BY request_id',(uid,)).fetchall())

    def reject(self,command,**params):
        before=self.server.snapshot();payload=dict(request_id=str(uuid.uuid4()),expected_revision=before['revision'],action=command,params=params)
        status,body=self.server.request('POST','/api/action',payload)
        self.assertEqual(status,422,body)
        self.assertEqual(self.server.snapshot()['state'],before['state'])

    def test_real_manual_win_then_sweeps_spend_three_and_eight_hour_get_is_readonly(self):
        self.reject('world_dungeon_sweep',dungeon='den',chapter=0,difficulty=1)
        self.p.dungeon(difficulty=1)
        self.assertIn('den:0:1',self.p.world()['r3']['journey']['manual_clears'])
        for _ in range(2):self.p.perform('world_dungeon_sweep',dungeon='den',chapter=0,difficulty=1)
        r=self.p.world()['r3']
        self.assertEqual((r['pity']['1'],r['drop_seq']),(3,3))
        self.assertEqual(self.credits()['available'],0)
        self.assertEqual(r['journey']['manual_clears'],['den:0:1'])
        self.reject('world_dungeon_sweep',dungeon='den',chapter=0,difficulty=1)
        before=self.dump();rev=self.server.snapshot()['revision']
        self.server.clock.advance(28799)
        self.assertEqual(self.credits()['available'],0)
        self.server.clock.advance(1)
        self.assertEqual(self.credits()['available'],1)
        self.assertEqual(self.dump(),before)
        self.assertEqual(self.server.snapshot()['revision'],rev)
        before_r=copy.deepcopy(self.p.world()['r3'])
        self.p.perform('world_dungeon_sweep',dungeon='den',chapter=0,difficulty=1)
        self.assertEqual(self.p.world()['r3']['drop_seq'],before_r['drop_seq']+1)
        self.assertEqual(self.credits()['available'],0)

    def test_full_occupied_run_restart_refund_and_success_do_not_hide_eight_hours(self):
        self.p.perform('world_dungeon_enter',dungeon='den',chapter=0,difficulty=1)
        run=self.p.world()['dungeon']['run_id']
        self.assertEqual((self.credits()['available'],self.credits()['reserved']),(2,1))
        self.server.clock.advance(28800)
        self.server.restart()
        self.assertEqual(self.p.world()['dungeon']['run_id'],run)
        self.assertEqual((self.credits()['available'],self.credits()['reserved']),(2,1))
        self.p.perform('world_dungeon_leave')
        self.assertEqual((self.credits()['available'],self.credits()['reserved']),(3,0))
        self.reject('world_dungeon_leave')
        self.p.dungeon(difficulty=1)
        self.assertEqual(self.credits()['available'],2)
        self.assertEqual(self.credits()['seconds_until_next'],28800)
        self.server.clock.advance(28799)
        self.assertEqual(self.credits()['available'],2)
        self.server.clock.advance(1)
        self.assertEqual(self.credits()['available'],3)

    def test_two_distinct_start_ids_same_revision_only_one_reserves(self):
        before=self.server.snapshot()
        payloads=[dict(request_id=str(uuid.uuid4()),expected_revision=before['revision'],
            action='world_dungeon_enter',params={'dungeon':'den','chapter':0,'difficulty':1}) for _ in range(2)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda p:self.server.request('POST','/api/action',p),payloads))
        self.assertEqual(sorted(s for s,b in results),[200,409],results)
        self.assertEqual((self.credits()['available'],self.credits()['reserved']),(2,1))
        self.assertEqual(self.server.snapshot()['revision'],before['revision']+1)

    def test_same_start_payload_replay_after_time_keeps_reservation_and_database_once(self):
        before=self.server.snapshot()
        payload=dict(request_id='r4-reserve-once',expected_revision=before['revision'],action='world_dungeon_enter',params={'dungeon':'den','chapter':0,'difficulty':1})
        self.assertEqual(self.server.request('POST','/api/action',payload)[0],200)
        db=self.dump();self.server.clock.advance(28800)
        status,duplicate=self.server.request('POST','/api/action',payload)
        self.assertEqual(status,200,duplicate);self.assertTrue(duplicate['duplicate'])
        self.assertEqual(self.dump(),db)
        self.assertEqual((self.credits()['available'],self.credits()['reserved']),(2,1))

    def test_sweep_commit_failure_rolls_back_credit_item_pity_and_can_retry_same_id(self):
        self.p.dungeon(difficulty=1)
        before=self.dump();snap=self.server.snapshot()
        payload=dict(request_id='r4-sweep-transaction',expected_revision=snap['revision'],action='world_dungeon_sweep',params=dict(dungeon='den',chapter=0,difficulty=1))
        with self.server.fail_commit('before'):
            status,body=self.server.request('POST','/api/action',payload)
        self.assertEqual(status,503,body)
        self.assertEqual(self.dump(),before)
        status,body=self.server.request('POST','/api/action',payload)
        self.assertEqual(status,200,body)
        r=body['state']['world']['r3'];old=snap['state']['world']['r3']
        self.assertEqual(r['drop_seq'],old['drop_seq']+1)
        self.assertEqual(r['pity']['1'],old['pity']['1']+1)
        self.assertEqual(r['cadence']['available'],old['cadence']['available']-1)
        status,again=self.server.request('POST','/api/action',payload)
        self.assertEqual(status,200,again);self.assertTrue(again['duplicate'])
        self.assertEqual(again['state'],body['state'])
