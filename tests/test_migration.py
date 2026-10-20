"""Real schema1 fixtures: explicit migration must preserve both slots and the ledger."""
import hashlib
import concurrent.futures
import json
import sqlite3
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from game.storage import Store, encode


def legacy_state(name='旧道友'):
    return dict(name=name,realm=0,cultivation=6,hp=60,mp=12,stones=0,herbs=2,
                pills=0,technique=0,region='village',victories=[],battle=None,
                completed=False,actions_taken=2,logs=['第2行 · 旧存档。'])


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
        checkpoint=legacy_state('旧检查点') if slot is True else slot
        with sqlite3.connect(self.path) as db:
            db.executescript('CREATE TABLE current (id INTEGER PRIMARY KEY CHECK(id=1), schema_version INTEGER NOT NULL, revision INTEGER NOT NULL, state TEXT NOT NULL, slot TEXT NOT NULL); CREATE TABLE requests (request_id TEXT PRIMARY KEY,payload TEXT NOT NULL);')
            db.execute('INSERT INTO current VALUES(1,1,9,?,?)',(encode(current),encode(checkpoint)))
            db.execute('INSERT INTO requests VALUES(?,?)',('old-request',self.canonical))
        return current,checkpoint

    def digest(self):
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def inspect(self,path=None):
        with sqlite3.connect(path or self.path) as db:
            return (db.execute('SELECT schema_version,revision,state,slot FROM current').fetchone(),
                    db.execute('SELECT request_id,payload FROM requests ORDER BY request_id').fetchall())

    def test_requires_explicit_flag_and_preserves_source_bytes(self):
        self.fixture();before=self.digest()
        with self.assertRaisesRegex(ValueError,'--migrate-save'):
            Store(self.directory)
        self.assertEqual(self.digest(),before)
        self.assertEqual(list(self.directory.glob('*.bak.db')),[])

    def test_migrates_current_and_slot_preserves_revision_ledger_and_backup(self):
        current,slot=self.fixture();original=self.inspect()
        store=Store(self.directory,migrate=True)
        snap=store.snapshot()
        self.assertEqual(snap['revision'],9)
        self.assertEqual({k:v for k,v in snap['state'].items() if k!='world'},current)
        self.assertFalse(snap['state']['world']['active'])
        migrated=self.inspect()
        self.assertEqual(migrated[0][0],2)
        upgraded_slot=json.loads(migrated[0][3])
        self.assertEqual({k:v for k,v in upgraded_slot.items() if k!='world'},slot)
        self.assertEqual(migrated[1],original[1])
        self.assertEqual(self.inspect(store.migration_backup),original)
        duplicate=store.write('action',self.payload)
        self.assertTrue(duplicate['duplicate'])
        self.assertEqual(duplicate['revision'],9)
        self.assertEqual(duplicate['events'],[])
        loaded=store.write('load',{'request_id':'after-migration','expected_revision':9})
        self.assertEqual(loaded['revision'],10)
        self.assertEqual(loaded['state'],upgraded_slot)

    def test_empty_state_and_slot_stay_null_and_repeat_is_noop(self):
        self.fixture(state=None,slot=None)
        first=Store(self.directory,migrate=True)
        self.assertIsNone(first.snapshot()['state'])
        self.assertFalse(first.snapshot()['save']['exists'])
        before=self.inspect();backups=list(self.directory.glob('*.bak.db'))
        second=Store(self.directory,migrate=True)
        self.assertIsNone(second.migration_backup)
        self.assertEqual(self.inspect(),before)
        self.assertEqual(list(self.directory.glob('*.bak.db')),backups)

    def test_failure_after_backup_rolls_back_and_keeps_recoverable_original(self):
        self.fixture()
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TRIGGER deny_migration BEFORE UPDATE ON current BEGIN SELECT RAISE(ABORT,'injected migration failure'); END")
        original=self.inspect()
        with self.assertRaises(sqlite3.Error):Store(self.directory,migrate=True)
        self.assertEqual(self.inspect(),original)
        backups=list(self.directory.glob('*.bak.db'))
        self.assertEqual(len(backups),1)
        self.assertEqual(self.inspect(backups[0]),original)

    def test_backup_failure_never_updates_source(self):
        self.fixture();before=self.digest()
        with patch('game.storage.tempfile.mkstemp',side_effect=OSError('no space')):
            with self.assertRaises(OSError):Store(self.directory,migrate=True)
        self.assertEqual(self.digest(),before)
        self.assertEqual(self.inspect()[0][0],1)

    def test_corrupt_or_invalid_slot_refused_without_backup_or_overwrite(self):
        broken=legacy_state();broken['region']=[]
        self.fixture(slot=broken);before=self.digest()
        with self.assertRaises(ValueError):Store(self.directory,migrate=True)
        self.assertEqual(self.digest(),before)
        self.assertEqual(list(self.directory.glob('*.bak.db')),[])

    def test_migrator_may_not_change_legacy_fields(self):
        self.fixture();before=self.inspect()
        def destructive(state):
            state['stones']=9999
            state['world']={}
            return state
        with patch('game.world.migrate_v1',side_effect=destructive):
            with self.assertRaisesRegex(ValueError,'原有角色字段'):Store(self.directory,migrate=True)
        self.assertEqual(self.inspect(),before)

    def test_corrupt_database_is_not_replaced(self):
        self.path.write_bytes(b'broken sqlite database')
        before=self.digest()
        with self.assertRaises(sqlite3.Error):Store(self.directory,migrate=True)
        self.assertEqual(self.digest(),before)
        self.assertEqual(list(self.directory.glob('*.bak.db')),[])

    def test_active_battles_in_current_and_checkpoint_preserved_exactly(self):
        current=legacy_state('林中道友')
        current.update(realm=1,region='forest',hp=50,mp=1,
                       battle={'enemy':'ape','hp':15,'turn':2})
        checkpoint=legacy_state('村中道友')
        checkpoint.update(hp=41,mp=6,battle={'enemy':'wolf','hp':20,'turn':3})
        self.fixture(state=current,slot=checkpoint)
        store=Store(self.directory,migrate=True)
        self.assertEqual(store.snapshot()['state']['battle'],current['battle'])
        slot=json.loads(self.inspect()[0][3])
        self.assertEqual(slot['battle'],checkpoint['battle'])
        restored=store.write('load',{'request_id':'restore-battle','expected_revision':9})
        self.assertEqual({k:v for k,v in restored['state'].items() if k!='world'},checkpoint)

    def test_unknown_newer_schema_refused_without_byte_changes(self):
        self.fixture()
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE current SET schema_version=99')
        before=self.digest()
        with self.assertRaisesRegex(ValueError,'版本'):
            Store(self.directory,migrate=True)
        self.assertEqual(self.digest(),before)
        self.assertEqual(list(self.directory.glob('*.bak.db')),[])

    def test_parallel_explicit_startups_migrate_once(self):
        self.fixture()
        def migrate(_):
            return Store(self.directory,migrate=True).snapshot()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(migrate,range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(results[0]['revision'],9)
        self.assertEqual(len(list(self.directory.glob('*.bak.db'))),1)

    def test_cli_explicit_migration_starts_schema2_service(self):
        self.fixture()
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1',0))
            port=reservation.getsockname()[1]
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve().parents[1]/'server.py'),
                                  '--port',str(port),'--data-dir',str(self.directory),'--migrate-save'],
                                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                if process.poll() is not None:
                    self.fail('Migration CLI exited before becoming ready')
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health',timeout=.3) as response:
                        health=json.load(response)
                    break
                except OSError:
                    time.sleep(.03)
            else:self.fail('Migration CLI did not become ready')
            self.assertEqual(health['schema_version'],2)
            self.assertEqual(len(list(self.directory.glob('*.bak.db'))),1)
            self.assertEqual(self.inspect()[0][:2],(2,9))
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__=='__main__':
    unittest.main()
