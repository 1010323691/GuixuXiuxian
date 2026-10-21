"""云海御空阶段二/三验收：用规则层真实生成的战报（序章/野外/秘境副本/支线精英/世界Boss）在三维斗法台回放并截图。

战报由真实 HTTP 服务按合法公开动作路线（R4Planner）打出，回放走游戏内 BattleReplay → fx3d → arena3d；
断言每场都启用三维、终局状态与战报一致（胜局敌方消散、败局才倒下）、无页面异常。截图在 artifacts/fx3d-qa/real/（不入库）。
使用硬件 GPU 参数启动（无 GPU 时 Chromium 自行回退软件渲染，帧率数值仅供参考）。需要 Playwright 与 Chromium/Edge。
"""
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

from tests.browser_fx3d import enter_world, wait_fx3d
from tests.r3_support import ClockHTTP
from tests.r4_route import R4Planner
from tests.support import Server, attach_session, baseline_route, launch_browser

ARTIFACTS = Path(__file__).resolve().parents[1] / 'artifacts' / 'fx3d-qa' / 'real'
GPU_ARGS = ['--no-sandbox', '--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--use-angle=d3d11']
STATS = "async () => { const m = await import('/fx3d.js'); return m.stats().battle; }"
PICK = [('prelude', 1, 1), ('wild', 0, 3), ('dungeon', -1, 5), ('elite', 0, 7), ('world_boss', 0, 8)]  # 战报类别、序号、展示境界档


def collect_reports():
    """沿 R4 合法路线打出各类真实战斗，按 enemy.kind 收集 battle_report。"""
    reports = {}
    server = ClockHTTP().start()
    try:
        server.create()

        def action(name, **params):
            result = server.action(name, **params)
            if result.get('battle_report'):
                reports.setdefault(result['battle_report']['enemy']['kind'], []).append({'report': result['battle_report'], 'world': result['state'].get('world')})
            return result
        baseline_route(server.snapshot, action)
        action('world_enter')
        p = R4Planner(server.snapshot, action)
        p.accept('first_forge'); p.prepare(); p.dungeon(difficulty=1); p.claim('first_forge')
        p.rest(); p.perform('world_hunt'); p.win()
        p.accept('allied_roads'); p.perform('world_sect_join', sect='sword')
        for _ in range(2):
            p.cost({'herb': 2}); p.perform('world_gift', npc='healer')
        p.cost({'herb': 3}); p.perform('world_sect_daily', item='herb'); p.claim('allied_roads')
        p.craft('barrier_pill'); p.craft('soul_talisman')
        start = server.clock(); p.advance(server.clock, 12 * 3600, start)
        p.accept('caravan_rescue'); p.secret('desert', 'chisha'); p.elite('caravan_guard', 'chisha')
        p.rest(); p.perform('world_boss_enter'); p.perform('world_auto_battle', strategy='frugal')
    finally:
        server.close()
    return reports


def swarm12():
    """阶段四压力回放：首领 + 10 只小怪 + 主角 = 12 个飞行单位；小怪逐拍扑击，第 3 拍群攻收 3 只，末拍首领败亡、残余溃散。"""
    ids = ['m%d' % (i + 1) for i in range(10)]
    hp = {u: 30 for u in ids}
    frames = [{'round': 0, 'player': {'hp': 400, 'mp': 60}, 'enemy': {'hp': 600, 'barrier': 0}, 'units': [{'id': u, 'hp': 30} for u in ids], 'intent': '常击', 'action': '准备', 'events': []}]
    leader = 600
    for n in range(1, 7):
        events = [{'type': 'damage', 'source': 'player', 'target': 'enemy', 'label': '运功强攻', 'amount': 100}]
        leader -= 100
        if n == 3:
            events.append({'type': 'damage', 'source': 'main', 'target': 'enemy', 'label': '本命法宝出击', 'amount': 30, 'aoe': True})
            for u in ids[:3]:
                hp[u] = 0
                events += [{'type': 'damage', 'source': 'main', 'target': 'enemy', 'label': '本命法宝出击', 'amount': 30, 'unit': u, 'aoe': True},
                           {'type': 'fall', 'source': 'main', 'target': 'enemy', 'label': u + '伏诛', 'unit': u}]
        if leader > 0:
            events.append({'type': 'damage', 'source': 'enemy', 'target': 'player', 'label': '敌方常击', 'amount': 20})
            events += [{'type': 'damage', 'source': 'enemy', 'target': 'player', 'label': '小妖扑击', 'amount': 3, 'unit': u} for u in ids if hp[u] > 0]
        else:
            events += [{'type': 'scatter', 'source': 'enemy', 'target': 'enemy', 'label': '残余小怪溃散', 'amount': 7}, {'type': 'victory', 'source': 'player', 'target': 'enemy', 'label': '战斗胜利'}]
        frames.append({'round': n, 'player': {'hp': 300, 'mp': 40}, 'enemy': {'hp': max(0, leader), 'barrier': 0}, 'units': [{'id': u, 'hp': hp[u]} for u in ids],
                       'intent': '常击', 'action': '运功强攻', 'events': events})
    return {'outcome': 'victory', 'rounds': 6, 'strategy': 'balanced', 'strategy_label': '均衡',
            'enemy': {'name': '赤沙妖狼王', 'max_hp': 600, 'kind': 'guard', 'units': [{'id': u, 'name': '荒野小妖', 'max_hp': 30} for u in ids]},
            'player': {'max_hp': 400, 'max_mp': 100}, 'treasures': {'main': {'name': '本命法宝', 'quality': '上品'}, 'guard': None}, 'frames': frames}


