"""Exact, side-effect-free continuous cultivation for longline profiles.

The current state is authoritative; a manual checkpoint never rewinds this account.
Time is supplied by Store, never accepted from an HTTP payload.
"""
import math
from fractions import Fraction
from .clone import clone

MICRO = 1_000_000
DENOMINATOR = 86400 * 10 * 10000
COEFFICIENTS = (10, 15, 22, 32, 45, 65, 90, 120)
FIELDS = {'version', 'last_settled', 'balance_micro', 'remainder', 'total_micro', 'rate_num'}
R4_FIELDS = FIELDS | {'curve_version', 'remainder_denominator','migrated_from'}


def is_longline(state):
    return isinstance(state,dict) and isinstance(state.get('world'),dict) and isinstance(state['world'].get('r3'),dict)


def initial(now=None):
    return dict(version=1, curve_version=2, migrated_from=None,remainder_denominator=DENOMINATOR,
                last_settled=now, balance_micro=0, remainder=0, total_micro=0, rate_num=0)


def curve_version(state):
    if not is_longline(state):return None
    return (state['world']['r3'].get('growth') or {}).get('curve_version',1)


def _denominator(account):return account.get('remainder_denominator',DENOMINATOR)


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def validate(state, check_balance=False):
    if not is_longline(state):
        return
    g = state['world']['r3'].get('growth')
    # Pure domain constructors may defer the clock until storage first handles them.
    if g is None:
        if check_balance:
            raise ValueError('持久化长线档缺少修炼账本')
        return
    if not isinstance(g, dict) or set(g) not in (FIELDS,R4_FIELDS):
        raise ValueError('持续修炼字段无效')
    if set(g)==R4_FIELDS and (type(g['curve_version']) is not int or g['curve_version']!=2 or not _integer(g['remainder_denominator'],DENOMINATOR) or g['remainder_denominator']%DENOMINATOR or g['remainder_denominator']//DENOMINATOR>51840):
        raise ValueError('成长曲线版本或精确积分分母无效')
    if set(g)==R4_FIELDS and g['migrated_from'] is not None and (type(g['migrated_from']) is not int or g['migrated_from']!=1):
        raise ValueError('成长曲线迁移标记无效')
    if type(g['version']) is not int or g['version'] != 1:
        raise ValueError('持续修炼版本无效')
    if g['last_settled'] is not None and not _integer(g['last_settled']):
        raise ValueError('修炼结算时刻无效')
    if any(not _integer(g[k]) for k in ('balance_micro', 'remainder', 'total_micro', 'rate_num')):
        raise ValueError('修炼账本数值无效')
    if g['remainder'] >= _denominator(g) or check_balance and g['balance_micro'] // MICRO != state['world']['xp']:
        raise ValueError('修炼余额或积分余数不一致')
    if check_balance and state['world']['active'] and g['last_settled'] is None:
        raise ValueError('已入世角色缺少修炼时间水位')
    if check_balance and g['rate_num'] != rate_num(state):
        raise ValueError('存档修炼速率与当前境界装备不一致')


def rate_num(state):
    if not state['world']['active']:
        return 0
    from . import loot
    bonus = loot.growth_bonus_bps(state)
    if not _integer(bonus) or bonus > 1500:
        raise ValueError('修炼加成超出约定')
    return 540 * MICRO * COEFFICIENTS[state['world']['stage']] * (10000 + bonus)


def sync(state, now):
    """Copy and integrate the persisted OLD rate; never advance world.tick."""
    if not _integer(now):
        raise ValueError('服务端UTC时钟无效')
    s = clone(state)
    if not is_longline(s):
        return s
    w = s['world']
    if w['r3'].get('growth') is None:
        w['r3']['growth'] = initial()
        w['r3']['growth']['balance_micro'] = w['xp'] * MICRO
    g = w['r3']['growth']
    if not w['active']:
        return s
    if g['last_settled'] is None:
        g['last_settled'] = now
        g['rate_num'] = rate_num(s)
        return s
    effective_now = max(now, g['last_settled'])
    denominator=_denominator(g)
    earned, remainder = divmod((effective_now - g['last_settled']) * g['rate_num'] * (denominator//DENOMINATOR) + g['remainder'], denominator)
    g['balance_micro'] += earned
    g['total_micro'] += earned
    g['remainder'] = remainder
    g['last_settled'] = effective_now
    w['xp'] = g['balance_micro'] // MICRO
    return s


def upgrade_legacy(state,now):
    """Settle the old segment, then preserve exact current-stage progress ratio.

    total_micro is historical production and is deliberately not fabricated by
    the representation change. Unsealed unspent balances are rescaled;
    sealed reserves keep their actual amount after old-rate settlement.
    """
    if not is_longline(state) or curve_version(state)==2:return clone(state)
    from . import r3_config as R
    result=sync(state,now);w=result['world'];g=w['r3']['growth']
    if curve_version(result)==2:return result
    old_den=_denominator(g)
    # A sealed realm has no remaining advancement price: its actual reserve
    # stays unchanged. Unsealed progress, including overflow, is rescaled.
    ratio=Fraction(1) if w['ending'] else Fraction(R.CURVES[2]['costs'][w['stage']],R.CURVES[1]['costs'][w['stage']])
    amount=Fraction(g['balance_micro']*old_den+g['remainder'],old_den)*ratio
    denominator=math.lcm(DENOMINATOR,amount.denominator)
    numerator=amount.numerator*(denominator//amount.denominator)
    g['balance_micro'],g['remainder']=divmod(numerator,denominator)
    g['remainder_denominator']=denominator;g['curve_version']=2;g['migrated_from']=1
    w['xp']=g['balance_micro']//MICRO
    validate(result,check_balance=True)
    return result


def finish(before, after, now):
    """Reconcile legitimate integer XP spending, then begin the new rate segment."""
    s = clone(after)
    if not is_longline(s):
        return s
    if s['world']['r3'].get('growth') is None:
        s['world']['r3']['growth'] = initial()
    g = s['world']['r3']['growth']
    old_xp = before['world']['xp'] if is_longline(before) else 0
    change = s['world']['xp'] - old_xp
    if before and before['world']['active'] and change > 0:
        raise ValueError('长线行动不得绕过持续成长直接增加修为')
    g['balance_micro'] += change * MICRO
    if g['balance_micro'] < 0:
        raise ValueError('修炼支出超过权威余额')
    if s['world']['active'] and g['last_settled'] is None:
        g['last_settled'] = now
    g['rate_num'] = rate_num(s)
    validate(s,check_balance=True)
    return s


def preview(state, now):
    projected = sync(state, now)
    if not is_longline(projected):
        return projected, None
    g = projected['world']['r3']['growth']
    old = state['world']['r3'].get('growth') or initial()
    per_second = g['rate_num'] / DENOMINATOR / MICRO
    return projected, dict(active=projected['world']['active'],
        curve_version=curve_version(projected),
        migrated_from=g.get('migrated_from'),
        settled=old['balance_micro'] / MICRO, available=g['balance_micro'] / MICRO,
        settled_micro=str(old['balance_micro']), available_micro=str(g['balance_micro']),
        last_settled=old['last_settled'], server_now=max(now,g['last_settled'] or now),
        clock_rewound=g['last_settled'] is not None and now<g['last_settled'],
        offline_gain=(g['balance_micro']-old['balance_micro']) / MICRO,
        rate=dict(per_day=per_second*86400, per_hour=per_second*3600,
                  numerator=str(g['rate_num']), denominator=DENOMINATOR))


def load_checkpoint(current, slot):
    """Longline restores safe position only; all progression/ownership stays current."""
    from .rules import GameError
    if not is_longline(current):
        if is_longline(slot):
            raise GameError('INCOMPATIBLE_SAVE', '检查点模式不属于当前角色。')
        return clone(slot), ['已载入手动检查点。']
    if not is_longline(slot) or current['world']['r3']['profile_id'] != slot['world']['r3']['profile_id']:
        raise GameError('INCOMPATIBLE_SAVE', '检查点不属于当前长线角色。')
    if not current['world']['active']:
        if slot['world']['active']:
            raise GameError('INCOMPATIBLE_SAVE', '检查点入世状态不兼容。')
        return clone(slot), ['已恢复序章检查点；尚未开始凡界持续修炼。']
    if not slot['world']['active']:
        raise GameError('INCOMPATIBLE_SAVE', '已入世角色不能退回序章；成长与资产保留。')
    s = clone(current)
    if any(s['world'][key] is not None for key in ('battle', 'exploration', 'dungeon')):
        return s, ['当前正在战斗或探索，保留当前位置与完整进度；修为、境界花费、资产及奖励资格均未回退。']
    # Only position is a checkpoint; no quest reward or battle cursor is restored.
    s['world']['region'] = slot['world']['region']
    return s, ['已恢复安全位置；保留当前剧情、战斗进度、修为、境界花费、资产、世界时间与奖励资格。']
