"""Deterministic, bounded combat laboratory. No production state or rewards."""
import copy
import hashlib
import json

VERSION=1
MAX_TICKS=120
RULES={'player_attack':100,'player_hp':600,'player_mp':60,'skill_mp':18,'skill_cd':3,'skill_damage':200,'sustain_damage':40,'sustain_cd':2,'sustain_initial':[0,1],'burst_damage':120,'burst_cd':6,'burst_initial':[2,4],'shield_hp':90,'shield_cd':4,'shield_initial':0,'item_cd':3,'boss_reference':990,'boss_reward_cap':1980}
BUDGET_LIMITS={'pill_budget':3,'fire_budget':2,'guard_budget':2,'soul_budget':2}
SCENARIOS={'den':'毒巢试炼','forge':'熔炉试炼','tower':'沉星试炼','boss':'世界Boss十二拍','dungeon':'三战副本'}
BUILDS={'sustain':'双持续宝','burst':'双爆发宝','guard':'持续与护持'}
STRATEGIES={'balanced':'均衡反制','aggressive':'强攻优先'}
DEFAULTS=dict(scenario='den',build='sustain',strategy='balanced',pill_budget=0,fire_budget=0,guard_budget=0,soul_budget=0,npc=False)


def configuration():
    r=RULES
    descriptions={
        'den':'气血1260；未防重击挂毒12×随后两机会，丹清毒、防重击免新毒。',
        'forge':'气血1260、一次盾315；有盾火符破盾200且不溢出。',
        'tower':'气血1260；未防常击抽最多6MP，防御/镇魂免抽。',
        'boss':'12个玩家机会；个人攻击与法宝计分，同行排除，R990/封顶1980。',
        'dungeon':'三场混合机制连战；气血/灵力、全程预算与玩家CD承接，无营地自动恢复。',
        'balanced':'先判断可终结，再按丹药、破盾、致死镇魂、低蓝汲灵反制、防重击与蓄势护符排序。',
        'aggressive':'先判断可终结，气血≤25%且有授权丹才服丹，其余技能/普攻；不自动使用三符。',
    }
    details=[
        {'value':'sustain','label':BUILDS['sustain'],'effect':'两宝各造成%d伤害，自动持续出手。'%r['sustain_damage'],'cd':'两宝各CD%d个玩家机会。'%r['sustain_cd'],'initial_delay':'主宝起始t%d，副宝起始t%d。'%tuple(r['sustain_initial'])},
        {'value':'burst','label':BUILDS['burst'],'effect':'两宝各造成%d伤害，启动较慢、错峰爆发。'%r['burst_damage'],'cd':'两宝各CD%d个玩家机会。'%r['burst_cd'],'initial_delay':'主宝起始t%d，副宝起始t%d。'%tuple(r['burst_initial'])},
        {'value':'guard','label':BUILDS['guard'],'effect':'主宝持续%d伤害；副宝在将受重击或气血≤40%%时提供%d护盾，替换剩余值、不叠加，持续2个敌方机会。'%(r['sustain_damage'],r['shield_hp']),'cd':'主宝CD%d；护持宝CD%d。'%(r['sustain_cd'],r['shield_cd']),'initial_delay':'主宝起始t%d；护持宝起始t%d可用，满足条件才触发。'%(r['sustain_initial'][0],r['shield_initial'])},
    ]
    descriptions.update({v['value']:v['effect']+' '+v['cd']+' '+v['initial_delay'] for v in details})
    def options(values):return [{'value':k,'label':v,'description':descriptions[k]} for k,v in values.items()]
    return {'experimental':True,'config_version':VERSION,'persistent':False,'rewards':False,'defaults':dict(DEFAULTS),
        'scenarios':options(SCENARIOS),'builds':options(BUILDS),'strategies':options(STRATEGIES),
        'limits':dict(BUDGET_LIMITS,ticks=MAX_TICKS,boss_ticks=12),'rules':copy.deepcopy(r),'build_details':details,
        'preparation_rules':{
            'common':['固定气血%d、灵力%d、攻击%d；不开放任意数值注入。'%(r['player_hp'],r['player_mp'],r['player_attack']),
                '归元斩造成%d伤害，消耗%dMP，CD%d，起始t0可用；灵力不足回退合法普攻/防御。'%(r['skill_damage'],r['skill_mp'],r['skill_cd']),
                '普攻100伤害并回2MP；防御回6MP且敌方物理伤害减半。',
                '每拍1主行动→主宝→副宝→同行→敌方机会；任意一段击杀立即结束后序动作。',
                'CD按玩家机会：t0使用CD3技能，下次t3可用；动画倍速、暂停不改变CD。'],
            'consumables':['丹药与三符均占本拍唯一主行动；各自CD%d，预算只在真实使用时扣除。'%r['item_cd'],
                '默认预算全0；本次上限：丹%d、火符%d、护符%d、魂符%d。预算与策略全程冻结。'%(BUDGET_LIMITS['pill_budget'],BUDGET_LIMITS['fire_budget'],BUDGET_LIMITS['guard_budget'],BUDGET_LIMITS['soul_budget']),
                '丹恢复最多80HP/20MP并清毒；火符有盾仅破盾、无溢出；护符减伤25%%；魂符跳过敌方机会但不免旧毒。'.replace('25%%','25%'),
                '同行每3拍10伤，初始t2；Boss个人成绩不计同行。']},
        'notice':'独立自动战斗实验；无正式存档、资格、奖励或排行榜。'}


