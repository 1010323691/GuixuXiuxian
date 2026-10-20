"""Parallel test runner: `python -m tests.parallel [-j N] [pattern ...]`.

Each test method runs as its own task in a worker process (class fixtures run per task),
slowest first using durations recorded by the previous run. Every test already owns an
isolated temporary save directory, so tasks never share state. Exit code is non-zero on any
failure or error. The serial entry `python -m unittest discover -s tests` still works.
"""
import argparse
import concurrent.futures
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
DURATIONS = Path(tempfile.gettempdir()) / 'guixu-test-durations.json'


def _ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _ids(item)
        else:
            yield item.id()


def _discover():
    return list(_ids(unittest.defaultTestLoader.discover(str(ROOT / 'tests'), top_level_dir=str(ROOT))))


def _run(test_id):
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    stream = io.StringIO()
    started = time.perf_counter()
    suite = unittest.defaultTestLoader.loadTestsFromName(test_id)
    result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    problems = [(kind, name.id() if hasattr(name, 'id') else str(name), text)
                for kind, items in (('ERROR', result.errors), ('FAIL', result.failures))
                for name, text in items]
    return test_id, time.perf_counter() - started, result.testsRun, len(result.skipped), problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('-j', '--jobs', type=int, default=os.cpu_count() or 4)
    parser.add_argument('patterns', nargs='*', help='only run test ids containing any of these substrings')
    args = parser.parse_args(argv)
    ids = [test_id for test_id in _discover()
           if not test_id.startswith('unittest.loader') and (not args.patterns or any(p in test_id for p in args.patterns))]
    if not ids:
        print('no tests matched'); return 1
    try:
        known = json.loads(DURATIONS.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        known = {}
    ids.sort(key=lambda test_id: -known.get(test_id, 1.0))
    started = time.perf_counter()
    durations, problems, ran, skipped = {}, [], 0, 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=min(args.jobs, len(ids))) as pool:
        for test_id, seconds, count, skips, issues in pool.map(_run, ids):
            durations[test_id] = seconds
            ran += count; skipped += skips; problems.extend(issues)
            print(('F' if issues else '.'), end='', flush=True)
    wall = time.perf_counter() - started
    print()
    for kind, name, text in problems:
        print('=' * 70); print(f'{kind}: {name}'); print('-' * 70); print(text)
    slowest = sorted(durations.items(), key=lambda item: -item[1])[:5]
    print('slowest: ' + ', '.join(f'{name.rsplit(".", 1)[-1]} {seconds:.1f}s' for name, seconds in slowest))
    print(f'Ran {ran} tests in {wall:.1f}s wall ({sum(durations.values()):.1f}s CPU-serial) with {min(args.jobs, len(ids))} workers; '
          f'skipped {skipped}; {"FAILED (" + str(len(problems)) + ")" if problems else "OK"}')
    try:
        DURATIONS.write_text(json.dumps({**known, **durations}), encoding='utf-8')
    except OSError:
        pass
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
