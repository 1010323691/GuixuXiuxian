# R3 开发实现与检查点

状态：应用实现已接通，等待当轮独立QA与真实浏览器冻结验收；本记录不把设计模拟当实测月余游玩。开发仅维护world/rules/loot，成长存储由架构、内容由策划、前端由视觉、测试由QA维护。

## 实现边界
- 纯 `rules.new_game(name)` 保持free兼容；支持mode='longline'。HTTP/Store默认长线由架构接入，显式free保留旧玩法及完整读档。
- 仅长线含world.r3，独立profile_id、实例所有权、材料、待领、确定性run/保底/日资格、Boss周期best/paid、里程碑与日周活动。growth字段由架构处理。
- rules/world接收服务端context={now,day}；不存在HTTP客户端指定时间、伤害或奖励入口。长线旧直接XP路径统一屏蔽，手动吐纳拒绝而不是点0收益；弟子授业改灵石5。碑文奇遇已用R3非XP配表，避免付晶换空效果。
- R3突破成本及最终封界消费144450总额服从r3_config；序章与旧自由档不改数值。装备实例与旧inventory/gear不双写；主线装备检查、任务交付、强化和分解采用uid唯一所有权。
- 当前成长预览按微修为，小境界0.5点阈值不截断。最终ready取真实world_finish可用条件；封界后required=0/reserve=true，不伪称又可突破。

## 新动作（全部沿POST /api/action）
| 动作 | params |
| --- | --- |
| world_loot_equip | uid |
| world_loot_unequip | slot：weapon/armor/pendant/main/guard |
| world_loot_choose | uid，effect_type：cultivation/combat |
| world_loot_enhance / world_loot_quality / world_loot_dismantle | uid |
| world_loot_craft_treasure | slot：main/guard，effect_type |
| world_loot_exchange | item：dust/enhance_material |
| world_loot_claim | receipt |
| world_boss_enter | {} |
| world_boss_claim | day：服务端已存在的UTC周期 |
| world_milestone_accept | stage，tier：25/50/75，branch |
| world_milestone_claim | stage，tier |
| world_activity_accept | project |
| world_activity_week_accept | {} |
| world_activity_claim | key |

共16种新动作。原world_dungeon_enter在长线增加chapter参数，难度仍1..3；旧free保持原参数。战斗沿原8个真实指令，不新增客户端评分入口。

## 投影与前端入口
既有11页全部保留。view.world.loot提供实例比较before/after/delta文本、五槽、材料、待领、分章节难度/资格/保底、Boss成绩差额和progress；行为仍由pages.actions/fields/confirm提供。已拥有实例在人物页、法宝与材料兑换在四艺、固定章节副本及Boss在秘境副本、可选里程碑和日周双目标在闻道。

view.world.goals最多3项，只引用已存在动作的page/id/static params，导航不提交；view.world.battle.statuses/counterplay表达毒次数、盾值、汲灵反制和Boss个人评分。副本活动不直接发修为，原非XP具体收益保留；detail最终由真实cost/effect重建。

日周活动由activities模块观察成功行动，不追溯接取前行为。满级阵法可暂停再启用计一次真实使用，关闭不计；制造阵法自动启用。三副本难度2/3末战分别为毒、一次护盾、常击汲灵；难度1和旧free均不改变。毒顺序是旧毒先跳、存活后刷新新毒2次；火符对盾2A无溢出本体；防常击或镇魂可免汲灵。

后端能力均已提供通用动作入口；特殊待领/补差/当前活动仅在实际存在相应权益时出现，不能把未触发状态说成已经完成浏览器验证。

## 已实际执行的开发检查
1. 真实Store默认长线新角色→完整原53行动序章→入世→时钟前进86400秒预览540修为→世界Boss正式开打、普攻、退出、领取best差额成功。Boss单场best40，币4；这些是隔离临时数据，不是修改玩家档。
2. R3首批27项实际运行25通过、2公开路线因QA兑换后未补矿失败，已交QA修正合法准备流程，不修改产品或削弱断言。
3. 后续选择性回归：rules/world_combat/world_validation/world_economy/migration/r3_items/r3_rewards/activities共57项通过（0.389秒）。新增成长/全部公开路线与浏览器最终结论由QA报告负责。
4. 三机制纯边界fixture断言通过：妖巢旧毒遇重击先跳后刷新2，丹清毒；熔炉火符护盾93→13且本体未受伤；星塔常击MP60→54。该fixture仅验证规则边界，不冒充公开通关。
5. 合法实例fixture性能：active长线世界50实例，完整投影3次平均48.5ms，JSON200.8KiB、345动作；200实例平均143.8ms，JSON494.6KiB、795动作。仅投影，不含HTTP/浏览器渲染；每uid动作只读检查，不逐项deepcopy整个世界。原领域动作仍有有限探测副本。

以上结果属于开发检查点，不替代QA独立验收、完整76旧回归、最终新测试与真实页面玩法。数值模拟40–45日不等于真人游玩月余，当前也不宣称所有未来缺陷不存在。
