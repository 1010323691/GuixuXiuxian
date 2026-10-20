---
name: run-guixu-xiuxian
description: Run, start, drive, screenshot and test the 归墟修行手札 (GuixuXiuxian) Chinese cultivation game - a stdlib Python HTTP server plus static HTML/JS UI. Use to launch the server on a throwaway save, click through the UI in the browser pane, or call its JSON API.
---

# Run 归墟修行手札

Paths are relative to the repo root. Python 3.11+ stdlib only for the game; no Node, no build step.
Verified on Windows 11, Python 3.14, Git Bash. Playwright is NOT installed (only needed by `tests.browser_*`).

## Start (always a throwaway data dir - never touch `./data`, it holds real saves)

```bash
D=$(mktemp -d); (python server.py --port 8123 --data-dir "$D" > /tmp/guixu.log 2>&1 &); sleep 2
curl -s localhost:8123/api/health        # {"ok": true, "schema_version": 2}
```

Stop it (Windows):
```bash
powershell -c "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | ? CommandLine -like '*server.py*8123*' | % { Stop-Process -Id \$_.ProcessId -Force }"
```

## Drive: API driver (agent path, no browser needed)

```bash
python .claude/skills/run-guixu-xiuxian/driver.py --port 8123 state
python .claude/skills/run-guixu-xiuxian/driver.py --port 8123 new 道友 longline   # or free
python .claude/skills/run-guixu-xiuxian/driver.py --port 8123 act cultivate        # substring of action id/label
```
Prints revision, phase, first 12 available actions and latest logs. Rejections (e.g. `ACTION_UNAVAILABLE`) are legitimate game responses, not driver bugs.

## Drive: UI in the built-in browser pane

1. `preview_start` with `url: http://127.0.0.1:8123` (the server is not in launch.json; use the url form).
2. Fresh state shows the creation form; the `执笔 · 开始修行` button is often reported "outside the viewport" by ref clicks - the page may already have created the character. Check with `javascript_tool`.
3. Click game actions through JS (reliable) and verify via the API:
```js
const b=[...document.querySelectorAll('#actions button')].find(x=>x.innerText.includes('吐纳修炼')); b.click();
await new Promise(r=>setTimeout(r,1000)); (await (await fetch('/api/state')).json()).revision
```
Then `computer {action:"screenshot"}`. Result seen: banner "吐纳归元，修为 +6", revision 1→2, 修为 6/32.

## Test

```bash
python -m tests.parallel                    # full white-box suite, 16 workers, ~30-45 s wall
python -m unittest discover -s tests -v     # same suite serially, ~3-4 min
python -m unittest tests.test_rules -q      # 5 tests, <1 s sanity check
```
`python -m tests.browser_smoke|browser_world` need `pip install playwright` + system Chromium (not verified here).

## Gotchas

- POST needs header `X-Game-Client: guixu-web`, JSON body (<=16 KiB), `request_id` (unique string) and `expected_revision` (current revision) or it is rejected; action body is `{action, params}` (not `action_id`) - unknown fields give `BAD_REQUEST`.
- Host header must be `127.0.0.1`/`localhost` with the real port.
- Windows consoles default to gbk: Python printing Chinese/`−` raises `UnicodeEncodeError`; the driver reconfigures stdout to UTF-8, do the same in ad-hoc scripts. Inline `curl -d` with Chinese in Git Bash gave `BAD_REQUEST: JSON格式不正确` - use the driver instead.
- Default mode `free` at API level; the UI form defaults to `longline`.
- Don't use the project's `data/` dir or `--migrate-save` while testing; that rewrites real saves.
