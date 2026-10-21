"""Terminology gate (AGENTS.md, MU_PRD 4.6, AC17/AC18): no stand-alone / manual-save vocabulary in anything a player or
operator can read: UI text, API messages, event logs, CLI help/output, launcher output and current documents.

Scopes
* static/*              HTML text nodes + title/aria-label/placeholder/alt/value attributes; JS and CSS source with
                        comments removed (string literals and template literals included, comments are not player visible).
* game/*.py, server.py, scripts/*.py   every string constant in the AST except docstrings (comments are not in the AST).
* runtime               error `message`s from real HTTP-path failures, every string in the state/view/events/logs of played
                        games, CLI help and CLI output (main() captured), `scripts/launch.py --help`.
* current documents     README.md, docs/API.md, docs/PLAYING.md, docs/R3_PLAYING.md, docs/R4_PLAYING.md, docs/UI.md.

Explicit whitelist (NOT scanned, with reason):
* code comments and docstrings          not player visible, may describe the retired behaviour for maintainers
* docs/history, docs/iterations/*, docs/studio/*, docs/ARCHITECTURE.md, docs/DELIVERY.md, docs/TESTING.md, docs/GDD.md,
  artifacts/, prototypes/               historical records, marked as such in docs/studio/README.md and their headers
* AGENTS.md                             quotes the banned words in the rule itself
* tests/                                tests must name the banned words to check for them
"""
import ast
import html.parser
import io
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import server as server_module
from game import admin
from tests.mu_support import ROOT, Server, post_action, post_new_game, state_of
from tests.support import route_to_ending

BANNED = ('存档', '读档', '载入', '检查点', '保存位置', '单机', '单人', '本地', '存盘', '手动保存', '手动存', '读取存', '加载存')
BANNED_EN = re.compile(r'\b(checkpoint|save\s*game|load\s*game|single[- ]?player|offline\s*mode|save\s*slot)\b', re.I)
BANNED_RE = re.compile('|'.join(map(re.escape, BANNED)))
# Documents may negate a feature ("没有手动保存"); there only the PRD 4.6 core vocabulary is banned.
CORE_RE = re.compile('存档|读档|载入|检查点|保存位置|单机|单人|本地')

HISTORICAL_DOCS = ('docs/history', 'docs/iterations', 'docs/studio', 'docs/ARCHITECTURE.md', 'docs/DELIVERY.md',
                   'docs/TESTING.md', 'docs/GDD.md', 'artifacts', 'prototypes', 'AGENTS.md', 'tests')
CURRENT_DOCS = ('README.md', 'docs/API.md', 'docs/PLAYING.md', 'docs/R3_PLAYING.md', 'docs/R4_PLAYING.md', 'docs/UI.md')


def hits(text, english=False):
    found = sorted(set(BANNED_RE.findall(text)))
    if english:
        found += sorted({m.group(0).lower() for m in BANNED_EN.finditer(text)})
    return found


