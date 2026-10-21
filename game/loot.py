"""R3 longline item ownership, deterministic loot and world-boss receipts.

Pure domain logic: UTC is injected; no filesystem/network/real clock is used.
"""
import copy
import uuid
import re
from . import world_config as C
from . import r3_config as R
from . import activities
from . import journey
from . import cadence
from . import gameplay_config as G

CAP=999999
INSTANCE_CAP=R.LIMITS['owned_instances']
SLOTS=('weapon','armor','pendant','main','guard')
TEMPLATES=('blade','armor','pendant','main_treasure','guard_treasure')


def initial_state():
    return dict(version=1,profile_id=str(uuid.uuid4()),growth=None,instances={},equipped={k:None for k in SLOTS},
        materials={'dust':0,'enhance_material':0,'boss_coin':0},pending={},seq=0,receipts=[],
        daily={},pity={'1':0,'2':0,'3':0},drop_seq=0,run_seq=0,runs={},boss={},milestones={},
        crafted={k:0 for k in C.ARTS},crafted_recipes={k:0 for k in C.RECIPES},used={k:0 for k in C.ARTS},secret_count=0,daily_count=0,activities=activities.initial_state(),journey=journey.initial_state(),cadence=cadence.initial_state())


def enabled(state):return isinstance(state,dict) and isinstance(state.get('world'),dict) and 'r3' in state['world']


def _fail(message,code='ACTION_UNAVAILABLE',status=422):
    from .rules import GameError
    raise GameError(code,message,status)


def _bad(message):_fail(message,'BAD_REQUEST',400)


def _integer(value,lo=0,hi=CAP):return type(value) is int and lo<=value<=hi


def day(context):
    value=(context or {}).get('day')
    if not isinstance(value,str):_bad('长线行动需要服务端UTC时间上下文。')
    return value


def cost(stage):return R.STAGES[stage]['cost']


def growth_bonus_bps(state):
    if not enabled(state):return 0
    w=state['world'];r=w['r3'];treasure=0
    for slot in ['main','guard']:
        item=r['instances'].get(r['equipped'][slot])
        if item and item['effect_type']=='cultivation':treasure+=R.QUALITIES[item['quality']]['treasure_speed_bp']
    bonuses=R.OTHER_BONUSES
    other=bonuses['wood_root']['levels_bp'][w['root']['level']] if w['root']['id']=='wood' else 0
    other+=bonuses['skill']['levels_bp'][w['skills'][w['skill']]]
    other+=bonuses['chamber']['levels_bp'][w['home']['chamber']]
    other+=bonuses['spirit_array']['levels_bp'][w['arrays']['spirit']] if w['arrays_enabled']['spirit'] else 0
    earned=w['sect_earned'].get(w['sect'],0) if w['sect'] else 0
    rank=sum(earned>=n for n in bonuses['sect']['thresholds'])
    other+=bonuses['sect']['ranks_bp'][rank]
    other+=bonuses['title']['equipped_bp'] if w['title'] else 0
    return min(R.TOTAL_SPEED_CAP_BP,min(R.TREASURE_CAP_BP,treasure)+min(R.OTHER_CAP_BP,other))


def item_slot(template):return {'blade':'weapon','armor':'armor','pendant':'pendant','main_treasure':'main','guard_treasure':'guard'}[template]


def item_name(item):
    return {'blade':'灵刃','armor':'玄甲','pendant':'灵佩','main_treasure':'本命法宝','guard_treasure':'护持法宝'}.get(item,item)


def material_name(item):return {'dust':'宝尘','enhance_material':'通用强化材','boss_coin':'世界Boss币'}.get(item,C.RESOURCES.get(item,C.ITEMS.get(item,{}).get('name',item)))


def instance_effect(item):
    t=item['chapter'];q=item['quality'];enhance=item['enhance'];template=item['template_id']
    if template not in {'blade','armor','pendant'}:return {}
    base=R.EQUIPMENT[template]['base']+R.EQUIPMENT[template]['per_chapter']*t
    amount=base*(10000+R.QUALITIES[q]['combat_bonus_bp']+R.ENHANCE_BONUS_BP[enhance])//10000
    return {{'blade':'attack','armor':'hp','pendant':'mp'}[template]:amount}


def combat_treasure(w,slot):
    """Equipped combat-path treasure for an auto-battle slot ('main' or 'guard'), else None."""
    r=w.get('r3')
    if not r:return None
    item=r['instances'].get(r['equipped'].get(slot))
    return item if item and item['effect_type']=='combat' else None


def attributes(w,base):
    r=w['r3'];result=dict(base)
    for slot in ['weapon','armor','pendant']:
        item=r['instances'].get(r['equipped'][slot])
        if item:
            for k,v in instance_effect(item).items():result[k]+=v
    main=r['instances'].get(r['equipped']['main']);guard=r['instances'].get(r['equipped']['guard'])
    if main and main['effect_type']=='combat':result['attack']=result['attack']*(10000+R.QUALITIES[main['quality']]['main_attack_bp'])//10000
    if guard and guard['effect_type']=='combat':result['hp']=result['hp']*(10000+R.QUALITIES[guard['quality']]['guard_hp_bp'])//10000
    return result


def _pay(w,costs):
    for item,n in costs.items():
        have=w['r3']['materials'][item] if item in w['r3']['materials'] else w['wallet'] if item=='stone' else w['inventory'].get(item,0)
        if have<n:_fail('缺少%s：需要%d，当前%d。'%(material_name(item),n,have))
    for item,n in costs.items():
        if item in w['r3']['materials']:w['r3']['materials'][item]-=n
        elif item=='stone':w['wallet']-=n
        else:w['inventory'][item]-=n


def _receipt(r,source):
    r['seq']+=1
    return '%s:%d:%s'%(r['profile_id'],r['seq'],source)


def _grant_materials(w,rewards,source):
    r=w['r3'];overflow={}
    for item,n in rewards.items():
        current=r['materials'].get(item,w['wallet'] if item=='stone' else w['inventory'].get(item,0))
        if current+n>CAP:overflow[item]=n;continue
        if item in r['materials']:r['materials'][item]+=n
        elif item=='stone':w['wallet']+=n
        else:w['inventory'][item]=current+n
    if overflow:
        key=_receipt(r,'delivery');r['pending'][key]={'source':source,'item':None,'materials':overflow}


