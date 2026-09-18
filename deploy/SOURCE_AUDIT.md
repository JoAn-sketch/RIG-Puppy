# 线上来源核查

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
