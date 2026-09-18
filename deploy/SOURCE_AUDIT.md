# 线上来源核查

## 最新进展（优先于下方历史记录）

- 已恢复 config.yaml，仅将天气 API 凭据替换成 YOUR_WEATHER_API_KEY，其余文本保持原样。管理 API 的 server-base 读取成功，返回配置未提供该天气字段；设备级配置及天气端到端行为尚未验证。
- 只读核实两个语音容器相对镜像没有环境变量覆盖，镜像摘要、命令、用户、目录、挂载及 restart 已写入 compose.voice.yml。
- Kokoro 模型位于 /app/api/src/models/v1_0，音色位于 /app/api/src/voices/v1_0。目录存在不等于已经证明与镜像一致；可写层恢复验证仍未完成。
- coordinated.py 实现已纳管服务的更新顺序和网络归属验证；尚未接入正式入口。现有阻止检查和 enabled=false 保留，不能将此模块直接当作首次迁移工具。
- 13 项基础及协调更新测试通过。当前本地 Docker 没有 Compose 子命令，组合配置验证未通过，未执行镜像构建或生产变更。
- 剩余：可写层/模型恢复验证、首次纳管及回退演练、隔离镜像构建、组合配置验证，以及将经演练模块接入正式入口。

协调更新的选定方向、首次纳管和回退步骤见 `COORDINATED_UPDATE.md`。新增 `health.py` 必须在主服务网络命名空间中执行；它仅检查 HTTP 路由和 TCP，不代替语音端到端测试。

本次为只读检查，未 reset 生产代码、构建生产镜像或更新容器。

- 主容器镜像 ID：`sha256:e494fae1799d48c15e89d4c43cc5ec14e6183589a6e8688cdda4e45afcef3b31`。
- Compose 项目：`xiaozhi-server`。
- 正式 Compose 文件：`/home/ubuntu/xiaozhi-esp32-server-main/main/xiaozhi-server/docker-compose.yml`。
- 主容器仅挂载该目录的 `data` 和 `models/SenseVoiceSmall`；业务代码在镜像中。
- FunASR 和 Kokoro 没有 Compose 项目标记，不能用主服务 Compose 重建它们。
- 主服务、FunASR、Kokoro 均运行；MySQL、Redis 显示 healthy。
- 服务器目录下载的 207 个 Python 文件逐个与运行容器 SHA-256 比较，全部一致。包含性能测试文件；本次只将业务源码及构建依赖恢复到 Git。
- `app.py` 与保留备份 `xiaozhi-esp32-server-main.backup.20260918_101605` 一致；未声称整个备份完全一致。

## 已恢复

`main/xiaozhi-server` 中的 app.py、core、config、plugins_func、requirements.txt、agent-base-prompt.txt 和线上原始 docker-compose.yml。业务 Python 未作修改。

## 尚未满足的部署前提

### 默认配置审查结果

本地用 YAML 解析器检查默认配置，仅输出字段名和占位符分类，没有输出认证值。`plugins.get_weather.api_key` 包含非占位凭据，不能原样提交。当前 `data/.config.yaml` 没有覆盖该字段，但启用了 manager-api 配置来源；必须继续核实实际合并结果，不能假设删除该值没有影响。未修改生产配置，也未提交未经脱敏的默认配置。

Kokoro 可写层检查在 25 秒超时，尚不能确认其模型是否包含在镜像内。随后简短检查确认所有容器仍运行；未重复昂贵的 diff 查询，未重建或停止容器。协调切换仍不可启用。

### 追加核实：共享网络阻止单独重建主容器

- 服务器为 x86_64，本地 Docker 为 aarch64。
- FunASR、Kokoro 的 NetworkMode 都是 `container:3610a83525fb889d90911197a5ddd1400d09583a411fa726661b05b4b103f244`，该 ID 正是当前主服务器。
- 宿主机没有 10095/8880 监听；在主容器中访问 Kokoro `/health` 返回 200，FunASR 10095 TCP 连接成功。
- 主服务器 `http://127.0.0.1:8003/mcp/vision/explain` 返回 200。此结果证明路由可用，不代表完整语音对话通过。
- 直接重建主服务会使语音容器仍引用旧网络命名空间。新脚本在 reset/build/up 前明确阻止该操作。需要另行设计并验证三容器协调更新，不能靠 `--no-deps` 单独更新主服务。
- `compose.build.yml` 仅为候选构建覆盖文件，尚未激活，也不改变数据挂载。

1. 原始 Compose 只有 image，没有 build；原样保留用于核查，不能用于 Git 构建部署。
2. config.yaml、config_from_api.yaml、mcp_server_settings.json 尚在仓库外审查目录，不提交未经审核的认证信息。缺少默认 config.yaml 的版本不可视为可运行版本。
3. 需要审查默认配置的认证字段与现有 data/.config.yaml 覆盖关系，保证不改变线上配置行为。
4. 未验证镜像仓库可用性和本地完整镜像构建；本地 Docker 为 aarch64，需核对服务器平台。
5. 需要核实语音服务网络模式及真实应用健康检查，不能把主接口根路径 404 当成功。
6. 部署配置仍为 enabled=false。恢复源码不代表已完成生产切换。
