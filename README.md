不再更新了，精力用在另一个项目上了（那个项目也有本项目的监控功能），本项目请自由更改二创，现在ai也很方便。



# EmbyQ（原 EmbyIPLimit）

EmbyQ（原 EmbyIPLimit）是一款面向 Emby 媒体服务器的账号安全与运营辅助工具，提供实时监控、自动化安全防护、用户运营管理以及邀请注册等一站式解决方案。

---

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

---

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


---

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

---

## 安全声明

1. **API Key 保护**：妥善保管 Emby API Key，不要将其提交到公共代码仓库
2. **访问控制**：建议通过反向代理（如 Nginx）配置 HTTPS 和访问控制
3. **数据持久化**：Docker 部署时务必将 `/app/data` 目录挂载到宿主机，避免数据丢失
4. **IP 归属地隐私**：启用 `ip_location.use_geocache` 功能时，仅上传 IP 数据用于丰富自建库，不会上传其他隐私数据

---

## 常见问题

**Q: 邀请链接生成后无法访问？**  
A: 检查 `service.external_url` 是否填写为真实可访问地址（含端口）。

**Q: 注册成功后跳转地址不对？**  
A: 检查 `emby.external_url` 配置是否正确。

---

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

---

## 相关链接

- Docker Hub：https://hub.docker.com/r/pdzhou/embyq
- GitHub 仓库：https://github.com/Qoo-330ml/EmbyQ
