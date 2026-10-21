"""Pure deterministic rules; no HTTP, disk, clocks or randomness."""
import unicodedata
from . import config as C
from . import world
from . import loot
from .clone import clone


class GameError(Exception):
    def __init__(self, code, message, status=422):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def fail(message):
    raise GameError('ACTION_UNAVAILABLE', message)


def valid_int(value, low, high):
    return type(value) is int and low <= value <= high


def validate_name(name):
    if not isinstance(name, str):
        raise GameError('BAD_REQUEST', '姓名必须为文字。', 400)
    name = name.strip() or "归墟客"
    if not 1 <= len(name) <= 12 or any(unicodedata.category(c).startswith('C') for c in name):
        raise GameError('BAD_REQUEST', '姓名须为1至12个可显示字符。', 400)
    return name


def legacy_new_game(name):
    return dict(name=validate_name(name), realm=0, cultivation=0, hp=60, mp=12,
                stones=0, herbs=0, pills=0, technique=0, region='village',
                victories=[], battle=None, completed=False, actions_taken=0,
                logs=['第0行 · 初入青岚村，一卷归元诀开启修行。'])


def validate_legacy_state(s):
    if s is None:
        return
    if not isinstance(s, dict) or set(s) - {'qi_at'} != set(legacy_new_game('归墟客')):
        raise ValueError('进度数据字段不完整或不受支持')
    if s.get('qi_at') is not None and not valid_int(s['qi_at'],0,2**63-1):
        raise ValueError('吐纳时间水位无效')
    try:
        stored_name=validate_name(s['name'])
    except GameError as exc:
        raise ValueError('姓名无效') from exc
    if stored_name != s['name']:
        raise ValueError('姓名无效')
    for key, hi in [('realm',3),('technique',2),('cultivation',9999),('stones',9999),('herbs',9999),('pills',9999),('actions_taken',2**63-1)]:
        if not valid_int(s[key],0,hi):
            raise ValueError('进度数据数值无效：'+key)
    if not valid_int(s['hp'],1,C.HP[s['realm']]) or not valid_int(s['mp'],0,C.MP[s['realm']]):
        raise ValueError('气血或灵力无效')
    if not isinstance(s['region'],str) or s['region'] not in C.REGIONS or C.REGIONS[s['region']]['realm'] > s['realm']:
        raise ValueError('区域无效')
    if not isinstance(s['victories'],list) or any(not isinstance(v,str) or v not in C.ENEMIES for v in s['victories']) or len(s['victories']) != len(set(s['victories'])):
        raise ValueError('首胜记录无效')
    if any(C.ENEMIES[v]['realm']>s['realm'] for v in s['victories']):
        raise ValueError('首胜与境界不一致')
    if type(s['completed']) is not bool or s['completed'] != ('shadow' in s['victories']):
        raise ValueError('结局记录无效')
    if s['realm'] >= 2 and 'ape' not in s['victories'] or s['realm'] >= 3 and 'sentinel' not in s['victories']:
        raise ValueError('境界缺少必要首胜')
    if not isinstance(s['logs'],list) or len(s['logs']) > 100 or any(not isinstance(v,str) or len(v)>1000 for v in s['logs']):
        raise ValueError('日志无效')
    b=s['battle']
    if b is not None:
        if not isinstance(b,dict) or set(b) != {'enemy','hp','turn'} or not isinstance(b['enemy'],str) or b['enemy'] not in C.ENEMIES:
            raise ValueError('战斗无效')
        e=C.ENEMIES[b['enemy']]
        if not valid_int(b['hp'],1,e['hp']) or not valid_int(b['turn'],0,2**63-1) or e['region'] != s['region'] or e['realm']>s['realm'] or b['enemy']=='shadow' and s['completed']:
            raise ValueError('战斗状态无效')


def new_game(name,mode="free"):
    if mode not in {"free","longline"}:raise GameError("BAD_REQUEST","游戏模式无效。",400)
    state=legacy_new_game(name)
    state['world']=world.initial_state()
    if mode=='longline':state['world']['r3']=loot.initial_state()
    return state


def validate_state(s):
    if s is None:
        return
    if not isinstance(s,dict) or 'world' not in s:
        raise ValueError('进度数据缺少完整世界数据')
    legacy={k:v for k,v in s.items() if k!='world'}
    validate_legacy_state(legacy)
    world.validate(s)


MANUAL_STEPS = {'attack', 'power_attack', 'defend', 'use_pill', 'flee'}  # 序章内部单拍，不再对外开放
AUTO_LIMIT = 60


