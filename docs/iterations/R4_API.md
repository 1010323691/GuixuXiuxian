# R4实际接口与兼容性（v1.2.0实施）

本文记录当前实现；最终完整验收以QA当轮报告为准。保留R3全部HTTP接口、11页投影、单机NPC、GET只读、POST request_id/expected_revision与SQLite事务。未新增客户端时钟、资源、胜负或收益注入端点。

## 成长曲线与精确旧档升级

新长线八阶段基础日为0.5/1.5/3/5/7/8/9/11，共45日，成本为270/1215/3564/8640/17010/28080/43740/71280。基础540×境界系数/日与相加15%上限不变；理论及时突破的结丹/元婴/化神分别在0.5/2/5基础日，仍须满足其他条件。旧自由档完全不变。

数据库仍schema2，r3.version与CONTENT_VERSION仍1；曲线由growth.curve_version=2标记，不冒用全内容版本使旧活动权益失效。新growth在R3字段外增加`curve_version:2,migrated_from:null|1,remainder_denominator:int`。新档积分分母初始8640000000；旧余额精确比例转换后分母可为其整数倍，用于无损表示8/7等比例的小数微修为。remainder严格小于该分母；rate_num仍以原8640000000为速率分母，不能拿余额分母误算每秒增量。

旧schema2长线在Store启动期间一次升级：BEGIN IMMEDIATE锁→重读并验证→唯一`game.r3-before-r4.*.bak.db`备份并核current/slot/requests→旧速率结算至max(now,旧水位)→当前阶段未消费余额及余数乘new_cost/old_cost（含超过门槛部分）→添加cadence与journey→current/slot一起事务提交，revision+1，requests原内容不变。境界与ending不回退、不替玩家突破；已封界角色的潜修储备保持原余额与精确余数，不按阶段成本比例重标。total_micro只记录原历史产出及迁移前真正经过的离线产出，比例换算不伪造新收入。

并发启动锁后重检，只有一份成功升级备份与一次版本推进；备份失败拒绝写源，升级失败完整回滚并保留已验证备份。坏档/未知曲线拒绝而不清空。空档、旧free不升级或增加revision；schema1仍原`--migrate-save`显式备份流程，且不变长线。重新启动curve2不重复换算。

`view.growth`保留R3字段，新增curve_version/migrated_from；`available_micro`为整数微修为十进制字符串，亚微修为精确余数在状态内。GET只计算副本上的可用余额及当前行动，不写库/水位/revision；POST先核原版本与去重，再成长/资格同步、领域动作、旧率切新率、当前/slot/请求同事务提交。系统时钟回拨仅保证已结算权威值不倒扣，未落盘的未来预估按当前服务端时间校正。

## 可恢复挑战资格

`state.world.r3.cadence`严格形状：

```text
{version:1, available:int[0,3], last_recovered:int|null,
 banked_seconds:int[0,28799],
 reservations:{run_id:'reserved'|'spent'|'released'}}
```

初始可用3，每8小时恢复1，`available + reserved数量 <= 3`。**预约占容量**：入场可用3变2+预约1，满额时不囤隐形时间；即使在进行中副本离线一天，也不会变成可用3+预约1。成功消耗预约后才腾出容量开始回复；失败/撤离精确退还预约，不白扣。若原先已有其他消耗，容量不足期间仍累计回复；失败退回后达到满额即清余时。达到上限、长期离线的额外时间不银行化。

0次可手战练习，无预约/新掉落实例；扫荡必须至少1次可用。练习成功不推进掉落序号/保底，原普通重复材料规则保持。run_id由服务端生成，终态幂等；当前正式run必须唯一对应reserved，spent必须完成，released不能仍进行或变完成。旧daily仅保留历史统计，不再作为恢复额度权威。

旧档升级按迁移时有效UTC日剩余`max(0,3-旧当日成功数)`开始新回复时钟；旧正式进行中run保留冻结结果与资格，并占用一个预约，不在原可用基础上额外叠加。若旧run无正式权益则仍练习；不根据无法证明的旧历史补发多天回复。current/slot分别转换，但长线载入始终保留current资格账，不退水位/消费/预约。

内部模块接口：

| 函数 | 行为 |
| --- | --- |
| cadence.initial_state(now=None) | 新账，未入世不开始恢复 |
| cadence.sync(state,now) | 返回副本；不推进world.tick |
| cadence.reserve(w,run_id,context) | 同run重试不再扣；返回是否获得正式预约 |
| cadence.finish(w,run_id,success,context=None) | 成功消耗或失败退还，终态重复返回false |
| cadence.migrate_legacy(state,now) | 一次创建旧档资格/进行中预约 |
| cadence.project(state,context) | 当前回复权益预览 |
| cadence.validate(state,check_clock=False) | 结构/额度/双向run约束；Store最终check_clock=True |

