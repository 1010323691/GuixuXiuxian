> 序章历史文档：本文件保留原v0.1.0范围与证据；完整凡界的当前契约和验收见 `docs/iterations/`，不能用本文件代替W1结论。

# JSON API 实施契约

状态：按项目经理裁决冻结协议形状，具体规则以 GDD 为准。UTF-8，同源；前端根据投影渲染，不读取磁盘存档或自算玩法。所有写入 `Content-Type: application/json` 和 `X-Game-Client: guixu-web`。

## 端点
| 方法与路径 | 请求 | 响应 |
| --- | --- | --- |
| GET `/api/health` | 无 | 存储可用时200 `{"ok":true,"schema_version":1}`，否则503 |
| GET `/api/state` | 无 | 200成功快照 |
| POST `/api/new-game` | 写信封 + `name` | 新局完整快照；参数合法值由GDD/config定义 |
| POST `/api/action` | 写信封 + `action`、`params` | 一次行动后的完整快照；无参数时params为{} |
| POST `/api/save` | 写信封 | 当前state写入单手动档，未开局时422 |
| POST `/api/load` | 写信封 | 从手动档恢复state，空档422 |

写信封为 `{"request_id":"客户端唯一字符串","expected_revision":3}`，request_id限1–128可打印ASCII字符，推荐crypto.randomUUID()。revision为非负整数且不可bool。新局 `name` 建议1–12个非空白可显示字符，最终范围由GDD确认。不提供出身/禀赋选择。

## 成功快照（所有成功状态端点同形）
```json
{
  "ok": true,
  "duplicate": false,
  "revision": 4,
  "state": null,
  "view": {
    "title": "归墟修行手札",
    "phase": "creation",
    "character": null,
    "location": null,
    "objective": "创建角色，开始修行",
    "resources": [],
    "battle": null,
    "actions": [],
    "logs": [],
    "ending": null
  },
  "save": {"exists":false,"summary":null},
  "events": []
}
```

`state` 为完整权威游戏状态供诊断/测试，前端只消费view/save。原始state字段为name、realm、cultivation、hp、mp、stones、herbs、pills、technique、region、victories、battle、completed、actions_taken、logs，具体含义和数值服从GDD；不得据此让UI自行推算展示。events为本次请求产生的字符串数组，GET为空；logs为按旧到新顺序的最近至多100条字符串。没有新事件时events为空，前端不得重复追加整个历史。

view必有上述键；phase为 `creation|exploration|battle|ending`，由服务端判断。character为null或 `{"name":"…","realm":"炼气一层"}`。location为null或 `{"id":"village","name":"…","description":"…"}`。objective为中文字符串。resources为 `{id,label,value,max}` 数组，value为整数，max可null（无上限显示）；资源顺序由后端决定。battle为null或 `{name,hp,max_hp,intent}`，intent是完整中文预告。ending为null或 `{title,text}`，text是字符串。

actions是当前页所有相关行动（含不可用项），每项：
```json
{"id":"cultivate","label":"吐纳修炼","detail":"…","cost":"免费","effect":"修为 +…","enabled":true,"reason":"","params":{},"primary":true}
```
detail为完整中文行动说明，cost/effect是可直接显示的中文成本/收益文本。id是POST action值，params原样提交；不同目标行动必须有不同id或params，以方便稳定渲染。disabled项reason必须有中文原因；enabled不替代后端执行时校验。primary最多一项。新局/存档/载入为独立全局入口，不放actions。save.summary为null或中文摘要字符串。前端渲染所有内容使用textContent，不将玩家姓名或日志拼成HTML。

action可附可选字符串 `group` 用于纯展示分组，当前有 `cultivation|exploration|trade|travel|battle`；客户端未知组使用通用分组，不能据此决定行动规则或可用性，不随POST提交。

## 幂等与冲突
写操作锁内先查request_id再检查revision。将端点与规范化请求JSON（含expected_revision）作为载荷比较依据；同ID同载荷返回当前最新快照及duplicate:true，events为空，不重新结算或加revision；同ID不同载荷409 `REQUEST_ID_REUSED`。所有成功响应有duplicate布尔值。前端仍应禁止用低于已渲染revision的响应覆盖视图；duplicate:true时提示“该操作已处理，已同步最新进度”。

expected_revision不等于当前revision返回409 `STALE_STATE`，附 `revision`（当前值）；前端刷新快照，向玩家解释另一个页面改变进度，不自动重放。只有成功写操作存储去重结果；校验失败后玩家的新意图使用新ID。前端一次只保留一个pending写请求；网络失败保留完整载荷、同ID重试入口，禁止生成新ID盲重做。新局/载入也使用同一机制；载入不回退全局revision或去重记录；新局清空手动slot，载入保持slot。

## 失败响应
```json
{"ok":false,"error":{"code":"STALE_STATE","message":"进度已在其他页面更新，请刷新后重试。"},"revision":7}
```
400 `BAD_REQUEST`（JSON/类型/字段）；403 `FORBIDDEN_ORIGIN`；404 `NOT_FOUND`；409 `STALE_STATE`/`REQUEST_ID_REUSED`；422 `ACTION_UNAVAILABLE`/`NO_GAME`/`NO_SAVE`；503 `SAVE_FAILED`（事务提交失败、状态未改变）；500 `INTERNAL_ERROR`。服务端message中文、前端只按code处理逻辑；异常不返回堆栈。错误不得暗示状态已保存。失败不推进回合或revision。

## 待GDD补充且不得前端猜测
action/资源ID、各行动参数、战斗与结局条件、初始数值。工程实施只依赖本协议形状；动作清单和中文预览必须来自后端投影。

## 已确定行动参数
区域切换 `action:"travel", params:{"region":"区域ID"}`；挑战 `action:"challenge", params:{"enemy":"敌人ID"}`。其余行动使用后端投影给定的id/params。travel免费、不增加actions_taken，但作为成功写入仍递增revision并持久化。UI不得从按钮文案推断机器ID。
