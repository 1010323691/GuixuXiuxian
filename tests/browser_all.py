"""Run the Playwright browser suites concurrently: `python -m tests.browser_all [-j N] [suite ...]`.

Each suite is its own process with its own server, random port, temporary data directory and
artifacts folder, so they do not share state. Slowest suites start first. Output of each suite is
kept in a temp log and printed only for failures. Exit code is non-zero if any suite fails.
"""
import argparse
import concurrent.futures
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
# slowest first (serial seconds measured on the dev machine): longest suites should start earliest
SUITES = ['browser_fx3d', 'browser_r4', 'browser_world', 'browser_fx3d_real', 'browser_r3', 'browser_smoke']


def _run(name, logdir):
    log = logdir / (name + '.log')
    started = time.perf_counter()
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    with open(log, 'wb') as handle:
        code = subprocess.run([sys.executable, '-m', 'tests.' + name], cwd=ROOT, env=env,
                              stdout=handle, stderr=subprocess.STDOUT).returncode
    return name, code, time.perf_counter() - started, log


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('-j', '--jobs', type=int, default=3, help='suites running at once (default 3)')
    parser.add_argument('suites', nargs='*', help='suite names or substrings, e.g. fx3d')
    args = parser.parse_args(argv)
    chosen = [s for s in SUITES if not args.suites or any(p in s for p in args.suites)]
    if not chosen:
        print('no suites matched:', ', '.join(SUITES)); return 1
    logdir = Path(tempfile.mkdtemp(prefix='guixu-browser-'))
    started = time.perf_counter()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.jobs, len(chosen))) as pool:
        futures = [pool.submit(_run, name, logdir) for name in chosen]
        for future in concurrent.futures.as_completed(futures):
            name, code, seconds, _ = future.result()
            results.append(future.result())
            print(f'{"PASS" if code == 0 else "FAIL"} {name} {seconds:.0f}s', flush=True)
    for name, code, _, log in results:
        if code != 0:
            print('=' * 70); print(f'FAILED: {name} (log {log})'); print('-' * 70)
            print(log.read_text(encoding='utf-8', errors='replace')[-3000:])
    wall = time.perf_counter() - started
    failed = [name for name, code, _, _ in results if code != 0]
    print(f'{len(results)} suites in {wall:.0f}s wall ({sum(r[2] for r in results):.0f}s serial) '
          f'with {min(args.jobs, len(chosen))} at once; {"FAILED " + ", ".join(failed) if failed else "OK"}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
