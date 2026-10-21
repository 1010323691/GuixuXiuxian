"""MU QA: front-end static checks and contract (AC15, AC16 partly, S2, A3, B1-B5).

No browser framework is available in the standard library, so this suite checks the shipped assets statically
(syntax via `node --check` when Node exists, element ids, endpoints, storage use) and serves them over real HTTP.
The Playwright suites (tests/browser_*.py) are NOT run here; see docs/iterations/MU_TESTING.md.
"""
import re
import shutil
import subprocess
import unittest
import urllib.request

from tests.mu_support import ROOT, Server
from tests.test_terminology import strip_js_comments

STATIC = ROOT / 'static'
APP_JS = (STATIC / 'app.js').read_text(encoding='utf-8')
INDEX = (STATIC / 'index.html').read_text(encoding='utf-8')
APP_CODE, _ = strip_js_comments(APP_JS)


class JavaScriptSyntaxTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'node is not installed: syntax check not run')
    def test_node_check_passes_for_every_script(self):
        for name in ('app.js', 'battle_replay.js'):
            result = subprocess.run([shutil.which('node'), '--check', str(STATIC / name)], capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))


class DomContractTests(unittest.TestCase):
    def test_every_element_id_used_by_app_js_exists(self):
        used = set(re.findall(r'\$\("([A-Za-z][\w-]*)"\)', APP_CODE))
        used |= set(re.findall(r'getElementById\("([\w-]+)"\)', APP_CODE))
        used |= set(re.findall(r'querySelector\("#([\w-]+)"\)', APP_CODE))
        used |= {i for group in re.findall(r'for \(const id of \[([^\]]+)\]', APP_CODE) for i in re.findall(r'"([\w-]+)"', group)}
        declared = set(re.findall(r'\bid="([^"]+)"', INDEX))
        created_by_script = set(re.findall(r'\bid[:=]\s*["\']([\w-]+)["\']', APP_CODE)) | set(re.findall(r'\bid="([\w-]+)"', APP_CODE)) \
            | set(re.findall(r'\.id\s*=\s*["`\']([\w-]+)', APP_CODE))
        self.assertGreater(len(used), 100)
        self.assertEqual(sorted(used - declared - created_by_script), [])

    def test_html_ids_are_unique(self):
        ids = re.findall(r'\bid="([^"]+)"', INDEX)
        self.assertEqual(sorted({i for i in ids if ids.count(i) > 1}), [])

    def test_labels_point_to_existing_controls(self):
        declared = set(re.findall(r'\bid="([^"]+)"', INDEX))
        targets = set(re.findall(r'<label[^>]*\bfor="([^"]+)"', INDEX))
        self.assertEqual(sorted(targets - declared), [])

    def test_account_and_auth_ui_is_reachable(self):
        for needed in ('auth-form', 'auth-username', 'auth-password', 'auth-confirm', 'auth-submit', 'auth-error', 'account-button',
                       'logout-button', 'password-button', 'password-form', 'old-password', 'new-password', 'new-password-confirm',
                       'save-status', 'retry-button', 'refresh-button'):
            self.assertIn('id="%s"' % needed, INDEX)
        self.assertIn('type="password"', INDEX)
        self.assertEqual(len(re.findall(r'type="password"', INDEX)), 5)
        for field in ('auth-password', 'auth-confirm', 'old-password', 'new-password', 'new-password-confirm'):
            self.assertRegex(INDEX, r'<input id="%s"[^>]*type="password"' % field)
        self.assertRegex(INDEX, r'id="auth-username"[^>]*autocomplete="username"')
        self.assertRegex(INDEX, r'id="auth-password"[^>]*autocomplete="current-password"')

    def test_page_loads_only_same_origin_scripts_and_styles(self):
        self.assertEqual(re.findall(r'<script[^>]*src="([^"]+)"', INDEX), ['/battle_replay.js', '/app.js'])
        self.assertEqual(re.findall(r'<link[^>]*rel="stylesheet"[^>]*href="([^"]+)"', INDEX), ['/styles.css'])
        self.assertNotRegex(INDEX, r'<script(?![^>]*\bsrc=)[^>]*>')            # no inline script (CSP script-src self)
        self.assertNotRegex(INDEX, r'\son\w+="')                                 # no inline event handlers
        self.assertNotRegex(INDEX, r'style="')                                   # CSP style-src self
        self.assertNotRegex(INDEX + APP_CODE, r'https?://(?!127\.0\.0\.1|localhost|www\.w3\.org)[\w.-]+\.[a-z]{2,}/')   # no external endpoints


