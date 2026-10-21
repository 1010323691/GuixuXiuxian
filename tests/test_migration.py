"""Pre-multiuser schema1 fixtures: explicit migration into the unclaimed area, then claiming.

The old single-user file layout (`current(id=1)` + `requests`) is built by hand. Every test
asserts that the source stays byte-identical until the final atomic swap, that a verified
backup exists, and that after `claim` the account sees exactly the old progress and ledger.
"""
import hashlib
import concurrent.futures
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import server
from game import legacy
from game.storage import Database, LayoutError, LegacyLayoutError, encode
from tests.support import open_db, test_settings


def legacy_state(name='旧道友'):
    return dict(name=name,realm=0,cultivation=6,hp=60,mp=12,stones=0,herbs=2,
                pills=0,technique=0,region='village',victories=[],battle=None,
                completed=False,actions_taken=2,logs=['第2行 · 旧记录。'])


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.directory=Path(self.folder.name)
        self.path=self.directory/'game.db'
        self.payload={'request_id':'old-request','expected_revision':1,'action':'cultivate','params':{}}
        self.canonical=encode({'endpoint':'action','payload':self.payload})

    def fixture(self,state=True,slot=True):
        current=legacy_state() if state is True else state
        spare=legacy_state('旧备用') if slot is True else slot
        with open_db(self.path) as db:
            db.executescript('CREATE TABLE current (id INTEGER PRIMARY KEY CHECK(id=1), schema_version INTEGER NOT NULL, revision INTEGER NOT NULL, state TEXT NOT NULL, slot TEXT NOT NULL); CREATE TABLE requests (request_id TEXT PRIMARY KEY,payload TEXT NOT NULL);')
            db.execute('INSERT INTO current VALUES(1,1,9,?,?)',(encode(current),encode(spare)))
            db.execute('INSERT INTO requests VALUES(?,?)',('old-request',self.canonical))
        return current,spare

    def digest(self):
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def inspect(self,path=None):
        """Rows of an OLD-format file (the source or a verified backup)."""
        with open_db(path or self.path) as db:
            return (db.execute('SELECT schema_version,revision,state,slot FROM current').fetchone(),
                    db.execute('SELECT request_id,payload FROM requests ORDER BY request_id').fetchall())

    def backups(self):
        return sorted(self.directory.glob('*.bak.db'))

    def claim(self,name='migrator'):
        """Open the migrated database as an App, create the account and claim; returns (app, user_id, record)."""
        app=server.App(self.directory,settings=test_settings())
        user_id=app.auth.create_account(name,'migrator-pass-1')
        record=legacy.claim(app.db,name)
        return app,user_id,record

    def progress(self,app,user_id):
        with app.db.read() as db:
            row=db.execute('SELECT schema_version,revision,state,slot FROM current WHERE user_id=?',(user_id,)).fetchone()
            ledger=db.execute('SELECT request_id,payload FROM requests WHERE user_id=? ORDER BY request_id',(user_id,)).fetchall()
        return row,ledger

    def test_requires_explicit_flag_and_preserves_source_bytes(self):
        self.fixture();before=self.digest()
        with self.assertRaisesRegex(ValueError,'--migrate-save'):
            legacy.migrate_multiuser(self.directory)
        self.assertEqual(self.digest(),before)
        self.assertEqual(self.backups(),[])
        self.assertTrue(legacy.legacy_format_present(self.directory))
        with self.assertRaises(LegacyLayoutError):
            Database(self.directory)
        self.assertEqual(self.digest(),before)
        self.assertFalse((self.directory/'.migrate.lock').exists())

    def test_migrates_into_unclaimed_area_then_claim_preserves_revision_ledger_and_backup(self):
        current,spare=self.fixture();original=self.inspect()
        record=legacy.migrate_multiuser(self.directory,confirm_v1=True)
        self.assertEqual((record.status,record.source_schema,record.revision,record.ledger_count),
                         (legacy.UNCLAIMED,1,9,1))
        self.assertEqual(self.inspect(self.directory/record.backup_file),original)
        self.assertEqual(len(self.backups()),1)
        self.assertFalse(legacy.legacy_format_present(self.directory))
        app,user_id,claimed=self.claim()
        self.assertEqual((claimed.status,claimed.claimed_by),(legacy.CLAIMED,user_id))
        store=app.store_for(user_id)
        snap=store.snapshot()
        self.assertEqual(snap['revision'],9)
        self.assertEqual({k:v for k,v in snap['state'].items() if k!='world'},current)
        self.assertFalse(snap['state']['world']['active'])
        self.assertTrue(snap['sync']['persisted'])
        row,ledger=self.progress(app,user_id)
        self.assertEqual(row[0],2)
        upgraded_slot=json.loads(row[3])
        self.assertEqual({k:v for k,v in upgraded_slot.items() if k!='world'},spare)
        self.assertEqual(ledger,original[1])
        duplicate=store.write('action',self.payload)
        self.assertTrue(duplicate['duplicate'])
        self.assertEqual(duplicate['revision'],9)
        self.assertEqual(duplicate['events'],[])
        restarted=server.App(self.directory,settings=test_settings()).store_for(user_id).snapshot()
        self.assertEqual(restarted['state'],snap['state'])
        self.assertEqual(restarted['revision'],9)

    def test_empty_state_and_slot_stay_null_and_repeat_is_noop(self):
        self.fixture(state=None,slot=None)
        first=legacy.migrate_multiuser(self.directory,confirm_v1=True)
        backups=self.backups()
        app,user_id,_=self.claim()
        snap=app.store_for(user_id).snapshot()
        self.assertIsNone(snap['state'])
        self.assertNotIn('save',snap)
        before=self.progress(app,user_id)
        again=legacy.migrate_multiuser(self.directory,confirm_v1=True)
        self.assertEqual(again.sha256,first.sha256)
        self.assertEqual(self.progress(app,user_id),before)
        self.assertEqual(self.backups(),backups)

    def test_failure_at_final_swap_keeps_original_bytes_and_recoverable_backup(self):
        self.fixture();before=self.digest();original=self.inspect()
        with patch.object(legacy.os,'replace',side_effect=OSError('injected swap failure')):
            with self.assertRaises(legacy.LegacyError):legacy.migrate_multiuser(self.directory,confirm_v1=True)
        self.assertEqual(self.digest(),before)
        self.assertEqual(self.inspect(),original)
        self.assertEqual(len(self.backups()),1)
        self.assertEqual(self.inspect(self.backups()[0]),original)
        self.assertFalse((self.directory/'.migrate.lock').exists())
        self.assertFalse((self.directory/'game.db.migrating').exists())
        legacy.migrate_multiuser(self.directory,confirm_v1=True)  # a re-run simply succeeds
        self.assertFalse(legacy.legacy_format_present(self.directory))

    def test_backup_failure_never_updates_source(self):
        self.fixture();before=self.digest()
        with patch('game.legacy.backup_verified',side_effect=OSError('no space')):
            with self.assertRaises(OSError):legacy.migrate_multiuser(self.directory,confirm_v1=True)
        self.assertEqual(self.digest(),before)
        self.assertEqual(self.inspect()[0][0],1)
        self.assertEqual(self.backups(),[])

    def test_corrupt_or_invalid_slot_refused_without_backup_or_overwrite(self):
        broken=legacy_state();broken['region']=[]
        self.fixture(slot=broken);before=self.digest()
        with self.assertRaises(ValueError):legacy.migrate_multiuser(self.directory,confirm_v1=True)
        self.assertEqual(self.digest(),before)
        self.assertEqual(self.backups(),[])

    def test_migrator_may_not_change_legacy_fields(self):
        self.fixture();before=self.inspect()
        def destructive(state):
            state['stones']=9999
            state['world']={}
            return state
        with patch('game.world.migrate_v1',side_effect=destructive):
            with self.assertRaisesRegex(ValueError,'原有角色字段'):legacy.migrate_multiuser(self.directory,confirm_v1=True)
        self.assertEqual(self.inspect(),before)
        self.assertEqual(self.backups(),[])

    def test_corrupt_database_is_not_replaced(self):
        self.path.write_bytes(b'broken sqlite database')
        before=self.digest()
        with self.assertRaises(ValueError):legacy.migrate_multiuser(self.directory,confirm_v1=True)
        self.assertEqual(self.digest(),before)
        with self.assertRaises(LayoutError):Database(self.directory)
        self.assertEqual(self.digest(),before)
        self.assertEqual(self.backups(),[])

    def test_active_battles_in_current_and_spare_slot_preserved_exactly(self):
        current=legacy_state('林中道友')
        current.update(realm=1,region='forest',hp=50,mp=1,
                       battle={'enemy':'ape','hp':15,'turn':2})
        spare=legacy_state('村中道友')
        spare.update(hp=41,mp=6,battle={'enemy':'wolf','hp':20,'turn':3})
        self.fixture(state=current,slot=spare)
        legacy.migrate_multiuser(self.directory,confirm_v1=True)
        app,user_id,_=self.claim()
        self.assertEqual(app.store_for(user_id).snapshot()['state']['battle'],current['battle'])
        slot=json.loads(self.progress(app,user_id)[0][3])
        self.assertEqual(slot['battle'],spare['battle'])
        self.assertEqual({k:v for k,v in slot.items() if k!='world'},spare)

    def test_unknown_newer_schema_refused_without_byte_changes(self):
        self.fixture()
        with open_db(self.path) as db:
            db.execute('UPDATE current SET schema_version=99')
        before=self.digest()
        with self.assertRaisesRegex(ValueError,'版本'):
            legacy.migrate_multiuser(self.directory,confirm_v1=True)
        self.assertEqual(self.digest(),before)
        self.assertEqual(self.backups(),[])

    def test_existing_migration_lock_blocks_a_second_migration(self):
        self.fixture();before=self.digest()
        (self.directory/'.migrate.lock').write_text('busy',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'迁移'):
            legacy.migrate_multiuser(self.directory,confirm_v1=True)
        self.assertEqual(self.digest(),before)
        self.assertTrue((self.directory/'.migrate.lock').exists(),'a foreign lock must not be removed')

    def test_parallel_migrations_import_once(self):
        self.fixture()
        def migrate(_):
            try:return legacy.migrate_multiuser(self.directory,confirm_v1=True)
            except legacy.LegacyError as exc:return exc
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(migrate,range(2)))
        records=[r for r in results if isinstance(r,legacy.LegacyRecord)]
        self.assertGreaterEqual(len(records),1,results)
        self.assertEqual({r.sha256 for r in records},{records[0].sha256})
        self.assertEqual(len(self.backups()),1)
        app,user_id,_=self.claim()
        self.assertEqual(app.store_for(user_id).snapshot()['revision'],9)

    def test_cli_explicit_migration_then_claim_starts_current_service(self):
        self.fixture();original=self.inspect()
        with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as refused:
            server.main(['--port','0','--data-dir',str(self.directory)])
        self.assertNotEqual(refused.exception.code,0)
        self.assertEqual(self.inspect(),original)
        out=io.StringIO()
        with redirect_stdout(out):
            code=server.main(['--migrate-multiuser','--migrate-save','--data-dir',str(self.directory)])
        self.assertEqual(code,0,out.getvalue())
        self.assertEqual(len(self.backups()),1)
        self.assertEqual(self.inspect(self.backups()[0]),original)
        app=server.App(self.directory,settings=test_settings())
        user_id=app.auth.create_account('cli_claimer','migrator-pass-1')
        out=io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(server.main(['--claim-legacy','cli_claimer','--data-dir',str(self.directory)]),0,out.getvalue())
        with patch.object(server.GameServer,'serve_forever',lambda self:None):
            service=server.main(['--port','0','--data-dir',str(self.directory)])
        status,body,_=server.dispatch(service.app,'GET','/api/health',{'Host':'127.0.0.1:8000'},b'',('127.0.0.1',8000))
        health=json.loads(body)
        self.assertEqual(status,200)
        self.assertEqual(health['schema_version'],2)
        row,ledger=self.progress(service.app,user_id)
        self.assertEqual(row[:2],(2,9))
        self.assertEqual(ledger,original[1])

    def test_unrecognised_layout_versions_and_empty_file_refused_with_original_bytes(self):
        Database(self.directory)
        with open_db(self.path) as db:
            db.execute('PRAGMA user_version=99')
        before=self.digest()
        with self.assertRaises(LayoutError):Database(self.directory)
        self.assertEqual(self.digest(),before)
        empty=Path(self.directory)/'empty'
        empty.mkdir()
        (empty/'game.db').write_bytes(b'')
        with self.assertRaises(LayoutError):Database(empty)
        self.assertEqual((empty/'game.db').read_bytes(),b'')

    def test_v1_layout_missing_a_required_table_is_refused(self):
        Database(self.directory)
        with open_db(self.path) as db:
            db.execute('DROP TABLE legacy_requests')
        before=self.digest()
        with self.assertRaises(LayoutError):Database(self.directory)
        self.assertEqual(self.digest(),before)


if __name__=='__main__':
    unittest.main()