def _new_instance(w,template,chapter,quality,source,effect_type='unselected'):
    r=w['r3'];active_run=w['dungeon']['run_id'] if w.get('dungeon') else None
    reserved=int(bool(active_run and active_run!=source and r['runs'][active_run]['eligible'] and not r['runs'][active_run]['completed']))
    if len(r['instances'])>=INSTANCE_CAP and sum(v['item'] is not None for v in r['pending'].values())>=R.LIMITS['pending_instances']-reserved:_fail('实例与掉落暂存均已满，请先领取/分解整理后再制作或挑战。')
    receipt=_receipt(r,source);uid='item:'+receipt
    item=dict(uid=uid,template_id=template,chapter=chapter,quality=quality,enhance=0,
        effect_type=effect_type if template.endswith('treasure') else 'combat',source_receipt=receipt)
    if len(r['instances'])>=INSTANCE_CAP:r['pending'][receipt]={'source':source,'item':item,'materials':{}}
    else:r['instances'][uid]=item
    r['receipts'].append({'id':receipt,'source':source,'uid':uid,'template':template,'quality':quality})
    return item


def equipment_score(w):
    r=w['r3'];score=0
    for slot in ['weapon','armor','pendant']:
        item=r['instances'].get(r['equipped'][slot])
        if item:score+=2*item['chapter']+item['quality']+1+item['enhance']
    return score


def difficulty_reason(w,dungeon,chapter,difficulty):
    if chapter>w['stage']:_fail('章节尚未解锁。')
    r=w['r3'];required=R.DIFFICULTIES[difficulty]['score_base']+R.DIFFICULTIES[difficulty]['score_per_chapter']*chapter
    previous='%s:%d:%d'%(dungeon,chapter,difficulty-1)
    if difficulty>1 and previous not in w['dungeon_wins']:_fail('需先完成同章节前一难度。')
    if equipment_score(w)<required:_fail('装备分需要%d，当前%d；可制作当前章节凡品并强化。'%(required,equipment_score(w)))


def begin_run(w,dungeon,chapter,difficulty,context):
    difficulty_reason(w,dungeon,chapter,difficulty);r=w['r3'];d=day(context)
    if (r.get('cadence',{}).get('available',r['daily'].get(d,0)<3)) and len(r['instances'])>=INSTANCE_CAP and sum(v['item'] is not None for v in r['pending'].values())>=R.LIMITS['pending_instances']:_fail('掉落实例与暂存容量均满，请先整理再参加正式掉落。')
    r['run_seq']+=1;run_id='run:%s:%d'%(r['profile_id'],r['run_seq'])
    next_pity=r['pity'][str(difficulty)]+1
    quality=next((entry['quality'] for entry in R.PITY[difficulty] if next_pity%entry['every']==0),R.DIFFICULTIES[difficulty]['quality_base'])
    r['runs'][run_id]={'day':d,'dungeon':dungeon,'chapter':chapter,'difficulty':difficulty,'eligible':r['daily'].get(d,0)<R.DUNGEON_RULES['daily_rewarded_clears'],'completed':False,
        'planned_seq':r['drop_seq']+1,'pity_next':next_pity,'template':R.DROP_CYCLE[r['drop_seq']%len(R.DROP_CYCLE)],'quality':quality,'table_version':R.CONTENT_VERSION}
    if 'cadence' in r:
        from . import cadence
        r['runs'][run_id]['eligible']=cadence.reserve(w,run_id,context)
    return run_id


def release_run(w):
    if 'r3' in w and 'cadence' in w['r3'] and w.get('dungeon'):
        from . import cadence
        cadence.finish(w,w['dungeon']['run_id'],False)


def complete_run(w,run_id,events):
    r=w['r3'];run=r['runs'][run_id]
    if run['completed']:_fail('这次副本已经结算。')
    run['completed']=True
    if not run['eligible'] or 'cadence' not in r and r['daily'].get(run['day'],0)>=R.DUNGEON_RULES['daily_rewarded_clears']:events.append('本次为练习通关，无新装备掉落；持续修炼不受影响。');return
    if 'cadence' in r:
        from . import cadence
        cadence.finish(w,run_id,True)
    difficulty=run['difficulty'];key=str(difficulty)
    if run['planned_seq']!=r['drop_seq']+1 or run['pity_next']!=r['pity'][key]+1:_fail('副本掉落权益序号不一致，请联系管理员检查服务日志。')
    r['pity'][key]=run['pity_next'];q=run['quality'];template=run['template'];r['drop_seq']+=1;r['daily'][run['day']]=r['daily'].get(run['day'],0)+1
    _new_instance(w,template,run['chapter'],q,run_id)
    _grant_materials(w,R.DIFFICULTIES[difficulty]['materials'],run_id)
    events.append('正式副本掉落：%s（%s）；宝尘%d、强化材%d。累计本UTC日正式成功%d次。'%(item_name(template),R.QUALITIES[q]['name'],difficulty+1,2*difficulty,r['daily'][run['day']]))


def ready_template(w,template):return next((uid for uid,item in w['r3']['instances'].items() if item['template_id']==template and uid not in w['r3']['equipped'].values()),None)


def consume_template(w,template):
    uid=ready_template(w,template)
    if uid is None:_fail('缺少可交付的未装备器物。')
    del w['r3']['instances'][uid]


def mark_use(w,art):w['r3']['used'][art]+=1


