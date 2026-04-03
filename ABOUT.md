# EmbyQ（原 EmbyIPLimit）- v1.4.3

## 更新日志

### v1.4.3（2026-04-03）

- **新增影子库**：新增影子库，更新了求片状态，修复了系统代理不生效的bug。

### v1.4.2（2026-04-02）

- **首页求片功能**：增加了首页求片功能，需要填写tmdb的api key。

### v1.4.0（2026-03-26）

- **WebUI 日志查看功能**：增加了日志查看功能，方便管理员查看系统运行日志

### v1.3.0（2026-03-24）

- **自建 IP 归属地库**：增加了来自 IP 数据云的 IP 数据，解析精度一般可达街道/乡镇级别
- **IP 归属地缓存策略**：引入缓存机制，避免重复查询相同 IP
- **注意**：启用自建库会上传 IP 信息到云端库查询，仅上传 IP 数据用于查询

### v1.2.0（2026-03-20）

- **用户组功能**：新增用户组管理，支持创建、添加/移除组成员
- **邀请注册系统**：支持生成邀请链接，用户自助注册
- **项目重命名**：从 EmbyIPLimit 更名为 EmbyQ

### v1.1.0（2026-03-19）

- **IP 归属地链路重构**：重构 IP 归属地查询系统，提升稳定性
- **双查询方式**：引入 IP138 和 IP 数据云（未启用）两种查询方式

### v1.0.0（2026-03-17）

- **前端重构**：由小龙虾协助将前端重构为 React + Vite 单页应用
- **前后端分离**：后端聚焦 Flask API 输出，前后端职责边界更清晰
- **管理后台优化**：统一导航与壳层结构（users/groups/config）
- **用户体验提升**：增加暗色模式、移动端卡片视图、后台交互细节优化
- **SPA 问题修复**：解决深链接刷新、嵌套路由等典型 SPA 问题

### v0.4.0（2026-03-09）

- **用户有效期管理**：支持设置用户有效期，到期自动禁用
- **用户状态管理**：快速启用/禁用用户账号

### v0.3.0（2026-03-02）

- **IP 归属地查询**：使用 ip138 查询 IP 归属地信息
- **性能优化**：修复 admin 页面因反复加载用户导致打开缓慢的问题

### v0.2.0（2025-01-19）

- **WebUI 上线**：通过 Flask + 静态 HTML 新增简单 WebUI
- **功能完善**：游客可查询播放情况，管理员可进行简单配置
- **IPv6 修复**：修复同一局域网下 IPv6 不同导致误禁用账号的问题

### v0.1.0（2025-12-30）

- **IPv6 支持**：从仅 IPv4 监控升级为 IPv4 + IPv6 混合网络环境兼容

### v0.0.1（2025-03-09）

- **项目诞生**：首个版本发布，纯脚本型工具
- **核心功能**：监控 Emby 服务器播放任务，通过 IP 监控避免同一账号多 IP 同时播放
- **项目名称**：EmbyIPLimit

***

EmbyQ（原 EmbyIPLimit）是一款面向 Emby 媒体服务器的账号安全与运营辅助工具，提供实时监控、自动化安全防护、用户运营管理以及邀请注册等一站式解决方案。

***

## 项目功能

### 安全监控能力

- **实时会话监控**：轮询检测 Emby 活跃播放会话
- **多 IP 并发识别**：智能识别同一账号在多个 IP 地址同时播放的行为
- **IP 归属地解析**：支持 IPv4/IPv6 提取与同网段判断，提供精确地理位置信息
- **自动告警处置**：达到设定阈值自动触发告警，可配置自动禁用违规账号
- **白名单保护**：管理员等特定用户可加入白名单，免受自动处置影响
- **Webhook 通知**：支持自定义 Webhook 推送封禁通知，兼容多种消息平台

### 用户运营能力

- **用户生命周期管理**：查看用户列表、批量启用/禁用账号
- **到期时间管理**：支持单个或批量设置账号到期时间，也可设为永不过期
- **用户组管理**：创建用户组、添加/移除组成员，实现精细化权限控制
- **快速创建用户**：支持基于模板用户复制权限快速创建新用户
- **用户删除**：一键快速删除用户账号

### 邀请注册系统

- **邀请链接生成**：自定义有效时长、可用人数、默认用户组、账号到期时间
- **邀请管理面板**：查看邀请历史、使用进度、失效状态，支持一键复制和作废删除
- **自助注册页面**：用户访问 `/invite/:code` 即可完成注册
- **自动跳转**：注册成功后自动跳转至 Emby 外网地址

