#!/usr/bin/env python3
"""R3 independent planning-only integrator; no game imports, writes, or API use.

Continuous XP only. Loot affects rate after an explicitly modeled acquisition
and equip event. Hypothetical loot dates are not measured drop availability.
"""
from fractions import Fraction as F
from pathlib import Path
import csv
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[1]
DAY = 86400
FACTORS = [F(1), F('1.5'), F('2.2'), F('3.2'), F('4.5'), F('6.5'), F(9), F(12)]
TARGET_DAYS = [3, 4, 5, 5, 6, 7, 7, 8]
NAMES = ['筑基', '结丹', '元婴', '化神', '炼虚', '合体', '大乘', '渡劫圆满']
COSTS = [F(540) * factor * days for factor, days in zip(FACTORS, TARGET_DAYS)]
assert COSTS == list(map(F, [1620, 3240, 5940, 8640, 14580, 24570, 34020, 51840]))
assert sum(COSTS) == 144450


def number(value):
    return int(value) if value.denominator == 1 else round(float(value), 9)


def simulate(name, gear_schedule=(), period=1, skip_days=(), policy='scheduled',
             utc_start_offset=0, uncapped_error=False):
    """Manual non-XP gates assumed ready; no offline automatic promotion.

    asap_manual adds explicit manual logins at exact XP readiness; scheduled
    acts at planned 24/48/72h logins; late_cycle delays each ready stage once.
    """
    stage, xp, total, spent, now = 0, F(0), F(0), F(0), F(0)
    gear, other, day_index, schedule_index, logins = F(0), F(0), 0, 0, 0
    skipped, pending, checkpoints, timeline = set(skip_days), {}, [], []
    schedule = sorted((F(str(day)), F(str(g)), F(str(o))) for day, g, o in gear_schedule)

    def bonus():
        return (gear + other) / 100 if uncapped_error else min(F(15), gear + other) / 100

    def rate():
        return F(540) * FACTORS[stage] * (1 + bonus()) / DAY

    def advance():
        nonlocal stage, xp, spent
        while stage < 8 and xp >= COSTS[stage]:
            if policy == 'late_cycle':
                if stage not in pending:
                    pending[stage] = now
                    return
                if now <= pending[stage]:
                    return
            cost = COSTS[stage]
            xp -= cost
            spent += cost
            checkpoints.append({'stage': stage, 'name': NAMES[stage], 'cost': int(cost),
                                'exact_seconds': str(now), 'seconds': number(now),
                                'elapsed_days': number(now / DAY), 'remaining_xp': number(xp),
                                'total_credited': number(total), 'bonus_percent': number(bonus() * 100)})
            stage += 1

    while stage < 8:
        while day_index in skipped:
            day_index += period
        planned = F(day_index * DAY)
        is_ready_login = False
        if policy == 'asap_manual':
            ready = now + max(F(0), (COSTS[stage] - xp) / rate())
            if ready < planned:
                target, is_ready_login = ready, True
            else:
                target = planned
        else:
            target = planned
        increment = (target - now) * rate()
        assert increment >= 0
        xp += increment
        total += increment
        now = target
        logins += 1
        # Settle old interval before rate-changing gear or realm operations.
        advance()
        if stage == 8:
            break
        while schedule_index < len(schedule) and schedule[schedule_index][0] * DAY <= now:
            _, gear, other = schedule[schedule_index]
            assert uncapped_error or (0 <= gear <= 10 and 0 <= other <= 5)
            schedule_index += 1
        timeline.append({'exact_seconds': str(now), 'stage': stage, 'xp': number(xp),
                         'gear_percent': number(gear), 'other_percent': number(other),
                         'total_bonus_percent': number(bonus() * 100), 'credited': number(total),
                         'manual_extra_login': is_ready_login})
        if not is_ready_login:
            day_index += period
        assert day_index < 2000
    assert total == spent + xp
    return {'scenario': name, 'policy': policy, 'login_every_days': period,
            'skip_days': sorted(skipped), 'gear_schedule': [[str(a), str(b), str(c)] for a,b,c in schedule],
            'utc_start_offset_seconds': utc_start_offset, 'direct_activity_xp': 0,
            'completion_days': number(now / DAY), 'completion_hours': number(now / 3600),
            'exact_completion_seconds': str(now), 'manual_logins': logins,
            'total_credited': number(total), 'spent_xp': int(spent), 'remaining_xp': number(xp),
            'checkpoints': checkpoints, 'timeline': timeline,
            'assumptions': 'Non-XP gates ready; fixed hypothetical loot eligibility dates equip only at real modeled login. No loot RNG or combat/content time measured.'}


