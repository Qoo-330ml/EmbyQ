import os
import time
import sqlite3
import socket
import re
import logging
from datetime import datetime
import requests
from webhook_notifier import WebhookNotifier
from location_service import LocationService


class EmbyMonitor:
    def __init__(self, db_manager, emby_client, security_client, config, location_service=None):
        self.db = db_manager
        self.emby = emby_client
        self.security = security_client
        self.config = config
        self.active_sessions = {}
        
        # 使用传入的 location_service 或创建新的
        if location_service:
            self.location_service = location_service
        else:
            use_geocache = config.get('ip_location', {}).get('use_geocache', False)
            # 获取Emby服务器信息
            emby_server_info = self.emby.get_server_info()
            self.location_service = LocationService(use_hiofd=use_geocache, db_manager=db_manager, emby_server_info=emby_server_info)
        
        # 预处理白名单（不区分大小写）
        self.whitelist = [name.strip().lower() 
                         for name in config['security']['whitelist'] 
                         if name.strip()]
        
        # 安全配置
        self.auto_disable = config['security']['auto_disable']
        self.alert_threshold = config['notifications']['alert_threshold']
        self.alerts_enabled = config['notifications']['enable_alerts']
        self.ipv6_prefix_length = config['security'].get('ipv6_prefix_length', 64)
        
        # 初始化Webhook通知器
        self.webhook_notifier = None
        self.update_runtime_config(config)

    def update_runtime_config(self, config):
        """热更新运行期配置（尤其是 webhook / 安全相关设置）"""
        self.config = config
        self.whitelist = [name.strip().lower() for name in config['security']['whitelist'] if name.strip()]
        self.auto_disable = config['security']['auto_disable']
        self.alert_threshold = config['notifications']['alert_threshold']
        self.alerts_enabled = config['notifications']['enable_alerts']
        self.ipv6_prefix_length = config['security'].get('ipv6_prefix_length', 64)

        webhook_config = config.get('webhook', {})
        try:
            if self.webhook_notifier:
                self.webhook_notifier.update_config(webhook_config)
            elif webhook_config.get('enabled', False):
                self.webhook_notifier = WebhookNotifier(webhook_config)

            if self.webhook_notifier and not self.webhook_notifier.is_enabled():
                logging.info("🔕 Webhook通知未启用")
            elif self.webhook_notifier:
                logging.info("🔔 Webhook通知已启用")
        except Exception as e:
            logging.error(f"❌ Webhook通知初始化/更新失败: {e}")
            self.webhook_notifier = None

    def _extract_ip_address(self, remote_endpoint):
        """智能提取IP地址，支持IPv4和IPv6"""
        if not remote_endpoint:
            return ""
        
        # 处理IPv6地址格式：[IPv6]:port 或 IPv6%interface:port
        ipv6_pattern = r'^\[(.*?)\](?::(\d+))?$|^([^%]:*)(?:%[^:]*)?:(?:(\d+))?$'
        match = re.match(ipv6_pattern, remote_endpoint)
        
        if match:
            # 方括号格式（IPv6）
            if match.group(1):  # [IPv6]:port格式
                return match.group(1)
            # 冒号格式（可能是IPv6）
            ip_part = match.group(3)
            if ip_part and self._is_ipv6(ip_part):
                return ip_part
            elif ip_part:
                return ip_part
        
        # 如果上面没匹配到，尝试其他方法
        # 对于IPv6格式2408:8207:28c:3c01:8c5e:7cff:fe2e:2c8e:8096
        parts = remote_endpoint.split(':')
        if len(parts) >= 8:  # IPv6至少有8个部分（16进制）
            # 尝试前8个部分组成IPv6地址
            potential_ipv6 = ':'.join(parts[:8])
            if self._is_ipv6(potential_ipv6):
                return potential_ipv6
        
        # 处理IPv4格式
        ipv4_pattern = r'^(\d+\.\d+\.\d+\.\d+):(\d+)$'
        match = re.match(ipv4_pattern, remote_endpoint)
        if match:
            return match.group(1)
        
        # 如果都匹配不到，返回原始值（可能是IPv6直接格式）
        return remote_endpoint.split('%')[0]  # 移除接口标识
    
    def _is_ipv6(self, ip_str):
        """检查是否为有效的IPv6地址"""
        try:
            socket.inet_pton(socket.AF_INET6, ip_str)
            return True
        except (socket.error, ValueError):
            return False
    
    def _is_ipv4(self, ip_str):
        """检查是否为有效的IPv4地址"""
        try:
            socket.inet_pton(socket.AF_INET, ip_str)
            return True
        except (socket.error, ValueError):
            return False
    
    def _get_ipv6_prefix(self, ipv6_address, prefix_length):
        """获取IPv6地址的前缀
        
        Args:
            ipv6_address: IPv6地址字符串
            prefix_length: 前缀长度（比特）
            
        Returns:
            前缀字符串，例如 "2409:8a55:9429:9a90::"（64位前缀）
        """
        if not ipv6_address or not self._is_ipv6(ipv6_address):
            return ipv6_address
            
        try:
            # 将IPv6地址转换为二进制数据
            binary_data = socket.inet_pton(socket.AF_INET6, ipv6_address)
            
            # 计算需要保留的字节数
            prefix_bytes = prefix_length // 8
            if prefix_length % 8 != 0:
                prefix_bytes += 1
            
            # 获取前缀字节
            prefix_binary = binary_data[:prefix_bytes]
            
            # 计算需要保留的段数（每个段16位=2字节）
            prefix_segments = prefix_length // 16
            if prefix_length % 16 != 0:
                prefix_segments += 1
            
            # 将前缀字节转换回IPv6地址字符串
            prefix_address = socket.inet_ntop(socket.AF_INET6, prefix_binary.ljust(16, b'\x00'))
            
            # 提取前缀部分
            segments = prefix_address.split(':')
            prefix_segments = segments[:prefix_segments]
            
            # 确保格式正确（添加::如果需要）
            if len(prefix_segments) < 8:
                prefix_segments.append('')
            
            return ':'.join(prefix_segments)
            
        except Exception:
            return ipv6_address
    
    def _is_same_network(self, ip1, ip2):
        """判断两个IP地址是否属于同一网络
        
        Args:
            ip1: 第一个IP地址
            ip2: 第二个IP地址
            
        Returns:
            True如果属于同一网络，否则False
        """
        if ip1 == ip2:
            return True
            
        # 检查是否都是IPv6地址
        if self._is_ipv6(ip1) and self._is_ipv6(ip2):
            # 比较前缀
            prefix1 = self._get_ipv6_prefix(ip1, self.ipv6_prefix_length)
            prefix2 = self._get_ipv6_prefix(ip2, self.ipv6_prefix_length)
            return prefix1 == prefix2
        
        # 检查是否都是IPv4地址（直接比较）
        if self._is_ipv4(ip1) and self._is_ipv4(ip2):
            return ip1 == ip2
        
        # 混合类型，认为不是同一网络
        return False

    def process_sessions(self):
        """核心会话处理逻辑"""
        try:
            current_sessions = self.emby.get_active_sessions()
            self._detect_new_sessions(current_sessions)
            self._detect_ended_sessions(current_sessions)
            self._update_session_positions(current_sessions)
        except Exception as e:
            logging.error(f"❌ 会话更新失败: {str(e)}")

    def _detect_new_sessions(self, current_sessions):
        """识别新会话"""
        for session_id, session in current_sessions.items():
            if session_id not in self.active_sessions:
                self._record_session_start(session)

    def _detect_ended_sessions(self, current_sessions):
        """识别结束会话"""
        ended = set(self.active_sessions.keys()) - set(current_sessions.keys())
        for sid in ended:
            self._record_session_end(sid)

    def _update_session_positions(self, current_sessions):
        """更新活跃会话的播放位置"""
        for session_id, session in current_sessions.items():
            if session_id in self.active_sessions:
                play_state = session.get('PlayState', {})
                position_ticks = play_state.get('PositionTicks', 0)
                
                # 获取上次记录的播放位置
                last_position_ticks = self.active_sessions[session_id].get('last_position_ticks', 0)
                
                # 计算增量播放时长（秒）
                if position_ticks > last_position_ticks:
                    # 播放位置前进，累加播放时长
                    delta_ticks = position_ticks - last_position_ticks
                    delta_seconds = int(delta_ticks / 10000000)
                    current_duration = self.active_sessions[session_id].get('playback_duration', 0)
                    self.active_sessions[session_id]['playback_duration'] = current_duration + delta_seconds
                
                # 更新上次播放位置
                self.active_sessions[session_id]['last_position_ticks'] = position_ticks

    def _record_session_start(self, session):
        """记录新会话"""
        try:
            user_id = session['UserId']
            user_info = self.emby.get_user_info(user_id)
            ip_address = self._extract_ip_address(session.get('RemoteEndPoint', ''))
            username = user_info.get('Name', '未知用户').strip()

            # 白名单检查 - 记录信息但不封禁
            is_whitelist = username.lower() in self.whitelist

            # 获取媒体信息
            media_item = session.get('NowPlayingItem', {})
            media_name = self.emby.parse_media_info(media_item)
            
            # 获取地理位置
            location = self._get_location(ip_address)

            session_data = {
                'session_id': session['Id'],
                'user_id': user_id,
                'username': username,
                'ip': ip_address,
                'device': session.get('DeviceName', '未知设备'),
                'client': session.get('Client', '未知客户端'),
                'media': media_name,
                'start_time': datetime.now(),
                'location': location,
                'playback_duration': 0,
                'last_position_ticks': 0
            }

            self.db.record_session_start(session_data)
            self.active_sessions[session['Id']] = session_data
            
            # 显示IP地址类型信息
            ip_type = "IPv6" if self._is_ipv6(ip_address) else "IPv4" if self._is_ipv4(ip_address) else "未知"
            if is_whitelist:
                logging.info(f"[▶] {username} (白名单) | 设备: {session_data['device']} | IP: {ip_address} ({ip_type}) | 位置: {location} | 内容: {session_data['media']}")
            else:
                logging.info(f"[▶] {username} | 设备: {session_data['device']} | IP: {ip_address} ({ip_type}) | 位置: {location} | 内容: {session_data['media']}")
            
            # 触发异常检测
            self._check_login_abnormality(user_id, ip_address)
        except KeyError as e:
            logging.error(f"❌ 会话数据缺失关键字段: {str(e)}")
        except Exception as e:
            logging.error(f"❌ 会话记录失败: {str(e)}")

    def _record_session_end(self, session_id):
        """记录会话结束"""
        try:
            session_data = self.active_sessions[session_id]
            end_time = datetime.now()
            
            # 使用内存中记录的实际播放时长
            duration = session_data.get('playback_duration', 0)
            
            # 如果播放时长为0，回退到时间差计算
            if duration == 0:
                duration = int((end_time - session_data['start_time']).total_seconds())
            
            self.db.record_session_end(session_id, end_time, duration)
            logging.info(f"[■] {session_data['username']} | 时长: {duration//60}分{duration%60}秒")
            del self.active_sessions[session_id]
        except KeyError:
            logging.warning(f"⚠️ 会话 {session_id} 已不存在")
        except Exception as e:
            logging.error(f"❌ 结束记录失败: {str(e)}")

    def _get_location(self, ip_address):
        """解析地理位置，使用 qoo-ip138，统一格式：位置·区·街道"""
        if not ip_address:
            return "未知位置"

        try:
            info = self.location_service.lookup(ip_address)
            return info.get("formatted", "未知位置")
        except Exception as e:
            logging.error(f"📍 解析 {ip_address} 失败: {str(e)}")
            return "解析失败"

    def _check_login_abnormality(self, user_id, new_ip):
        """检测登录异常"""
        if not self.alerts_enabled:
            return
        
        existing_networks = set()
        for sess in self.active_sessions.values():
            if sess['user_id'] == user_id:
                existing_ip = sess['ip']
                # 如果是同一网络，跳过
                if not self._is_same_network(existing_ip, new_ip):
                    # 对于IPv6，存储网络前缀
                    if self._is_ipv6(existing_ip):
                        network = self._get_ipv6_prefix(existing_ip, self.ipv6_prefix_length)
                    else:
                        network = existing_ip
                    existing_networks.add(network)
        
        if len(existing_networks) >= (self.alert_threshold - 1):
            self._trigger_alert(user_id, new_ip, len(existing_networks)+1)

    def _trigger_alert(self, user_id, trigger_ip, session_count):
        """触发安全告警"""
        try:
            user_info = self.emby.get_user_info(user_id)
            username = user_info.get('Name', '未知用户').strip()
            
            # 最终白名单确认
            if username.lower() in self.whitelist:
                logging.info(f"⚪ 白名单用户 [{username}] 受保护，跳过禁用")
                return

            location = self._get_location(trigger_ip)
            ip_type = "IPv6" if self._is_ipv6(trigger_ip) else "IPv4" if self._is_ipv4(trigger_ip) else "未知"
            
            # 记录会话信息以获取设备等详细信息
            device = "未知设备"
            client = "未知客户端"
            for sess in self.active_sessions.values():
                if sess['user_id'] == user_id and sess['ip'] == trigger_ip:
                    device = sess.get('device', '未知设备')
                    client = sess.get('client', '未知客户端')
                    break
            
            alert_msg = f"""
            🚨 安全告警 🚨
            时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            用户名: {username}
            可疑IP: {trigger_ip} ({ip_type}) ({location})
            并发会话数: {session_count}
            """
            logging.info("=" * 60)
            logging.info(alert_msg.strip())
            logging.info("=" * 60)
            
            if self.auto_disable:
                if self.security.disable_user(user_id, username):
                    self._log_security_action(user_id, trigger_ip, session_count, username)
                    
                    # 发送Webhook通知
                    self._send_webhook_notification({
                        'username': username,
                        'user_id': user_id,
                        'ip_address': trigger_ip,
                        'ip_type': ip_type,
                        'location': location,
                        'session_count': session_count,
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'reason': f'检测到{session_count}个并发会话',
                        'device': device,
                        'client': client
                    })
        except Exception as e:
            logging.error(f"❌ 告警处理失败: {str(e)}")

    def _send_webhook_notification(self, user_info: dict):
        """发送Webhook通知"""
        if not self.webhook_notifier:
            return
        
        try:
            success = self.webhook_notifier.send_ban_notification(user_info)
            if success:
                logging.info(f"🔔 Webhook通知已发送: {user_info['username']}")
            else:
                logging.warning(f"⚠️ Webhook通知发送失败: {user_info['username']}")
        except Exception as e:
            logging.error(f"❌ Webhook通知异常: {str(e)}")

    def test_webhook(self):
        """测试Webhook配置"""
        if not self.webhook_notifier or not self.webhook_notifier.is_enabled():
            logging.warning("⚠️ Webhook未启用，无法测试")
            return False

        logging.info("🧪 测试Webhook配置...")
        return self.webhook_notifier.test_webhook()

    def _log_security_action(self, user_id, ip, count, username):
        """记录安全日志"""
        log_data = {
            'timestamp': datetime.now(),
            'user_id': user_id,
            'username': username,
            'trigger_ip': ip,
            'active_sessions': count,
            'action': 'DISABLE'
        }
        try:
            self.db.log_security_event(log_data)
        except Exception as e:
            logging.error(f"❌ 安全日志记录失败: {str(e)}")

    def _check_expired_users(self):
        """检查并封禁到期用户"""
        try:
            # 获取所有已到期但未禁用的用户
            expired_users = self.db.get_all_expired_users()

            for user_id in expired_users:
                try:
                    # 获取用户信息
                    user_info = self.emby.get_user_info(user_id)
                    if not user_info:
                        continue

                    username = user_info.get('Name', '未知用户').strip()

                    # 检查是否已在白名单
                    if username.lower() in self.whitelist:
                        logging.info(f"⚪ 白名单用户 [{username}] 到期但受保护，跳过禁用")
                        continue

                    # 检查用户是否已被禁用
                    is_disabled = user_info.get('Policy', {}).get('IsDisabled', False)
                    if is_disabled:
                        continue

                    # 封禁用户
                    if self.security.disable_user(user_id, username):
                        logging.info(f"🔒 用户 [{username}] 账号已到期，自动封禁")

                        # 记录安全日志
                        log_data = {
                            'timestamp': datetime.now(),
                            'user_id': user_id,
                            'username': username,
                            'trigger_ip': 'system',
                            'active_sessions': 0,
                            'action': 'DISABLE'
                        }
                        self.db.log_security_event(log_data)

                        # 发送Webhook通知
                        self._send_webhook_notification({
                            'username': username,
                            'user_id': user_id,
                            'ip_address': 'system',
                            'ip_type': 'N/A',
                            'location': '系统自动',
                            'session_count': 0,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'reason': '账号已到期',
                            'device': 'N/A',
                            'client': 'N/A'
                        })

                except Exception as e:
                    logging.error(f"❌ 处理到期用户 {user_id} 失败: {str(e)}")

        except Exception as e:
            logging.error(f"❌ 检查到期用户失败: {str(e)}")

    def run(self):
        """启动监控服务"""
        logging.info(f"🔍 监控服务启动 | 数据库: {self.config['database']['name']}")

        # 到期用户检查计数器
        expiry_check_counter = 0
        expiry_check_interval = 60  # 每60个主循环周期检查一次到期用户

        # IP归属地缓存清理计数器
        ip_cache_cleanup_counter = 0
        ip_cache_cleanup_interval = 7200  # 每7200个主循环周期清理一次IP归属地缓存（约10小时）

        try:
            while True:
                self.process_sessions()

                # 定期检查到期用户
                expiry_check_counter += 1
                if expiry_check_counter >= expiry_check_interval:
                    self._check_expired_users()
                    expiry_check_counter = 0

                # 定期清理IP归属地缓存
                ip_cache_cleanup_counter += 1
                if ip_cache_cleanup_counter >= ip_cache_cleanup_interval:
                    try:
                        deleted_count = self.db.cleanup_old_ip_locations(days=30)
                        if deleted_count > 0:
                            logging.info(f"🧹 已清理 {deleted_count} 条30天前的IP归属地缓存记录")
                    except Exception as e:
                        logging.error(f"❌ 清理IP归属地缓存失败: {str(e)}")
                    ip_cache_cleanup_counter = 0

                time.sleep(self.config['monitor']['check_interval'])
        except KeyboardInterrupt:
            logging.info("\n👋 监控服务停止")
