import tempfile
import unittest
from pathlib import Path

from server import App, dispatch
from tests.support import test_settings

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'static'
ARENA_SRC = ROOT / 'src' / 'battle' / 'replay.ts'   # 战报斗法台源码（打包进 static/arena3d.js）
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
        # 战报斗法台释放材质贴图、立绘贴图与共享缓存
        arena = ARENA_SRC.read_text(encoding='utf-8')
        self.assertIn('if (v instanceof THREE.Texture) v.dispose()', arena)
        self.assertIn('disposeTextures(art); disposeTextures(lionArt);', arena)

    def test_manager_exposes_stage_scene_with_single_context_guards(self):
        fx = (STATIC / 'fx3d.js').read_text(encoding='utf-8')
        for must in ('export function mountStage', 'export function unmountStage', 'export function stats', 'liveRenderers',
                     'suspendStage()', 'resumeStage()', 'adapt()', 'visibilitychange', 'if (destroyed) return;'):
            self.assertIn(must, fx)
        app = (STATIC / 'app.js').read_text(encoding='utf-8')
        self.assertIn('import("/fx3d.js")', app)
        self.assertIn('reducedMotion()', app[app.index('const stage3d'):app.index('const fx = ')])

    def test_arena_bundle_is_served_same_origin_and_old_arena_retired(self):
        import server
        with tempfile.TemporaryDirectory() as folder:
            app = App(Path(folder), settings=test_settings())
            status, body, ctype = self.get(app, '/arena3d.js')[:3]
            self.assertEqual(status, 200)
            self.assertTrue(ctype.startswith('text/javascript'))
            self.assertIn(b'buildArena', body)
            # 旧斗法台与其后期扩展已由打包的新斗法台取代，不再服务
            for path in ('/battle3d.js', '/vendor/addons/EffectComposer.js'):
                self.assertNotIn(path, server.FILES)
                self.assertEqual(self.get(app, path)[0], 404, path)
        self.assertFalse((STATIC / 'battle3d.js').exists())
        self.assertFalse((STATIC / 'vendor' / 'addons').exists())

    def test_arena_releases_gpu_resources_and_never_settles_rules(self):
        arena = ARENA_SRC.read_text(encoding='utf-8')
        for must in ('export function buildArena', 'post.dispose()', 'fx.dispose()', 'mesh.geometry?.dispose()', 'm.dispose()',
                     'cancelAnimationFrame', "removeEventListener('visibilitychange'", 'observer?.disconnect()'):
            self.assertIn(must, arena)
        # 斗法台只演出：不发请求、不写进度（源码与打包产物都检查）
        bundle = (STATIC / 'arena3d.js').read_text(encoding='utf-8')
        for banned in ('fetch(', 'XMLHttpRequest', '/api/', 'localStorage', 'sessionStorage'):
            self.assertNotIn(banned, arena)
            self.assertNotIn(banned, bundle)
        fx = (STATIC / 'fx3d.js').read_text(encoding='utf-8')
        self.assertIn('import { buildArena } from "/arena3d.js"', fx)
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
