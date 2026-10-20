"""Independent Chromium protocol-to-scene checks. All game state is experimental."""
import json
import re
from playwright.sync_api import sync_playwright, expect
from lab_support import ARTIFACTS,LabServer


def main():
    ARTIFACTS.mkdir(parents=True,exist_ok=True)
    report=dict(passed=False,checks=[],posts=[],errors=[],console_errors=[],failed_requests=[])
    server=LabServer().start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':1000})
            page.on('pageerror',lambda e:report['errors'].append(str(e)))
            page.on('console',lambda m:report['console_errors'].append(m.text) if m.type=='error' else None)
            page.on('requestfailed',lambda r:report['failed_requests'].append(r.url))
            page.on('request',lambda r:report['posts'].append(dict(url=r.url,body=r.post_data_json)) if r.method=='POST' else None)
            def capture_motion():
                return page.evaluate("""async()=>{const out=[];const until=performance.now()+2200;
              while(performance.now()<until){const g=document.querySelector('#air-effects g[data-flight-source="main"]');
                if(g){const b=g.getBoundingClientRect();out.push({event_id:g.dataset.eventId,x:b.x+b.width/2,y:b.y+b.height/2});}
                await new Promise(r=>setTimeout(r,16));}return out;}""")
            page.goto(server.url);expect(page.locator('#simulate')).to_be_enabled()
            page.locator('#preparation-rules summary').click()
            rules=page.locator('#preparation-rule-content')
            expect(rules).to_contain_text('18MP');expect(rules).to_contain_text('CD3');expect(rules).to_contain_text('占本拍唯一主行动')
            expect(rules.locator('dl')).to_contain_text('40');expect(rules.locator('dl')).to_contain_text('CD2')
            page.locator('input[name=build][value=burst]').check()
            for text in ['120','CD6','t2','t4']:expect(rules.locator('dl')).to_contain_text(text)
            page.locator('input[name=build][value=guard]').check()
            for text in ['90','CD4']:expect(rules.locator('dl')).to_contain_text(text)
            assert not report['posts']
            page.locator('#preparation-rules summary').click()
            report['checks'].append('server preparation metadata: 18MP/CD3, sustain40/CD2, burst120/CD6 t2/t4, shield90/CD4 and consumable main-action cost; switches zero POST')
            page.locator('#scenario').select_option('dungeon')
            page.locator('.budget-details summary').click()
            page.locator('[name=pill_budget]').fill('3');page.locator('[name=fire_budget]').fill('1')
            with page.expect_response(lambda r:r.url.endswith('/api/simulate')) as event:page.locator('#simulate').click()
            data=event.value.json();assert event.value.status==200 and data['result']['outcome']=='win'
            expect(page.locator('#timeline')).to_have_attribute('max',str(len(data['frames'])-1))
            page.locator('#arena').scroll_into_view_if_needed()
            page.locator('#timeline').evaluate('(el)=>{el.value="0";el.dispatchEvent(new Event("input",{bubbles:true}));}')
            page.locator('#play-pause').click()
            motion=capture_motion()
            assert len(motion)>=4,('no observable artifact entity flight',motion)
            xs=[m['x'] for m in motion];peak=max(range(len(xs)),key=xs.__getitem__)
            assert max(xs)-min(xs)>20 and any(x<xs[peak]-20 for x in xs[peak+1:]),('artifact did not fly outward and return',motion)
            actual_ids={e['id'] for e in data['events'] if e['source']=='main'}
            assert all(m['event_id'] in actual_ids for m in motion)
            report['treasure_motion']=motion
            if page.locator('#play-pause').inner_text()=='暂停播放':page.locator('#play-pause').click()
            page.locator('#timeline').evaluate('(el)=>{el.value="0";el.dispatchEvent(new Event("input",{bubbles:true}));}')
            page.wait_for_timeout(300)
            assert page.locator('#air-effects g[data-flight-source]').count()==0
            expect(page.locator('#arena')).to_have_attribute('data-flight','false')
            report['checks'].append('normal-speed same-shape main treasure flyer moves out and returns on real source event; seek removes old flyer, not just a beam')
            assert len(report['posts'])==1
            def seek(i):
                page.locator('#timeline').evaluate('(el,i)=>{el.value=String(i);el.dispatchEvent(new Event("input",{bubbles:true}));}',i)
                f=data['frames'][i]
                arena=page.locator('#arena')
                expect(arena).to_have_attribute('data-frame-tick',str(f['tick']))
                expect(arena).to_have_attribute('data-simulation-id',data['simulation_id'])
                event_id=arena.get_attribute('data-event-id')
                if event_id:
                    e=next(e for e in f['events'] if e['id']==event_id)
                    expect(arena).to_have_attribute('data-current-source',e['source'])
                    expect(arena).to_have_attribute('data-current-target',e['target'])
                    expect(arena).to_have_attribute('data-event-tick',str(e['tick']))
                    if e['source'] in ['main','secondary']:
                        expect(page.locator('[data-treasure="'+e['source']+'"]')).to_have_class(re.compile('source-active'))
                        assert not page.locator('[data-actor=player]').evaluate('(el)=>el.classList.contains("source-active")')
                    if e['type']=='shield_absorb':expect(arena).to_have_attribute('data-effect','absorb')
                expect(page.locator('#decision-reason')).to_have_text(f['decision_reason'])
                expect(page.locator('#player-hp')).to_have_text(f"气血 {f['player']['hp']} / {f['player']['max_hp']}")
                expect(page.locator('#player-mp')).to_have_text(f"灵力 {f['player']['mp']} / {f['player']['max_mp']}")
                expect(page.locator('#enemy-hp')).to_have_text(f"气血 {f['enemy']['hp']} / {f['enemy']['max_hp']}")
                if f['enemy']['hp']>0:expect(page.locator('#enemy-intent')).to_contain_text(f['enemy']['intent'])
                else:expect(page.locator('#enemy-intent')).to_contain_text('结束')
                for c in f['cooldowns']:
                    el=page.locator(f'[data-skill="{c["id"]}"] .skill-copy small')
                    if el.count():expect(el).to_have_text(f"冷却余 {c['remaining']} 拍" if c['remaining'] else '冷却就绪')
            for actor in ['player','enemy']:expect(page.locator('[data-actor="'+actor+'"]')).to_be_visible()
            for slot,mode in [('main','sustain'),('secondary','guard')]:expect(page.locator('[data-treasure="'+slot+'"]')).to_have_attribute('data-mode',mode)
            absorb_index=next(i for i,f in enumerate(data['frames']) if any(e['type']=='shield_absorb' for e in f['events']))
            seek(absorb_index)
            expect(page.locator('#arena')).to_have_attribute('data-effect','absorb')
            page.evaluate('scrollTo(0,0)');page.screenshot(path=str(ARTIFACTS/'air-guard-detail.png'),full_page=True)
            seek(0);page.wait_for_timeout(500)
            assert page.locator('#arena').get_attribute('data-event-id') is None
            assert page.locator('.source-active').count()==0
            seek(1);expect(page.locator('#arena')).to_have_attribute('data-effect','sustain')
            for i in [0,1,len(data['frames'])//2,len(data['frames'])-1]:seek(i)
            report['checks'].append('flying identity seals and independent sustain/guard treasures; actual absorb source/event/reason match current frame, seek clears old effects')
            expect(page.locator('#result')).to_be_visible()
            for node in [1,2]:expect(page.locator(f'#route button[data-node="{node}"]')).to_have_attribute('aria-label',re.compile('已通过'))
            # Natural last-frame completion must not cancel its later main-treasure event.
            final_main={e['id'] for e in data['frames'][-1]['events'] if e['source']=='main' and e['type']=='damage'}
            assert final_main,'chosen public route must exercise final-hit main treasure'
            seek(len(data['frames'])-2);page.locator('#play-pause').click()
            last_motion=capture_motion()
            last_motion=[m for m in last_motion if m['event_id'] in final_main]
            assert len(last_motion)>=4,('natural end swallowed final treasure flight',last_motion)
            xs=[m['x'] for m in last_motion];peak=max(range(len(xs)),key=xs.__getitem__)
            assert max(xs)-min(xs)>20 and any(x<xs[peak]-20 for x in xs[peak+1:]),('final flyer never returned',last_motion)
            report['final_treasure_motion']=last_motion
            report['checks'].append('natural final frame actually plays its later main-treasure hit and return before stopping; no extra simulation')
            summary=page.locator('#metrics').inner_text()
            page.locator('.battle-journal summary').click();assert page.locator('#event-log li').count()>0
            report['checks'].append('real HTTP three-node win; timeline HP/MP/intent/CD matches authoritative frames; cleared route and readable event log')
            count=len(report['posts'])
            page.locator('#replay').click();page.locator('#play-pause').click()
            frame=page.locator('#timeline').input_value();page.wait_for_timeout(1500);assert page.locator('#timeline').input_value()==frame
            page.locator('#speed').click()
            expect(page.locator('#speed')).to_have_text('速度 2×')
            page.locator('#play-pause').click();page.wait_for_timeout(1000);page.locator('#play-pause').click()
            assert int(page.locator('#timeline').input_value())>=1
            page.locator('#skip').click();assert page.locator('#metrics').inner_text()==summary
            page.locator('#route button[data-node="1"]').click();seek(0)
            page.locator('#skip').focus();page.keyboard.press('Enter');expect(page.locator('#result')).to_be_visible()
            assert len(report['posts'])==count
            report['checks'].append('pause stops cursor; replay/speed/route/skip and keyboard only play same trace, zero extra POST and same result')
            page.evaluate('scrollTo(0,0)');page.wait_for_timeout(250)
            page.screenshot(path=str(ARTIFACTS/'air-desktop.png'),full_page=True)
            page.set_viewport_size({'width':320,'height':780});page.emulate_media(reduced_motion='reduce')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert page.locator('#player-hp-fill').evaluate('(el)=>getComputedStyle(el).transitionDuration')=='0s'
            seek(absorb_index);expect(page.locator('#arena')).to_have_attribute('data-effect','absorb')
            page.evaluate('scrollTo(0,0)');page.screenshot(path=str(ARTIFACTS/'air-guard-mobile.png'),full_page=True)
            page.locator('#skip').click();page.locator('#replay').click()
            page.wait_for_timeout(1600)
            assert page.locator('#air-effects animateMotion').count()==0
            page.locator('#skip').click()
            assert page.locator('#metrics').inner_text()==summary
            page.evaluate('scrollTo(0,0)');page.wait_for_timeout(250)
            page.screenshot(path=str(ARTIFACTS/'air-mobile.png'),full_page=True)
            # New run is the only additional POST; old trace timer must not repaint it.
            details=page.locator('#preparation-details')
            if details.get_attribute('open') is None:details.locator('summary').first.click()
            page.locator('#scenario').select_option('boss');page.locator('input[name=build][value=burst]').check()
            page.locator('#strategy').select_option('aggressive')
            page.locator('[name=npc]').check()
            details.locator('summary').first.click()
            with page.expect_response(lambda r:r.url.endswith('/api/simulate')) as event:page.locator('#quick-simulate').click()
            boss=event.value.json();assert boss['result']['ticks']<=12
            assert boss['result']['outcome'] in ['window','loss'] and boss['frames'][-1]['enemy']['hp']>0
            page.locator('#timeline').evaluate('(el)=>{el.value="0";el.dispatchEvent(new Event("input",{bubbles:true}));}')
            expect(page.locator('[data-treasure=main]')).to_have_attribute('data-charge','2')
            page.locator('#timeline').evaluate('(el)=>{el.value="3";el.dispatchEvent(new Event("input",{bubbles:true}));}')
            expect(page.locator('#arena')).to_have_attribute('data-effect','burst')
            expect(page.locator('#arena')).to_have_attribute('data-current-source','main')
            for slot in ['main','secondary']:expect(page.locator('[data-treasure="'+slot+'"]')).to_have_attribute('data-mode','burst')
            assert page.locator('#arena').get_attribute('data-event-id') in [e['id'] for e in boss['frames'][3]['events']]
            page.evaluate('scrollTo(0,0)');page.screenshot(path=str(ARTIFACTS/'air-burst-detail.png'),full_page=True)
            page.locator('#skip').click()
            expect(page.locator('#metrics')).to_contain_text('个人评分封顶值')
            expect(page.locator('#boss-score')).to_be_visible()
            expect(page.locator('#boss-personal')).to_have_text(str(boss['metrics']['player_damage']))
            expect(page.locator('#boss-npc')).to_have_text(str(boss['metrics']['npc_damage']))
            expect(page.locator('#boss-window')).to_contain_text(str(boss['result']['ticks'])+' / 12')
            expected=boss['frames'][-1]['enemy']
            expect(page.locator('#enemy-hp')).to_have_text(f"气血 {expected['hp']} / {expected['max_hp']}")
            last=page.locator('#player-hp').inner_text();page.wait_for_timeout(1500)
            expect(page.locator('#player-hp')).to_have_text(last)
            page.evaluate('scrollTo(0,0)');page.wait_for_timeout(250)
            page.screenshot(path=str(ARTIFACTS/'air-boss-mobile.png'),full_page=True)
            page.set_viewport_size({'width':1440,'height':1000})
            page.evaluate('scrollTo(0,0)');page.wait_for_timeout(250)
            page.screenshot(path=str(ARTIFACTS/'air-boss-desktop.png'),full_page=True)
            assert len(report['posts'])==count+1
            assert all(x['url']==server.url+'/api/simulate' for x in report['posts'])
            report['checks'].append('320px reduced-motion and new Boss run; old timer cannot repaint, twelve-opportunity result; no formal API requests')
            assert not report['errors'] and not report['console_errors'] and not report['failed_requests'],report
            report['passed']=True;browser.close()
    finally:
        server.close();(ARTIFACTS/'air-browser-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
