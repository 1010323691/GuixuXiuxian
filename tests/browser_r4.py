"""Real Chromium R4 seven-story/three-elite route; UTC injected, never save XP."""
import json
from playwright.sync_api import sync_playwright, expect
from tests.r3_support import ClockHTTP
from tests.support import ROOT, baseline_route
from tests.browser_world import BrowserWorldDriver, reveal
from tests.r4_route import R4Planner


def main():
    out=ROOT/'artifacts/r4-qa';out.mkdir(parents=True,exist_ok=True)
    report=dict(passed=False,checks=[],page_errors=[],console_errors=[],failed_requests=[],posts=[])
    server=ClockHTTP(live=True).start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':900})
            page.on('pageerror',lambda e:report['page_errors'].append(str(e)))
            page.on('console',lambda m:report['console_errors'].append(m.text) if m.type=='error' else None)
            page.on('requestfailed',lambda r:report['failed_requests'].append(r.url))
            page.on('request',lambda r:report['posts'].append(r.post_data_json.get('action',r.url)) if r.method=='POST' else None)
            page.goto(server.url);driver=BrowserWorldDriver(page,server)
            page.locator('#name').fill('R4独立实玩')
            driver.click_write(page.locator('#create-button'),'/api/new-game')
            baseline_route(server.snapshot,driver.legacy);driver.action('world_enter')
            expect(page.locator('#r4-credits-balance')).to_be_visible()
            # Goal buttons reference projected actions; clicking navigates without a POST.
            goal=page.locator('.r3-goal-button').first
            reveal(goal)
            before=server.snapshot()['revision'];count=len(report['posts'])
            goal.click();assert server.snapshot()['revision']==before and len(report['posts'])==count
            report['checks'].append('live story goal navigates only; initial three credits visible')
            route=R4Planner(server.snapshot,driver.action)
            checkpoints=route.first_week(server.clock)
            assert [x['claimed'] for x in checkpoints]==[4,6,7]
            assert len(route.world()['r3']['journey']['elite_wins'])==3
            report['checkpoints']=checkpoints
            report['checks'].append('real forms: seven accepted stories, crafted/used/social/secret objectives, three tactical elites, fixed chapter gear choices equipped')
            # Same ordinary repeat reward, compare browser write burden. Manual proof already exists.
            route.travel('qinglan');route.rest()
            before_posts=len(report['posts']);before_r=route.world()['r3']['drop_seq']
            route.dungeon(difficulty=1)
            manual_posts=len(report['posts'])-before_posts
            assert route.world()['r3']['drop_seq']==before_r+1
            before_posts=len(report['posts']);w=route.world();seq=w['r3']['drop_seq'];pity=w['r3']['pity']['1'];credits=w['r3']['cadence']['available'];wallet=w['wallet'];herb=w['inventory'].get('herb',0)
            route.perform('world_dungeon_sweep',dungeon='den',chapter=0,difficulty=1)
            sweep_posts=len(report['posts'])-before_posts;w=route.world()
            assert sweep_posts==1 and manual_posts>1
            assert w['r3']['drop_seq']==seq+1 and w['r3']['pity']['1']==pity+1
            assert w['r3']['cadence']['available']==credits-1 and w['wallet']-wallet==10 and w['inventory'].get('herb',0)-herb==3
            report['burden']=dict(manual_posts=manual_posts,sweep_posts=sweep_posts,scope='same ordinary reward type/one drop and pity/one credit; world.tick intentionally differs; automation time is not human effort')
            report['checks'].append('same chapter proof enables one-POST sweep with actual ordinary reward and credit/pity; manual retains many combat posts')
            for p in server.snapshot()['view']['world']['pages']:driver.visit(p['id'])
            page.screenshot(path=str(out/'r4-desktop.png'),full_page=True)
            page.set_viewport_size({'width':320,'height':780})
            for p in server.snapshot()['view']['world']['pages']:
                driver.visit(p['id']);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),p['id']
            page.screenshot(path=str(out/'r4-mobile.png'),full_page=True)
            report['checks'].append('eleven actual pages desktop/320px no horizontal overflow')
            assert not report['page_errors'] and not report['console_errors'] and not report['failed_requests'],report
            report['passed']=True;browser.close()
    finally:
        server.close();(out/'browser-r4-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2), encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
