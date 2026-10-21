> 多用户在线化（MU）版契约：本文件已按账号登录、服务端自动同步的新架构更新，权威设计见 `docs/iterations/MU_DESIGN.md`。序章与凡界的行动/投影字段形状沿用原契约（`docs/iterations/WORLD_API.md`、`R3_API.md`、`R4_API.md`、`R5_INTEGRATION.md`），本文只描述认证、同步与通用信封。实现与自动化测试的实测通过情况以 QA 报告为准，本文不代表已验收。

# JSON API 实施契约

UTF-8，同源；前端根据投影渲染，不自算玩法。所有 POST 须 `Content-Type: application/json` 与 `X-Game-Client: guixu-web`；`Origin` 若存在须与 `Host` 匹配（`--secure-cookies` 时额外允许同主机的 `https://`）。请求体上限 16 KiB，字段集严格，未知字段返回 400 `BAD_REQUEST`。

## 身份与安全模型
- 账号身份只来自服务端会话 Cookie：`guixu_session`（`--secure-cookies` 时为 `__Host-guixu_session`），`HttpOnly; SameSite=Lax; Path=/`。请求体、URL、请求头里**没有**任何用户参数；出现 `user_id`/`account_id` 之类字段一律 400。
- 每个账号的进度在数据库中以 `user_id` 行级隔离；不同账号可使用相同 `request_id`，互不影响。
- 会话空闲 7 天、绝对 30 天过期；同账号最多 10 个会话（允许多设备同时登录）。
- 未登录访问需登录的接口：401，响应体不含任何进度数据。

## 端点
| 方法与路径 | 鉴权 | 请求体（严格字段集） | 成功响应 |
| --- | --- | --- | --- |
| GET `/api/health` | 否 | 无 | 200 `{"ok":true,"schema_version":2,"layout_version":1,"registration_open":true}`；只检查库可用，不返回任何账号或进度数据；库不可用 503 |
| GET `/api/session` | 否（Cookie 可选） | 无 | **恒 200** `{"ok":true,"authenticated":false,"registration_open":true}` 或 `{"ok":true,"authenticated":true,"account":{"username":"…"},"registration_open":true}`；会话失效时 `authenticated:false` 并带 `reason`（`SESSION_EXPIRED`）且清除 Cookie |
| POST `/api/register` | 否 | `{"username","password"}` | 200 `{"ok":true,"account":{"username":"…"}}` + `Set-Cookie`（注册即登录） |
| POST `/api/login` | 否 | `{"username","password"}` | 200 `{"ok":true,"account":{"username":"…"}}` + `Set-Cookie` |
| POST `/api/logout` | Cookie（失效亦成功） | `{}` | 200 `{"ok":true}` + 清除 Cookie；幂等 |
| POST `/api/password` | 是 | `{"old_password","new_password"}` | 200 `{"ok":true}`；该账号的其他会话立即失效，当前会话保留 |
| GET `/api/state` | 是 | 无 | 200 成功快照（见下） |
| POST `/api/new-game` | 是 | 写信封 + `name`（凡界另可含 `mode`） | 新局完整快照 |
| POST `/api/action` | 是 | 写信封 + `action`、`params` | 一次行动后的完整快照，自动斗法另带不入库的 `battle_report`（群战时含 `enemy.units`、每帧 `units`、事件 `unit`/`aoe` 与 `fall`/`scatter`，见 `docs/iterations/FB3_SWARM.md`）；无参数时 params 为 {} |

**已删除**：POST `/api/save`、`/api/load` 两个旧端点及其手动操作语义。这两个路径现返回 404 `NOT_FOUND`，响应不含 `save` 字段，`profile.load_policy` 亦已移除；`NO_SAVE`、`INCOMPATIBLE_SAVE` 错误码退役。进度由服务端在每次写操作成功提交后自动同步，没有“手动同步”操作。

### 账号规则
- 用户名：NFKC 规范化、去首尾空白后须匹配 `^[一-鿿A-Za-z0-9_]{3,20}$`；以 `casefold` 后的键判重（`Alice` 与 `alice`、全角字母视为同名）。用户名与 `new-game` 的角色名 `name` 相互独立，角色名可重名。
- 密码：8–64 个字符，不得与用户名相同，不做规范化与截断。服务端以 scrypt 加盐哈希存储，不保存明文密码或明文会话令牌。没有邮箱或手机号，忘记密码只能由运维用 `--reset-password` 重置。
- 登录限流：同一用户名+来源、同一用户名、同一来源分级限次，超限返回 429 `RATE_LIMITED` 与 `Retry-After`；“用户不存在”与“密码错误”返回同一状态码和文案。`--trust-proxy` 时来源取 `X-Forwarded-For` 最右一段，否则取连接地址。注册另按来源限次。

## 写信封
`{"request_id":"客户端唯一字符串","expected_revision":3}`，request_id 限 1–128 个可打印 ASCII 字符，推荐 `crypto.randomUUID()`；revision 为非负整数且不可 bool。request_id 在**账号内**唯一。新局 `name` 建议 1–12 个非空白可显示字符。