### 前端管理界面

- **React + Vite 单页应用**：现代化前端技术栈，流畅的用户体验
- **响应式设计**：移动端用户列表卡片化，桌面端表格列宽优化
- **登录态管理**：安全的后台管理登录机制
- **多页面支持**：用户管理、用户组管理、配置管理、日志查看等功能页面

***

## 部署方式

### Docker Compose（推荐）

```yaml
services:
  embyq:
    image: pdzhou/embyq:latest
    container_name: embyq
    restart: always
    tty: true
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
```

启动后自动在 `./data/config.yaml` 生成配置模板，请根据实际情况修改配置。

### Docker 运行

```bash
docker run -dt \
  --name embyq \
  --restart always \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  pdzhou/embyq:latest
```

### 本地运行

**环境要求**：Python 3.12+、Node.js 22+

```bash
# 1. 克隆仓库
git clone https://github.com/Qoo-330ml/EmbyQ.git
cd EmbyQ

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 构建前端
cd frontend
npm install
npm run build
cd ..

# 4. 启动服务
python scripts/main.py
```

服务默认监听 `http://0.0.0.0:5000`

***

## 配置说明

首次启动后，可以在后台管理界面修改配置或者直接修改 `data/config.yaml` 进行配置：

```yaml
emby:
  server_url: https://emby.example.com      # Emby 服务器地址
  external_url: https://emby.example.com    # 对外访问地址（用于注册后跳转）
  api_key: your_api_key_here                # Emby API Key

service:
  external_url: https://embyq.example.com:5000  # EmbyQ 对外访问地址，用于发送注册邀请链接

monitor:
  check_interval: 10                        # 监控轮询间隔（秒）

notifications:
  alert_threshold: 2                        # 触发告警的并发会话数
  enable_alerts: true                       # 是否启用告警

security:
  auto_disable: true                        # 是否自动禁用违规账号
  whitelist:                                # 白名单用户列表
    - "admin"

ip_location:
  use_geocache: false # 注意！默认使用IP138解析归属地，启用本开关将切换到优先自建归属地库+备用IP数据云（付费库），同时也会开启上传IP数据到自建库以丰富自建库数据，不会上传其他隐私数据，请考虑后开启！

webhook:
  enabled: false                            # 是否启用 Webhook 通知
  url: "https://your-webhook-url"           # Webhook 地址
  timeout: 10                               # 请求超时时间
  retry_attempts: 3                         # 重试次数
  body:                                     # 自定义请求体
    title: "Emby用户封禁通知"
    content: "用户 {username} 在 {location} 使用 {ip_address} ({ip_type}) 登录，检测到 {session_count} 个并发会话，已自动封禁。"

web:
  admin_username: admin                     # 管理员用户名
  admin_password: admin123                  # 管理员密码
```

***

## 安全声明

1. **API Key 保护**：妥善保管 Emby API Key，不要将其提交到公共代码仓库
2. **访问控制**：建议通过反向代理（如 Nginx）配置 HTTPS 和访问控制
3. **数据持久化**：Docker 部署时务必将 `/app/data` 目录挂载到宿主机，避免数据丢失
4. **IP 归属地隐私**：启用 `ip_location.use_geocache` 功能时，仅上传 IP 数据用于丰富自建库，不会上传其他隐私数据

***

## 常见问题

**Q: 邀请链接生成后无法访问？**\
A: 检查 `service.external_url` 是否填写为真实可访问地址（含端口）。

**Q: 注册成功后跳转地址不对？**\
A: 检查 `emby.external_url` 配置是否正确。

***

## 开源协议

本项目采用 [MIT 许可证](LICENSE)。

### 许可证要点

- **允许**：商业使用、修改、分发、私有使用
- **要求**：在副本中包含原始版权声明和许可证声明
- **免责声明**：软件按"原样"提供，不提供任何明示或暗示的担保

### 第三方依赖许可证

- **前端**：React (MIT)、Vite (MIT)、Tailwind CSS (MIT)
- **后端**：Flask (BSD-3-Clause)、requests (Apache-2.0)、pyyaml (MIT)

完整许可证文本请查看 [LICENSE](LICENSE) 文件。

***

## 相关链接

- Docker Hub：<https://hub.docker.com/r/pdzhou/embyq>
- GitHub 仓库：<https://github.com/Qoo-330ml/EmbyQ>