def look(entry, tier):
    """与 app.js battleLook/enemyLook 相同的展示线索（只用于外观）。"""
    report, world = entry['report'], entry['world'] or {}
    name = report['enemy']['name']
    rules = [('ape', '猿|猴|猩'), ('golem', '傀|石|岩|铁|甲'), ('shade', '影|魂|鬼|魅|灵体|怨'), ('beast', '狼|犬|虎|豹|熊|兽|彘|猪'),
             ('serpent', '蛟|龙|蛇|蟒|虺'), ('fox', '狐|妖|魅'), ('human', '修|客|弟子|长老|魔|贼|匪|人|士|师|将|使|尊|王|主')]
    form = next((kind for kind, pattern in rules if re.search(pattern, name)), 'spirit')
    prelude = report['enemy']['kind'] == 'prelude'
    return {'tier': tier, 'root': None if prelude else (world.get('root') or {}).get('id'), 'skill': 'origin' if prelude else world.get('skill') or 'origin',
            'form': form, 'boss': bool(re.search('王|尊|主|守|首领|精英|劫|归墟', name))}


def main():
    result = {'passed': False, 'fights': [], 'errors': []}
    reports = collect_reports()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    server = Server(live=True)
    try:
        server.start()
        with sync_playwright() as p:
            browser = launch_browser(p, args=GPU_ARGS)
            page = browser.new_page(viewport={'width': 1280, 'height': 860})
            attach_session(page, server)
            page.on('pageerror', lambda e: result['errors'].append(str(e)))
            page.on('console', lambda m: result['errors'].append(m.text) if m.type == 'error' else None)
            enter_world(page, server, '斗法QA')
            for kind, index, tier in PICK:
                entry = reports[kind][index]
                report, lk = entry['report'], look(entry, tier)
                page.evaluate("([r, l]) => BattleReplay.open(r, l)", [report, lk])
                wait_fx3d(page)
                page.wait_for_timeout(1900)
                page.screenshot(path=str(ARTIFACTS / ('%s-0-intro.png' % kind)))
                page.wait_for_timeout(1300)   # 第一拍 2.3 秒开始，招式约 0.5–0.8 秒后命中
                page.screenshot(path=str(ARTIFACTS / ('%s-1-hit.png' % kind)))
                if len(report['frames']) > 2:
                    page.wait_for_timeout(1950)
                    page.screenshot(path=str(ARTIFACTS / ('%s-2-beat2.png' % kind)))
                page.locator('#replay-skip').click()
                page.wait_for_timeout(2200)
                page.screenshot(path=str(ARTIFACTS / ('%s-9-result.png' % kind)))
                stats = page.evaluate(STATS)
                last = report['frames'][-1]
                assert stats and stats['form'] == lk['form'], stats
                assert stats['foeGone'] == (last['enemy']['hp'] <= 0), (kind, stats)
                assert (stats['heroFall'] > 0) == (report['outcome'] == 'defeat' and last['player']['hp'] <= 0), (kind, stats)
                # 群战：斗法台小怪数与战报一致；首领败亡后小怪全部倒下或溃散，HUD 小格与之对应
                assert stats['units'] == len(report['enemy'].get('units', [])), (kind, stats)
                if last['enemy']['hp'] <= 0:
                    assert stats['unitsUp'] == 0, (kind, stats)
                pips = page.evaluate("document.querySelectorAll('#replay-units .unit-pip').length")
                assert pips == stats['units'], (kind, pips, stats)
                result['fights'].append({'kind': kind, 'enemy': report['enemy']['name'], 'outcome': report['outcome'], 'rounds': report['rounds'],
                                         'events': sorted({e['type'] + ':' + e['source'] for f in report['frames'] for e in f['events']}),
                                         'units': stats['units'], 'fps': stats['fps'], 'drawCalls': stats['drawCalls'], 'geometries': stats['geometries']})
                page.locator('#replay-close').click()
                page.wait_for_timeout(300)
                assert page.evaluate("document.querySelectorAll('.fx3d-canvas').length") == 0
            # 阶段四：12 个单位自由飞行完整回放——全程不撞石柱、避障确实介入、AI 30Hz、终局全部倒下或溃散
            page.evaluate("(r) => BattleReplay.open(r, {tier: 6, root: 'wood', skill: 'origin', form: 'fox', boss: true})", swarm12())
            wait_fx3d(page)
            page.wait_for_timeout(9000)
            page.screenshot(path=str(ARTIFACTS / 'swarm12-mid.png'))
            for _ in range(60):
                if page.locator('#replay-result').is_visible():
                    break
                page.wait_for_timeout(500)
            page.wait_for_timeout(2600)   # 首领败亡后残余小怪飞散约 2.2 秒
            page.screenshot(path=str(ARTIFACTS / 'swarm12-end.png'))
            stats = page.evaluate(STATS)
            assert stats['agents'] == 12 and stats['units'] == 10, stats
            assert stats['clearance'] is not None and stats['clearance'] >= 0, ('a flier touched a pillar', stats)
            assert stats['avoids'] > 0, ('pillar avoidance never engaged', stats)
            assert 27 <= stats['aiHz'] <= 31, ('AI tick off 30 Hz', stats)
            assert stats['unitsUp'] == 0 and stats['foeGone'], stats
            result['swarm12'] = {k: stats[k] for k in ('fps', 'frameMs', 'level', 'ratio', 'drawCalls', 'triangles', 'geometries', 'textures', 'agents', 'aiHz', 'clearance', 'avoids')}
            page.locator('#replay-close').click()
            browser.close()
        assert not [e for e in result['errors'] if 'Failed to load resource' not in e], result['errors']
        result['passed'] = True
    finally:
        server.stop()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