def main():
    specs = [
        ('no_treasure_no_other_bonus', {}),
        ('single_training_treasure_progressive', {'gear_schedule': [(3,1,0),(10,3,0),(20,4,0)]}),
        ('dual_training_treasures_progressive', {'gear_schedule': [(3,2,0),(10,6,0),(20,8,0)]}),
        ('single_training_plus_other_progressive', {'gear_schedule': [(3,1,0),(10,3,2),(20,4,5)]}),
        ('dual_training_plus_other_progressive', {'gear_schedule': [(3,2,0),(10,6,2),(20,8,5)]}),
        ('late_single_treasure', {'gear_schedule': [(20,1,0),(30,3,0)]}),
        ('extreme_day0_full15', {'gear_schedule': [(0,10,5)]}),
        ('day20_only_full15', {'gear_schedule': [(20,10,5)]}),
        ('strict_48h_no_treasure', {'period': 2}),
        ('strict_48h_dual_progressive', {'period':2,'gear_schedule':[(3,2,0),(10,6,2),(20,8,5)]}),
        ('strict_72h_no_treasure', {'period':3}),
        ('miss_seven_logins_no_treasure', {'skip_days':range(1,8)}),
        ('miss_thirty_logins_no_treasure', {'skip_days':range(1,31)}),
        ('extreme15_utc2350', {'gear_schedule':[(0,10,5)],'utc_start_offset':DAY-600}),
        ('error_twenty_drops_stack100percent', {'gear_schedule':[(0,100,0)],'uncapped_error':True}),
    ]
    results=[]
    for name, options in specs:
        for policy in ['asap_manual','scheduled','late_cycle']:
            if policy=='asap_manual' and (options.get('period',1)!=1 or options.get('skip_days')):
                continue  # Absence cannot contain secret extra manual logins.
            results.append(simulate(name,policy=policy,**options))
    assert next(r for r in results if r['scenario']=='no_treasure_no_other_bonus' and r['policy']=='asap_manual')['completion_days']==45
    assert next(r for r in results if r['scenario']=='extreme_day0_full15' and r['policy']=='asap_manual')['exact_completion_seconds']==str(F(45*DAY)/F('1.15'))
    plain_utc=next(r for r in results if r['scenario']=='extreme_day0_full15' and r['policy']=='scheduled')
    shifted=next(r for r in results if r['scenario']=='extreme15_utc2350' and r['policy']=='scheduled')
    assert plain_utc['exact_completion_seconds']==shifted['exact_completion_seconds']
    split=sum((F(s)*F(621,DAY) for s in [1,17,3600,82782]),F(0));assert split==621
    slot_xp,seen,total=100,700,1000
    assert slot_xp+(total-seen)==400 and slot_xp+(1100-seen)==500
    payload={'version':'R3_CONTINUOUS_XP_LOOT_RATE_ONLY','status':'planning_only_not_implemented',
             'costs':list(map(int,COSTS)),'total_cost':int(sum(COSTS)),
             'base_per_day':540,'factors':list(map(str,FACTORS)),'base_target_days':TARGET_DAYS,
             'activity_direct_xp':0,'treasure_slots':2,'per_slot_training_percent_cap':5,
             'other_bonus_percent_cap':5,'additive_total_percent_cap':15,
             'scenarios':results,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'never_logs_in':[{'days':d,'stage':0,'xp':540*d,'ending':False} for d in [1,3,30,120,2000]],
             'math_contract_checks':{'segmented_day_540_then810_halfdays':675,'wrong_retroactive_high_realm':810,
                 'segmented_bonus_halfday0_halfday15':580.5,'wrong_retroactive_whole_day15':621,
                 'split_86400_seconds_plus15_xp':number(split),'same_slot_same_ledger_repeat_load_xp':400,
                 'same_slot_later_ledger1100_xp':500,'load_is_not_new_credit':True},
             'scope':'Exact rational-second numeric model. Non-XP gates and hypothesized loot timing not actual-game verified; no game source/save/tests modified.'}
    output=ROOT/'artifacts/balance';output.mkdir(parents=True,exist_ok=True)
    (output/'qa-month-r3-model.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    columns=['scenario','policy','login_every_days','completion_days','completion_hours','manual_logins','total_credited','spent_xp','remaining_xp']
    with (output/'qa-month-r3-scenarios.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows({k:r[k] for k in columns} for r in results)
    columns=['scenario','policy','stage','name','cost','elapsed_days','exact_seconds','remaining_xp','bonus_percent']
    with (output/'qa-month-r3-stages.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader()
        for r in results:
            for c in r['checkpoints']:w.writerow({k:r[k] if k in {'scenario','policy'} else c[k] for k in columns})
    print(json.dumps([{'scenario':r['scenario'],'policy':r['policy'],'days':r['completion_days']} for r in results],ensure_ascii=False,indent=2))


if __name__=='__main__':main()
