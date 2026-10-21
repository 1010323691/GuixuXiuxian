"""Large free-profile inventories stay compact and keep original semantics."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from game import rules
from tests.support import baseline_route, fast_store, open_db


class R3CompatibilityTests(unittest.TestCase):
    def test_schema2_free_large_stack_and_shared_enhancement_do_not_expand_or_switch_mode(self):
        with tempfile.TemporaryDirectory(prefix='guixu-r3-large-') as folder:
            store=fast_store(folder)
            store.write('new-game',dict(request_id='fixture-new',expected_revision=0,name='百万旧器',mode='free'))
            state=rules.new_game('百万旧器')
            def action(command,**params):
                nonlocal state
                state,_=rules.apply_action(state,command,params)
                return {'state':state}
            baseline_route(lambda:{'state':state},action)
            action('world_enter')
            state['world']['inventory']['blade']=999999
            state['world']['gear']['blade']=3
            state['world']['equipment']['weapon']='blade'
            rules.validate_state(state)
            with open_db(Path(folder)/'game.db') as db:
                db.execute('UPDATE current SET state=?,slot=? WHERE user_id=1',
                           (json.dumps(state),json.dumps(state)))
            reopened=fast_store(folder).snapshot()
            self.assertEqual(reopened['state'],state)
            self.assertNotIn('r3',reopened['state']['world'])
            self.assertEqual(reopened['state']['world']['inventory']['blade'],999999)
            self.assertEqual(reopened['state']['world']['gear']['blade'],3)
            self.assertLess((Path(folder)/'game.db').stat().st_size,200_000,
                            'million legacy stack was expanded to individual instances')
            again=fast_store(folder).snapshot()
            self.assertEqual(again['state'],state)
            self.assertEqual(again['revision'],reopened['revision'])
