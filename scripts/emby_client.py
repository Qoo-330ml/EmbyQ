import copy

import requests


class EmbyClient:
    def __init__(self, server_url, api_key):
        self.server_url = server_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({'X-Emby-Token': self.api_key})

    def get_session(self):
        return self.session

    def get_user_info(self, user_id):
        try:
            response = self.session.get(
                f"{self.server_url}/emby/Users/{user_id}",
                timeout=3
            )
            return response.json()
        except Exception as e:
            print(f"获取用户信息失败: {str(e)}")
            return {}

    def get_user_policy(self, user_id):
        try:
            response = self.session.get(
                f"{self.server_url}/emby/Users/{user_id}/Policy",
                timeout=5
            )
            if response.status_code != 200:
                return {}
            return response.json() or {}
        except Exception as e:
            print(f"获取用户策略失败: {str(e)}")
            return {}

    def set_user_policy(self, user_id, policy):
        try:
            clean_policy = copy.deepcopy(policy or {})
            # 保险起见移除少量只读字段
            for key in ('Id', 'UserId', 'Name'):
                clean_policy.pop(key, None)

            response = self.session.post(
                f"{self.server_url}/emby/Users/{user_id}/Policy",
                json=clean_policy,
                timeout=8,
            )
            return response.status_code in (200, 204)
        except Exception as e:
            print(f"设置用户策略失败: {str(e)}")
            return False

    def set_user_password(self, user_id, password):
        try:
            payload = {
                'CurrentPw': '',
                'CurrentPassword': '',
                'NewPw': password,
                'NewPassword': password,
                'ResetPassword': False,
            }
            response = self.session.post(
                f"{self.server_url}/emby/Users/{user_id}/Password",
                json=payload,
                timeout=8,
            )
            return response.status_code in (200, 204)
        except Exception as e:
            print(f"设置用户密码失败: {str(e)}")
            return False

    def create_user(self, username, password):
        username = (username or '').strip()
        if not username:
            return None, '用户名不能为空'

        try:
            response = self.session.post(
                f"{self.server_url}/emby/Users/New",
                params={'Name': username},
                timeout=8,
            )
            if response.status_code not in (200, 201, 204):
                return None, f'创建用户失败: HTTP {response.status_code}'

            user_data = response.json() if response.text else {}
            user_id = user_data.get('Id')

            if not user_id:
                # 兼容部分实例不返回 body，回查用户列表
                user = self.get_user_by_name(username)
                user_id = user.get('Id') if user else None

            if not user_id:
                return None, '创建用户成功但未获取到用户ID'

            if not self.set_user_password(user_id, password):
                return None, '用户已创建，但设置密码失败'

            return user_id, ''
        except Exception as e:
            return None, f'创建用户异常: {str(e)}'

    def get_user_by_name(self, username):
        target = (username or '').strip().lower()
        if not target:
            return None
        for user in self.get_users():
            if str(user.get('Name') or '').strip().lower() == target:
                return user
        return None

    def get_active_sessions(self):
        try:
            response = self.session.get(
                f"{self.server_url}/emby/Sessions",
                timeout=5
            )
            return {s['Id']: s for s in response.json() if s.get('NowPlayingItem')}
        except Exception as e:
            print(f"获取会话失败: {str(e)}")
            return {}

    @staticmethod
    def parse_media_info(item):
        if not item:
            return "未知内容"
        if item.get('SeriesName'):
            return f"{item['SeriesName']} S{item['ParentIndexNumber']}E{item['IndexNumber']}"
        return item.get('Name', '未知内容')

    def get_users(self):
        """获取所有用户列表"""
        try:
            response = self.session.get(
                f"{self.server_url}/emby/Users",
                timeout=5
            )
            return response.json()
        except Exception as e:
            print(f"获取用户列表失败: {str(e)}")
            return []

    def delete_user(self, user_id):
        try:
            response = self.session.delete(
                f"{self.server_url}/emby/Users/{user_id}",
                timeout=8,
            )
            return response.status_code in (200, 204)
        except Exception as e:
            print(f"删除用户失败: {str(e)}")
            return False

    def get_server_info(self):
        """获取Emby服务器信息"""
        try:
            response = self.session.get(
                f"{self.server_url}/emby/System/Info",
                timeout=5
            )
            return response.json()
        except Exception as e:
            print(f"获取服务器信息失败: {str(e)}")
            return {}

    def get_library_views(self):
        """获取媒体库视图（电影、剧集等）"""
        try:
            response = self.session.get(
                f"{self.server_url}/emby/Views",
                timeout=10
            )
            return response.json().get('Items') or []
        except Exception as e:
            print(f"获取媒体库视图失败: {str(e)}")
            return []

    def get_library_items(self, parent_id=None, include_item_types=None, recursive=True, fields=None):
        """获取媒体库项目列表

        Args:
            parent_id: 父级ID（媒体库/文件夹ID）
            include_item_types: 项目类型，如 'Movie', 'Series', 'Episode'
            recursive: 是否递归获取
            fields: 需要返回的字段列表
        """
        try:
            params = {
                'Recursive': str(recursive).lower()
            }
            if parent_id:
                params['ParentId'] = parent_id
            if include_item_types:
                params['IncludeItemTypes'] = include_item_types
            if fields:
                params['Fields'] = fields

            response = self.session.get(
                f"{self.server_url}/emby/Items",
                params=params,
                timeout=30
            )
            return response.json().get('Items') or []
        except Exception as e:
            print(f"获取媒体库项目失败: {str(e)}")
            return []

    def get_movies(self, fields=None):
        """获取所有电影 - 只获取基本信息"""
        fields = fields or 'ProviderIds,ProductionYear,Status'
        return self.get_library_items(include_item_types='Movie', fields=fields)

    def get_series_list(self, fields=None):
        """获取所有剧集列表（不包含季和集） - 只获取基本信息"""
        fields = fields or 'ProviderIds,ProductionYear,Status,RecursiveItemCount'
        return self.get_library_items(include_item_types='Series', fields=fields)

    def get_series_seasons(self, series_id, fields=None):
        """获取剧集的季列表 - 只获取基本信息"""
        try:
            fields = fields or 'EpisodeCount,PremiereDate'
            response = self.session.get(
                f"{self.server_url}/emby/Shows/{series_id}/Seasons",
                params={'Fields': fields},
                timeout=15
            )
            return response.json().get('Items') or []
        except Exception as e:
            print(f"获取季列表失败: {str(e)}")
            return []

    def get_season_episodes(self, series_id, season_id, fields=None):
        """获取指定季的所有剧集 - 只获取基本信息"""
        try:
            fields = fields or 'PremiereDate,SortOrder'
            response = self.session.get(
                f"{self.server_url}/emby/Shows/{series_id}/Episodes",
                params={
                    'seasonId': season_id,
                    'Fields': fields
                },
                timeout=15
            )
            return response.json().get('Items') or []
        except Exception as e:
            print(f"获取剧集列表失败: {str(e)}")
            return []

    def get_all_series_episodes(self, series_id, fields=None):
        """递归获取剧集的所有季和集 - 只获取基本信息"""
        try:
            fields = fields or 'PremiereDate,SortOrder'
            response = self.session.get(
                f"{self.server_url}/emby/Shows/{series_id}/Episodes",
                params={
                    'Fields': fields
                },
                timeout=30
            )
            return response.json().get('Items') or []
        except Exception as e:
            print(f"获取全部剧集失败: {str(e)}")
            return []