def walk_strings(value, path=''):
    """Yield (path, string) for every string value and every dict key."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield path + '/' + str(key), str(key)
            yield from walk_strings(item, path + '/' + str(key))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from walk_strings(item, '%s[%d]' % (path, index))


# --------------------------------------------------------------------- JS / CSS comment stripping
_REGEX_PREV = set('(,=:[!&|?{};+-*%<>~^')
_REGEX_WORDS = {'return', 'typeof', 'case', 'in', 'of', 'delete', 'void', 'throw', 'new', 'else', 'do'}


def strip_js_comments(src, i=0, in_expr=False):
    """Remove // and /* */ comments while keeping strings, template literals (with ${} nesting) and regex literals intact.

    Returns (text, next_index). Small purpose-built lexer; tests below pin its behaviour.
    """
    out, n, depth, prev, word = [], len(src), 0, '', ''
    while i < n:
        c, nxt = src[i], src[i + 1:i + 2]
        if c == '/' and nxt == '/':
            while i < n and src[i] != '\n':
                i += 1
            continue
        if c == '/' and nxt == '*':
            end = src.find('*/', i + 2)
            i = n if end < 0 else end + 2
            continue
        if c in '\'"':
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == '\\' else 1
            out.append(src[i:j + 1])
            i, prev, word = j + 1, c, ''
            continue
        if c == '`':
            out.append('`')
            i += 1
            while i < n and src[i] != '`':
                if src[i] == '\\':
                    out.append(src[i:i + 2])
                    i += 2
                elif src[i:i + 2] == '${':
                    out.append('${')
                    inner, i = strip_js_comments(src, i + 2, True)
                    out.append(inner + '}')
                else:
                    out.append(src[i])
                    i += 1
            out.append('`')
            i, prev, word = i + 1, '`', ''
            continue
        if c == '/' and (prev in _REGEX_PREV or prev == '' or word in _REGEX_WORDS):
            j, in_class = i + 1, False
            while j < n and (src[j] != '/' or in_class) and src[j] != '\n':
                if src[j] == '\\':
                    j += 1
                elif src[j] == '[':
                    in_class = True
                elif src[j] == ']':
                    in_class = False
                j += 1
            out.append(src[i:j + 1])
            i, prev, word = j + 1, ')', ''
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            if in_expr and depth == 0:
                return ''.join(out), i + 1
            depth -= 1
        out.append(c)
        if c.isalnum() or c in '_$':
            word = word + c if word or c.isalpha() or c in '_$' else word
            prev = c
        elif not c.isspace():
            prev, word = c, ''
        elif c.isspace() and word:
            prev = word[-1]
            word = word if word in _REGEX_WORDS else ''
        i += 1
    return ''.join(out), i


def strip_css_comments(src):
    return re.sub(r'/\*.*?\*/', '', src, flags=re.S)


class HtmlText(html.parser.HTMLParser):
    """Visible text nodes (outside script/style) and the attributes a user can see or hear."""
    ATTRS = ('title', 'aria-label', 'placeholder', 'alt', 'value', 'content', 'aria-description', 'label')

    def __init__(self):
        super().__init__()
        self.items, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        for name, value in attrs:
            if name in self.ATTRS and value:
                self.items.append(('%s[%s]' % (tag, name), value))

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.items.append(('text', data.strip()))


class JsLexerSelfTests(unittest.TestCase):
    """The comment stripper decides what is scanned; pin its behaviour on tricky inputs."""

    def strip(self, src):
        return strip_js_comments(src)[0]

    def test_removes_line_and_block_comments_only(self):
        self.assertEqual(self.strip('a = 1; // 存档\nb = 2; /* 单机 */ c = 3;'), 'a = 1; \nb = 2;  c = 3;')

    def test_keeps_comment_markers_inside_strings_and_regex(self):
        for src in ('u = "http://x.test/存档";', "u = '/* 存档 */';", 'r = /["\'`]\\/\\//g; z = 1;', 'u = `//${ "}" }/*`;'):
            self.assertEqual(self.strip(src), src, src)

    def test_division_is_not_a_regex(self):
        src = 'x = (a + b) / 2; y = a / b // 存档 here\nz = 1;'
        self.assertEqual(self.strip(src), 'x = (a + b) / 2; y = a / b \nz = 1;')

    def test_template_expression_comments(self):
        self.assertEqual(self.strip('t = `a${ x /* 存档 */ }b`;'), 't = `a${ x  }b`;')

    def test_real_app_js_survives_stripping(self):
        source = (ROOT / 'static' / 'app.js').read_text(encoding='utf-8')
        text, end = strip_js_comments(source)
        self.assertEqual(end, len(source))
        self.assertLess(len(text), len(source))
        for needle in ('进度同步中', '/api/state', 'X-Game-Client'):
            self.assertIn(needle, text)


class StaticFileTermsTests(unittest.TestCase):
    def test_index_html_visible_text_and_attributes(self):
        parser = HtmlText()
        parser.feed((ROOT / 'static' / 'index.html').read_text(encoding='utf-8'))
        self.assertGreater(len(parser.items), 80)
        bad = [(where, text[:60], hits(text, True)) for where, text in parser.items if hits(text, True)]
        self.assertEqual(bad, [])

    def test_javascript_sources_without_comments(self):
        for name in ('app.js', 'battle_replay.js', 'fx3d.js', 'battle3d.js'):
            source = (ROOT / 'static' / name).read_text(encoding='utf-8')
            text, _ = strip_js_comments(source)
            found = []
            for number, line in enumerate(text.splitlines(), 1):
                if hits(line, True):
                    found.append('%s:%d %s %s' % (name, number, hits(line, True), line.strip()[:80]))
            self.assertEqual(found, [], name)

    def test_css_content_strings(self):
        text = strip_css_comments((ROOT / 'static' / 'styles.css').read_text(encoding='utf-8'))
        self.assertEqual(hits(text), [])

    def test_frontend_never_calls_retired_endpoints_or_stores_secrets_locally(self):
        text, _ = strip_js_comments((ROOT / 'static' / 'app.js').read_text(encoding='utf-8'))
        self.assertNotRegex(text, r'/api/(save|load)\b')
        self.assertNotIn('localStorage', text)
        for forbidden in ('document.cookie', 'indexedDB'):
            self.assertNotIn(forbidden, text)
        html_text = (ROOT / 'static' / 'index.html').read_text(encoding='utf-8')
        for retired in ('save-button', 'load-button', 'checkpoint', 'id="save"', 'id="load"'):
            self.assertNotIn(retired, html_text)

    def test_ui_has_sync_status_element_and_service_wording(self):
        html_text = (ROOT / 'static' / 'index.html').read_text(encoding='utf-8')
        self.assertRegex(html_text, r'<p id="save-status"[^>]*role="status"[^>]*aria-live="polite"[^>]*>[^<]*同步[^<]*</p>')
        js, _ = strip_js_comments((ROOT / 'static' / 'app.js').read_text(encoding='utf-8'))
        for phrase in ('进度同步中…', '进度已同步', '同步失败，正在重试…', '网络中断，正在重连…', '进度保存失败，请稍后重试，当前操作未生效',
                       '登录已过期，请重新登录', '进度已在其他页面更新'):
            self.assertIn(phrase, js)
        for control in ('account-button', 'password-button', 'logout-button', 'auth-dialog', 'password-dialog'):
            self.assertIn('id="%s"' % control, html_text)


# --------------------------------------------------------------------- Python source strings
def docstring_nodes(tree):
    skipped = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                skipped.add(id(first.value))
    return skipped


def python_string_hits(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    skipped = docstring_nodes(tree)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skipped:
            if hits(node.value):
                found.append('%s:%d %s %r' % (path.relative_to(ROOT).as_posix(), node.lineno, hits(node.value), node.value[:60]))
    return found


class PythonStringTermsTests(unittest.TestCase):
    def test_game_package_and_server_strings(self):
        files = sorted((ROOT / 'game').glob('*.py')) + [ROOT / 'server.py']
        found = [item for path in files for item in python_string_hits(path)]
        self.assertEqual(found, [])

    def test_launch_script_strings(self):
        self.assertEqual(python_string_hits(ROOT / 'scripts' / 'launch.py'), [])

    def test_launcher_bat_echo_lines(self):
        lines = (ROOT / '启动游戏.bat').read_text(encoding='utf-8', errors='replace').splitlines()
        visible = [line for line in lines if not line.strip().lower().startswith('rem ')]
        self.assertEqual([hits(line, True) for line in visible if hits(line, True)], [])

    def test_other_scripts_listed_for_information(self):
        """Developer tooling (not player/operator facing); reported, never failing, so the whitelist stays explicit."""
        extra = [item for path in sorted((ROOT / 'scripts').glob('*.py')) if path.name != 'launch.py' for item in python_string_hits(path)]
        self.assertIsInstance(extra, list)

    def test_current_documents(self):
        found = []
        for name in CURRENT_DOCS:
            path = ROOT / name
            if not path.exists():
                continue
            for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                if CORE_RE.search(line):
                    found.append('%s:%d %s' % (name, number, sorted(set(CORE_RE.findall(line)))))
        self.assertEqual(found, [])

    def test_whitelist_entries_exist_so_the_list_cannot_rot(self):
        for name in HISTORICAL_DOCS:
            self.assertTrue((ROOT / name).exists(), name)


# --------------------------------------------------------------------- runtime scans
class RuntimeTermsTests(unittest.TestCase):
    def setUp(self):
        self.server = Server().start()
        self.addCleanup(self.server.close)

    def test_error_messages_from_every_failure_family(self):
        server, a = self.server, self.server.as_user('alice_a')
        post_new_game(a, name='甲')
        host = {'Host': '127.0.0.1:8000'}
        cases = [
            ('GET', '/api/state', None, {}),                                              # 401
            ('POST', '/api/action', {'request_id': 'x', 'expected_revision': 0, 'action': 'explore', 'params': {}}, {}),
            ('POST', '/api/login', {'username': 'nobody1', 'password': 'whatever-1'}, {}),  # 401 LOGIN_FAILED
            ('POST', '/api/login', {'username': 'alice_a'}, {}),                           # 400 field set
            ('POST', '/api/register', {'username': 'ab', 'password': 'x'}, {}),            # 400 validation
            ('POST', '/api/register', {'username': 'alice_a', 'password': 'long-enough-pw'}, {}),   # 409
            ('POST', '/api/save', {}, {}), ('POST', '/api/load', {}, {}), ('GET', '/api/nope', None, {}),   # 404
            ('PUT', '/api/state', None, {}),                                               # 405
            ('POST', '/api/login', {'username': 'alice_a', 'password': 'long-enough-pw'}, {'X-Game-Client': 'bad'}),   # 403
            ('GET', '/api/health', None, {'Host': 'evil.example.com'}),                    # 403 host
            ('POST', '/api/login', None, {}),                                              # 400 empty
            ('POST', '/api/login', None, {'Content-Type': 'text/plain'}),
        ]
        messages = []
        for method, path, payload, headers in cases:
            status, body = server.raw_request(method, path, payload, headers)
            self.assertGreaterEqual(status, 400, (path, body))
            messages.append(body['error']['message'])
        for _ in range(5):                                                                 # 429
            _, body = server.raw_request('POST', '/api/login', {'username': 'alice_a', 'password': 'bad-password-1'})
        messages.append(body['error']['message'])
        status, body = post_action(a, 'explore', revision=0)                                # 409 stale
        messages.append(body['error']['message'])
        status, body = post_action(a, 'nonexistent_action')                                 # unknown action
        messages.append(body['error']['message'])
        status, body = post_action(a, 'travel', {'region': 'ruins'})                        # 422 unavailable
        messages.append(body['error']['message'])
        status, body = post_new_game(a, name='x' * 50, revision=1)
        messages.append(body['error']['message'])
        b = server.as_user('bob_b')
        with server.fail_commit('before'):                                                   # 503
            status, body = post_new_game(b, name='乙', revision=0)
        self.assertEqual(status, 503)
        messages.append(body['error']['message'])
        status, body = post_action(a, 'explore', request_id='r' * 200)
        messages.append(body['error']['message'])
        self.assertGreaterEqual(len(set(messages)), 12)
        self.assertEqual([(m, hits(m, True)) for m in messages if hits(m, True)], [])

    def play_and_collect(self, client_name, mode, actions=30):
        client = self.server.as_user(client_name)
        collected = []
        first = client.write('/api/new-game', name='试玩', mode=mode)
        collected += list(walk_strings(first, 'new-game'))
        for index in range(actions):
            result = client.action('explore') if index % 3 else client.action('gather')
            collected += list(walk_strings(result, 'action'))
        collected += list(walk_strings(client.snapshot(), 'state'))
        return client, collected

    def test_state_view_events_and_logs_for_both_profiles(self):
        for name, mode in (('free_player', 'free'), ('line_player', 'longline')):
            _, collected = self.play_and_collect(name, mode)
            self.assertGreater(len(collected), 400)
            found = sorted({(path.split('/')[-1], text[:50]) for path, text in collected if hits(text, True)})
            self.assertEqual(found, [], mode)

    def test_full_prologue_route_text(self):
        client = self.server.as_user('route_player')
        client.write('/api/new-game', name='通关', mode='free')
        seen = []

        def action(name, **params):
            result = client.action(name, **params)
            seen.extend(text for _, text in walk_strings(result))
            return result

        route_to_ending(client.snapshot, action)
        seen.extend(text for _, text in walk_strings(client.snapshot()))
        self.assertGreater(len(seen), 1000)
        self.assertEqual(sorted({text[:60] for text in seen if hits(text, True)}), [])

    def test_state_payload_does_not_expose_retired_save_fields(self):
        client = self.server.as_user('alice_a')
        post_new_game(client, name='甲', mode='longline')
        post_action(client, 'explore')
        _, body = state_of(client)
        keys = {path.split('/')[-1] for path, _ in walk_strings(body) if '/' in path}
        for retired in ('save', 'load_policy', 'slot', 'checkpoint', 'manual_save'):
            self.assertNotIn(retired, body, retired)
            self.assertNotIn(retired, body['view'].get('profile', {}), retired)
        self.assertIn('sync', body)
        self.assertTrue(body['sync']['persisted'])
        self.assertNotIn('load_policy', keys)

    def run_cli(self, argv, data_dir):
        out, err = io.StringIO(), io.StringIO()
        code = None
        with redirect_stdout(out), redirect_stderr(err):
            try:
                result = server_module.main(list(argv) + ['--data-dir', str(data_dir)])
                code = result if isinstance(result, int) else 0
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue() + err.getvalue()

    def test_cli_help_and_outputs(self):
        outputs = [server_module.build_parser().format_help()]
        with tempfile.TemporaryDirectory() as folder:
            outputs.append(self.run_cli(['--help'], folder)[1])
            for argv in (['--legacy-status'], ['--backup'], ['--migrate-multiuser'], ['--claim-legacy', 'nobody_x'],
                         ['--force'], ['--migrate-save'], ['--legacy-status', '--backup'], ['--reset-password', 'ghost_x']):
                code, text = self.run_cli(argv, folder)
                outputs.append(text)
                self.assertNotEqual(text.strip(), '', argv)
        for text in outputs:
            self.assertEqual(hits(text, True), [], text[:200])
        self.assertIn('--migrate-data', outputs[0])         # PRD T2: neutral alias exists

    def test_cli_refusal_of_unmigrated_old_data_uses_service_wording(self):
        with tempfile.TemporaryDirectory() as folder:
            import sqlite3
            conn = sqlite3.connect(str(Path(folder) / 'game.db'))
            conn.executescript('CREATE TABLE current (id INTEGER PRIMARY KEY, schema_version INTEGER, revision INTEGER, state TEXT, slot TEXT);'
                               'CREATE TABLE requests (request_id TEXT PRIMARY KEY, payload TEXT);')
            conn.commit()
            conn.close()
            code, text = self.run_cli([], folder)
            self.assertEqual(code, 1)
            self.assertIn('--migrate-multiuser', text)
            self.assertEqual(hits(text, True), [])
            code, text = self.run_cli(['--migrate-multiuser'], folder)
            self.assertEqual(code, 1)
            self.assertEqual(hits(text, True), [])

    def test_launcher_help_output(self):
        proc = subprocess.run([sys.executable, '-I', str(ROOT / 'scripts' / 'launch.py'), '--help'], capture_output=True, timeout=60, cwd=str(ROOT))
        text = (proc.stdout + proc.stderr).decode('utf-8', 'replace')
        self.assertEqual(proc.returncode, 0, text)
        self.assertEqual(hits(text, True), [])


if __name__ == '__main__':
    unittest.main()
