"""Executable 16-action real-HTTP projection audit in controlled valid contexts.

Ownership/pending fixtures expose boundary UI entries; daily/milestone contexts
are reached by actual public actions. This is additional evidence, not gameplay
reachability proof and not counted as unittest cases.
"""
import json
import sqlite3
from tests.r3_support import ClockHTTP
from tests.support import ROOT,baseline_route, open_db

EXPECTED={'world_loot_equip','world_loot_unequip','world_loot_enhance',
    'world_loot_dismantle','world_loot_choose','world_loot_craft_treasure',
    'world_loot_quality','world_loot_exchange','world_loot_claim',
    'world_boss_enter','world_boss_claim','world_milestone_accept','world_milestone_claim',
    'world_activity_accept','world_activity_week_accept','world_activity_claim'}


def main():
    server=ClockHTTP().start()
    report={'passed':False,'coverage':{},'contexts':[]}
    def collect(context):
        snap=server.snapshot()
        report['contexts'].append(context)
        for page in snap['view']['world']['pages']:
            for a in page['actions']:
                if a['id'] not in EXPECTED:continue
                assert a['enabled'] or a['reason'],a
                assert isinstance(a['params'],dict)
                names=[]
                for field in a.get('fields',[]):
                    assert field['type'] in ['number','text','select'],field
                    names.append(field['name'])
                    assert field['name'] not in a['params'],field
                    if field['type']=='select':assert field['options'],field
                    if field['type']=='number':assert type(field['min']) is int and type(field['max']) is int and field['min']<=field['max']
                assert len(names)==len(set(names))
                report['coverage'].setdefault(a['id'],[]).append({'context':context,'page':page['id'],
                    'params':a['params'],'fields':a.get('fields',[]),'enabled':a['enabled'],'reason':a['reason']})
    try:
        server.create();baseline_route(server.snapshot,server.action);server.action('world_enter')
        with open_db(server.data/'game.db') as db:
            state=json.loads(db.execute('SELECT state FROM current WHERE id=1').fetchone()[0]);w=state['world'];r=w['r3']
            def item(uid,t,path):return dict(uid=uid,template_id=t,chapter=0,quality=0,enhance=0,effect_type=path,source_receipt='fixture:'+uid)
            r['instances']={'blade':item('blade','blade','combat'),
                'main':item('main','main_treasure','cultivation'),
                'guard':item('guard','guard_treasure','unselected')}
            r['equipped']['weapon']='blade'
            r['pending']['fixture-pending']={'source':'fixture-full-bag','item':item('pending','armor','combat'),'materials':{}}
            r['materials'].update(dust=20,enhance_material=20,boss_coin=2)
            w['inventory'].update(ore=30,wood=30,herb=30,crystal=30)
            w['xp']=405;r['growth']['balance_micro']=405000000;r['growth']['total_micro']=405000000
            db.execute('UPDATE current SET state=? WHERE id=1',(json.dumps(state),))
        collect('owned-equipped-unselected-pending + 25percent')
        previews=server.snapshot()['view']['world']['loot']['dungeons']
        for entry in previews:
            assert entry['mechanic'],entry
            if entry['difficulty']>=2:
                assert {'den':'毒','forge':'护盾','tower':'灵力'}[entry['id']] in entry['mechanic'],entry
        report['dungeon_previews_checked']=len(previews)
        server.action('world_milestone_accept',stage=0,tier=25,branch='herb')
        collect('accepted optional milestone')
        server.action('world_sect_join',sect='sword')
        server.action('world_activity_accept',project='social')
        server.action('world_sect_daily',item='herb')
        server.action('world_chat',npc='healer')
        collect('completed two-objective daily')
        server.action('world_boss_enter');server.action('world_defend');server.action('world_flee')
        collect('valid low-damage world Boss period')
        missing=sorted(EXPECTED-set(report['coverage']))
        assert not missing,('no real projected entry for new actions',missing)
        report['passed']=True
        report['covered']=len(report['coverage'])
    finally:
        folder=ROOT/'artifacts'/'r3-qa';folder.mkdir(parents=True,exist_ok=True)
        (folder/'new-action-projection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2), encoding='utf-8')
        server.close()
    print(json.dumps({'passed':report['passed'],'covered':report['covered'],'contexts':report['contexts']},ensure_ascii=False))


if __name__=='__main__':main()