## 成功快照（`state`/`new-game`/`action` 同形）
```json
{
  "ok": true,
  "duplicate": false,
  "revision": 4,
  "state": null,
  "view": {"title": "归墟修行手札", "phase": "creation", "character": null, "location": null,
           "objective": "创建角色，开始修行", "resources": [], "battle": null,
           "actions": [], "logs": [], "ending": null},
  "sync": {"persisted": true, "revision": 4, "saved_at": 1760000000, "summary": null},
  "account": {"username": "…"},
  "events": []
}
```
- `sync`：该响应对应的进度已提交到数据库。`persisted` 恒为 true（写失败时不会有成功响应）；`revision` 为已提交版本；`saved_at` 为服务端 UTC 整数秒；`summary` 为中文进度摘要或 null。前端“进度已同步”只依据成功响应及其 `sync`，不得先行宣称。
- `account.username`：当前登录账号的展示名；内部账号 id 永不出现在响应中。
- 原 `save` 字段删除。`state` 为完整权威状态供诊断，前端只消费 `view`/`sync`/`account`。其余 `view`、`actions`、`group` 等形状沿用序章/凡界契约，前端渲染一律使用 textContent。
- 服务端按时间自动累积的结算（序章吐纳、长线修为等）在读取与写入时按该账号自己的状态计算，一个账号的离线不影响其他账号。查看/切页的 GET 只读预览，不写库。

## 幂等、冲突与自动同步
写操作按“事务外读状态并计算 → 事务内乐观校验 revision → 同一事务更新进度并登记 request_id → 提交后才返回成功”处理：
- 同 ID 同载荷（含 expected_revision）：返回当前最新快照且 `duplicate:true`，events 为空，不重复结算、不加 revision。同 ID 不同载荷：409 `REQUEST_ID_REUSED`。
- expected_revision 不等于当前值：409 `STALE_STATE`，附 `revision`。同账号多页面/多设备并发时，先提交者成功，后到者得到 409；服务端不自动重放，前端提示“进度已在其他页面更新，已为你刷新到最新”并重新读取。
- 提交失败：整次回滚，返回 503 `SAVE_FAILED`（用户可见文案“进度保存失败，请稍后重试，当前操作未生效。”），不更新 revision。结果未知（超时、断线、503）时，客户端保留完整载荷，用**同一 request_id** 重试：若实际已提交则得到 `duplicate:true`，不会重复扣费或领奖；禁止生成新 request_id 盲重做。离线期间不排队，重连后由玩家重新操作或重试最后一个未确认请求。
- 前端一次只保留一个待确认写请求；待确认载荷记录所属账号，登录后若与当前账号不一致则丢弃。

## 失败响应
```json
{"ok":false,"error":{"code":"STALE_STATE","message":"进度已在其他页面更新，请刷新后重试。"},"revision":7}
```
可选字段：`error.field`（表单字段名）、`error.retry_after`（秒）。`message` 为中文，前端按 `code` 处理逻辑；异常不返回堆栈；错误不得暗示状态已同步。失败不推进回合或 revision。

| HTTP | code | 含义 |
| --- | --- | --- |
| 400 | `BAD_REQUEST` | JSON/类型/字段集不符、含用户参数 |
| 400 | `INVALID_USERNAME` / `INVALID_PASSWORD`（带 `field`） | 用户名或密码不合规 |
| 400 | `OLD_PASSWORD_INCORRECT` | 改密时旧密码错误 |
| 401 | `AUTH_REQUIRED` | 未携带会话 |
| 401 | `SESSION_EXPIRED` | 会话无效或过期（同时清除 Cookie） |
| 401 | `LOGIN_FAILED` | 用户名或密码不正确（不区分原因） |
| 403 | `FORBIDDEN_ORIGIN` | Host/Origin/X-Game-Client 不符 |
| 403 | `REGISTRATION_CLOSED` | 服务以 `--no-register` 启动 |
| 404 | `NOT_FOUND` | 未知路径（含已删除的 `/api/save`、`/api/load`） |
| 405 | `METHOD_NOT_ALLOWED` | 不支持的请求方式 |
| 409 | `USERNAME_TAKEN` | 用户名已被使用 |
| 409 | `STALE_STATE` / `REQUEST_ID_REUSED` | 版本冲突 / 同 ID 异载荷 |
| 422 | `ACTION_UNAVAILABLE` / `NO_GAME` | 行动不可用 / 尚未开局 |
| 429 | `RATE_LIMITED` | 尝试过多，带 `Retry-After` |
| 503 | `SAVE_FAILED` | 读写进度失败（事务提交失败、状态未改变；错误码保留，用户不可见） |
| 500 | `INTERNAL_ERROR` | 未预期错误 |

## 动作与参数
动作清单、成本、效果与禁用原因均来自后端投影，前端不得猜测机器 ID。区域切换 `action:"travel", params:{"region":"区域ID"}`；序章挑战 `action:"challenge", params:{"enemy":"敌人ID"}`；其余使用投影给定的 id/params。凡界与长线动作、R5 自动斗法见 `docs/iterations/` 对应接口文档。

> 序章吐纳已改为服务端按时间自动结算（`config.QI_SECONDS`=5 秒 +1 修为，补到当前境界瓶颈即止，不囤积离线时间）；`cultivate` 行动已退役（400），视图含 `view.qi={seconds,cap,value,next_in}`，状态可含可选字段 `qi_at`。
