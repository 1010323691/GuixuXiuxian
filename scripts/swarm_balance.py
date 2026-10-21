"""群战平衡对照（FB3）：同一角色、同一策略下，旧单体战斗与新群战的拍数、剩余气血与胜负对比。

用法：python scripts/swarm_balance.py [--check]
--check 时任一组超出目标（拍数 ±15%、剩余气血 ±10% 满血比例）即以非零退出。
白盒直接调用 world._auto_battle；胜利结算被替换为空操作，只比较战斗本身（不改任何进度数据）。
"""
import copy
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game import rules, world, world_config as C  # noqa: E402
from tests.support import baseline_route  # noqa: E402

KINDS = [('wild', ''), ('escort', ''), ('secret', next(iter(C.SECRETS))), ('guard', ''), ('dungeon', 'den'), ('dungeon_boss', 'den'), ('elite', 'caravan_guard')]
STAGES = [0, 2, 4, 6]
STRATEGIES = ['balanced', 'steady', 'aggressive', 'frugal']
BEAT_TOL, HP_TOL = .15, .10


def base_state():
    state = rules.new_game('平衡QA', mode='longline')
    context = {'now': 1800000000, 'day': '2027-01-15'}

    def act(action, **params):
        nonlocal state
        state, _ = rules.apply_action(state, action, params, context=context)
    baseline_route(lambda: {'state': state}, act)
    act('world_enter')
    return state


def fight(state, kind, target, stage, strategy, swarm):
    w = copy.deepcopy(state['world'])
    w['stage'] = stage
    attrs = world.attributes(w, kind in {'guard', 'elite', 'dungeon_boss'})
    w.update(hp=attrs['hp'], mp=attrs['mp'], battle=None)
    real = 'dungeon' if kind == 'dungeon_boss' else kind
    if real == 'dungeon':
        w['dungeon'] = {'id': target, 'difficulty': 1, 'stage': stage, 'round': 2 if kind == 'dungeon_boss' else 0, 'run_id': 'balance'}
    counts = C.SWARMS['counts'] if swarm else {}
    with mock.patch.dict(C.SWARMS, {'counts': counts}), mock.patch.object(world, '_victory', lambda w, b, events: w.update(battle=None)):
        world._start(w, real, target, 1, stage if real == 'elite' else None)
        context = {}
        world._auto_battle(w, {'strategy': strategy}, [], context)
    report = context['battle_report']
    return {'beats': report['rounds'], 'hp': report['frames'][-1]['player']['hp'], 'max_hp': report['player']['max_hp'], 'outcome': report['outcome'],
            'units': len(report['enemy'].get('units', []))}


def main():
    check = '--check' in sys.argv
    state = base_state()
    rows, worst = [], []
    for kind, target in KINDS:
        for stage in STAGES:
            for strategy in STRATEGIES:
                old = fight(state, kind, target, stage, strategy, False)
                new = fight(state, kind, target, stage, strategy, True)
                dbeat = (new['beats'] - old['beats']) / max(1, old['beats'])
                dhp = (new['hp'] - old['hp']) / max(1, old['max_hp'])
                ok = abs(dbeat) <= BEAT_TOL + 1 / max(1, old['beats']) and abs(dhp) <= HP_TOL and old['outcome'] == new['outcome']
                rows.append((kind, stage, strategy, old, new, dbeat, dhp, ok))
                if not ok:
                    worst.append(rows[-1])
    print('| 类别 | 境界 | 策略 | 小怪 | 旧拍数 | 新拍数 | Δ拍 | 旧余血 | 新余血 | Δ余血(满血比) | 胜负 | 判定 |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|')
    for kind, stage, strategy, old, new, dbeat, dhp, ok in rows:
        print('| %s | %d | %s | %d | %d | %d | %+.0f%% | %d | %d | %+.0f%% | %s→%s | %s |' % (kind, stage, strategy, new['units'], old['beats'], new['beats'], dbeat * 100,
                                                                       old['hp'], new['hp'], dhp * 100, old['outcome'], new['outcome'], '✓' if ok else '✗'))
    print('\n超出目标：%d / %d 组（拍数 ±%d%%（另容 1 拍取整）、剩余气血 ±%d%%、胜负一致）' % (len(worst), len(rows), BEAT_TOL * 100, HP_TOL * 100))
    return 1 if check and worst else 0


if __name__ == '__main__':
    raise SystemExit(main())
