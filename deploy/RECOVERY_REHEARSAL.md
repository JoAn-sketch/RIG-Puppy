# 本地恢复演练结果

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
