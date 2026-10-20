# R5 空中斗法实验

独立的自动战斗评估原型：以神识、灵印代身，本命与护持双宝独立飞行，展示出手、蓄势、命中与回护。画面由本地SVG/CSS绘制，不接正式游戏存档，不持久化战斗，不消耗正式道具，也不发修为、物品或排行榜奖励。本实验不代表正式自动战斗已经完成接入。

## 启动与试玩

运行只需Python标准库。在本目录执行：

```sh
python server.py --host 127.0.0.1 --port 8001
```

打开 `http://127.0.0.1:8001`。从完整仓库启动也可使用：

```sh
python prototypes/r5-combat/server.py --host 127.0.0.1 --port 8001
```

`--port 0`可让系统分配隔离测试端口，地址会打印到终端。实验服务与正式游戏8000端口相互独立。

推荐先保持补给预算全0、同行关闭，比较以下组合：

| 场景 | 构筑 | 策略 | 观察重点 |
| --- | --- | --- | --- |
| 毒巢 den | 双持续宝 sustain | 强攻 aggressive | 双宝交替出手与快速终结 |
| 熔炉 forge | 持续与护持 guard | 均衡 balanced | 炉盾破损、重击防御与护持回护 |
| 三战 dungeon | 双爆发宝 burst | 均衡 balanced | 错峰爆发与全程灵力、CD、补给承接 |

三战是毒巢→熔炉→沉星的混合机制连战实验，不是正式v1.2副本：没有战间营地自动恢复，气血、灵力、玩家CD和总预算连续。也可选世界Boss，观察12拍个人有效伤害；不要求击杀其巨大血量。

展开“本战式规则”可查看当前构筑的伤害、CD、启动延迟和补给机会成本。补给预算默认全0；高级预算是本次实验允许使用的虚拟上限，实际用量由策略判断，预算更多不保证战果更好。提交后本场配置冻结，调整表单只影响下一次演算。

## 回放与规则含义

服务器一次算好完整、有界的战斗，客户端只播放已返回的帧。暂停、倍速、拖动、重播和跳过不会推进规则、重复消耗或重新结算。每场最多120个玩家机会，世界Boss最多12个；相同版本和输入得到相同结果及事件ID。

CD的单位是逻辑拍，不是现实秒：t0使用CD3技能，下一次t3可用。每拍一个主行动，再依次处理主宝、副宝、同行与敌方机会；任意一段击杀即停止后续动作。丹药与三符也占唯一主行动，各自CD3。零蓝会回退到合法普攻或防御，不会因技能不足而重复报错。

实验候选玩家攻击100、气血600、灵力60；归元斩200伤害、耗18MP、CD3。双持续宝各40伤害/CD2，起始t0/t1；双爆发宝各120伤害/CD6，起始t2/t4；护持构筑用一枚持续宝配90点屏障/CD4。护盾不叠加，满足重击或低血条件才触发，持续两个敌方机会。所有候选数值与策略来自实验后端，不代表正式版本平衡。

空中轨迹只解释真实事件，不存在法宝互撞抵消机制。展开护盾不等于已经挡下伤害；`shield_absorb`事件只在实际吸收大于0时给出拦截量。`frame.decision_reason`显示本拍真正选中的策略分支。攻击宝的本体伤害与破敌盾分别记录；玩家直接攻击与攻击宝计入个人Boss伤害，同行NPC独立统计、不计个人成绩。

## 检查命令

在本实验目录执行标准库测试：

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```

可选的真实浏览器检查需要Python Playwright包和 `/usr/bin/chromium`。例如Debian/Ubuntu环境可自行安装开发依赖：

```sh
python -m pip install playwright
sudo apt-get update
sudo apt-get install -y chromium
python tests/browser_lab.py
```

浏览器脚本自行启动随机端口的隔离实验服务；游戏运行本身不需要这些开发依赖。其他平台需先调整脚本的Chromium可执行路径。这些是可复现命令，不表示最终空中视觉验收已经通过；当轮实际结果以独立QA报告为准。

## 最小接口

GET `/api/health`、`/api/config`和静态资源不修改状态。POST `/api/simulate`生成本次完整实验结果。没有正式登录、存读档、领取奖励或任意时间推进接口。

```json
{"scenario":"dungeon","build":"burst","strategy":"balanced","pill_budget":0,"fire_budget":0,"guard_budget":0,"soul_budget":0,"npc":false}
```

必需字段为scenario/build/strategy；四项预算缺省0、npc缺省false。scenario为den/forge/tower/boss/dungeon，build为sustain/burst/guard，strategy为balanced/aggressive。pill预算整数0..3，三符各0..2；拒绝bool冒充整数、未知字段、旧talisman_budget/companion别名、任意角色数值或时间注入、重复JSON键和非有限数，请求最多16KiB。

响应包含simulation_id、config_version、规范化input、frames、events、metrics和nodes。初态是frames[0]，后续tick每拍递增，node是1基整数；帧带before/after、双方状态、CD、选技原因与本拍事件。metrics区分直接/法宝/NPC伤害及实际补给用量。`build_details`与`preparation_rules`是战前只读展示元数据。engine.simulate的initial仅供内部受控低蓝fixture，HTTP不暴露。
