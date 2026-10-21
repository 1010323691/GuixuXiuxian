# R5 自动斗法正式接入（点击战斗退役）

状态：已实现并通过白盒全量（196项，`python -m tests.parallel`）。真实浏览器套件（`tests.browser_*`）依赖 Playwright 与 `/usr/bin/chromium`，本轮环境未安装，**未运行**；已按新接口修改其脚本，需在具备浏览器的环境重跑。以最新代码与当轮证据为准。

## 1. 玩家侧变化

| 项 | 旧 | 新 |
| --- | --- | --- |
| 战斗操作 | 每回合点普攻/强攻/防御/丹/符/撤退 | 战斗中仅「自动斗法」策略按钮，一次提交打完整场 |
| 世界策略 | — | 均衡 `balanced`、稳妥 `steady`、强攻 `aggressive`、节制 `frugal` |
| 序章 | 五个战斗按钮 | 单一「自动斗法」`auto_battle` |
| 法宝 | 战力型只加攻击/气血倍率 | 战力型仍保留倍率；另外本命法宝独立出击、护持法宝重击时回护（见 §3） |
| 撤退 | `world_flee`/`flee` | 退役。败退/平局上限自动返回安全地；进行中的旧档战斗同样由自动斗法完成 |
| 回放 | — | 响应带 `battle_report`，页面云海御空回放；刷新后仅保留日志，不入存档 |

## 2. 接口

- 世界：`POST /api/action`，`action=world_auto_battle`，`params={"strategy":"balanced|steady|aggressive|frugal"}`，须当前处于战斗，其余字段被拒。
- 序章：`action=auto_battle`，`params={}`。
- 退役动作 `world_attack/power/defend/pill/fire/guard/soul/flee` 与序章 `attack/power_attack/defend/use_pill/flee`：不再出现在投影，提交一律 400，且不修改状态。
- 响应新增可选 `battle_report`：`outcome(victory|defeat|window|stalemate)`、`rounds`、`strategy`、`enemy`、`player`、`treasures`、`frames[{round,player,enemy,intent,action,events[{type,source,target,label,amount}]}]`。`frames` 长度为 `rounds+1`；重复请求（`duplicate`）不再返回回放。
- 事务与时钟：整场在同一次请求事务内原子完成并沿用 `request_id/expected_revision`；每拍仍推进一次世界时钟并计一次行动（`tick`、`actions_taken` 增加 `rounds`），与旧点击战斗等价。

## 3. 规则

- 内部单拍 resolver `world._round` 保留旧的全部战斗数值（防御减半、护身符、镇魂、焚火破盾、毒、汲灵、同行支援、Boss 十二拍、演武快照背包等），只由自动斗法调用。
- 决策：规则策略 `_choose` 给出首选招，再对合法候选各自「前瞻试演」到战斗结束并按策略评分，取最优（不弱于规则策略）。评分：均衡=胜负、少耗补给、剩余气血；稳妥=胜负、剩余气血（命中保命规则直接执行，气血≤75% 服丹）；强攻=胜负、拍数少；节制=不耗任何丹符。世界Boss按个人有效伤害。试演有步数与总预算上限，超限回退规则策略；全程确定性，同初态得同结果。
- 上限：单场最多120拍；平局上限自动撤离，无反击也无本战奖励。
- 法宝（仅 `effect_type=combat`）：本命每2个玩家机会出击一次，伤害=攻击×30/34/38/42/46%（按品质），经敌方护盾吸收后才计 Boss 个人伤害；护持在敌方重击时回护，拦截=最大气血×6/8/10/12/14%，仅实际拦下才产生 `shield_absorb`。修炼型法宝不参战。配置在 `game/r3_config.py::TREASURE_COMBAT`。

## 4. 影响与未验证

- 战力型法宝在战斗中强于旧版（倍率之外新增出击/回护），经济与奖励未做重平衡；Boss 评分仍受 2×参考封顶。
- 完整战斗逐拍演算不进存档；若需存档级战报须新设计迁移。
- 未执行真实浏览器套件；回放视觉仅在内置浏览器桌面/手机宽度做过人工抽查，未做自动化像素验收。

## 5. 验证入口

`python -m tests.parallel`；新增/改写测试：`tests/test_auto_battle.py`（法宝出击/回护、策略边界、平局上限、按钮可达）、`tests/test_world_combat.py`、`tests/test_r3_mechanics.py`、`tests/test_r3_boss.py`、`tests/test_rules.py`、`tests/test_game.py`。旧单拍规则断言经 `tests.support.battle_round` 访问内部 resolver 保留。
