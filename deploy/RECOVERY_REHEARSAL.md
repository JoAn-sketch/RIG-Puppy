# 本地恢复演练结果

## 实际保留/回退模块 Docker 集成验证：通过

执行 `python3 deploy/rehearse_modules.py`，实例前缀 `puppy-modules-4c08df1164-`。本次直接调用 adoption.retain / adoption.rollback，验证旧容器 ID、名称、restart 策略、共享网络全部恢复；新版本保留为停止状态且 restart=no。六个测试容器最后全部停止、禁用重启并保留。

日志保存在本地 `puppy-module-report-zikb798_` 临时目录；日志采用 0600 文件和 pending/complete 步骤。本测试仅通过名称前缀适配隔离测试实例，不使用生产目录、环境变量、挂载或端口。

已完成实际模块的 Docker 生命周期验收，仍未完成真实业务配置和生产挂载的恢复验收。不能据此启用生产部署。

## 回退模块实现

adoption.rollback 已实现按记录的原容器 ID 恢复：先核对全部旧 ID、失败版本 ID、名称占用、旧共享网络、重启策略；任何不符在修改前停止。失败版本禁用 restart、停止并改名保留；旧主服务先恢复名称/策略并启动，随后恢复语音服务。每条命令先写 pending 日志，完成后写 complete；中断后要求检查，禁止盲目重放。

18 个修改位置分别注入失败，均立即停止并保留 pending 记录。此实现未用于生产，尚未用真实 Docker 运行该具体模块（上方/下方的 Docker 演练为独立机制验证）。返回 containers_restored_health_not_verified 不代表应用健康。当前命令行仍只读，未暴露生产执行入口。

## Compose 首次纳管机制追加演练

`rehearse_adoption.py` 在本地测试项目 `puppy-adoption-25745262` 验证通过：旧三容器停止并改名，新版本使用不同 Compose 项目身份，旧 ID 全部保留；模拟失败后停止并保留新版本，恢复旧容器名称并启动，旧 ID 和共享网络 ID 完全一致。最后所有测试容器停止。

此方法不切换代码目录，但改变 Compose 项目名。实际使用前须显式保留生产网络归属和 DNS 别名，核对 Web/数据库/Redis 的连接，不能直接使用新项目默认网络。生产配置模板尚未变更，强制部署保护仍开启。

测试只模拟三容器生命周期，不代表真实三服务功能通过。没有使用生产卷、环境变量、端口或密钥。旧容器的 restart 策略在真实备份期间也需要记录并临时禁用，以免宿主机重启时抢占端口；恢复时还原原策略。

使用已构建的 puppy-build-check:local（linux/amd64），在本地 Colima 执行 deploy/rehearse_recovery.py。

结果：通过。测试实例前缀：`puppy-rehearsal-53c6c6c57b`。

## 已实测

1. 创建三个无外网、无生产挂载、无宿主机端口的模拟容器；两个模拟语音容器共享模拟主容器网络。
2. 写入可写层标记，按依赖顺序停止旧容器，为三个容器分别创建快照，保留旧容器。
3. 创建新版本三容器，模拟发布失败并停止新版本，保留失败现场。
4. 从三个快照恢复三个容器，核对可写层标记仍为 old-state。
5. 核对两个恢复语音容器的 NetworkMode 均精确引用恢复主容器 ID。
6. 演练结束，所有测试容器停止；九个测试容器和三个快照保留在本地，不删除用户镜像。

## 不能据此宣称的结果

- 不是实际 FunASR/Kokoro 语音处理或模型加载测试。
- 没有验证数据库一致性、生产 bind mounts、真实启动参数、业务环境变量或生产流量恢复。
- docker commit 不包含卷和 bind mount 数据，也不是数据库备份。
- 没有演练 Compose 项目标签匹配、旧生产容器保留及首次纳管。仅改名生产容器仍不安全。
- 生产备份可能包含密钥，只能保存于服务器权限受限的位置，禁止 push/export 到 GitHub。

## 使用

```bash
python3 deploy/rehearse_recovery.py --report /private/tmp/puppy-recovery-rehearsal.json
```

工具仅接受本地 colima context，拒绝 DOCKER_HOST 覆盖；不接受生产容器名、生产挂载或生产端口参数。测试产物保留，不执行 prune。

## 生产入口状态

`RECOVERY_IMPLEMENTATION_VERIFIED=False` 和 `enabled=false` 保持。下一项验收是用完整生产等价配置在隔离环境验证恢复，再实现能够保留旧生产容器且避免 Compose 标签误匹配的首次纳管路径。不能用 JSON 开关代替这个验收。
