"""三维特效真实浏览器验收：单上下文、舞台数据绑定、战报让出/恢复上下文、开合 30 次无 GPU 对象累积、无 WebGL 降级。

需要 Playwright 与 Chromium/Edge（见 tests.support.launch_browser）。WebGL 使用 SwiftShader 软件渲染，
帧率数值仅代表本机软件渲染环境，不代表真实 GPU。
"""
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from tests.browser_world import BrowserWorldDriver
from tests.support import Server, attach_session, baseline_route, launch_browser

REPORT = {'outcome': 'victory', 'rounds': 1, 'strategy': 'balanced', 'strategy_label': '均衡', 'enemy': {'name': '测试', 'max_hp': 100, 'kind': 'beast'},
          'player': {'max_hp': 100, 'max_mp': 50}, 'treasures': {'main': None, 'guard': None},
          'frames': [{'round': 0, 'player': {'hp': 100, 'mp': 20}, 'enemy': {'hp': 100, 'barrier': 0}, 'intent': '蓄势', 'action': '准备', 'events': []},
                     {'round': 1, 'player': {'hp': 100, 'mp': 20}, 'enemy': {'hp': 0, 'barrier': 0}, 'intent': '—', 'action': '斗法',
                      'events': [{'type': 'damage', 'source': 'player', 'target': 'enemy', 'label': '攻', 'amount': 100}]}]}
# 三维斗法台：覆盖本方/法宝/同行/敌方重击/回护/丹药/封印/金钟罩/破盾与终局消散
def _ev(kind, source, target, label, amount=None):
    item = {'type': kind, 'source': source, 'target': target, 'label': label}
    if amount is not None:
        item['amount'] = amount
    return item


def _frame(round_, php, ehp, barrier, action, events):
    return {'round': round_, 'player': {'hp': php, 'mp': 60}, 'enemy': {'hp': ehp, 'barrier': barrier}, 'intent': '重击', 'action': action, 'events': events}


ARENA = {'outcome': 'victory', 'rounds': 5, 'strategy': 'balanced', 'strategy_label': '均衡', 'enemy': {'name': '赤沙妖狼王', 'max_hp': 400, 'kind': 'guard'},
         'player': {'max_hp': 300, 'max_mp': 100}, 'treasures': {'main': {'name': '本命法宝', 'quality': '上品'}, 'guard': {'name': '护持法宝', 'quality': '中品'}},
         'frames': [_frame(0, 300, 400, 60, '准备', []),
                    _frame(1, 270, 300, 0, '运功强攻', [_ev('shield', 'player', 'enemy', '破盾：运功强攻', 60), _ev('damage', 'player', 'enemy', '运功强攻', 80),
                                                    _ev('damage', 'main', 'enemy', '本命法宝出击', 20), _ev('shield_absorb', 'guard', 'player', '护持法宝实际拦截', 40),
                                                    _ev('damage', 'enemy', 'player', '敌方重击', 30)]),
                    _frame(2, 290, 250, 0, '服回元丹', [_ev('heal', 'player', 'player', '服回元丹', 50), _ev('damage', 'npc', 'enemy', '同行支援', 10), _ev('damage', 'enemy', 'player', '敌方常击', 30)]),
                    _frame(3, 290, 250, 0, '镇魂符', [_ev('control', 'player', 'enemy', '镇魂符')]),
                    _frame(4, 290, 120, 0, '防御', [_ev('defend', 'player', 'player', '防御回灵', 6), _ev('damage', 'main', 'enemy', '本命法宝出击', 130)]),
                    _frame(5, 290, 0, 0, '焚火符', [_ev('damage', 'player', 'enemy', '焚火符', 120), _ev('victory', 'player', 'enemy', '战斗胜利')])]}
# 群战战报（FB3）：首领 + 两只小怪，第二拍群攻扫倒一只
SWARM = {**ARENA, 'enemy': {**ARENA['enemy'], 'units': [{'id': 'm1', 'name': '荒野小妖甲', 'max_hp': 40}, {'id': 'm2', 'name': '荒野小妖乙', 'max_hp': 40}]},
         'frames': [{**f, 'units': [{'id': 'm1', 'hp': 40 if i < 4 else 0}, {'id': 'm2', 'hp': 40}]} for i, f in enumerate(ARENA['frames'])]}
SWARM['frames'][4] = {**SWARM['frames'][4], 'events': SWARM['frames'][4]['events'] + [_ev('damage', 'main', 'enemy', '本命法宝出击', 40) | {'unit': 'm1', 'aoe': True}, _ev('fall', 'main', 'enemy', '荒野小妖甲伏诛') | {'unit': 'm1'}]}
LOOKS = [{'tier': 7, 'root': 'fire', 'skill': 'flame', 'form': 'beast', 'boss': True},
         {'tier': 2, 'root': 'wood', 'skill': 'origin', 'form': 'serpent', 'boss': False},
         {'tier': 4, 'root': 'earth', 'skill': 'mountain', 'form': 'golem', 'boss': False},
         {'tier': 0, 'root': None, 'skill': 'origin', 'form': 'shade', 'boss': False}]
ARTIFACTS = Path(__file__).resolve().parents[1] / 'artifacts' / 'fx3d-qa'
GPU_ARGS = ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']
STATS = "async () => { const m = await import('/fx3d.js'); return m.stats(); }"


