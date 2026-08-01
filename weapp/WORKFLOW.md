# RIG-Puppy Workflow

## 默认操作顺序

1. 在本地目录改代码
2. 将本地改动同步到服务器
3. 将本地代码推送到 GitHub

## 本地目录

- `xiaozhi-esp32-server-main/`
- `kb-admin/`
- `xiaozhi-server/`

## 说明

- `xiaozhi-esp32-server-main` 是服务器上的主源码仓库，线上已有未提交修改。
- `xiaozhi-server` 是部署目录，不等于源码仓库；这里只保留部署配置、插件目录和 `web-html`。
- `kb-admin` 是单独的自建后端。
- GitHub 不能直接使用账号密码推送，后续需要配置 `PAT` 或 `SSH key`。

## 常用命令

- 同步到服务器：`./deploy_to_server.sh`
- 只同步主源码：`./deploy_to_server.sh --only source`
- 只同步 kb-admin：`./deploy_to_server.sh --only kb-admin`
- 预览本次会传什么：`./deploy_to_server.sh --dry-run`