def check(s, action, params):
    if s is None:
        raise GameError('NO_GAME','请先创建角色。')
    if not isinstance(action,str) or not isinstance(params,dict):
        raise GameError('BAD_REQUEST','行动和参数格式不正确。',400)
    known={'rest','gather','alchemy','explore','upgrade','buy_pill','sell_herbs','breakthrough','challenge','travel','attack','power_attack','defend','use_pill','flee','auto_battle'}
    if action not in known:
        raise GameError('BAD_REQUEST','未知行动。',400)
    expected={'region'} if action=='travel' else {'enemy'} if action=='challenge' else set()
    if set(params)!=expected or any(not isinstance(v,str) for v in params.values()):
        raise GameError('BAD_REQUEST','行动参数不正确。',400)
    battle_action=action in MANUAL_STEPS|{'auto_battle'}
    if bool(s['battle']) != battle_action:
        fail('战斗中无法进行此行动。' if s['battle'] else '当前不在战斗中。')
    r=s['realm']
    if action=='travel':
        target=params['region']
        if target not in C.REGIONS: fail('未知区域。')
        if C.REGIONS[target]['realm']>r: fail('境界不足，区域尚未解锁。')
        if target==s['region']: fail('已在此地。')
    elif action=='challenge':
        target=params['enemy']
        if target not in C.ENEMIES: fail('未知敌人。')
        e=C.ENEMIES[target]
        if e['region'] != s['region']: fail('敌人不在当前区域。')
        if e['realm']>r: fail('需要筑基后方可挑战。')
        if target=='shadow' and s['completed']: fail('归墟已平，无需再战。')
    elif action=='rest' and s['hp']==C.HP[r] and s['mp']==C.MP[r]: fail('气血和灵力均已充盈。')
    elif action=='gather' and s['herbs']==9999: fail('药草已达上限。')
    elif action in {'alchemy','buy_pill'}:
        if s['pills']==9999: fail('回春丹已达上限。')
        if action=='alchemy' and s['herbs']<3: fail('需要3株药草。')
        if action=='buy_pill' and s['stones']<8: fail('需要8枚灵石。')
    elif action=='explore' and s['stones']==9999 and s['herbs']==9999: fail('探索所得均已达上限。')
    elif action=='upgrade':
        if s['technique']==2: fail('归元诀已达满级。')
        if s['stones'] < [12,24][s['technique']]: fail('灵石不足，升级需要%d枚。'%[12,24][s['technique']])
    elif action=='sell_herbs':
        if s['herbs']<2: fail('需要2株药草。')
        if s['stones']==9999: fail('灵石已达上限。')
    elif action=='breakthrough':
        if r==3: fail('已稳固筑基，暂无下一境界。')
        if s['cultivation']<C.BREAKTHROUGH[r]: fail('修为不足，还差%d。'%(C.BREAKTHROUGH[r]-s['cultivation']))
        required={1:'ape',2:'sentinel'}.get(r)
        if required and required not in s['victories']: fail('需先战胜'+C.ENEMIES[required]['name']+'。')
    elif action=='power_attack' and s['mp']<6: fail('灵力不足，需要6点。')
    elif action=='use_pill':
        if s['pills']<1: fail('没有回春丹。')
        if s['hp']==C.HP[r] and s['mp']==C.MP[r]: fail('气血和灵力均已充盈。')


def apply_action(state, action, params, context=None):
    if isinstance(action,str) and action.startswith('world_'):
        result,events=world.apply_action(state,action,params,context=context)
        validate_state(result)
        return result,events
    if state and state.get('world',{}).get('active'):
        fail('已进入完整修仙界，请使用世界行动。')
    if action in MANUAL_STEPS:
        raise GameError('BAD_REQUEST','点击式战斗已退役，请使用自动斗法。',400)
    if action=='cultivate':
        raise GameError('BAD_REQUEST','吐纳已改为随时间自动进行，无需点击。',400)
    now=(context or {}).get('now')
    if now is not None:state=settle_qi(state,now)
    if action=='auto_battle':
        check(state,action,params)
        return _auto_battle(state,context)
    return _step(state,action,params)


def settle_qi(state,now):
    """序章吐纳随服务端时间自动结算：每 QI_SECONDS 秒 +1 修为，只补到当前境界瓶颈，不囤积离线时间。"""
    if state is None or state['world']['active'] or not valid_int(now,0,2**63-1):return state
    s=clone(state);last=s.get('qi_at')
    if last is None or now<=last:
        s['qi_at']=now;return s
    r=s['realm'];room=C.BREAKTHROUGH[r]-s['cultivation'] if r<3 else 0
    if room<=0:
        s['qi_at']=now;return s
    ticks=(now-last)//C.QI_SECONDS;gain=min(ticks,room)
    s['cultivation']+=gain
    s['qi_at']=now if gain==room else last+ticks*C.QI_SECONDS
    return s


