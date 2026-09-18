# 三容器协调更新方案（尚未启用）

## 核实的约束

FunASR 和 Kokoro 均使用 `network_mode=container:<主服务ID>`。主服务重建会产生新 ID，已有语音容器不会自动迁移。FunASR 模型仍保留在 `/home/ubuntu/funasr-runtime-resources/models`；主服务 data、SenseVoiceSmall 的路径不变。

FunASR 镜像为 `registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:funasr-runtime-sdk-online-cpu-0.1.12`，restart 为 unless-stopped；Kokoro 为 `ghcr.io/remsky/kokoro-fastapi-cpu:v0.2.4`，同样 unless-stopped。Kokoro 以 appuser 在 /app 启动 ./entrypoint.sh。不得只凭镜像名重建：还需核实环境覆盖、镜像摘要、可写层的模型等内容。

## 选定方向

### 已核实的生产网络及备份策略

主服务、Web、MySQL、Redis 都在 `xiaozhi-server_default`。新增 `compose.network.yml` 显式复用该 external 网络，保留主服务 DNS 别名；候选新项目不管理 Web、数据库、Redis，也不创建/删除它们的网络。容器 IP 可能变化，尚需排除业务对旧 IP 的硬编码依赖。

主服务 restart 为 always，两个语音服务为 unless-stopped。未来备份前应持久保存完整 inspect（权限 0600），禁用旧三容器 restart，再停止和改名；每一步记录原值和结果。失败或回退时恢复原策略。不可只改名后留下 always 策略，避免宿主机重启时旧容器抢占端口。

新增 migration_checks.py 只读验证实际网络/别名/重启策略，任何漂移停止。它不是迁移执行器，不会停止或更新生产资源。

追加实测：不同 Compose 项目身份能够规避旧容器标签匹配，并完整恢复旧 ID/共享网络。详见 RECOVERY_REHEARSAL.md。候选首次纳管应采用明确的新项目身份，同时显式复用已核实的生产网络；当前模板仍使用原项目，不能据此执行纳管。需要核实跨服务网络和备份 restart 策略后才能实现生产步骤。

保持现有 localhost 通信语义，不修改业务配置。将语音服务纳入同一 Compose 项目，并配置 `network_mode: service:xiaozhi-esp32-server`。初次纳管必须在单独授权的维护窗口执行；当前脚本继续阻止共享网络下的单服务更新。

不要把 `depends_on` 当成自动迁移保证。每次主服务 ID 改变，两个语音容器必须明确重建并验证 NetworkMode 引用新的主服务 ID。

## 首次纳管步骤

1. 完成默认配置审查、镜像构建验证及三个服务的完整启动参数核对。将非秘密配置通过 Git 提交；秘密使用既有安全配置，不复制入仓库。
2. 在停止任何容器前，保存三者的 inspect（权限 0600、仓库外）、镜像 ID、可写层差异、挂载及已验证恢复命令。语音镜像固定到核实摘要。Kokoro 无挂载，必须确认下载模型是否位于可写层，不能假设新建容器会保留。
3. 获取部署锁、检查工作树、锁定 Git SHA、构建主服务镜像；失败不操作线上容器。
4. **不能仅重命名旧容器然后 compose up**：旧主容器保留 Compose 项目/服务标签，Compose 仍可能找到并删除重建它。首次纳管必须先完成独立恢复快照及恢复容器验证，并明确选择不删除旧环境的切换实现；在实现通过隔离演练前，禁止执行停机/改名/纳管操作。
5. 上述保留方案验证完成后，才可按固定生产目录启动新主服务，再启动明确引用它的两个语音服务。恢复流程必须验证旧网络引用，不能只恢复容器名称。
6. 验证新主镜像/commit、三容器健康、语音 NetworkMode、主网络内 10095 TCP 及 8880 HTTP、主服务 HTTP。TCP 检查不代表 FunASR 识别质量通过，仍需语音端到端验证。
7. 失败时不删除旧环境、不自动清理；根据已验证恢复命令，停止新容器并释放名称，再恢复旧名称，按旧主服务→旧语音顺序启动。恢复操作必须另外授权或在维护窗口授权中明确包含。

## 后续常规部署

在首次纳管完成且恢复演练通过后，脚本才可允许协调更新：build 成功→停止语音服务→更新主服务→强制重建两语音服务→有限等待和健康检查。整个流程存在服务中断窗口，不能声称零停机。

## 当前不能启用的条件

- 未完成默认 config.yaml 的安全模板与现有配置覆盖关系审查。
- 未保存完整环境差异和可写层模型状态，未生成经过演练的恢复命令。
- 未完成隔离构建和协调更新演练。

本文件是可评审方案，不是允许执行生产操作的脚本。`enabled=false` 和现有网络保护继续有效。
