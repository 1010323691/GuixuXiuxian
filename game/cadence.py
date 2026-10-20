"""Recoverable dungeon reward credits; no real clock or filesystem access.

Reservations occupy capacity until a run succeeds. Failed/abandoned runs release
that exact reservation. The current-state ledger is never restored from a slot.
"""
import datetime as dt
from .clone import clone

CAPACITY = 3
INTERVAL = 8 * 3600
FIELDS = {'version','available','last_recovered','banked_seconds','reservations'}


def initial_state(now=None):
    return dict(version=1,available=CAPACITY,last_recovered=now,banked_seconds=0,reservations={})


def _long(state):
    return isinstance(state,dict) and isinstance(state.get('world'),dict) and isinstance(state['world'].get('r3'),dict)


def _int(value,minimum=0,maximum=None):
    return type(value) is int and value>=minimum and (maximum is None or value<=maximum)


def _reserved(account):return sum(value=='reserved' for value in account['reservations'].values())


def _now(w,context):
    value=(context or {}).get('now')
    if value is None:value=w['r3']['cadence']['last_recovered']
    if value is None:value=0
    if not _int(value):raise ValueError('挑战资格时钟无效')
    return value


def _sync(w,now):
    account=w['r3']['cadence']
    if not w['active']:return
    if account['last_recovered'] is None:
        account['last_recovered']=now
        return
    now=max(now,account['last_recovered'])
    occupied=account['available']+_reserved(account)
    if occupied>=CAPACITY:
        account['banked_seconds']=0
    else:
        elapsed=account['banked_seconds']+now-account['last_recovered']
        recovered,remaining=divmod(elapsed,INTERVAL)
        account['available']+=min(recovered,CAPACITY-occupied)
        account['banked_seconds']=0 if account['available']+_reserved(account)==CAPACITY else remaining
    account['last_recovered']=now


def sync(state,now):
    if not _int(now):raise ValueError('挑战资格时钟无效')
    result=clone(state)
    if _long(result) and 'cadence' in result['world']['r3']:
        _sync(result['world'],now)
    return result


def reserve(w,run_id,context):
    """Reserve once; a practice run receives no reusable ledger entry."""
    if 'cadence' not in w['r3']:raise ValueError('挑战资格尚未升级')
    if not isinstance(run_id,str) or not run_id:raise ValueError('挑战预约编号无效')
    _sync(w,_now(w,context))
    a=w['r3']['cadence'];old=a['reservations'].get(run_id)
    if old is not None:return old=='reserved'
    if a['available']==0:return False
    a['available']-=1;a['reservations'][run_id]='reserved'
    return True


def finish(w,run_id,success,context=None):
    if type(success) is not bool:raise ValueError('挑战结算类型无效')
    if 'cadence' not in w['r3']:raise ValueError('挑战资格尚未升级')
    _sync(w,_now(w,context));a=w['r3']['cadence']
    if a['reservations'].get(run_id)!='reserved':return False
    a['reservations'][run_id]='spent' if success else 'released'
    if not success:a['available']+=1
    if a['available']+_reserved(a)==CAPACITY:a['banked_seconds']=0
    return True


def migrate_legacy(state,now):
    result=clone(state)
    if not _long(result) or 'cadence' in result['world']['r3']:return result
    w=result['world'];r=w['r3'];g=r.get('growth') or {}
    now=max(now,g.get('last_settled') or now)
    date=dt.datetime.fromtimestamp(now,dt.timezone.utc).date().isoformat()
    used=min(CAPACITY,r['daily'].get(date,0))
    a=initial_state(now if w['active'] else None);a['available']=CAPACITY-used
    dungeon=w.get('dungeon')
    if dungeon and dungeon.get('run_id') in r['runs']:
        key=dungeon['run_id'];run=r['runs'][key]
        if run['eligible'] and not run['completed'] and r['daily'].get(run['day'],0)<CAPACITY:
            if a['available']==0:
                # The old in-flight entitlement is preserved, not added on top.
                a['available']=1
            a['available']-=1;a['reservations'][key]='reserved'
    r['cadence']=a
    return result


def project(state,context):
    now=context['now'];projected=sync(state,now)
    a=projected['world']['r3']['cadence'];raw=state['world']['r3']['cadence']
    reserved=_reserved(a);full=a['available']+reserved>=CAPACITY
    effective=max(now,a['last_recovered'] or now)
    wait=None if full or not projected['world']['active'] else INTERVAL-a['banked_seconds']
    return dict(available=a['available'],capacity=CAPACITY,reserved=reserved,
        server_now=effective,next_at=None if wait is None else effective+wait,
        seconds_until_next=wait,interval_seconds=INTERVAL,
        clock_rewound=raw['last_recovered'] is not None and context.get('raw_now',now)<raw['last_recovered'],
        status='未入世，初始资格保留。' if not projected['world']['active'] else '额度已满（含进行中预约），满额期间不累计回复时间。' if full else '每8小时回复1次，达到3次后停止累计。')


def validate(state,check_clock=False):
    if not _long(state) or 'cadence' not in state['world']['r3']:return
    w=state['world'];a=w['r3']['cadence']
    if not isinstance(a,dict) or set(a)!=FIELDS or type(a['version']) is not int or a['version']!=1:raise ValueError('挑战资格字段无效')
    if not _int(a['available'],0,CAPACITY) or not _int(a['banked_seconds'],0,INTERVAL-1):raise ValueError('挑战额度或回复余时无效')
    if a['last_recovered'] is not None and not _int(a['last_recovered']):raise ValueError('挑战回复水位无效')
    if not isinstance(a['reservations'],dict):raise ValueError('挑战预约账本无效')
    reserved=[]
    for key,value in a['reservations'].items():
        if not isinstance(key,str) or not key or len(key)>300 or not isinstance(value,str) or value not in {'reserved','spent','released'}:raise ValueError('挑战预约记录无效')
        run=w['r3']['runs'].get(key)
        if not run or not run['eligible']:raise ValueError('预约没有对应正式副本')
        if value=='reserved':
            if run['completed'] or not w.get('dungeon') or w['dungeon'].get('run_id')!=key:raise ValueError('进行中预约与副本不一致')
            reserved.append(key)
        if value=='spent' and not run['completed']:raise ValueError('消耗预约缺少完成副本')
        if value=='released' and (run['completed'] or w.get('dungeon') and w['dungeon'].get('run_id')==key):raise ValueError('已归还预约不能继续进行或再次结算')
    if len(reserved)>1 or a['available']+len(reserved)>CAPACITY:raise ValueError('挑战额度超出上限')
    if w.get('dungeon'):
        key=w['dungeon'].get('run_id');run=w['r3']['runs'].get(key)
        if run and run['eligible'] and not run['completed'] and a['reservations'].get(key)!='reserved':
            raise ValueError('正式进行中副本缺少有效预约')
    if a['available']+len(reserved)==CAPACITY and a['banked_seconds']!=0:raise ValueError('满额不能囤积隐藏回复时间')
    if check_clock and w['active'] and a['last_recovered'] is None:raise ValueError('已入世档缺少资格时间水位')
