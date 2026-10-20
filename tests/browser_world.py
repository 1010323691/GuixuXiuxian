"""True-browser world driver; gameplay uses visible forms/buttons only."""
import json

from playwright.sync_api import expect, sync_playwright

from tests.support import ROOT, Server, baseline_route
from tests.test_world_systems import WorldPlanner

# V3 one-screen UI: nothing may scroll; long content is paged inside fixed regions.
ONE_SCREEN = """() => {
  const de = document.documentElement;
  if (de.scrollHeight > innerHeight + 1 || de.scrollWidth > innerWidth + 1) return 'document ' + de.scrollWidth + 'x' + de.scrollHeight;
  for (const el of document.querySelectorAll('body *')) {
    if (!el.getClientRects().length || el.matches('input, select, textarea')) continue;
    const style = getComputedStyle(el);
    if (/(auto|scroll)/.test(style.overflowY + style.overflowX) && (el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1)) return 'scrollable ' + (el.id || el.className || el.tagName);
  }
  return '';
}"""


def reveal(locator):
    """Ask the paged UI to bring a node's tab and page into view (the same path goal/story buttons use)."""
    locator.evaluate("(node) => node.dispatchEvent(new CustomEvent('guixu:reveal', {bubbles: true}))")


def assert_one_screen(page, label):
    problem = page.evaluate(ONE_SCREEN)
    assert not problem, (label, page.viewport_size, problem)


class BrowserWorldDriver:
    def __init__(self, page, server):
        self.page, self.server = page, server
        self.visited_pages = set()
        self.used_fields = set()
        self.used_actions = set()

    def click_write(self, button, endpoint='/api/action', confirm=False):
        if confirm:
            before = self.server.snapshot()
            button.click()
            expect(self.page.locator('#confirm-dialog')).to_be_visible()
            self.page.locator('#cancel-confirm').click()
            assert self.server.snapshot() == before, 'confirmation cancel wrote state'
            button.click()
            button = self.page.locator('#accept-confirm')
        with self.page.expect_response(lambda response: response.url == self.server.url + endpoint and response.request.method == 'POST') as event:
            button.click()
        response = event.value
        body = response.json()
        assert response.status == 200 and body['ok'], body
        expect(self.page.locator('#main')).to_have_attribute('aria-busy', 'false')
        if body.get('battle_report'):
            # The replay is a modal view of the already-settled report; close it so later clicks stay reachable.
            expect(self.page.locator('#battle-replay')).to_be_visible()
            self.page.locator('#replay-skip').click()
            expect(self.page.locator('#replay-result')).to_be_visible()
            self.page.locator('#replay-close').click()
            expect(self.page.locator('#battle-replay')).to_be_hidden()
        return body

    def legacy(self, command, **params):
        key = command + ':' + json.dumps(params, ensure_ascii=False, separators=(',', ':'))
        button = self.page.locator('[data-action-key=' + json.dumps(key) + ']')
        group = button.evaluate('(b) => b.closest(".action-group")?.id || null')
        if group and not button.is_visible():
            self.page.locator('[data-group=' + json.dumps(group.removeprefix('group-')) + ']').click()
        reveal(button)
        return self.click_write(button)

    def visit(self, page_id):
        before = self.server.snapshot()
        self.page.locator('[data-world-page=' + json.dumps(page_id) + ']').click()
        expect(self.page.locator('[data-world-page=' + json.dumps(page_id) + ']')).to_have_attribute('aria-pressed', 'true')
        show_all = self.page.locator('#world-actions-show-all')
        if show_all.count() and show_all.is_visible():
            show_all.click()
        assert_one_screen(self.page, page_id)
        assert self.server.snapshot() == before, 'navigation advanced game or simulation'
        self.visited_pages.add(page_id)

    def action(self, command, **params):
        if command == 'world_enter' and not self.server.snapshot()['state']['world']['active']:
            return self.legacy(command, **params)
        candidates = [(entry, action) for entry in self.server.snapshot()['view']['world']['pages']
                      for action in entry['actions'] if action['id'] == command
                      and all(params.get(key) == value for key, value in action['params'].items())
                      and set(params) <= set(action['params']) | {field['name'] for field in action.get('fields', [])}]
        assert len(candidates) == 1, ('ambiguous/missing player-facing action', command, params)
        entry, action = candidates[0]
        self.visit(entry['id'])
        target_params = json.dumps(action['params'], ensure_ascii=False, separators=(',', ':'))
        selector = '.world-submit[data-action=' + json.dumps(command) + '][data-params=' + json.dumps(target_params, ensure_ascii=False) + ']'
        button = self.page.locator(selector)
        reveal(button)
        details = button.locator('xpath=ancestor::details')
        if details.count() and not details.get_attribute('open'):
            details.locator('summary').click()
        form = button.locator('xpath=ancestor::form')
        for field in action.get('fields', []):
            if field['name'] not in params:
                assert not field['required']
                continue
            element = form.locator('[name=' + json.dumps(field['name']) + ']')
            if field['type'] == 'select':
                element.select_option(str(params[field['name']]))
            else:
                element.fill(str(params[field['name']]))
            self.used_fields.add(field['type'])
        result = self.click_write(button, confirm=bool(action.get('confirm')))
        self.used_actions.add(command)
        return result


