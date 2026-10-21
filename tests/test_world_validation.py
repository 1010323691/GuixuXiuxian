"""Corrupt schema2 fixtures must fail safely before projection or any state write."""
import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from game import rules, world, world_config
from game.storage import Database, Store
from tests.support import fast_store, open_db


class WorldValidationTests(unittest.TestCase):
    def fresh(self):
        return rules.new_game('校验道友')

    def active(self):
        state=self.fresh()
        state.update(realm=3,hp=140,mp=28,region='ruins',
                     victories=['ape','sentinel','shadow'],completed=True)
        return rules.apply_action(state,'world_enter',{})[0]

    def rejects(self,state):
        before=copy.deepcopy(state)
        with self.assertRaises(ValueError):
            rules.validate_state(state)
        self.assertEqual(state,before,'validation must never repair or mutate invalid data')

    def test_legal_initial_null_and_real_battle_snapshots(self):
        rules.validate_state(None)
        initial=self.fresh();before=copy.deepcopy(initial)
        rules.validate_state(initial)
        self.assertEqual(initial,before)
        active=self.active()
        for action,params in [('world_hunt',{}),('world_arena',{'opponent':next(iter(world_config.ARENA_OPPONENTS)),'mode':'local'})]:
            with self.subTest(action=action):
                state=rules.apply_action(active,action,params)[0]
                before=copy.deepcopy(state)
                self.assertIsNotNone(state['world']['battle'])
                rules.validate_state(state)
                rules.project(state)
                self.assertEqual(state,before)

    def test_container_types_reject_valueerror_before_deep_access(self):
        for key,value in [('quests',[]),('dialogue',[]),('disciples',[]),('npc_agents',[]),
                          ('arena',None),('auctions',{}),('battle',[]),('event',[]),
                          ('exploration',[]),('dungeon',[]),('sect_quest',[]),('encounter',[]),
                          ('home_storage',[]),('arrays_enabled',[]),('counters',[])]:
            with self.subTest(field=key):
                state=self.fresh();state['world'][key]=value;self.rejects(state)

    def test_exact_counter_shape_and_non_null_battle_shape(self):
        for key,value in [('counters',{}),('battle',{}),('auctions',[{'item':[]}]),
                          ('arena',{'points':0}),('disciples',{'herbalist':{}})]:
            with self.subTest(field=key):
                state=self.fresh();state['world'][key]=value;self.rejects(state)
        state=self.fresh();state['world']['counters']['unrecognized']=1;self.rejects(state)

    def test_known_ids_enums_and_bounds_in_nested_records(self):
        cases=[('quests',{'unknown_quest':'active'}),('quests',{'unknown_quest':[]}),
               ('dialogue',{'not_a_npc':'text'}),('disciples',{'not_a_disciple':{'xp':0,'mission':None}}),
               ('npc_agents',{'not_a_npc':{'wallet':0,'inventory':{},'turns':0,'last':''}}),
               ('guard_wins',['99']),('secret_wins',['not_a_secret']),
               ('dungeon_wins',['not_a_dungeon:1']),('achievements',['not_an_achievement:0']),
               ('stage',8),('tick',True),('root',{'id':'wood','level':0,'points':0,'awakened':1}),
               ('event',{'id':'not_an_event','name':'bad','end':1}),
               ('encounter',{'id':'not_an_encounter','end':1})]
        for key,value in cases:
            with self.subTest(field=key,value=value):
                state=self.fresh();state['world'][key]=value;self.rejects(state)

    def test_invalid_battle_snapshot_and_targets_rejected(self):
        state=rules.apply_action(self.active(),'world_arena',
                                 {'opponent':next(iter(world_config.ARENA_OPPONENTS)),'mode':'local'})[0]
        for key,value in [('snapshot',{}),('snapshot',{'hp':True,'mp':0,'inventory':{}}),
                          ('snapshot',{'hp':200,'mp':0,'inventory':{'unknown_item':1}}),
                          ('target',[]),('kind',[]),('hp',True),('stage',8)]:
            with self.subTest(field=key):
                broken=copy.deepcopy(state);broken['world']['battle'][key]=value;self.rejects(broken)

    def test_invalid_auction_identity_and_delivery_rejected(self):
        state=self.active()
        self.assertTrue(state['world']['auctions'],'entry must produce genuine NPC escrow orders')
        for key,value in [('item',[]),('id',[]),('seller',[]),('bidder',[]),('delivery',[]),
                          ('delivery',{'unknown_item':1}),('price',True),('settled',1)]:
            with self.subTest(field=key):
                broken=copy.deepcopy(state);broken['world']['auctions'][0][key]=value;self.rejects(broken)

    def test_schema2_corruption_does_not_reset_database(self):
        with tempfile.TemporaryDirectory() as directory:
            store=fast_store(directory)
            path=Path(directory)/'game.db'
            store.snapshot()  # creates the account's empty progress row
            invalid=self.fresh();invalid['world']['quests']=[]
            with open_db(path) as db:
                db.execute('UPDATE current SET state=? WHERE user_id=1',(json.dumps(invalid),))
            before=hashlib.sha256(path.read_bytes()).digest()
            with self.assertRaises(ValueError):Store(Database(directory),1).snapshot()
            self.assertEqual(hashlib.sha256(path.read_bytes()).digest(),before)


if __name__=='__main__':
    unittest.main()