def _choose(s):
    """Prelude auto-battle policy: returns one internal single-round action."""
    b=s['battle'];e=C.ENEMIES[b['enemy']];r=s['realm']
    atk=C.ATTACK[r]+2*s['technique'];turn=b['turn']%3;incoming=[e['attack'],0,e['heavy']][turn]
    if atk>=b['hp']:return 'attack'
    if s['mp']>=6 and atk*2>=b['hp']:return 'power_attack'
    not_full=s['hp']<C.HP[r] or s['mp']<C.MP[r]
    if s['pills']>0 and not_full and (s['hp']<=incoming or s['hp']*100<=C.HP[r]*40):return 'use_pill'
    if turn==2 and incoming*100>=s['hp']*35:return 'defend'
    return 'power_attack' if s['mp']>=6 else 'attack'


def _fx_events(hp0,hp1,foe0,foe1):
    """由本拍气血实际变化得出的可视特效事件（fx_only：只驱动演出，不进文字日志）。"""
    out=[]
    if foe0>foe1:out.append({'type':'damage','source':'player','target':'enemy','label':'命中','amount':foe0-foe1,'fx_only':True})
    if hp0>hp1:out.append({'type':'damage','source':'enemy','target':'player','label':'受创','amount':hp0-hp1,'fx_only':True})
    elif hp1>hp0:out.append({'type':'heal','source':'player','target':'player','label':'回复','amount':hp1-hp0,'fx_only':True})
    return out


def _auto_battle(state,context=None):
    s=state;events=[];labels={'attack':'普攻','power_attack':'运功强攻','defend':'凝神防御','use_pill':'服用回春丹','flee':'撤退'}
    enemy=C.ENEMIES[s['battle']['enemy']];r=s['realm'];intents=['常规攻击','蓄势','重击']
    frames=[{'round':0,'player':{'hp':s['hp'],'mp':s['mp']},'enemy':{'hp':s['battle']['hp'],'barrier':0},'intent':intents[s['battle']['turn']%3],'action':'准备','events':[]}]
    outcome='stalemate'
    for n in range(1,AUTO_LIMIT+1):
        if not s['battle']:break
        action=_choose(s)
        hp0,foe0=s['hp'],s['battle']['hp']
        s,ev=_step(s,action,{})
        events.extend('第%d拍·%s：%s'%(n,labels[action],line) for line in ev)
        text=''.join(ev)
        outcome='victory' if '战胜' in text else 'defeat' if '不敌' in text else outcome
        frames.append({'round':n,'player':{'hp':s['hp'],'mp':s['mp']},'enemy':{'hp':s['battle']['hp'] if s['battle'] else 0,'barrier':0},'intent':intents[s['battle']['turn']%3] if s['battle'] else '—','action':labels[action],
            'events':[{'type':'text','source':'player','target':'enemy','label':line} for line in ev]+_fx_events(hp0,s['hp'],foe0,s['battle']['hp'] if s['battle'] else 0)})
    else:
        s,ev=_step(s,'flee',{});events.extend(ev);outcome='stalemate'
    if isinstance(context,dict):
        context['battle_report']={'outcome':outcome,'rounds':frames[-1]['round'],'strategy':'balanced','strategy_label':'自动','enemy':{'name':enemy['name'],'max_hp':enemy['hp'],'kind':'prelude'},
            'player':{'max_hp':C.HP[r],'max_mp':C.MP[r]},'treasures':{'main':None,'guard':None},'frames':frames}
    return s,events


