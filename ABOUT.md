# EmbyQ 关于

## 版本信息

当前版本：1.1.0

## 日志信息

### 查看日志
- **Docker 容器日志**：使用 `docker logs embyq` 查看
- **本地运行日志**：直接在终端查看输出
- **日志内容**：包含启动信息、监控事件、IP 解析结果、用户封禁通知等

## 项目介绍

EmbyQ 是一个面向 Emby 的账号安全与运营辅助工具，提供实时监控播放会话、识别同一账号多 IP 并发播放并自动处理、可视化后台管理等功能。

## 功能特性

### 安全监控能力
- 实时轮询 Emby 活跃会话
- 支持 IPv4 / IPv6 提取与同网段判断
- 按阈值触发告警（可自动禁用账号）
- 白名单用户保护
- Webhook 通知（可自定义 body）

### 用户运营能力
- 用户列表、批量启用/禁用
- 到期时间管理（单个/批量）
- 永不过期设置
- 用户组管理（建组、加成员、移除成员）
- 新建用户（支持模板用户复制权限）
- 快速删除用户

### 邀请注册能力
- 生成邀请链接（有效时长、可用人数、用户组、账号到期时间）
- 邀请链接历史列表（使用进度、失效态、一键复制、作废删除）
- 用户访问 `/invite/:code` 自助注册
- 注册成功后自动跳转到 Emby 外网地址

### 前端体验
- React + Vite 单页应用
- 管理后台登录态
- 移动端用户列表卡片化（避免横向滚动）
- 桌面端表格列宽优化

## 安装与运行

### Docker Compose（推荐）

```yaml
services:
  embyq:
    image: pdzhou/embyq:latest   # 若使用 ip-hiofd 分支镜像请改为 ip-hiofd 标签
    container_name: embyq
    restart: always
    tty: true
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
```

### 本地运行

1. 克隆仓库
2. 安装依赖：`pip install -r requirements.txt`
3. 前端构建：`cd frontend && npm install && npm run build && cd ..`
4. 启动：`python3 scripts/main.py`

默认监听：`http://0.0.0.0:5000`

## 管理后台功能

- ` /admin/users`：用户管理
- `/admin/groups`：用户组管理
- `/admin/config`：配置管理

公开页面：
- `/search`：用户播放查询
- `/invite/:code`：邀请注册页面

## 常见问题

### Q1: 邀请链接生成后无法访问？
先检查 `service.external_url` 是否填写为真实可访问地址（含端口）。

### Q2: 注册成功后跳转地址不对？
检查 `emby.external_url`。

### Q3: 页面改了但看不到效果？
确认已执行 `npm run build`，并重启服务。

## 开发说明

- 前端开发热更新：`cd frontend && npm run dev`
- 后端主程序：`scripts/main.py`
- API 路由：`scripts/web_server.py`
- 数据层：`scripts/database.py`

## 许可证

按仓库实际 License 文件为准。若无明确声明，请在使用前自行确认。

## README.md 内容

# EmbyQ（原EmbyIPLimit)

EmbyQ 是一个面向 Emby 的账号安全与运营辅助工具：
- 实时监控播放会话
- 识别"同一账号多 IP 并发播放"并自动处理
- 提供可视化后台（用户管理 / 用户组 / 配置）
- 支持邀请注册链路与到期时间管理

---

## 1. 项目总结（当前版本）

这个项目现在已经从"单纯封禁脚本"升级为一套轻量后台系统，核心能力包括：

### 安全监控能力
- 实时轮询 Emby 活跃会话
- 支持 IPv4 / IPv6 提取与同网段判断
- 按阈值触发告警（可自动禁用账号）
- 白名单用户保护
- Webhook 通知（可自定义 body）

### 用户运营能力
- 用户列表、批量启用/禁用
- 到期时间管理（单个/批量）
- 永不过期设置
- 用户组管理（建组、加成员、移除成员）
- 新建用户（支持模板用户复制权限）
- 快速删除用户

