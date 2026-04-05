from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Any

import yaml
from flask import Flask, jsonify, request, send_from_directory
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user

from config_loader import load_config, save_config
from location_service import LocationService
from logger import get_logs
from session_manager import update_proxy_config

logger = logging.getLogger(__name__)


class WebServer:
    def __init__(
        self,
        db_manager,
        emby_client,
        security_client,
        config,
        location_service=None,
        monitor=None,
        tmdb_client=None,
        wish_store=None,
        shadow_library=None,
        shadow_syncer=None,
    ):
        self.db_manager = db_manager
        self.emby_client = emby_client
        self.security_client = security_client
        self.config = config
        self.tmdb_client = tmdb_client
        self.wish_store = wish_store
        self.shadow_library = shadow_library
        self.shadow_syncer = shadow_syncer

        if location_service:
            self.location_service = location_service
        else:
            use_geocache = config.get('ip_location', {}).get('use_geocache', False)
            emby_server_info = self.emby_client.get_server_info()
            self.location_service = LocationService(
                use_hiofd=use_geocache,
                db_manager=db_manager,
                emby_server_info=emby_server_info,
            )

        self.monitor = monitor

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.frontend_dist = os.path.join(base_dir, 'frontend', 'dist')
        self.frontend_assets = os.path.join(self.frontend_dist, 'assets')

        self.app = Flask(__name__, static_folder=None)
        self.app.secret_key = 'embyq_secret_key'

        self.login_manager = LoginManager()
        self.login_manager.init_app(self.app)
        self.login_manager.login_view = None

        self._register_routes()

        self.running = False
        self.server_thread = None

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
            return jsonify(
                {
                    'ok': True,
                    'frontend_built': os.path.exists(os.path.join(self.frontend_dist, 'index.html')),
                }
            )

        @self.app.post('/api/auth/login')
        def api_login():
            data = request.get_json(silent=True) or {}
            username = data.get('username', '')
            password = data.get('password', '')

            admin_username = self.config.get('web', {}).get('admin_username', 'admin')
            admin_password = self.config.get('web', {}).get('admin_password', 'admin123')

            if username == admin_username and password == admin_password:
                login_user(AdminUser())
                logger.info('管理员登录成功: username=%s', admin_username)
                return jsonify({'success': True, 'user': {'username': admin_username}})

            logger.warning('管理员登录失败: username=%s', username)
            return jsonify({'error': '用户名或密码错误'}), 401

        @self.app.post('/api/auth/logout')
        @login_required
        def api_logout():
            logger.info('管理员退出登录')
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
            for session in sessions:
                user_id = session.get('user_id')
                session['groups'] = groups_map.get(user_id, []) if user_id else []
            return jsonify({'sessions': sessions})

        @self.app.get('/api/public/search')
        def public_search():
            username = (request.args.get('username') or '').strip()
            if not username:
                return jsonify({'error': '请输入用户名'}), 400

            logger.info('公开搜索用户: username=%s', username)
            user_id = self._get_user_id_by_username(username)
            if not user_id:
                logger.warning('公开搜索未找到用户: username=%s', username)
                return jsonify({'error': f'未找到用户名为 {username} 的用户'}), 404

            playback_records = self._serialize_playback_records(
                self._get_user_playback_records(user_id=user_id, username=username)
            )
            ban_info = self._serialize_ban_info(self._get_user_ban_info(user_id=user_id, username=username))
            user_info = self.emby_client.get_user_info(user_id) or {}
            active_sessions = self._get_user_active_sessions(user_id)
            user_groups = self._get_user_groups_map().get(user_id, [])

            return jsonify(
                {
                    'user_id': user_id,
                    'username': username,
                    'user_info': user_info,
                    'user_groups': user_groups,
                    'playback_records': playback_records,
                    'ban_info': ban_info,
                    'active_sessions': active_sessions,
                }
            )

        @self.app.get('/api/public/tmdb/search')
        def public_tmdb_search():
            if not self._is_guest_request_enabled():
                return jsonify({'error': '求片功能未启用'}), 403
            if not self.tmdb_client:
                return jsonify({'error': 'TMDB 客户端未初始化'}), 503

            query = (request.args.get('q') or '').strip()
            if not query:
                return jsonify({'error': '请输入搜索关键词'}), 400

            logger.info('公开 TMDB 搜索: query=%s, page=%s', query, request.args.get('page', 1))
            try:
                page = request.args.get('page', 1)
                search_payload = self.tmdb_client.search_multi(query, page=page)
                results = search_payload.get('results') or []
                if self.wish_store and results:
                    request_map = self.wish_store.get_request_map(results)
                    for item in results:
                        season_number = 0
                        if item.get('media_type') == 'tv':
                            try:
                                season_number = max(int(item.get('season_number') or 0), 0)
                            except Exception:
                                season_number = 0
                        lookup_key = f"{item.get('media_type')}:{item.get('tmdb_id')}:{season_number}"
                        item['lookup_key'] = lookup_key
                        item['season_number'] = season_number
                        request_record = request_map.get(lookup_key)
                        item['requested'] = bool(request_record)
                        if request_record:
                            item['request_id'] = request_record.get('id')
                            item['request_status'] = request_record.get('status')
                if self.shadow_library and results:
                    for item in results:
                        tmdb_id = item.get('tmdb_id')
                        media_type = item.get('media_type')
                        shadow_records = self.shadow_library.check_tmdb(tmdb_id, media_type)
                        if shadow_records:
                            item['in_library'] = True
                            if media_type == 'tv':
                                season_records = self.shadow_library.get_series_seasons_by_tmdb(tmdb_id)
                                item['library_season_count'] = len(season_records)
                                try:
                                    tmdb_result = self.tmdb_client.get_tv_seasons(tmdb_id)
                                    tmdb_seasons = tmdb_result.get('seasons') or []
                                    item['tmdb_season_count'] = len(tmdb_seasons)
                                except Exception:
                                    item['tmdb_season_count'] = 0
                        else:
                            item['in_library'] = False
                            if media_type == 'tv':
                                item['library_season_count'] = 0
                                item['tmdb_season_count'] = 0
                return jsonify(search_payload)
            except RuntimeError as exc:
                logger.warning('TMDB 搜索运行时失败: query=%s, error=%s', query, exc)
                return jsonify({'error': str(exc)}), 503
            except Exception as exc:
                logger.exception('TMDB 搜索失败: query=%s, error=%s', query, exc)
                return jsonify({'error': f'TMDB 搜索失败: {exc}'}), 500

        @self.app.get('/api/public/tmdb/seasons')
        def public_tmdb_seasons():
            if not self._is_guest_request_enabled():
                return jsonify({'error': '求片功能未启用'}), 403
            if not self.tmdb_client:
                return jsonify({'error': 'TMDB 客户端未初始化'}), 503

            tmdb_id = request.args.get('tmdb_id')
            if not tmdb_id:
                return jsonify({'error': '缺少 tmdb_id 参数'}), 400

            logger.info('公开 TMDB 季详情查询: tmdb_id=%s', tmdb_id)

            try:
                tmdb_id_int = int(tmdb_id)
            except ValueError:
                return jsonify({'error': 'tmdb_id 参数错误'}), 400

            try:
                tmdb_result = self.tmdb_client.get_tv_seasons(tmdb_id_int)
                tmdb_seasons = tmdb_result.get('seasons') or []
                shadow_seasons = []
                if self.shadow_library:
                    shadow_seasons = self.shadow_library.get_series_seasons_by_tmdb(tmdb_id_int)
                shadow_season_numbers = {s.get('season_number') for s in shadow_seasons}
                request_map = {}
                if self.wish_store and tmdb_seasons:
                    request_map = self.wish_store.get_request_map(
                        [
                            {
                                'tmdb_id': tmdb_id_int,
                                'media_type': 'tv',
                                'season_number': season.get('season_number'),
                            }
                            for season in tmdb_seasons
                        ]
                    )
                result_seasons = []
                for season in tmdb_seasons:
                    sn = season.get('season_number')
                    in_library = sn in shadow_season_numbers
                    lookup_key = f"tv:{tmdb_id_int}:{max(int(sn or 0), 0)}"
                    request_record = request_map.get(lookup_key)
                    result_seasons.append({
                        **season,
                        'lookup_key': lookup_key,
                        'requested': bool(request_record),
                        'request_id': request_record.get('id') if request_record else None,
                        'request_status': request_record.get('status') if request_record else '',
                        'in_library': in_library,
                    })
                return jsonify({
                    'seasons': result_seasons,
                    'library_season_count': len(shadow_seasons),
                })
            except RuntimeError as exc:
                return jsonify({'error': str(exc)}), 503
            except Exception as exc:
                return jsonify({'error': f'获取季信息失败: {exc}'}), 500

        @self.app.get('/api/public/wishes')
        def public_list_wishes():
            if not self._is_guest_request_enabled():
                return jsonify({'error': '求片功能未启用'}), 403
            if not self.wish_store:
                return jsonify({'error': '求片存储未初始化'}), 503

            try:
                page = request.args.get('page', 1)
                page_size = request.args.get('page_size', 20)
                return jsonify(self.wish_store.list_public_requests(page=page, page_size=page_size))
            except Exception as exc:
                return jsonify({'error': f'获取已求列表失败: {exc}'}), 500

        @self.app.post('/api/public/wishes')
        def public_create_wish():
            if not self._is_guest_request_enabled():
                return jsonify({'error': '求片功能未启用'}), 403
            if not self.wish_store:
                return jsonify({'error': '求片存储未初始化'}), 503

            data = request.get_json(silent=True) or {}
            item = data.get('item') if isinstance(data.get('item'), dict) else data
            if not isinstance(item, dict):
                return jsonify({'error': '请求参数错误'}), 400

            logger.info(
                '公开提交求片: title=%s, media_type=%s, tmdb_id=%s, season_number=%s',
                item.get('title'),
                item.get('media_type'),
                item.get('tmdb_id'),
                item.get('season_number'),
            )
            try:
                if item.get('media_type') == 'tv':
                    try:
                        season_number = max(int(item.get('season_number') or 0), 0)
                    except Exception:
                        season_number = 0
                    if season_number == 0:
                        tmdb_id = int(item.get('tmdb_id'))
                        tmdb_seasons = (self.tmdb_client.get_tv_seasons(tmdb_id) or {}).get('seasons') or []
                        if len(tmdb_seasons) > 1:
                            return jsonify({'error': '该剧包含多季，请先选择具体季再提交求片'}), 400
                record = self.wish_store.add_request(item)
                message = '已加入想看清单' if record.get('created') else '该内容已在求片清单中'
                status_code = 201 if record.get('created') else 200
                if record.get('created') and self.monitor and self.monitor.webhook_notifier and self.monitor.webhook_notifier.is_enabled():
                    self.monitor.webhook_notifier.send(
                        'guest_request_created',
                        {
                            'request_id': record.get('id'),
                            'tmdb_id': record.get('tmdb_id'),
                            'media_type': record.get('media_type'),
                            'season_number': record.get('season_number'),
                            'title': record.get('title'),
                            'original_title': record.get('original_title'),
                            'request_status': record.get('status'),
                            'created_at': record.get('created_at'),
                            'source': 'public_request',
                        },
                    )
                logger.info(
                    '公开提交求片完成: title=%s, media_type=%s, tmdb_id=%s, season_number=%s, created=%s, request_id=%s',
                    item.get('title'),
                    item.get('media_type'),
                    item.get('tmdb_id'),
                    item.get('season_number'),
                    record.get('created'),
                    record.get('id'),
                )
                return jsonify({'success': True, 'request': record, 'message': message}), status_code
            except ValueError as exc:
                logger.warning('公开提交求片参数错误: item=%s, error=%s', item, exc)
                return jsonify({'error': str(exc)}), 400
            except Exception as exc:
                logger.exception('公开提交求片失败: item=%s, error=%s', item, exc)
                return jsonify({'error': f'保存求片失败: {exc}'}), 500

        @self.app.get('/api/public/invite/<code>')
        def public_get_invite(code):
            available, message = self.db_manager.is_invite_available(code)
            if not available:
                return jsonify({'error': message}), 404

            invite = self.db_manager.get_invite_by_code(code)
            if not invite:
                return jsonify({'error': '邀请不存在'}), 404

            return jsonify({'invite': invite})

        @self.app.post('/api/public/invite/<code>/register')
        def public_register_invite(code):
            available, message = self.db_manager.is_invite_available(code)
            if not available:
                return jsonify({'error': message}), 400

            data = request.get_json(silent=True) or {}
            username = (data.get('username') or '').strip()
            password = (data.get('password') or '').strip() or username
            if not username:
                return jsonify({'error': '请输入用户名'}), 400

            invite = self.db_manager.get_invite_by_code(code)
            if not invite:
                return jsonify({'error': '邀请不存在'}), 404

            user_id, create_error = self.emby_client.create_user(username, password)
            if create_error:
                return jsonify({'error': create_error}), 500

            try:
                if invite.get('group_id'):
                    self.db_manager.add_user_to_group(invite['group_id'], user_id)
                if invite.get('account_expiry_date'):
                    self.db_manager.set_user_expiry(user_id, invite['account_expiry_date'], False)
                self.db_manager.consume_invite(code)
            except Exception as exc:
                return jsonify({'error': f'注册成功但后续处理失败: {exc}'}), 500

            if self.monitor and self.monitor.webhook_notifier and self.monitor.webhook_notifier.is_enabled():
                self.monitor.webhook_notifier.send(
                    'invite_registered',
                    {
                        'username': username,
                        'user_id': user_id,
                        'invite_code': code,
                        'group_id': invite.get('group_id') or '',
                        'account_expiry_date': invite.get('account_expiry_date') or '',
                        'redirect_url': (self.config.get('emby', {}).get('external_url') or '').rstrip('/'),
                    },
                )

            redirect_url = (self.config.get('emby', {}).get('external_url') or '').rstrip('/')
            return jsonify({'success': True, 'redirect_url': redirect_url})

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
                if policy and not self.emby_client.set_user_policy(user_id, policy):
                    return jsonify({'error': '用户已创建，但复制模板权限失败'}), 500

            for group_id in group_ids:
                try:
                    self.db_manager.add_user_to_group(group_id, user_id)
                except Exception:
                    pass

            return jsonify({'success': True, 'user_id': user_id})

        @self.app.delete('/api/admin/users/<user_id>')
        @login_required
        def admin_delete_user(user_id):
            ok = self.emby_client.delete_user(user_id)
            if not ok:
                return jsonify({'error': '删除用户失败'}), 500
            try:
                self.db_manager.clear_user_expiry(user_id)
            except Exception:
                pass
            return jsonify({'success': True})

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
                return jsonify({'error': f'用户{"封禁" if action == "ban" else "解封"}失败'}), 500

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

        @self.app.get('/api/admin/wishes')
        @login_required
        def admin_list_wishes():
            if not self.wish_store:
                return jsonify({'error': '求片存储未初始化'}), 503
            status = (request.args.get('status') or '').strip()
            return jsonify({'requests': self.wish_store.list_requests(status=status)})

        @self.app.patch('/api/admin/wishes/<int:request_id>/status')
        @login_required
        def admin_update_wish_status(request_id):
            if not self.wish_store:
                return jsonify({'error': '求片存储未初始化'}), 503
            data = request.get_json(silent=True) or {}
            status = (data.get('status') or '').strip()
            try:
                record = self.wish_store.update_request_status(request_id, status)
                if not record:
                    return jsonify({'error': '求片记录不存在'}), 404
                return jsonify({'success': True, 'request': record})
            except ValueError as exc:
                return jsonify({'error': str(exc)}), 400
            except Exception as exc:
                return jsonify({'error': f'更新状态失败: {exc}'}), 500

        @self.app.get('/api/admin/logs')
        @login_required
        def admin_logs():
            return jsonify({'logs': get_logs()})

        @self.app.get('/api/admin/shadow/stats')
        @login_required
        def admin_shadow_stats():
            if not self.shadow_library:
                return jsonify({'error': '影子库未初始化'}), 503
            return jsonify({'stats': self.shadow_library.get_library_stats()})

        @self.app.post('/api/admin/shadow/sync')
        @login_required
        def admin_shadow_sync():
            if not self.shadow_syncer:
                return jsonify({'error': '影子库同步器未初始化'}), 503
            logger.warning('管理员触发影子库同步')
            try:
                result = self.shadow_syncer.sync_all()
                logger.warning('影子库同步完成: result=%s', result)
                if self.monitor and self.monitor.webhook_notifier and self.monitor.webhook_notifier.is_enabled():
                    self.monitor.webhook_notifier.send(
                        'shadow_sync_completed',
                        {
                            'movies_synced': ((result or {}).get('movies') or {}).get('synced', 0),
                            'movies_failed': ((result or {}).get('movies') or {}).get('failed', 0),
                            'series_synced': ((result or {}).get('series') or {}).get('synced', 0),
                            'series_failed': ((result or {}).get('series') or {}).get('failed', 0),
                            'result': result,
                        },
                    )
                return jsonify({'success': True, 'result': result})
            except Exception as exc:
                logger.exception('影子库同步失败: error=%s', exc)
                if self.monitor and self.monitor.webhook_notifier and self.monitor.webhook_notifier.is_enabled():
                    self.monitor.webhook_notifier.send(
                        'shadow_sync_failed',
                        {
                            'error': str(exc),
                        },
                    )
                return jsonify({'error': f'同步失败: {exc}'}), 500

        @self.app.get('/api/admin/shadow/movies')
        @login_required
        def admin_shadow_movies():
            if not self.shadow_library:
                return jsonify({'error': '影子库未初始化'}), 503
            page = request.args.get('page', 1)
            page_size = request.args.get('page_size', 20)
            return jsonify(self.shadow_library.get_movies(page=page, page_size=page_size))

        @self.app.get('/api/admin/shadow/series')
        @login_required
        def admin_shadow_series():
            if not self.shadow_library:
                return jsonify({'error': '影子库未初始化'}), 503
            page = request.args.get('page', 1)
            page_size = request.args.get('page_size', 20)
            return jsonify(self.shadow_library.get_series_list(page=page, page_size=page_size))

        @self.app.get('/api/admin/shadow/series/<emby_id>')
        @login_required
        def admin_shadow_series_detail(emby_id):
            if not self.shadow_library:
                return jsonify({'error': '影子库未初始化'}), 503
            detail = self.shadow_library.get_series_detail(emby_id)
            if not detail:
                return jsonify({'error': '剧集不存在'}), 404
            return jsonify(detail)

        @self.app.get('/api/admin/shadow/search')
        @login_required
        def admin_shadow_search():
            if not self.shadow_library:
                return jsonify({'error': '影子库未初始化'}), 503
            query = (request.args.get('q') or '').strip()
            media_type = (request.args.get('type') or '').strip() or None
            if not query:
                return jsonify({'error': '请输入搜索关键词'}), 400
            results = self.shadow_library.search_library(query, media_type)
            return jsonify({'results': results})

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

                old_use_geocache = self.config.get('ip_location', {}).get('use_geocache', False)
                new_use_geocache = new_config.get('ip_location', {}).get('use_geocache', False)

                if save_config(new_config):
                    self.config = load_config()
                    update_proxy_config(self.config.get('proxy', {}))
                    if old_use_geocache != new_use_geocache:
                        self.location_service.update_config(new_use_geocache)
                    if self.tmdb_client:
                        self.tmdb_client.update_config(self.config.get('tmdb', {}))
                    if self.monitor:
                        self.monitor.update_runtime_config(self.config)
                    return jsonify({'success': True})
                return jsonify({'error': '保存配置失败'}), 500
            except yaml.YAMLError as exc:
                return jsonify({'error': f'Webhook Body YAML 格式错误: {exc}'}), 400
            except Exception as exc:
                return jsonify({'error': f'保存配置时发生错误: {exc}'}), 500

        @self.app.post('/api/admin/webhook/test')
        @login_required
        def admin_test_webhook():
            if not self.monitor:
                return jsonify({'error': '监控器未初始化'}), 503
            ok = self.monitor.test_webhook()
            if ok:
                return jsonify({'success': True})
            return jsonify({'error': 'Webhook 测试发送失败，请检查 URL、超时、Body 与接收端响应'}), 500

        @self.app.get('/api/admin/groups')
        @login_required
        def admin_groups():
            return jsonify({'groups': self.db_manager.get_all_user_groups()})

        @self.app.post('/api/admin/groups')
        @login_required
        def admin_create_group():
            data = request.get_json(silent=True) or {}
            name = (data.get('name') or '').strip()
            if not name:
                return jsonify({'error': '请输入用户组名称'}), 400

            group_id = f'group_{datetime.now().strftime("%Y%m%d%H%M%S%f")}'
            try:
                self.db_manager.create_user_group(group_id, name)
                return jsonify({'success': True, 'group': {'id': group_id, 'name': name, 'members': []}})
            except Exception as exc:
                return jsonify({'error': f'创建用户组失败: {exc}'}), 500

        @self.app.delete('/api/admin/groups/<group_id>')
        @login_required
        def admin_delete_group(group_id):
            try:
                self.db_manager.delete_user_group(group_id)
                return jsonify({'success': True})
            except Exception as exc:
                return jsonify({'error': f'删除用户组失败: {exc}'}), 500

        @self.app.post('/api/admin/groups/<group_id>/members')
        @login_required
        def admin_add_group_member(group_id):
            data = request.get_json(silent=True) or {}
            user_id = (data.get('user_id') or '').strip()
            if not user_id:
                return jsonify({'error': '请选择用户'}), 400
            added = self.db_manager.add_user_to_group(group_id, user_id)
            if not added:
                return jsonify({'error': '用户已在该组中'}), 400
            return jsonify({'success': True})

        @self.app.delete('/api/admin/groups/<group_id>/members/<user_id>')
        @login_required
        def admin_remove_group_member(group_id, user_id):
            try:
                self.db_manager.remove_user_from_group(group_id, user_id)
                return jsonify({'success': True})
            except Exception as exc:
                return jsonify({'error': f'移除组成员失败: {exc}'}), 500

        @self.app.get('/api/admin/invites')
        @login_required
        def admin_list_invites():
            invites = self.db_manager.list_invites()
            service_url = (self.config.get('service', {}).get('external_url') or '').rstrip('/')
            for invite in invites:
                invite['invite_url'] = f'{service_url}/invite/{invite["code"]}' if service_url else f'/invite/{invite["code"]}'
            return jsonify({'invites': invites})

        @self.app.delete('/api/admin/invites/<code>')
        @login_required
        def admin_delete_invite(code):
            self.db_manager.delete_invite(code)
            return jsonify({'success': True})

        @self.app.post('/api/admin/invites')
        @login_required
        def admin_create_invite():
            data = request.get_json(silent=True) or {}
            valid_hours = int(data.get('valid_hours') or 24)
            max_uses = int(data.get('max_uses') or 1)
            group_id = (data.get('group_id') or '').strip() or None
            account_expiry_date = (data.get('account_expiry_date') or '').strip() or None

            try:
                invite = self.db_manager.create_invite(
                    valid_hours=valid_hours,
                    max_uses=max_uses,
                    group_id=group_id,
                    account_expiry_date=account_expiry_date,
                    created_by='admin',
                )
                service_url = (self.config.get('service', {}).get('external_url') or '').rstrip('/')
                invite_url = f'{service_url}/invite/{invite["code"]}' if service_url else f'/invite/{invite["code"]}'
                invite['invite_url'] = invite_url
                return jsonify({'success': True, 'invite': invite, 'invite_url': invite_url})
            except Exception as exc:
                return jsonify({'error': f'生成邀请链接失败: {exc}'}), 500

        @self.app.get('/assets/<path:filename>')
        def serve_assets(filename):
            return send_from_directory(self.frontend_assets, filename)

        @self.app.get('/logo.svg')
        def serve_logo():
            return send_from_directory(self.frontend_dist, 'logo.svg')

        @self.app.get('/favicon.svg')
        def serve_favicon():
            return send_from_directory(self.frontend_dist, 'favicon.svg')

        @self.app.get('/icons.svg')
        def serve_icons():
            return send_from_directory(self.frontend_dist, 'icons.svg')

        @self.app.get('/emby-upload.jpg')
        def serve_emby_upload():
            return send_from_directory(self.frontend_dist, 'emby-upload.jpg')

        @self.app.get('/VERSION')
        def serve_version():
            return send_from_directory(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'VERSION')

        @self.app.get('/ABOUT.md')
        def serve_about():
            return send_from_directory(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ABOUT.md')

        @self.app.get('/')
        def serve_home():
            return send_from_directory(self.frontend_dist, 'index.html')

        @self.app.get('/<path:path>')
        def serve_spa(path):
            if path.startswith('api/'):
                return jsonify({'error': '接口不存在'}), 404

            candidate = os.path.join(self.frontend_dist, path)
            if os.path.exists(candidate) and os.path.isfile(candidate):
                return send_from_directory(self.frontend_dist, path)
            return send_from_directory(self.frontend_dist, 'index.html')

    def start(self):
        from waitress import serve

        if self.running:
            return

        def run_server():
            serve(self.app, host='0.0.0.0', port=5000)

        self.running = True
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        logger.info('Web服务器已启动: url=http://localhost:5000')

    def _get_all_active_sessions(self):
        active_sessions = getattr(self.monitor, 'active_sessions', {}) if self.monitor else {}
        sessions = []
        for session in (active_sessions or {}).values():
            sessions.append(
                {
                    'session_id': session.get('session_id'),
                    'user_id': session.get('user_id'),
                    'username': session.get('username') or '未知用户',
                    'ip_address': session.get('ip') or '',
                    'location': session.get('location') or '未知位置',
                    'device': session.get('device') or '未知设备',
                    'client': session.get('client') or '未知客户端',
                    'media': session.get('media') or '未知内容',
                }
            )
        sessions.sort(key=lambda current: (current.get('username') or '', current.get('session_id') or ''))
        return sessions

    def _get_user_groups_map(self):
        groups = self.db_manager.get_all_user_groups() or []
        mapping = {}
        for group in groups:
            group_name = (group.get('name') or '').strip()
            if not group_name:
                continue
            for user_id in group.get('members') or []:
                mapping.setdefault(user_id, []).append(group_name)
        return mapping

    def _get_user_id_by_username(self, username):
        user = self.emby_client.get_user_by_name(username)
        return user.get('Id') if user else None

    def _get_user_playback_records(self, user_id=None, username=''):
        if user_id:
            records = self.db_manager.get_user_playback_records(user_id, limit=10)
            if records:
                return records
        if username:
            return self.db_manager.get_playback_records_by_username(username, limit=10)
        return []

    def _serialize_playback_records(self, records):
        payload = []
        for record in records or []:
            payload.append(
                {
                    'session_id': record[0],
                    'ip_address': record[1],
                    'device_name': record[2],
                    'client_type': record[3],
                    'media_name': record[4],
                    'start_time': record[5],
                    'end_time': record[6],
                    'duration': record[7],
                    'location': record[8],
                }
            )
        return payload

    def _get_user_ban_info(self, user_id=None, username=''):
        if user_id:
            record = self.db_manager.get_user_ban_info(user_id)
            if record:
                return record
        if username:
            return self.db_manager.get_ban_info_by_username(username)
        return None

    def _serialize_ban_info(self, record):
        if not record:
            return None
        return {
            'timestamp': record[0],
            'trigger_ip': record[1],
            'active_sessions': record[2],
            'action': record[3],
        }

    def _get_user_active_sessions(self, user_id):
        return [session for session in self._get_all_active_sessions() if session.get('user_id') == user_id]

    def _is_guest_request_enabled(self):
        return bool(self.config.get('guest_request', {}).get('enabled', False))

    def _get_all_users_with_expiry(self):
        groups_map = self._get_user_groups_map()
        users = []
        today = datetime.now().date()

        for user in self.emby_client.get_users() or []:
            user_id = user.get('Id')
            expiry_info = self.db_manager.get_user_expiry(user_id) or {}
            expiry_date = expiry_info.get('expiry_date') or ''
            never_expire = bool(expiry_info.get('never_expire'))
            is_expired = False

            if expiry_date and not never_expire:
                try:
                    is_expired = datetime.strptime(expiry_date, '%Y-%m-%d').date() < today
                except ValueError:
                    is_expired = False

            users.append(
                {
                    'id': user_id,
                    'name': user.get('Name') or '',
                    'groups': groups_map.get(user_id, []),
                    'is_disabled': bool((user.get('Policy') or {}).get('IsDisabled')),
                    'expiry_date': expiry_date,
                    'never_expire': never_expire,
                    'is_expired': is_expired,
                }
            )

        users.sort(key=lambda current: (current.get('name') or '').lower())
        return users


class AdminUser(UserMixin):
    id = 'admin'
