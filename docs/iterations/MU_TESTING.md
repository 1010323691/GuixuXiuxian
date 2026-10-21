# MU_TESTING：多用户在线化 QA 报告（第 1 轮）

日期：2026-10-21 · 执行：QA · 环境：Windows 11，Python 3.14.8，Node v24.19.0，仅标准库 unittest。所有测试使用临时目录，未打开真实 `data/`，未改任何源码。

# Test Report

## Summary
- Total Tests: 372（既有 205 + 本轮新增 167） | Passed: 371 | Failed: 1 | Skipped: 0
- 全量命令 `python -m tests.parallel`：45.3 s 墙钟（449 s CPU 串行，16 worker），无跳过。
- Coverage: 未用覆盖率工具度量（仅标准库）。按 AC1–AC21 逐条映射见下表，关键路径（隔离、保存时机、认证、迁移、文案）均有用例；浏览器渲染类 AC 未覆盖。
- Routing: Engineer（1 个源码缺陷：注册失败不限流，违反 PRD A7）

## Failed Tests
- `tests.test_mu_auth.RegistrationFailureThrottleTests.test_a7_repeated_failed_registrations_from_one_source_are_throttled`
  - 用例：同一来源对已存在用户名连续 12 次 `POST /api/register`。
  - 期望（PRD A7“登录和注册必须有失败限流，连续失败 5 次锁定 5 分钟，429”）：前 5 次 409 `USERNAME_TAKEN`，之后出现 429 `RATE_LIMITED`。
  - 实际：12 次全部 409，无任何 429（实测 40 次连续仍全是 409）。
  - 源码位置：`game/auth.py` 的 `AuthService.register`。限流计数 `_count_register` 只在注册成功后累加，失败分支（`_insert_account` 抛 `USERNAME_TAKEN`）不计数、不锁定。
  - 附带影响：`register` 在插入前先执行 scrypt（`self.hasher.hash(password)`），所以同名重复注册每次耗约 75 ms CPU 且不受限，可被当作 CPU 杠杆（受 `hash_concurrency=4` 信号量约束，但不限速）。建议：把注册失败（重名）计入 `login_attempts` 的用户名加来源作用域，5 次后锁定；并在 KDF 前先做一次廉价的 `username_key` 存在性预检（仍保留 UNIQUE 约束兜底）。
  - 严重度：中低（无数据泄露或串号；影响为暴力枚举与资源消耗）。

## Known Issues（第 2 轮结束后仍失败才记入；本轮尚未进入第 2 轮）
- 无。上述缺陷待工程师修复后在第 2 轮回归。

## 观察项（非缺陷，已在代码或实测中确认）
1. HTTP 处理器无套接字超时：`server.Handler.timeout is None`。实测：声明 `Content-Length: 100` 只发送几字节，6 秒后连接仍被服务端挂起等待，线程不释放。公网部署须靠反向代理做慢连接防护（README 已要求 HTTPS 反代，但未提慢连接）。建议在 Handler 设 `timeout`。
2. AC20 措辞“备份逐字节校验”与实现不同：`legacy.backup_verified` 用 SQLite backup API 并逐行比对（`_rows(source) == _rows(target)`），备份文件与原文件字节不同（实测头部计数器不同，大小相同）。已按“逐行一致”断言，并建议把 AC 措辞改为“逐行校验”。
3. 登录锁定有账号级作用域（`login_user_max_failures=20`）：任何来源累计 20 次失败即可把该账号锁 5 分钟，属“锁定换防爆破”的取舍，可被用来骚扰指定账号。未改，仅记录。
4. 现行性能数据与 PRD N3 对比：scrypt 单次约 75 ms，低于 PRD 目标“约 100–300 ms”（见实测数据），如需对齐可把 `kdf_n` 提到 2^16。

