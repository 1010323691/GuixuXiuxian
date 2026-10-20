"""Complete local cultivation world: pure state transitions and view projection."""
import copy
import math
import pickle
import unicodedata
from . import world_config as C
from . import loot
from . import r3_config as R
from . import gameplay_config as G
from . import activities
from . import journey
from .clone import clone

CAP=999999
ARTS=('alchemy','smithing','talismans','formations')
PAGES=[('world','九州'),('character','人物'),('sects','宗门'),('social','同道'),('craft','四艺'),('exploration','秘境副本'),('estate','洞府'),('market','NPC坊市'),('quests','闻道'),('achievements','名录'),('arena','NPC演武')]


def initial_state():
    return dict(version=2,active=False,stage=0,xp=0,hp=200,mp=60,wallet=0,
        inventory={},root={'id':'wood','level':0,'points':0,'awakened':False},constitution={'id':'renew','level':0,'awakened':False},
        skills={'origin':1},skill='origin',equipment={'weapon':None,'armor':None,'pendant':None},
        gear={},arts={a:0 for a in ARTS},factions={},sect=None,contributions={},contribution_total=0,
        sect_quest=None,sect_earned={},relations={},friends=[],companion=None,master=None,disciples={},
        family=None,family_members=[],family_buildings={'garden':0,'guard':0,'school':0},family_builds=0,family_renown=0,
        home={'garden':0,'workshop':0,'chamber':0},home_storage={'garden':0,'workshop':0,'chamber':0},home_origin={'garden':0,'workshop':0,'chamber':0},arrays_enabled={'spirit':True,'mountain':True,'seal':True},arrays={'spirit':0,'mountain':0,'seal':0},
        region='qinglan',exploration=None,dungeon=None,battle=None,guard_wins=[],secret_wins=[],dungeon_wins=[],
        quests={},dialogue={},achievements=[],title=None,arena={'points':0,'claims':[],'wins':0,'season':0,'regional_points':0,'growth':0,'current':None},
        auctions=[],auction_seq=0,npc_agents={},event=None,encounter=None,event_seq=0,tick=0,
        counters={'battles':0,'crafts':0,'teaching':0,'gathers':0,'wins':0},last_chat={},last_teach=-3,
        journal=[],ending=False,extension={'content_version':1,'realm_cap':'渡劫','next_realm_locked':True})


def migrate_v1(state):
    result=clone(state)
    if result is not None and 'world' not in result:result['world']=initial_state()
    return result


def _error(message,code='ACTION_UNAVAILABLE',status=422):
    from .rules import GameError
    raise GameError(code,message,status)


def _bad(message):_error(message,'BAD_REQUEST',400)


def _int(value,lo=0,hi=CAP):return type(value) is int and lo<=value<=hi


def _validate_state(state):
    if not isinstance(state,dict) or not isinstance(state.get('world'),dict):raise ValueError('缺少世界存档')
    w=state['world'];template=initial_state()
    if set(w)!=(set(template)|({'r3'} if 'r3' in w else set())) or type(w['version']) is not int or w['version']!=2:raise ValueError('世界字段或版本不受支持')
    for k in ['active','ending']:
        if type(w[k]) is not bool:raise ValueError('世界开关类型无效')
    for k in ['stage','xp','hp','mp','wallet','contribution_total','family_builds','auction_seq','event_seq','tick']:
        if not _int(w[k],0,7 if k=='stage' else w[k] if k=='xp' and 'r3' in w and type(w[k]) is int else CAP):raise ValueError('世界数值无效：'+k)
    if w['active'] and not state['completed']:raise ValueError('未完成序章不能入世')
    for k in ['inventory','skills','gear','arts','factions','contributions','relations','family_buildings','home','arrays','counters','last_chat']:
        if not isinstance(w[k],dict) or any(not isinstance(x,str) or not _int(v) for x,v in w[k].items()):raise ValueError('世界数值表无效：'+k)
    if set(w['arts'])!=set(ARTS) or set(w['home'])!={'garden','workshop','chamber'} or set(w['arrays'])!={'spirit','mountain','seal'} or set(w['family_buildings'])!={'garden','guard','school'}:raise ValueError('世界设施字段无效')
    if any(v>3 for k in ['home','arrays','family_buildings'] for v in w[k].values()):raise ValueError('设施等级无效')
    if any(v>3 for v in w['gear'].values()) or any(v<1 or v>3 for v in w['skills'].values()):raise ValueError('装备功法等级无效')
    for k,catalog in [('inventory',dict(C.ITEMS,**C.RESOURCES)),('skills',C.SKILLS),('gear',C.ITEMS),('relations',C.NPCS),('factions',C.REGIONS),('contributions',C.SECTS)]:
        if any(key not in catalog for key in w[k]):raise ValueError('未知世界内容：'+k)
    for key,catalog,level in [('root',C.ROOTS,{'id','level','points','awakened'}),('constitution',C.CONSTITUTIONS,{'id','level','awakened'})]:
        value=w[key]
        if not isinstance(value,dict) or set(value)!=level or (not isinstance(value['id'],str) or value['id'] not in catalog) or not _int(value['level'],0,3):raise ValueError('禀赋无效')
        if key=='root' and not _int(value['points'],0,2):raise ValueError('养根点无效')
    for k,catalog in [('region',C.REGIONS),('skill',C.SKILLS)]:
        if not isinstance(w[k],str) or w[k] not in catalog:raise ValueError('世界内容无效：'+k)
    if w['skill'] not in w['skills']:raise ValueError('未学习已装备功法')
    for k,catalog in [('sect',C.SECTS),('master',C.NPCS),('companion',C.NPCS),('title',C.TITLES)]:
        if w[k] is not None and (not isinstance(w[k],str) or w[k] not in catalog):raise ValueError('关系或称号无效')
    for k in ['friends','family_members','guard_wins','secret_wins','dungeon_wins','achievements','journal']:
        if not isinstance(w[k],list) or any(not isinstance(x,str) for x in w[k]) or len(w[k])>(100 if k=='journal' else 1000):raise ValueError('世界列表无效：'+k)
        if k!='journal' and len(w[k])!=len(set(w[k])):raise ValueError('世界重复记录')
    if any(k not in C.NPCS for k in w['friends']+w['family_members']):raise ValueError('未知好友')
    if w['companion'] is not None and w['companion'] not in w['friends']:raise ValueError('同行不是好友')
    if w['family'] is not None and (not isinstance(w['family'],str) or not 1<=len(w['family'])<=16):raise ValueError('家族名无效')
    if not isinstance(w['equipment'],dict) or set(w['equipment'])!={'weapon','armor','pendant'}:raise ValueError('装备槽无效')
    for slot,item in w['equipment'].items():
        if item is not None and (not isinstance(item,str) or item not in w['gear'] or count(w,item)<1 or C.ITEMS[item].get('slot')!=slot):raise ValueError('已装备物品无效')
    _deep_validate(w)
    if not 1<=w['hp']<=attributes(w)['hp'] or not 0<=w['mp']<=attributes(w)['mp']:raise ValueError('世界气血灵力超界')
    for k in ['quests','dialogue','disciples','npc_agents']:
        if not isinstance(w[k],dict):raise ValueError('世界对象表无效：'+k)
    if not isinstance(w['auctions'],list) or len(w['auctions'])>100:raise ValueError('拍卖表无效')
    for a in w['auctions']:
        if not isinstance(a,dict) or set(a)!={'id','item','quantity','base','price','bidder','seller','end','settled','cancelled','last_bid','delivery'}:raise ValueError('拍卖字段无效')
        if a['item'] not in dict(C.ITEMS,**C.RESOURCES) or not all(_int(a[k]) for k in ['quantity','base','price','end']) or a['quantity']<1 or type(a['settled']) is not bool or type(a['cancelled']) is not bool:raise ValueError('拍卖数值无效')
    for k in ['exploration','dungeon','battle','sect_quest','event','encounter']:
        if w[k] is not None and not isinstance(w[k],dict):raise ValueError('世界活动无效：'+k)
    if type(w['last_teach']) is not int or w['last_teach'] < -3 or w['last_teach']>CAP:raise ValueError('请教回合无效')
    if w['battle'] is not None:
        b=w['battle']
        if b.get('kind') in {'world_boss','elite'} and 'r3' not in w:raise ValueError('旧档不支持长线专属挑战')
        if set(b)!=({'name','hp','max_hp','attack','heavy','turn','kind','target','stage','shield','heals','snapshot','start_tick','growth'}|({'r3_day','r3_attempt','player_damage','commands'} if b.get('kind')=='world_boss' and 'r3' in w else {'mechanic','poison_turns','poison_damage','barrier'} if 'r3' in w and b.get('kind')=='elite' else {'mechanic','poison_turns','poison_damage','barrier'} if 'r3' in w and b.get('kind')=='dungeon' and w.get('dungeon') and w['dungeon'].get('difficulty',0)>=2 and w['dungeon'].get('round')==2 else set())) or not all(_int(b[k],0,R.BOSS['hp'] if b.get('kind')=='world_boss' and k in {'hp','max_hp'} else CAP) for k in ['hp','max_hp','attack','heavy','turn','stage','shield','heals']) or not 1<=b['hp']<=b['max_hp'] or b['kind'] not in {'wild','guard','secret','dungeon','arena','regional','escort','world_boss','elite'}:raise ValueError('世界战斗无效')
    if not isinstance(w['arena'],dict) or set(w['arena'])!={'points','claims','wins','season','regional_points','growth','current'} or any(not _int(w['arena'][k]) for k in ['points','wins','season','regional_points']) or not isinstance(w['arena']['claims'],list):raise ValueError('演武记录无效')
    if 'r3' in w:loot.validate({'world':w})
    if w['ending'] and (w['stage']!=7 or '7' not in w['guard_wins']):raise ValueError('凡界结局无效')


def count(w,item):return w['inventory'].get(item,0)


def item_name(item):return C.RESOURCES.get(item, {'xp':'修为','relation':'NPC好感','reputation':'地域声望','family_renown':'家族声望'}.get(item,C.ITEMS.get(item,{}).get('name',item)))


def gain(w,item,n):
    if item=='xp' and 'r3' in w:return 0
    if item=='stone':
        actual=min(n,CAP-w['wallet']);w['wallet']+=actual
    elif item=='xp':
        actual=min(n,CAP-w['xp']);w['xp']+=actual
    else:
        actual=min(n,CAP-count(w,item));w['inventory'][item]=count(w,item)+actual
    return actual


def pay(w,cost):
    for item,n in cost.items():
        have=w['wallet'] if item=='stone' else w['xp'] if item=='xp' else count(w,item)
        if have<n:_error('缺少%s：需要%d，当前%d；可去九州免费采集/凝灵，或修炼后再来。'%(item_name(item),n,have))
    for item,n in cost.items():
        if item=='stone':w['wallet']-=n
        elif item=='xp':w['xp']-=n
        else:w['inventory'][item]-=n


def _catalog(catalog,key):
    if not isinstance(key,str) or key not in catalog:_bad('目标不存在。')
    return catalog[key]


def _params(params,keys):
    if not isinstance(params,dict) or set(params)!=set(keys):_bad('行动参数不完整或含未知字段。')


def _level(w,item):return w['gear'].get(item,0)


def attributes(w,boss=False):
    s=w['stage'];root=w['root'];con=w['constitution'];rn=root['id'];cn=con['id'];rl=root['level']+1;cl=con['level']+1
    hp=C.STAGES[s]['max_hp']+(C.ROOTS['earth']['max_hp']*rl if rn=='earth' else 0)+10*w['family_buildings']['guard']
    mp=C.STAGES[s]['max_mp']+(C.CONSTITUTIONS['clear']['max_mp']*cl if cn=='clear' else 0)
    atk=C.STAGES[s]['attack']+(C.ROOTS['fire']['attack']*rl if rn=='fire' else 0)+(3 if w['title']=='veteran' else 0)
    for slot,item in w['equipment'].items():
        if item:
            level=_level(w,item);definition=C.ITEMS[item]
            hp+=definition.get('max_hp',0)*level;mp+=definition.get('max_mp',0)*level;atk+=definition.get('attack',0)*level
    if boss:atk+=6*w['arrays']['seal']*w['arrays_enabled']['seal']
    base={'hp':hp,'mp':mp,'attack':atk}
    return loot.attributes(w,base) if 'r3' in w else base


def _clamp(w):
    a=attributes(w);w['hp']=min(w['hp'],a['hp']);w['mp']=min(w['mp'],a['mp'])


def _art_level(w,art):return 3 if w['arts'][art]>=50 else 2 if w['arts'][art]>=20 else 1


def _reputation(w,region,n):w['factions'][region]=min(100,w['factions'].get(region,0)+n)


def _relation(w,npc,n):w['relations'][npc]=min(100,w['relations'].get(npc,0)+n)


def _progress(w,kind):
    q=w['sect_quest']
    if q and q['type']==kind and not q['done']:q['done']=True


def _npc_seed():
    return {k:{'wallet':50,'inventory':dict(C.ECONOMY['npc_initial_materials']),'turns':0,'last':'NPC正在筹备修行物资。','pending':{}} for k in C.NPCS}


def _order(w,seller,item,quantity,base,at=None):
    if len(w['auctions'])>=120 or sum(not a['settled'] and not a['cancelled'] for a in w['auctions'])>=12:return False
    if sum(a['seller']==seller and not a['settled'] and not a['cancelled'] for a in w['auctions'])>=(3 if seller=='player' else 2):return False
    at=w['tick'] if at is None else at
    w['auction_seq']+=1
    w['auctions'].append(dict(id=str(w['auction_seq']),item=item,quantity=quantity,base=base,price=0,bidder=None,seller=seller,end=at+6,settled=False,cancelled=False,last_bid=at,delivery={}))
    return True


def _create_auctions(w):
    for npc,agent in w['npc_agents'].items():
        for lot in C.ECONOMY['lots']:
            item=lot['item'];quantity=lot['amount']
            if agent['inventory'].get(item,0)>=quantity and _order(w,npc,item,quantity,lot['price']):
                agent['inventory'][item]-=quantity;break


def _deliver(w,owner,item,n,order):
    if n<=0:return
    if owner=='player':
        current=w['wallet'] if item=='stone' else count(w,item)
        if current+n>CAP:order['delivery'][item]=order['delivery'].get(item,0)+n
        else:gain(w,item,n)
    elif owner in w['npc_agents']:
        agent=w['npc_agents'][owner]
        current=agent['wallet'] if item=='stone' else agent['inventory'].get(item,0)
        accepted=min(n,max(0,200-current))
        if item=='stone':agent['wallet']+=accepted
        else:agent['inventory'][item]=current+accepted
        if accepted<n:agent['pending'][item]=agent['pending'].get(item,0)+n-accepted


def _refund(w,order):
    if order['bidder']:_deliver(w,order['bidder'],'stone',order['price'],order)