def process(w,action,p,events,context):
    r=w['r3']
    if action=='world_loot_equip':
        uid=p['uid'];item=_owned(r,uid);slot=item_slot(item['template_id'])
        if item['effect_type']=='unselected':_fail('请先选择法宝的修炼或战力方向。')
        if r['equipped'][slot]==uid:_fail('该实例已经装备。')
        r['equipped'][slot]=uid;mark_use(w,'smithing');events.append('已装备'+item_name(item['template_id'])+'；新效果从当前时刻生效。');return True
    if action=='world_loot_unequip':
        slot=p['slot']
        if slot not in SLOTS:_bad('未知装备槽。')
        if r['equipped'][slot] is None:_fail('该槽为空。')
        r['equipped'][slot]=None;events.append('已卸下装备，新速率不追溯过去。');return True
    if action=='world_loot_choose':
        item=_owned(r,p['uid']);path=p['effect_type']
        if path not in {'cultivation','combat'}:_bad('法宝方向必须为修炼或战力。')
        if not item['template_id'].endswith('treasure') or item['effect_type']!='unselected':_fail('仅未定向的新法宝可选择一次方向。')
        item['effect_type']=path;events.append('法宝定向完成，不能兼得两类效果。');return True
    if action=='world_loot_enhance':
        item=_owned(r,p['uid'])
        if item['template_id'].endswith('treasure'):_fail('法宝请使用提质，强化不会额外增加修炼效率。')
        target=item['enhance']+1
        if target>3:_fail('强化已达三级。')
        _pay(w,R.FORGE_COSTS[target]);item['enhance']=target;events.append('该装备实例强化至%d级，无失败降级。'%target);return True
    if action=='world_loot_quality':
        item=_owned(r,p['uid'])
        if not item['template_id'].endswith('treasure'):_fail('此入口仅提升法宝品质。')
        target=item['quality']+1
        if target>4:_fail('已达极品，单件修炼加成上限5%。')
        _pay(w,R.QUALITY_UPGRADE_COSTS[target]);item['quality']=target;events.append('法宝提质至'+R.QUALITIES[target]['name']+'。');return True
    if action=='world_loot_dismantle':
        uid=p['uid'];item=_owned(r,uid)
        if uid in r['equipped'].values():_fail('请先卸下再分解。')
        _grant_materials(w,R.DECOMPOSE[item['quality']],'分解:'+uid)
        del r['instances'][uid];events.append('实例已消费，分解材料已入库或待领，不能再装备原物。');return True
    if action=='world_loot_craft_treasure':
        slot=p['slot'];path=p['effect_type']
        if slot not in {'main','guard'} or path not in {'cultivation','combat'}:_bad('请选择合法法宝槽和方向。')
        _pay(w,R.TREASURES[slot+'_treasure']['cost']);_new_instance(w,slot+'_treasure',w['stage'],0,'保底制作',path);events.append('保底制作凡品法宝完成。');return True
    if action=='world_loot_exchange':
        item=p['item']
        if item=='dust':_pay(w,{'boss_coin':2});_grant_materials(w,{'dust':1},'世界Boss币兑换')
        elif item=='enhance_material':_pay(w,{'ore':4,'wood':2});_grant_materials(w,{'enhance_material':1},'四艺材料兑换')
        else:_bad('未知材料兑换。')
        events.append('材料兑换完成，无直接修为奖励。');return True
    if action=='world_loot_claim':
        key=p['receipt'];delivery=r['pending'].get(key)
        if not delivery:_fail('没有此待领权益。')
        if delivery['item'] and len(r['instances'])>=INSTANCE_CAP:_fail('实例背包已满，请先分解不用的器物。')
        for k,n in delivery['materials'].items():
            current=r['materials'].get(k,w['wallet'] if k=='stone' else w['inventory'].get(k,0))
            if current+n>CAP:_fail('材料容量不足，本笔待领保留。')
        if delivery['item']:r['instances'][delivery['item']['uid']]=delivery['item']
        _grant_materials(w,delivery['materials'],delivery['source']);del r['pending'][key];events.append('待领实例与材料已完整领取一次。');return True
    return False


def _owned(r,uid):
    if not isinstance(uid,str) or uid not in r['instances']:_fail('不持有该装备实例。')
    return r['instances'][uid]


def begin_boss(w,context,events):
    from .world import _error
    if w['battle'] or w['dungeon'] or w['exploration']:_fail('请先结束当前战斗或探索。')
    r=w['r3'];d=day(context);period=r['boss'].get(d)
    if period is None:
        s=w['stage'];period=dict(encounter='boss:'+r['profile_id']+':'+d,stage=s,reference=R.BOSS['reference_base']+R.BOSS['reference_stage']*s,
            attempts=0,best=0,paid_coin=0,paid_dust=0,last_damage=0,last_delta_coin=0,last_delta_dust=0,participated=False,runs={})
        r['boss'][d]=period
    if period['attempts']>=R.BOSS['daily_attempts']:_fail('本期三次正式世界Boss挑战已用完，持续修炼不受影响。')
    period['attempts']+=1;attempt=period['encounter']+':'+str(period['attempts']);period['runs'][attempt]={'settled':False,'damage':0,'commands':0}
    s=period['stage'];w['battle']=dict(name=R.BOSS['name'],hp=R.BOSS['hp'],max_hp=R.BOSS['hp'],attack=R.BOSS['attack_base']+R.BOSS['attack_stage']*s,
        heavy=R.BOSS['heavy_base']+R.BOSS['heavy_stage']*s,turn=0,kind='world_boss',target=attempt,stage=s,shield=0,heals=0,snapshot=None,start_tick=w['tick'],growth=0,
        r3_day=d,r3_attempt=attempt,player_damage=0,commands=0)
    events.append('世界Boss正式挑战开始：最多12回合，只计本场玩家有效伤害；NPC/同行不计分。')


def finish_boss(w,b,events):
    period=w['r3']['boss'][b['r3_day']];run=period['runs'][b['r3_attempt']]
    if run['settled']:_fail('本次世界Boss已经结算。')
    run.update(settled=True,damage=b['player_damage'],commands=b['commands'])
    period['last_damage']=b['player_damage']
    if b['commands']>=R.BOSS['minimum_valid_commands']:
        period['participated']=True;period['best']=max(period['best'],b['player_damage'])
    w['battle']=None
    events.append('本场世界Boss有效伤害%d；本期单次最高%d（不累计多场）。'%(b['player_damage'],period['best']))


def boss_entitlement(period):
    if not period['participated']:return 0,0
    reference=period['reference'];score=min(period['best'],2*reference)
    coins=R.BOSS['coin_participation']+R.BOSS['coin_scale']*score//(2*reference)
    dust=max((band['dust_total'] for band in R.BOSS['bands'] if score*band['den']>=reference*band['num']),default=0)
    return coins,dust


def _boss_action(w,action,p,events,context):
    if action=='world_boss_enter':begin_boss(w,context,events);return True
    if action=='world_boss_claim':
        period=w['r3']['boss'].get(p['day'])
        if not period:_fail('本期尚无正式世界Boss成绩。')
        coins,dust=boss_entitlement(period);dc=coins-period['paid_coin'];dd=dust-period['paid_dust']
        if dc==0 and dd==0:_fail('成绩未提高或本期差额已领取。')
        _grant_materials(w,{'boss_coin':dc,'dust':dd},period['encounter']);period['paid_coin']=coins;period['paid_dust']=dust;period['last_delta_coin']=dc;period['last_delta_dust']=dd
        events.append('世界Boss仅补新差额：战功币%d、宝尘%d。'%(dc,dd));return True
    return False


def _balance_micro(w):
    g=w['r3']['growth'];return g['balance_micro'] if isinstance(g,dict) else w['xp']*1_000_000