## 实测数据（`python -m tests.mu_measure`，本机，真实 fsync，`synchronous=FULL`，WAL）
scrypt 默认参数 `n=2^15, r=8, p=1`：
- 哈希中位 74.5 ms（最小 72.0，最大 77.1），验证中位 74.2 ms（10 次采样）。
- 4 个哈希并行：墙钟约 82–86 ms，单个最大约 85 ms（多核并行，无明显排队）。

写事务耗时（`new-game` 后 400 次 `action`，单写者；及 4 账号各 100 次并发）：

| 场景 | 测量对象 | p50 | p95 | p99 | max |
|---|---|---|---|---|---|
| 单写者，系统临时目录(C:) | `Store.write()` 整次调用 | 26.7 ms | 29.7 ms | 30.9 ms | 33.1 ms |
| 同上 | 写事务窗口（BEGIN IMMEDIATE 到 COMMIT） | 17.3 ms | 18.7 ms | 21.0 ms | 22.9 ms |
| 4 账号并发(C:) | `write()` | 46.1 ms | 90.6 ms | 122.7 ms | 203.7 ms |
| 同上 | 写事务窗口 | 22.2 ms | 63.2 ms | 103.2 ms | 193.0 ms |
| 单写者，项目所在盘(D:) | `write()` | 21.1 ms | 24.3 ms | 25.1 ms | 27.0 ms |
| 同上 | 写事务窗口 | 13.9 ms | 16.1 ms | 17.2 ms | 18.1 ms |
| 4 账号并发(D:) | `write()` | 41.2 ms | 101.1 ms | 284.0 ms | 372.6 ms |
| 同上 | 写事务窗口 | 19.5 ms | 67.3 ms | 169.8 ms | 327.8 ms |

吞吐约 73–75 次写/秒（4 账号并发）。PRD N3 要求 50 并发账号 p95 < 300 ms；本机 4 并发 p95 约 90–101 ms，满足趋势，但 50 账号并发未测（见未运行项）。单次采样受磁盘与杀软影响，D: 盘 4 并发 p99 出现 284 ms 的长尾。

## AC → 用例映射

