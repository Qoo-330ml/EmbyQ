import copy

import requests


class EmbyClient:
    def __init__(self, server_url, api_key):
        self.server_url = server_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({'X-Emby-Token': self.api_key})

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
