#!/usr/bin/env python3
"""Independent planning-only time integrator. Does not import or mutate game code.

Run from any cwd: python scripts/simulate_month_growth.py
All times integrate with Fraction seconds; manual advancement and UTC activity
claims are separate events. This is not gameplay, a migration, or a live clock.
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
STAGE_DAYS = [3, 4, 4, 5, 5, 6, 6, 6]
NAMES = ['筑基', '结丹', '元婴', '化神', '炼虚', '合体', '大乘', '渡劫圆满']
# Independently derive literal costs, never call a designer's result function.
COSTS = [F(900) * factor * days for factor, days in zip(FACTORS, STAGE_DAYS)]
assert COSTS == list(map(F, [2700, 5400, 7920, 14400, 20250, 35100, 48600, 64800]))
assert sum(COSTS) == 199170


def num(value):
    return int(value) if value.denominator == 1 else round(float(value), 9)


def simulate(name, participation=F(1), base_bonus=F(0), extra=F(0), period=1,
             skip_days=(), policy='login_before', all_reward_bonus=False, utc_start_offset=0):
    """Non-XP gates assumed prepared: numerical lower-bound, not game completion.

    asap_manual: adds explicit player logins at exact XP readiness, not offline
    auto-advancement. login_before: scheduled login, settle->advance->each claim.
    login_after: scheduled login, all claims at old stage before advancement.
    late_cycle: player notices eligibility but advances next scheduled login.
    """
    stage = 0
    xp = F(0)
    now = F(0)
    base_earned = regular_earned = extra_earned = F(0)
    spent = F(0)
    checkpoints = []
    claims = set()
    pending = {}
    logins = 0
    day_index = 0
    skipped = set(skip_days)

    def rate():
        return F(540) * FACTORS[stage] * (1 + base_bonus) / DAY

    def advance(at):
        nonlocal stage, xp, spent
        while stage < 8 and xp >= COSTS[stage]:
            if policy == 'late_cycle':
                if stage not in pending:
                    pending[stage] = at
                    return
                if at <= pending[stage]:
                    return
            cost = COSTS[stage]
            xp -= cost
            spent += cost
            checkpoints.append({'stage': stage, 'name': NAMES[stage], 'cost': int(cost),
                                'seconds': num(at), 'exact_seconds': str(at),
                                'elapsed_days': num(at / DAY), 'remaining_xp': num(xp),
                                'earned_base': num(base_earned), 'earned_regular': num(regular_earned),
                                'earned_extra': num(extra_earned)})
            stage += 1

    def next_login_day(index):
        while index in skipped:
            index += period
        return index

    while stage < 8:
        day_index = next_login_day(day_index)
        login_at = F(0 if day_index == 0 else day_index * DAY - utc_start_offset)
        if login_at < now:
            raise AssertionError('non-monotonic scheduler')
        if policy == 'asap_manual':
            ready_at = now + max(F(0), (COSTS[stage] - xp) / rate())
            if ready_at < login_at:
                delta = (ready_at - now) * rate()
                xp += delta
                base_earned += delta
                now = ready_at
                logins += 1  # Player explicitly returns and completes gate.
                advance(now)
                continue
        delta = (login_at - now) * rate()
        xp += delta
        base_earned += delta
        now = login_at
        logins += 1
        if policy != 'login_after':
            advance(now)
        if stage == 8:
            break
        # Three independent once-per-UTC-day categories; no offline activity grants.
        for category, units in [('map', 120), ('dungeon', 160), ('event', 80)]:
            key = (day_index, category)
            assert key not in claims
            claims.add(key)
            amount = units * participation * FACTORS[stage]
            if all_reward_bonus:
                amount *= 1 + base_bonus
            xp += amount
            regular_earned += amount
            if policy != 'login_after':
                advance(now)
            if stage == 8:
                break
        if stage < 8 and extra:
            key = (day_index, 'shared_extra')
            assert key not in claims
            claims.add(key)
            amount = extra * FACTORS[stage]
            xp += amount
            extra_earned += amount
            if policy != 'login_after':
                advance(now)
        if policy == 'login_after' and stage < 8:
            advance(now)
        day_index += period
        assert day_index < 2000, 'scenario failed to reach numerical endpoint'
    assert base_earned + regular_earned + extra_earned == spent + xp
    return {'scenario': name, 'policy': policy, 'participation': str(participation),
            'base_bonus': str(base_bonus), 'extra_units_per_active_day': str(extra),
            'login_every_days': period, 'skip_days': sorted(skipped), 'utc_start_offset_seconds': utc_start_offset,
            'all_reward_bonus_error_case': all_reward_bonus,
            'completion_days': num(now / DAY), 'completion_hours': num(now / 3600),
            'exact_completion_seconds': str(now), 'manual_logins': logins,
            'spent_xp': int(spent), 'remaining_xp': num(xp),
            'earned_base': num(base_earned), 'earned_regular': num(regular_earned),
            'earned_extra': num(extra_earned), 'checkpoints': checkpoints,
            'gate_assumption': 'All non-XP gates already prepared at advancement; no battle/material time modeled.'}


def main():
    output = ROOT / 'artifacts' / 'balance'
    output.mkdir(parents=True, exist_ok=True)
    specs = [
        ('daily_full', {}),
        ('daily_half', {'participation': F('0.5')}),
        ('daily_zero_activities', {'participation': F(0)}),
        ('wood_base_plus10', {'base_bonus': F('0.10')}),
        ('fire_earth_other_bonuses_plus11', {'base_bonus': F('0.11')}),
        ('max_base_plus15_no_extra', {'base_bonus': F('0.15')}),
        ('max_base_plus15_extra30', {'base_bonus': F('0.15'), 'extra': F(30)}),
        ('half_activity_base_plus15', {'participation': F('0.5'), 'base_bonus': F('0.15')}),
        ('login_every_two_days', {'period': 2}),
        ('login_every_three_days', {'period': 3}),
        ('login_every_two_days_plus15', {'period': 2, 'base_bonus': F('0.15')}),
        ('miss_first_seven_daily_logins', {'skip_days': range(1, 8)}),
        ('return_after_thirty_missed_logins', {'skip_days': range(1, 31)}),
        ('start_at_utc_2350', {'utc_start_offset': DAY - 600}),
        ('max_start_at_utc_2350', {'utc_start_offset': DAY - 600, 'base_bonus': F('0.15'), 'extra': F(30)}),
        ('start_one_second_before_utc_midnight', {'utc_start_offset': DAY - 1}),
        ('max_at_one_second_before_utc_midnight', {'utc_start_offset': DAY - 1, 'base_bonus': F('0.15'), 'extra': F(30)}),
        ('error_bonus_applies_to_all_rewards', {'base_bonus': F('0.15'), 'all_reward_bonus': True}),
        ('error_three_uncapped_multiplicative_buffs', {'base_bonus': F('1.15') ** 3 - 1}),
    ]
    results = []
    for name, kwargs in specs:
        for policy in ['asap_manual', 'login_before', 'login_after', 'late_cycle']:
            if policy == 'asap_manual' and (kwargs.get('period', 1) != 1 or kwargs.get('skip_days')):
                continue  # Strict absences cannot contain extra readiness logins.
            results.append(simulate(name, policy=policy, **kwargs))
    # Idle proof: no claims or advancement; no storage ceiling or automatic stage-up.
    idle = [{'offline_days': days, 'stage_stays': 0, 'basic_xp': 540 * days,
             'ended': False, 'assumption': 'Never logs in, no automatic advancement or activities.'}
            for days in [1, 3, 30, 120, 2000]]
    # An arbitrary-second split must not create or lose fractional passive XP.
    split = sum((F(seconds) * F(540) * F('1.15') / DAY for seconds in [1, 17, 3600, 82782]), F(0))
    assert split == 621
    # Pure arithmetic contract checks, not implementation tests.
    slot_xp, slot_seen, ledger_total = 100, 700, 1000
    restored = slot_xp + (ledger_total - slot_seen)
    assert restored == 400
    assert slot_xp + (ledger_total - slot_seen) == restored
    assert slot_xp + (1100 - slot_seen) == 500
    segmented_realm = F(540, 2) + F(810, 2)
    segmented_bonus = F(540, 2) + F(621, 2)
    assert segmented_realm == 675 and segmented_bonus == F('580.5')
    invariants = {
        'repeat_load_fixed_ledger_xp': restored,
        'later_ledger_1100_same_slot_xp': 500,
        'incorrect_second_load_add_to_current_xp': restored + (ledger_total - slot_seen),
        'realm_change_at_half_day_correct_xp': num(segmented_realm),
        'incorrect_retroactive_high_realm_whole_day_xp': 810,
        'bonus_change_at_half_day_correct_xp': num(segmented_bonus),
        'incorrect_retroactive_plus15_whole_day_xp': 621,
        'incorrect_floor_to_whole_xp_every_second_daily_xp': math.floor(F(540, DAY)) * DAY,
        'correct_basic_daily_xp': 540,
        'time_rollback_1000_to_900_elapsed': max(0, 900 - 1000),
        'time_rollback_retained_watermark': max(1000, 900),
        'watermark_then_1100_only_new_seconds': 1100 - max(1000, 900),
        'scope': 'Math-only planned contract assertions; no new runtime code or HTTP behavior tested.'}
    payload = {'kind': 'planning_only_not_implemented', 'basic_units_per_day': 540,
               'regular_activity_units': [120, 160, 80], 'extra_shared_units_cap': 30,
               'base_bonus_additive_total_cap': '15%', 'factor_by_stage': list(map(str, FACTORS)),
               'costs': list(map(int, COSTS)), 'total_cost': int(sum(COSTS)),
               'utc_day_seconds': DAY, 'initial_xp': 0, 'initial_basic_pack': 0,
               'warning': 'No真人时长/实际游戏验证. asap_manual includes extra player logins, not offline auto-breakthrough.',
               'scenarios': results, 'never_login_idle': idle,
               'planning_contract_invariants': invariants,
               'non_xp_progress_milestones': [{'stage': i, 'fractions': ['25%', '50%', '75%'], 'nominal_feedback_spacing_days': days / 4, 'reward_xp': 0} for i, days in enumerate(STAGE_DAYS)],
               'simulation_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'fractional_split_invariance_86400_seconds_plus15': num(split)}
    (output / 'qa-month-continuous-model.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    columns = ['scenario', 'policy', 'participation', 'base_bonus', 'extra_units_per_active_day',
               'login_every_days', 'completion_days', 'completion_hours', 'manual_logins',
               'spent_xp', 'remaining_xp', 'earned_base', 'earned_regular', 'earned_extra']
    with (output / 'qa-month-scenarios.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows({key: result[key] for key in columns} for result in results)
    stage_columns = ['scenario', 'policy', 'stage', 'name', 'cost', 'seconds', 'exact_seconds', 'elapsed_days', 'remaining_xp']
    with (output / 'qa-month-stage-timings.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=stage_columns)
        writer.writeheader()
        for result in results:
            for entry in result['checkpoints']:
                writer.writerow({key: result[key] if key in {'scenario', 'policy'} else entry[key] for key in stage_columns})
    print(json.dumps([{'scenario': result['scenario'], 'policy': result['policy'], 'days': result['completion_days']}
                      for result in results if result['policy'] in {'asap_manual', 'login_before'}], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
