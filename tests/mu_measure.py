"""Manual measurements for the MU QA report (not a unittest module; run `python -m tests.mu_measure [--dir PATH]`).

* default scrypt (n=2**15, r=8, p=1) hash and verify time, single and 4 in parallel
* write latency of the production Store (real fsync, synchronous=FULL, WAL): whole `write()` call and the
  write-transaction window alone (BEGIN IMMEDIATE .. COMMIT), single writer and 4 concurrent accounts
Everything runs in a temporary directory (under --dir when given); the real data/ is never opened.
"""
import argparse
import statistics
import tempfile
import threading
import time
import uuid

from game.auth import PasswordHasher
from game.settings import Settings
from game.storage import Database, Store
from server import App
from tests.support import test_settings


def percentile(values, q):
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(q * len(ordered) + 0.5)) - 1))
    return ordered[index]


def summary(label, values):
    ms = [v * 1000 for v in values]
    print('%-34s n=%-4d p50=%7.2f ms  p95=%7.2f ms  p99=%7.2f ms  max=%7.2f ms' % (
        label, len(ms), percentile(ms, .50), percentile(ms, .95), percentile(ms, .99), max(ms)))


def measure_scrypt():
    hasher = PasswordHasher(Settings())
    hashes, verifies = [], []
    salt = digest = None
    for _ in range(10):
        started = time.perf_counter()
        params, salt, digest = hasher.hash('a-reasonable-passphrase')
        hashes.append(time.perf_counter() - started)
        started = time.perf_counter()
        assert hasher.verify('a-reasonable-passphrase', salt, digest, params)
        verifies.append(time.perf_counter() - started)
    print('scrypt %s  hash: median %.1f ms (min %.1f, max %.1f)   verify: median %.1f ms' % (
        params, statistics.median(hashes) * 1000, min(hashes) * 1000, max(hashes) * 1000, statistics.median(verifies) * 1000))
    results = []

    def one():
        started = time.perf_counter()
        hasher.hash('a-reasonable-passphrase')
        results.append(time.perf_counter() - started)

    threads = [threading.Thread(target=one) for _ in range(4)]
    started = time.perf_counter()
    [t.start() for t in threads]
    [t.join() for t in threads]
    print('scrypt 4 parallel hashes: wall %.1f ms, per-hash max %.1f ms' % ((time.perf_counter() - started) * 1000, max(results) * 1000))


def play(app, user_id, count, durations, tx_durations):
    store = app.store_for(user_id)
    revision = 0
    payload = {'request_id': str(uuid.uuid4()), 'expected_revision': 0, 'name': '测速', 'mode': 'free'}
    store.write('new-game', payload)
    revision = 1
    for index in range(count):
        payload = {'request_id': str(uuid.uuid4()), 'expected_revision': revision, 'action': 'explore' if index % 2 else 'gather', 'params': {}}
        started = time.perf_counter()
        store.write('action', payload)
        durations.append(time.perf_counter() - started)
        revision += 1


def measure_writes(base):
    with tempfile.TemporaryDirectory(prefix='guixu-measure-', dir=base) as folder:
        app = App(folder, settings=test_settings())
        tx_times = []
        original = Database.tx

        def timed_tx(self):
            manager = original(self)

            class Timed:
                def __enter__(inner):
                    inner.t = time.perf_counter()
                    return manager.__enter__()

                def __exit__(inner, *exc):
                    result = manager.__exit__(*exc)
                    tx_times.append(time.perf_counter() - inner.t)
                    return result

            return Timed()

        Database.tx = timed_tx
        try:
            ids = [app.auth.create_account('measure_%d' % i, 'measure-pass-%d' % i) for i in range(5)]
            single = []
            play(app, ids[0], 400, single, tx_times)
            summary('single writer: write() call', single)
            commit_only = [t for t in tx_times[-400:]]
            summary('single writer: write transaction', commit_only)
            tx_times.clear()
            results = [[] for _ in range(4)]
            threads = [threading.Thread(target=play, args=(app, ids[i + 1], 100, results[i], tx_times)) for i in range(4)]
            started = time.perf_counter()
            [t.start() for t in threads]
            [t.join() for t in threads]
            wall = time.perf_counter() - started
            merged = [v for r in results for v in r]
            summary('4 accounts concurrent: write()', merged)
            summary('4 accounts concurrent: transaction', tx_times)
            print('4 accounts concurrent: %d writes in %.2f s (%.1f writes/s)' % (len(merged), wall, len(merged) / wall))
        finally:
            Database.tx = original


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', default=None, help='parent directory for the temporary database (default: system temp)')
    args = parser.parse_args()
    print('target filesystem dir:', args.dir or tempfile.gettempdir())
    measure_scrypt()
    measure_writes(args.dir)


if __name__ == '__main__':
    main()