def wait_fx3d(page, timeout=15000):
    # 页面 CSP 禁 eval，wait_for_function 的字符串谓词不可用；改用 evaluate 轮询
    for _ in range(timeout // 100):
        if page.evaluate("() => document.querySelector('#replay-stage')?.dataset.fx3d === 'on'"):
            return
        page.wait_for_timeout(100)
    raise AssertionError('三维斗法台未在 %d ms 内就绪' % timeout)


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

            # 三维斗法台：四种外形/天时各完整播放一遍并截图；信息层（气血、飘字、日志）与三维并行存在
            ARTIFACTS.mkdir(parents=True, exist_ok=True)
            page.evaluate("(r) => { window.__arena = r; }", ARENA)
            for index, look in enumerate(LOOKS):
                page.evaluate("(look) => BattleReplay.open(window.__arena, look)", look)
                wait_fx3d(page)
                assert page.evaluate("document.getElementById('battle-replay').classList.contains('immersive')")
                battle = page.evaluate(STATS)['battle']
                assert battle and battle['form'] == look['form'] and battle['geometries'] > 20, battle
                if index == 0:
                    for beat in range(len(ARENA['frames']) - 1):
                        page.wait_for_timeout(2600 if beat == 0 else 900)
                        page.screenshot(path=str(ARTIFACTS / ('arena-beat%d.png' % (beat + 1))))
                    page.wait_for_timeout(900)
                else:
                    page.wait_for_timeout(2600)
                floaters = page.evaluate("document.querySelectorAll('#replay-floaters .floater3d').length")
                page.screenshot(path=str(ARTIFACTS / ('arena-%s.png' % look['form'])))
                page.locator('#replay-skip').click()
                expect(page.locator('#replay-result')).to_be_visible()
                page.wait_for_timeout(1500)
                page.screenshot(path=str(ARTIFACTS / ('arena-%s-result.png' % look['form'])))
                assert page.evaluate("document.getElementById('replay-player-hp-text').textContent").startswith('本方气血')
                report.setdefault('arena', []).append({'look': look, 'battle': page.evaluate(STATS)['battle'], 'floaters_seen': floaters})
                page.locator('#replay-close').click()
                expect(page.locator('#battle-replay')).to_be_hidden()
                assert page.evaluate("document.querySelectorAll('.fx3d-canvas').length") == 0
            report['checks'].append('3D arena: four enemy forms x four sky tiers play, skip/close work, canvas released; screenshots in artifacts/fx3d-qa')
            page.evaluate("(r) => BattleReplay.open(r, {tier: 3, root: 'wood', skill: 'origin', form: 'beast', boss: false})", SWARM)
            wait_fx3d(page)
            battle = page.evaluate(STATS)['battle']
            assert battle['units'] == 2 and battle['unitsUp'] == 2, battle
            page.locator('#replay-skip').click()
            page.wait_for_timeout(600)
            battle = page.evaluate(STATS)['battle']
            assert battle['unitsUp'] == 0 and battle['foeGone'], battle
            page.screenshot(path=str(ARTIFACTS / 'arena-swarm-result.png'))
            page.locator('#replay-close').click()
            report['checks'].append('3D swarm: minion roster built from the report; skip lands with the pack fallen/scattered')

            # 窄屏：斗法台与 HUD 在 375x812 下可见且不出横向滚动
            page.set_viewport_size({'width': 375, 'height': 812})
            page.evaluate("(look) => BattleReplay.open(window.__arena, look)", LOOKS[1])
            wait_fx3d(page)
            page.wait_for_timeout(2600)
            page.screenshot(path=str(ARTIFACTS / 'arena-mobile.png'))
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
            box = page.locator('#replay-stage').bounding_box()
            assert box and box['height'] >= 150, box
            page.locator('#replay-close').click()
            page.set_viewport_size({'width': 1365, 'height': 900})
            report['checks'].append('mobile 375x812: arena stage visible, no horizontal overflow')
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
            page.evaluate("(r) => BattleReplay.open(r, {tier: 3, root: 'fire', skill: 'flame', form: 'beast', boss: true})", ARENA)
            expect(page.locator('#battle-replay')).to_be_visible()
            page.wait_for_timeout(2500)
            assert page.evaluate("document.querySelectorAll('.fx3d-canvas').length") == 0
            assert page.evaluate("document.querySelector('#replay-stage').dataset.fx3d") is None
            assert page.evaluate("getComputedStyle(document.querySelector('.replay-svg')).visibility") == 'visible'
            page.locator('#replay-skip').click()
            expect(page.locator('#replay-result')).to_be_visible()
            page.evaluate("() => BattleReplay.close()")
            report['checks'].append('without WebGL: no 3D canvas, replay and pages still work (SVG/Canvas2D fallback)')
            page.evaluate("(r) => BattleReplay.open(r, {tier: 3, root: 'fire', skill: 'flame', form: 'beast', boss: false})", SWARM)
            expect(page.locator('#battle-replay')).to_be_visible()
            assert page.evaluate("document.querySelectorAll('#replay-stage .actor.unit').length") == 2
            page.locator('#replay-timeline').evaluate("(n) => { n.value = '4'; n.dispatchEvent(new Event('input')); }")
            assert page.evaluate("document.querySelectorAll('#replay-units .unit-pip.down').length") == 1
            assert page.evaluate("document.querySelector('#replay-stage [data-actor=\"m1\"]').classList.contains('down')")
            page.locator('#replay-skip').click()
            assert page.evaluate("document.querySelectorAll('#replay-units .unit-pip.down').length") == 2, 'the pack scatters with the leader'
            page.evaluate("() => BattleReplay.close()")
            report['checks'].append('without WebGL: swarm report shows minions on the SVG stage and HUD pips; fallen and scattered minions dim')
            browser.close()
        assert not [e for e in report['errors'] if 'Failed to load resource' not in e], report['errors']
        report['passed'] = True
    finally:
        server.stop()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
