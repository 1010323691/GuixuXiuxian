import tempfile
import unittest
from pathlib import Path

from server import App, dispatch
from tests.support import test_settings

STATIC = Path(__file__).resolve().parents[1] / 'static'
ADDRESS = ('127.0.0.1', 8000)


class Fx3dAssetTests(unittest.TestCase):
    def get(self, app, path):
        return dispatch(app, 'GET', path, {'Host': '127.0.0.1:8000'}, b'', ADDRESS)

    def test_three_layer_and_vendored_library_are_served_same_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder), settings=test_settings())
            for path, marker in (('/fx3d.js', b'WebGLRenderer'), ('/vendor/three.module.min.js', b'Three.js Authors')):
                status, body, ctype = self.get(app, path)[:3]
                self.assertEqual(status, 200, path)
                self.assertTrue(ctype.startswith('text/javascript'), path)
                self.assertIn(marker, body, path)

    def test_replay_degrades_without_the_three_layer(self):
        source = (STATIC / 'battle_replay.js').read_text(encoding='utf-8')
        # 三维层只能按需动态加载，失败回退 SVG；战报脚本自身不静态依赖它
        self.assertIn('import("/fx3d.js")', source)
        self.assertIn('.catch(() => { fx3d = null; })', source)
        self.assertNotIn('\nimport ', source)
        fx = (STATIC / 'fx3d.js').read_text(encoding='utf-8')
        for must in ('webglAvailable', 'forceContextLoss', 'geometry.dispose()', 'spriteTex.dispose()', 'webglcontextlost'):
            self.assertIn(must, fx)
        # 战报贴图的释放已随斗法台移入 battle3d.js（程序贴图与材质贴图逐一 dispose）
        arena = (STATIC / 'battle3d.js').read_text(encoding='utf-8')
        self.assertIn('m.map?.dispose?.()', arena)
        self.assertIn('disposables.forEach((x) => x.dispose?.())', arena)

    def test_manager_exposes_stage_scene_with_single_context_guards(self):
        fx = (STATIC / 'fx3d.js').read_text(encoding='utf-8')
        for must in ('export function mountStage', 'export function unmountStage', 'export function stats', 'liveRenderers',
                     'suspendStage()', 'resumeStage()', 'adapt()', 'visibilitychange', 'if (destroyed) return;'):
            self.assertIn(must, fx)
        app = (STATIC / 'app.js').read_text(encoding='utf-8')
        self.assertIn('import("/fx3d.js")', app)
        self.assertIn('reducedMotion()', app[app.index('const stage3d'):app.index('const fx = ')])

    def test_arena_and_postprocessing_addons_are_vendored_same_origin(self):
        import server
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder), settings=test_settings())
            paths = ['/battle3d.js'] + ['/vendor/addons/%s.js' % name for name in server.VENDOR_ADDONS]
            for path in paths:
                status, body, ctype = self.get(app, path)[:3]
                self.assertEqual(status, 200, path)
                self.assertTrue(ctype.startswith('text/javascript'), path)
        for name in server.VENDOR_ADDONS:
            source = (STATIC / 'vendor' / 'addons' / ('%s.js' % name)).read_text(encoding='utf-8')
            # 裸模块名 'three' 与跨目录引用都会在无 importmap（CSP 禁内联脚本）下失败；只能指向同源固定路径
            self.assertNotIn("from 'three'", source, name)
            self.assertNotIn("'../", source, name)
            self.assertNotRegex(source, r'''(from|import)\s*\(?\s*['"](https?:)?//''', name)
        self.assertTrue((STATIC / 'vendor' / 'addons' / 'LICENSE').exists())

    def test_arena_releases_gpu_resources_and_never_settles_rules(self):
        arena = (STATIC / 'battle3d.js').read_text(encoding='utf-8')
        for must in ('export function buildArena', 'composer.dispose()', 'bloom.dispose()', 'geos.forEach((g) => g.dispose())',
                     'mats.forEach((m) =>', 'cancelAnimationFrame', 'removeEventListener("visibilitychange"', 'observer?.disconnect()'):
            self.assertIn(must, arena)
        # 斗法台只演出：不发请求、不写进度
        for banned in ('fetch(', 'XMLHttpRequest', '/api/', 'localStorage', 'sessionStorage'):
            self.assertNotIn(banned, arena)
        fx = (STATIC / 'fx3d.js').read_text(encoding='utf-8')
        self.assertIn('import { buildArena } from "/battle3d.js"', fx)
        self.assertIn('liveRenderers.delete(renderer)', fx[fx.index('export function create'):fx.index('// ------------------------------------------------------------------ 舞台氛围')])
        replay = (STATIC / 'battle_replay.js').read_text(encoding='utf-8')
        # 三维丢失/失败时回到 SVG：飘字与信息层不依赖三维
        self.assertIn('onLost: () => markFx3d(false)', replay)
        self.assertIn('if (!fx3dOn()) return float(pointOf(actor), text, cls);', replay)

    def test_page_scripts_unchanged(self):
        html = (STATIC / 'index.html').read_text(encoding='utf-8')
        self.assertNotIn('three', html.lower())


if __name__ == '__main__':
    unittest.main()