### 邀请注册能力
- 生成邀请链接（有效时长、可用人数、用户组、账号到期时间）
- 邀请链接历史列表（使用进度、失效态、一键复制、作废删除）
- 用户访问 `/invite/:code` 自助注册
- 注册成功后自动跳转到 Emby 外网地址

### 前端体验
- React + Vite 单页应用
- 管理后台登录态
- 移动端用户列表卡片化（避免横向滚动）
- 桌面端表格列宽优化

---

## 2. 分支说明（重点）

仓库维护两个主分支，**功能基本同步**，保留一个核心差异：IP 归属地解析策略。

### `main`
- 归属地解析：`qoo-ip138`
- Docker 标签：`latest` 系列

### `ip-hiofd`
- 归属地解析：`ip-hiofd`
- Docker 标签：`ip-hiofd` 系列

> 约定：除了归属地解析器及对应发布标签差异，其他功能尽量保持一致。

---

## 3. 目录结构

```txt
EmbyQ/
├─ scripts/                 # 后端（Flask API + 监控逻辑 + 数据层）
├─ frontend/                # 前端（React + Vite）
├─ data/                    # 配置与数据库（运行时）
├─ Dockerfile
├─ requirements.txt
└─ README.md
```

---

## 4. 安装与运行

## 4.1 Docker Compose（推荐）

```yaml
services:
  embyq:
    image: pdzhou/embyq:latest   # 若使用 ip-hiofd 分支镜像请改为 ip-hiofd 标签
    container_name: embyq
    restart: always
    tty: true
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
```

启动后会自动在 `data/config.yaml` 生成配置模板。

---

## 4.2 本地运行

### 1) 克隆仓库
```bash
git clone https://github.com/Qoo-330ml/EmbyIPLimit.git
cd EmbyQ
```

### 2) 安装依赖
```bash
pip install -r requirements.txt
```

### 3) 前端构建
```bash
cd frontend
npm install
npm run build
cd ..
```

### 4) 启动
```bash
python3 scripts/main.py
```

默认监听：`http://0.0.0.0:5000`

---

## 5. 配置说明（data/config.yaml）

关键字段：

```yaml
emby:
  server_url: https://emby.example.com      # Emby 内网/直连地址（API调用）
  external_url: https://emby.example.com    # Emby 外网地址（邀请注册后跳转）
  api_key: your_api_key_here

service:
  external_url: https://embyq.example.com:5000  # EmbyQ 对外访问地址（用于生成邀请链接）

monitor:
  check_interval: 10

notifications:
  enable_alerts: true
  alert_threshold: 2

security:
  auto_disable: true
  whitelist:
    - admin
```

后台登录配置：
```yaml
web:
  admin_username: admin
  admin_password: admin123
```

> 建议生产环境立即修改默认后台账号密码。

---

## 6. 管理后台功能速览

- ` /admin/users`：用户管理
  - 新建用户（模板复制权限）
  - 邀请管理（生成、复制、删除、进度）
  - 批量操作（到期、封禁、启用）
  - 删除用户
- `/admin/groups`：用户组管理
- `/admin/config`：配置管理

公开页面：
- `/search`：用户播放查询
- `/invite/:code`：邀请注册页面

---

## 7. 常见问题

### Q1: 邀请链接生成后无法访问？
先检查 `service.external_url` 是否填写为真实可访问地址（含端口）。

### Q2: 注册成功后跳转地址不对？
检查 `emby.external_url`。

### Q3: 页面改了但看不到效果？
确认已执行 `npm run build`，并重启服务。

---

## 8. 开发说明

- 前端开发热更新：
  ```bash
  cd frontend
  npm run dev
  ```
- 后端主程序：`scripts/main.py`
- API 路由：`scripts/web_server.py`
- 数据层：`scripts/database.py`

---

## 9. License

按仓库实际 License 文件为准。若无明确声明，请在使用前自行确认。