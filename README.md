20260309：根据意见增加了用户封禁时间，越改越杂了

20260302:改用ip138查询ip归属地，同时修复了admin页面打开很慢的问题；增加了点emoji，调整了下ui；想法有限，可能不会再更新

20260119：修复同一局域网下ipv6的问题，新增了一个web页面，供游客查询播放情况，及管理员简单配置。
目前已知存在问题：同局域网下v4和v6的不同设备无法识别是否是同一局域网


# Emby IPLimit 项目

## 项目简介

Emby IPLimit 是一个专门用于监控和限制 Emby 媒体服务器用户访问行为的工具。它能够实时监控用户的播放会话，检测异常登录行为（如同一用户在多个不同IP地址同时播放），并在达到阈值时自动禁用用户账号，提供完整的安全防护和访问控制功能。

## 主要功能

- 🔍 **实时会话监控** - 监控 Emby 用户的播放会话状态
- 🌐 **IP 地理位置查询** - 自动获取用户 IP 地址的地理位置信息
- 🚨 **异常行为检测** - 检测同一用户在不同 IP 地址的并发播放行为
- 🛡️ **自动安全防护** - 达到阈值时自动禁用问题用户
- 📊 **会话记录存储** - 将播放会话记录到本地 SQLite 数据库
- 🔔 **Webhook 通知** - 支持自定义格式的 Webhook 通知
- ⚪ **白名单管理** - 白名单内用户不会被禁用
- 📝 **详细日志** - 完整的操作日志和监控记录

## 技术特性

- **支持 IPv4 和 IPv6** - 完整支持双栈网络环境
- **灵活配置** - 可自定义监控间隔、告警阈值等参数
- **高兼容性** - 支持各种 Webhook 服务（钉钉、企业微信、飞书等）
- **Docker 支持** - 提供完整的 Docker 部署方案

## 安装部署

### 方式一：Docker Compose部署（推荐）

#### 1. 拉取镜像
```bash
services:
  emby-iplimit:
    image: pdzhou/emby-iplimit:latest
    container_name: emby-iplimit
    restart: always
    tty: true
    network_mode: bridge
    ports:
      - 5000:5000
    volumes:
      - ./data:/app/data
```

#### 2. 配置服务
首次启动后，程序会在 `/path/to/emby-iplimit/data` 目录下生成默认配置文件 `config.yaml`。
您可以直接编辑yaml配置文件，也可以打开5000端口登录管理员账号（admin/admin123）进行配置

### 方式二：本地部署

#### 1. 克隆项目
```bash
git clone https://github.com/Qoo-330ml/EmbyIPLimit.git
cd Emby-IPLimit-main
```

#### 2. 安装依赖
```bash
pip install -r requirements.txt
```

#### 3. 复制配置模板
```bash
cp scripts/default_config.yaml data/config.yaml
```

#### 4. 编辑配置
```bash
vim data/config.yaml
```

#### 5. 运行服务
```bash
python scripts/main.py
```
