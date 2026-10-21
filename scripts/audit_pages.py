"""凡界逐页体验审计：11 卷目 × 4 视口，截图 + 一屏/溢出/按钮尺寸/七问要素自动检查。

用法：python scripts/audit_pages.py   （需 Playwright 与 Chromium/Edge，见 tests.support.launch_browser）
产物：artifacts/audit-pages/*.png 与 artifacts/audit-pages/report.json；同时打印 Markdown 汇总。
使用临时数据目录，不触碰 ./data。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import expect, sync_playwright  # noqa: E402

from tests.browser_world import BrowserWorldDriver, ONE_SCREEN  # noqa: E402
from tests.support import Server, attach_session, baseline_route, launch_browser  # noqa: E402

VIEWPORTS = {'desktop': (1365, 900), 'laptop': (1024, 768), 'tablet': (768, 1024), 'phone': (320, 740)}

PROBE = """() => {
  const vis = (el) => el && el.getClientRects().length && !el.closest('[hidden]');
  const count = (sel) => [...document.querySelectorAll(sel)].filter(vis).length;
  const small = [...document.querySelectorAll('button')].filter(vis).map((b) => [b, b.getBoundingClientRect()])
    .filter(([, r]) => r.height < 44 - 0.5).map(([b]) => (b.id || b.className || b.textContent || '').toString().trim().slice(0, 24));
  const text = (id) => (document.getElementById(id)?.textContent || '').trim();
  return {
    where: text('world-page-title'),
    status: count('#resources > *'),
    cards: count('#world-page-actions .action-card, #world-page-actions > *'),
    reasons: count('.action-reason'),
    meta: count('.action-meta'),
    guide: text('world-summary').slice(0, 40),
    logs: count('#world-recent-logs li'),
    smallButtons: small.length, smallSamples: small.slice(0, 5),
    hScroll: document.documentElement.scrollWidth > innerWidth + 1,
  };
}"""


def main():
    out = ROOT / 'artifacts' / 'audit-pages'
    out.mkdir(parents=True, exist_ok=True)
    report = {'pages': [], 'console_errors': [], 'page_errors': []}
    server = Server(live=True)
    try:
        server.start()
        with sync_playwright() as p:
            browser = launch_browser(p)
            page = browser.new_page(viewport={'width': 1365, 'height': 900})
            page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
            page.on('console', lambda m: report['console_errors'].append(m.text) if m.type == 'error' else None)
            attach_session(page, server)
            page.goto(server.url)
            expect(page.locator('#creation')).to_be_visible()
            page.locator('#mode').select_option('free')
            page.locator('#name').fill('审计道友')
            driver = BrowserWorldDriver(page, server)
            driver.click_write(page.locator('#create-button'), '/api/new-game')
            baseline_route(server.snapshot, driver.legacy)
            driver.action('world_enter')
            ids = [entry['id'] for entry in server.snapshot()['view']['world']['pages']]
            for vp, (w, h) in VIEWPORTS.items():
                page.set_viewport_size({'width': w, 'height': h})
                for pid in ids:
                    page.locator(f'[data-world-page="{pid}"]').click()
                    expect(page.locator(f'[data-world-page="{pid}"]')).to_have_attribute('aria-pressed', 'true')
                    page.wait_for_timeout(250)
                    row = page.evaluate(PROBE)
                    row.update(viewport=vp, page=pid, oneScreen=page.evaluate(ONE_SCREEN) or 'ok')
                    page.screenshot(path=str(out / f'{vp}-{pid}.png'))
                    report['pages'].append(row)
            browser.close()
    finally:
        server.stop()
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    bad = [r for r in report['pages'] if r['oneScreen'] != 'ok' or r['hScroll']]
    print(f"| 视口 | 卷目 | 一屏 | 事项卡 | 原因行 | 消耗所得 | 小按钮(<44px) |\n|---|---|---|---|---|---|---|")
    for r in report['pages']:
        print(f"| {r['viewport']} | {r['page']} | {r['oneScreen']} | {r['cards']} | {r['reasons']} | {r['meta']} | {r['smallButtons']} |")
    print('一屏/横向溢出问题:', len(bad), '控制台错误:', len(report['console_errors']), '页面异常:', len(report['page_errors']))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
