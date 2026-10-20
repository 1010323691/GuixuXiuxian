"""UTC daily/weekly projects: pure progress observations and atomic reward rights."""
import datetime as dt
from . import r3_config as R
from . import gameplay_config as G

KINDS={'gather','craft','use','secret','dungeon','boss','commission','social'}
ENTRY_FIELDS={'kind','period','project','name','objectives','reward','completed','claimed','receipt','config_version'}


def initial_state():return {'version':1,'entries':{}}
initial=initial_state


def _fail(message,code='ACTION_UNAVAILABLE',status=422):
    from .rules import GameError
    raise GameError(code,message,status)


def _periods(context):
    try:
        day=dt.date.fromisoformat(context['day'])
        if day.isoformat()!=context['day']:raise ValueError()
    except (KeyError,TypeError,ValueError):
        _fail('活动需要服务端UTC周期上下文。','BAD_REQUEST',400)
    year,week,_=day.isocalendar()
    return day,day.isoformat(),'%04d-W%02d'%(year,week)


def _weekly(day):
    catalog=G.WEEKLY_ACTIVITIES
    return catalog[((day-dt.date(1970,1,5)).days//7)%len(catalog)]


def _entry(kind,period,project,definition):
    return dict(kind=kind,period=period,project=project,name=definition['name'],
        objectives=[dict(kind=o['kind'],target=o['target'],amount=o['amount'],label=o['label'],progress=0) for o in definition['objectives']],
        reward=dict(definition['reward']),completed=False,claimed=False,receipt=None,config_version=R.CONTENT_VERSION)


def handle(w,action,p,events,context):
    if action not in {'world_activity_accept','world_activity_week_accept','world_activity_claim'}:return False
    day,date,week=_periods(context);a=w['r3']['activities'];entries=a['entries']
    if action=='world_activity_accept':
        project=p['project']
        if not isinstance(project,str) or project not in G.DAILY_PROJECTS:_fail('请选择有效日常项目。','BAD_REQUEST',400)
        key='d:'+date
        if key in entries:_fail('本UTC日已选择日常项目，不可换项重置。')
        entries[key]=_entry('daily',date,project,G.DAILY_PROJECTS[project])
        events.append('已接取日常项目：'+entries[key]['name']+'；从本次接取之后记录双目标。')
    elif action=='world_activity_week_accept':
        key='w:'+week
        if key in entries:_fail('本UTC周已接取主题活动。')
        definition=_weekly(day);entries[key]=_entry('weekly',week,definition['id'],definition)
        events.append('已接取本周活动：'+definition['name']+'；不追溯接取前行为。')
    else:
        key=p['key'];entry=entries.get(key) if isinstance(key,str) else None
        if entry is None:_fail('没有此活动记录。')
        if entry['claimed']:_fail('此活动权益已经领取。')
        if not entry['completed']:_fail('请先完成活动全部目标。')
        from .loot import _grant_materials
        receipt='activity:'+w['r3']['profile_id']+':'+key
        _grant_materials(w,entry['reward'],receipt)
        entry['claimed']=True;entry['receipt']=receipt
        events.append('活动奖励已完整入库或待领：'+entry['name']+'；不增加修为或额外副本资格。')
    return True


def _events(before,after,action,params):
    br,ar=before['r3'],after['r3'];counts={}
    if action=='world_gather':counts[('gather',params['item'])]=1
    for kind,key in [('craft','crafted'),('use','used')]:
        for art,n in ar[key].items():counts[(kind,art)]=max(0,n-br[key].get(art,0))
    counts[('use','any')]=sum(n for (kind,target),n in counts.items() if kind=='use')
    counts[('craft','any')]=sum(n for (kind,target),n in counts.items() if kind=='craft')
    counts[('social','any')]=int(action in {'world_chat','world_gift','world_consult'})
    counts[('secret','any')]=max(0,ar['secret_count']-br['secret_count'])
    counts[('commission','any')]=max(0,ar['daily_count']-br['daily_count'])
    counts[('dungeon','any')]=sum(run['completed'] and not br['runs'].get(key,{}).get('completed',False) for key,run in ar['runs'].items())
    boss=0
    for period,record in ar['boss'].items():
        old=br['boss'].get(period,{}).get('runs',{})
        boss+=sum(run['settled'] and run['commands']>=1 and not old.get(key,{}).get('settled',False) for key,run in record['runs'].items())
    counts[('boss','any')]=boss
    return counts


def observe(before,after,action,params,context):
    if 'r3' not in after or not after['active']:return
    _,date,week=_periods(context)
    counts=_events(before,after,action,params)
    old_entries=before['r3']['activities']['entries']
    for key,entry in after['r3']['activities']['entries'].items():
        if key not in old_entries or entry['completed'] or entry['claimed']:continue
        if entry['period']!=(date if entry['kind']=='daily' else week):continue
        for objective in entry['objectives']:
            objective['progress']=min(objective['amount'],objective['progress']+counts.get((objective['kind'],objective['target']),0))
        entry['completed']=all(o['progress']>=o['amount'] for o in entry['objectives'])


def _reward_text(reward):
    from .loot import material_name
    return '、'.join('%s%d'%(material_name(k),n) for k,n in reward.items())


def project(state,context):
    w=state['world'];day,date,week=_periods(context)
    entries=w['r3']['activities']['entries'];sections=[];actions=[]
    def section(id,title,body,rows):sections.append(dict(id=id,title=title,body=body,rows=[{'label':k,'value':str(v)} for k,v in rows]))
    def action(id,label,params,reason='',effect=''):
        if not w['active']:reason='请先完成序章并入世。'
        if w['battle']:reason='请先结束当前战斗。'
        actions.append(dict(id=id,label=label,params=params,detail=effect,cost='免费',effect=effect,enabled=not reason,reason=reason,primary=False,group='quests'))
    section('r3_daily','UTC日常项目 · 三选一','接取后完成两个目标；跨日未完成可接新期，已完成权益不过期。', [('周期',date),('奖励','宝尘1、强化材2；0直接修为')])
    for id,definition in G.DAILY_PROJECTS.items():
        action('world_activity_accept','日常项目：'+definition['name'],{'project':id},'本UTC日已选择项目。' if 'd:'+date in entries else '',definition.get('description','')+'；奖励'+_reward_text(definition['reward']))
    weekly=_weekly(day)
    section('r3_weekly','UTC周常活动 · '+weekly['name'],'每周一个轮换主题，接取后计数，完成权益可跨周领取。',[('周期',week),('奖励',_reward_text(weekly['reward']))])
    action('world_activity_week_accept','周常活动：'+weekly['name'],{},'本UTC周已接取活动。' if 'w:'+week in entries else '',weekly.get('description',''))
    for key,entry in entries.items():
        current=entry['period']==(date if entry['kind']=='daily' else week)
        if not current and (entry['claimed'] or not entry['completed']):continue
        status='已领取' if entry['claimed'] else '已完成待领取' if entry['completed'] else '进行中'
        rows=[('周期',entry['period']),('状态',status),('奖励',_reward_text(entry['reward']))]
        rows += [(o['label'],'%d / %d'%(o['progress'],o['amount'])) for o in entry['objectives']]
        section('r3_activity:'+key,entry['name'], '只记录接取后成功行为；不消耗额外成长额度。',rows)
        action('world_activity_claim',('日常' if entry['kind']=='daily' else '周常')+'领奖：'+entry['name'],{'key':key},'已经领取。' if entry['claimed'] else '' if entry['completed'] else '尚未完成全部目标。',_reward_text(entry['reward']))
    return dict(sections=sections,actions=actions)


def _validate(state):
    w=state.get('world',{})
    if 'r3' not in w:return
    a=w['r3']['activities']
    def bad():raise ValueError('活动周期、进度或奖励账本无效')
    if not isinstance(a,dict) or set(a)!={'version','entries'} or type(a['version']) is not int or a['version']!=1 or not isinstance(a['entries'],dict):bad()
    for key,entry in a['entries'].items():
        if not isinstance(key,str) or not isinstance(entry,dict) or set(entry)!=ENTRY_FIELDS:bad()
        if entry['kind'] not in {'daily','weekly'} or not isinstance(entry['period'],str):bad()
        if key!=('d:' if entry['kind']=='daily' else 'w:')+entry['period']:bad()
        try:
            if entry['kind']=='daily':
                parsed=dt.date.fromisoformat(entry['period'])
                if parsed.isoformat()!=entry['period']:bad()
                definition=G.DAILY_PROJECTS[entry['project']]
            else:
                parsed=dt.date.fromisocalendar(int(entry['period'][:4]),int(entry['period'][6:]),1)
                if '%04d-W%02d'%parsed.isocalendar()[:2]!=entry['period']:bad()
                definition=_weekly(parsed)
                if definition['id']!=entry['project']:bad()
        except (KeyError,ValueError,TypeError,StopIteration):bad()
        if not isinstance(entry['reward'],dict) or any(type(n) is not int or n<0 for n in entry['reward'].values()):bad()
        if entry['name']!=definition['name'] or entry['reward']!=definition['reward'] or type(entry['config_version']) is not int or entry['config_version']!=R.CONTENT_VERSION:bad()
        if any(type(entry[k]) is not bool for k in ('completed','claimed')):bad()
        if not isinstance(entry['objectives'],list) or len(entry['objectives'])!=len(definition['objectives']):bad()
        for objective,expected in zip(entry['objectives'],definition['objectives']):
            if not isinstance(objective,dict) or set(objective)!={'kind','target','amount','label','progress'}:bad()
            if any(objective[k]!=expected[k] for k in ('kind','target','amount','label')):bad()
            if type(objective['amount']) is not int:bad()
            if type(objective['progress']) is not int or not 0<=objective['progress']<=objective['amount']:bad()
        if entry['completed']!=all(o['progress']==o['amount'] for o in entry['objectives']):bad()
        if entry['claimed'] and not entry['completed']:bad()
        expected_receipt='activity:'+w['r3']['profile_id']+':'+key if entry['claimed'] else None
        if entry['receipt']!=expected_receipt:bad()


def validate(state):
    try:_validate(state)
    except (KeyError,TypeError,AttributeError,IndexError) as exc:
        raise ValueError("活动嵌套存档结构无效") from exc