def _step(state,action,params):
    check(state,action,params)
    s=clone(state)
    events=[]
    r=s['realm']
    def add(key,amount,maximum=9999):
        old=s[key];s[key]=min(maximum,s[key]+amount);return s[key]-old
    if action=='travel':
        s['region']=params['region'];events.append('前往'+C.REGIONS[s['region']]['name']+'。')
    else:
        s['actions_taken']+=1
        if action=='rest': events.append('静养调息，气血 +%d，灵力 +%d。'%(add('hp',30,C.HP[r]),add('mp',8,C.MP[r])))
        elif action=='gather': events.append('采得药草 +%d。'%add('herbs',2))
        elif action=='alchemy': s['herbs']-=3;add('pills',1);events.append('药草 −3，炼成回春丹 +1。')
        elif action=='explore':
            area=C.REGIONS[s['region']];events.append('探访%s，灵石 +%d，药草 +%d。'%(area['name'],add('stones',area['stones']),add('herbs',area['herbs'])))
        elif action=='upgrade':
            cost=[12,24][s['technique']];s['stones']-=cost;s['technique']+=1;events.append('灵石 −%d，归元诀升至%d级。'%(cost,s['technique']))
        elif action=='buy_pill':s['stones']-=8;add('pills',1);events.append('灵石 −8，购得回春丹 +1。')
        elif action=='sell_herbs':s['herbs']-=2;events.append('药草 −2，灵石 +%d。'%add('stones',3))
        elif action=='breakthrough':
            cost=C.BREAKTHROUGH[r];s['cultivation']-=cost;s['realm']+=1;s['hp']=C.HP[r+1];s['mp']=C.MP[r+1];events.append('修为 −%d，突破至%s！气血与灵力恢复充盈。'%(cost,C.REALMS[r+1]));events.append(C.BREAKTHROUGH_STORIES[r])
        elif action=='challenge':
            enemy=params['enemy'];s['battle']={'enemy':enemy,'hp':C.ENEMIES[enemy]['hp'],'turn':0};events.append('迎战%s，留意敌方下一招。'%C.ENEMIES[enemy]['name'])
        elif action=='flee':s['battle']=None;events.append('及时撤退，保留已有成长与资源。')
        else:
            b=s['battle'];e=C.ENEMIES[b['enemy']];atk=C.ATTACK[r]+2*s['technique']
            if action in {'attack','power_attack'}:
                damage=atk*(2 if action=='power_attack' else 1)
                if action=='power_attack':s['mp']-=6
                actual=min(b['hp'],damage);b['hp']-=actual;events.append(('运功强攻' if action=='power_attack' else '出手攻击')+'，造成%d伤害。'%actual)
            elif action=='defend':events.append('凝神防御，灵力 +%d，本回合所受伤害减半。'%add('mp',3,C.MP[r]))
            elif action=='use_pill':s['pills']-=1;events.append('服用回春丹，气血 +%d，灵力 +%d。'%(add('hp',45,C.HP[r]),add('mp',6,C.MP[r])))
            if b['hp']<=0:
                enemy=b['enemy'];first=enemy not in s['victories']
                events.append('战胜%s！灵石 +%d，修为 +%d。'%(e['name'],add('stones',e['stones']),add('cultivation',e['cultivation'])))
                if first:s['victories'].append(enemy);events.append('记下'+e['name']+'首胜。')
                if enemy=='shadow':s['completed']=True;events.append(C.ENDING)
                s['battle']=None
            else:
                turn=b['turn']%3;damage=[e['attack'],0,e['heavy']][turn]
                if action=='defend':damage//=2
                s['hp']=max(0,s['hp']-damage);b['turn']+=1
                events.append(e['name']+('正在蓄势，本回合未出手。' if turn==1 else ('施展重击' if turn==2 else '发起攻击')+'，气血 −%d。'%damage))
                if s['hp']==0:s['hp']=1;s['region']='village';s['battle']=None;events.append('不敌败退，返回青岚村，气血保留1点；静养即可恢复。')
    s['logs']=(s['logs']+['第%d行 · %s'%(s['actions_taken'],e) for e in events])[-100:]
    validate_state(s)
    return s,events


def objective(s):
    r=s['realm']
    if s['completed']:return '归墟已平，修行未止。你可以继续游历，或另启新篇。'
    if r==3:return '前往归墟古境，战胜归墟之影，平息古境。'
    text='下一目标：突破至%s；修为 %d / %d，'%(C.REALMS[r+1],s['cultivation'],C.BREAKTHROUGH[r])+('灵气每%d秒自行汲取1点。'%C.QI_SECONDS if s['cultivation']<C.BREAKTHROUGH[r] else '已圆满，可以突破。')
    required={1:'ape',2:'sentinel'}.get(r)
    if required:text+=' '+C.ENEMIES[required]['name']+'首胜：'+('已完成。' if required in s['victories'] else '未完成。')
    return text