def _milestone(w,action,p,events):
    if action not in {'world_milestone_accept','world_milestone_claim'}:return False
    stage=p['stage'];tier=p['tier']
    if not _integer(stage,0,7) or tier not in R.MILESTONES:_bad('小境界阶段或档位无效。')
    r=w['r3'];key='%d:%d'%(stage,tier);entry=r['milestones'].get(key)
    if action=='world_milestone_accept':
        if entry:_fail('此档小境界任务已接取或领取。')
        if stage>w['stage'] or stage==w['stage'] and _balance_micro(w)*100<cost(stage)*tier*1_000_000:_fail('尚未达到此阶段小境界进度。')
        branch=p['branch'];allowed={25:{'herb','pill'},50:set(C.ARTS),75:{'secret','commission'}}[tier]
        if branch not in allowed:_bad('该档任务分支无效。')
        if tier==50 and branch=='formations' and all(level>=3 for level in w['arrays'].values()):_fail('三种阵法均已满级，无法再制造；请改选炼丹、炼器或制符分支。')
        r['milestones'][key]={'branch':branch,'claimed':False,'crafts':dict(r['crafted']),'used':dict(r['used']),'secrets':r['secret_count'],'commissions':r['daily_count'],'pills':r['crafted_recipes']['pill']}
        events.append('接取可选小境界任务，不锁突破、不发修为。');return True
    if not entry or entry['claimed']:_fail('请先接取本档任务，或此档已经领取。')
    branch=entry['branch']
    if tier==25:
        if branch=='herb':_pay(w,{'herb':2})
        elif r['crafted_recipes']['pill']<=entry['pills']:_fail('请在接取后制成一枚回元丹。')
        _grant_materials(w,{'ore':2},'小境界:'+key)
    elif tier==50:
        if r['crafted'][branch]<=entry['crafts'][branch] or r['used'][branch]<=entry['used'][branch]:_fail('请在接取后完成所选技艺制造并实际使用一次。')
        w['arts'][branch]+=5
    else:
        if branch=='secret' and r['secret_count']<=entry['secrets'] or branch=='commission' and r['daily_count']<=entry['commissions']:_fail('请在接取后完成一次秘境或材料课业委托。')
        _grant_materials(w,{'wood':2},'小境界:'+key)
    entry['claimed']=True;events.append('小境界任务奖励已发：仅材料/熟练/剧情，修为增加0。');return True


def handle(w,action,p,events,context):
    return activities.handle(w,action,p,events,context) or process(w,action,p,events,context) or _boss_action(w,action,p,events,context) or _milestone(w,action,p,events)


def validate(state):
    from . import growth
    if not enabled(state):return
    r=state['world']['r3'];expected=set(initial_state())
    expected-=({'journey','cadence'}-set(r))
    if 'cadence' in r:expected.add('cadence')
    def bad(message='长线实例或权益字段无效'):raise ValueError(message)
    def obj(v,keys):
        if not isinstance(v,dict) or set(v)!=set(keys):bad()
    def integer(v,lo=0,hi=CAP):
        if not _integer(v,lo,hi):bad()
    def ident(v):
        if not isinstance(v,str) or not 1<=len(v)<=300:bad()
    obj(r,expected)
    if r['version']!=1 or type(r['version']) is not int:bad()
    ident(r['profile_id'])
    for key in ['seq','drop_seq','run_seq','secret_count','daily_count']:integer(r[key],0,2**63-1)
    obj(r['materials'],R.MATERIALS)
    for n in r['materials'].values():integer(n)
    obj(r['equipped'],SLOTS)
    if not isinstance(r['instances'],dict) or len(r['instances'])>INSTANCE_CAP:bad()
    def instance(item):
        obj(item,R.INSTANCE_FIELDS);ident(item['uid']);ident(item['source_receipt'])
        if item['template_id'] not in TEMPLATES:bad()
        integer(item['chapter'],0,7);integer(item['quality'],0,4);integer(item['enhance'],0,3)
        if item['effect_type'] not in {'unselected','cultivation','combat'}:bad()
        if item['template_id'] in R.EQUIPMENT and item['effect_type']!='combat':bad()
        if item['template_id'] in R.TREASURES and item['enhance']!=0:bad()
    for uid,item in r['instances'].items():
        instance(item)
        if uid!=item['uid']:bad()
    equipped=[]
    for slot,uid in r['equipped'].items():
        if uid is not None:
            if not isinstance(uid,str) or uid not in r['instances'] or item_slot(r['instances'][uid]['template_id'])!=slot or r['instances'][uid]['effect_type']=='unselected':bad()
            equipped.append(uid)
    if len(equipped)!=len(set(equipped)):bad()
    if not isinstance(r['pending'],dict):bad()
    pending_uids=[]
    for key,delivery in r['pending'].items():
        ident(key);obj(delivery,{'source','item','materials'});ident(delivery['source'])
        if delivery['item'] is not None:instance(delivery['item']);pending_uids.append(delivery['item']['uid'])
        if not isinstance(delivery['materials'],dict):bad()
        for k,n in delivery['materials'].items():
            if k not in R.RESOURCE_STORAGE and k not in C.ITEMS:bad()
            integer(n)
    if len(pending_uids)!=len(set(pending_uids)) or set(pending_uids)&set(r['instances']):bad()
    if not isinstance(r['receipts'],list):bad()
    seen=set()
    for receipt in r['receipts']:
        obj(receipt,{'id','source','uid','template','quality'})
        for key in ['id','source','uid']:ident(receipt[key])
        if receipt['id'] in seen or receipt['template'] not in TEMPLATES:bad()
        seen.add(receipt['id']);integer(receipt['quality'],0,4)
    for key in ['daily','pity','runs','boss','milestones','crafted','crafted_recipes','used']:
        if not isinstance(r[key],dict):bad()
    obj(r['pity'],{'1','2','3'})
    for value in list(r['pity'].values())+list(r['daily'].values()):integer(value,0,2**63-1)
    obj(r['crafted_recipes'],C.RECIPES)
    for n in r['crafted_recipes'].values():integer(n,0,2**63-1)
    for key in ['crafted','used']:
        obj(r[key],C.ARTS)
        for n in r[key].values():integer(n,0,2**63-1)
    for key,run in r['runs'].items():
        ident(key);obj(run,({'manual'} if 'manual' in run else set())|{'day','dungeon','chapter','difficulty','eligible','completed','planned_seq','pity_next','template','quality','table_version'})
        if 'manual' in run and type(run['manual']) is not bool:bad()
        ident(run['day'])
        if run['dungeon'] not in C.DUNGEONS or run['template'] not in TEMPLATES:bad()
        for k,hi in [('chapter',7),('difficulty',3),('quality',4)]:integer(run[k],1 if k=='difficulty' else 0,hi)
        for k in ['planned_seq','pity_next','table_version']:integer(run[k],1,2**63-1)
        if type(run['eligible']) is not bool or type(run['completed']) is not bool:bad()
    for key,period in r['boss'].items():
        ident(key);obj(period,{'encounter','stage','reference','attempts','best','paid_coin','paid_dust','last_damage','last_delta_coin','last_delta_dust','participated','runs'})
        ident(period['encounter']);integer(period['stage'],0,7);integer(period['reference'],1,CAP);integer(period['attempts'],0,R.BOSS['daily_attempts'])
        if period['reference']!=R.BOSS['reference_base']+R.BOSS['reference_stage']*period['stage'] or period['encounter']!='boss:'+r['profile_id']+':'+key:bad()
        for k in ['best','last_damage']:integer(period[k],0,R.BOSS['hp'])
        for k in ['paid_coin','paid_dust','last_delta_coin','last_delta_dust']:integer(period[k])
        if type(period['participated']) is not bool or not isinstance(period['runs'],dict):bad()
        for attempt,data in period['runs'].items():
            ident(attempt);obj(data,{'settled','damage','commands'})
            if type(data['settled']) is not bool:bad()
            integer(data['damage'],0,R.BOSS['hp']);integer(data['commands'],0,R.BOSS['rounds'])
        coins,dust=boss_entitlement(period)
        if period['paid_coin']>coins or period['paid_dust']>dust:bad()
    for key,m in r['milestones'].items():
        if key not in {'%d:%d'%(s,t) for s in range(8) for t in R.MILESTONES}:bad()
        obj(m,{'branch','claimed','crafts','used','secrets','commissions','pills'})
        if m['branch'] not in {'herb','pill','secret','commission',*C.ARTS} or type(m['claimed']) is not bool:bad()
        for k in ['crafts','used']:
            obj(m[k],C.ARTS)
            for n in m[k].values():integer(n,0,2**63-1)
        integer(m['secrets'],0,2**63-1);integer(m['commissions'],0,2**63-1);integer(m['pills'],0,2**63-1)
    growth.validate(state)
    activities.validate(state)
    journey.validate(state)
    if 'cadence' in r:cadence.validate(state)


