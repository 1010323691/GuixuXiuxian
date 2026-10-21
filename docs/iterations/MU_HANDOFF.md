# MU 多用户在线化：交接报告（来自分叉会话「一个用户一个数据库？这太浪费了吧」）

时间：2026-10-21 01:0x。本分叉会话已停用，其子代理已全部停止。以下供主会话 `local_caba65ce-df17-45ed-9e76-9a12d8e75f87` 接手。

## 1. 用户决策（最新，覆盖设计文档中的方案 A）
- **隔离方案由 A（每用户独立 SQLite）改为 B：单库 `data/game.db` + `user_id` + WAL。**
- 理由：用户认为每用户一个库浪费。已向用户说明：磁盘浪费可忽略（单库约 80KB），真正代价是文件数和运维；B 的前提是缩短写事务。
- 其余 PRD 默认值不变：删除手动存档/载入；开放注册（可 `--no-register` 关闭）；旧库进待认领区，`--claim-legacy 用户名` 认领，严禁首位注册者自动继承；运维 CLI 重置密码；允许多设备；中文用户名（NFKC）；角色名与用户名分离；仅标准库；不引入 FastAPI 等第三方包。
- 接受架构师新增：`/api/session`（恒 200）、注册即登录。错误码 `SAVE_FAILED` 保留（用户不可见）。

## 2. 已完成、不需重做
- `docs/iterations/MU_PRD.md`（21 条 AC，PM 产出）。
- **T03 文案服务化**：`game/__init__.py, rules.py, world.py, loot.py, activities.py, world_config.py`，仅改字符串，工程师报 IS_PASS: YES，未跑测试。tests/ 无断言命中被改文案。

## 3. 需要按 B 重做或修订
- `docs/iterations/MU_DESIGN.md`、`MU_sequence.mermaid`、`MU_class.mermaid`：**仍是方案 A**（MU_DESIGN 2.1 节标题仍为「A（每用户独立 SQLite 文件）」，最后修改 00:56）。B 的修订任务因代理被停止而**未落盘**。
- 需新增的 B 设计要点（给架构师）：
  1. 进度表 `current` 以 `user_id` 为主键；`requests` 主键 `(user_id, request_id)`；唯一数据访问层，禁止裸 SQL，确保不漏写 `WHERE user_id`。
  2. WAL + `busy_timeout`；`synchronous=FULL`（严格满足提交成功后断电不丢）。
  3. **缩短写事务**：当前 `Store.write` 在 `BEGIN IMMEDIATE` 内执行 `rules.apply_action/growth/cadence`。改为：事务外读状态与 revision → 事务外计算 → `BEGIN IMMEDIATE` 后按 expected revision 乐观校验 → 只做 UPDATE + 账本 INSERT → COMMIT。须保证同 `request_id` 并发幂等、同一用户并发不丢更新，正确性不能只依赖进程内锁。
  4. 迁移：旧 `data/game.db`（schema2 单行，表 `{current,requests}`）→ 新单库；先 `sqlite3.backup` 校验备份，可续跑；旧数据进待认领区；与 schema1 的 `--migrate-save` 路径共存需说明；单库备份命令 `--backup`。
  5. 删除 StoreRegistry / LRU / 用户目录相关设计。

## 4. 工作区里的 A 方案半成品（未提交，需按 B 处置）
| 文件 | 状态 | 建议 |
|---|---|---|
| `game/userstore.py`（新） | A 专用 | **删除** |
| `game/storage.py`、`game/growth.py`（已改） | T01 中途，含 A 假设（owner_id/user_version/Registry/退役 save-load） | 以 B 设计重构，先读现状；`growth.load_checkpoint` 的移除可保留 |
| `game/legacy.py`、`game/settings.py`、`game/auth.py`、`game/admin.py`（新） | 原会话子代理在 00:58–01:02 写入，T01/T02 进行中 | 逐个审：认证、会话、scrypt、限流、CLI 与存储无关部分可能可复用；凡引用 `StoreRegistry`/用户目录的需改 |
| `server.py`（已改） | 原会话 T02 中途 | 同上，核对是否依赖 Registry |
- 注意：这些文件由原会话的子代理在写，**主会话需先确认其子代理已全部停止**，再动手，以免与 B 重写互相覆盖。

## 5. 任务列表（建议，不超过 5 个、文件归属不重叠）
- T01 存储与迁移（B 版，重做）：`storage.py, legacy.py, growth.py`，删 `userstore.py`。
- T02 认证与服务入口：`settings.py, auth.py, admin.py, server.py, scripts/launch.py`；依赖 T01。
- T03 文案：**已完成**。
- T04 前端：`static/*`；依赖 T02。
- T05 测试/脚本/文档：`tests/*, scripts/*, docs/*, AGENTS.md`；依赖 T01–T04。

## 6. 已知环境问题（重要）
- 子代理默认模型 `deepseek/deepseek-v4.1-flash` 不可用（404 model_not_found）。**派工必须显式 `model: "sonnet"`**；`SendMessage` 续接子代理会回落到默认模型而失败，应改为新起子代理并把已有产出路径作为输入。
- 未运行任何测试（白盒 `python -m tests.parallel`、浏览器套件均未跑）。浏览器套件依赖 Playwright，本机未必可用，须如实记录“未运行”。
- `AGENTS.md`、`docs/API.md` 等中的“单机/保存载入/--migrate-save/手动 slot”表述需在 T05 同步。
- scrypt 参数在目标机上的耗时需 QA 实测一次。
- 工作区另有他人未提交改动（V4 设计系统、序章吐纳修为等），不可回滚。

## 7. 下一步
1. 主会话确认其子代理已停；
2. 派架构师（`model: sonnet`）按第 3 节改 MU_DESIGN 与两个 mermaid；
3. 依次 T01 → T02 → T04 → T05（QA 两轮上限，覆盖多账号隔离、保存时机、文案一致性扫描）；
4. 最终交付汇报，并列出对用户的待确认项（见 PRD 第 10 节默认值）。
