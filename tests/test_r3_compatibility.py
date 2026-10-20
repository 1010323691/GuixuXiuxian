"""Large free-profile inventories stay compact and keep original semantics."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from game import rules
from game.storage import Store
from tests.support import baseline_route


class R3CompatibilityTests(unittest.TestCase):
    def test_schema2_free_large_stack_and_shared_enhancement_do_not_expand_or_switch_mode(self):
        with tempfile.TemporaryDirectory(prefix='guixu-r3-large-') as folder:
            store=Store(folder)
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
            with sqlite3.connect(Path(folder)/'game.db') as db:
                db.execute('UPDATE current SET state=?,slot=? WHERE id=1',
                           (json.dumps(state),json.dumps(state)))
            reopened=Store(folder).snapshot()
            self.assertEqual(reopened['state'],state)
            self.assertNotIn('r3',reopened['state']['world'])
            self.assertEqual(reopened['state']['world']['inventory']['blade'],999999)
            self.assertEqual(reopened['state']['world']['gear']['blade'],3)
            self.assertLess((Path(folder)/'game.db').stat().st_size,200_000,
                            'million legacy stack was expanded to individual instances')
            loaded=Store(folder).write('load',dict(request_id='fixture-load',expected_revision=reopened['revision']))
            self.assertEqual(loaded['state'],state)
