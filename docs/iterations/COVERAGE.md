# W1 完整凡界验收矩阵

冻结代码的独立标准库76/76全部通过（无跳过），原序章与完整世界两个真实浏览器脚本通过。下列22条均有可运行闭环证据；这指本版已定义有限内容范围，不宣称穷尽所有修仙设定、全设备兼容或绝无未知缺陷。用户确认PVP/跨域/拍卖为明确标注的本地NPC模拟，仙界不进入本版。

详细命令和证据以WORLD_TESTING.md、WORLD_BALANCE.md、WORLD_ARCHITECTURE.md及artifacts/world-qa为准。表内“通过”同时要求实现、公开UI入口及相应规则/集成/页面验证，不以静态展示替代行为。

| 模块 | 验收闭环 | 状态 | 实际证据 |
| --- | --- | --- | --- |
| 世界/势力 | 三洲声望、地域解锁、任务与市场作用 | 通过 | 三秘境/社会路线、九州真实页面、WORLD_BALANCE |
| 境界/功法 | 炼气序章→筑基至渡劫→封界；三功法升级切换 | 通过 | 完整凡界、三灵根体质功法用例；两条独立HTTP路线 |
| 灵根/体质 | 三类觉醒/培养/重修，派生收益与上限 | 通过 | test_three_roots_bodies_and_skills_have_actual_effect_and_caps |
| 宗门/师徒 | 三宗委托贡献分账与职位；拜师请教、授业派遣 | 通过 | test_repeated_rewards_social_permissions_and_dispatched_progress；三NPC关系用例 |
| 家族/社交 | 三NPC好友同行、建族邀请建设移除解散 | 通过 | test_three_npc_relationships_teacher_and_family_variants；浏览器text表单 |
| 炼丹 | 三丹方产物实际恢复/破障消耗/养根 | 通过 | test_all_twelve_recipes_outputs_are_consumed_equipped_or_affect_rules |
| 炼器/装备 | 三器制作装备强化；任务交备用器保留已装备物 | 通过 | 12配方用例、test_delivering_spare_blade_keeps_the_equipped_copy_and_its_stats |
| 制符 | 焚火/护身/镇魂实际伤害、防护和控制 | 通过 | 12配方用例、6项战斗精确边界 |
| 阵法 | 三阵制造、等级、启停及修炼/战斗/突破影响 | 通过 | 12配方用例、test_home_production_collect_and_array_effect_can_be_toggled |
| 秘境/奇遇 | 三秘境多节点与三种有实际结果的奇遇 | 通过 | test_all_three_secrets_and_three_dungeons_have_real_completion；三奇遇不可重放 |
| 洞府 | 三设施生产→仓储上限→收取→再投资 | 通过 | 洞府生产规则用例；浏览器实际生产/收取 |
| 副本/Boss | 三副本各三难度真实三战胜利、八境守关及失败恢复 | 通过 | 九档副本/重复奖励、完整凡界用例、独立B高难路线 |
| NPC竞技 | 三类对手、周期奖励、模拟耗材隔离、真实赛果 | 通过 | 三域/竞技用例、test_real_auction_delivery_during_simulated_combat_survives_flee |
| 模拟跨域 | 三域晋级、冠军一次结算、新赛季与NPC封顶成长 | 通过 | test_three_domain_npc_season_and_claim_once；浏览器冠军闭环 |
| 商城/交易 | 真实数量买卖、价格修正、可再生来源与资产变化 | 通过 | 市场数量边界、动态事件、浏览器非默认数量买卖 |
| NPC拍卖 | 币货托管、具体NPC超价退款、交割待领、资金回流 | 通过 | test_world_economy.py十项，含逐tick守恒与NPC满资产pending |
| NPC/剧情任务 | 主线/三NPC支线真实目标交付与一次奖励 | 通过 | test_three_npc_side_quests_require_real_delivery_and_claim_once；凡界封界 |
| 成就/称号/榜单 | 分档一次奖励、佩戴派生效果、本地实际统计口径 | 通过 | 成就称号用例、三NPC关系；策划R3榜单0赛果定点复核；浏览器佩戴 |
| 规则AI/动态事件 | 真实预算库存生产挂牌竞价、三动态生效到期 | 通过 | test_dynamic_events_have_real_modifiers_expire_and_npc_assets_are_bounded；经济守恒 |
| 长线/版本 | 凡界终局后继续经营赛季；仙界只留扩展无假入口 | 通过 | 完整路线、下一季、数据/扩展契约；无仙界实现 |
| 前后端一致性 | 11页、79种动作公开投影、字段/确认/禁用/异常同步 | 通过 | 架构6真实情境79/79入口；真实浏览器11页/39动作/3字段；合同7项 |
| 迁移/持久化 | schema1当前/手动/战斗/账本唯一备份原子升级，失败保留 | 通过 | 迁移12项、深校验7项、world事务/保存重启；主实例schema2+schema1备份 |

## 多轮迭代记录
R1：五岗位独立提案，逐项识别原版缺口，PM与用户确认单机NPC范围。
R2：交叉质疑数据/协议、全系统门槛、跨域赛程、洞府生产、NPC预算与派遣时序；统一schema2显式迁移及11页投影，改善多路径道行与战斗取舍。
R3：真实联调发现并修复资产满容量丢失、具体NPC退款、演武快照吞收益、表单误禁、坏档浅校验、入口隐藏/战斗指令难找、任务奖励文案和虚假竞技口径；保留全部失败和执行器修正证据。
R4：冻结后76项与两个浏览器完整运行通过；项目经理审图、核对真实输出，并从独立解压runtime归档完成序章53动作、入世/炼器装备、停服重启/读档。最终源码归档逐文件CRC/哈希与此验证代码保持一致。

## 边界
未执行真人时长/主观乐趣测试、实体手机/其他浏览器/全面读屏器、长期负载/真实断电/磁盘满。320px为Chromium视口模拟。规则AI非外部大模型，NPC榜非真人榜；未提供公网多用户服务。保留这些验证边界，不将其写成失败或通过；后续版本按实际反馈进入新一轮迭代。