def validate_input(data):
    if not isinstance(data,dict) or set(data)-set(DEFAULTS):raise ValueError('输入仅允许实验白名单字段。')
    if not {'scenario','build','strategy'}<=set(data):raise ValueError('须选择场景、构筑和策略。')
    p=dict(DEFAULTS,**data)
    for name,catalog in [('scenario',SCENARIOS),('build',BUILDS),('strategy',STRATEGIES)]:
        if not isinstance(p[name],str) or p[name] not in catalog:raise ValueError('未知'+name+'。')
    for key,limit in BUDGET_LIMITS.items():
        if type(p[key]) is not int or not 0<=p[key]<=limit:raise ValueError(key+'超出允许整数预算。')
    if type(p['npc']) is not bool:raise ValueError('npc须为布尔值。')
    return p


def _enemy(kind,index=1):
    names={'den':'毒巢守卫','forge':'炉甲守卫','tower':'沉星守卫','boss':'归墟世界Boss'}
    return dict(id=kind+':'+str(index),type=kind,name=names[kind],hp=10**12 if kind=='boss' else 1260,max_hp=10**12 if kind=='boss' else 1260,attack=66 if kind=='boss' else 99,heavy=110 if kind=='boss' else 165,barrier=315 if kind=='forge' else 0,intent='常规攻击')


