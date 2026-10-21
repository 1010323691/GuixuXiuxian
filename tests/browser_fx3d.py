"""三维特效真实浏览器验收：单上下文、舞台数据绑定、战报让出/恢复上下文、开合 30 次无 GPU 对象累积、无 WebGL 降级。

需要 Playwright 与 Chromium/Edge（见 tests.support.launch_browser）。WebGL 使用 SwiftShader 软件渲染，
帧率数值仅代表本机软件渲染环境，不代表真实 GPU。
"""
import json

from playwright.sync_api import expect, sync_playwright

from tests.browser_world import BrowserWorldDriver
from tests.support import Server, attach_session, baseline_route, launch_browser

REPORT = {'outcome': 'victory', 'rounds': 1, 'strategy': 'balanced', 'strategy_label': '均衡', 'enemy': {'name': '测试', 'max_hp': 100, 'kind': 'beast'},
          'player': {'max_hp': 100, 'max_mp': 50}, 'treasures': {'main': None, 'guard': None},
          'frames': [{'round': 0, 'player': {'hp': 100, 'mp': 20}, 'enemy': {'hp': 100, 'barrier': 0}, 'intent': '蓄势', 'action': '准备', 'events': []},
                     {'round': 1, 'player': {'hp': 100, 'mp': 20}, 'enemy': {'hp': 0, 'barrier': 0}, 'intent': '—', 'action': '斗法',
                      'events': [{'type': 'damage', 'source': 'player', 'target': 'enemy', 'label': '攻', 'amount': 100}]}]}
GPU_ARGS = ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']
STATS = "async () => { const m = await import('/fx3d.js'); return m.stats(); }"


def enter_world(page, server, name):
    page.goto(server.url)
    expect(page.locator('#creation')).to_be_visible()
    page.locator('#mode').select_option('free')
    page.locator('#name').fill(name)
    driver = BrowserWorldDriver(page, server)
    driver.click_write(page.locator('#create-button'), '/api/new-game')
    baseline_route(server.snapshot, driver.legacy)
    driver.action('world_enter')
    return driver


def main():
    report = {'passed': False, 'checks': [], 'errors': []}
    server = Server(live=True)
    try:
        server.start()
        with sync_playwright() as p:
            browser = launch_browser(p, args=GPU_ARGS)
            page = browser.new_page(viewport={'width': 1365, 'height': 900})
            attach_session(page, server)
            page.on('pageerror', lambda e: report['errors'].append(str(e)))
            page.on('console', lambda m: report['errors'].append(m.text) if m.type == 'error' else None)
            enter_world(page, server, '三维QA')
            page.locator('[data-world-page="estate"]').click()
            page.wait_for_timeout(1500)
            first = page.evaluate(STATS)
            assert first['renderers'] == 1 and first['stage'], first
            assert page.evaluate("document.body.classList.contains('stage3d-on')")
            report['checks'].append('stage scene mounts on the world banner with exactly one WebGL renderer')

            # 数据绑定：洞府等级 → 灯笼数（总等级 6 → 6 盏；非洞府页为 0）
            page.evaluate("async () => { const m = await import('/fx3d.js'); m.mountStage({host: document.querySelector('.world-page-heading'), tier: 3, color: '#3FA585', page: 'estate', estate: {garden: 2, workshop: 2, chamber: 2}}); }")
            page.wait_for_timeout(800)
            assert page.evaluate(STATS)['stage']['lanterns'] == 6
            page.locator('[data-world-page="market"]').click()
            page.wait_for_timeout(800)
            assert page.evaluate(STATS)['stage']['lanterns'] == 0
            report['checks'].append('estate levels drive lantern count; other pages show none')

            # 战报让出上下文并在合上后恢复；开合 30 次 GPU 对象不累积
            page.evaluate("(r) => { window.__report = r; }", REPORT)
            baseline = None
            for index in range(30):
                page.evaluate("() => BattleReplay.open(window.__report)")
                page.wait_for_timeout(250)
                during = page.evaluate(STATS)
                assert during['renderers'] == 1 and during['stage'] is None and during['battleDepth'] == 1, during
                page.evaluate("() => BattleReplay.close()")
                page.wait_for_timeout(120)
                if index == 0:
                    page.wait_for_timeout(600)
                    baseline = page.evaluate(STATS)['stage']
            page.wait_for_timeout(800)
            after = page.evaluate(STATS)
            assert after['renderers'] == 1 and after['stage'], after
            assert after['stage']['geometries'] == baseline['geometries'] and after['stage']['textures'] == baseline['textures'], (baseline, after)
            assert page.evaluate("document.querySelectorAll('.fx3d-canvas').length") == 0
            report['checks'].append('30 replay open/close cycles: one renderer, geometries/textures stable, no leftover battle canvas')
            report['stats'] = after['stage']
            browser.close()

            # 无 WebGL：屏蔽 getContext，游戏照常运行并保留 Canvas2D 灵气
            browser = launch_browser(p, args=['--no-sandbox', '--disable-gpu', '--disable-3d-apis', '--disable-webgl', '--disable-webgl2'])
            page = browser.new_page(viewport={'width': 1365, 'height': 900})
            attach_session(page, server)
            page.add_init_script("""const orig = HTMLCanvasElement.prototype.getContext;
                HTMLCanvasElement.prototype.getContext = function (type, ...rest) { return /webgl/.test(type) ? null : orig.call(this, type, ...rest); };""")
            page.on('pageerror', lambda e: report['errors'].append('nogl:' + str(e)))
            page.goto(server.url)
            expect(page.locator('#character-name')).to_be_visible()
            page.locator('[data-world-page="estate"]').click()
            page.wait_for_timeout(1200)
            assert not page.evaluate("document.body.classList.contains('stage3d-on')")
            page.evaluate("(r) => BattleReplay.open(r)", REPORT)
            expect(page.locator('#battle-replay')).to_be_visible()
            assert page.evaluate("document.querySelectorAll('.fx3d-canvas').length") == 0
            page.evaluate("() => BattleReplay.close()")
            report['checks'].append('without WebGL: no 3D canvas, replay and pages still work (SVG/Canvas2D fallback)')
            browser.close()
        assert not [e for e in report['errors'] if 'Failed to load resource' not in e], report['errors']
        report['passed'] = True
    finally:
        server.stop()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
