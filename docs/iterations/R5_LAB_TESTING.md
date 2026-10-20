# R5 独立战斗实验QA

状态：最终独立空战实验验收通过，14/14实验测试与7项真实浏览器检查通过，17份正式运行源SHA不变。不是正式游戏升级或正式战斗发布；未跑正式181项，未修改game/static/data。QA仅维护`prototypes/r5-combat/tests/`、`artifacts/r5-review/qa/`和本报告。

## 1. 实际合同与边界

依据R5_ARCHITECTURE_PROPOSAL末节、R5_DESIGN_PROPOSAL及PM最终裁决。独立server/engine一次同步生成整场确定性轨迹；UI播放已算结果。请求必需scenario/build/strategy三枚举，丹预算0..3、火/护/魂各0..2、npc严格bool，预算默认0/false。没有正式revision、存档、恢复资格、奖励或DB，未来正式分块/持久化仍只是方案。

实验三节点为**毒→盾→汲灵的混合机制连战**，不等于正式副本“前二巡守+末Boss”的复刻。Boss血量1e12，用12个玩家机会评分，不要求击杀；R990、评分上限1980只是实验参考，不发正式币/道具。

## 2. 独立测试与实际结果

初版源码：`test_lab_engine.py`8项、`test_lab_http.py`5项，合13项；空战补实际吸收账后引擎9项，合14项，不把subtest矩阵膨胀成用例数。metadata之前最终一次13/13通过0.174s（`pre-metadata/final-suite.txt`）；最终补丁后结果待下节。

- 独立Boss算式：强攻显示拍1/4/7/10（内部索引0/3/6/9），4×200+8×100=1600直接伤；双持续宝各错峰6次×40，共480；个人2080，同行3/6/9/12拍各10共40且不计个人；参考封顶1980。所有事件不超过第12拍，死亡可在第12拍发生，不把败退改成胜利。
- 双爆发宝本命3/9拍、护持5/11拍，各120，共480；第一轮预热与重触发实际生效，不补第13拍。强攻每帧CD是按下一机会计算的0/2/1/0循环，明确显示拍与内部索引差一。
- 受控engine fixture初MP0：普攻回蓝，直到第10拍才首次合法强攻；不负MP、不错误重试循环。星塔初0MP普攻回2、汲灵只扣2，HP仅受99敌伤而非额外“蓝不足转血”。此fixture不冒充HTTP允许传任意stats。
- 60格engine（5场景×3构筑×2策略×零预算/全预算+NPC）：玩家/敌方快照一致、事件ID唯一/帧事件复原全轨迹、实际伤害与metrics守恒、每帧HP/MP有界、CD跨节点不免费重置、总消耗不越预算、输入不被修改。矩阵不要求全部构筑默认胜利；授权多补给不保证成绩单调提高，主行动机会成本与CD相位是真取舍。
- 火符实破盾200、不溢本体；初炉盾315−200−本命持续40=75，敌HP仍1260。毒巢进攻策略出现实际毒跳，均衡防重免挂，低血授权丹真实清毒；不是只检查状态图标。完整受控三节点护持/均衡/3丹1火真实22拍胜；HP/MP/CD/预算连续。HP1/MP0早败后后两节点仍锁定、无后续伤害/假通关。
- 真实隔离HTTP30格重复请求得到完全相同结果/稳定simulation_id；零默认与显式零相同。拒未知/缺枚举、旧talisman_budget/companion、stats/initial/time/version、bool冒整数、float预算、越界/负数/非法npc、NaN/Infinity/1e999、重复JSON键、坏JSON/编码/Content-Type；16384字节合法输入接受、16385拒413。GET health/config纯读且正式state/action/new-game/save/load路径均404，静态路径不能读server源码。

## 3. 真实Chromium

