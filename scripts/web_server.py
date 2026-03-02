from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import threading
import time
import yaml
from config_loader import load_config, save_config

class WebServer:
    def __init__(self, db_manager, emby_client, security_client, config):
        self.db_manager = db_manager
        self.emby_client = emby_client
        self.security_client = security_client
        self.config = config
        
        # 创建Flask应用
        self.app = Flask(__name__, template_folder='../templates', static_folder='../static')
        self.app.secret_key = 'emby_iplimit_secret_key'  # 生产环境应从配置文件读取
        
        # 初始化登录管理器
        self.login_manager = LoginManager()
        self.login_manager.init_app(self.app)
        self.login_manager.login_view = 'login'
        
        # 注册路由
        self._register_routes()
        
        # 注册上下文处理器，将yaml模块注入模板
        @self.app.context_processor
        def inject_yaml():
            return dict(yaml=yaml)
        
        # 服务器状态
        self.running = False
        self.server_thread = None
    
    def _register_routes(self):
        """注册所有路由"""
        
        @self.login_manager.user_loader
        def load_user(user_id):
            """加载用户"""
            if user_id == 'admin':
                return AdminUser()
            return None
        
        @self.app.route('/')
        def index():
            """首页 - 游客搜索页面"""
            # 获取所有正在播放的会话
            all_active_sessions = self._get_all_active_sessions()
            return render_template('index.html', all_active_sessions=all_active_sessions)
        
        @self.app.route('/search', methods=['POST'])
        def search():
            """用户搜索接口"""
            username = request.form.get('username')
            if not username:
                flash('请输入用户名')
                return redirect(url_for('index'))
            
            # 通过用户名获取用户ID
            user_id = self._get_user_id_by_username(username)
            if not user_id:
                flash(f'未找到用户名为 {username} 的用户')
                return redirect(url_for('index'))
            
            # 查询用户播放记录（同时使用user_id和username确保兼容性）
            playback_records = self._get_user_playback_records(user_id=user_id, username=username)
            # 查询用户封禁信息（同时使用user_id和username确保兼容性）
            ban_info = self._get_user_ban_info(user_id=user_id, username=username)
            # 查询用户基本信息
            user_info = self.emby_client.get_user_info(user_id)
            # 查询用户当前活跃会话（正在播放）
            active_sessions = self._get_user_active_sessions(user_id)

            return render_template('search_result.html',
                                 user_id=user_id,
                                 username=username,
                                 user_info=user_info,
                                 playback_records=playback_records,
                                 ban_info=ban_info,
                                 active_sessions=active_sessions)
        
        @self.app.route('/login', methods=['GET', 'POST'])
        def login():
            """管理员登录"""
            # 如果用户已登录，直接跳转到管理员页面
            if current_user.is_authenticated:
                return redirect(url_for('admin'))
            
            if request.method == 'POST':
                username = request.form.get('username')
                password = request.form.get('password')
                
                # 管理员认证（从配置文件读取，或使用默认密码）
                admin_username = self.config.get('web', {}).get('admin_username', 'admin')
                admin_password = self.config.get('web', {}).get('admin_password', 'admin123')
                if username == admin_username and password == admin_password:
                    user = AdminUser()
                    login_user(user)
                    return redirect(url_for('admin'))
                else:
                    flash('用户名或密码错误')
            
            return render_template('login.html')
        
        @self.app.route('/logout')
        @login_required
        def logout():
            """管理员登出"""
            logout_user()
            return redirect(url_for('index'))
        
        @self.app.route('/admin')
        @login_required
        def admin():
            """管理员页面 - 用户列表"""
            users = self._get_all_users()
            return render_template('admin.html', users=users)
        
        @self.app.route('/admin/toggle_user', methods=['POST'])
        @login_required
        def toggle_user():
            """封禁/解封用户"""
            user_id = request.form.get('user_id')
            action = request.form.get('action')
            
            if not user_id or not action:
                flash('参数错误')
                return redirect(url_for('admin'))
            
            success = False
            if action == 'ban':
                success = self.security_client.disable_user(user_id)
            elif action == 'unban':
                success = self.security_client.enable_user(user_id)
            
            if success:
                flash(f'用户已成功{"封禁" if action == "ban" else "解封"}')
            else:
                flash(f'用户{"封禁" if action == "ban" else "解封"}失败')
            
            return redirect(url_for('admin'))
        
        @self.app.route('/admin/config')
        @login_required
        def config():
            """配置编辑页面"""
            # 加载当前配置
            config = load_config()
            return render_template('config_form.html', config=config)
        
        @self.app.route('/admin/config/save', methods=['POST'])
        @login_required
        def save_config_route():
            """保存配置"""
            try:
                # 构建新的配置结构
                new_config = load_config()  # 先加载现有配置，再更新
                
                # 数据库配置已设为默认值，不可更改
                
                # 更新Emby配置
                new_config['emby']['server_url'] = request.form.get('emby_server_url')
                new_config['emby']['api_key'] = request.form.get('emby_api_key')
                new_config['emby']['check_interval'] = int(request.form.get('emby_check_interval', 10))
                
                # 更新通知配置
                new_config['notifications']['alert_threshold'] = int(request.form.get('notifications_alert_threshold', 2))
                new_config['notifications']['enable_alerts'] = request.form.get('notifications_enable_alerts') == 'on'
                
                # 更新安全配置
                new_config['security']['auto_disable'] = request.form.get('security_auto_disable') == 'on'
                whitelist = request.form.getlist('security_whitelist[]')
                # 过滤掉空字符串
                new_config['security']['whitelist'] = [user.strip() for user in whitelist if user.strip()]
                
                # 更新Webhook配置
                new_config['webhook']['enabled'] = request.form.get('webhook_enabled') == 'on'
                new_config['webhook']['url'] = request.form.get('webhook_url')
                new_config['webhook']['timeout'] = int(request.form.get('webhook_timeout', 10))
                new_config['webhook']['retry_attempts'] = int(request.form.get('webhook_retry_attempts', 3))
                
                # 更新Webhook body配置
                webhook_body = request.form.get('webhook_body', '')
                try:
                    body_config = yaml.safe_load(webhook_body)
                    if body_config is None:
                        body_config = {}
                except yaml.YAMLError as e:
                    flash(f'Webhook请求体配置格式错误：{str(e)}', 'error')
                    return redirect(url_for('config'))
                new_config['webhook']['body'] = body_config
                
                # 更新Web服务器配置
                if 'web' not in new_config:
                    new_config['web'] = {}
                new_config['web']['admin_username'] = request.form.get('web_admin_username')
                new_config['web']['admin_password'] = request.form.get('web_admin_password')
                
                # 保存配置
                if save_config(new_config):
                    flash('配置已成功保存', 'success')
                else:
                    flash('保存配置失败，请检查日志', 'error')
            
            except ValueError as e:
                flash(f'配置值错误：{str(e)}', 'error')
            except Exception as e:
                flash(f'保存配置时发生错误：{str(e)}', 'error')
            
            return redirect(url_for('config'))
    
    def _get_user_playback_records(self, user_id=None, username=None, limit=10):
        """获取用户最近的播放记录"""
        try:
            if user_id:
                return self.db_manager.get_user_playback_records(user_id, limit)
            elif username:
                return self.db_manager.get_playback_records_by_username(username, limit)
            return []
        except Exception as e:
            print(f"获取播放记录失败: {e}")
            return []

    def _get_user_active_sessions(self, user_id):
        """获取用户当前正在播放的活跃会话"""
        try:
            all_sessions = self.emby_client.get_active_sessions()
            user_sessions = []
            for session_id, session in all_sessions.items():
                if session.get('UserId') == user_id:
                    media_item = session.get('NowPlayingItem', {})
                    media_name = self.emby_client.parse_media_info(media_item)
                    ip_address = session.get('RemoteEndPoint', '未知IP').split(':')[0]
                    location = self._get_location(ip_address)
                    user_sessions.append({
                        'session_id': session_id,
                        'ip_address': ip_address,
                        'location': location,
                        'device': session.get('DeviceName', '未知设备'),
                        'client': session.get('Client', '未知客户端'),
                        'media': media_name
                    })
            return user_sessions
        except Exception as e:
            print(f"获取用户活跃会话失败: {e}")
            return []

    def _get_all_active_sessions(self):
        """获取所有正在播放的活跃会话"""
        try:
            all_sessions = self.emby_client.get_active_sessions()
            active_sessions = []
            for session_id, session in all_sessions.items():
                media_item = session.get('NowPlayingItem', {})
                media_name = self.emby_client.parse_media_info(media_item)
                ip_address = session.get('RemoteEndPoint', '未知IP').split(':')[0]
                location = self._get_location(ip_address)
                active_sessions.append({
                    'session_id': session_id,
                    'username': session.get('UserName', '未知用户'),
                    'ip_address': ip_address,
                    'location': location,
                    'device': session.get('DeviceName', '未知设备'),
                    'client': session.get('Client', '未知客户端'),
                    'media': media_name
                })
            return active_sessions
        except Exception as e:
            print(f"获取所有活跃会话失败: {e}")
            return []

    def _get_location(self, ip_address):
        """解析地理位置、运营商和IP类型"""
        if not ip_address:
            return "未知位置"

        # 使用 ip138 包查询 IP 信息
        try:
            from ip138.ip138 import ip138
            result = ip138(ip_address)

            # 检查是否获取到归属地信息
            if "归属地" in result:
                location = result["归属地"]
                isp = result.get("运营商", "")
                ip_type = result.get("iP类型", "")

                # 组合信息：归属地 | 运营商 | IP类型
                info_parts = [location]
                if isp:
                    info_parts.append(isp)
                if ip_type:
                    info_parts.append(ip_type)

                return " | ".join(info_parts)
            elif "提示" in result:
                # 可能是公共DNS，返回提示信息
                return result.get("页面标题", "未知位置")
            else:
                return "未知区域"
        except Exception as e:
            print(f"📍 解析 {ip_address} 失败: {str(e)}")
            return "解析失败"

    def _get_user_ban_info(self, user_id=None, username=None):
        """获取用户封禁信息"""
        try:
            if user_id:
                return self.db_manager.get_user_ban_info(user_id)
            elif username:
                return self.db_manager.get_ban_info_by_username(username)
            return None
        except Exception as e:
            print(f"获取封禁信息失败: {e}")
            return None
    
    def _get_user_id_by_username(self, username):
        """通过用户名获取用户ID"""
        try:
            users = self.emby_client.get_users()
            for user in users:
                if user.get('Name') == username:
                    return user.get('Id')
            return None
        except Exception as e:
            print(f"通过用户名获取用户ID失败: {e}")
            return None
    
    def _get_all_users(self):
        """获取所有用户列表"""
        try:
            # 从Emby获取所有用户
            users = self.emby_client.get_users()

            # 直接从返回数据中提取封禁状态，避免额外的API调用
            users_with_status = []
            for user in users:
                user_id = user.get('Id')
                # 直接从用户数据中获取Policy.IsDisabled，不需要额外请求
                is_disabled = user.get('Policy', {}).get('IsDisabled', False)

                users_with_status.append({
                    'id': user_id,
                    'name': user.get('Name'),
                    'is_disabled': is_disabled
                })

            return users_with_status
        except Exception as e:
            print(f"获取用户列表失败: {e}")
            return []
    
    def start(self):
        """启动Web服务器"""
        if self.running:
            return
            
        self.running = True
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        print("Web服务器已启动，访问地址: http://localhost:5000")
    
    def stop(self):
        """停止Web服务器"""
        self.running = False
        if self.server_thread:
            self.server_thread.join(timeout=5)
    
    def _run_server(self):
        """在线程中运行Flask服务器"""
        try:
            # 使用waitress作为生产级WSGI服务器
            from waitress import serve
            serve(self.app, host='0.0.0.0', port=5000, threads=10)
        except Exception as e:
            print(f"Web服务器运行错误: {e}")
            self.running = False

class AdminUser(UserMixin):
    """管理员用户类"""
    def get_id(self):
        return 'admin'