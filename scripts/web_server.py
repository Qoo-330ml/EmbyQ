from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta
from typing import Any

import yaml
from flask import Flask, jsonify, request, send_from_directory
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user

from config_loader import load_config, save_config
from location_service import LocationService


class WebServer:
    def __init__(self, db_manager, emby_client, security_client, config):
        self.db_manager = db_manager
        self.emby_client = emby_client
        self.security_client = security_client
        self.config = config

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.frontend_dist = os.path.join(base_dir, 'frontend', 'dist')
        self.frontend_assets = os.path.join(self.frontend_dist, 'assets')

        # 禁用 Flask 默认 static 根路由，避免与 SPA 深链接路由冲突（如 /admin/config 刷新 404）
        self.app = Flask(__name__, static_folder=None)
        self.app.secret_key = 'emby_iplimit_secret_key'

        self.login_manager = LoginManager()
        self.login_manager.init_app(self.app)
        self.login_manager.login_view = None

        self._register_routes()

        self.running = False
        self.server_thread = None
        self.location_service = LocationService()

    def _register_routes(self):
        @self.login_manager.user_loader
        def load_user(user_id):
            if user_id == 'admin':
                return AdminUser()
            return None

        @self.login_manager.unauthorized_handler
        def unauthorized():
            return jsonify({'error': '未登录或登录已失效'}), 401

        @self.app.get('/api/health')
        def health():
            return jsonify({
                'ok': True,
                'frontend_built': os.path.exists(os.path.join(self.frontend_dist, 'index.html')),
            })

        @self.app.post('/api/auth/login')
        def api_login():
            data = request.get_json(silent=True) or {}
            username = data.get('username', '')
            password = data.get('password', '')

            admin_username = self.config.get('web', {}).get('admin_username', 'admin')
            admin_password = self.config.get('web', {}).get('admin_password', 'admin123')

            if username == admin_username and password == admin_password:
                login_user(AdminUser())
                return jsonify({'success': True, 'user': {'username': admin_username}})

            return jsonify({'error': '用户名或密码错误'}), 401

        @self.app.post('/api/auth/logout')
        @login_required
        def api_logout():
            logout_user()
            return jsonify({'success': True})

        @self.app.get('/api/auth/me')
        def api_me():
            if current_user.is_authenticated:
                return jsonify({'authenticated': True, 'user': {'username': 'admin'}})
            return jsonify({'authenticated': False})

        @self.app.get('/api/public/active-sessions')
        def public_active_sessions():
            sessions = self._get_all_active_sessions()
            groups_map = self._get_user_groups_map()
            for s in sessions:
                user_id = s.get('user_id')
                s['groups'] = groups_map.get(user_id, []) if user_id else []
            return jsonify({'sessions': sessions})

        @self.app.get('/api/public/search')
        def public_search():
            username = (request.args.get('username') or '').strip()
            if not username:
                return jsonify({'error': '请输入用户名'}), 400

            user_id = self._get_user_id_by_username(username)
            if not user_id:
                return jsonify({'error': f'未找到用户名为 {username} 的用户'}), 404

            playback_records = self._serialize_playback_records(
                self._get_user_playback_records(user_id=user_id, username=username)
            )
            ban_info = self._serialize_ban_info(self._get_user_ban_info(user_id=user_id, username=username))
            user_info = self.emby_client.get_user_info(user_id) or {}
            active_sessions = self._get_user_active_sessions(user_id)
            user_groups = self._get_user_groups_map().get(user_id, [])

            return jsonify({
                'user_id': user_id,
                'username': username,
                'user_info': user_info,
                'user_groups': user_groups,
                'playback_records': playback_records,
                'ban_info': ban_info,
                'active_sessions': active_sessions,
            })

        @self.app.get('/api/admin/users')
        @login_required
        def admin_users():
            users = self._get_all_users_with_expiry()
            stats = {
                'total': len(users),
                'disabled': sum(1 for user in users if user.get('is_disabled')),
                'expired': sum(1 for user in users if user.get('is_expired')),
                'never_expire': sum(1 for user in users if user.get('never_expire')),
            }
            return jsonify({'users': users, 'stats': stats})

        @self.app.post('/api/admin/users/create')
        @login_required
        def admin_create_user():
            data = request.get_json(silent=True) or {}
            username = (data.get('username') or '').strip()
            password = (data.get('password') or '').strip() or username
            template_user_id = (data.get('template_user_id') or '').strip()
            group_ids = data.get('group_ids') or []

            if not username:
                return jsonify({'error': '请输入用户名'}), 400

            user_id, error = self.emby_client.create_user(username, password)
            if error:
                return jsonify({'error': error}), 500

            if template_user_id:
                policy = self.emby_client.get_user_policy(template_user_id)
                if policy:
                    if not self.emby_client.set_user_policy(user_id, policy):
                        return jsonify({'error': '用户已创建，但复制模板权限失败'}), 500

            for group_id in group_ids:
                try:
                    self.db_manager.add_user_to_group(group_id, user_id)
                except Exception:
                    pass

            return jsonify({'success': True, 'user_id': user_id})

        @self.app.post('/api/admin/users/toggle')
        @login_required
        def admin_toggle_user():
            data = request.get_json(silent=True) or {}
            user_id = data.get('user_id')
            action = data.get('action')
            if not user_id or action not in {'ban', 'unban'}:
                return jsonify({'error': '参数错误'}), 400

            success = self.security_client.disable_user(user_id) if action == 'ban' else self.security_client.enable_user(user_id)
            if not success:
                return jsonify({'error': f'用户{ "封禁" if action == "ban" else "解封" }失败'}), 500

            return jsonify({'success': True})

        @self.app.post('/api/admin/users/expiry')
        @login_required
        def admin_set_user_expiry():
            data = request.get_json(silent=True) or {}
            user_id = data.get('user_id')
            expiry_date = (data.get('expiry_date') or '').strip()
            never_expire = bool(data.get('never_expire', False))

            if not user_id:
                return jsonify({'error': '参数错误'}), 400

            try:
                if never_expire:
                    self.db_manager.set_user_never_expire(user_id, True)
                    return jsonify({'success': True, 'message': '用户已设置为永不过期'})

                if expiry_date:
                    datetime.strptime(expiry_date, '%Y-%m-%d')
                    self.db_manager.set_user_expiry(user_id, expiry_date, False)
                    return jsonify({'success': True, 'message': f'用户到期时间已设置为 {expiry_date}'})

                self.db_manager.clear_user_expiry(user_id)
                return jsonify({'success': True, 'message': '用户到期时间已清除'})
            except ValueError:
                return jsonify({'error': '日期格式错误，应为 YYYY-MM-DD'}), 400
            except Exception as exc:
                return jsonify({'error': f'设置到期时间失败: {exc}'}), 500

        @self.app.post('/api/admin/users/batch_expiry')
        @login_required
        def admin_batch_expiry():
            data = request.get_json(silent=True) or {}
            user_ids = data.get('user_ids') or []
            days = data.get('days')
            target_date = (data.get('target_date') or '').strip()

            if not user_ids:
                return jsonify({'error': '请选择用户'}), 400

            try:
                success_count = 0
                fail_count = 0
                for user_id in user_ids:
                    try:
                        if target_date:
                            datetime.strptime(target_date, '%Y-%m-%d')
                            self.db_manager.set_user_expiry(user_id, target_date, False)
                        else:
                            days_int = int(days)
                            current_expiry = self.db_manager.get_user_expiry(user_id)
                            if current_expiry and current_expiry.get('expiry_date'):
                                current_date = datetime.strptime(current_expiry['expiry_date'], '%Y-%m-%d')
                            else:
                                current_date = datetime.now()
                            new_date = current_date + timedelta(days=days_int)
                            self.db_manager.set_user_expiry(user_id, new_date.strftime('%Y-%m-%d'), False)
                        success_count += 1
                    except Exception:
                        fail_count += 1

                return jsonify({'success': True, 'success_count': success_count, 'fail_count': fail_count})
            except Exception as exc:
                return jsonify({'error': f'批量设置到期时间失败: {exc}'}), 500

        @self.app.post('/api/admin/users/batch_clear_expiry')
        @login_required
        def admin_batch_clear_expiry():
            data = request.get_json(silent=True) or {}
            user_ids = data.get('user_ids') or []
            if not user_ids:
                return jsonify({'error': '请选择用户'}), 400

            success_count = 0
            fail_count = 0
            for user_id in user_ids:
                try:
                    self.db_manager.clear_user_expiry(user_id)
                    success_count += 1
                except Exception:
                    fail_count += 1

            return jsonify({'success': True, 'success_count': success_count, 'fail_count': fail_count})

        @self.app.post('/api/admin/users/batch_never_expire')
        @login_required
        def admin_batch_never_expire():
            data = request.get_json(silent=True) or {}
            user_ids = data.get('user_ids') or []
            cancel = bool(data.get('cancel', False))
            if not user_ids:
                return jsonify({'error': '请选择用户'}), 400

            success_count = 0
            fail_count = 0
            for user_id in user_ids:
                try:
                    self.db_manager.set_user_never_expire(user_id, not cancel)
                    success_count += 1
                except Exception:
                    fail_count += 1

            return jsonify({'success': True, 'success_count': success_count, 'fail_count': fail_count})

        @self.app.post('/api/admin/users/batch_toggle')
        @login_required
        def admin_batch_toggle():
            data = request.get_json(silent=True) or {}
            user_ids = data.get('user_ids') or []
            action = data.get('action')
            if not user_ids or action not in {'ban', 'unban'}:
                return jsonify({'error': '参数错误'}), 400

            success_count = 0
            fail_count = 0
            for user_id in user_ids:
                ok = self.security_client.disable_user(user_id) if action == 'ban' else self.security_client.enable_user(user_id)
                if ok:
                    success_count += 1
                else:
                    fail_count += 1

            return jsonify({'success': True, 'success_count': success_count, 'fail_count': fail_count})

        @self.app.get('/api/admin/config')
        @login_required
        def admin_get_config():
            return jsonify({'config': load_config()})

        @self.app.put('/api/admin/config')
        @login_required
        def admin_save_config():
            data = request.get_json(silent=True) or {}
            new_config = data.get('config')
            if not isinstance(new_config, dict):
                return jsonify({'error': '配置格式错误'}), 400

            try:
                if new_config.get('webhook', {}).get('body') and isinstance(new_config['webhook']['body'], str):
                    new_config['webhook']['body'] = yaml.safe_load(new_config['webhook']['body']) or {}

                if 'web' not in new_config:
                    new_config['web'] = {}

                if save_config(new_config):
                    self.config = load_config()
                    return jsonify({'success': True})
                return jsonify({'error': '保存配置失败'}), 500
            except yaml.YAMLError as exc:
                return jsonify({'error': f'Webhook Body YAML 格式错误: {exc}'}), 400
            except Exception as exc:
                return jsonify({'error': f'保存配置时发生错误: {exc}'}), 500

        @self.app.get('/api/admin/groups')
        @login_required
        def admin_groups():
            return jsonify({'groups': self.db_manager.get_all_user_groups()})

        @self.app.post('/api/admin/invites')
        @login_required
        def admin_create_invite():
            data = request.get_json(silent=True) or {}
            valid_hours = int(data.get('valid_hours') or 24)
            max_uses = int(data.get('max_uses') or 1)
            group_id = (data.get('group_id') or '').strip() or None
            account_expiry_date = (data.get('account_expiry_date') or '').strip() or None

            if valid_hours <= 0 or max_uses <= 0:
                return jsonify({'error': '参数错误'}), 400

            try:
                invite = self.db_manager.create_invite(
                    valid_hours=valid_hours,
                    max_uses=max_uses,
                    group_id=group_id,
                    account_expiry_date=account_expiry_date,
                    created_by='admin',
                )
            except Exception as exc:
                return jsonify({'error': str(exc)}), 500

            service_url = (self.config.get('service', {}).get('external_url') or '').rstrip('/')
            invite_url = f"{service_url}/invite/{invite['code']}" if service_url else f"/invite/{invite['code']}"

            return jsonify({'invite': invite, 'invite_url': invite_url})

        @self.app.post('/api/admin/groups')
        @login_required
        def admin_create_group():
            data = request.get_json(silent=True) or {}
            name = (data.get('name') or '').strip()
            group_id = (data.get('group_id') or f'group_{int(datetime.now().timestamp() * 1000)}').strip()
            if not name:
                return jsonify({'error': '请输入用户组名称'}), 400
            try:
                self.db_manager.create_user_group(group_id, name)
                return jsonify({'success': True, 'group_id': group_id})
            except Exception as exc:
                return jsonify({'error': str(exc)}), 500

        @self.app.delete('/api/admin/groups/<group_id>')
        @login_required
        def admin_delete_group(group_id):
            try:
                self.db_manager.delete_user_group(group_id)
                return jsonify({'success': True})
            except Exception as exc:
                return jsonify({'error': str(exc)}), 500

        @self.app.post('/api/admin/groups/<group_id>/members')
        @login_required
        def admin_add_group_member(group_id):
            data = request.get_json(silent=True) or {}
            user_id = data.get('user_id')
            if not user_id:
                return jsonify({'error': '参数错误'}), 400
            try:
                result = self.db_manager.add_user_to_group(group_id, user_id)
                if result:
                    return jsonify({'success': True})
                return jsonify({'error': '成员已在组中'}), 400
            except Exception as exc:
                return jsonify({'error': str(exc)}), 500

        @self.app.delete('/api/admin/groups/<group_id>/members/<user_id>')
        @login_required
        def admin_remove_group_member(group_id, user_id):
            try:
                self.db_manager.remove_user_from_group(group_id, user_id)
                return jsonify({'success': True})
            except Exception as exc:
                return jsonify({'error': str(exc)}), 500

        @self.app.get('/api/public/invite/<code>')
        def public_invite_info(code):
            available, message = self.db_manager.is_invite_available(code)
            if not available:
                return jsonify({'error': message}), 400
            invite = self.db_manager.get_invite_by_code(code)
            return jsonify({'invite': invite})

        @self.app.post('/api/public/invite/<code>/register')
        def public_invite_register(code):
            data = request.get_json(silent=True) or {}
            username = (data.get('username') or '').strip()
            password = (data.get('password') or '').strip() or username

            if not username:
                return jsonify({'error': '请输入用户名'}), 400

            available, message = self.db_manager.is_invite_available(code)
            if not available:
                return jsonify({'error': message}), 400

            user_id, error = self.emby_client.create_user(username, password)
            if error:
                return jsonify({'error': error}), 500

            invite = self.db_manager.get_invite_by_code(code)
            if invite and invite.get('group_id'):
                try:
                    self.db_manager.add_user_to_group(invite['group_id'], user_id)
                except Exception:
                    pass

            if invite and invite.get('account_expiry_date'):
                try:
                    self.db_manager.set_user_expiry(user_id, invite['account_expiry_date'], False)
                except Exception:
                    pass

            self.db_manager.consume_invite(code)

            redirect_url = (self.config.get('emby', {}).get('external_url') or '').strip() or \
                (self.config.get('emby', {}).get('server_url') or '').strip()

            return jsonify({'success': True, 'redirect_url': redirect_url})

        @self.app.get('/assets/<path:filename>')
        def serve_assets(filename):
            return send_from_directory(self.frontend_assets, filename)

        @self.app.get('/', defaults={'path': ''})
        @self.app.get('/<path:path>')
        def serve_spa(path):
            if path.startswith('api/'):
                return jsonify({'error': '接口不存在'}), 404

            target = os.path.join(self.frontend_dist, path)
            if path and os.path.exists(target) and os.path.isfile(target):
                return send_from_directory(self.frontend_dist, path)

            index_file = os.path.join(self.frontend_dist, 'index.html')
            if os.path.exists(index_file):
                return send_from_directory(self.frontend_dist, 'index.html')

            return jsonify({
                'error': '前端尚未构建，请先在 frontend 目录执行 npm run build',
                'frontend_dist': self.frontend_dist,
            }), 503

    def _get_user_groups_map(self):
        """构建用户ID -> 组名列表映射"""
        mapping = {}
        try:
            for group in self.db_manager.get_all_user_groups():
                group_name = group.get('name')
                for uid in group.get('members', []):
                    mapping.setdefault(uid, []).append(group_name)
        except Exception:
            return {}
        return mapping

    def _serialize_playback_records(self, rows: list[Any]):
        records = []
        for row in rows or []:
            records.append({
                'session_id': row[0],
                'ip_address': row[1],
                'device_name': row[2],
                'client_type': row[3],
                'media_name': row[4],
                'start_time': row[5],
                'end_time': row[6],
                'duration': row[7],
                'location': row[8],
            })
        return records

    def _serialize_ban_info(self, row: Any):
        if not row:
            return None
        return {
            'timestamp': row[0],
            'trigger_ip': row[1],
            'active_sessions': row[2],
            'action': row[3],
        }

    def _get_user_playback_records(self, user_id=None, username=None, limit=10):
        try:
            if user_id:
                return self.db_manager.get_user_playback_records(user_id, limit)
            if username:
                return self.db_manager.get_playback_records_by_username(username, limit)
            return []
        except Exception as exc:
            print(f'获取播放记录失败: {exc}')
            return []

    def _get_user_active_sessions(self, user_id):
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
                        'media': media_name,
                    })
            return user_sessions
        except Exception as exc:
            print(f'获取用户活跃会话失败: {exc}')
            return []

    def _get_all_active_sessions(self):
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
                    'user_id': session.get('UserId'),
                    'username': session.get('UserName', '未知用户'),
                    'ip_address': ip_address,
                    'location': location,
                    'device': session.get('DeviceName', '未知设备'),
                    'client': session.get('Client', '未知客户端'),
                    'media': media_name,
                })
            return active_sessions
        except Exception as exc:
            print(f'获取所有活跃会话失败: {exc}')
            return []

    def _get_location(self, ip_address):
        if not ip_address:
            return '未知位置'

        try:
            info = self.location_service.lookup(ip_address)
            return info.get('formatted', '未知位置')
        except Exception as exc:
            print(f'📍 解析 {ip_address} 失败: {exc}')
            return '解析失败'

    def _get_user_ban_info(self, user_id=None, username=None):
        try:
            if user_id:
                return self.db_manager.get_user_ban_info(user_id)
            if username:
                return self.db_manager.get_ban_info_by_username(username)
            return None
        except Exception as exc:
            print(f'获取封禁信息失败: {exc}')
            return None

    def _get_user_id_by_username(self, username):
        try:
            users = self.emby_client.get_users()
            for user in users:
                if user.get('Name') == username:
                    return user.get('Id')
            return None
        except Exception as exc:
            print(f'通过用户名获取用户ID失败: {exc}')
            return None

    def _get_all_users_with_expiry(self):
        try:
            users = self.emby_client.get_users()
            user_groups = self.db_manager.get_all_user_groups()
            user_group_map = {}
            for group in user_groups:
                for member_id in group.get('members', []):
                    user_group_map.setdefault(member_id, []).append(group['name'])

            users_with_status = []
            for user in users:
                user_id = user.get('Id')
                is_disabled = user.get('Policy', {}).get('IsDisabled', False)
                expiry_info = self.db_manager.get_user_expiry(user_id)
                expiry_date = expiry_info.get('expiry_date') if expiry_info else None
                never_expire = expiry_info.get('never_expire', False) if expiry_info else False

                is_expired = False
                if expiry_date and not never_expire:
                    try:
                        expiry = datetime.strptime(expiry_date, '%Y-%m-%d')
                        if expiry.date() < datetime.now().date():
                            is_expired = True
                    except Exception:
                        pass

                users_with_status.append({
                    'id': user_id,
                    'name': user.get('Name'),
                    'is_disabled': is_disabled,
                    'expiry_date': expiry_date,
                    'is_expired': is_expired,
                    'never_expire': never_expire,
                    'groups': user_group_map.get(user_id, []),
                })
            return users_with_status
        except Exception as exc:
            print(f'获取用户列表失败: {exc}')
            return []

    def start(self):
        if self.running:
            return

        self.running = True
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        print('Web服务器已启动，访问地址: http://localhost:5000')

    def stop(self):
        self.running = False
        if self.server_thread:
            self.server_thread.join(timeout=5)

    def _run_server(self):
        try:
            from waitress import serve

            serve(self.app, host='0.0.0.0', port=5000, threads=10)
        except Exception as exc:
            print(f'Web服务器运行错误: {exc}')
            self.running = False


class AdminUser(UserMixin):
    def get_id(self):
        return 'admin'
