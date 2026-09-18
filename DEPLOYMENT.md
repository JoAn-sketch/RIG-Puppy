# Puppy：仅通过 Git 部署

## 当前状态与范围

正式代码来源：https://github.com/JoAn-sketch/RIG-Puppy/tree/clean-server

生产目录固定为 `/home/ubuntu/xiaozhi-esp32-server-main`。本次只交付部署脚本和配置约束，不执行生产 reset、build、up，不修改业务逻辑和数据存储，不删除历史环境。

**当前分支缺少 `main/xiaozhi-server` 及正式 Compose 文件，尚不可部署。** 必须从实际服务器只读核实并恢复完整源码，确认正式 Compose 文件、覆盖文件、项目名、挂载及健康接口后，才能启用部署。不能用猜测的 Compose 配置替代线上配置。

## 正式流程

本地开发 → commit → push clean-server → 服务器检查 → fetch 并锁定 SHA → reset 到 SHA → build → up → 健康检查。

禁止 SFTP、SCP、rsync 直接覆盖生产代码。SSH 只用于触发服务器上的 Git 部署脚本。备份中的历史脚本不修改。脚本不上传任何业务代码。

1. 固定仓库、生产目录和分支；验证工具，获取部署独占锁。
2. 核实正式 Compose 文件及覆盖文件，所有命令显式使用同一项目名和文件列表。明确主服务器、FunASR、Kokoro 各自所属项目，不删除 orphan 容器。
3. 用 `git status --porcelain --untracked-files=all` 检查已跟踪及未忽略文件。任何修改均停止并报告路径，禁止自动 stash、commit 或 clean。运行数据不能为通过检查而迁移。
4. 验证 origin 为指定 GitHub 仓库，显式 fetch clean-server，解析固定 target SHA。fetch 失败不得使用缓存引用。
5. 再检查工作区；确认目标没有跟踪 `.env`、模型、数据库、运行数据，确认容器没有挂载待替换的源码。保存旧 HEAD、容器 ID 和镜像 ID。
6. `git reset --hard "$target_commit"`，核实 HEAD。reset 只允许在上述条件通过后执行。即使忽略文件不会显示为脏，也必须检查目标路径是否会覆盖它们。
7. 校验 Compose 配置，主服务必须包含明确的 build context 和 Dockerfile，确保构建目标 Git 源码。用 SHA 标记主服务镜像及 revision 标签，保留旧镜像 ID。不允许无构建任务的成功被算作构建成功。
8. build 完全成功后才执行相同 Compose 配置的 `up -d --no-build --pull never`，范围限主服务且不启动依赖。build 失败保留运行容器，报告工作树已更新而线上未更新。
9. 有限等待三个核心容器运行；存在 healthcheck 则必须 healthy。检查主服务镜像、revision 和 HEAD，检查 10095、8880 监听，再执行经核实的应用健康检查。404 不代表检查通过；没有健康检查则不能启用部署。
10. 健康检查失败返回非零，报告失败阶段、线上影响及回退依据。未验证安全回退前，不自动回滚。

禁止 `docker compose down`、`--remove-orphans`、任何 prune 或卷删除。更新过程不修改数据库、模型、环境文件及运行数据的存储方式。若线上直接挂载源码，必须先报告并单独设计迁移，不能直接 reset。

## 配置与使用

`deploy/deploy.py` 是服务器入口。只读配置模板见 `deploy/config.example.json`；模板默认禁止部署。核实实际环境后，在服务器仓库外保存配置，例如 `/home/ubuntu/puppy-deploy-config.json`，不要提交秘密。

```bash
# 本地静态检查，不连接服务器
python3 -m py_compile deploy/deploy.py
python3 -m unittest discover -s deploy/tests

# 以下仅为未来操作示例，本次不执行
git push origin clean-server
ssh ubuntu@SERVER 'python3 /home/ubuntu/xiaozhi-esp32-server-main/deploy/deploy.py --config /home/ubuntu/puppy-deploy-config.json'
```

首次安装脚本也必须由服务器 fetch Git 获取，不能从本地传脚本覆盖生产代码。当前生产仓库和 GitHub 的历史不同，且现有代码未验证完整；首次切换须另行核实，不得直接执行上述命令。

## 每次结果报告

- 部署目录、GitHub 仓库与分支、Compose 文件与项目名
- 部署前 HEAD、目标 commit、部署后 HEAD
- build 结果、更新结果
- 部署前后容器 ID / 镜像 ID
- 主服务、FunASR、Kokoro 状态
- FunASR 10095、Kokoro 8880
- 应用健康检查、最终结果、失败阶段及线上影响、回退依据

未执行的阶段标为未执行，不能报告成功。报告不包含敏感配置或认证信息。
