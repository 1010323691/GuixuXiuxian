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
        for must in ('webglAvailable', 'forceContextLoss', 'geometry.dispose()', 'texture.dispose()', 'webglcontextlost'):
            self.assertIn(must, fx)

    def test_manager_exposes_stage_scene_with_single_context_guards(self):
        fx = (STATIC / 'fx3d.js').read_text(encoding='utf-8')
        for must in ('export function mountStage', 'export function unmountStage', 'export function stats', 'liveRenderers',
                     'suspendStage()', 'resumeStage()', 'adapt()', 'visibilitychange', 'if (destroyed) return;'):
            self.assertIn(must, fx)
        app = (STATIC / 'app.js').read_text(encoding='utf-8')
        self.assertIn('import("/fx3d.js")', app)
        self.assertIn('reducedMotion()', app[app.index('const stage3d'):app.index('const fx = ')])

    def test_page_scripts_unchanged(self):
        html = (STATIC / 'index.html').read_text(encoding='utf-8')
        self.assertNotIn('three', html.lower())


if __name__ == '__main__':
    unittest.main()