metadata之前浏览器3checks通过（`pre-metadata/browser-report.json`），无pageerror、console.error或failed request。只两次POST，均到隔离实验`/api/simulate`：三节点连战和另一次Boss。真实表单设置构筑/策略/丹符预算，桌面运行按钮与窄屏quick-simulate均提交真实后台。

轨迹抽样初态/第一拍/中段/末帧逐一核HP/MP、敌下一意图与CD。已通关节点真标已通过，死亡节点不显示活敌下一招。暂停后游标不动，2x播放游标真实推进；回看节点/拖动时间轴/重播/跳尾和键盘Enter只播放不新增POST，最终metrics逐字一致。切新Boss后旧timer不能覆盖新战况。320px无横向溢出，减少动态效果后实际meter transition为0s。Boss评分面板个人/NPC与最终metrics吻合，12拍窗口可读，敌血仍>0、不假击杀。完整复盘包含事件归属/节点/拍数，已亲看桌面与窄屏截图。

截图：`desktop.png`/`mobile.png`为三节点，`boss-desktop.png`/`boss-mobile.png`为评分窗口；均在实验QA目录。最终补丁后将覆盖最新截图，pre-metadata保留前版。

## 4. 发现与回修/测试自身问题

- 只读审查发现旧frame先复制after再更新intent，after与投影不同；开发在稳定checkpoint前已修，独立60格断言确认一致，不伪称新产品失败。
- UI旧complete与cleared映射不同会使完成节点仍未通过；反馈视觉后最小修复，真实三节点浏览器已验证。
- 前两次浏览器失败是QA测试假设错误：把1→2→1两次速度切换当4x，及inner_text换行与textContent比较不一致。只修测试，保留`browser-round1.txt`/`browser-round2.txt`，不改应用数值或削弱“零POST/同结果”断言；第三轮通过。
- PM最后要求战前可展开准确倍率/预热/成本说明，属于只读metadata/UI可用性补全。正在等待该补丁，前版结果不冒充新hash已测。

## 5. 隔离与复现

17份正式运行源SHA：`formal-runtime-before.json`与`formal-runtime-after.json`一致，0变更。实验engine仅copy/hash/json，server独立静态目录与HTTP处理，无生产模块/SQLite导入；真实浏览器网络仅实验API/静态，不连接正式8000或玩家数据。实验测试临时独立端口，结束进程清理。

执行：`python -m unittest discover -s prototypes/r5-combat/tests -v`；可选Playwright+`/usr/bin/chromium`后`python prototypes/r5-combat/tests/browser_lab.py`。受控initial hook只有engine fixture，HTTP明确拒绝。最终tested源码SHA见`lab-tested-hashes.json`。

## 6. 当前结论与未覆盖

候选实验已证明自动/CD/构筑/三机制、三节点、12拍个人评分和只播放UI可以实际运行。metadata与空战补丁后的统一复验见§8。没有本轮正式发布、旧档迁移、九类世界战斗自动兼容、分块持久恢复、正式经济/伤害重平衡结论；这些均不能引用本实验通过替代。未做真人长期可玩性/可访问性用户研究，不把自动化耗时当真人体验。


## 7. 用户新增空中斗法视觉范围与实施过程

PM同步用户要求：修士必须御空，可用代身；独立法宝视觉借鉴修仙题材的设计语言。策划/视觉进一步讨论后由PM裁决具体方案，当前地面人形checkpoint仅历史。数值/CD/预算不变，metadata后13项继续通过（metadata-engine-suite.txt）；不重跑正式181套。

新版浏览器保留原全部权威数值/控制/路线/评分断言，额外亲看桌面/320截图核无地面站立姿态、云海与悬空灵印、主副法宝有独立图形与来源。持续/爆发/护持须可辨，事件source=player/main/secondary/npc不混主体；减少动态效果下仍有静态归属和状态，不依赖闪烁才能理解。当时新场景未freeze，不标通过；最终结果见§8。


