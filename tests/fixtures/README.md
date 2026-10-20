# R4兼容性测试来源

`r4_v1_1_released_save.json` 来自已发布 `guixu-mortal-v1.1.0.zip`，源ZIP SHA256为 `59a2d0321ac5a3be81d884e2351795938cb5b6a37a95e42a07e7791c02c3964a`。生成时在临时目录解压旧源码，由独立Python进程执行fixture内provenance.generator_python：新建长线→完整合法序章→入世→接同道日常→正式妖巢→开战→保存slot→防御一回合。

数据全部为隔离生成的虚构角色/请求；没有读取workspace/data或玩家档。current与slot均包含活动和进行中正式run，battle游标不同。JSON保留原字段值及请求canonical payload，没有手删新字段伪造旧结构；原state/slot/request序列及源DB的SHA256与简要状态在provenance/summary中。

正常测试从此JSON重建临时SQLite，两表与旧版一致，核对原payload哈希后运行升级/备份/幂等/回滚断言。不依赖dist旧ZIP，不发行.db，不跳过兼容测试。若需重新生成，使用记录SHA相同的旧ZIP和记录的generator_python，在临时目录运行；原始SQLite文件字节hash用于来源审计，重建库只保证payload一致，不声称SQLite页头字节相同。