def _cost_label(costs):return '、'.join('%s%d'%(material_name(k),n) for k,n in costs.items()) or '免费'


def project(state,view,context=None):
    """Augment the existing 11 pages; item actions use O(1) readonly conditions."""
    from . import world
    w=state['world'];r=w['r3'];pages={p['id']:p for p in view['pages']};ctx=context or {}
    d=ctx.get('day','');before=world.attributes(w);balance=_balance_micro(w);required=cost(w['stage'])
    def section(page,title,rows=(),body=''):
        pages[page]['sections'].append({'title':title,'body':body,'rows':[{'label':str(k),'value':str(v)} for k,v in rows]})
    def affordability(costs):
        for key,n in costs.items():
            current=r['materials'].get(key,w['wallet'] if key=='stone' else w['inventory'].get(key,0))
            if current<n:return '缺少%s：需要%d，当前%d。'%(material_name(key),n,current)
        return ''
    def add(page,id,label,cost_text,effect,params=None,reason='',fields=None,confirm=None):
        reason=('完成序章后进入凡界。' if not w['active'] else '战斗中请先结束当前交锋。' if w['battle'] else reason)
        a=dict(id=id,label=label,detail=label+'：'+cost_text+'；'+effect+'。',cost=cost_text,effect=effect,enabled=not reason,reason=reason,params=params or {},group=page,primary=False)
        if fields:a['fields']=fields
        if confirm:a['confirm']=confirm
        pages[page]['actions'].append(a)
    for page in view['pages']:
        # These old modes have no valid R3 interpretation; give new explicit paths.
        page['actions']=[a for a in page['actions'] if a['id'] not in {'world_cultivate','world_dungeon_enter','world_equip','world_unequip','world_forge'}]
        for a in page['actions']:
            if a['id'] not in {'world_advance','world_finish'}:
                # All formerly direct XP sources are actual non-XP actions now.
                if '修为' in a['effect']:
                    effect=re.sub(r'、修为\d+','',a['effect'])
                    effect=re.sub(r'；终节点修为\d+，','；',effect)
                    effect=effect.replace('、修为12及','及').replace('，首次修为20','').replace('及修为一次领取','一次领取')
                    a['effect']=effect+'；直接修为0，持续潜修不停。'
                if a['id']=='world_quest_claim':
                    quest=C.QUESTS[a['params']['quest']];a['effect']='一次领取：'+world._cost_text(quest['reward'])+'；直接修为0'
                if a['id']=='world_sect_claim' and w['sect_quest']:
                    payout=C.SECT_RULES['tasks'][w['sect_quest']['type']];a['effect']='灵石%d、贡献%d、地域声望5；直接修为0'%(payout['stone'],payout['contribution'])
                if a['id']=='world_encounter' and w['encounter'] and w['encounter']['id'] in R.ENCOUNTER_OVERRIDES and a['params']['choice']!='leave':
                    choice=R.ENCOUNTER_OVERRIDES[w['encounter']['id']][a['params']['choice']];a['label']=choice['name'];a['cost']=_cost_label(choice['cost']);a['effect']='实际获得：'+_cost_label(choice['reward'])+'；直接修为0'
                if a['id']=='world_teach':a['cost']='灵石5';a['effect']='弟子经验5+学堂加成，不消耗主线修为。'
                if a['id']=='world_root':a['effect']='木根持续效率按0/0.25/0.5/1%；火土提供攻击/生存，采草加成照常'
                if a['id']=='world_title':
                    title=a['params']['title'];a['effect']=('攻击+3，' if title=='veteran' else '静养气血+10，' if title=='companion' else '')+'佩戴称号持续修炼+0.5%，受总15%上限约束'
            if a['id']=='world_advance':a['cost']='修为%d及阶段条件'%required
            if a['id']=='world_finish':a['cost']='渡劫修为51840、守关与三秘境及主线备阵'
            if a['id']=='world_auto_battle':a['group']='battle'
        if page['id']=='quests':
            for s in page['sections']:
                for row in s['rows']:
                    if row['label']=='奖励':row['value']=row['value'].split('、修为')[0]+'；直接修为0'
        if page['id']=='character':
            for s in page['sections']:
                for row in s['rows']:
                    if row['label']=='下一关':row['value']='凡界界门已封，持续修为计潜修储备。' if w['ending'] else world._advance_reason(w) or '条件已齐，可突破。'
    if w['stage']==7 and not w['ending']:
        for a in pages['character']['actions']:
            if a['id']=='world_finish' and w['xp']<required:a.update(enabled=False,reason='渡劫圆满封界需要51840修为，尚未满足。')
    section('character','长线持续修炼',[("当前余额",'%.3f'%(balance/1_000_000)),('未来速率加成','%.2f%%'%(growth_bonus_bps(state)/100)),('模式','在线离线持续；副本、首胜、社交、任务、点击均不直接发修为')])
    items=[]
    for uid,item in r['instances'].items():
        slot=item_slot(item['template_id']);equipped=r['equipped'][slot]==uid;after_w=dict(w);after_r=dict(r);after_r['equipped']={**r['equipped'],slot:uid};after_w['r3']=after_r
        after=world.attributes(after_w);after_speed=growth_bonus_bps({'world':after_w})
        comparisons=[{'label':label,'before':str(before[k]),'after':str(after[k]),'delta':'%+d'%(after[k]-before[k])} for k,label in [('attack','攻击'),('hp','气血上限'),('mp','灵力上限')]]
        comparisons.append({'label':'持续修炼加成','before':'%.2f%%'%(growth_bonus_bps(state)/100),'after':'%.2f%%'%(after_speed/100),'delta':'%+.2f%%'%((after_speed-growth_bonus_bps(state))/100)})
        q=R.QUALITIES[item['quality']]['name'];name='第%d章%s'%(item['chapter'],item_name(item['template_id']))
        items.append(dict(uid=uid,name=name,slot=slot,quality=q,chapter=item['chapter'],enhance=item['enhance'],effect_type=R.TREASURE_PATHS[item['effect_type']] if item['template_id'] in R.TREASURES else '战斗装备',equipped=equipped,source=item['source_receipt'],comparison=comparisons))
        add('character','world_loot_equip','装备'+name+' · '+q,'免费','单一实例槽位；未来速率从此刻生效',{'uid':uid},'该实例已装备。' if equipped else '请先为法宝选择方向。' if item['effect_type']=='unselected' else '')
        if item['template_id'] in R.TREASURES:
            if item['effect_type']=='unselected':
                add('character','world_loot_choose','选择'+name+'方向','免费，只能选择一次','修炼只提未来效率，战力只改战斗属性',{'uid':uid},fields=[{'name':'effect_type','label':'法宝方向','type':'select','required':True,'options':[{'value':'cultivation','label':'修炼型'},{'value':'combat','label':'战力型'}]}])
            target=item['quality']+1;costs=R.QUALITY_UPGRADE_COSTS.get(target,{})
            add('character','world_loot_quality','提质'+name,_cost_label(costs),'最高极品，单件修炼增速最高5%',{'uid':uid},'已达到极品。' if target>4 else affordability(costs))
        else:
            target=item['enhance']+1;costs=R.FORGE_COSTS.get(target,{})
            add('character','world_loot_enhance','强化'+name,_cost_label(costs),'只强化该uid；品质与强化加法计算，不重复叠乘',{'uid':uid},'强化已满三级。' if target>3 else affordability(costs))
        add('character','world_loot_dismantle','分解'+name,'消费该实例，不可找回','返还强化材%d、宝尘%d'%(1+item['quality'],1+item['quality']//2),{'uid':uid},'请先卸下该实例。' if equipped else '',confirm='分解会消费该uid，只留下材料，原物无法找回。')
    for slot,uid in r['equipped'].items():add('character','world_loot_unequip','卸下'+{'weapon':'武器','armor':'护甲','pendant':'灵佩','main':'本命法宝','guard':'护持法宝'}[slot],'免费','只改变未来速率/当前合法战力',{'slot':slot},'' if uid else '槽位为空。')
    for slot in ['main','guard']:
        costs=R.TREASURES[slot+'_treasure']['cost'];add('craft','world_loot_craft_treasure','保底制作'+item_name(slot+'_treasure'),_cost_label(costs),'凡品法宝，方向固定；无需高难稀有掉落',{'slot':slot},affordability(costs),fields=[{'name':'effect_type','label':'法宝方向','type':'select','required':True,'options':[{'value':'cultivation','label':'修炼型'},{'value':'combat','label':'战力型'}]}])
    for item,costs in [('enhance_material',{'ore':4,'wood':2}),('dust',{'boss_coin':2})]:add('craft','world_loot_exchange','兑换'+material_name(item),_cost_label(costs),'安全补给材料，不发修为',{'item':item},affordability(costs))
    for key,delivery in r['pending'].items():
        reason='实例背包已满。' if delivery['item'] and len(r['instances'])>=INSTANCE_CAP else ''
        for material,n in delivery['materials'].items():
            if r['materials'].get(material,w['wallet'] if material=='stone' else w['inventory'].get(material,0))+n>CAP:reason='材料容量不足，本笔权益完整保留。'
        add('character','world_loot_claim','领取掉落暂存','需要实例/材料完整容量','来源：'+delivery['source'],{'receipt':key},reason)
    credits=None
    if 'cadence' in r:
        from . import cadence
        credits=cadence.project(state,context)
    dungeon_views=[]
    for dungeon,definition in C.DUNGEONS.items():
        for chapter in range(w['stage']+1):
            for difficulty,data in R.DIFFICULTIES.items():
                reason=''
                try:difficulty_reason(w,dungeon,chapter,difficulty)
                except Exception as exc:reason=str(exc)
                if w['region']!=definition['region']:reason='请先前往'+C.REGIONS[definition['region']]['name']+'。'
                if w['exploration'] or w['dungeon']:reason='已有探索活动，请先完成或撤离。'
                eligible=('可用挑战资格%d / %d；预约%d；每8小时恢复1次'%(credits['available'],credits['capacity'],credits['reserved'])) if credits else 'UTC日正式成功 %d / 3；本次%s'%(r['daily'].get(d,0),'有掉落资格' if r['daily'].get(d,0)<3 else '无新掉落，仅练习')
                pity='本难度有资格成功%d次；保证%s，周期保底按独立难度累计'%(r['pity'][str(difficulty)],R.QUALITIES[data['quality_base']]['name'])
                rewards='保证1实例；'+_cost_label(data['materials'])+'；模板顺序灵刃→玄甲→灵佩→本命法宝→护持法宝'
                mechanic=G.DUNGEON_MECHANICS[dungeon]['description'] if difficulty>=2 else '基础常击→蓄势→重击，无额外毒/盾/汲灵。'
                dungeon_views.append(dict(id=dungeon,name=definition['name'],chapter=chapter,difficulty=difficulty,conditions=reason or '条件已满足；装备分%d'%equipment_score(w),rewards=rewards,eligible=eligible,pity=pity,mechanic=mechanic+' 敌强按入场章节固定，不随玩家升级抬涨。'))
                sweep_reason=reason
                if not sweep_reason and '%s:%d:%d'%(dungeon,chapter,difficulty) not in r.get('journey',{}).get('manual_clears',[]):sweep_reason='需先同章同难真实手战通关一次。'
                if not sweep_reason and (not credits or credits['available']<1):sweep_reason='扫荡需要1次挑战资格；零次可手战练习。'
                if not sweep_reason and len(r['instances'])>=INSTANCE_CAP and sum(v['item'] is not None for v in r['pending'].values())>=R.LIMITS['pending_instances']:sweep_reason='实例与暂存均满，请先整理。'
                sweep_params={'dungeon':dungeon,'chapter':chapter,'difficulty':difficulty}
                dungeon_views[-1]['sweep']={'enabled':not sweep_reason and not w['battle'] and w['active'],'reason':sweep_reason,'consume':'挑战资格1；立即成功消费','preview':rewards+'；重复灵石%d、地域材料3'%(10*difficulty),'action':{'id':'world_dungeon_sweep','params':sweep_params}}
                add('exploration','world_dungeon_sweep','扫荡第%d章%s · %s'%(chapter,definition['name'],data['name']),'挑战资格1，不耗丹符',rewards+'；重复灵石%d、地域材料3，不产生首通'%(10*difficulty),sweep_params,sweep_reason)
                add('exploration','world_dungeon_enter','第%d章%s · %s'%(chapter,definition['name'],data['name']),'免费；失败不扣成功保底','敌强固定不随升级抬涨。'+mechanic+' '+rewards+'。'+eligible,{'dungeon':dungeon,'chapter':chapter,'difficulty':difficulty},reason)
    period=r['boss'].get(d);active=w['battle'] if w['battle'] and w['battle']['kind']=='world_boss' else None
    boss=dict(encounter=period['encounter'] if period else '本UTC日尚未创建',attempts='%d / 3'%(period['attempts'] if period else 0),current_damage=str(active['player_damage'] if active else period['last_damage'] if period else 0),best=str(period['best'] if period else 0),reference=str(period['reference'] if period else R.BOSS['reference_base']+R.BOSS['reference_stage']*w['stage']),paid='币%d / 宝尘%d'%(period['paid_coin'],period['paid_dust']) if period else '币0 / 宝尘0',next='',status='尚未挑战')
    if period:
        reference=period['reference'];best=period['best'];coin,dust=boss_entitlement(period);delta=(coin-period['paid_coin'],dust-period['paid_dust'])
        boss['status']='进行中：第%d / 12回合'%(active['commands']+1) if active else '可补领币%d、宝尘%d'%delta if any(delta) else '已结算或成绩无新差额'
        next_band=next((b for b in R.BOSS['bands'] if best*b['den']<reference*b['num']),None)
        boss['next']='本期2R奖励已封顶：最多62币/8宝尘。' if best>=2*reference else ('下一档%s还差%d有效伤害；'%(next_band['name'],(reference*next_band['num']+next_band['den']-1)//next_band['den']-best) if next_band else '')+'每提高约R/30伤害进一步增加1币；不累计多场伤害。'
    add('exploration','world_boss_enter','挑战本期世界Boss','UTC日最多3次正式尝试','独立12回合，单次最高伤害，同行/NPC不计分，败退或退出按实际成绩结算','' or {},'本期尝试已用完。' if period and period['attempts']>=3 else '请先结束当前探索。' if w['exploration'] or w['dungeon'] else '')
    for date,record in r['boss'].items():
        coins,dust=boss_entitlement(record);delta=(coins-record['paid_coin'],dust-record['paid_dust'])
        if any(delta):add('exploration','world_boss_claim','领取'+date+'Boss新差额','不消耗','只补币%d、宝尘%d；重复无新权益不再发'%delta,{'day':date})
    section('exploration','世界Boss · NPC模拟',[(k,v) for k,v in [('本次有效伤害',boss['current_damage']),('本期最高',boss['best']),('已领',boss['paid']),('下一进展',boss['next']),('尝试',boss['attempts'])]],body=boss['status'])
    phase=100 if balance>=required*1_000_000 else 75 if balance*4>=required*3_000_000 else 50 if balance*2>=required*1_000_000 else 25 if balance*4>=required*1_000_000 else 0
    for stage in range(w['stage']+1):
        for tier,definition in R.MILESTONES.items():
            key='%d:%d'%(stage,tier);entry=r['milestones'].get(key);unlocked=stage<w['stage'] or balance*100>=cost(stage)*tier*1_000_000
            if entry and entry['claimed']:continue
            if not entry:
                branches=[('herb','交付药草2'),('pill','接取后炼回元丹')] if tier==25 else list(C.ARTS.items()) if tier==50 else [('secret','接取后通关任一秘境'),('commission','接取后完成材料课业')]
                if tier==50 and all(level>=3 for level in w['arrays'].values()):branches=[(k,v) for k,v in branches if k!='formations']
                add('quests','world_milestone_accept','第%d境 %d%% · %s'%(stage,tier,definition['name']),'可选，不阻断突破','仅材料/熟练奖励，不给额外修为',{'stage':stage,'tier':tier},'' if unlocked else '尚未达到本阶段精确进度。',fields=[{'name':'branch','label':'选择目标','type':'select','required':True,'options':[{'value':k,'label':v} for k,v in branches]}])
            else:
                branch=entry['branch'];reason=''
                if tier==25:
                    if branch=='herb':reason=affordability({'herb':2})
                    elif r['crafted_recipes']['pill']<=entry['pills']:reason='请在接取后炼成回元丹。'
                elif tier==50:
                    if r['crafted'][branch]<=entry['crafts'][branch] or r['used'][branch]<=entry['used'][branch]:reason='接取后需所选技艺制造并实际使用一次。'
                elif branch=='secret' and r['secret_count']<=entry['secrets'] or branch=='commission' and r['daily_count']<=entry['commissions']:reason='接取后需通关秘境或完成材料课业。'
                add('quests','world_milestone_claim','交付第%d境%d%%小目标'%(stage,tier),'达到接取后的任务条件','奖励材料或技艺熟练5，不提高额外修炼速率',{'stage':stage,'tier':tier},reason)
    conditions=world._advance_reason(w) if w['stage']<7 else '渡劫首胜、三秘境、主线备阵与51840修为。'
    if not w['ending'] and balance<required*1_000_000:conditions='距离%s还差%.3f修为；在线离线持续潜修，修炼法宝只提高未来速率。'%('渡劫圆满封界' if w['stage']==7 else R.STAGES[w['stage']+1]['name'],(required*1_000_000-balance)/1_000_000)
    if w['ending']:conditions='凡界已封；持续修为计潜修储备，仙界未开放。'
    for section_view in pages['character']['sections']:
        for row in section_view['rows']:
            if row['label']=='下一关':row['value']=conditions
    summary=dict(mode='longline',capacity={'used':len(r['instances']),'max':INSTANCE_CAP},speed_bonus_bp=growth_bonus_bps(state),items=items,
        materials=[{'label':material_name(k),'value':str(v)} for k,v in r['materials'].items()],pending=[{'id':k,'label':item_name(v['item']['template_id']) if v['item'] else _cost_label(v['materials']),'source':v['source']} for k,v in r['pending'].items()],dungeons=dungeon_views,boss=boss,
        progress={'required':required,'stage_label':R.STAGES[w['stage']]['name'],'next_label':'渡劫圆满封界' if w['stage']==7 else R.STAGES[w['stage']+1]['name'],'milestone_label':{0:'初期',25:'中期',50:'后期',75:'小境界圆满·蓄势封界' if w['stage']==7 else '小境界圆满·蓄势待破',100:'修为已足'}[phase],'conditions':conditions,'ready':not world._advance_reason(w) if w['stage']<7 else w['xp']>=required})
    if credits is not None:summary['credits']=credits
    view['loot']=summary;view['summary']=conditions
    journey.project(state,view,add)
    if context:
        activity_view=activities.project(state,context)
        pages['quests']['sections'].extend(activity_view['sections']);pages['quests']['actions'].extend(activity_view['actions'])
        view['activities']={'sections':activity_view['sections']}
    finish_action=next((a for a in pages['character']['actions'] if a['id']==('world_finish' if w['stage']==7 else 'world_advance')),None)
    summary['progress']['ready']=bool(finish_action and finish_action['enabled'] and not w['ending'])
    if w['ending']:summary['progress'].update(required=0,reserve=True,next_label='潜修储备',milestone_label='凡界已封界')
    goals=[]
    def goal(action_id,title,reason,filters=None,enabled_only=False):
        filters=filters or {}
        for page in view['pages']:
            for action in page['actions']:
                if action['id']!=action_id or any(action['params'].get(k)!=v for k,v in filters.items()) or enabled_only and not action['enabled']:continue
                identity=(page['id'],action['id'],tuple(sorted(action['params'].items())))
                if any(g['_identity']==identity for g in goals):return
                goals.append({'id':'goal:'+str(len(goals)+1),'title':title,'reason':reason or action['reason'] or action['effect'],'page':page['id'],'target_page':page['id'],'action':{'id':action['id'],'params':dict(action['params'])},'_identity':identity})
                return
    if w['battle']:
        goal('world_auto_battle','先完成当前交锋','选一种自动斗法策略，法宝会随真实冷却自动出击与回护。',{'strategy':'balanced'},enabled_only=True)
    goal('world_story_claim','领取已经完成的首周故事','领取这一段的实物或自选器物后，可开启下一段。',enabled_only=True)
    goal('world_activity_claim','领取已经完成的双目标项目','这些非XP材料可投入法宝/强化，完成权益可跨周期保留。',enabled_only=True)
    if not w['ending']:
        goal('world_finish' if w['stage']==7 else 'world_advance','推进当前大境界','修为和必要条件均由服务端检查。',enabled_only=True)
    goal('world_story_accept','继续首周故事链','按实际境界和前段领奖解锁，不用等待建议日期。',enabled_only=True)
    goal('world_elite_enter','挑战当前故事精英','固定敌强，先查看反制；免费重试，不消耗副本资格。',enabled_only=True)
    goal('world_loot_claim','领取保留的掉落权益','仓满不会丢物，清出容量后完整领取。',enabled_only=True)
    if not any(r['equipped'][slot] for slot in R.EQUIPMENT_SLOTS):
        goal('world_craft','先做一件可用器物','安全采集→四艺凡品→装备实例→低难/强化，提高挑战能力。',{'recipe':'blade'})
    unselected=next((i for i in r['instances'].values() if i['effect_type']=='unselected'),None)
    if unselected:goal('world_loot_choose','为新法宝确定成长方向','修炼型提高未来速率；战力型帮助副本与Boss，两类不兼得。',{'uid':unselected['uid']})
    else:
        unmounted=next((i for uid,i in r['instances'].items() if i['template_id'] in R.TREASURES and uid not in r['equipped'].values()),None)
        if unmounted:goal('world_loot_equip','比较并装备法宝','看当前/候选属性与每小时修炼变化，不追溯已经离线的时段。',{'uid':unmounted['uid']})
        elif any(r['equipped'][slot] is None for slot in ['main','guard']):
            goal('world_loot_craft_treasure','用保底材料做法宝','低难宝尘或Boss币兑换可取得宝尘，不依赖稀有运气。',enabled_only=True)
    if period and period['attempts']<R.BOSS['daily_attempts']:
        goal('world_boss_enter','试一次更高的个人有效伤害',boss['next'],enabled_only=True)
    goal('world_rest','免费恢复后继续挑战','气血与灵力恢复不影响全天持续修炼。',enabled_only=True)
    goal('world_gather','安全补齐材料缺口','基础材料可再生，免费采集不发额外修为。',{'item':'ore'},enabled_only=True)
    view['goals']=[{k:v for k,v in g.items() if k!='_identity'} for g in goals[:3]]
    if view.get('battle'):
        battle=w['battle'];statuses=[];counterplay='敌方按常击→蓄势→重击循环；自动斗法会在重击前防御、必要时补给，法宝按冷却独立出击。'
        if battle.get('mechanic'):
            definition=G.ELITES[battle['target']] if battle['kind']=='elite' else G.DUNGEON_MECHANICS[battle['target']]
            statuses.append({'label':'独特机制','value':definition['name']});counterplay=definition['description']
            if battle['mechanic']=='venom':statuses.extend([{'label':'残留毒','value':'%d次，每次%d固定伤害'%(battle['poison_turns'],battle['poison_damage'])}])
            if battle['mechanic']=='furnace_shield':statuses.append({'label':'熔炉护盾','value':str(battle['barrier'])})
            if battle['mechanic']=='mana_seal':statuses.append({'label':'常击汲灵','value':'未防/未镇魂扣最多6MP；零MP仍可普攻'})
        if battle['kind']=='world_boss':statuses.append({'label':'个人评分','value':'%d伤害；%d / 12回合'%(battle['player_damage'],battle['commands'])});counterplay='只计玩家本场有效伤害，同行不计；提前退出或败退也按实际成绩比较best。'
        view['battle']['statuses']=statuses;view['battle']['counterplay']=counterplay
    for resource in view['resources']:
        if resource['id']=='world_xp':resource['max']=None
    for page in view['pages']:
        found=False
        for a in page['actions']:
            a['primary']=bool(a['enabled'] and not found)
            if a['primary']:found=True
            a['detail']=a['label']+'：'+a['cost']+'；'+a['effect']+'。'