| AC | 主要用例（文件::类/方法） | 结果 |
|---|---|---|
| AC1 未登录 401 且无进度数据 | test_mu_isolation::IsolationTests.test_ac1_* ；test_mu_isolation::IsolationTests.test_unauthenticated_write_does_not_create_progress | 通过 |
| AC2 注册、登录、重名（含大小写、NFKC） | test_mu_auth::RegistrationTests.test_ac2_*、test_nfkc_*、test_username_and_password_validation | 通过 |
| AC3 无明文密码和令牌、盐不同 | test_mu_auth::PasswordStorageTests（4 项），CookieAttributeTests | 通过 |
| AC4 登出后 401、过期 SESSION_EXPIRED（后端部分） | test_mu_isolation::SessionTamperTests.test_logout_*；test_mu_auth::SessionLifetimeTests（空闲 7 天滑动、绝对 30 天、expires_at 调到过去） | 通过；前端登录面板需浏览器，未运行 |
| AC5 锁定 429、不泄露用户存在 | test_mu_auth::LoginRateLimitTests（5 次后 429 含 Retry-After、5 分钟后恢复、未知用户与错误密码一致）、ConcurrentAccountTests | 通过 |
| AC5/A7 注册失败限流 | test_mu_auth::RegistrationFailureThrottleTests | 失败（缺陷） |
| AC6 改密 | test_mu_auth::ChangeAndResetPasswordTests；test_mu_isolation::SessionTamperTests.test_password_change_revokes_other_sessions_but_keeps_current | 通过 |
| AC7 状态、revision、日志互相独立 | test_mu_isolation::IsolationTests.test_ac7_*；TimeSettlementTests | 通过 |
| AC8 同 request_id 各自独立 | test_mu_isolation::IsolationTests.test_ac8_* | 通过 |
| AC9 夹带 user_id 等被拒、无可选他人 ID 的参数 | test_mu_isolation::IsolationTests.test_ac9_*；SessionTamperTests（篡改、他人、畸形 Cookie） | 通过 |
| AC10 两账号各 100 个并发动作 | test_mu_autosave::ConcurrencyTests.test_ac10_*；同账号竞争 test_b1_*、幂等 test_b2_*（多 App 实例） | 通过 |
| AC11 时间结算按账号 | test_mu_isolation::TimeSettlementTests | 通过 |
| AC12 响应返回前已落库 | test_mu_autosave::SaveTimingTests.test_ac12_*（另开连接直读） | 通过 |
| AC13 提交前后故障 | test_mu_autosave::FaultInjectionTests；ProcessKillTests（子进程在 COMMIT 边界 `os._exit`）；LiveHttp 的 ProcessRestartTests（真实 `server.py` 进程硬杀后重启） | 通过 |
| AC14 断线重放 | test_mu_autosave::SaveTimingTests.test_ac14_*；FaultInjectionTests lost-ack；test_mu_migration 中迁移后旧 request_id 仍幂等 | 通过 |
| AC15 前端不调用 save/load，两路径 404 | test_mu_frontend::NetworkContractTests；test_mu_auth::RequestGuardTests.test_save_and_load_are_retired | 通过（网络日志需浏览器，未运行） |
| AC16 同步状态三态 | 静态：test_terminology::StaticFileTermsTests.test_ui_has_sync_status_element_and_service_wording（含 #save-status 与五种文案）；服务端 503 文案：FaultInjectionTests | 静态通过；浏览器观察未运行 |
| AC17 静态术语扫描 | test_terminology（HTML 文本与属性、JS/CSS 去注释、game/*.py 与 server.py 与 launch.py 的 AST 字符串、启动脚本、现行文档） | 通过 |
| AC18 运行时抽检 | test_terminology::RuntimeTermsTests（各类错误路径 message、自由与长线两种玩法的 state/view/events/logs、序章通关全路线文本、CLI 帮助与输出、launcher --help） | 通过；浏览器可见文本抓取未运行 |
| AC19 全量通过、无跳过 | `python -m tests.parallel`：372 项，跳过 0，1 项失败（见上） | 失败 1 项 |
| AC20 迁移、备份、新号读不到、认领一致 | test_mu_migration::MigrationDrillTests、FixtureUpgradeTests（真实 v1.1 样本，注入时钟）| 通过 |
| AC21 迁移中途失败原库不变且拒绝启动 | test_mu_migration::MigrationDrillTests.test_ac21_*、StartupGuardTests | 通过 |
| 设计 B-1、B-2 | test_mu_autosave::ConcurrencyTests | 通过 |
| 设计 B-3 SQL 隔离扫描 | test_mu_isolation::SqlIsolationScanTests（AST 静态 + sqlite trace 动态 + `ProgressRepo._exec` 兜底） | 通过 |
| 设计 B-4 短事务 | test_mu_autosave::ShortTransactionTests（规则不在写事务内、事务内语句集合最小、A 账号规则慢 0.8 s 不阻塞 B） | 通过 |
| 设计 B-5 WAL 与耐久 | test_mu_autosave::PragmaTests、BackupWalTests | 通过 |
| 设计 B-6 库布局与迁移 | test_mu_migration::StartupGuardTests（旧库、损坏、空文件、未来版本、未知进度版本均保留原件） | 通过 |

## 新增与修改文件（均在 tests/ 下，另有本报告）
- `tests/test_mu_isolation.py`（31 项）：隔离、会话篡改、SQL 隔离扫描、按账号时间结算、损坏行隔离。
- `tests/test_mu_autosave.py`（30 项）：保存时机、PRAGMA、故障注入、进程硬杀、并发、短事务、请求校验、备份。
- `tests/test_mu_auth.py`（44 项）：scrypt、存储形态、Cookie 属性、会话寿命、锁定、注册规则、改密与运维重置、Host/Origin/CSRF、日志不含秘密、并发注册。
- `tests/test_mu_migration.py`（24 项）：迁移演练、认领、CLI 退出码与文案、真实 HTTP 端到端、真实 `server.py` 进程硬杀重启。
- `tests/test_mu_frontend.py`（15 项）：`node --check`、id 契约、端点契约、存储与口令、资源同源与 CSP 兼容。
- `tests/test_terminology.py`（23 项）：术语门禁（含一个带自测的 JS 去注释扫描器）。
- `tests/mu_support.py`：共用辅助。`tests/mu_measure.py`：手动实测脚本（非 unittest）。

术语白名单（`test_terminology.py` 文档头注释逐项列出）：代码注释与 docstring、`docs/history`、`docs/iterations`、`docs/studio`、`docs/ARCHITECTURE.md`、`docs/DELIVERY.md`、`docs/TESTING.md`、`docs/GDD.md`、`artifacts`、`prototypes`、`AGENTS.md`（规则本身引用禁用词）、`tests`。现行文档（README、API、PLAYING、R3_PLAYING、R4_PLAYING、UI）只禁 PRD 4.6 核心词，允许“没有手动保存”这类否定表述。

## 未运行项与限制（如实记录）
- Playwright 浏览器套件（`tests/browser_smoke.py`、`browser_world.py`、`browser_r3.py`、`browser_r4.py`）：未运行，本机 `import playwright` 失败。AC4 前端登录面板、AC15 网络日志、AC16 三态观察、AC18 浏览器可见文本、10 视口一屏巡检均因此未验证。
- Edge headless：本机有 Edge 155，但 `--dump-dom` 与 `--screenshot` 调用立即返回且无输出、无截图（疑为环境限制），未能做未登录页冒烟，已放弃，不计入通过。
- HTTPS 反向代理下 `--secure-cookies` 与 `--trust-proxy` 的真实表现：未运行；只在白盒层验证了 `__Host-` 前缀、Secure 属性、https Origin 放行和 X-Forwarded-For 取最右段。
- 50 账号并发 p95（PRD N3）：未测，只测了 4 账号并发。
- 真实旧库演练：未对真实 `data/game.db` 操作（任务禁止）；用 v1.1 官方样本和合成 schema2 库代替。schema1 库的 `--migrate-save` 确认路径沿用既有 `tests/test_migration.py`，本轮未重复。
- 覆盖率未度量；长时间浸泡、磁盘满、真实断电未测（只做了 `os._exit` 进程硬杀和提交点故障注入）。

## 第 2 轮待办（工程师修复后）
1. 重跑 `test_a7_repeated_failed_registrations_from_one_source_are_throttled`，并确认 `python -m tests.parallel` 全绿、通过数不低于 372。
2. 若工程师同时处理观察项 1（Handler 超时），QA 补一个用例；本轮未作为缺陷计入。

Routing: Engineer


---

# 第 2 轮（最后一轮）

日期：2026-10-21。范围：回归第 1 轮缺陷（A7 注册失败无节流）的工程师修复，并独立复核。只改 `tests/` 与本文件，未改源码，未碰真实 `data/`。

## 结果（均为本轮实测）
| 运行 | 结果 |
|---|---|
| `python -m unittest tests.test_mu_auth` | 44 项 OK（4.9 s），含 `test_a7_repeated_failed_registrations_from_one_source_are_throttled` |
| `python -m tests.parallel` 全量 #1 | 372 项，45.2 s 墙钟（448.8 s CPU 串行，16 worker），跳过 0，OK |
| `python -m tests.parallel` 全量 #2 | 372 项，44.4 s 墙钟（456.4 s CPU 串行），跳过 0，OK |
| 新增 `tests/test_mu_register_throttle.py` 单跑 | 10 项 OK（0.6 s） |
| `python -m tests.parallel` 全量 #3（含新文件） | 382 项，50.6 s 墙钟（449.2 s CPU 串行），跳过 0，OK |

第 1 轮的唯一失败项（AC19 全量 1 项失败）已消除。

## 独立复核修复（新增 `tests/test_mu_register_throttle.py`，10 项，用 `register_fail_max_failures=4` 的小阈值）
- 409 契约：未达阈值时仍为 409，body 的 `code=USERNAME_TAKEN`、`field=username`、`message=该用户名已被使用。` 与修复前一致；达阈值后第 N+1 次为 429 `RATE_LIMITED`。
- 成功注册与 login 不受影响：阈值内失败后换名可注册成功并可登录；校验类 400 错误不计入失败；被锁来源仍可登录。
- 被锁来源不做 scrypt：对 `hasher.hash` 做 spy，锁定后（含空闲用户名）调用 0 次；未锁来源调用 1 次。
- 不同来源 IP 互不影响；锁过期（`lockout_seconds` 后）恢复注册；失败窗口（`failure_window_seconds`）外的旧失败不累计。
- 生产默认值断言为 10（`Settings()`），并显式标注与 PRD 的偏差。

## 与 PRD 的偏差及评估（供主理人决定）
- PRD A7 原文“连续 5 次失败 -> 429”；实现为默认 10，可通过 `Settings.register_fail_max_failures` 配置。原因：既有并发注册同名用例需要在不触发锁的情况下容纳多次 409。
- 评估：AC 意图是“防止对注册接口做无限次用户名枚举/暴力尝试，且不绕过节流”。阈值 10 仍满足：每个来源每 900 s 窗口内最多 10 次失败后锁 300 s，枚举速率上限约 40 次/小时/来源（另受 `register_per_ip_hour=10` 成功注册限额约束），与登录 5 次相比只放宽 2 倍。结论：建议接受 10（记为已批准偏差）；若主理人坚持 5，需同时改并发用例使其不依赖 409 次数，QA 不建议在本轮再动。
- 已知局限：节流按来源 IP 计，未启用 `--trust-proxy` 且处于反代之后时所有用户共享一个来源，会互相锁定（与登录 IP 级节流同类问题）。

## 本轮已通过 / 未运行 汇总
已通过（白盒，本轮实测）：全部 382 项，含 AC1-AC3、AC5-AC14、AC17-AC21 的白盒覆盖、A7 注册节流、设计 B-1 至 B-6。

未运行或未验证（不计为通过）：
- Playwright 浏览器套件（browser_smoke / world / r3 / r4）：本机无 playwright，未运行；AC4 前端登录面板、AC15 网络日志、AC16 同步状态三态浏览器观察、AC18 浏览器可见文本为“静态通过 / 浏览器未验证”。
- 10 视口一屏巡检：未运行（依赖浏览器）。
- HTTPS 反向代理下 `--secure-cookies` / `--trust-proxy` 真实表现：未运行，仅白盒验证。
- 50 账号并发 p95（PRD N3）：未测，仅测 4 账号并发。
- 真实旧库演练（`--migrate-multiuser` / `--claim-legacy` 对真实 `data/game.db`）：未运行（禁止触碰真实数据），以官方样本与合成库代替。
- 覆盖率、浸泡、磁盘满、真实断电：未测。

## Known Issues（不再开第 3 轮）
1. 慢连接 / 慢速请求的 `Handler.timeout`：第 1 轮观察项，未修复也未补用例，存在慢连接占用线程风险。
2. 备份“逐字节一致”表述：备份为 WAL 在线备份，逻辑一致而非逐字节一致，文档措辞应改为“一致性备份”。
3. 账号级锁可被骚扰：攻击者可对已知用户名持续输错口令使其被锁（`user` 20 次 / `user_ip` 5 次），属节流设计取舍，未缓解。
4. 注册失败阈值 10 与 PRD 的 5 偏差（见上，建议接受）。
5. 反代后未配 `--trust-proxy` 时来源 IP 共享，节流会误伤（见上）。
6. 上述“未运行”各项（浏览器套件、10 视口巡检、HTTPS 反代、50 账号并发、真实旧库演练）。

Routing: NoOne (Known Issues)
