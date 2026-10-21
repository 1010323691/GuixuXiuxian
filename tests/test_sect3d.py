"""三维宗门主界面（src/sect → static/sect3d.js，HUD static/sect_hub.js）的白盒约束。

- 产物头部记录的 src-sha256（src/sect/** + package.json）与 body-sha256 和磁盘一致（与 test_frontend_build 同配方）；
- 只从同源 /vendor/three.module.min.js 导入 three，不发请求、不碰浏览器存储；
- HUD 只读快照：不调用 fetch、不出现 /api/；建筑入口与菜单入口全部指向服务端真实返回的凡界卷目；
- app.js 的桥接只派发只读事件、复用原卷目与事项卡（写操作仍走原提交/确认流程）；
- 场景提供释放（dispose）与无 WebGL 降级入口。
"""
import hashlib
import json
import re
import unittest
from pathlib import Path

import server
from tests.r3_support import ClockHTTP
from tests.support import baseline_route

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'static'
BUNDLE = STATIC / 'sect3d.js'
HUB = (STATIC / 'sect_hub.js').read_text(encoding='utf-8')
APP = (STATIC / 'app.js').read_text(encoding='utf-8')
INDEX = (STATIC / 'index.html').read_text(encoding='utf-8')
LAYOUT = (ROOT / 'src' / 'sect' / 'layout.ts').read_text(encoding='utf-8')


def source_hash():
    inputs = sorted([p for p in (ROOT / 'src' / 'sect').rglob('*') if p.is_file()] + [ROOT / 'package.json'],
                    key=lambda p: p.relative_to(ROOT).as_posix())
    digest = hashlib.sha256()
    for path in inputs:
        digest.update((path.relative_to(ROOT).as_posix() + '\n').encode('utf-8'))
        digest.update((path.read_bytes().decode('utf-8').replace('\r\n', '\n') + '\n').encode('utf-8'))
    return digest.hexdigest()


def world_pages():
    """服务端真实返回的凡界卷目 id（按公开路线进入凡界后读取）。"""
    s = ClockHTTP().start()
    try:
        s.create()
        baseline_route(s.snapshot, s.action)
        s.action('world_enter')
        return {page['id'] for page in s.snapshot()['view']['world']['pages']}
    finally:
        s.close()


class SectBundleTests(unittest.TestCase):
    def test_bundle_header_matches_sources(self):
        head = BUNDLE.read_text(encoding='utf-8')[:400]
        self.assertIn('sect3d bundle', head)
        found = re.search(r'src-sha256: ([0-9a-f]{64})', head)
        self.assertIsNotNone(found, 'bundle header missing; run npm run build')
        self.assertEqual(found.group(1), source_hash(), 'static/sect3d.js is stale: run npm run build and commit it')

    def test_bundle_body_matches_its_recorded_hash(self):
        raw = BUNDLE.read_bytes().replace(b'\r\n', b'\n')
        first, _, body = raw.partition(b'\n')
        found = re.search(rb'body-sha256: ([0-9a-f]{64})', first)
        self.assertIsNotNone(found)
        self.assertEqual(found.group(1).decode('ascii'), hashlib.sha256(body).hexdigest(), 'static/sect3d.js body edited without a rebuild')

    def test_bundle_imports_only_the_shared_vendored_three(self):
        text = BUNDLE.read_text(encoding='utf-8')
        self.assertEqual(set(re.findall(r'(?:from|import)\s*"([^"]+)"', text)), {'/vendor/three.module.min.js'})
        self.assertIn('postprocessing v6.39.5 - Zlib', text[:1200])

    def test_scene_never_talks_to_the_server_or_storage(self):
        sources = [p.read_text(encoding='utf-8') for p in (ROOT / 'src' / 'sect').glob('*.ts')]
        for text in sources + [BUNDLE.read_text(encoding='utf-8'), HUB]:
            for banned in ('fetch(', 'XMLHttpRequest', '/api/', 'localStorage', 'sessionStorage', 'document.cookie'):
                self.assertNotIn(banned, text)

    def test_scene_releases_gpu_resources(self):
        index = (ROOT / 'src' / 'sect' / 'index.ts').read_text(encoding='utf-8')
        for must in ('dispose()', 'geometry?.dispose()', 'm.dispose()', 't.dispose()', 'composer?.dispose()', 'renderer.dispose()',
                     'forceContextLoss()', 'cancelAnimationFrame(frameId)', 'observer.disconnect()', "removeEventListener('visibilitychange'",
                     "addEventListener('webglcontextlost'"):
            self.assertIn(must, index)

    def test_served_same_origin(self):
        for path, name in (('/sect3d.js', 'sect3d.js'), ('/sect_hub.js', 'sect_hub.js')):
            self.assertEqual(server.FILES.get(path), (name, 'text/javascript; charset=utf-8'))
        self.assertIn('import("/sect3d.js")', HUB)
        self.assertEqual(re.findall(r'<script[^>]*src="([^"]+)"', INDEX), ['/battle_replay.js', '/app.js', '/sect_hub.js'])


class SectEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = world_pages()

    def test_hub_entries_mirror_the_scene_layout(self):
        layout = re.findall(r"\{ id: '([\w-]+)', label: '([^']+)', page: '(\w+)'", LAYOUT[LAYOUT.index('export const ENTRIES'):])
        hub = re.findall(r'\{ id: "([\w-]+)", label: "([^"]+)", page: "(\w+)"', HUB)
        self.assertEqual(layout, hub)
        self.assertGreaterEqual(len(hub), 12)

    def test_every_entry_opens_a_real_world_page_and_every_page_is_reachable(self):
        scene = {page for _, _, page in re.findall(r'\{ id: "([\w-]+)", label: "([^"]+)", page: "(\w+)"', HUB)}
        menus = set(re.findall(r'data-open="(\w+)"', INDEX))
        self.assertLessEqual(scene, self.pages)
        self.assertLessEqual(menus, self.pages)
        self.assertEqual(menus, self.pages, 'every world page needs a HUD entry')
        self.assertEqual(scene, self.pages, 'every world page needs a building entry')

    def test_dock_has_the_six_concept_slots_with_keys(self):
        dock = INDEX[INDEX.index('class="sh-dock"'):INDEX.index('</nav>', INDEX.index('class="sh-dock"'))]
        self.assertEqual(re.findall(r'<span>(\S\S)<kbd>', dock), ['角色', '功法', '背包', '宗门', '洞府', '四艺'])
        self.assertEqual(re.findall(r'data-key="(\w)"', dock), ['c', 'k', 'b', 'g', 'h', 'l'])


    def test_old_workbench_entries_have_hud_homes(self):
        # 原工作台的卷宗三页签、潜修详情与序章旧事各有 HUD 入口，并复用原页签/原按钮（不另造一份内容）
        self.assertEqual(sorted(re.findall(r'data-dossier="(\w+)"', INDEX)), ['progress', 'quests', 'recent'])
        self.assertEqual(sorted(re.findall(r'data-side-tab="(\w+)"', INDEX)), ['progress', 'quests', 'recent'])
        for must in ('id="sh-growth-open"', 'id="sh-legacy"', 'id="sect-window-bar"'):
            self.assertIn(must, INDEX)
        self.assertIn('#side-tabs [data-side-tab="${tab}"]', HUB)
        self.assertIn('$("legacy-history-button").click()', HUB)
        self.assertIn('[$("growth-panel"), $("world-workbench")]', HUB)


class BridgeTests(unittest.TestCase):
    def test_app_broadcasts_read_only_snapshots_and_opens_pages_through_existing_paths(self):
        self.assertIn('new CustomEvent("guixu:render", { detail: snapshot })', APP)
        self.assertIn('new CustomEvent("guixu:growth"', APP)
        handler = APP[APP.index('document.addEventListener("guixu:open"'):APP.index('let noticeTimer')]
        self.assertIn('selectWorldPage(page)', handler)
        self.assertIn('revealNode(node)', handler)
        self.assertNotIn('beginWrite', handler)               # 写入只经原事项卡的按钮与确认流程
        self.assertIn('button.click()', handler)
        self.assertIn('!node.querySelector("select, input")', handler)   # 需要选择参数的事项不代为提交

    def test_hub_only_reads_state_and_dispatches_open(self):
        self.assertNotIn('beginWrite', HUB)
        self.assertIn('new CustomEvent("guixu:open"', HUB)
        self.assertIn('document.addEventListener("guixu:render"', HUB)
        # 不编造示例数值：概念图里的战力/收益数字不出现在 HUD 代码中
        for fake in ('28,640', '12,860', '+128', '+360', '68%', '96%'):
            self.assertNotIn(fake, HUB + INDEX)

    def test_stage_scene_yields_to_sect_mode_and_fallback_exists(self):
        self.assertIn('document.body.classList.contains("sect-mode")', APP[APP.index('const stage3d'):APP.index('const fx = ')])
        for must in ('showFallback(', 'webgl()', 'onLost:', 'params.has("no3d")'):
            self.assertIn(must, HUB)
        self.assertIn('id="sect-fallback"', INDEX)

    def test_index_stays_csp_clean(self):
        self.assertNotRegex(INDEX, r'style="')
        self.assertNotRegex(INDEX, r'\son\w+="')


if __name__ == '__main__':
    unittest.main()