def project(s,context=None):
    view=dict(title=C.TITLE,phase='creation',character=None,location=None,objective='创建角色，开始修行',resources=[],battle=None,actions=[],logs=[],ending=None)
    if s is None:return view
    now=(context or {}).get('now')
    if now is not None:s=settle_qi(s,now)
    view["world"]=world.project(s,context=context)
    r=s['realm'];b=s['battle'];area=C.REGIONS[s['region']]
    view.update(phase='battle' if b else 'ending' if s['completed'] else 'exploration',character={'name':s['name'],'realm':C.REALMS[r]},location={'id':s['region'],'name':area['name'],'description':area['description']},objective=objective(s),logs=s['logs'])
    view['resources']=[dict(id=k,label=label,value=s[k],max=maximum) for k,label,maximum in [('hp','气血',C.HP[r]),('mp','灵力',C.MP[r]),('cultivation','修为',C.BREAKTHROUGH[r] if r<3 else 9999),('stones','灵石',9999),('herbs','药草',9999),('pills','回春丹',9999),('technique','归元诀',2)]]
    if s['realm']<3 and not s['world']['active']:
        qi_at=s.get('qi_at')
        view['qi']=dict(seconds=C.QI_SECONDS,cap=C.BREAKTHROUGH[s['realm']],value=s['cultivation'],next_in=None if qi_at is None or s['cultivation']>=C.BREAKTHROUGH[s['realm']] else max(0,C.QI_SECONDS-(now-qi_at)) if now is not None else None)
    if s['completed']:view['ending']={'title':'归墟已平，修行未止','text':C.ENDING}
    def action(id,label,cost,effect,group,params=None):
        params=params or {};reason=''
        effect='最多'+effect+'（恢复与奖励按上限截断）' if id in {'cultivate','rest','gather','explore','sell_herbs','alchemy','buy_pill','defend','use_pill'} else effect
        try:check(s,id,params)
        except GameError as exc:reason=exc.message
        view['actions'].append(dict(id=id,label=label,cost=cost,effect=effect,detail=label+'：'+cost+'；'+effect+'。',group=group,params=params,enabled=not reason,reason=reason,primary=False))
    if b:
        e=C.ENEMIES[b['enemy']];t=b['turn']%3
        intent=['常规攻击：造成%d点伤害'%e['attack'],'蓄势：本回合不造成伤害','重击：造成%d点伤害'%e['heavy']][t]
        view['battle']={'name':e['name'],'hp':b['hp'],'max_hp':e['hp'],'intent':intent}
        action('auto_battle','自动斗法','按战况消耗灵力与回春丹','自动强攻、防重击、必要时服丹，直至分出胜负；败退返回青岚村','battle')
    else:
        for args in [('breakthrough','突破境界','修为 −%d'%C.BREAKTHROUGH[r] if r<3 else '已筑基','突破保证成功，气血灵力恢复全满','cultivation'),('rest','静养调息','免费','气血 +30、灵力 +8','cultivation'),('gather','采集药草','免费','药草 +2','exploration'),('alchemy','炼制回春丹','药草 −3','回春丹 +1','cultivation'),('explore','探索此地','免费','灵石 +%d、药草 +%d'%(area['stones'],area['herbs']),'exploration'),('upgrade','研习归元诀','灵石 −%d'%([12,24][s['technique']] if s['technique']<2 else 0),'功法 +1级，攻击 +2','cultivation'),('buy_pill','购买回春丹','灵石 −8','回春丹 +1','trade'),('sell_herbs','出售药草','药草 −2','灵石 +3','trade')]:action(*args)
        for id,region in C.REGIONS.items():action('travel','前往'+region['name'],'免费','切换区域，不计行动','travel',{'region':id})
        for id,e in C.ENEMIES.items():
            if e['region']==s['region']:action('challenge','挑战'+e['name'],'免费','胜利最多：灵石 +%d、修为 +%d（按上限截断）'%(e['stones'],e['cultivation']),'challenge',{'enemy':id})
    if not s['world']['active']:
        reason='' if s['completed'] else '需先完成序章，平息归墟之影。'
        view['actions'].append(dict(id='world_enter',label='进入完整修仙界',detail='序章之后，开启九州长线修行。',cost='免费',effect='解锁世界、宗门、四艺与长线成长',params={},group='exploration',enabled=not reason,reason=reason,primary=False))
    if s['world']['active']:
        view['resources']=view['world']['resources']
        view['character']['realm']=view['world']['stage']
        view['objective']=view['world']['summary']
        view['actions']=[]
        view['ending']=None
    if s['completed'] and not s['world']['active']:
        view['ending']['text']+=' 序章告成，可进入完整修仙界，继续九州修行。'
    preferred=['world_enter','auto_battle','breakthrough','explore']
    for id in preferred:
        chosen=next((a for a in view['actions'] if a['id']==id and a['enabled']),None)
        if chosen:chosen['primary']=True;break
    return view