def _ai(w,events):
    tick=w['tick']
    for agent in w['npc_agents'].values():
        for item,n in list(agent['pending'].items()):
            current=agent['wallet'] if item=='stone' else agent['inventory'].get(item,0);accepted=min(n,max(0,200-current))
            if item=='stone':agent['wallet']+=accepted
            else:agent['inventory'][item]=current+accepted
            agent['pending'][item]-=accepted
            if not agent['pending'][item]:del agent['pending'][item]
    # Settlement precedes new bids at the exact expiry boundary.
    for order in w['auctions']:
        if order['settled'] or order['cancelled'] or tick<order['end']:continue
        if order['bidder']:
            _deliver(w,order['bidder'],order['item'],order['quantity'],order)
            _deliver(w,order['seller'],'stone',order['price']-order['price']//20,order)
            events.append('NPC拍卖订单'+order['id']+'成交，货款按托管一次结算。')
        else:_deliver(w,order['seller'],order['item'],order['quantity'],order);events.append('NPC拍卖订单'+order['id']+'流拍，货品已返还或进入待领。')
        order['settled']=True
    # Production uses each facility's own completed-action origin.
    for facility,level in w['home'].items():
        if level and tick>w['home_origin'][facility] and (tick-w['home_origin'][facility])%3==0:
            w['home_storage'][facility]=min(20*level,w['home_storage'][facility]+level)
    # One deterministic NPC agent acts every third successful world action.
    if tick%3==0:
        keys=list(C.NPCS);npc=keys[(tick//3-1)%len(keys)];agent=w['npc_agents'][npc]
        product={'healer':'pill','smith':'blade','stargazer':'fire_talisman'}[npc];recipe=C.RECIPES[product];inv=agent['inventory']
        missing='crystal' if npc=='stargazer' and inv.get('crystal',0)<3 else next((k for k,n in recipe['cost'].items() if inv.get(k,0)<n),None)
        if missing:inv[missing]=min(200,inv.get(missing,0)+2);agent['last']='采集'+item_name(missing)+' +2'
        elif inv.get(product,0)<200:
            for k,n in recipe['cost'].items():inv[k]-=n
            inv[product]=inv.get(product,0)+1;agent['last']='按配方制作'+item_name(product)
        else:agent['last']='仓储已满，等待流通'
        if inv.get(product,0)>=2 and _order(w,npc,product,1,C.ITEMS[product].get('sell',8)):inv[product]-=1;agent['last']+='；托管一件至NPC拍卖'
        agent['turns']+=1;events.append(C.NPCS[npc]['name']+'（规则NPC）：'+agent['last'])
    # NPC reply is never in the same action as a player's bid.
    for order in w['auctions']:
        if order['settled'] or order['cancelled'] or tick<=order['last_bid'] or order['price']>=order['base']+4:continue
        price=max(order['base'],order['price']+1)
        for npc,agent in w['npc_agents'].items():
            if npc in {order['seller'],order['bidder']} or agent['wallet']<price:continue
            _refund(w,order);agent['wallet']-=price;order['price']=price;order['bidder']=npc;order['last_bid']=tick
            events.append(C.NPCS[npc]['name']+'出价%d；旧托管即时退回。'%price);break
    if w['event'] and tick>=w['event']['end']:events.append('动态事件结束：'+w['event']['name']);w['event']=None
    if tick%20==0:
        key=['herb','beast','trade'][(tick//20-1)%3];names={'herb':'药潮','beast':'兽潮','trade':'商潮'}
        w['event']={'id':key,'name':names[key],'end':tick+6};events.append('规则AI触发'+names[key]+'，持续6世界行动。');_create_auctions(w)
    if w['encounter'] and tick>=w['encounter']['end']:events.append('路边奇遇已散去。');w['encounter']=None
    if tick%12==0 and not w['encounter']:
        key=['traveler','furnace','inscription'][w['event_seq']%3];w['event_seq']+=1;w['encounter']={'id':key,'end':tick+6};events.append('发现奇遇：'+C.EVENTS[key]['name'])
    closed=[a for a in w['auctions'] if (a['settled'] or a['cancelled']) and not a['delivery']]
    retained=[a for a in w['auctions'] if not (a['settled'] or a['cancelled']) or a['delivery']]
    w['auctions']=retained+closed[-60:]


def _enemy(w,kind,target='',difficulty=1,stage=None):
    s=w['stage'] if stage is None else stage;boss=kind=='guard' or kind=='dungeon' and w['dungeon']['round']==2
    hp=(C.COMBAT['boss_hp_base']+C.COMBAT['boss_hp_stage']*s) if boss else (C.COMBAT['mob_hp_base']+C.COMBAT['mob_hp_stage']*s);atk=(C.COMBAT['boss_hit_base']+C.COMBAT['boss_hit_stage']*s) if boss else (C.COMBAT['mob_hit_base']+C.COMBAT['mob_hit_stage']*s);heavy=(C.COMBAT['boss_heavy_base']+C.COMBAT['boss_heavy_stage']*s) if boss else (C.COMBAT['mob_heavy_base']+C.COMBAT['mob_heavy_stage']*s)
    name='第%d境劫影'%(s+1) if kind=='guard' else '荒野妖兽'
    if kind=='secret':name=C.SECRETS[target]['name']+'守卫'
    if kind=='dungeon':name=C.DUNGEONS[target]['name']+('镇守Boss' if boss else '巡守妖兽')
    if kind in {'arena','regional'}:
        growth=w['arena']['current']['growth'] if kind=='regional' and w['arena']['current'] else w['arena']['growth']
        hp+=15*growth;atk+=2*growth;heavy+=2*growth
        name={k:v['name'] for k,v in C.ARENA_OPPONENTS.items()}[target]
        if target=='swordsman':hp=max(60,hp-30);atk+=10;heavy+=10
        if target=='bodyguard':hp+=80;atk=max(1,atk-5);heavy=max(1,heavy-5)
    multiplier=1+0.25*(difficulty-1)
    result=dict(name=name,hp=math.floor(hp*multiplier),max_hp=math.floor(hp*multiplier),attack=math.floor(atk*multiplier),heavy=math.floor(heavy*multiplier),turn=0,kind=kind,target=target,stage=s,shield=0,heals=0,snapshot=None,start_tick=w['tick'],growth=w['arena']['growth'])
    if 'r3' in w and kind=='dungeon' and boss and difficulty>=2:
        result.update(mechanic=G.DUNGEON_MECHANICS[target]['id'],poison_turns=0,poison_damage=G.DUNGEON_MECHANICS['den']['poison_base']+G.DUNGEON_MECHANICS['den']['poison_per_chapter']*s,barrier=result['max_hp']*G.DUNGEON_MECHANICS['forge']['shield_num']//G.DUNGEON_MECHANICS['forge']['shield_den'] if target=='forge' else 0)
    if kind=='elite':
        e=G.ELITES[target];result.update(name=e['name'],hp=e['hp'],max_hp=e['hp'],attack=e['attack'],heavy=e['heavy'],stage=e['chapter'],mechanic=e['mechanic'],poison_turns=0,poison_damage=e['poison_damage'],barrier=e['barrier'])
    return result


def _start(w,kind,target='',difficulty=1,stage=None):
    if w['battle']:_error('请先结束当前战斗。')
    b=_enemy(w,kind,target,difficulty,stage)
    if kind in {'arena','regional'}:b['snapshot']={'hp':w['hp'],'mp':w['mp'],'inventory':copy.deepcopy(w['inventory'])}
    w['battle']=b


def _combat_pay(w,b,cost):
    if b['snapshot'] is None:
        pay(w,cost)
        return
    real=w['inventory']
    try:
        w['inventory']=b['snapshot']['inventory']
        pay(w,cost)
    finally:
        w['inventory']=real


MANUAL_ACTIONS={'world_attack','world_power','world_defend','world_pill','world_fire','world_guard','world_soul'}
CONSUMABLES={'world_pill':'pill','world_fire':'fire_talisman','world_guard':'guard_talisman','world_soul':'soul_talisman'}
ACTION_LABELS={'world_attack':'普攻','world_power':'运功强攻','world_defend':'防御','world_pill':'服回元丹','world_fire':'焚火符','world_guard':'护身符','world_soul':'镇魂符'}
STRATEGIES={'balanced':'均衡','steady':'稳妥','aggressive':'强攻','frugal':'节制'}
AUTO_LIMIT=120


def _stock(w,b,item):
    return (b['snapshot']['inventory'] if b['snapshot'] is not None else w['inventory']).get(item,0)


def _reduction(w):
    return (2*(w['constitution']['level']+1) if w['constitution']['id']=='sturdy' else 0)+2*w['arrays']['mountain']*w['arrays_enabled']['mountain']


def _incoming(w,b):
    """Enemy damage the next enemy opportunity deals if the player does not defend or skip."""
    damage=max(0,[b['attack'],0,b['heavy']][b['turn']%3]-_reduction(w))
    return math.floor(damage*0.75) if b['shield'] else damage


def _choose(w,b,strategy,attrs,round_no,last_item):
    """Deterministic rule policy: returns one internal single-round action."""
    skill=w['skill'];level=w['skills'][skill]
    normal=attrs['attack']+(4*level if skill=='flame' else 0)
    power=attrs['attack']*(20+level)//10 if skill=='origin' else attrs['attack']*2
    mp_ok=w['mp']>=C.COMBAT['power_mp']
    turn=b['turn']%3;barrier=b.get('barrier',0);reach=barrier+b['hp']
    full=w['hp']>=attrs['hp'] and w['mp']>=attrs['mp']
    if normal>=reach:return 'world_attack'
    if mp_ok and power>=reach:return 'world_power'
    can_item=strategy!='frugal' and round_no-last_item>=3
    def have(item):return can_item and _stock(w,b,item)>0
    if strategy in {'balanced','steady'}:
        pill_line=75 if strategy=='steady' else 40
        if have('pill') and not full and (w['hp']*100<=attrs['hp']*pill_line or b.get('poison_turns',0) or (turn==1 and not mp_ok)):return 'world_pill'
        if barrier>=normal and have('fire_talisman'):return 'world_fire'
        if turn==2 and _incoming(w,b)>=w['hp'] and have('soul_talisman'):return 'world_soul'
        if b.get('mechanic')=='mana_seal' and turn==0 and not mp_ok and have('soul_talisman'):return 'world_soul'
        if turn==1 and w['hp']<=(3 if strategy=='steady' else 2)*b['heavy'] and not b['shield'] and have('guard_talisman'):return 'world_guard'
    elif strategy=='aggressive':
        if have('pill') and not full and w['hp']*100<=attrs['hp']*25:return 'world_pill'
    if strategy!='aggressive':
        if turn==2 and _incoming(w,b)*100>=w['hp']*35:return 'world_defend'
        if b.get('mechanic')=='mana_seal' and turn==0 and not mp_ok:return 'world_defend'
    return 'world_power' if mp_ok else 'world_attack'


ROLLOUT_STEPS=60
ROLLOUT_BUDGET=30000


def _candidates(w,b,strategy,attrs,round_no,last_item,preferred):
    """Legal single-round moves this strategy may consider; the rule policy's move is tried first."""
    moves=[]
    if w['mp']>=C.COMBAT['power_mp']:moves.append('world_power')
    moves.append('world_attack')
    if strategy!='aggressive':moves.append('world_defend')
    if strategy!='frugal' and round_no-last_item>=3:
        full=w['hp']>=attrs['hp'] and w['mp']>=attrs['mp']
        if _stock(w,b,'pill')>0 and not full and (strategy!='aggressive' or w['hp']*100<=attrs['hp']*25):moves.append('world_pill')
        if strategy in {'balanced','steady'}:
            if b.get('barrier',0) and _stock(w,b,'fire_talisman')>0:moves.append('world_fire')
            if not b['shield'] and _stock(w,b,'guard_talisman')>0:moves.append('world_guard')
            if _stock(w,b,'soul_talisman')>0:moves.append('world_soul')
    if preferred in moves:moves.remove(preferred);moves.insert(0,preferred)
    return moves


def _rollout(w0,first,strategy,attrs,round_no,last_item,budget):
    """Play `first` then the rule policy to the end on a private copy; returns a score tuple or None."""
    w=pickle.loads(pickle.dumps(w0,protocol=pickle.HIGHEST_PROTOCOL));b=w['battle'];boss_window=b['kind']=='world_boss'
    action=first;n=round_no;used=0;outcome=None
    for _ in range(ROLLOUT_STEPS):
        trace=[]
        try:_round(w,action,[],trace)
        except Exception:return None
        budget[0]-=1
        if action in CONSUMABLES:used+=1;last_item=n
        n+=1
        end=next((t['type'] for t in trace if t['type'] in {'victory','defeat','window'}),None)
        if end:outcome=end
        if w['battle'] is None:break
        action=_choose(w,w['battle'],strategy,attrs,n,last_item)
    won=outcome=='victory'
    if boss_window:return (b['player_damage'],-used,w['hp'])
    left=0 if won else b['hp']+b.get('barrier',0)
    if strategy=='aggressive':return (won,-left,-(n-round_no),-used,w['hp'])
    if strategy in {'frugal','steady'}:return (won,-left,w['hp'],-(n-round_no))
    return (won,-left,-used,w['hp'],-(n-round_no))


def _decide(w,b,strategy,attrs,round_no,last_item,budget):
    """Rule policy proposes; look-ahead rollouts may overrule it with a better-scoring legal move."""
    preferred=_choose(w,b,strategy,attrs,round_no,last_item)
    if budget[0]<=0 or strategy=='steady' and preferred in CONSUMABLES:return preferred  # 稳妥：命中保命规则即直接执行
    best=None;best_move=preferred
    for move in _candidates(w,b,strategy,attrs,round_no,last_item,preferred):
        score=_rollout(w,move,strategy,attrs,round_no,last_item,budget)
        if score is not None and (best is None or score>best):best=score;best_move=move
    return best_move


def _auto_battle(w,p,events,context=None):
    b=w['battle']
    if not b:_error('当前不在世界战斗中。')
    strategy=p['strategy']
    if strategy not in STRATEGIES:_bad('未知自动斗法策略。')
    boss=b['kind'] in {'guard','world_boss','elite'} or b['kind']=='dungeon' and w['dungeon']['round']==2
    attrs=attributes(w,boss)
    treasures={slot:loot.combat_treasure(w,slot) for slot in R.TREASURE_SLOTS}
    intents=['常规攻击','蓄势','重击']
    frames=[{'round':0,'player':{'hp':w['hp'],'mp':w['mp']},'enemy':{'hp':b['hp'],'barrier':b.get('barrier',0)},'intent':intents[b['turn']%3],'action':'准备','events':[]}]
    outcome='stalemate';last_item=-9;rounds=0;finished=False;budget=[ROLLOUT_BUDGET];used={};tail=[]
    for n in range(1,AUTO_LIMIT+1):
        action=_decide(w,b,strategy,attrs,n,last_item,budget)
        if action in CONSUMABLES:last_item=n;used[ACTION_LABELS[action]]=used.get(ACTION_LABELS[action],0)+1
        sub=[];trace=[]
        _round(w,action,sub,trace)
        rounds=n
        frames.append({'round':n,'player':{'hp':w['hp'],'mp':w['mp']},'enemy':{'hp':b['hp'],'barrier':b.get('barrier',0)},'intent':intents[b['turn']%3],'action':ACTION_LABELS[action],'events':trace})
        tail=sub
        end=next((t['type'] for t in trace if t['type'] in {'victory','defeat','window'}),None)
        if end:outcome=end
        if w['battle'] is None:finished=True;break
    events.append('自动斗法（%s）：共%d拍，%s%s。逐拍过程见战报回放。'%(STRATEGIES[strategy],rounds,{'victory':'胜利','defeat':'败退','window':'十二拍窗口结束'}.get(outcome,'未分胜负'),'；用去'+'、'.join('%s×%d'%kv for kv in used.items()) if used else ''))
    events.extend(tail)
    if not finished:
        if b['snapshot']:w.update(hp=b['snapshot']['hp'],mp=b['snapshot']['mp'])
        w['battle']=None
        if b['kind']=='secret':w['exploration']=None
        if b['kind']=='dungeon':loot.release_run(w);w['dungeon']=None
        events.append('斗法达到%d拍上限仍未分胜负，自动撤离，无反击也无本战奖励。'%AUTO_LIMIT)
    if isinstance(context,dict):
        context['battle_report']={'outcome':outcome,'rounds':rounds,'strategy':strategy,'strategy_label':STRATEGIES[strategy],'enemy':{'name':b['name'],'max_hp':b['max_hp'],'kind':b['kind']},
            'player':{'max_hp':attrs['hp'],'max_mp':attrs['mp']},
            'treasures':{slot:({'name':loot.item_name(item['template_id']),'quality':R.QUALITIES[item['quality']]['name']} if item else None) for slot,item in treasures.items()},
            'frames':frames}
    return rounds  # 每拍仍是一次世界行动：世界时钟与行动计数按拍推进，与旧点击战斗等价


def _battle(w,action,params,events,context=None):
    if not w['battle']:_error('当前不在世界战斗中。')
    if action!='world_auto_battle':_error('交锋未止：请先选择一种自动斗法策略完成本战。')
    return _auto_battle(w,params,events,context)


def _round(w,action,events,trace):
    """One internal player opportunity; only the auto resolver calls it."""
    if action not in MANUAL_ACTIONS:_error('战斗中只能使用战斗行动。')
    b=w['battle']
    def note(kind,source,target,label,amount=None):
        item={'type':kind,'source':source,'target':target,'label':label}
        if amount is not None:item['amount']=amount
        trace.append(item)
    boss=b['kind'] in {'guard','world_boss','elite'} or b['kind']=='dungeon' and w['dungeon']['round']==2
    a=attributes(w,boss);skill=w['skill'];level=w['skills'][skill];damage=0;skip=False;old_poison=b.get('poison_turns',0)
    if action=='world_attack':damage=a['attack']+(4*level if skill=='flame' else 0)
    elif action=='world_power':
        if w['mp']<C.COMBAT['power_mp']:_error('强攻需要%d点灵力，可防御回灵。'%C.COMBAT['power_mp'])
        w['mp']-=C.COMBAT['power_mp'];damage=a['attack']*(20+level)//10 if skill=='origin' else a['attack']*2
    elif action=='world_defend':w['mp']=min(a['mp'],w['mp']+6);events.append('防御回灵 +6，本回合伤害减半。');note('defend','player','player','防御回灵',6)
    elif action=='world_pill':
        if w['hp']==a['hp'] and w['mp']==a['mp']:_error('气血灵力均已充盈。')
        _combat_pay(w,b,{'pill':1})
        if b.get('mechanic')=='venom':b['poison_turns']=0;old_poison=0;events.append('回元丹清除旧毒，本回合免疫重挂。')
        healed=min(80,a['hp']-w['hp']);w['hp']=min(a['hp'],w['hp']+80);w['mp']=min(a['mp'],w['mp']+20);events.append('回元丹恢复气血最多80、灵力最多20。');note('heal','player','player','服回元丹',healed)
    elif action=='world_fire':_combat_pay(w,b,{'fire_talisman':1});damage=math.floor(a['attack']*1.5)
    elif action=='world_guard':_combat_pay(w,b,{'guard_talisman':1});b['shield']=2;events.append('护身符生效，本回合和下一回合减伤25%。');note('buff','player','player','护身符减伤25%',2)
    elif action=='world_soul':_combat_pay(w,b,{'soul_talisman':1});skip=True;events.append('镇魂符使敌人本回合无法行动。');note('control','player','enemy','镇魂符')
    def strike(source,label,amount,fire=False):
        """One hit through any hostile barrier; only what reaches the body counts as damage."""
        if b.get('barrier',0) and amount:
            absorbed=min(b['barrier'],G.DUNGEON_MECHANICS['forge']['fire_shield_num']*a['attack']//G.DUNGEON_MECHANICS['forge']['fire_shield_den'] if fire else amount);b['barrier']-=absorbed
            events.append(('焚火符专破护盾%d，本次不溢出本体。'%absorbed) if fire else '护盾吸收%d点伤害，剩余%d。'%(absorbed,b['barrier']));note('shield',source,'enemy','破盾：'+label,absorbed)
            amount=0 if fire else amount-absorbed
        if amount>0:
            actual=min(b['hp'],amount)
            if b['kind']=='world_boss':b['player_damage']+=actual
            b['hp']-=actual;events.append('%s对%s造成%d伤害。'%(label,b['name'],actual));note('damage',source,'enemy',label,actual)
    if b['kind']=='world_boss':b['commands']+=1
    if 'r3' in w:
        if action=='world_pill':loot.mark_use(w,'alchemy')
        if action in {'world_fire','world_guard','world_soul'}:loot.mark_use(w,'talismans')
    if damage:strike('player',ACTION_LABELS[action],damage,fire=action=='world_fire')
    main=loot.combat_treasure(w,'main')
    if b['hp']>0 and main and b['turn']%2==0:
        strike('main','本命法宝出击',max(1,a['attack']*R.TREASURE_COMBAT['main']['attack_pct'][main['quality']]//100))
    if b['hp']>0 and w['companion'] and (b['turn']+1)%3==0:
        support=10
        if b.get('barrier',0):absorbed=min(b['barrier'],support);b['barrier']-=absorbed;support-=absorbed
        b['hp']=max(0,b['hp']-support);events.append('同行NPC支援，本体伤害%d；世界Boss评分不计同行。'%support);note('damage','npc','enemy','同行支援',support)
    if b['hp']==0:
        note('victory','player','enemy','战斗胜利')
        if b['kind']=='world_boss':loot.finish_boss(w,b,events)
        else:_victory(w,b,events)
        return
    enemy_damage=[b['attack'],0,b['heavy']][b['turn']%3]
    if skip:enemy_damage=0
    else:
        reduction=_reduction(w)
        if action=='world_defend' and skill=='mountain':reduction+=2*level
        enemy_damage=max(0,enemy_damage-reduction)
        if action=='world_defend':enemy_damage=math.floor(enemy_damage*0.5)
        if b['shield']:enemy_damage=math.floor(enemy_damage*0.75)
    guard=loot.combat_treasure(w,'guard')
    if guard and enemy_damage>0 and b['turn']%3==2:
        absorbed=min(enemy_damage,a['hp']*R.TREASURE_COMBAT['guard']['absorb_hp_pct'][guard['quality']]//100)
        if absorbed>0:enemy_damage-=absorbed;events.append('护持法宝回护，实际拦截%d点伤害。'%absorbed);note('shield_absorb','guard','player','护持法宝实际拦截',absorbed)
    w['hp']=max(0,w['hp']-enemy_damage);events.append('%s本回合造成%d伤害。'%(b['name'],enemy_damage));note('damage','enemy','player','敌方'+['常击','蓄势','重击'][b['turn']%3],enemy_damage)
    if b.get('mechanic')=='venom':
        if old_poison>0 and action!='world_pill' and w['hp']>0:
            w['hp']=max(0,w['hp']-b['poison_damage']);b['poison_turns']=max(0,old_poison-1);events.append('旧毒发作，固定气血 −%d，剩%d次。'%(b['poison_damage'],b['poison_turns']));note('poison','enemy','player','旧毒结算',b['poison_damage'])
        if b['turn']%3==2 and not skip and action not in {'world_defend','world_pill'} and w['hp']>0:
            b['poison_turns']=G.DUNGEON_MECHANICS['den']['poison_turns'];events.append('重击挂毒：随后两次敌方结算机会固定毒伤；防重击/丹/魂可反制。');note('status','enemy','player','新毒：随后两机会',b['poison_turns'])
    if b.get('mechanic')=='mana_seal' and b['turn']%3==0 and not skip and action!='world_defend':
        drained=min(G.DUNGEON_MECHANICS['tower']['mp_drain'],w['mp']);w['mp']-=drained;events.append('沉星汲灵，灵力 −%d；防常击或镇魂可免。'%drained);note('mana','enemy','player','常击汲灵',-drained)
    b['turn']+=1;b['shield']=max(0,b['shield']-1)
    if b['kind'] in {'arena','regional'} and b['target']=='alchemist' and b['turn']%3==0 and b['heals']<2:b['hp']=min(b['max_hp'],b['hp']+30);b['heals']+=1;events.append('NPC丹师回复30气血（最多两次）。')
    if w['hp']==0:
        note('defeat','enemy','player','本方气血归零')
        if b['kind']=='world_boss':
            w['hp']=1;loot.finish_boss(w,b,events);events.append('世界Boss挑战败退，已造成的有效伤害保留。');return
        if b['kind']=='regional':
            season=w['arena']['current'];season['npc_scores'][b['target']]=min(10,season['npc_scores'][b['target']]+5)
        if b['snapshot']:w.update(hp=b['snapshot']['hp'],mp=b['snapshot']['mp'])
        else:w['hp']=1
        loot.release_run(w)
        w['battle']=None;w['region']='qinglan';w['exploration']=None;w['dungeon']=None;events.append('本战败退，返回青岚安全地，可免费静养。')
    elif b['kind']=='world_boss' and b['commands']>=R.BOSS['rounds']:
        note('window','player','enemy','十二拍结束');loot.finish_boss(w,b,events)


def _victory(w,b,events):
    kind=b['kind'];target=b['target'];s=b['stage'];w['counters']['wins']+=1
    if kind=='guard':
        first=str(s) not in w['guard_wins'];gain(w,'xp',(20+6*s) if first else (8+2*s));gain(w,'stone',60+20*s if first else 15);gain(w,'crystal',2 if first else 1)
        if first:w['guard_wins'].append(str(s))
    elif kind=='elite':
        if target not in w['r3']['journey']['elite_wins']:w['r3']['journey']['elite_wins'].append(target)
        events.append('精英战果已记入故事，无额外独立掉落。')
    elif kind in {'wild','escort'}:
        gain(w,'stone',12+4*s+(4 if w['event'] and w['event']['id']=='beast' else 0));gain(w,'herb',2);w['counters']['battles']+=1;_progress(w,'battle')
        if kind=='escort':gain(w,'stone',15)
    elif kind=='secret':
        if 'r3' in w:w['r3']['secret_count']+=1
        gain(w,'xp',18+6*s)
        if target not in w['secret_wins']:w['secret_wins'].append(target);gain(w,'crystal',2);_reputation(w,w['region'],5)
        else:gain(w,C.SECRETS[target].get('material','herb'),3)
        w['exploration']=None;_progress(w,'secret')
    elif kind=='dungeon':
        d=w['dungeon'];d['round']+=1
        if d['round']==3:
            _complete_dungeon(w,events,manual=True)
        else:events.append('本场获胜，可静养后继续下一战或撤离。')
    elif kind in {'arena','regional'}:
        arena=w['arena']
        if kind=='regional':
            season=arena['current'];season['round']+=1;arena['regional_points']+=10;gain(w,'stone',10);events.append('NPC跨域赛晋级：本场积分10，灵石10，一次发放。')
        else:
            key='%s:%s:%d'%(kind,target,b['start_tick']//20)
            if key not in arena['claims']:arena['claims'].append(key);arena['points']+=10;gain(w,'stone',10);events.append('本周期NPC首胜：演武积分 +10，灵石 +10。')
            else:events.append('同周期重复演练，本次不重复领取奖励。')
        arena['wins']+=1
        snapshot=b['snapshot'];w.update(hp=snapshot['hp'],mp=snapshot['mp'])
    w['battle']=None;events.append('战胜'+b['name']+'，战果已保存。')


def _complete_dungeon(w,events,manual=True):
    d=w['dungeon'];target=d['id'];s=d['stage']
    gain(w,'xp',(24+6*s)*d['difficulty'])
    key=('%s:%d:%d'%(target,s,d['difficulty'])) if 'r3' in w else target+':'+str(d['difficulty'])
    first=key not in w['dungeon_wins']
    if 'r3' in w:
        loot.complete_run(w,d['run_id'],events)
        if manual:
            j=w['r3'].get('journey')
            if j is not None and key not in j['manual_clears']:j['manual_clears'].append(key)
    if first:w['dungeon_wins'].append(key);gain(w,'crystal',2*d['difficulty']);gain(w,'stone',30*d['difficulty'])
    else:gain(w,'stone',10*d['difficulty']);gain(w,C.DUNGEONS[target].get('material','ore'),3)
    w['dungeon']=None;events.append('副本三战通关，首通或重复奖励已结算。' if manual else '熟练关快捷结算，正式掉落与重复奖励已结算。')


def _growth(w,action,p,events):
    if action=='world_enter':
        _params(p,[])
        if w['active']:_error('已经进入完整世界。')
        w['active']=True;w['wallet']=60;w['inventory']={'herb':6,'ore':6,'wood':6,'crystal':2};w['npc_agents']=_npc_seed();_create_auctions(w)
        events.append(C.STORIES['enter']);events.append('获得一次入世行囊：凡界灵石60、草6、矿6、木6、灵晶2。');return True
    if action=='world_cultivate':
        if 'r3' in w:_error('修为在线离线持续增长，无需反复点击吐纳；副本活动只提供实物。')
        _params(p,[])
        if w['xp']==CAP:_error('修为已达上限。')
        amount=C.PROGRESSION['cultivate_base']+C.PROGRESSION['cultivate_stage']*w['stage']+(3*(w['root']['level']+1) if w['root']['id']=='wood' else 0)+4*w['arrays']['spirit']*w['arrays_enabled']['spirit']+(2 if w['title']=='artisan' else 0)
        events.append('世界修炼，修为 +%d。'%gain(w,'xp',amount));return True
    if action=='world_rest':
        _params(p,[]);a=attributes(w)
        if w['hp']==a['hp'] and w['mp']==a['mp']:_error('气血灵力均已充盈。')
        w['hp']=min(a['hp'],w['hp']+80+(20*(w['constitution']['level']+1) if w['constitution']['id']=='renew' else 0)+(10 if w['title']=='companion' else 0));w['mp']=min(a['mp'],w['mp']+30+5*w['home']['chamber']);events.append('免费静养，气血灵力恢复。');return True
    if action=='world_gather':
        _params(p,['item']);item=p['item']
        if item not in {'herb','ore','wood','crystal'}:_bad('只能采集基础材料。')
        if count(w,item)==CAP:_error('该材料已满。')
        specialty={'qinglan':'herb','chisha':'ore','xuanchao':'wood'}[w['region']]
        amount=1 if item=='crystal' else 3+(1 if specialty==item else 0)
        if item=='herb':amount+=(w['root']['level']+1 if w['root']['id']=='wood' else 0)+w['family_buildings']['garden']+w['home']['garden']+(1 if w['event'] and w['event']['id']=='herb' else 0)
        events.append('采集%s +%d。'%(item_name(item),gain(w,item,amount)));w['counters']['gathers']+=1;return True
    if action=='world_travel':
        _params(p,['region']);region=_catalog(C.REGIONS,p['region'])
        if p['region']==w['region']:_error('已在此地。')
        if w['stage']<region['stage']:_error('需先达到'+C.STAGES[region['stage']]['name']+'，该地域尚未解锁。')
        if w['exploration'] or w['dungeon']:_error('请先撤离秘境或副本。')
        w['region']=p['region'];events.append('前往'+region['name']+'。');return True
    if action in {'world_root','world_constitution'}:
        _params(p,['choice']);key='root' if action=='world_root' else 'constitution';definition=_catalog(C.ROOTS if key=='root' else C.CONSTITUTIONS,p['choice'])
        if w[key]['id']==p['choice'] and w[key]['awakened']:_error('已是此禀赋。')
        if w[key]['awakened']:pay(w,{'stone':30})
        w[key]['awakened']=True;w[key]['id']=p['choice'];_clamp(w);events.append('选择'+definition['name']+'，培养等级保留；上限变化不免费补满。');return True
    if action in {'world_root_train','world_constitution_train'}:
        _params(p,[]);key='root' if action=='world_root_train' else 'constitution'
        if w[key]['id'] is None:_error('请先鉴定禀赋。')
        if w[key]['level']==3:_error('培养已达三级。')
        pay(w,{'herb':6,'crystal':1} if key=='root' else {'ore':4,'crystal':1});w[key]['level']+=1;events.append('禀赋培养升至%d级。'%w[key]['level']);return True
    if action=='world_dew':
        _params(p,[])
        if w['root']['id'] is None or w['root']['level']==3:_error('请先鉴定灵根，且灵根未满级。')
        pay(w,{'root_dew':1});w['root']['points']+=1
        if w['root']['points']==3:w['root']['level']+=1;w['root']['points']=0
        events.append('服用养根露，培养点推进。');return True
    if action in {'world_skill_learn','world_skill_equip','world_skill_upgrade'}:
        _params(p,['skill']);key=p['skill'];definition=_catalog(C.SKILLS,key)
        if action=='world_skill_learn':
            if key in w['skills']:_error('已经学会此功法。')
            pay(w,{'stone':20});w['skills'][key]=1
        elif action=='world_skill_equip':
            if key not in w['skills']:_error('尚未学会。')
            if key==w['skill']:_error('已经装备此功法。')
            w['skill']=key
        else:
            if key not in w['skills'] or w['skills'][key]>=3:_error('未学习或已经满级。')
            target=w['skills'][key]+1;cost={'crystal':target}
            if count(w,'skill_coupon'):cost['skill_coupon']=1
            else:cost['stone']=20*target
            pay(w,cost);w['skills'][key]=target
        events.append('功法更新：'+definition['name']);return True
    if action=='world_advance':
        if w['exploration'] or w['dungeon']:_error('请先结束探索后突破。')
        _params(p,[]);reason=_advance_reason(w)
        if reason:_error(reason)
        s=w['stage']
        pay(w,{'xp':loot.cost(s) if 'r3' in w else C.STAGES[s]['xp_cost']})
        if s==0:pay(w,{'barrier_pill':1})
        if s==1:pay(w,{'soul_talisman':1})
        w['stage']+=1;a=attributes(w);w['hp']=a['hp'];w['mp']=a['mp'];events.append('突破至'+C.STAGES[w['stage']]['name']+'！世界气血灵力恢复充盈。');return True
    if action=='world_finish':
        _params(p,[])
        if w['ending']:_error('凡界故事已经完成。')
        if 'r3' in w and w['xp']<loot.cost(7):_error('渡劫圆满封界还需%d修为，持续修炼仍会增长。'%(loot.cost(7)-w['xp']))
        if w['stage']!=7 or '7' not in w['guard_wins'] or len(w['secret_wins'])!=len(C.SECRETS) or w['quests'].get('seal_gate')!='claimed':_error('需渡劫劫影首胜、三秘境首通，并领取主线“合拢裂隙”。')
        if 'r3' in w:pay(w,{'xp':loot.cost(7)});loot._grant_materials(w,R.FINAL_REWARD,'凡界封界')
        w['ending']=True;events.append(C.STORIES['ending']);return True
    return False


def _advance_reason(w):
    s=w['stage']
    if s==7:return '已达渡劫；请完成凡界终劫。'
    need=loot.cost(s) if 'r3' in w else C.STAGES[s]['xp_cost']
    if w['xp']<need:return ('修为还差%d；在线离线持续潜修，装备修炼法宝提高未来速率。' if 'r3' in w else '修为还差%d；可在人物页免费修炼。')%(need-w['xp'])
    if str(s) not in w['guard_wins']:return '需先挑战并战胜本阶段劫影（秘境副本页）。'
    if s==0 and count(w,'barrier_pill')<1:return '需要破障丹1；四艺草6晶2可炼。'
    if s==1 and count(w,'soul_talisman')<1:return '需要镇魂符1；四艺木5晶2可制。'
    if s==2 and not (any(w['r3']['equipped'][k] for k in R.EQUIPMENT_SLOTS) if 'r3' in w else any(w['equipment'].values())):return '需要装备至少一件器物实例；可安全制作或副本掉落后装备。' if 'r3' in w else '需要装备至少一件自制器；四艺制作后装备。'
    if s==3 and not w['arrays']['spirit']:return '需要在四艺建成聚灵阵1级。'
    if s==4 and max(w['sect_earned'].values(),default=0)<40:return '宗门累计贡献还差%d；日常交材料可保底推进。'%(40-max(w['sect_earned'].values(),default=0))
    if s==5 and (max(w['relations'].values(),default=0)<30 or w['counters']['teaching']<1):return '需要一位师友好感30，并完成一次弟子授业。'
    if s==6 and (w['family_builds']<2 or not w['arrays']['seal']):return '需要家族建设两次和封界阵至少1级。'
    return ''


def _craft(w,action,p,events):
    if action=='world_craft':
        _params(p,['recipe','quantity']);quantity=p['quantity'];recipe=_catalog(C.RECIPES,p['recipe']);output=recipe['output'];art=recipe['art']
        item=next(iter(output));definition=C.ITEMS[item];kind=definition.get('kind','consumable')
        if item in {'spirit_array','mountain_array','seal_array'}:
            if quantity!=1:_bad('永久阵法每次只能建造一级。')
            key={'spirit_array':'spirit','mountain_array':'mountain','seal_array':'seal'}[item];target=w['arrays'][key]+1
            if target>3:_error('该阵法已经三级。')
            pay(w,{k:v*target for k,v in recipe['cost'].items()});w['arrays'][key]=target
            if 'r3' in w:w['arrays_enabled'][key]=True;loot.mark_use(w,'formations')
        elif definition.get('slot'):
            if 'r3' in w:
                pay(w,{k:v*quantity for k,v in recipe['cost'].items()})
                for _ in range(quantity):loot._new_instance(w,item,w['stage'],0,'安全四艺制作')
            else:
                if count(w,item)+quantity>CAP:_error('装备库存不足。')
                pay(w,{k:v*quantity for k,v in recipe['cost'].items()});w['gear'].setdefault(item,1);gain(w,item,quantity)
        else:
            totals={k:(v+(1 if _art_level(w,art)==3 and k in {'pill','fire_talisman','guard_talisman'} else 0))*quantity for k,v in output.items()}
            if any(count(w,k)+n>CAP for k,n in totals.items()):_error('完整产物将超过容量，未扣材料。')
            pay(w,{k:v*quantity for k,v in recipe['cost'].items()})
            for k,v in totals.items():gain(w,k,v)
        w['arts'][art]+=(5+w['home']['workshop'])*quantity;w['counters']['crafts']+=quantity
        if 'r3' in w:w['r3']['crafted'][art]+=quantity;w['r3']['crafted_recipes'][p['recipe']]+=quantity
        if art=='alchemy':_progress(w,'craft')
        events.append('完成'+recipe['name']+'，'+C.ARTS[art]+'熟练提升。');return True
    if action in {'world_equip','world_unequip','world_forge'}:
        if 'r3' in w:_error('长线装备按实例操作，请使用实例装备/强化入口。')
        _params(p,['item']);item=p['item'];definition=_catalog(C.ITEMS,item)
        if item not in w['gear'] or not definition.get('slot'):_error('未拥有该自制器。')
        slot=definition['slot']
        if action=='world_equip':
            if w['equipment'][slot]==item:_error('已装备。')
            w['equipment'][slot]=item
        elif action=='world_unequip':
            if w['equipment'][slot]!=item:_error('该器未装备。')
            w['equipment'][slot]=None
        else:
            target=w['gear'][item]+1
            if target>3:_error('强化已满三级。')
            pay(w,{'ore':4*target,'crystal':target});w['gear'][item]=target
        _clamp(w);events.append('器物状态更新：'+definition['name']);return True
    if action in {'world_home','world_family_build'}:
        _params(p,['facility']);facility=p['facility'];key={'orchard':'garden'}.get(facility,facility)
        if action=='world_home':
            if key not in w['home']:_bad('未知洞府设施。')
            target=w['home'][key]+1
            if target>3:_error('设施已经三级。')
            costs={k:v['cost'] for k,v in C.HOMES.items()}
            pay(w,{k:v*target for k,v in costs[key].items()});w['home'][key]=target;w['home_origin'][key]=w['tick']+1
        else:
            if not w['family']:_error('请先创建家族。')
            if key not in w['family_buildings']:_bad('未知家族建设项目。')
            if w['family_buildings'][key]>=3:_error('建设已达三级。')
            pay(w,{'wood':3,'ore':3});w['family_buildings'][key]+=1;w['family_builds']+=1;w['family_renown']+=5
        events.append('完成设施建设。');return True
    return False


def _social(w,action,p,events):
    if action in {'world_sect_join','world_sect_leave','world_sect_daily','world_sect_redeem','world_sect_accept','world_sect_claim'}:
        if action=='world_sect_join':
            _params(p,['sect']);definition=_catalog(C.SECTS,p['sect'])
            if w['sect']:_error('请先退出当前宗门。')
            w['sect']=p['sect'];w['contributions'].setdefault(p['sect'],0);w['sect_earned'].setdefault(p['sect'],0);events.append('加入'+definition['name']+'，贡献按宗门分别保留。')
        else:
            if not w['sect']:_error('尚未加入宗门。')
            sect=w['sect']
            if action=='world_sect_leave':_params(p,[]);w['sect']=None;w['sect_quest']=None;events.append('退出宗门，分宗贡献保留，未交委托取消。')
            elif action=='world_sect_daily':
                _params(p,['item']);item=p['item']
                if item not in {'herb','ore','wood'}:_bad('日常委托仅收草矿木。')
                pay(w,{item:3});gain(w,'xp',4);gain(w,'stone',10);w['contributions'][sect]+=8;w['contribution_total']+=8;w['sect_earned'][sect]+=8;
                if 'r3' in w:w['r3']['daily_count']+=1
                _reputation(w,w['region'],5);events.append('材料委托完成：灵石 +10，宗门贡献 +8，地域声望 +5。')
            elif action=='world_sect_redeem':
                _params(p,['reward']);rewards={'pill':(10,1),'crystal':(20,3),'skill_coupon':(40,1)}
                if p['reward'] not in rewards:_bad('未知贡献兑换。')
                cost,n=rewards[p['reward']]
                if w['contributions'][sect]<cost:_error('当前宗门贡献不足。')
                if count(w,p['reward'])==CAP:_error('奖励库存已满。')
                w['contributions'][sect]-=cost;gain(w,p['reward'],n);events.append('宗门兑换完成。')
            elif action=='world_sect_accept':
                _params(p,['type'])
                if p['type'] not in {'battle','craft','secret'}:_bad('未知宗门委托。')
                if w['sect_quest']:_error('已有未交委托，请完成或退出宗门。')
                w['sect_quest']={'type':p['type'],'done':False};events.append('接取宗门委托，仅计算接取后的行动。')
            else:
                _params(p,[]);q=w['sect_quest']
                if not q or not q['done']:_error('委托尚未完成。')
                gain(w,'xp',12)
                if 'r3' in w:w['r3']['daily_count']+=1
                contribution,coins={'battle':(10,12),'craft':(8,10),'secret':(15,20)}[q['type']]
                w['contributions'][sect]+=contribution;w['contribution_total']+=contribution;w['sect_earned'][sect]+=contribution;gain(w,'stone',coins);w['sect_quest']=None;_reputation(w,w['region'],5);events.append('宗门委托交付，贡献 +%d。'%contribution)
        return True
    if action in {'world_chat','world_gift','world_friend','world_companion','world_master','world_master_leave','world_consult','world_family_invite'}:
        if action=='world_master_leave':
            _params(p,[])
            if not w['master']:_error('尚未拜师。')
            w['master']=None;events.append('辞别NPC师父，已学技艺保留。');return True
        _params(p,['npc']);npc=p['npc'];definition=_catalog(C.NPCS,npc);relation=w['relations'].get(npc,0)
        if action=='world_chat':
            if w['tick']-w['last_chat'].get(npc,-3)<3:_error('与该NPC交谈需间隔3个世界行动。')
            _relation(w,npc,1);w['last_chat'][npc]=w['tick'];events.append(definition['name']+'：山海虽远，材料与心意都可慢慢积累。好感 +1。')
        elif action=='world_gift':pay(w,{definition.get('gift','herb'):2});_relation(w,npc,5);events.append('赠礼给'+definition['name']+'，好感 +5。')
        elif action=='world_friend':
            if npc in w['friends']:_error('已经结交。')
            if relation<30:_error('好感需达到30。')
            w['friends'].append(npc);gain(w,'xp',20);events.append('结交NPC好友'+definition['name']+'。')
        elif action=='world_companion':
            if npc not in w['friends']:_error('请先结交为好友。')
            if w['companion']==npc:_error('已经同行。')
            w['companion']=npc;events.append('邀请NPC同行，每第三回合支援10伤害。')
        elif action=='world_master':
            if w['master']:_error('已有NPC师父，请先辞别。')
            if relation<10:_error('拜师需要好感10。')
            w['master']=npc;events.append('拜'+definition['name']+'为NPC师父。')
        elif action=='world_consult':
            if w['master']!=npc:_error('只能请教当前师父。')
            if w['tick']-w['last_teach']<3:_error('请教需间隔3个世界行动。')
            pay(w,{'stone':5});gain(w,'xp',6)
            for art in ([definition.get('art','alchemy'),'talismans'] if npc=='stargazer' else [definition.get('art','alchemy')]):w['arts'][art]+=5
            _relation(w,npc,2);w['last_teach']=w['tick'];events.append('请教师父，所教学艺熟练 +5，好感 +2。')
        else:
            if not w['family']:_error('请先创建家族。')
            if relation<20:_error('邀请家族成员需要好感20。')
            if npc in w['family_members']:_error('已是族员。')
            w['family_members'].append(npc);events.append('NPC '+definition['name']+'加入家族。')
        return True
    if action=='world_family_create':
        _params(p,['name']);name=p['name']
        if not isinstance(name,str):_bad('家族名必须为文字。')
        name=name.strip()
        if not 1<=len(name)<=16 or any(unicodedata.category(c).startswith('C') for c in name):_bad('家族名须1至16个可显示字符。')
        if w['family']:_error('已有家族。')
        w['family']=name;events.append('建立'+name+'，玩家为族长；可邀请三位NPC共建。');return True
    if action in {'world_disciple','world_teach','world_dispatch','world_collect_disciple','world_cancel_dispatch'}:
        keys=['disciple','destination'] if action=='world_dispatch' else ['disciple'];_params(p,keys);disciple=p['disciple']
        if disciple not in C.DISCIPLES:_bad('未知NPC弟子。')
        if action=='world_disciple':
            if w['stage']<2:_error('元婴后可收徒，洞府简居已具备。')
            if disciple in w['disciples']:_error('该弟子已经入门。')
            w['disciples'][disciple]={'xp':0,'mission':None};events.append('收下NPC弟子。')
        else:
            if disciple not in w['disciples']:_error('该弟子尚未入门。')
            d=w['disciples'][disciple]
            if action=='world_teach':
                if d['mission']:_error('弟子外出期间无法授业。')
                pay(w,{'stone':5} if 'r3' in w else {'xp':5});d['xp']+=5+w['family_buildings']['school'];w['counters']['teaching']+=1;events.append('弟子授业完成，弟子经验提升。')
            elif action=='world_dispatch':
                if d['mission']:_error('已有派遣。')
                if p['destination'] not in {'herb','ore','crystal'}:_bad('未知派遣目标。')
                d['mission']={'item':p['destination'],'end':w['tick']+4};events.append('NPC弟子出发，3个世界行动后领取。')
            elif action=='world_cancel_dispatch':
                if not d['mission']:_error('没有派遣。')
                d['mission']=None;events.append('取消派遣，无奖励，无永久惩罚。')
            else:
                if not d['mission'] or w['tick']<d['mission']['end']:_error('尚未归队。')
                level=3 if d['xp']>=50 else 2 if d['xp']>=20 else 1;item=d['mission']['item'];gain(w,item,1+level//2 if item=='crystal' else 3+level);d['mission']=None;events.append('弟子归队，派遣奖励已领取一次。')
        return True
    return False


def _explore(w,action,p,events):
    if action in {'world_hunt','world_boss'}:
        _params(p,[])
        if w['exploration'] or w['dungeon']:_error('请先结束或撤离当前探索。')
        _start(w,'guard' if action=='world_boss' else 'wild');events.append('世界战斗开始，请观察敌方意图。');return True
    if action=='world_secret_enter':
        _params(p,['secret']);definition=_catalog(C.SECRETS,p['secret'])
        if w['exploration'] or w['dungeon']:_error('已有探索进度，请先撤离。')
        if definition['region']!=w['region']:_error('请先前往该秘境所在地域。')
        w['exploration']={'id':p['secret'],'node':0};events.append('进入'+definition['name']+'，三节点进度会随存档保留。');return True
    if action=='world_secret_step':
        _params(p,['choice']);ex=w['exploration']
        if not ex:_error('尚未进入秘境。')
        material=C.SECRETS[ex['id']]['material']
        if ex['node']==0:
            if p['choice']!='survey':_bad('当前节点需要勘察。')
            gain(w,material,2);ex['node']=1;events.append('勘察秘境，获得材料2份。')
        elif ex['node']==1:
            if p['choice']=='gather':gain(w,material,3)
            elif p['choice']=='rest':
                if w['hp']==attributes(w)['hp']:_error('气血充盈，可选择采集。')
                w['hp']=min(attributes(w)['hp'],w['hp']+40)
            else:_bad('秘境第二节点仅可采集或修整。')
            ex['node']=2;events.append('选择已结算，即将面对守卫。')
        elif ex['node']==2:
            if p['choice']!='fight':_bad('末节点需要挑战守卫。')
            _start(w,'secret',ex['id']);events.append('秘境守卫现身。')
        return True
    if action in {'world_secret_leave','world_dungeon_leave'}:
        _params(p,[]);key='exploration' if action=='world_secret_leave' else 'dungeon'
        if not w[key]:_error('没有进行中的探索。')
        if key=='dungeon':loot.release_run(w)
        w[key]=None;events.append('撤离探索，保留已结算材料，不发未完成通关奖励。');return True
    if action=='world_dungeon_enter':
        _params(p,['dungeon','difficulty']);definition=_catalog(C.DUNGEONS,p['dungeon']);difficulty=p['difficulty']
        if not _int(difficulty,1,3):_bad('副本难度须为1至3整数。')
        if w['stage']<difficulty-1:_error('境界不足以进入该难度。')
        if w['dungeon'] or w['exploration']:_error('请先结束当前探索。')
        if definition['region']!=w['region']:_error('请先前往副本所在地。')
        w['dungeon']={'id':p['dungeon'],'difficulty':difficulty,'stage':w['stage'],'round':0};events.append('进入三战副本，敌人按入场境界快照生成。');return True
    if action=='world_dungeon_next':
        _params(p,[]);d=w['dungeon']
        if not d:_error('尚未进入副本。')
        _start(w,'dungeon',d['id'],d['difficulty'],d['stage']);events.append('副本第%d战开始。'%(d['round']+1));return True
    if action=='world_encounter':
        _params(p,['choice']);ex=w['encounter']
        if not ex:_error('当前没有奇遇。')
        if p['choice']=='leave':w['encounter']=None;events.append('放下奇遇，无惩罚。');return True
        definition=C.EVENTS[ex['id']];choice=_catalog(definition['choices'],p['choice'])
        if 'r3' in w and ex['id'] in R.ENCOUNTER_OVERRIDES:choice=R.ENCOUNTER_OVERRIDES[ex['id']][p['choice']]
        pay(w,choice.get('cost',{}))
        if choice.get('battle'):_start(w,'escort')
        reward=choice.get('reward',{})
        for item,n in reward.items():
            if item=='reputation':_reputation(w,w['region'],n)
            elif item=='relation':
                for npc in C.NPCS:_relation(w,npc,n)
            elif not choice.get('battle'):gain(w,item,n)
        w['encounter']=None;events.append('奇遇选择：'+choice['name']+'；结果已结算。');return True
    return False


def _price(w,item,buy):
    base=2 if item in {'herb','ore','wood','crystal'} else C.ITEMS[item].get('buy' if buy else 'sell',0)
    if not buy and item in {'herb','ore','wood','crystal'}:base=2
    factor=1
    if w['event'] and (w['event']['id']=='herb' and item=='herb' or w['event']['id']=='trade' and item in {'ore','wood','crystal'}):factor=.8
    if buy and w['factions'].get(w['region'],0)>=20:factor*=.9
    return max(1,math.ceil(base*factor) if buy else math.floor(base*factor))


def _economy(w,action,p,events):
    if action in {'world_buy','world_sell'}:
        _params(p,['item','quantity']);item=p['item'];quantity=p['quantity']
        if item not in {'herb','ore','wood','crystal','pill','fire_talisman'} or not _int(quantity,1,20):_bad('交易物品或数量无效。')
        price=_price(w,item,action=='world_buy')*quantity
        if action=='world_buy':
            if count(w,item)+quantity>CAP:_error('背包容量不足。')
            pay(w,{'stone':price});gain(w,item,quantity)
        else:
            if w['wallet']+price>CAP:_error('灵石已满。')
            pay(w,{item:quantity});gain(w,'stone',price)
        events.append(('购买' if action=='world_buy' else '出售')+'%s ×%d，%d灵石。'%(item_name(item),quantity,price));return True
    if action=='world_auction_list':
        _params(p,['item','quantity','price']);item=p['item'];quantity=p['quantity'];price=p['price']
        if item not in {'herb','ore','wood','crystal','pill'} or not _int(quantity,1,20) or not _int(price,1,1000):_bad('寄售物品、数量或底价无效。')
        if sum(1 for a in w['auctions'] if a['seller']=='player' and not a['settled'] and not a['cancelled'])>=3:_error('最多三笔进行中寄售。')
        pay(w,{item:quantity})
        if not _order(w,'player',item,quantity,price,w['tick']+1):_error('拍卖保留/活跃订单已满，请先领货。')
        events.append('物品已托管至NPC拍卖，6行动到期；有人出价后不可撤单。');return True
    if action in {'world_auction_bid','world_auction_cancel'}:
        _params(p,['auction','price'] if action=='world_auction_bid' else ['auction']);a=next((a for a in w['auctions'] if a['id']==p['auction']),None)
        if not a:_bad('未知拍卖。')
        if a['settled'] or a['cancelled'] or w['tick']>=a['end']:_error('拍卖已经结束。')
        if action=='world_auction_cancel':
            if a['seller']!='player':_error('只能撤销自己的寄售。')
            if a['bidder'] is not None:_error('已经有人出价，不能撤单。')
            _deliver(w,'player',a['item'],a['quantity'],a);a['cancelled']=True;events.append('寄售已撤销，托管物品返还。')
        else:
            if a['seller']=='player':_error('不能竞拍自己的寄售。')
            price=p['price']
            if not _int(price,1,CAP):_bad('出价须为正整数。')
            if price<max(a['base'],a['price']+1):_error('出价至少为%d灵石。'%max(a['base'],a['price']+1))
            pay(w,{'stone':price-a['price'] if a['bidder']=='player' else price})
            if a['bidder']!='player':_refund(w,a)
            a['price']=price;a['bidder']='player';a['last_bid']=w['tick']+1;events.append('出价%d灵石已托管，到期交割；被NPC超价则退款。'%price)
        return True
    return False


def _quest_ready(w,quest):
    kind=quest['kind'];target=quest['target'];amount=quest['amount']
    if kind=='counter':return {'craft_total':w['counters']['crafts'],'sect_contribution_total':w['contribution_total'],'family_build_total':w['family_builds']}[target]>=amount
    if kind=='deliver':
        if 'r3' in w and target in R.EQUIPMENT:return loot.ready_template(w,target) is not None
        return count(w,target)-(1 if target in w['equipment'].values() else 0)>=amount
    if kind=='secret':return target in w['secret_wins']
    if kind=='finale':return w['stage']==7 and '7' in w['guard_wins'] and len(w['secret_wins'])==len(C.SECRETS)
    return False


def _achievement_count(w,kind):return {'battle':w['counters']['battles'],'craft':w['counters']['crafts'],'friends':len(w['friends'])}[kind]


def _quests(w,action,p,events):
    if action in {'world_quest_accept','world_quest_claim'}:
        _params(p,['quest']);q=_catalog(C.QUESTS,p['quest']);status=w['quests'].get(p['quest'])
        if action=='world_quest_accept':
            if status:_error('任务已经接取或完成。')
            w['quests'][p['quest']]='active';events.append('接取：'+q['name'])
        else:
            if status!='active':_error('请先接取任务，已领任务不可重复领取。')
            if not _quest_ready(w,q):_error('目标尚未完成：'+q['description'])
            if q['kind']=='deliver':
                if 'r3' in w and q['target'] in R.EQUIPMENT:loot.consume_template(w,q['target'])
                else:pay(w,{q['target']:q['amount']})
                if q['target'] in w['gear'] and count(w,q['target'])==0:del w['gear'][q['target']]
            for item,n in q['reward'].items():
                if item=='relation':_relation(w,q['npc'],n)
                else:gain(w,item,n)
            gain(w,'xp',15 if q.get('npc') else 30);w['quests'][p['quest']]='claimed';events.append('任务完成：'+q['name']+'，奖励仅发放一次。')
        return True
    if action=='world_achievement':
        _params(p,['kind','tier']);kind=p['kind'];definition=_catalog(C.ACHIEVEMENTS,kind);tier=p['tier']
        if not _int(tier,0,2):_bad('成就档位必须0至2。')
        key=kind+':'+str(tier)
        if key in w['achievements']:_error('此档成就已领取。')
        if _achievement_count(w,kind)<definition['tiers'][tier]:_error('成就进度不足。')
        for item,n in definition['rewards'][tier].items():gain(w,item,n)
        w['achievements'].append(key);events.append('成就达成：'+definition['name']+'第%d档。'%(tier+1));return True
    if action=='world_title':
        _params(p,['title']);title=_catalog(C.TITLES,p['title'])
        if _achievement_count(w,title['achievement'])<title['threshold']:_error('称号条件尚未达成。')
        if w['title']==p['title']:_error('已佩戴此称号。')
        w['title']=p['title'];events.append('佩戴称号：'+title['name']);return True
    if action=='world_arena':
        _params(p,['opponent','mode']);_catalog(C.ARENA_OPPONENTS,p['opponent'])
        if p['mode']!='local':_bad('跨域赛请使用正式报名与赛程入口。')
        if w['exploration'] or w['dungeon']:_error('请先结束当前探索。')
        _start(w,'regional' if p['mode']=='regional' else 'arena',p['opponent']);events.append('开始本地NPC模拟演武，丹符消耗只影响本次演练，战后恢复真实背包。');return True
    return False


def apply_action(state,action,params,context=None):
    if state is None:_error('请先创建角色。','NO_GAME')
    if not isinstance(action,str) or not action.startswith('world_') or not isinstance(params,dict):_bad('世界行动格式错误。')
    params=_normalize(action,params)
    result=clone(state);w=result['world'];events=[]
    if action=='world_enter' and not state['completed']:_error('需先完成序章，平息归墟之影。')
    if not w['active'] and action!='world_enter':_error('请先完成序章并进入修仙界。')
    steps=_execute(w,action,params,events,context=context)
    steps=steps if type(steps) is int else 1
    _clamp(w)
    advances=action not in {'world_travel','world_enter'}
    if action=='world_enter':result['actions_taken']+=1
    if advances:
        for _ in range(steps):
            w['tick']+=1;result['actions_taken']+=1;_ai(w,events)
    if 'r3' in w:
        activities.observe(state['world'],w,action,params,context)
        journey.observe(state['world'],w,action,params)
    result['logs']=(result['logs']+['第%d行 · %s'%(result['actions_taken'],line) for line in events])[-100:]
    w['journal']=(w['journal']+events)[-100:]
    validate(result)
    return result,events


def _misc(w,action,p,events):
    if action=='world_array_toggle':
        _params(p,['array']);key=p['array']
        if key not in w['arrays']:_bad('未知阵法。')
        if not w['arrays'][key]:_error('尚未建成此阵。')
        w['arrays_enabled'][key]=not w['arrays_enabled'][key]
        if 'r3' in w and w['arrays_enabled'][key]:loot.mark_use(w,'formations')
        events.append('阵法'+('启用' if w['arrays_enabled'][key] else '暂停')+'，不退材料。');return True
    if action=='world_home_collect':
        _params(p,['facility']);key=p['facility']
        if key not in w['home']:_bad('未知设施。')
        amount=w['home_storage'][key];item=C.HOME_PRODUCTION[key]['item']
        if not amount:_error('仓库尚无产出，每3世界行动生产。')
        if count(w,item)+amount>CAP:_error('背包容量不足，仓库保留不变。')
        gain(w,item,amount);w['home_storage'][key]=0;events.append('收取洞府%s ×%d。'%(item_name(item),amount));return True
    if action=='world_delivery':
        _params(p,['auction']);order=next((a for a in w['auctions'] if a['id']==p['auction']),None)
        if not order:_bad('未知订单。')
        if not order['delivery']:_error('没有待领资产。')
        if any((w['wallet'] if k=='stone' else count(w,k))+n>CAP for k,n in order['delivery'].items()):_error('容量不足，待领资产将完整保留。')
        for item,n in order['delivery'].items():gain(w,item,n)
        order['delivery']={};events.append('订单溢出托管资产已完整领取一次。');return True
    if action=='world_wait':
        _params(p,[])
        pending=any(not a['settled'] and not a['cancelled'] for a in w['auctions']) or any(d['mission'] and d['mission']['end']>w['tick'] for d in w['disciples'].values()) or any(level and w['home_storage'][key]<20*level for key,level in w['home'].items())
        if not pending:_error('没有订单、派遣或生产等待事项，请进行实际修行。')
        events.append('守候一个世界行动，订单、派遣和洞府生产按规则推进。');return True
    if action=='world_family_dissolve':
        _params(p,[])
        if not w['family']:_error('没有家族。')
        w['family']=None;w['family_members']=[];w['family_buildings']={'garden':0,'guard':0,'school':0};_clamp(w);events.append('家族解散，不退建设材料；历史建设保留，被动效果停止。');return True
    if action=='world_family_remove':
        _params(p,['npc']);_catalog(C.NPCS,p['npc'])
        if not w['family'] or p['npc'] not in w['family_members']:_error('不是本族成员。')
        w['family_members'].remove(p['npc']);events.append('NPC离开家族，关系不清空。');return True
    if action=='world_disciple_release':
        _params(p,['disciple']);key=p['disciple']
        if key not in w['disciples']:_error('未招收该弟子。')
        if w['disciples'][key]['mission']:_error('请先取消派遣再解除师徒。')
        del w['disciples'][key];events.append('NPC弟子辞行，原有世界成长保留。');return True
    if action=='world_companion_leave':
        _params(p,[])
        if not w['companion']:_error('当前没有同行。')
        w['companion']=None;events.append('与同行暂别，友谊保留。');return True
    if action=='world_season_join':
        _params(p,[]);arena=w['arena']
        if arena['current'] and not arena['current']['claimed']:_error('当前赛季尚未结算，请继续赛程。')
        arena['season']+=1;arena['current']={'id':arena['season'],'stage':w['stage'],'round':0,'claimed':False,'npc_scores':{k:0 for k in C.ARENA_OPPONENTS},'growth':arena['growth']};events.append('报名三域NPC模拟跨域赛，三场对手已锁定本季境界快照。');return True
    if action=='world_season_fight':
        _params(p,[]);season=w['arena']['current']
        if not season or season['round']>=3:_error('请先报名，或领取本季冠军奖励。')
        if w['exploration'] or w['dungeon']:_error('请先结束当前探索。')
        target=C.CROSS_DOMAIN['rounds'][season['round']]['opponent'];_start(w,'regional',target,stage=season['stage']);w['battle']['growth']=season['growth'];events.append('进入'+C.CROSS_DOMAIN['rounds'][season['round']]['name']+'，胜利晋级，败退可重试。');return True
    if action=='world_season_claim':
        _params(p,[]);season=w['arena']['current']
        if not season or season['round']!=3 or season['claimed']:_error('需完成三胜，且本季未结算。')
        if w['wallet']+30>CAP or count(w,'crystal')+3>CAP:_error('冠军奖励容量不足，请先整理资产。')
        gain(w,'stone',30);gain(w,'crystal',3);w['family_renown']+=5;season['claimed']=True;w['arena']['growth']=min(10,w['arena']['growth']+1);events.append('三域NPC赛冠军结算：灵石30、灵晶3、家族声望5；可开启下一季。');return True
    return False


SCHEMAS={
 'world_activity_accept':{'project':'str'},'world_activity_week_accept':{},'world_activity_claim':{'key':'str'},

 'world_loot_equip':{'uid':'str'},'world_loot_unequip':{'slot':'str'},'world_loot_choose':{'uid':'str','effect_type':'str'},
 'world_loot_enhance':{'uid':'str'},'world_loot_quality':{'uid':'str'},'world_loot_dismantle':{'uid':'str'},
 'world_loot_craft_treasure':{'slot':'str','effect_type':'str'},'world_loot_exchange':{'item':'str'},'world_loot_claim':{'receipt':'str'},
 'world_boss_enter':{},'world_boss_claim':{'day':'str'},
 'world_milestone_accept':{'stage':'stage','tier':'milestone','branch':'str'},'world_milestone_claim':{'stage':'stage','tier':'milestone'},
 'world_enter':{},'world_cultivate':{},'world_rest':{},'world_gather':{'item':'str'},'world_travel':{'region':'str'},
 'world_root':{'choice':'str'},'world_constitution':{'choice':'str'},'world_root_train':{},'world_constitution_train':{},'world_dew':{},
 'world_skill_learn':{'skill':'str'},'world_skill_equip':{'skill':'str'},'world_skill_upgrade':{'skill':'str'},'world_advance':{},'world_finish':{},
 'world_craft':{'recipe':'str','quantity':'qty'},'world_equip':{'item':'str'},'world_unequip':{'item':'str'},'world_forge':{'item':'str'},
 'world_home':{'facility':'str'},'world_home_collect':{'facility':'str'},'world_family_build':{'facility':'str'},'world_array_toggle':{'array':'str'},
 'world_sect_join':{'sect':'str'},'world_sect_leave':{},'world_sect_daily':{'item':'str'},'world_sect_redeem':{'reward':'str'},'world_sect_accept':{'type':'str'},'world_sect_claim':{},
 'world_chat':{'npc':'str'},'world_gift':{'npc':'str'},'world_friend':{'npc':'str'},'world_companion':{'npc':'str'},'world_master':{'npc':'str'},'world_master_leave':{},'world_consult':{'npc':'str'},'world_family_invite':{'npc':'str'},'world_family_create':{'name':'str'},'world_family_dissolve':{},'world_family_remove':{'npc':'str'},'world_companion_leave':{},
 'world_disciple':{'disciple':'str'},'world_teach':{'disciple':'str'},'world_dispatch':{'disciple':'str','destination':'str'},'world_collect_disciple':{'disciple':'str'},'world_cancel_dispatch':{'disciple':'str'},'world_disciple_release':{'disciple':'str'},
 'world_story_accept':{'story':'str'},'world_story_claim':{'story':'str'},'world_elite_enter':{'elite':'str'},
 'world_hunt':{},'world_boss':{},'world_secret_enter':{'secret':'str'},'world_secret_step':{'choice':'str'},'world_secret_leave':{},'world_dungeon_enter':{'dungeon':'str','difficulty':'difficulty'},'world_dungeon_next':{},'world_dungeon_sweep':{'dungeon':'str','difficulty':'difficulty','chapter':'chapter'},'world_dungeon_leave':{},'world_encounter':{'choice':'str'},
 'world_buy':{'item':'str','quantity':'qty'},'world_sell':{'item':'str','quantity':'qty'},'world_auction_list':{'item':'str','quantity':'qty','price':'price'},'world_auction_bid':{'auction':'str','price':'bid'},'world_auction_cancel':{'auction':'str'},'world_delivery':{'auction':'str'},
 'world_quest_accept':{'quest':'str'},'world_quest_claim':{'quest':'str'},'world_achievement':{'kind':'str','tier':'tier'},'world_title':{'title':'str'},'world_arena':{'opponent':'str','mode':'str'},'world_season_join':{},'world_season_fight':{},'world_season_claim':{},'world_wait':{},
 'world_auto_battle':{'strategy':'str'}}


def _normalize(action,params):
    if action not in SCHEMAS:_bad('未知世界行动。')
    p=dict(params)
    if action=='world_craft' and 'quantity' not in p:p['quantity']=1
    schema=dict(SCHEMAS[action])
    if action=='world_dungeon_enter' and 'chapter' in p:schema['chapter']='chapter'
    if action=='world_story_claim' and 'item' in p:schema['item']='str'
    _params(p,schema)
    for key,kind in schema.items():
        value=p[key]
        if kind=='str':
            if not isinstance(value,str) or not 1<=len(value)<=300:_bad('参数%s须为有效字符串。'%key)
        elif not _int(value,{'qty':1,'difficulty':1,'price':1,'bid':1,'tier':0,'chapter':0,'stage':0,'milestone':25}[kind],{'qty':20,'difficulty':3,'price':1000,'bid':CAP,'tier':2,'chapter':7,'stage':7,'milestone':75}[kind]):_bad('参数%s不是允许范围内的整数。'%key)
    return p


def _execute(w,action,p,events,context=None):
    if 'r3' in w and not w['battle']:
        if action in {'world_dungeon_enter','world_dungeon_sweep'}:
            if w['dungeon'] or w['exploration']:_error('请先结束当前探索。')
            definition=_catalog(C.DUNGEONS,p['dungeon']);chapter=p.get('chapter',w['stage'])
            if definition['region']!=w['region']:_error('请先前往副本所在地。')
            if action=='world_dungeon_sweep':
                key='%s:%d:%d'%(p['dungeon'],chapter,p['difficulty'])
                if key not in w['r3'].get('journey',{}).get('manual_clears',[]):_error('需先同章同难真实手战通关一次。')
                if w['r3'].get('cadence',{}).get('available',0)<1:_error('扫荡需要1次恢复挑战资格；零次仍可手战练习。')
            run_id=loot.begin_run(w,p['dungeon'],chapter,p['difficulty'],context)
            w['dungeon']={'id':p['dungeon'],'difficulty':p['difficulty'],'stage':chapter,'round':0,'run_id':run_id}
            if action=='world_dungeon_sweep':
                w['r3']['runs'][run_id]['manual']=False
                _complete_dungeon(w,events,manual=False);events.append('扫荡复用正式通关掉落，不产生新手战证明。');return
            events.append('章节固定副本开始；掉落序号、品质、配置和恢复型挑战资格预约已绑定本次run。');return
        if journey.handle(w,action,p,events):return
        if loot.handle(w,action,p,events,context):return
    if w['battle']:return _battle(w,action,p,events,context)
    elif action=='world_auto_battle':_error('当前不在世界战斗中。')
    elif not any(handler(w,action,p,events) for handler in [_growth,_craft,_social,_explore,_economy,_quests,_misc]):_bad('未知世界行动。')


def _deep_validate(w):
    def invalid(message='世界嵌套数据无效'):raise ValueError(message)
    def shape(value,keys):
        if not isinstance(value,dict) or set(value)!=set(keys):invalid()
    def scalar(value,lo=0,hi=CAP):
        if not _int(value,lo,hi):invalid()
    def enum(value,catalog):
        if not isinstance(value,str) or value not in catalog:invalid()
    for key in ['root','constitution']:
        if type(w[key]['awakened']) is not bool:invalid()
    for key in ['home_storage','home_origin']:
        shape(w[key],w['home'])
        for facility,n in w[key].items():scalar(n,0,20*w['home'][facility] if key=='home_storage' else w['tick'])
    shape(w['arrays_enabled'],w['arrays'])
    if any(type(v) is not bool for v in w['arrays_enabled'].values()):invalid()
    if not isinstance(w['sect_earned'],dict) or any(k not in C.SECTS or not _int(v) for k,v in w['sect_earned'].items()):invalid()
    scalar(w['family_renown'])
    if any(v>100 for v in w['relations'].values()) or any(v>100 for v in w['factions'].values()):invalid()
    if any(k not in C.QUESTS or v not in {'active','claimed'} for k,v in w['quests'].items()):invalid()
    if any(k not in C.NPCS or not isinstance(v,str) for k,v in w['dialogue'].items()):invalid()
    shape(w['counters'],{'battles','crafts','teaching','gathers','wins'})
    if any(not C.ITEMS.get(k,{}).get('slot') or count(w,k)<1 for k in w['gear']):invalid()
    if w['sect'] and (w['sect'] not in w['contributions'] or w['sect'] not in w['sect_earned']):invalid()
    if not w['family'] and (w['family_members'] or any(w['family_buildings'].values())):invalid()
    if 'stone' in w['inventory']:invalid('凡界灵石只能位于钱包')
    if len(w['disciples'])>3:invalid()
    for key,d in w['disciples'].items():
        enum(key,C.DISCIPLES);shape(d,{'xp','mission'});scalar(d['xp'])
        if d['mission'] is not None:
            shape(d['mission'],{'item','end'});enum(d['mission']['item'],{'herb','ore','crystal'});scalar(d['mission']['end'])
    if w['active'] and set(w['npc_agents'])!=set(C.NPCS):invalid()
    for key,agent in w['npc_agents'].items():
        enum(key,C.NPCS);shape(agent,{'wallet','inventory','turns','last','pending'});scalar(agent['wallet'],0,200);scalar(agent['turns'])
        if not isinstance(agent['last'],str) or len(agent['last'])>1000 or not isinstance(agent['inventory'],dict):invalid()
        for item,n in agent['inventory'].items():enum(item,dict(C.ITEMS,**C.RESOURCES));scalar(n,0,200)
        if not isinstance(agent['pending'],dict):invalid()
        for item,n in agent['pending'].items():enum(item,dict(C.ITEMS,**C.RESOURCES));scalar(n)
    if w['sect_quest'] is not None:
        shape(w['sect_quest'],{'type','done'});enum(w['sect_quest']['type'],{'battle','craft','secret'})
        if type(w['sect_quest']['done']) is not bool or not w['sect']:invalid()
    if w['event'] is not None:
        shape(w['event'],{'id','name','end'});enum(w['event']['id'],{'herb','beast','trade'});scalar(w['event']['end'])
        if not isinstance(w['event']['name'],str):invalid()
    if w['encounter'] is not None:
        shape(w['encounter'],{'id','end'});enum(w['encounter']['id'],{'traveler','furnace','inscription'});scalar(w['encounter']['end'])
    if w['exploration'] is not None:
        shape(w['exploration'],{'id','node'});enum(w['exploration']['id'],C.SECRETS);scalar(w['exploration']['node'],0,2)
    if w['dungeon'] is not None:
        shape(w['dungeon'],{'id','difficulty','stage','round'}|({'run_id'} if 'r3' in w else set()));enum(w['dungeon']['id'],C.DUNGEONS);scalar(w['dungeon']['difficulty'],1,3);scalar(w['dungeon']['stage'],0,7);scalar(w['dungeon']['round'],0,2)
    if w['dungeon'] and w['exploration']:invalid()
    for value in w['guard_wins']:
        if value not in {str(i) for i in range(8)} or int(value)>w['stage']:invalid()
    for value in w['secret_wins']:enum(value,C.SECRETS)
    for value in w['dungeon_wins']:
        if value not in ({'%s:%d:%d'%(k,s,i) for k in C.DUNGEONS for s in range(8) for i in range(1,4)} if 'r3' in w else {k+':'+str(i) for k in C.DUNGEONS for i in range(1,4)}):invalid()
    for value in w['achievements']:
        if value not in {k+':'+str(i) for k in C.ACHIEVEMENTS for i in range(3)}:invalid()
    if w['battle'] is not None:
        b=w['battle'];shape(b,{'name','hp','max_hp','attack','heavy','turn','kind','target','stage','shield','heals','snapshot','start_tick','growth'}|({'r3_day','r3_attempt','player_damage','commands'} if b.get('kind')=='world_boss' and 'r3' in w else {'mechanic','poison_turns','poison_damage','barrier'} if 'r3' in w and b.get('kind')=='elite' else {'mechanic','poison_turns','poison_damage','barrier'} if 'r3' in w and b.get('kind')=='dungeon' and w.get('dungeon') and w['dungeon'].get('difficulty',0)>=2 and w['dungeon'].get('round')==2 else set()))
        if not isinstance(b['name'],str) or not isinstance(b['target'],str):invalid()
        scalar(b['start_tick'],0,w['tick']);scalar(b['growth'],0,10);scalar(b['stage'],0,7);scalar(b['shield'],0,2);scalar(b['heals'],0,2)
        if b.get('mechanic'):
            if b['kind']=='elite':
                if b['target'] not in G.ELITES or b['mechanic']!=G.ELITES[b['target']]['mechanic'] or b['stage']!=G.ELITES[b['target']]['chapter']:invalid()
                e=G.ELITES[b['target']]
                j=w['r3'].get('journey',{});record=j.get('stories',{}).get(e['story'])
                if not record or record['claimed'] or b['target'] in j.get('elite_wins',[]) or w['region']!=e['region']:invalid()
                if b['max_hp']!=e['hp'] or b['attack']!=e['attack'] or b['heavy']!=e['heavy'] or b['poison_damage']!=e['poison_damage'] or e['story'] not in w['r3'].get('journey',{}).get('stories',{}):invalid()
            elif b['mechanic']!=G.DUNGEON_MECHANICS[b['target']]['id']:invalid()
            scalar(b['poison_turns'],0,2);scalar(b['poison_damage']);scalar(b['barrier'],0,b['max_hp']//4)
        if b['kind']=='world_boss':
            scalar(b['player_damage'],0,R.BOSS['hp']);scalar(b['commands'],0,R.BOSS['rounds'])
            period=w['r3']['boss'].get(b['r3_day'])
            if not period or b['r3_attempt'] not in period['runs'] or period['runs'][b['r3_attempt']]['settled'] or b['target']!=b['r3_attempt'] or b['stage']!=period['stage']:invalid()
        if b['kind']=='secret' and (not w['exploration'] or b['target']!=w['exploration']['id']):invalid()
        if b['kind']=='dungeon' and (not w['dungeon'] or b['target']!=w['dungeon']['id']):invalid()
        if b['kind'] in {'arena','regional'}:
            enum(b['target'],C.ARENA_OPPONENTS);shape(b['snapshot'],{'hp','mp','inventory'});scalar(b['snapshot']['hp'],1,attributes(w)['hp']);scalar(b['snapshot']['mp'],0,attributes(w)['mp'])
            if not isinstance(b['snapshot']['inventory'],dict):invalid()
            for item,n in b['snapshot']['inventory'].items():enum(item,dict(C.ITEMS,**C.RESOURCES));scalar(n)
        elif b['snapshot'] is not None:invalid()
    ids=[]
    for a in w['auctions']:
        if not isinstance(a['id'],str) or not a['id'].isdigit():invalid()
        ids.append(a['id']);scalar(a['last_bid']);scalar(a['base'],1,1000);scalar(a['price'])
        if a['seller']!='player':enum(a['seller'],C.NPCS)
        if a['bidder'] is not None and a['bidder']!='player':enum(a['bidder'],C.NPCS)
        if a['seller']==a['bidder']:invalid()
        if a['bidder'] is None and a['price']!=0 or a['bidder'] is not None and a['price']<a['base']:invalid()
        if not isinstance(a['delivery'],dict):invalid()
        for item,n in a['delivery'].items():enum(item,dict(C.ITEMS,**C.RESOURCES));scalar(n)
    if len(ids)!=len(set(ids)):invalid()
    arena=w['arena'];scalar(arena['growth'],0,10)
    if any(not isinstance(v,str) for v in arena['claims']) or len(arena['claims'])!=len(set(arena['claims'])):invalid()
    current=arena['current']
    if current is not None:
        shape(current,{'id','stage','round','claimed','npc_scores','growth'});scalar(current['id'],1,arena['season']);scalar(current['stage'],0,7);scalar(current['round'],0,3);scalar(current['growth'],0,10)
        if type(current['claimed']) is not bool or current['claimed'] and current['round']!=3:invalid()
        shape(current['npc_scores'],C.ARENA_OPPONENTS)
        for n in current['npc_scores'].values():scalar(n,0,10)
    if w['extension']!={'content_version':1,'realm_cap':'渡劫','next_realm_locked':True}:invalid()


def _cost_text(cost):return '、'.join('%s ×%d'%(item_name(k),n) for k,n in cost.items()) or '免费'


def project(state,context=None):
    w=state['world'];stage=C.STAGES[w['stage']]['name'];attrs=attributes(w)
    # Each projected action is dry-run on a private deep copy; projection never mutates w, so one
    # pickle snapshot unpickled per action equals clone(w) at a fraction of the cost.
    frozen=pickle.dumps(w,protocol=pickle.HIGHEST_PROTOCOL)
    pages=[dict(id=id,label=label,title=label+' · '+stage,description='',stats=[],sections=[],actions=[]) for id,label in PAGES];by={p['id']:p for p in pages}
    def section(page,title,rows=None,body=''):
        by[page]['sections'].append({'title':title,'body':body,'rows':[{'label':str(k),'value':str(v)} for k,v in (rows or [])]})
    def add(page,id,label,cost,effect,params=None,fields=None,probe=None,confirm=None):
        params=params or {};fields=fields or [];reason=''
        try:
            if not w['active']:_error('需完成序章并进入修仙界。')
            normalized=_normalize(id,{**params,**(probe or {})})
            # 自动斗法会整场演算；投影只校验参数，战斗存在性已由本页是否进入战斗保证。
            if id!='world_auto_battle':_execute(pickle.loads(frozen),id,normalized,[],context=context)
        except Exception as exc:
            from .rules import GameError
            if not isinstance(exc,GameError):raise
            reason=exc.message
        action=dict(id=id,label=label,detail=label+'：'+cost+'；'+effect+'。',cost=cost,effect=effect,enabled=not reason,reason=reason,params=params,primary=False,group=page)
        if fields:action['fields']=fields
        if confirm:action['confirm']=confirm
        by[page]['actions'].append(action)
    def select(name,label,choices):return dict(name=name,label=label,type='select',required=True,options=[{'value':str(k),'label':str(v)} for k,v in choices])
    def number(name,label,lo,hi):return dict(name=name,label=label,type='number',required=True,min=lo,max=hi)
    def text(name,label,maximum):return dict(name=name,label=label,type='text',required=True,maxLength=maximum)
    for page in pages:
        page['description']='单人本地凡界；规则AI与NPC模拟，无真人、无真实跨服。'
    by['world']['stats']=[{'label':'世界行动','value':str(w['tick'])},{'label':'境界','value':stage},{'label':'凡界终章','value':'已完成' if w['ending'] else '尚未封界'}]
    section('world','三洲与势力',[(v['name'],v['description']+' 势力：'+v['faction']+'；声望%d / 100。'%w['factions'].get(k,0)) for k,v in C.REGIONS.items()])
    for id,region in C.REGIONS.items():add('world','world_travel','前往'+region['name'],'免费，不推进世界行动','到达'+region['name'],{'region':id})
    for item in ['herb','ore','wood','crystal']:add('world','world_gather','采集'+item_name(item),'免费','材料可再生，按地域、禀赋、家园及事件加成；最多至库存上限',{'item':item})
    add('world','world_wait','守候进度','免费','仅在有订单、派遣或生产时推进一个世界行动')
    section('world','规则AI动态',[(C.NPCS[k]['name']+'（NPC）','钱包%d；待入库资产%s；行为%d次；%s'%(a['wallet'],_cost_text(a['pending']) if a['pending'] else '无',a['turns'],a['last'])) for k,a in w['npc_agents'].items()],body=('当前动态：'+w['event']['name']+'，剩%d行动。'%(w['event']['end']-w['tick']) if w['event'] else '当前无全域动态事件；每20个世界行动轮换。')+' 三类NPC依次采料、按配方制作、寄售和竞拍，钱包库存真实保存。')
    if w['ending']:section('world','凡界终章 · 山河守望',body=C.STORIES['ending'])
    section('world','凡界与仙界边界',[('当前版本','完整凡界，止于渡劫封界'),('仙界','版本化扩展接口已预留，当前不可进入')])
    by['character']['stats']=[{'label':k,'value':str(v)} for k,v in [('气血','%d / %d'%(w['hp'],attrs['hp'])),('灵力','%d / %d'%(w['mp'],attrs['mp'])),('攻击',attrs['attack']),('修为',w['xp'])]]
    section('character','当前成长目标',[('下一关','凡界界门已封，修行未止。' if w['ending'] else _advance_reason(w) or '条件已齐，可突破。'),('凡界灵石',w['wallet']),('当前功法',C.SKILLS[w['skill']]['name']+' %d级'%w['skills'][w['skill']])])
    add('character','world_cultivate','吐纳修炼','免费','修为随境界、木灵根、聚灵阵与称号增加')
    add('character','world_rest','静养恢复','免费','恢复气血最多80、灵力最多30，再加体质/静室/称号效果')
    add('character','world_advance','突破下一境界','修为%d及阶段条件'%(C.STAGES[w['stage']]['xp_cost']),'保证突破，恢复新气血灵力上限')
    add('character','world_finish','完成凡界终章','渡劫首胜、三秘境与主线任务','封闭凡界界门，保留经营与重复挑战')
    for key,catalog,action in [('root',C.ROOTS,'world_root'),('constitution',C.CONSTITUTIONS,'world_constitution')]:
        obj=w[key];section('character','灵根' if key=='root' else '体质',[('当前',catalog[obj['id']]['name']+' %d级'%obj['level']),('觉醒','第一次选择免费' if not obj['awakened'] else '重修消耗30凡界灵石')])
        add('character',action,'鉴定灵根' if key=='root' else '选择体质','首次免费，之后30灵石','基础增益按等级+1；更改只截断上限，不回满',fields=[select('choice','选择禀赋',[(k,v['name']+'：'+v['description']) for k,v in catalog.items()])],probe={'choice':next(k for k in catalog if k!=obj['id'])})
        add('character','world_root_train' if key=='root' else 'world_constitution_train','温养灵根' if key=='root' else '锻炼体质','草6晶1' if key=='root' else '矿4晶1','培养一级，最高3级')
    add('character','world_dew','服用养根露','养根露1','每3点灵根升一级，最高3级')
    for id,skill in C.SKILLS.items():
        section('character',skill['name'],[('效果',skill['description']),('已学等级',w['skills'].get(id,0))])
        for action,label,cost in [('world_skill_learn','学习','20灵石'),('world_skill_equip','装备','免费'),('world_skill_upgrade','进修','20×目标级灵石与目标级灵晶；券可抵灵石')]:add('character',action,label+skill['name'],cost,'影响当前功法；不会免费回血回灵',{'skill':id})
    section('character','凡界背包',[(item_name(k),n) for k,n in w['inventory'].items() if n],body='序章财富仅存旧卷；本页为凡界独立资产，不暗中互换。')
    for item,level in w['gear'].items():
        for action,label,cost in [('world_equip','装备','免费'),('world_unequip','卸下','免费'),('world_forge','强化','矿石4×目标级、灵晶目标级')]:add('character',action,label+item_name(item),cost,'每槽一件，效果派生，强化最高3级',{'item':item})
    sect=w['sect'];contribution=w['contributions'].get(sect,0)
    section('sects','宗门身份',[('当前宗门',C.SECTS[sect]['name'] if sect else '散修'),('可用贡献',contribution),('本宗历史贡献',w['sect_earned'].get(sect,0)),('累计历史',w['contribution_total']),('职位',C.SECT_RULES['rank_names'][sum(w['sect_earned'].get(sect,0)>=n for n in C.SECT_RULES['ranks'])])])
    for id,s in C.SECTS.items():add('sects','world_sect_join','加入'+s['name'],'免费',s['description'],{'sect':id})
    add('sects','world_sect_leave','退出当前宗门','取消未交委托，贡献分宗保留','旧权限立即失效',confirm='退出宗门会取消尚未交付的委托，已获得贡献保留。')
    for item in ['herb','ore','wood']:add('sects','world_sect_daily','交付'+item_name(item)+'日常',item_name(item)+'3','灵石10、修为4、贡献8、地域声望5',{'item':item})
    for kind,label in [('battle','清剿普通妖兽'),('craft','制造丹药'),('secret','通关秘境')]:add('sects','world_sect_accept','接取委托：'+label,'免费','只计算接取后的行为',{'type':kind})
    section('sects','当前宗门委托',[({'battle':'清剿妖兽','craft':'制造丹药','secret':'秘境勘察'}[w['sect_quest']['type']],'可交付' if w['sect_quest']['done'] else '进行中')] if w['sect_quest'] else [])
    add('sects','world_sect_claim','交付宗门委托','已完成接取后的目标','对应灵石、贡献、修为12及地域声望5')
    for item,cost in [('pill',10),('crystal',20),('skill_coupon',40)]:add('sects','world_sect_redeem','贡献兑换'+item_name(item),'当前宗门贡献%d'%cost,'获得'+item_name(item),{'reward':item})
    section('social','师友与家族',[('师父',C.NPCS[w['master']]['name'] if w['master'] else '未拜师'),('同行',C.NPCS[w['companion']]['name'] if w['companion'] else '无'),('家族',w['family'] or '未建立'),('建设历史',w['family_builds']),('家族声望',w['family_renown'])])
    for npc,n in C.NPCS.items():
        section('social',n['name']+' · NPC',[('好感',w['relations'].get(npc,0)),('好友','已结交' if npc in w['friends'] else '未结交'),('族员','已加入' if npc in w['family_members'] else '未加入')],body=n['dialogue'][2 if npc in w['friends'] else 1 if w['quests'].get(n['quest'])=='claimed' else 0])
        for action,label,cost,effect in [('world_chat','交谈','每3行动一次','好感+1'),('world_gift','赠礼',item_name(n['gift'])+'2','好感+5'),('world_friend','结交','好感30','成为好友，首次修为20'),('world_companion','同行','已结交','每第三战斗回合支援10伤害'),('world_master','拜师','好感10','成为NPC师徒，可请教'),('world_consult','请教','5灵石，每3行动一次','对应技艺熟练5、好感2、修为6'),('world_family_invite','邀请入族','已建家族，好感20','NPC成员加入'),('world_family_remove','请离家族','当前族员','不清空关系')]:add('social',action,label+n['name'],cost,effect,{'npc':npc})
    add('social','world_master_leave','辞别师父','免费','已学技艺保留')
    add('social','world_companion_leave','暂别同行','免费','友谊保留')
    add('social','world_family_create','建立家族','免费','玩家为唯一族长，可邀NPC共建',fields=[text('name','家族名',16)],probe={'name':'青岚家族'})
    for id,definition in C.FAMILIES.items():add('social','world_family_build','建设'+definition['name'],_cost_text(definition['cost']),definition['description']+' 最高3级',{'facility':id})
    add('social','world_family_dissolve','解散家族','不退建设材料，设施加成停止','历史建设保留，新建家族设施归零',confirm='解散后所有NPC族员离开，建设材料不返还，被动加成停止。确认解散？')
    for id,d in C.DISCIPLES.items():
        current=w['disciples'].get(id);section('social',d['name']+' · NPC弟子',[('经验',current['xp'] if current else '尚未收徒'),('派遣',item_name(current['mission']['item'])+'：'+('可领取' if w['tick']>=current['mission']['end'] else '还需%d世界行动'%(current['mission']['end']-w['tick'])) if current and current['mission'] else '无')])
        add('social','world_disciple','收徒：'+d['name'],'元婴后免费','每类最多一位NPC弟子',{'disciple':id})
        add('social','world_teach','授业：'+d['name'],'修为5','弟子经验5+学堂等级，完成传承门槛',{'disciple':id})
        add('social','world_dispatch','派遣：'+d['name'],'免费，3世界行动后归队','按弟子等级取得草/矿/晶',{'disciple':id},[select('destination','目的地',[('herb','药谷：药草'),('ore','矿山：矿石'),('crystal','古迹：灵晶')])],{'destination':d['material']})
        for action,label in [('world_collect_disciple','领取归队'),('world_cancel_dispatch','取消派遣'),('world_disciple_release','解除师徒')]:add('social',action,label+'：'+d['name'],'免费','仅结算一次；解除前须取消派遣',{'disciple':id})
    section('craft','四艺熟练',[(C.ARTS[a],'%d级 · 熟练%d'%(_art_level(w,a),w['arts'][a])) for a in ARTS])
    for id,recipe in C.RECIPES.items():
        array=id.endswith('_array');add('craft','world_craft','制作'+recipe['name'],'每份：'+_cost_text(recipe['cost'])+('；永久阵法按目标级乘成本' if array else ''),'产物：'+_cost_text(recipe['output'])+'；数量1–20，整批原子结算，满背包拒绝',{'recipe':id},[number('quantity','制作数量',1,1 if array else 20)],{'quantity':1})
    for key,label in [('spirit','聚灵阵'),('mountain','护山阵'),('seal','封界阵')]:
        section('craft',label,[('等级',w['arrays'][key]),('状态','启用' if w['arrays_enabled'][key] else '暂停')]);add('craft','world_array_toggle','切换'+label,'免费，不退材料','暂停或恢复派生加成',{'array':key})
    for id,definition in C.HOMES.items():
        section('estate',definition['name'],[('等级',w['home'][id]),('仓库','%d / %d'%(w['home_storage'][id],20*w['home'][id]))],body=definition['description']+' 每3世界行动生产相应材料至独立仓库；升级重设生产起点，不回填历史。')
        add('estate','world_home','升级'+definition['name'],'基础成本×目标级：'+_cost_text(definition['cost']),'最高3级，保留仓库',{'facility':id})
        add('estate','world_home_collect','收取'+definition['name'],'免费','全部转入背包，容量不足完整保留',{'facility':id})
    section('estate','守候生产',body='如需推进待办，可在九州页使用守候进度；查看页面不会生产。')
    section('exploration','当前活动',[('秘境',C.SECRETS[w['exploration']['id']]['name']+' 节点%d'%(w['exploration']['node']+1) if w['exploration'] else '无'),('副本',C.DUNGEONS[w['dungeon']['id']]['name']+' 第%d战'%(w['dungeon']['round']+1) if w['dungeon'] else '无'),('本境劫影','已首胜' if str(w['stage']) in w['guard_wins'] else '尚未首胜')])
    add('exploration','world_hunt','清剿野外妖兽','免费','胜利取得灵石与药草，可完成宗门战斗委托；奖励随当前境界与兽潮变化')
    add('exploration','world_boss','挑战'+stage+'劫影','免费','首胜：灵石%d、灵晶2、修为%d；重复：灵石15、灵晶1、修为%d'%(60+20*w['stage'],20+6*w['stage'],8+2*w['stage']))
    for id,d in C.SECRETS.items():add('exploration','world_secret_enter','进入'+d['name'],'位于'+C.REGIONS[d['region']]['name'],'三节点：勘察→采集/修整→守卫；终节点修为%d，首通灵晶2与声望5'%(18+6*w['stage']),{'secret':id})
    for choice,label in [('survey','勘察秘境'),('gather','秘境采集'),('rest','秘境修整'),('fight','挑战秘境守卫')]:add('exploration','world_secret_step',label,'免费','依当前节点结算，首通标记一次',{'choice':choice})
    add('exploration','world_secret_leave','离开秘境','无额外奖励','保留已经获得的节点材料')
    for id,d in C.DUNGEONS.items():add('exploration','world_dungeon_enter','进入'+d['name'],'位于'+C.REGIONS[d['region']]['name'],'两场妖兽、一场Boss；按入场境界快照，终场修为(24+6×入场境界序号)×难度',{'dungeon':id},[number('difficulty','难度',1,3)],{'difficulty':1})
    add('exploration','world_dungeon_next','继续副本下一战','当前副本进度','开始下一场；战间可以静养或制作')
    add('exploration','world_dungeon_leave','撤离副本','不发未完成通关奖励','保留永久成长')
    if w['encounter']:
        definition=C.EVENTS[w['encounter']['id']];section('exploration','奇遇：'+definition['name'],[('有效期','剩%d世界行动'%(w['encounter']['end']-w['tick']))],definition['description'])
        for id,c in definition['choices'].items():add('exploration','world_encounter',c['name'],_cost_text(c.get('cost',{})),'战斗护送' if c.get('battle') else '结果：'+_cost_text(c.get('reward',{})),{'choice':id})
        add('exploration','world_encounter','放弃当前奇遇','无惩罚','清除本次奇遇',{'choice':'leave'})
    section('market','NPC商会与资产',[('凡界灵石',w['wallet']),('活跃订单',sum(not a['settled'] and not a['cancelled'] for a in w['auctions']))],body='全部为本地NPC模拟。每件单价由服务端决定；数量表单的实际总价按每件×数量原子扣除。卖价不高于同条件买价，无真实货币。')
    for item in ['herb','ore','wood','crystal','pill','fire_talisman']:
        for action,buy,label in [('world_buy',True,'购买'),('world_sell',False,'出售')]:add('market',action,label+item_name(item),'单价%d灵石；数量1–20'%_price(w,item,buy),'库存与钱包同一次结算',{'item':item},[number('quantity','数量',1,20)],{'quantity':1})
    add('market','world_auction_list','寄售至NPC拍卖','托管所选物品；成交抽5%费用','6世界行动到期，无人出价可撤单',fields=[select('item','物品',[(k,item_name(k)) for k in ['herb','ore','wood','crystal','pill']]),number('quantity','数量',1,20),number('price','底价（灵石）',1,1000)],probe={'item':next((k for k in ['herb','ore','wood','crystal','pill'] if count(w,k)>0),'herb'),'quantity':1,'price':8},confirm='寄售将托管物品。有人出价后不能撤单，成交后系统收取5%手续费。')
    ordered=sorted(w['auctions'],key=lambda a:(0 if a['delivery'] else 1 if not a['settled'] and not a['cancelled'] else 2,-int(a['id'])))
    shown_closed=0
    for order in ordered:
        if (order['settled'] or order['cancelled']) and not order['delivery']:
            shown_closed+=1
            if shown_closed>6:continue
        status='已撤单' if order['cancelled'] else '已结算' if order['settled'] else '剩%d行动'%(order['end']-w['tick'])
        section('market','订单'+order['id']+' · '+item_name(order['item']),[('数量',order['quantity']),('卖家','玩家' if order['seller']=='player' else C.NPCS[order['seller']]['name']+'（NPC）'),('领先','无' if order['bidder'] is None else '玩家' if order['bidder']=='player' else C.NPCS[order['bidder']]['name']+'（NPC）'),('价格',order['price'] or order['base']),('状态',status),('待领',_cost_text(order['delivery']) if order['delivery'] else '无')])
        if not order['settled'] and not order['cancelled']:
            if order['seller']!='player':add('market','world_auction_bid','竞拍订单'+order['id'],'出价全额托管，自己加价仅付差额','被超价全额退回，到期一次成交',{'auction':order['id']},[number('price','出价',max(order['base'],order['price']+1),CAP)],{'price':max(order['base'],order['price']+1)},confirm='此次出价将托管灵石；被NPC超价时退款，领先至到期则取得拍品。')
            else:add('market','world_auction_cancel','撤销订单'+order['id'],'仅无人出价可撤','原物返还；容量满则进入待领',{'auction':order['id']})
        if order['delivery']:add('market','world_delivery','领取订单'+order['id']+'资产','需要完整背包/钱包容量','整笔领取一次，容量不足不丢资产',{'auction':order['id']})
    section('quests','当前主线',[(q['name'],('已领奖' if w['quests'].get(id)=='claimed' else '可交付' if w['quests'].get(id)=='active' and _quest_ready(w,q) else '进行中' if w['quests'].get(id)=='active' else '未接取')+'；'+q['description']) for id,q in C.QUESTS.items() if not q.get('npc')])
    for id,q in C.QUESTS.items():
        section('quests',q['name'],[('状态',{'active':'进行中','claimed':'已领取'}.get(w['quests'].get(id),'未接取')),('奖励',_cost_text(q['reward'])+'、修为%d'%(15 if q.get('npc') else 30))],q['description'])
        add('quests','world_quest_accept','接取：'+q['name'],'免费','记录任务状态；历史目标可回溯验证',{'quest':id})
        add('quests','world_quest_claim','交付：'+q['name'],'交付型消耗目标道具，其余检查事实','任务奖励及修为一次领取',{'quest':id})
    for kind,d in C.ACHIEVEMENTS.items():
        section('achievements',d['name'],[('进度',_achievement_count(w,kind))])
        for tier,target in enumerate(d['tiers']):add('achievements','world_achievement',d['name']+' %d次'%target,'达到对应计数','奖励：'+_cost_text(d['rewards'][tier]),{'kind':kind,'tier':tier})
    for title,d in C.TITLES.items():add('achievements','world_title','佩戴'+d['name'],'条件%d'%d['threshold'],'单一槽位：'+{'attack':'攻击','cultivate':'修炼收益','rest_hp':'静养气血恢复'}[d['effect']]+' +%d'%d['amount'],{'title':title})
    scores=[(state['name']+'（玩家）',w['stage']*1000000+w['xp'],w['arena']['points']+w['arena']['regional_points'],sum(w['arts'].values()))]+[(C.NPCS[k]['name']+'（规则NPC）',a['turns']*10,a['turns'],a['turns']*5) for k,a in w['npc_agents'].items()]
    for index,label in [(1,'境界成长（NPC行为经验折算）'),(3,'四艺历练（NPC行为经验折算）')]:section('achievements','本地NPC模拟榜 · '+label,[(str(i+1)+' '+row[0],row[index]) for i,row in enumerate(sorted(scores,key=lambda row:(-row[index],row[0])))],body='单人本地统计；NPC数据由实际行动状态派生，不代表真人或全球榜。')
    season=w['arena']['current']
    season_scores=[(state['name']+'（玩家）',season['round']*10 if season else 0)]+[(v['name'],season['npc_scores'][k] if season else 0) for k,v in C.ARENA_OPPONENTS.items()]
    section('achievements','本地NPC模拟榜 · 跨域本季真实赛果',sorted(season_scores,key=lambda row:(-row[1],row[0])),body='仅计本季实际胜败；未交手NPC为0分，不将生产行为冒充竞技。')
    section('arena','本地NPC模拟演武',[('演武积分',w['arena']['points']),('跨域总分',w['arena']['regional_points']),('NPC成长级',w['arena']['growth'])],body='普通演武按挑战开始tick所属20行动周期，每模板首胜一次奖励；同周期重试只练习。演武丹符与HP/MP从开场快照恢复，赛果奖励留在真实世界。')
    for id,d in C.ARENA_OPPONENTS.items():add('arena','world_arena','演武：'+d['name'],'模拟消耗，无真人匹配','本周期首胜积分10及灵石10；'+d['description'],{'opponent':id,'mode':'local'})
    current=w['arena']['current'];section('arena','三域NPC模拟跨域赛',[('赛季',w['arena']['season']),('晋级进度',str(current['round'])+' / 3' if current else '尚未报名'),('赛季状态','已领取冠军奖励' if current and current['claimed'] else '进行中' if current else '未报名')],body='青岚剑会 → 赤砂武会 → 玄潮丹会；报名锁定对手境界及成长快照，胜一场晋一级，失败可重试。')
    if current:section('arena','本季NPC模拟榜',sorted([(state['name']+'（玩家）',current['round']*10)]+[(C.ARENA_OPPONENTS[k]['name'],v) for k,v in current['npc_scores'].items()],key=lambda row:(-row[1],row[0])))
    add('arena','world_season_join','报名下一季','免费，前一季须已结算','冻结三位NPC对手，本季不随成长抬强')
    add('arena','world_season_fight','挑战当前赛区','模拟战斗，无真实玩家','胜利晋级、积分10与灵石10，每场一次')
    add('arena','world_season_claim','领取本季冠军奖励','本季三胜','灵石30、灵晶3、家族声望5；NPC下季成长一级')
    if w['battle']:
        battle=w['battle'];intent=['攻击%d'%battle['attack'],'蓄势，本回合0伤害','重击%d'%battle['heavy']][battle['turn']%3]
        for page in pages:
            page['actions']=[a for a in page['actions'] if a['id'].startswith('world_')]
        section('exploration','当前战斗：'+battle['name'],[('敌方气血','%d / %d'%(battle['hp'],battle['max_hp'])),('下一意图',intent),('战斗回合',battle['turn']+1)])
        for strategy,label,cost,effect in [('balanced','自动斗法·均衡','按战况自动出招；必要时才用回元丹与三符','自动攻守、回灵与回血；战力型法宝按各自冷却独立出击或回护，直到本战分出结果'),('steady','自动斗法·稳妥','气血≤75%即服丹，符箓提前备用','优先保住气血，愿意多用丹符；战力型法宝同样出手'),('aggressive','自动斗法·强攻','只在气血≤25%时服丹，不用三符','优先输出，防御与符箓不自动使用；战力型法宝同样出手'),('frugal','自动斗法·节制','不消耗任何丹药与符箓','只用普攻、强攻与防御；战力型法宝同样出手')]:add('arena' if battle['kind'] in {'arena','regional'} else 'exploration','world_auto_battle',label,cost,effect,{'strategy':strategy})
        if battle['kind'] in {'arena','regional'}:section('arena','当前演武',[(battle['name'],'气血%d / %d；下一招%s'%(battle['hp'],battle['max_hp'],intent))])
    for page in pages:
        enabled=next((a for a in page['actions'] if a['enabled']),None)
        if enabled:enabled['primary']=True
    resources=[{'id':k,'label':label,'value':v,'max':maximum} for k,label,v,maximum in [('world_hp','凡界气血',w['hp'],attrs['hp']),('world_mp','凡界灵力',w['mp'],attrs['mp']),('world_xp','凡界修为',w['xp'],CAP),('world_stone','凡界灵石',w['wallet'],CAP)]]
    battle_view=None
    if w['battle']:
        b=w['battle'];battle_view={'name':b['name'],'hp':b['hp'],'max_hp':b['max_hp'],'intent':['常规攻击%d'%b['attack'],'蓄势：本回合无伤害','重击%d'%b['heavy']][b['turn']%3],'page':'arena' if b['kind'] in {'arena','regional'} else 'exploration'}
    result={'version':2,'active':w['active'],'battle':battle_view,'stage':stage,'summary':'凡界已封界，修行未止。' if w['ending'] else _advance_reason(w) or '突破条件已齐。','resources':resources,'pages':pages}
    if 'r3' in w:loot.project(state,result,context=context)
    return result


def validate(state):
    """Malformed nested JSON always has one storage-facing failure type."""
    try:
        _validate_state(state)
    except (KeyError,TypeError,AttributeError,IndexError) as exc:
        raise ValueError('世界嵌套存档结构无效') from exc
