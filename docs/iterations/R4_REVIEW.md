# R4架构交叉审查

范围：实际读取world/loot/journey/growth/cadence/storage，审查规则、权限、时序、经济及持久化；不修改开发拥有的模块。以下证据是架构定向验证，不能替代QA最终全量与浏览器。

| 项 | 风险与处理 | 实际复查 |
| --- | --- | --- |
| R4-A01 故事装备凭证双向性 | 原仅claimed=true要求凭证，false但已有source会允许再次领奖；已交开发修复为source数量==int(claimed)，并核奖品模板/品质/仍持有章节 | legal elite fixture通过，追加未领奖story receipt须ValueError且输入保持；tests.test_r4_architecture跨模块用例通过 |
| R4-A02 精英战斗权限 | 原仅关联story存在，未排除已领奖/已胜/异地；已交开发修复 | 合法caravan_guard允许，非法region/已elitewin拒绝；固定HP/攻击/重击/章节/机制与配置相符 |
| R4-A03 预约反向关系 | 只检查账本→run不足以发现当前正式run删除预约；cadence已反向要求当前eligible run为reserved，released不能仍当前/再完成 | 缺预约、非法额度/余时/伪run坏档用例拒绝；成功/失败/重试/练习边界通过 |
| R4-A04 发包可复现性 | 初测试依赖dist旧ZIP，源码包不带dist会失败；已用真实旧发行版生成固定JSON源fixture，记录源ZIP/current/slot/requests哈希与生成脚本 | 正常测试无旧ZIP依赖，无.db、无玩家数据、无skip；临时重建库后升级/备份/回滚验证通过 |

时序/经济实审：扫荡与手战共用_complete_dungeon→loot.complete_run；只推进一次世界行动，不伪造三战kills；一份预约成功消耗、一次保底/轮换、正常重复钱材。独立定向用例核HP/MP不变、灵石+10/地域草+3/尘+2/强化材+2、tick+1、actions_taken+1、不新增手战证明或战斗胜次。手战flee、战败与探索外撤离均在清dungeon之前调用release_run，胜利调用finish(success)。同章同难manual_clears为扫荡前置，困难故事只认manual=true，不能快捷刷“实际手战”证明。

持久化实审：GET同步仅副本；POST dedup与原revision先于同步，current+slot+requests一笔SQLite事务；失败不留下额度或成长水位。升级先锁/重读/验证/独立backup，再旧率积分与精确成本比例变换；并发启动仅一次备份和revision+1。total_micro是历史产出而非转换后余额，迁移不将表示差额计作收益。slot同步迁移后仍只允许安全位置恢复，不返突破消费/预约/奖励资格；free不迁移。

实际验证：架构19项通过0.311秒；growth9与schema1迁移12此前组合通过，当前完整QA在独立执行。已关闭上述审查项，当前未登记架构阻断。内容长线可玩性、45天整体数值/装备可达性和浏览器控件仍由主策划/QA按本轮代码验证；本地文件/系统时间可改，不宣称绝对反作弊。

冻结复核SHA256（运行源文件，不包含文档）：

- `game/growth.py`：`760b385a5651f093df0d90f6c28ab9dafdd83059fc9dc9aa4e5d9d8dc719744d`
- `game/storage.py`：`76770087f8d4d40d27552eab6ecd3299dcf724f1f7452badbacea2817e434511`
- `game/cadence.py`：`fc33d7d89eda3cf4e99d9fda29a7e9e9d95fd2ec46712dc448335a1324b0012e`
- `game/activities.py`：`ab3152388170ede25e6a7a0d40f5a36e29923961bf899d184a8be74518e2ac3c`
- `server.py`：`1e6df718ae842e577e3c0f09fc5538f0f1fbcdfed4ec57da6cfa9bcc9106d789`
- `game/world.py`：`4c64d48f52526930414ff308e8066b7f963c5658d9dd0109c04f58773e469db7`
- `game/loot.py`：`c0e108fed25d8ace701ba9173650bf5708e4e5995d9a240bdffdd0e935c423a6`
- `game/journey.py`：`eff17c029bf67feaefb813fb1a2f2a58b3e0f96a119ce1920d5ad954c37b0146`

封界储备一致性修复：按PM最终裁决，旧封界角色先按旧速率结算实际离线产出，随后ratio=1保留真实余额与精确余数，不按新晋升成本重标；stage/ending与total_micro历史定义不变。sealed用例已改为独立原精确余额预期，并显式核历史产出与整点余额。修复后架构19+growth9共28项通过0.958秒；完整QA须以此新growth哈希重跑，不沿用旧freeze全量。