空战表现增量复验：开发仅新增真实`shield_absorb`事件和`frame.decision_reason`。独立用例总数升为14（`air-event-suite.txt`，14/14、0.186s），不把架构/策划矩阵诊断数量加入QA计数。均衡护持Boss、零耗材的独立吸收账：第3/4/9/10拍55/35/55/35共180，四次防御另减220，总减免400、实际损血304、末HP296；吸收事件只在>0出现，secondary→player且先于敌HP伤害事件，策略原因对应真实行动。无数值/正式经济改变。旧地面结果与截图留档；当时仍待空中freeze，最终14项与浏览器结果见§8。实验历史不同源码可能扩展表现事件，复现应使用源码SHA，不能把simulation_id当正式持久经济账本键。


## 8. 最终空战独立验收

冻结后`python -m unittest discover -s prototypes/r5-combat/tests -v`：**14/14通过，0.236s，0失败/错误/跳过**（`final-air-suite.txt`）。包括准确metadata/严格HTTP、独立CD伤害算式、60格engine、30格HTTP重复确定性、真实吸收与策略原因；不加总前轮/他岗诊断数。

`python prototypes/r5-combat/tests/browser_lab.py`：**7项检查通过**，仅2次真实`/api/simulate` POST，0 pageerror/console.error/failed request（`final-air-browser.txt`、`air-browser-report.json`）。`browser-report.json`现为同一最终空战报告副本；旧地面结果留在`pre-metadata/`与各round日志，不以其替代新UI。

- 战前实际展开三种战式规则：18MP/CD3、持续40/CD2、爆发120/CD6且t2/t4预热、护持90/CD4、道具占主行动均可读；切换/展开0 POST。
- 实看最新桌面与320截图：云海上双层神识灵印作为修士代身，无原地面站立人形；主副法宝与身份核是独立实体，持续梭、爆发棱与护持盾有不同形状/槽位文字。source/event-id/tick/target均对应当前权威帧，护持吸收为真实secondary→player；实体未混同主体。减少动态效果仍有静态归属/形状，实际播放中无animateMotion，meter transition为0s。
- 不是只查动画DOM：正常速度采样实际飞行替身bounding rect，首拍main真实事件取得13个位置样本，x约643→1128→476；自然末拍main事件另42个位置样本，同样真实向目标出击后回收。末拍完成未取消后续法宝事件。固定原槽保留文字/淡轮廓，同形飞行代理代表实际器物，不让HUD标签随飞行移动。数据在报告`treasure_motion`/`final_treasure_motion`。
- seek/新run/节点回看清旧飞行g、事件属性与高亮，不补历史伤害；倍速/暂停/回放/键盘/跳尾零额外模拟，结果相同。三节点真实22拍胜，Boss显示12拍个人/NPC评分、敌HP仍>0且不假称击杀。减弱动画下爆发、护持与持续静态模式均对应真实事件。

最终新增一次浏览器测试自身可见性修正：中段seek后结果面板已隐藏，测试误点仅结算可见的replay而超时；改为先skip回真实结算再replay。保留`air-browser-round1.txt`及报告，不改应用或删除有效断言。后续同版本完整浏览器7项通过，无开放实验功能阻断。

最新受测SHA（全值见`lab-tested-hashes.json`）：engine `43aa7cdc`、server `0cddbb0c`；index `a3f68bde`、styles `bda71f9f`、app `1e8dfbca`。最终脚本与运行源哈希均在清单，17份正式runtime before/after再次逐字一致。`final-summary.json`汇总实际count与范围。原正式源码/测试/存档未改，181套未重跑。

截图均使用`air-*`新名，不覆盖地面：air-desktop/mobile、air-guard-detail/mobile、air-burst-detail、air-boss-desktop/mobile。自动化数值/动作与真实截图通过不等于真人研究、全部正式战斗兼容或正式发布；正式持久化/旧档/经济联动仍待另行授权实施。PM接下来独立打包/解包验证，本报告不提前声称尚未提供结果的包验收。
