"""R4 first-week accepted story progress and manual-clear proof."""
from . import gameplay_config as G


def initial_state():
    return {'version':1,'stories':{},'elite_wins':[],'manual_clears':[]}


def migrate(w):
    if 'journey' not in w['r3']:
        w['r3']['journey']=initial_state()
        w['r3']['journey']['manual_clears']=list(w['dungeon_wins'])
    return w


def validate(state):
    w=state['world'];j=w.get('r3',{}).get('journey')
    if j is None:return
    if not isinstance(j,dict) or set(j)!={'version','stories','elite_wins','manual_clears'} or type(j['version']) is not int or j['version']!=1:raise ValueError('首周旅程无效')
    if not isinstance(j['stories'],dict):raise ValueError('故事记录无效')
    for key in ['elite_wins','manual_clears']:
        if not isinstance(j[key],list) or any(not isinstance(v,str) for v in j[key]) or len(j[key])!=len(set(j[key])):raise ValueError('旅程战果无效')
    if any(v not in G.ELITES for v in j['elite_wins']):raise ValueError('精英战果无效')
    if any(G.ELITES[v]['story'] not in j['stories'] for v in j['elite_wins']):raise ValueError('精英未接取故事')
    if any(v not in w['dungeon_wins'] for v in j['manual_clears']):raise ValueError('手战证明缺少真实通关记录')
    catalog={s['id']:s for s in G.STORIES}
    for id,record in j['stories'].items():
        if id not in catalog or not isinstance(record,dict) or set(record)!={'progress','claimed'} or type(record['claimed']) is not bool:raise ValueError('故事权益无效')
    for id,record in j['stories'].items():
        story=catalog[id]
        if story['previous'] and not j['stories'].get(story['previous'],{}).get('claimed'):raise ValueError('故事前置未领奖')
        if w['stage']<story['min_stage']:raise ValueError('故事境界前置无效')
        if not isinstance(record['progress'],list) or len(record['progress'])!=len(catalog[id]['objectives']) or any(type(n) is not int or n<0 or n>o['amount'] for n,o in zip(record['progress'],catalog[id]['objectives'])):raise ValueError('故事进度无效')
        if record['claimed'] and any(n<o['amount'] for n,o in zip(record['progress'],story['objectives'])):raise ValueError('未完成故事不能领奖')
        for n,o in zip(record['progress'],story['objectives']):
            if o['kind']=='elite' and bool(n)!=(o['target'] in j['elite_wins']):raise ValueError('精英进度与战果不符')
        if story.get('equipment_reward'):
            source='story:'+w['r3']['profile_id']+':'+id
            receipts=[r for r in w['r3']['receipts'] if r['source']==source]
            if len(receipts)!=int(record['claimed']):raise ValueError('故事装备权益凭证无效')
            gear=story['equipment_reward']
            for receipt in receipts:
                if receipt['template'] not in G.STORY_RULES['equipment_choices'] or receipt['quality']!=gear['quality']:raise ValueError('故事装备奖品不符')
                item=w['r3']['instances'].get(receipt['uid'])
                if item and item['chapter']!=gear['chapter']:raise ValueError('故事装备章节不符')



def reason(w,story):
    j=w['r3'].get('journey',initial_state())
    if story['previous'] and not j['stories'].get(story['previous'],{}).get('claimed'):return '需先领取前段故事奖励。'
    if w['stage']<story['min_stage']:return '需达到'+__import__('game.world_config',fromlist=['STAGES']).STAGES[story['min_stage']]['name']+'。'
    return ''


def handle(w,action,p,events):
    from . import loot
    if not action.startswith(('world_story_','world_elite_')):return False
    j=w['r3'].setdefault('journey',initial_state())
    if action=='world_elite_enter':
        e=G.ELITES.get(p['elite'])
        if e is None:loot._bad('未知支线精英。')
        record=j['stories'].get(e['story'])
        if not record or record['claimed']:loot._fail('需先接取对应未领奖故事。')
        if p['elite'] in j['elite_wins']:loot._fail('本故事精英已经战胜，请完成其余目标。')
        if w['region']!=e['region'] or w['stage']<e['min_stage']:loot._fail('请达到境界并前往精英所在地。')
        if w['dungeon'] or w['exploration']:loot._fail('请先结束探索。')
        from . import world
        world._start(w,'elite',p['elite'],stage=e['chapter']);events.append(e['description']);return True
    story=next((s for s in G.STORIES if s['id']==p['story']),None)
    if story is None:loot._bad('未知故事。')
    id=story['id'];record=j['stories'].get(id)
    if action=='world_story_accept':
        if record:loot._fail('故事已接取，不会重复重置。')
        blocked=reason(w,story)
        if blocked:loot._fail(blocked)
        j['stories'][id]={'progress':[0]*len(story['objectives']),'claimed':False};events.append('接取'+story['name']+'，只记录此后的真实行动。');return True
    if action!='world_story_claim':loot._bad('未知故事行动。')
    if not record or record['claimed'] or any(n<o['amount'] for n,o in zip(record['progress'],story['objectives'])):loot._fail('故事尚未完成或已经领奖。')
    source='story:'+w['r3']['profile_id']+':'+id
    gear=story.get('equipment_reward')
    if gear:
        if p.get('item') not in G.STORY_RULES['equipment_choices']:loot._bad('请选择灵刃、玄甲或灵佩。')
        loot._new_instance(w,p['item'],gear['chapter'],gear['quality'],source)
    loot._grant_materials(w,story['reward'],source)
    record['claimed']=True;events.append(story['name']+'奖励已完整入包或暂存，不消耗资格/保底。');return True


