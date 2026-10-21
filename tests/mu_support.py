"""Shared helpers for the multi-user QA suites (test_mu_*.py, test_terminology.py).

Everything here works on temporary directories only; the real data/ directory is never touched.
"""
import json
import uuid
from contextlib import contextmanager
from pathlib import Path

from tests.support import Server, TestClock, test_settings

ROOT = Path(__file__).resolve().parents[1]


def state_of(client):
    """(status, body) of GET /api/state for this client's cookie."""
    return client.request('GET', '/api/state')


def revision_of(client):
    status, body = state_of(client)
    assert status == 200, body
    return body['revision']


def post_new_game(client, name='甲道友', request_id=None, revision=None, mode='free', **extra):
    """POST /api/new-game through the production routing; returns (status, body)."""
    payload = {'request_id': request_id or str(uuid.uuid4()),
               'expected_revision': revision if revision is not None else revision_of(client),
               'name': name, 'mode': mode}
    payload.update(extra)
    return client.request('POST', '/api/new-game', payload)


def post_action(client, action='explore', params=None, request_id=None, revision=None, **extra):
    """POST /api/action; returns (status, body)."""
    payload = {'request_id': request_id or str(uuid.uuid4()),
               'expected_revision': revision if revision is not None else revision_of(client),
               'action': action, 'params': params or {}}
    payload.update(extra)
    return client.request('POST', '/api/action', payload)


def started_server(**kwargs):
    """A started Server (default account `tester` registered)."""
    return Server(**kwargs).start()


def dump_tables(db_path, tables=('current', 'requests')):
    """Raw rows of the given tables, read through a fresh connection (an independent reader)."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        return {t: conn.execute('SELECT * FROM %s ORDER BY 1,2' % t).fetchall() for t in tables}
    finally:
        conn.close()


def read_progress(db_path, user_id):
    """(revision, state_dict) straight from game.db via a separate connection, or None."""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute('SELECT revision,state FROM current WHERE user_id=?', (user_id,)).fetchone()
        ledger = conn.execute('SELECT count(*) FROM requests WHERE user_id=?', (user_id,)).fetchone()[0]
    finally:
        conn.close()
    return (row[0], json.loads(row[1]), ledger) if row else None


__all__ = ['Server', 'TestClock', 'test_settings', 'ROOT', 'state_of', 'revision_of', 'post_new_game',
           'post_action', 'started_server', 'dump_tables', 'read_progress', 'contextmanager']