def simulate(data,initial=None):
    """initial is an engine-only controlled-fixture hook; never accepted by HTTP."""
    p=validate_input(data)
    player=dict(hp=RULES['player_hp'],max_hp=RULES['player_hp'],mp=RULES['player_mp'],max_mp=RULES['player_mp'])
    if initial is not None:
        if not isinstance(initial,dict) or set(initial)-{'hp','mp'}:raise ValueError('未知fixture字段。')
        for k,v in initial.items():
            if type(v) is not int or not (0 if k=='mp' else 1)<=v<=player['max_'+k]:raise ValueError('fixture数值越界。')
            player[k]=v
    path=['den','forge','tower'] if p['scenario']=='dungeon' else [p['scenario']]
    nodes=[dict(id=i+1,label=SCENARIOS[k],status='locked' if i else 'active') for i,k in enumerate(path)]
    enemies=[_enemy(k,i+1) for i,k in enumerate(path)]
    # Dungeon has two lighter, fixed approach fights and one full mechanism boss.
    if len(enemies)>1:
        for enemy,hp,atk,heavy in zip(enemies[:2],[420,630],[30,45],[50,75]):enemy.update(hp=hp,max_hp=hp,attack=atk,heavy=heavy,barrier=hp//4 if enemy['type']=='forge' else 0)
    canonical=json.dumps({'version':VERSION,'input':p,'initial':initial},sort_keys=True,separators=(',',':'))
    sid=hashlib.sha256(canonical.encode()).hexdigest()[:20]
    events=[];frames=[];used={k:0 for k in ['pill','fire','guard','soul']};metrics=dict(player_damage=0,direct_damage=0,treasure_damage=0,npc_damage=0,damage_taken=0,damage_prevented=0,mp_spent=0,skill_uses=0,treasure_triggers=0)
    node=0;enemy=enemies[0];poison=0;guard_turns=0;barrier=0;barrier_turns=0;enemy_turn=0
    ready={'skill':0,'main':RULES['burst_initial'][0] if p['build']=='burst' else RULES['sustain_initial'][0],'secondary':RULES['burst_initial'][1] if p['build']=='burst' else RULES['shield_initial'] if p['build']=='guard' else RULES['sustain_initial'][1],'npc':2,'pill':0,'fire':0,'guard':0,'soul':0}
    cds={'skill':RULES['skill_cd'],'main':RULES['burst_cd'] if p['build']=='burst' else RULES['sustain_cd'],'secondary':RULES['burst_cd'] if p['build']=='burst' else RULES['shield_cd'] if p['build']=='guard' else RULES['sustain_cd'],'npc':3,'pill':RULES['item_cd'],'fire':RULES['item_cd'],'guard':RULES['item_cd'],'soul':RULES['item_cd']}
    labels={'skill':'归元斩','main':'本命爆发' if p['build']=='burst' else '本命持续','secondary':'护持屏障' if p['build']=='guard' else '护持爆发' if p['build']=='burst' else '护持持续','npc':'同行支援','pill':'回元丹','fire':'焚火符','guard':'护身符','soul':'镇魂符'}
    def snapshot():return {'player':copy.deepcopy(player),'enemy':copy.deepcopy(enemy)}
    def emit(t,kind,source,target,label,amount=None):
        event=dict(id=sid+':'+str(len(events)+1),tick=t,node=node+1,type=kind,source=source,target=target,label=label)
        if amount is not None:event['amount']=amount
        events.append(event)
    def hit(t,amount,source,label,fire=False):
        nonlocal enemy
        if enemy['barrier']:
            blocked=min(enemy['barrier'],200 if fire else amount);enemy['barrier']-=blocked
            emit(t,'shield',source,'enemy','破盾：'+label,blocked)
            if fire:return
            amount-=blocked
        actual=min(enemy['hp'],amount);enemy['hp']-=actual
        if actual:
            emit(t,'damage',source,'enemy',label,actual)
            key='npc_damage' if source=='npc' else 'treasure_damage' if source in {'main','secondary'} else 'direct_damage'
            metrics[key]+=actual
            if source!='npc':metrics['player_damage']+=actual
    def frame(t,before,start_index,decision='准备',decision_reason='战斗初态，尚未出招。'):
        enemy['intent']=['常规攻击','蓄势','重击'][enemy_turn%3];after=snapshot()
        frames.append(dict(tick=t,node=node+1,player=copy.deepcopy(player),enemy=copy.deepcopy(enemy),before=before,after=after,decision=decision,decision_reason=decision_reason,
            cooldowns=[dict(id=k,name=labels[k],remaining=max(0,ready[k]-t),total=cds[k]) for k in ready if k!='npc' or p['npc']],
            statuses=[{'label':'残毒','value':str(poison)},{'label':'玩家护盾','value':str(barrier)},{'label':'护身符剩余','value':str(guard_turns)}],events=copy.deepcopy(events[start_index:]),nodes=copy.deepcopy(nodes)))
    frame(0,snapshot(),0)
    outcome='stalemate';reason='达到120拍上限，实验停止；无正式损失或收益。';ticks=0
    for t in range(MAX_TICKS):
        ticks=t+1;before=snapshot();start=len(events);heavy=enemy_turn%3==2;normal=enemy_turn%3==0;old_poison=poison;skip=False;defending=False;immune=False
        can=lambda name:used[name]<p[name+'_budget'] and t>=ready[name]
        attack_bonus=sum(RULES['burst_damage'] if p['build']=='burst' else RULES['sustain_damage'] for slot in ['main','secondary'] if t>=ready[slot] and not (slot=='secondary' and p['build']=='guard'))
        # Forecast only legal player channels, excluding NPC support and absent MP.
        attack_kill=RULES['player_attack']+attack_bonus>=enemy['barrier']+enemy['hp']
        skill_legal=t>=ready['skill'] and player['mp']>=RULES['skill_mp']
        skill_kill=skill_legal and RULES['skill_damage']+attack_bonus>=enemy['barrier']+enemy['hp']
        action='skill' if skill_legal else 'attack'
        decision_reason='归元斩就绪且灵力足够。' if skill_legal else '归元斩冷却或灵力不足，普攻回灵。'
        if attack_kill:action='attack';decision_reason='普攻与本拍可用攻击宝足以终结，优先节省灵力。'
        elif skill_kill:action='skill';decision_reason='归元斩与本拍可用攻击宝足以终结，优先结束战斗。'
        elif p['strategy']=='balanced':
            if can('pill') and (player['hp']<=240 or old_poison or (enemy_turn%3==1 and player['mp']<RULES['skill_mp'])):action='pill';decision_reason='均衡策略：授权丹药满足低血、旧毒或蓄势补灵条件。'
            elif enemy['barrier']>=100 and can('fire'):action='fire';decision_reason='敌盾至少100，使用已授权火符破盾。'
            elif heavy and max(0,(enemy['heavy']//2*(3 if guard_turns else 4)//4)-barrier)>=player['hp'] and can('soul'):action='soul';decision_reason='预测防御后仍致死，用已授权镇魂跳过重击。'
            elif enemy['type']=='tower' and normal and player['mp']<RULES['skill_mp'] and can('soul'):action='soul';decision_reason='汲灵常击且当前低蓝，用已授权镇魂保留灵力。'
            elif heavy or (enemy['type']=='tower' and normal and player['mp']<RULES['skill_mp']):action='defend';decision_reason='防御反制重击或低蓝时的汲灵常击，同时回灵。'
            elif enemy_turn%3==1 and player['hp']<=2*enemy['heavy'] and not guard_turns and can('guard'):action='guard';decision_reason='敌方蓄势、血量偏低且未有护符，提前施放已授权护符。'
        elif player['hp']<=150 and can('pill'):action='pill';decision_reason='强攻策略：气血不超过25%，使用已授权丹药。'
        if action in used:ready[action]=t+cds[action]
        if action=='pill':
            used['pill']+=1;hp=min(80,player['max_hp']-player['hp']);mp=min(20,player['max_mp']-player['mp']);player['hp']+=hp;player['mp']+=mp;poison=0;old_poison=0;immune=True
            emit(ticks,'heal','player','player','服丹恢复气血',hp);emit(ticks,'mana','player','player','服丹恢复灵力',mp)
        elif action=='defend':
            defending=True;amount=min(6,player['max_mp']-player['mp']);player['mp']+=amount;emit(ticks,'defend','player','player','防御并回灵',amount)
        elif action=='fire':used['fire']+=1;hit(ticks,150,'player','焚火符',fire=True)
        elif action=='guard':used['guard']+=1;guard_turns=2;emit(ticks,'buff','player','player','护身符减伤25%，持续两机会',2)
        elif action=='soul':used['soul']+=1;skip=True;emit(ticks,'control','player','enemy','镇魂符跳过本次敌方机会',1)
        elif action=='skill':
            player['mp']-=RULES['skill_mp'];metrics['mp_spent']+=RULES['skill_mp'];metrics['skill_uses']+=1;ready['skill']=t+RULES['skill_cd'];emit(ticks,'mana','player','player','归元斩耗灵',-RULES['skill_mp']);hit(ticks,RULES['skill_damage'],'player','归元斩')
        else:
            hit(ticks,RULES['player_attack'],'player','普攻');amount=min(2,player['max_mp']-player['mp']);player['mp']+=amount;emit(ticks,'mana','player','player','普攻回灵',amount)
        for slot in ['main','secondary']:
            if enemy['hp']<=0:break
            if t<ready[slot]:continue
            if slot=='secondary' and p['build']=='guard':
                if not heavy and player['hp']>240:continue
                barrier=RULES['shield_hp'];barrier_turns=2;ready[slot]=t+RULES['shield_cd'];metrics['treasure_triggers']+=1;emit(ticks,'shield',slot,'player','护持宝屏障',RULES['shield_hp'])
            else:
                ready[slot]=t+cds[slot];metrics['treasure_triggers']+=1;hit(ticks,RULES['burst_damage'] if p['build']=='burst' else RULES['sustain_damage'],slot,labels[slot])
        if p['npc'] and enemy['hp']>0 and t>=ready['npc']:ready['npc']=t+3;hit(ticks,10,'npc','同行支援（不计个人Boss伤害）')
        if enemy['hp']<=0:
            nodes[node]['status']='complete';emit(ticks,'victory','player','enemy','战斗胜利')
            frame(ticks,before,start,action,decision_reason)
            if node==len(enemies)-1:outcome='win';reason='所有实际战斗节点完成。';break
            node+=1;enemy=enemies[node];nodes[node]['status']='active';enemy_turn=0;poison=0
            continue
        raw=[enemy['attack'],0,enemy['heavy']][enemy_turn%3]
        damage=0 if skip else raw//2 if defending else raw
        if guard_turns:damage=damage*3//4
        absorbed=min(barrier,damage);barrier-=absorbed;damage-=absorbed;metrics['damage_prevented']+=raw-damage
        if absorbed>0:emit(ticks,'shield_absorb','secondary','player','护持宝实际拦截',absorbed)
        actual=min(player['hp'],damage);player['hp']-=actual;metrics['damage_taken']+=actual;emit(ticks,'damage','enemy','player','敌方'+['常击','蓄势','重击'][enemy_turn%3],actual)
        if old_poison and not immune and player['hp']>0:
            amount=min(player['hp'],12);player['hp']-=amount;metrics['damage_taken']+=amount;poison=old_poison-1;emit(ticks,'poison','enemy','player','旧毒结算',amount)
        if enemy['type']=='den' and heavy and not skip and not defending and not immune and player['hp']>0:poison=2;emit(ticks,'status','enemy','player','新毒：随后两机会',2)
        if enemy['type']=='tower' and normal and not skip and not defending:
            amount=min(6,player['mp']);player['mp']-=amount;emit(ticks,'mana','enemy','player','常击汲灵',-amount)
        enemy_turn+=1;guard_turns=max(0,guard_turns-1);barrier_turns=max(0,barrier_turns-1)
        if not barrier_turns:barrier=0
        frame(ticks,before,start,action,decision_reason)
        if player['hp']<=0:outcome='loss';reason='气血归零，实验败退；无正式损失。';break
        if p['scenario']=='boss' and ticks>=12:outcome='window';reason='12个玩家行动机会结束；NPC伤害不计个人成绩。';break
    metrics.update(outcome=outcome,rounds=ticks,end_reason=reason,pills_used=used['pill'],fire_used=used['fire'],guard_used=used['guard'],soul_used=used['soul'],talismans_used=sum(used[k] for k in ['fire','guard','soul']),boss_reference=990,boss_capped_score=min(1980,metrics['player_damage']) if p['scenario']=='boss' else 0)
    return dict(ok=True,experimental=True,simulation_id=sid,config_version=VERSION,input=p,result={'outcome':outcome,'ticks':ticks},frames=frames,events=events,metrics=metrics,nodes=nodes,notice='实验仿真，无正式存档/奖励/资格。')
