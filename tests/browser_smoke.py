"""Run: python -m tests.browser_smoke (requires Playwright and Chromium)."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

from tests.support import ROOT, Server, baseline_route
from tests.browser_world import assert_one_screen, reveal as reveal_node


def main():
    artifacts = ROOT / 'artifacts' / 'qa'
    artifacts.mkdir(parents=True, exist_ok=True)
    report = {'checks': [], 'console_errors': [], 'page_errors': [], 'failed_requests': [], 'http_errors': []}
    server = Server(live=True)
    try:
        server.start()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                args=['--no-sandbox'])
            context = browser.new_context(viewport={'width': 1365, 'height': 900}, reduced_motion='reduce')
            page = context.new_page()
            injected = {'active': False}

            def monitor(p):
                p.on('pageerror', lambda error: report['page_errors'].append(str(error)))
                p.on('console', lambda message: report['console_errors'].append({'text': message.text, 'injected': injected['active']}) if message.type == 'error' else None)
                p.on('requestfailed', lambda request: report['failed_requests'].append({'url': request.url, 'failure': request.failure, 'injected': injected['active']}))
                p.on('response', lambda response: report['http_errors'].append({'status': response.status, 'url': response.url, 'injected': injected['active']}) if response.status >= 400 else None)

            monitor(page)
            page.goto(server.url)
            expect(page.locator('#creation')).to_be_visible()
            page.locator('#mode').select_option('free')
            page.locator('#name').fill('问道QA')

            def reveal(selector, target=page):
                group = target.locator(selector).evaluate('(button) => button.closest(".action-group")?.id || null')
                if group and not target.locator(selector).is_visible():
                    target.locator('[data-group=' + json.dumps(group.removeprefix('group-')) + ']').click()
                reveal_node(target.locator(selector))
                expect(target.locator(selector)).to_be_visible()

            def click_write(selector, endpoint, target=page):
                reveal(selector, target)
                with target.expect_response(lambda response: response.url == server.url + endpoint and response.request.method == 'POST') as received:
                    target.locator(selector).click()
                response = received.value
                body = response.json()
                assert response.status == 200, body
                expect(target.locator('#main')).to_have_attribute('aria-busy', 'false')
                return body

            click_write('#create-button', '/api/new-game')
            expect(page.locator('#character-name')).to_have_text('问道QA')
            expect(page.locator('.group-button')).to_have_count(4)
            expect(page.locator('.action-group:visible')).to_have_count(1)

            def action(command, **params):
                key = command + ':' + json.dumps(params, ensure_ascii=False, separators=(',', ':'))
                selector = '[data-action-key=' + json.dumps(key) + ']'
                body = click_write(selector, '/api/action')
                assert body['state'] == server.snapshot()['state']
                return body

            # Each write is a physical click on the player-facing action button.
            baseline_route(server.snapshot, action)
            expect(page.locator('#ending')).to_be_visible()
            expect(page.locator('#ending-text')).to_contain_text('归墟')
            page.screenshot(path=str(artifacts / 'desktop-ending.png'), full_page=True)
            report['checks'].append('real-page exact 53-action no-upgrade completion')

            saved = click_write('#save-button', '/api/save')['state']
            action('gather')
            before_cancel = server.snapshot()
            page.locator('#load-button').click()
            expect(page.locator('#confirm-dialog')).to_be_visible()
            page.locator('#cancel-confirm').click()
            expect(page.locator('#load-button')).to_be_focused()
            assert server.snapshot() == before_cancel
            page.locator('#load-button').click()
            restored = click_write('#accept-confirm', '/api/load')
            assert restored['state'] == saved
            page.reload()
            expect(page.locator('#character-name')).to_have_text('问道QA')
            expect(page.locator('#ending')).to_be_visible()
            report['checks'].append('manual save/load confirmation cancel/focus and refresh restore')

            # Another actual page remains stale; no API writes are injected.
            other = context.new_page()
            monitor(other)
            other.goto(server.url)
            expect(other.locator('#character-name')).to_have_text('问道QA')
            action('gather')
            before = server.snapshot()
            injected['active'] = True  # Expected 409 is retained in report.
            reveal('[data-action-key="gather:{}"]', other)
            with other.expect_response(lambda response: response.url.endswith('/api/action')) as conflict:
                other.locator('[data-action-key="gather:{}"]').click()
            assert conflict.value.status == 409
            expect(other.locator('#notice-text')).to_contain_text('重新')
            expect(other.locator('#main')).to_have_attribute('aria-busy', 'false')
            assert server.snapshot() == before
            injected['active'] = False
            other.close()
            report['checks'].append('two real pages: stale request rejected without mutation')

            # Commit an action but drop its response; retry must use original ID.
            before = server.snapshot()
            seen = []

            def drop_after_commit(route):
                seen.append(route.request.post_data_json)
                response = route.fetch()
                assert response.status == 200
                route.abort('failed')

            injected['active'] = True
            page.route('**/api/action', drop_after_commit, times=1)
            reveal('[data-action-key="gather:{}"]')
            page.locator('[data-action-key="gather:{}"]').click()
            expect(page.locator('#retry-button')).to_be_visible()
            expect(page.locator('#notice-text')).to_contain_text('尚未确认')
            once = server.snapshot()
            assert once['revision'] == before['revision'] + 1
            assert once['state']['herbs'] == before['state']['herbs'] + 2
            # R05: B starts while A has an unresolved request. Its own write must
            # neither inherit A's pending payload nor overwrite/clear A's retry.
            independent = context.new_page()
            monitor(independent)
            independent.goto(server.url)
            expect(independent.locator('#character-name')).to_have_text('问道QA')
            expect(independent.locator('#retry-button')).to_be_hidden()
            independent_action = '[data-action-key="gather:{}"]'
            reveal(independent_action, independent)
            b_result = click_write(independent_action, '/api/action', independent)
            latest = server.snapshot()
            assert latest['revision'] == once['revision'] + 1
            assert latest['state']['herbs'] == once['state']['herbs'] + 2
            assert b_result['state'] == latest['state']
            independent.close()
            page.reload()
            expect(page.locator('#retry-button')).to_be_visible()
            with page.expect_request(lambda request: request.url.endswith('/api/action')) as retry:
                retried = click_write('#retry-button', '/api/action')
            assert retry.value.post_data_json == seen[0]
            assert retried['duplicate'] is True
            assert retried['state'] == latest['state']
            assert server.snapshot()['state'] == latest['state']
            assert server.snapshot()['revision'] == latest['revision']
            assert server.snapshot()['state']['herbs'] == before['state']['herbs'] + 4
            expect(page.locator('#notice-text')).to_contain_text('已处理')
            injected['active'] = False
            report['checks'].append('response lost after commit + independent tab write + reload + identical-ID retry preserves latest state and counts once')

            # New-game cancellation preserves state; confirmed replacement clears slot.
            page.locator('#new-button').click()
            page.locator('#cancel-confirm').click()
            assert server.snapshot()['state'] == latest['state']
            page.locator('#new-button').click()
            page.locator('#new-name').fill('窄屏道友')
            page.locator('#new-mode').select_option('free')
            created = click_write('#accept-confirm', '/api/new-game')
            assert created['state']['actions_taken'] == 0 and not created['save']['exists']
            expect(page.locator('#load-button')).to_be_disabled()
            page.set_viewport_size({'width': 320, 'height': 740})
            action('cultivate')
            page.screenshot(path=str(artifacts / 'mobile-320.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'horizontal overflow at 320px'
            assert_one_screen(page, 'prologue 320px')
            buttons = page.locator('button:visible').evaluate_all('(buttons) => buttons.map(b => ({text:b.textContent,height:b.getBoundingClientRect().height}))')
            assert all(button['height'] >= 44 for button in buttons), buttons
            page.locator('[data-action-key="cultivate:{}"]').focus()
            with page.expect_response(lambda response: response.url.endswith('/api/action')):
                page.keyboard.press('Enter')
            expect(page.locator('#main')).to_have_attribute('aria-busy', 'false')
            assert server.snapshot()['state']['cultivation'] == 12
            report['checks'].append('confirmed new game clears slot; 320px layout and keyboard action')

            unexpected_console = [error for error in report['console_errors'] if not error['injected']]
            unexpected_failed = [request for request in report['failed_requests'] if not request['injected']]
            unexpected_http = [response for response in report['http_errors'] if not response['injected']]
            assert not report['page_errors'], report['page_errors']
            assert not unexpected_console, unexpected_console
            assert not unexpected_failed, unexpected_failed
            assert not unexpected_http, unexpected_http
            browser.close()
            report['passed'] = True
    except Exception as exc:
        report['passed'] = False
        report['failure'] = repr(exc)
        raise
    finally:
        server.close()
        (artifacts / 'browser-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