context为Store内部整数UTC秒，now/day按成长水位钳制，raw_now仅内部诊断实际回拨；客户端不能提交context。增长与额度使用同一服务端时刻，在线离线一致；不是UTC午夜重置。Boss三次正式挑战与原日周活动仍独立UTC周期，不能混用此额度。

`view.world.loot.credits`：`{available,capacity:3,reserved,server_now,next_at,seconds_until_next,interval_seconds:28800,clock_rewound,status}`。available已扣进行中预约；满额或未入世next_at/seconds_until_next为null。UI倒数到0只能刷新服务端，不能本地加次数；回拨提示与growth一致。GET在副本上预览恢复，实际扣除由POST重算。

## 快捷结算与实际动作

所有新增行为仍在POST /api/action；类型/未知字段由world.SCHEMAS严格校验。

| action | params / 规则 |
| --- | --- |
| world_dungeon_sweep | `{dungeon:string,chapter:int[0,7],difficulty:int[1,3]}` |
| world_story_accept | `{story:string}` |
| world_story_claim | `{story:string,item?:'blade|armor|pendant'}`；器物奖励必须选择item，材料奖励无需item |
| world_elite_enter | `{elite:string}` |

扫荡必须有同副本/章节/难度实际手战clear证明，且地域/境界/装备分/前难度条件满足，无进行中的战斗或探索；不凭高级战力预览或其他难度胜利解锁。旧长线已有dungeon_wins在一次迁移中转为实际手战证明（旧版没有扫荡）；新扫荡run.manual=false，不能伪造新手战/困难故事证明。

扫荡复用普通最终通关结算：同冻结表、掉落实例、保底、材料、重复灵石10×难度与地域材料3；消耗1恢复资格，无HP/MP/丹符消耗，仅推进1世界行动及1次AI/经济tick，不伪造三次战斗胜场或回填十余行动生产。与手战相比世界时间不同，不能声称整段NPC经济收益完全等同。正常通关/退出/战败均处理原预约，所有结果与请求记录一笔事务。

`view.world.loot.dungeons[].sweep={enabled,reason,consume,preview,action:{id,params}}`与探索页同名标准action共同给真实入口；禁用原因由服务端出，客户端导航不代替执行校验。

## 七段故事与支线精英

`r3.journey={version:1,stories:{id:{progress:[int...],claimed:bool}},elite_wins:[id...],manual_clears:[clear_key...]}`。故事按前段已领奖和stage[0,0,1,1,2,2,3]开放，recommended_day仅建议、不是现实日历锁；接取后计数，无失效，漏登可补。故事装备3段为自选三器q1/ch1、q2/ch2、q3/ch3，不消耗挑战资格/掉落保底，不发XP或额外效率。

装备故事唯一来源为`story:profile_id:story_id`，原r3.receipts保留唯一实例凭证；source数量必须等于claimed的0/1，核模板/品质及仍持有物的章节，分解后原source凭证仍在但原uid不复活。普通材料故事以claimed资格记录同事务发材料/待领，重复请求及新ID重复领奖均不能再发。

三精英是同一战斗引擎的elite kind，固定配置/炉盾、毒、抽灵机制；进入需对应已接未领奖故事、合法地域/境界且未赢过。战败可补给重试，赢过一次不再重复刷；无独立常刷掉落，收益归故事唯一权益。坏档校验反向核故事、已领奖、elite_wins与当前elite battle，不能仅检查target存在。

`view.world.journey={layers:[{id,title,recommended_day,unlock,status,objectives:[{label,value}],rewards,action:{id,params}}],elites:[{id,title,status,preparation,rewards,action:{id,params}}]}`；quests页标准sections id为r4_story:id，探索页提供真实elite_enter action，器物选择通过标准select fields。仍遵循disabled/reason与确认规则，不让客户端根据建议日自行开锁。

## 读档、测试与边界

新长线检查点仍仅恢复安全位置：当前完整成长/曲线、资格预约、物品经济、journey故事/领奖/手战证明、日周/Boss权益和world.tick都不回退；进行中战斗/探索保持当前位置。已入世不可退序章、不同profile拒绝。旧free完整回档与未入世序章原行为不变。升级slot不等于载入时把旧slot账覆盖当前。

架构测试在tests/test_r4_architecture.py；真实v1.1.0来源JSON fixture及哈希/生成脚本在tests/fixtures，正常测试重建临时DB不依赖dist或真实.db。封界储备一致性修复后架构19+growth9共28项已通过（0.958秒），schema1迁移12此前组合通过；其中包含并发升级唯一备份、失败源字节不变、精确比例/overflow/封界储备、旧请求去重、位置检查点不回退预约、扫荡真实材料/时钟/资源及反向坏档。独立浏览器、全部新动作入口及完整45日路线仍以QA最终当轮结果为准，不沿用旧版通过替代。
