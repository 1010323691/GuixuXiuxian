"""三维宗门主界面真实浏览器验收（1920×1080、100% 缩放，Playwright + 本机 Chromium/Edge）。

真实 HTTP 服务、真实账号与公开动作路线进入凡界；检查：
- HUD 数值与 /api/state 一致（不使用示例数字）；
- 南侧默认、东、西、背面、高空、近景五类视角截图，记录帧率/绘制调用/三角形，镜头不入山、不入云、不进建筑；
- 拖拽与点击区分；建筑（画布拾取与标记）、Dock、右侧入口、任务「前往」打开同一卷目；面板内拖拽不转场景；Esc 返回；
- 1080p 下图标/字号范围、面板不超屏、可见标记互不重叠且不压 HUD；
- 突破按钮的可用性与原因来自服务端；从山门打开九州卷后按原事项卡写入，HUD 资源与同步状态随之更新；
- ?no3d=1 降级图录可打开卷目；dispose 后几何/贴图计数归零。
截图与报告写入 artifacts/sect3d-qa/（本地证据，不入库）。帧率依赖本机 GPU，只作记录不设门槛。
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from tests.r3_support import ClockHTTP
from tests.support import attach_session, baseline_route, launch_browser, save_screenshot

ARTIFACTS = Path(__file__).resolve().parents[1] / 'artifacts' / 'sect3d-qa'
GPU_ARGS = ['--no-sandbox', '--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--use-angle=d3d11']
VIEWS = {  # 方位角（0=自南向北看）、俯仰、距离、注视点
    'south-default': None,
    'east-side': (1.5708, .38, 520, [40, 130, -60]),
    'west-side': (-1.5708, .38, 520, [-40, 130, -60]),
    'back-north': (3.1416, .42, 600, [0, 150, -80]),
    'high-aerial': (0.4, 1.2, 900, [0, 130, -60]),
    'main-hall-close': (0.3, .3, 200, [0, 230, -290]),
    'gate-close': (0.5, .25, 160, [0, 92, 140]),
    'west-zone': (-0.6, .4, 260, [-185, 150, -40]),
    'east-zone': (0.7, .4, 260, [185, 150, -40]),
    'grand-stairs': (0.6, .18, 300, [0, 50, 280]),
}
PRESSED = "() => document.querySelector('[data-world-page][aria-pressed=true]')?.dataset.worldPage || null"
STATE = "() => ({panel: document.body.classList.contains('sect-panel-open'), page: (" + PRESSED + ")()})"
HUD_SIZES = """() => {
  const out = {icons: [], text: [], panels: []};
  for (const el of document.querySelectorAll('#sect-hub .icon')) { const r = el.getBoundingClientRect(); if (r.width) out.icons.push(Math.round(r.width)); }
  for (const el of document.querySelectorAll('#sect-hub span, #sect-hub strong, #sect-hub p, #sect-hub button, #sect-hub li, #sect-hub h2, #sect-hub small')) {
    if (!el.getClientRects().length || !el.textContent.trim() || el.children.length > 2) continue;
    out.text.push(parseFloat(getComputedStyle(el).fontSize));
  }
  for (const sel of ['.sh-player', '.sh-top', '.sh-corner', '.sh-tracker', '.sh-plays', '.sh-cultivate', '.sh-dock', '.sh-view']) {
    const r = document.querySelector(sel).getBoundingClientRect(); out.panels.push([sel, Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)]);
  }
  return out;
}"""
WINDOW = """() => {
  const box = (el) => { if (!el || !el.getClientRects().length) return null; const r = el.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; };
  const visible = (sel) => { const el = document.querySelector(sel); return !!el && !!el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden'; };
  const hud = ['.sh-player', '.sh-top', '.sh-corner', '.sh-tracker', '.sh-plays', '.sh-cultivate', '.sh-dock', '.sh-view'].map((sel) => [sel, box(document.querySelector(sel))]);
  return {open: document.body.classList.contains('sect-panel-open'), view: document.getElementById('world-workbench').dataset.sectView,
          win: box(document.getElementById('world-workbench')), title: document.getElementById('sect-window-title').textContent,
          nav: visible('#world-navigation'), aside: visible('.world-aside'), growth: visible('#growth-panel'), sources: visible('#growth-sources'), legacy: visible('#legacy-history'),
          side: document.querySelector('[data-side-tab][aria-selected=true]')?.dataset.sideTab || null, hud};
}"""
MARKERS = """() => {
  const vis = [...document.querySelectorAll('.sect-marker')].filter((m) => !m.hidden).map((m) => { const r = m.getBoundingClientRect(); return {t: m.textContent, l: r.left, r: r.right, top: r.top, b: r.bottom, occ: m.classList.contains('occluded')}; });
  const hud = [...document.querySelectorAll('.sh-player, .sh-top, .sh-corner, .sh-tracker, .sh-plays, .sh-cultivate, .sh-dock, .sh-view')].map((n) => n.getBoundingClientRect());
  const hit = (a, b) => a.l < b.r && a.r > b.l && a.top < b.b && a.b > b.top;
  const overlaps = [];
  vis.forEach((a, i) => vis.slice(i + 1).forEach((b) => { if (hit(a, b)) overlaps.push([a.t, b.t]); }));
  const onHud = vis.filter((a) => hud.some((h) => hit(a, {l: h.left, r: h.right, top: h.top, b: h.bottom}))).map((a) => a.t);
  const out = vis.filter((a) => a.l < 0 || a.top < 0 || a.r > innerWidth || a.b > innerHeight).map((a) => a.t);
  return {visible: vis.length, occluded: vis.filter((a) => a.occ).length, overlaps, onHud, offscreen: out};
}"""


def check(report, name, ok, detail=''):
    report['checks'].append({'name': name, 'ok': bool(ok), 'detail': detail})
    print(('PASS ' if ok else 'FAIL ') + name + ('  ' + json.dumps(detail, ensure_ascii=False) if detail != '' else ''))


def wait_scene(page):
    for _ in range(300):
        if page.evaluate('() => !!window.__sect3d || !document.getElementById("sect-fallback").hidden'):
            break
        page.wait_for_timeout(100)
    page.wait_for_timeout(2000)


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    report = {'checks': [], 'views': {}, 'errors': []}
    server = ClockHTTP(live=True).start()
    try:
        server.create()
        baseline_route(server.snapshot, server.action)
        server.action('world_enter')
        with sync_playwright() as p:
            browser = launch_browser(p, args=GPU_ARGS)
            page = browser.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
            attach_session(page, server)
            page.on('pageerror', lambda e: report['errors'].append(str(e)))
            page.on('console', lambda m: report['errors'].append(m.text) if m.type == 'error' else None)
            page.goto(server.url)
            wait_scene(page)
            check(report, '三维宗门已初始化', page.evaluate('() => !!window.__sect3d'))

            # ---- HUD 真实数据
            snap = server.snapshot()
            world = snap['view']['world']
            res = {r['id']: r for r in world['resources']}
            hud = page.evaluate("() => Object.fromEntries(['sh-name','sh-realm','sh-stone','sh-herb','sh-attack','sh-mp-text','sh-hp-text','sh-contrib'].map((id) => [id, document.getElementById(id).textContent]))")
            prog = world['loot']['progress']
            attack = next(s['value'] for p in world['pages'] if p['id'] == 'character' for s in p['stats'] if s['label'] == '攻击')
            expected = {'sh-name': snap['view']['character']['name'], 'sh-realm': prog['stage_label'] + prog['milestone_label'],
                        'sh-stone': format(res['world_stone']['value'], ','), 'sh-herb': str(snap['state']['world']['inventory']['herb']),
                        'sh-attack': '攻击 %s' % attack, 'sh-mp-text': '%d/%d' % (res['world_mp']['value'], res['world_mp']['max']),
                        'sh-hp-text': '%d/%d' % (res['world_hp']['value'], res['world_hp']['max'])}
            check(report, 'HUD 数值与 /api/state 一致', all(hud[k] == v for k, v in expected.items()), {'hud': hud, 'expected': expected})

            # ---- 视角与性能
            for name, v in VIEWS.items():
                if v:
                    page.evaluate('(v) => window.__sect3d.view(v[0], v[1], v[2], v[3])', list(v))
                page.wait_for_timeout(1800)
                save_screenshot(page, ARTIFACTS / ('%s.png' % name))
                stats = page.evaluate('() => window.__sect3d.stats()')
                marks = page.evaluate(MARKERS)
                report['views'][name] = {'stats': stats, 'markers': marks}
                cam = stats['camera']
                check(report, '视角 %s 镜头不入云/山/建筑' % name, cam['y'] >= 46 and cam['y'] > cam['ground'] + 10 and not cam['inBox'], cam)
                check(report, '视角 %s 标记不重叠、不压 HUD、不出屏' % name, not marks['overlaps'] and not marks['onHud'] and not marks['offscreen'], marks)
            # 极限：最近距离 + 最低俯仰 + 贴近主殿；最大俯仰
            for label, az, el, dist, tgt in (('极限近低', .2, .05, 10, [0, 230, -290]), ('极限近低-台地', 2.4, .05, 10, [-185, 150, -40]), ('极限高', 0, 3, 5000, [0, 130, -60])):
                page.evaluate('(v) => window.__sect3d.view(v[0], v[1], v[2], v[3])', [az, el, dist, tgt])
                page.wait_for_timeout(900)
                cam = page.evaluate('() => window.__sect3d.stats().camera')
                check(report, '镜头约束 %s' % label, cam['y'] >= 46 and cam['y'] > cam['ground'] + 10 and not cam['inBox'], cam)
            save_screenshot(page, ARTIFACTS / 'limit-high.png')
            page.evaluate('() => window.__sect3d.home()'); page.wait_for_timeout(1600)

            # ---- 1080p 尺寸
            sizes = page.evaluate(HUD_SIZES)
            report['hud_sizes'] = sizes
            check(report, 'HUD 图标 18–36px', all(18 <= w <= 36 for w in sizes['icons']), sorted(set(sizes['icons'])))
            check(report, 'HUD 文字 11–20px（正文 14–16）', all(11 <= f <= 20 for f in sizes['text']), sorted(set(sizes['text'])))
            check(report, 'HUD 面板均在 1920×1080 内', all(l >= 0 and t >= 0 and r <= 1920 and b <= 1080 for _, l, t, r, b in sizes['panels']), sizes['panels'])

            # ---- 拖拽 ≠ 点击
            before = page.evaluate('() => window.__sect3d.stats().cameraPosition')
            page.mouse.move(960, 520); page.mouse.down(); page.mouse.move(1180, 540, steps=12); page.mouse.up(); page.wait_for_timeout(700)
            moved = page.evaluate('() => window.__sect3d.stats().cameraPosition') != before
            check(report, '拖拽旋转场景且不打开面板', moved and not page.evaluate(STATE)['panel'])
            page.evaluate('() => window.__sect3d.home()'); page.wait_for_timeout(1600)

            # ---- 画布拾取：在主殿投影附近找一个命中点，用真实鼠标点击
            target = page.evaluate("""() => { const m = window.__sect3d.markers().find((x) => x.id === 'main-hall');
                for (let dy = 8; dy < 120; dy += 6) if (window.__sect3d.pickAt(m.x, m.y + dy) === 'main-hall') return [m.x, m.y + dy]; return null; }""")
            check(report, '主殿可被画布拾取', target is not None, target)
            if target:
                page.mouse.click(*target); page.wait_for_timeout(1400)
                check(report, '点击主殿 → 聚焦并打开宗门卷', page.evaluate(STATE) == {'panel': True, 'page': 'sects'}, page.evaluate(STATE))
                save_screenshot(page, ARTIFACTS / 'panel-sects.png')
                ws = page.evaluate("() => { const r = document.getElementById('world-workbench').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }")
                check(report, '功能面板不超出 1080p 视口', ws[0] >= 0 and ws[1] >= 0 and ws[2] <= 1920 and ws[3] <= 1080, ws)
                cam0 = page.evaluate('() => window.__sect3d.stats().cameraPosition')
                page.mouse.move(900, 420); page.mouse.down(); page.mouse.move(1100, 430, steps=8); page.mouse.up(); page.wait_for_timeout(400)
                check(report, '面板内拖拽不穿透到场景', page.evaluate('() => window.__sect3d.stats().cameraPosition') == cam0)
                page.keyboard.press('Escape'); page.wait_for_timeout(400)
                check(report, 'Esc 返回宗门', not page.evaluate(STATE)['panel'])

            # ---- 标记、Dock、右侧、任务前往、快捷键打开同一卷目
            for label, action, want in (
                ('标记 试剑台', lambda: page.locator('.sect-marker', has_text='试剑台').click(), 'arena'),
                ('Dock 洞府', lambda: page.locator('.sh-slot', has_text='洞府').click(), 'estate'),
                ('快捷键 L', lambda: page.keyboard.press('l'), 'craft'),
                ('右侧 世界首领', lambda: page.locator('.sh-play', has_text='世界首领').click(), 'exploration'),
                ('右上 名录', lambda: page.locator('.sh-event', has_text='名录').click(), 'achievements'),
                ('任务 前往', lambda: page.locator('.sh-go').first.click(), world['goals'][0]['target_page']),
            ):
                page.evaluate('() => window.__sect3d.home()'); page.wait_for_timeout(1300)
                action(); page.wait_for_timeout(1300)
                check(report, '%s → %s' % (label, want), page.evaluate(STATE) == {'panel': True, 'page': want}, page.evaluate(STATE))
                page.keyboard.press('Escape'); page.wait_for_timeout(300)
                if page.evaluate(STATE)['panel']:
                    page.keyboard.press('Escape'); page.wait_for_timeout(300)

            # ---- 小窗：原工作台退为右侧小窗，卷目导航与卷宗栏不在窗内；HUD 与场景照常可用
            page.evaluate('() => window.__sect3d.home()'); page.wait_for_timeout(1300)
            page.locator('.sh-slot', has_text='角色').click(); page.wait_for_timeout(1600)
            geo = page.evaluate(WINDOW)
            win = geo['win']
            overlaps = [sel for sel, r in geo['hud'] if r and win and r[0] < win[2] and win[0] < r[2] and r[1] < win[3] and win[1] < r[3]]
            check(report, '小窗在 1080p 内且不压任何 HUD 面板', win and win[0] >= 0 and win[1] >= 0 and win[2] <= 1920 and win[3] <= 1080 and not overlaps, {'win': win, 'overlaps': overlaps})
            check(report, '小窗内不再有原卷目导航与卷宗栏', geo['open'] and geo['view'] == 'page' and not geo['nav'] and not geo['aside'] and geo['title'] == '人物', geo)
            focus = page.evaluate("() => window.__sect3d.markers().find((m) => m.id === 'scripture')")
            check(report, '小窗打开时画面让开：聚焦的藏经阁在小窗左侧', focus['onScreen'] and focus['x'] < win[0] - 40, {'x': round(focus['x']), 'win_left': win[0]})
            other = page.evaluate("""() => { const pages = Object.fromEntries(window.__sect3d.markers().map((m) => [m.label, m.page]));
                const node = [...document.querySelectorAll('.sect-marker')].find((m) => !m.hidden && !m.classList.contains('occluded') && pages[m.getAttribute('aria-label').replace('，打开对应功能', '')] !== 'character');
                if (!node) return null; node.dataset.qa = 'other'; return pages[node.getAttribute('aria-label').replace('，打开对应功能', '')]; }""")
            if other:
                page.locator('[data-qa="other"]').click(); page.wait_for_timeout(1600)
            check(report, '小窗打开时点场景标记直接切换卷目', other is not None and page.evaluate(STATE) == {'panel': True, 'page': other}, {'want': other, 'got': page.evaluate(STATE)})
            page.locator('.sh-slot', has_text='功法').click(); page.wait_for_timeout(900)
            check(report, '小窗打开时 Dock 仍可切换卷目', page.evaluate(STATE) == {'panel': True, 'page': 'character'}, page.evaluate(STATE))
            page.keyboard.press('Escape'); page.wait_for_timeout(300)
            if page.evaluate(STATE)['panel']:
                page.keyboard.press('Escape'); page.wait_for_timeout(300)

            # ---- 原工作台的卷宗（任务/回执/进度）、潜修详情、序章旧事：各自在 HUD 有入口，开同一份原内容，一次 Esc 合上
            def via_settings(selector):
                return lambda: (page.locator('#sh-settings-button').click(), page.locator(selector).click())
            for label, action, view, expect_ in (
                ('追踪 任务簿', lambda: page.locator('.sh-tracker [data-dossier="quests"]').click(), 'dossier', lambda g: g['aside'] and g['side'] == 'quests'),
                ('追踪 回执', lambda: page.locator('.sh-tracker [data-dossier="recent"]').click(), 'dossier', lambda g: g['aside'] and g['side'] == 'recent'),
                ('设置 本卷进度', via_settings('#sh-settings-menu [data-dossier="progress"]'), 'dossier', lambda g: g['aside'] and g['side'] == 'progress'),
                ('潜修 详情', lambda: page.locator('#sh-growth-open').click(), 'growth', lambda g: g['growth'] and g['sources']),
                ('设置 序章旧事', via_settings('#sh-legacy'), 'legacy', lambda g: g['legacy']),
            ):
                action(); page.wait_for_timeout(700)
                g = page.evaluate(WINDOW)
                w = g['win']
                check(report, '%s → 小窗 %s' % (label, view), g['open'] and g['view'] == view and expect_(g) and w and w[2] <= 1920 and w[3] <= 1080 and not g['nav'],
                      {k: g[k] for k in ('open', 'view', 'title', 'aside', 'side', 'growth', 'sources', 'legacy', 'win')})
                page.keyboard.press('Escape'); page.wait_for_timeout(300)
                check(report, '%s 一次 Esc 合上' % label, not page.evaluate(STATE)['panel'] and page.evaluate("document.getElementById('legacy-history').hidden"))
            save_screenshot(page, ARTIFACTS / 'hud-entries.png')

            # ---- 突破按钮：状态与原因来自服务端 world_advance（拨快时钟使修为足够，仍受守关等条件约束）
            server.clock.advance(14 * 3600)
            page.reload(); wait_scene(page)
            page.wait_for_timeout(800)
            advance = next(a for p in server.snapshot()['view']['world']['pages'] if p['id'] == 'character' for a in p['actions'] if a['id'] == 'world_advance')
            button = page.evaluate("() => ({disabled: document.getElementById('sh-break').disabled, title: document.getElementById('sh-break').title, bar: document.getElementById('sh-break-bar').getAttribute('aria-valuenow')})")
            check(report, 'HUD 突破按钮与服务端 world_advance 一致', button['disabled'] == (not advance['enabled']) and (advance['enabled'] or button['title'] == advance['reason']),
                  {'hud': button, 'server': {'enabled': advance['enabled'], 'reason': advance['reason']}})

            # ---- 真实写入：从山门打开九州卷，按原事项卡提交采集，HUD 资源与同步状态随之更新
            herb_before = server.snapshot()['state']['world']['inventory'].get('herb', 0)
            page.locator('.sect-marker', has_text='山门').click(); page.wait_for_timeout(1400)
            check(report, '标记 山门 → world', page.evaluate(STATE) == {'panel': True, 'page': 'world'}, page.evaluate(STATE))
            page.evaluate("(key) => { const n = [...document.querySelectorAll('.world-action')].find((x) => x.dataset.actionKey === key); if (n) { n.dataset.qa = 'gather'; n.dispatchEvent(new CustomEvent('guixu:reveal', {bubbles: true})); } }", 'world:world_gather:{"item":"herb"}')
            card = page.locator('[data-qa="gather"]')
            submit = card.locator('.world-submit')
            if card.count() and submit.is_enabled():
                if not submit.is_visible():
                    card.locator('summary').click()
                with page.expect_response(lambda r: r.url.endswith('/api/action') and r.request.method == 'POST') as event:
                    submit.click()
                body = event.value.json()
                page.wait_for_timeout(1000)
                herb_after = server.snapshot()['state']['world']['inventory'].get('herb', 0)
                sync = page.evaluate("() => [document.getElementById('save-status').dataset.state, document.getElementById('sh-sync-dot').dataset.state]")
                check(report, '面板内原事项卡写入成功，HUD 药草与同步状态更新', body.get('ok') is True and herb_after > herb_before and page.locator('#sh-herb').text_content() == str(herb_after) and sync == ['synced', 'synced'],
                      {'herb': [herb_before, herb_after, page.locator('#sh-herb').text_content()], 'sync': sync})
            else:
                check(report, '面板内原事项卡写入成功，HUD 药草与同步状态更新', False, '采集药草事项不可用')
            save_screenshot(page, ARTIFACTS / 'panel-world-write.png')
            # 写入后的叠加提示（.toast）与操作反馈（#notice）不得压住「返回宗门」，提示也不得盖到面板上
            overlap = page.evaluate("""() => {
                const box = (el) => { const r = el.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; };
                const hit = (a, b) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
                const close = box(document.getElementById('sect-panel-close'));
                const panel = box(document.getElementById('world-workbench'));
                const toasts = [...document.querySelectorAll('.toast')].map(box);
                const notice = document.getElementById('notice');
                const noticeBox = notice.hidden ? null : box(notice);
                const c = [(close[0] + close[2]) / 2, (close[1] + close[3]) / 2];
                const top = document.elementFromPoint(c[0], c[1]);
                return { toasts: toasts.length, onClose: toasts.filter((t) => hit(t, close)).length, onPanel: toasts.filter((t) => hit(t, panel)).length,
                         noticeOnClose: !!noticeBox && hit(noticeBox, close), closeOnTop: !!top && !!top.closest('#sect-panel-close') };
            }""")
            check(report, '写入后提示不压「返回宗门」与面板，按钮可点', overlap['toasts'] > 0 and overlap['onClose'] == 0 and overlap['onPanel'] == 0 and not overlap['noticeOnClose'] and overlap['closeOnTop'], overlap)
            page.keyboard.press('Escape'); page.wait_for_timeout(300)
            if page.evaluate(STATE)['panel']:
                page.keyboard.press('Escape'); page.wait_for_timeout(300)

            # ---- 释放
            freed = page.evaluate('() => { const before = window.__sect3d.stats(); const after = window.__sect3d.dispose(); return {before: {geometries: before.geometries, textures: before.textures}, after}; }')
            report['dispose'] = freed
            check(report, 'dispose 后几何与贴图释放', freed['after']['geometries'] == 0 and freed['after']['textures'] == 0, freed)

            # ---- 降级图录
            page.goto(server.url + '/?no3d=1'); wait_scene(page)
            check(report, '降级图录可见', page.locator('#sect-fallback').is_visible())
            save_screenshot(page, ARTIFACTS / 'fallback.png')
            page.locator('.sect-fallback-entry', has_text='修炼洞府').click(); page.wait_for_timeout(800)
            check(report, '降级图录打开洞府卷', page.evaluate(STATE) == {'panel': True, 'page': 'estate'}, page.evaluate(STATE))
            browser.close()
    finally:
        server.close()
    real_errors = [e for e in report['errors'] if 'Password forms' not in e]
    check(report, '页面无脚本错误', not real_errors, real_errors[:5])
    report['passed'] = all(c['ok'] for c in report['checks'])
    (ARTIFACTS / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print('passed' if report['passed'] else 'FAILED', sum(c['ok'] for c in report['checks']), '/', len(report['checks']))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
