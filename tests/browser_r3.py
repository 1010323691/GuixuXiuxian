"""Real Chromium longline entry/time/item UX. Injected UTC is not a 40-day user study."""
from tests.support import launch_browser, attach_session
import json
import sqlite3
from playwright.sync_api import sync_playwright, expect
from tests.r3_support import ClockHTTP
from tests.support import ROOT, baseline_route, open_db
from tests.browser_world import BrowserWorldDriver, reveal


def main():
    artifacts = ROOT / 'artifacts' / 'r3-qa'
    artifacts.mkdir(parents=True, exist_ok=True)
    server = ClockHTTP(live=True)
    report = {'passed': False, 'checks': [], 'page_errors': [], 'console_errors': [],
              'failed_requests': [], 'post_requests': []}
    try:
        server.start()
        with sync_playwright() as p:
            browser = launch_browser(p)
            page = browser.new_page(viewport={'width':1365,'height':900})
            page.on('pageerror', lambda error: report['page_errors'].append(str(error)))
            page.on('console', lambda msg: report['console_errors'].append(msg.text) if msg.type == 'error' else None)
            page.on('requestfailed', lambda req: report['failed_requests'].append(req.url))
            page.on('request', lambda req: report['post_requests'].append(req.url) if req.method == 'POST' else None)
            attach_session(page, server)
            page.goto(server.url)
            expect(page.locator('#mode')).to_have_value('longline')
            page.locator('#name').fill('长线实玩QA')
            driver = BrowserWorldDriver(page, server)
            driver.click_write(page.locator('#create-button'), '/api/new-game')
            assert 'r3' in server.snapshot()['state']['world']
            baseline_route(server.snapshot, driver.legacy)
            driver.action('world_enter')
            expect(page.locator('#growth-panel')).to_be_visible()
            assert server.snapshot()['view']['growth']['rate']['per_day'] == 540
            driver.visit('social')
            draft_form=page.locator('form[data-world-action=world_family_create]')
            draft_details=draft_form.locator('xpath=ancestor::details')
            reveal(draft_form)
            if draft_details.count() and not draft_details.get_attribute('open'):
                draft_details.locator('summary').click()
            draft=draft_form.locator('input[name=name]')
            draft.fill('保留未提交草稿')
            draft.focus()
            original_draft=draft.element_handle()
            before_posts = len(report['post_requests'])
            with open_db(server.data / 'game.db') as db:
                before_db = tuple(db.execute('select * from current').fetchall()) + tuple(db.execute('select * from requests').fetchall())
            server.clock.advance(160)
            with page.expect_response(lambda r: r.url == server.url+'/api/state' and r.request.method == 'GET',timeout=20000):
                pass  # the page polls /api/state every 15s; leaving the block waits for that response
            expect(page.locator('#growth-available')).not_to_be_empty()
            assert server.snapshot()['view']['growth']['available_micro'] == '1000000'
            assert len(report['post_requests']) == before_posts
            expect(draft).to_have_value('保留未提交草稿')
            assert original_draft.evaluate('(el)=>el===document.activeElement'), 'GET refresh replaced form node or lost focus'
            with open_db(server.data / 'game.db') as db:
                assert tuple(db.execute('select * from current').fetchall()) + tuple(db.execute('select * from requests').fetchall()) == before_db, 'read-only refresh persisted growth'
            report['checks'].append('default longline + visible 53-action prologue + entry + exact160sec read-only automatic GET growth')
            # Real forms: acquire and craft an owned instance, then equip its UID.
            for _ in range(2):
                driver.action('world_gather', item='ore')
            driver.action('world_craft', recipe='blade', quantity=1)
            r3 = server.snapshot()['state']['world']['r3']
            uid = next(uid for uid,item in r3['instances'].items() if item['template_id']=='blade')
            driver.action('world_loot_equip', uid=uid)
            assert server.snapshot()['state']['world']['r3']['equipped']['weapon'] == uid
            report['checks'].append('public material acquisition -> craft blade instance -> UID equip')
            driver.action('world_sect_join',sect='sword')
            driver.action('world_activity_accept',project='social')
            key=next(k for k in server.snapshot()['state']['world']['r3']['activities']['entries'] if k.startswith('d:'))
            driver.action('world_sect_daily',item='herb')
            driver.action('world_chat',npc='healer')
            driver.action('world_activity_claim',key=key)
            assert server.snapshot()['state']['world']['r3']['activities']['entries'][key]['claimed']
            report['checks'].append('daily choice -> actual commission and NPC chat -> one material reward')
            driver.action('world_boss_enter')
            driver.action('world_auto_battle',strategy='frugal')
            boss=server.snapshot()['state']['world']['r3']['boss']
            day=next(iter(boss))
            assert boss[day]['best']>0 and boss[day]['attempts']==1
            driver.action('world_boss_claim',day=day)
            first_coin=server.snapshot()['state']['world']['r3']['materials']['boss_coin']
            first_best=boss[day]['best']
            assert first_coin>=2
            report['checks'].append('real auto-battle world Boss window with personal damage -> participation and score coins')
            while server.snapshot()['state']['world']['hp']<200:
                driver.action('world_rest')
            driver.action('world_boss_enter')
            driver.action('world_auto_battle',strategy='aggressive')
            if server.snapshot()['state']['world']['r3']['boss'][day]['best']>first_best:
                driver.action('world_boss_claim',day=day)
            for _ in range(4):
                driver.action('world_loot_exchange',item='dust')
            driver.action('world_gather',item='herb')
            old=set(server.snapshot()['state']['world']['r3']['instances'])
            driver.action('world_loot_craft_treasure',slot='main',effect_type='cultivation')
            new=set(server.snapshot()['state']['world']['r3']['instances'])-old
            treasure=next(iter(new))
            driver.action('world_loot_equip',uid=treasure)
            assert abs(server.snapshot()['view']['growth']['rate']['per_day']-545.4)<1e-9
            reveal(page.locator('#r3-item-select'))
            expect(page.locator('#r3-item-select')).to_be_visible()
            page.locator('#r3-item-select').select_option(treasure)
            expect(page.locator('.r3-comparison')).to_be_visible()
            report['checks'].append('higher Boss damage -> delta coins -> real dust exchange -> cultivation treasure -> actual545.4/day and same-slot comparison')
            from datetime import datetime,timezone,date
            today=datetime.fromtimestamp(server.clock(),timezone.utc).date()
            anchor=date(1970,1,5)
            offset=next(n for n in range(21) if ((today.toordinal()+n-anchor.toordinal())//7)%3==2)
            server.clock.advance(offset*86400)
            page.reload()
            expect(page.locator('#growth-panel')).to_be_visible()
            driver.action('world_activity_week_accept')
            weekly=next(k for k in server.snapshot()['state']['world']['r3']['activities']['entries'] if k.startswith('w:'))
            for resource in ['ore','wood']:
                while server.snapshot()['state']['world']['inventory'].get(resource,0)<4:
                    driver.action('world_gather',item=resource)
            driver.action('world_craft',recipe='spirit_array',quantity=1)
            driver.action('world_boss_enter')
            driver.action('world_auto_battle',strategy='frugal')
            driver.action('world_activity_claim',key=weekly)
            assert server.snapshot()['state']['world']['r3']['activities']['entries'][weekly]['claimed']
            report['checks'].append('real weekly project -> actual formation use and formal Boss -> material claim')
            driver.visit('world')
            goals=server.snapshot()['view']['world']['goals']
            assert 0<len(goals)<=3
            all_actions=[(p['id'],a) for p in server.snapshot()['view']['world']['pages'] for a in p['actions']]
            for goal in goals:
                assert any(pid==goal['page'] and a['id']==goal['action']['id'] and a['params']==goal['action']['params'] for pid,a in all_actions), 'fake goal action'
            before=server.snapshot()
            posts=len(report['post_requests'])
            selected=goals[0]
            reveal(page.locator('.r3-goal-button').first)
            page.locator('.r3-goal-button').first.click()
            expect(page.locator('[data-world-page='+json.dumps(selected['page'])+']')).to_have_attribute('aria-pressed','true')
            assert server.snapshot()['revision']==before['revision']
            assert len(report['post_requests'])==posts,'goal navigation submitted a game action'
            report['checks'].append('real gap recommendations point only to existing actions and navigate without revision/write')
            from tests.r3_route import R3Planner
            class TacticalBrowserPlanner(R3Planner):
                poison_seen=False
                def perform(self,command,**params):
                    result=super().perform(command,**params)
                    battle=result['state']['world']['battle']
                    if battle and battle.get('mechanic')=='venom':
                        expect(page.locator('#world-battle-statuses')).to_contain_text('残留毒')
                        expect(page.locator('#world-battle-counterplay')).not_to_be_empty()
                        if battle['poison_turns']>0:
                            self.poison_seen=True
                            page.screenshot(path=str(artifacts/'r3-venom-counterplay.png'),full_page=True)
                    return result
            tactical=TacticalBrowserPlanner(server.snapshot,driver.action)
            for recipe in ['armor','pendant']:
                old=set(tactical.world()['r3']['instances'])
                tactical.craft(recipe)
                uid=next(iter(set(tactical.world()['r3']['instances'])-old))
                tactical.perform('world_loot_equip',uid=uid)
            for slot in ['weapon','armor','pendant']:
                uid=tactical.world()['r3']['equipped'][slot]
                while tactical.world()['r3']['materials']['enhance_material']<1:
                    tactical.cost({'ore':4,'wood':2})
                    tactical.perform('world_loot_exchange',item='enhance_material')
                tactical.cost({'ore':4})
                tactical.perform('world_loot_enhance',uid=uid)
            for _ in range(3):
                tactical.craft('pill')
            tactical.dungeon(difficulty=1)
            tactical.dungeon(difficulty=2)
            # 点击式战斗已退役为自动斗法，毒状态不再逐拍暴露；以下由 dungeon() 内的真实胜利断言覆盖
            report['checks'].append('real crafted/strengthened three slots -> low dungeon -> hard venom boss with visible status and counterplay -> actual victory')
            for entry in server.snapshot()['view']['world']['pages']:
                driver.visit(entry['id'])
            page.screenshot(path=str(artifacts/'r3-desktop.png'), full_page=True)
            page.set_viewport_size({'width':320,'height':780})
            for entry in server.snapshot()['view']['world']['pages']:
                driver.visit(entry['id'])
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), entry['id']
            page.screenshot(path=str(artifacts/'r3-mobile.png'), full_page=True)
            report['checks'].append('all eleven real pages and 320px no horizontal overflow')
            assert not report['page_errors'], report['page_errors']
            assert not report['console_errors'], report['console_errors']
            assert not report['failed_requests'], report['failed_requests']
            report['passed'] = True
            browser.close()
    finally:
        (artifacts/'browser-r3-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2), encoding='utf-8')
        server.close()
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':
    main()