class NetworkContractTests(unittest.TestCase):
    def test_app_js_only_calls_existing_endpoints(self):
        called = set(re.findall(r'"(/api/[\w-]+)"', APP_CODE))
        self.assertEqual(called, {'/api/state', '/api/session', '/api/register', '/api/login', '/api/logout', '/api/password',
                                  '/api/new-game', '/api/action'})

    def test_retired_endpoints_are_not_referenced_anywhere_in_static(self):
        for path in STATIC.iterdir():
            if path.suffix in ('.js', '.html', '.css'):
                self.assertNotRegex(path.read_text(encoding='utf-8'), r'/api/(save|load)\b', path.name)

    def test_every_post_sends_the_csrf_header_and_json_type(self):
        self.assertIn('"X-Game-Client": "guixu-web"', APP_CODE)
        self.assertIn('"Content-Type": "application/json"', APP_CODE)
        posts = re.findall(r'method: "POST"[^}]*', APP_CODE)
        self.assertGreaterEqual(len(posts), 4)
        for call in posts:
            self.assertIn('headers: postHeaders', call)

    def test_same_origin_credentials_and_no_cache(self):
        self.assertIn('credentials: "same-origin"', APP_CODE)
        self.assertIn('cache: "no-store"', APP_CODE)

    def test_user_identity_is_never_sent_in_game_requests(self):
        for call in re.findall(r'beginWrite\("(/api/[\w-]+)", ([^)]*)\)', APP_CODE):
            self.assertNotRegex(call[1], r'user_?id|username|account', call)
        self.assertNotRegex(APP_CODE, r'expected_revision[^;\n]*(user|account)')


class BrowserStorageTests(unittest.TestCase):
    def test_only_session_storage_with_one_key_is_used_and_holds_no_secret(self):
        self.assertNotIn('localStorage', APP_CODE)
        self.assertNotIn('document.cookie', APP_CODE)
        self.assertEqual(len(re.findall(r'sessionStorage\.setItem\(', APP_CODE)), 1)
        self.assertIn('sessionStorage.setItem(storageKey, JSON.stringify(value))', APP_CODE)
        # what may be stored: the pending game request (path, normalised account name, body with request id + revision + game payload)
        self.assertIn('const candidate = { path, account: accountKey(account), body: { request_id: requestId(), expected_revision: snapshot.revision, ...payload } }',
                      APP_CODE)
        for call in re.findall(r'beginWrite\("(/api/[\w-]+)", ([^)]*)\)', APP_CODE):
            self.assertIn(call[0], ('/api/action', '/api/new-game'))
            self.assertNotRegex(call[1], r'pass|token|secret', call)

    def test_password_fields_are_cleared_after_use_and_on_switch(self):
        self.assertGreaterEqual(len(re.findall(r'\$\("auth-password"\)\.value = ""', APP_CODE)), 3)
        self.assertGreaterEqual(len(re.findall(r'\["old-password", "new-password", "new-password-confirm"\]\) \$\(id\)\.value = ""', APP_CODE)), 2)

    def test_session_token_is_never_read_or_written_by_scripts(self):
        self.assertNotRegex(APP_CODE, r'guixu_session|__Host-')
        self.assertNotRegex(APP_CODE, r'(Authorization|Bearer|Set-Cookie)')


class ServedAssetTests(unittest.TestCase):
    def test_assets_are_served_without_a_session_and_match_disk(self):
        server = Server(live=True).start()
        self.addCleanup(server.close)
        for url_path, name in (('/', 'index.html'), ('/app.js', 'app.js'), ('/styles.css', 'styles.css'), ('/battle_replay.js', 'battle_replay.js')):
            with urllib.request.urlopen(server.url + url_path, timeout=10) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), (STATIC / name).read_bytes(), url_path)
        with urllib.request.urlopen(server.url + '/api/session', timeout=10) as response:
            self.assertIn(b'"authenticated":', response.read().replace(b' ', b''))


if __name__ == '__main__':
    unittest.main()