def main():
    artifacts = ROOT / 'artifacts' / 'world-qa'
    artifacts.mkdir(parents=True, exist_ok=True)
    server = Server(live=True)
    report = {'passed': False, 'page_errors': [], 'console_errors': [], 'failed_requests': [], 'http_errors': []}
    try:
        server.start()
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1365, 'height': 900})
            page.on('pageerror', lambda error: report['page_errors'].append(str(error)))
            page.on('console', lambda message: report['console_errors'].append(message.text) if message.type == 'error' else None)
            page.on('requestfailed', lambda request: report['failed_requests'].append(request.url))
            page.on('response', lambda response: report['http_errors'].append([response.status, response.url]) if response.status >= 400 else None)
            page.goto(server.url)
            expect(page.locator('#creation')).to_be_visible()
            page.locator('#mode').select_option('free')
            page.locator('#name').fill('凡界实玩QA')
            driver = BrowserWorldDriver(page, server)
            driver.click_write(page.locator('#create-button'), '/api/new-game')
            baseline_route(server.snapshot, driver.legacy)
            driver.action('world_enter')
            planner = WorldPlanner(server.snapshot, driver.action)
            for entry in server.snapshot()['view']['world']['pages']:
                driver.visit(entry['id'])
                page.screenshot(path=str(artifacts / (entry['id'] + '.png')), full_page=True)
            # Filled below with the frozen legal full-world route; a partial
            # framework must fail rather than claim full-world completion.
            planner.full_progress()
            assert server.snapshot()['state']['world']['ending']
            assert len(driver.visited_pages) == 11
            # Close pages that are optional to the main progression: estate,
            # NPC arena/season and achievement/title are actual interactions.
            planner.cost({'ore': 4, 'crystal': 1})
            planner.perform('world_home', facility='workshop')
            planner.repeat_until(lambda: planner.world()['home_storage']['workshop'] > 0,
                                 lambda: planner.perform('world_wait'), budget=5)
            planner.perform('world_home_collect', facility='workshop')
            planner.perform('world_achievement', kind='craft', tier=1)
            planner.perform('world_title', title='artisan')
            planner.perform('world_season_join')
            for _ in range(3):
                planner.rest()
                planner.perform('world_season_fight')
                planner.win()
            planner.perform('world_season_claim')
            assert planner.world()['arena']['current']['claimed']
            # Real non-default market inputs, beyond the first action per page.
            planner.perform('world_buy', item='ore', quantity=3)
            planner.perform('world_sell', item='ore', quantity=2)
            world_before = server.snapshot()
            saved = driver.click_write(page.locator('#save-button'), '/api/save')
            planner.perform('world_gather', item='wood')
            restored = driver.click_write(page.locator('#load-button'), '/api/load', confirm=True)
            assert restored['state'] == saved['state'] == world_before['state']
            page.reload()
            expect(page.locator('[data-world-page="world"]')).to_be_visible()
            assert server.snapshot()['state'] == restored['state']
            page.set_viewport_size({'width': 320, 'height': 740})
            for entry in server.snapshot()['view']['world']['pages']:
                driver.visit(entry['id'])
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), ('320px overflow', entry['id'])
                page.screenshot(path=str(artifacts / ('mobile-' + entry['id'] + '.png')), full_page=True)
            # Numeric constraints must prevent a malformed write from real form.
            driver.visit('market')
            forms = page.locator('form[data-world-action]')
            numeric_form = None
            for index in range(forms.count()):
                candidate = forms.nth(index)
                if candidate.locator('input[type="number"]').count() and candidate.locator('.world-submit').is_enabled():
                    numeric_form = candidate
                    break
            assert numeric_form is not None, 'no reachable numeric world form'
            reveal(numeric_form)
            details = numeric_form.locator('xpath=ancestor::details')
            if details.count() and not details.get_attribute('open'):
                details.locator('summary').click()
            field = numeric_form.locator('input[type="number"]').first
            field.fill('0')
            before = server.snapshot()
            numeric_form.locator('.world-submit').click()
            assert field.evaluate('(node) => !node.validity.valid'), 'zero should violate projected numeric range'
            page.wait_for_timeout(150)
            assert server.snapshot() == before, 'invalid form wrote state'
            report.update(visited_pages=sorted(driver.visited_pages), used_actions=sorted(driver.used_actions), used_fields=sorted(driver.used_fields))
            assert not any(report[key] for key in ['page_errors', 'console_errors', 'failed_requests', 'http_errors']), report
            report['passed'] = True
            browser.close()
    except Exception as exc:
        report['failure'] = repr(exc)
        raise
    finally:
        server.close()
        (artifacts / 'browser-world-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