def observe(before,w,action,p):
    if 'journey' not in w['r3']:return
    # Match only committed state transitions. Newly accepted stories do not count their acceptance.
    b=before['r3'];a=w['r3'];j=a['journey']
    completed=[v for k,v in a['runs'].items() if v['completed'] and not b['runs'].get(k,{}).get('completed')]
    for story in G.STORIES:
        record=j['stories'].get(story['id'])
        if not record or record['claimed'] or story['id'] not in b.get('journey',{}).get('stories',{}):continue
        for i,o in enumerate(story['objectives']):
            kind=o['kind'];target=o['target'];delta=0
            if kind=='craft':delta=max(0,a['crafted'][target]-b['crafted'][target])
            elif kind=='use':delta=max(0,a['used'][target]-b['used'][target])
            elif kind=='dungeon':delta=len(completed)
            elif kind=='dungeon_difficulty':delta=sum(v['difficulty']>=2 and v.get('manual',True) for v in completed)
            elif kind=='secret':delta=max(0,a['secret_count']-b['secret_count'])
            elif kind=='elite':delta=int(target in j['elite_wins'] and target not in b.get('journey',{}).get('elite_wins',[]))
            elif kind=='social':delta=int(action in {'world_chat','world_gift','world_consult'})
            elif kind=='commission':delta=max(0,a['daily_count']-b['daily_count'])
            elif kind=='boss':
                for day,period in a['boss'].items():
                    old=b['boss'].get(day,{}).get('runs',{})
                    delta+=sum(v['settled'] and not old.get(k,{}).get('settled') and v['commands']>0 and v['damage']>0 for k,v in period['runs'].items())
            record['progress'][i]=min(o['amount'],record['progress'][i]+delta)


def project(state,view,add):
    from . import loot,world_config as C
    w=state['world'];j=w['r3'].get('journey',initial_state());layers=[];elites=[]
    quests=next(p for p in view['pages'] if p['id']=='quests')
    for story in G.STORIES:
        id=story['id'];record=j['stories'].get(id);blocked=reason(w,story)
        done=bool(record and all(n>=o['amount'] for n,o in zip(record['progress'],story['objectives'])))
        status='已领奖' if record and record['claimed'] else '可领奖' if done else '进行中' if record else '未解锁' if blocked else '可接取'
        progress=[{'label':o['label'],'value':'%d / %d'%((record['progress'][i] if record else 0),o['amount'])} for i,o in enumerate(story['objectives'])]
        reward='、'.join(loot.material_name(k)+str(n) for k,n in story['reward'].items())
        gear=story.get('equipment_reward')
        if gear:reward='自选第%d章%s灵刃/玄甲/灵佩1件'%(gear['chapter'],loot.R.QUALITIES[gear['quality']]['name'])
        action={'id':'world_story_claim' if record else 'world_story_accept','params':{'story':id}}
        layers.append({'id':id,'title':story['name'],'recommended_day':story['recommended_day'],'unlock':blocked or '实际前置已满足；建议日不是日期锁','status':status,'objectives':progress,'rewards':reward,'action':action})
        quests['sections'].append({'id':'r4_story:'+id,'title':story['name']+' · '+status,'body':story['description']+' 奖励：'+reward,'rows':progress})
        if not record:add('quests','world_story_accept','接取'+story['name'],'免费','仅记录接取后的真实行动；永久可补做',{'story':id},blocked)
        elif not record['claimed']:
            fields=[{'name':'item','label':'自选器物','type':'select','required':True,'options':[{'value':v,'label':loot.item_name(v)} for v in G.STORY_RULES['equipment_choices']]}] if gear else None
            add('quests','world_story_claim','领取'+story['name'],'一次性故事权益',reward,{'story':id},'' if done else '接取后的目标尚未完成。',fields=fields)
    for id,e in G.ELITES.items():
        record=j['stories'].get(e['story']);blocked=''
        if not record or record['claimed']:blocked='先接取对应故事。'
        elif id in j['elite_wins']:blocked='精英已战胜，继续故事其余目标。'
        elif w['stage']<e['min_stage']:blocked='境界尚不足。'
        elif w['region']!=e['region']:blocked='请前往'+C.REGIONS[e['region']]['name']+'。'
        elif w['exploration'] or w['dungeon']:blocked='先完成或撤离探索。'
        action={'id':'world_elite_enter','params':{'elite':id}}
        elites.append({'id':id,'title':e['name'],'status':'已战胜' if id in j['elite_wins'] else '可挑战' if not blocked else blocked,'preparation':e['description'],'rewards':'无独立掉落；完成对应故事领取唯一器物','action':action})
        add('exploration','world_elite_enter','挑战'+e['name'],'免费重试，不耗挑战资格','固定气血%d/常击%d/重击%d。%s'%(e['hp'],e['attack'],e['heavy'],e['description']),{'elite':id},blocked)
    view['journey']={'layers':layers,'elites':elites}
