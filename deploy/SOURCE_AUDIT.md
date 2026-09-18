# 线上来源核查

## 最新进展（优先于下方历史记录）

新增 migration_flow.py 九阶段编排：preflight→sync→build→recheck→backup→retain→create_main→create_voices→verify。逐阶段先落盘，失败停止、不自动回退，拒绝已有日志盲目重放。九阶段分别注入失败，总计28项测试通过。该模块要求调用方提供所有真实操作适配，尚未接入生产 CLI，不能用模拟测试代替完整迁移验收。

首次纳管只读预检已接入 adoption.py：检查三容器运行/健康状态，精确核对全部 bind mount 的源、目标、RW 模式，网络别名和 restart 策略。基于生产 docker inspect 返回值实测通过。检查主服务、两语音服务及 Web 的 Env/Cmd/Entrypoint，未发现旧主服务 IP 引用（仅输出字段命中结果，不输出密钥）。此检查不覆盖配置文件及数据库记录。25 项单元测试通过，未执行任何生产变更。

实际 retain/rollback 模块已通过本地 Docker 集成演练：原 ID、名称、restart 策略、共享网络恢复，失败版本保留且禁用重启，测试实例全部停止。新增日志目录 fsync 与重复失败 ID 防护；22 项单元测试通过。首次生产纳管的完整编排/真实配置验收仍未完成，强制保护仍生效。

新增回退模块及测试：保留失败容器，按原 ID、名称、重启策略恢复旧三容器；修改前验证未知名称占用和旧网络引用。18 处失败注入通过，总计 22 项测试通过。尚待该模块的真实 Docker 集成演练及生产等价配置验收，执行入口仍禁用。

新增 adoption.py：命令行只读输出首次迁移计划，保留函数逐操作记录 pending/complete，权限 0600，拒绝已有日志重放，使用不可变容器 ID，依赖服务先停。九个变更位置逐一注入失败验证，19 项测试通过。此函数尚未暴露执行入口，回退执行器和真实配置验证未完成，不能作为生产迁移完成的证据。

生产网络只读核查已完成：主服务/Web/MySQL/Redis 同属 xiaozhi-server_default，主服务别名保持 xiaozhi-esp32-server。主服务 restart=always，语音服务=unless-stopped。新增 external 网络覆盖文件和只读迁移检查。四份 Compose 组合校验、17 项测试通过。尚未核实所有业务是否硬编码原 IP，尚未执行生产或真实配置恢复验收。

Compose 项目身份隔离的首次纳管机制已在本地模拟通过，旧容器 ID 保留、失败版本保留、旧网络恢复。下一项实际配置检查是生产网络/DNS/跨服务依赖及备份 restart 策略；本次未改变生产项目名或生产配置。详见 RECOVERY_REHEARSAL.md。

本地三容器快照恢复机制演练通过，详见 RECOVERY_REHEARSAL.md。实测可写层恢复和共享网络 ID 重绑定；全部测试容器已停止且产物保留。该演练不涉及生产配置/挂载或 Compose 首次纳管，因此生产恢复保护仍保留。

### 本地构建验证已通过

使用临时 Buildx v0.28.0 / BuildKit 完成本地 linux/amd64 构建，未删除镜像或清理存储。之前 legacy builder 的 content digest 错误在 BuildKit 下没有复现。基础镜像固定为本次使用的 `sha256:6b62dba28638d845920d437f9f958c99bd8dd29c6714381257177b993d7ce43c`。

在无网络一次性容器中执行 pip check，结果为 No broken requirements found；yaml、aiohttp、websockets、openai、portalocker、jinja2、psutil 导入成功。空测试 data/.config.yaml 下主程序 import app 成功。没有使用生产密钥或启动生产服务。

存在 RequestsDependencyWarning（urllib3/chardet/charset_normalizer 组合）；不影响本次导入，但尚未完成实际 HTTP、语音对话验收。构建通过不等于可安全切换：恢复实现、首次纳管与回退演练仍未完成，强制部署保护保留。

固定生产摘要 Kokoro 镜像已成功在本地拉取，使用无网络只读临时容器核实模型。镜像与生产模型 SHA-256 均为 `496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4`，两者音色文件数均为 67（仅数量核对，不声称音色内容逐个一致）。主模型确认镜像自带，无需从生产可写层迁移该文件。

部署入口新增不可由 JSON 开关绕过的恢复实现保护；当前恢复实现未验证，任何 enabled=true 部署仍会停止。14 项测试通过。

本地主服务首次构建在 COPY 阶段失败，Docker 报 content digest not found，属于本地镜像内容存储错误，未执行生产构建。已保留原镜像，未清理 Docker 数据。

补充验证：本地已有 Kokoro v0.2.4 镜像中存在 313 MiB 模型和 67 个音色文件，但本地摘要 `c8812546...` 与生产 `f330d69e...` 不同，不能作为生产模型恢复验证通过的依据。发现仅重命名 Compose 容器仍会被项目标签匹配的风险，首次纳管方案已纠正，禁止照旧步骤执行。

新增验证：使用临时 Compose v2.40.3 工具对三个 Compose 文件执行 config --quiet，通过。协调模块现已接入正式部署入口，但 enabled=false、recovery_rehearsed=false，且未纳管的容器会被拒绝。健康检查已改为主容器命名空间内执行并有限重试。开始本地 linux/amd64 构建验证；镜像下载和最终构建结果另行记录。

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
