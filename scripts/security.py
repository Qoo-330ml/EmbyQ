class EmbySecurity:
    def __init__(self, emby_client):
        self.emby_client = emby_client
        self.session = emby_client.get_session()

    def disable_user(self, user_id, username=None):
        """显示用户名的禁用方法"""
        try:
            policy_url = f"{self.emby_client.server_url}/emby/Users/{user_id}/Policy"
            display_name = username or user_id
            print(f"🛡 正在禁用用户 [{display_name}] (ID: {user_id})")

            response = self.session.post(
                policy_url,
                json={"IsDisabled": True}
            )

            if response.status_code in (200, 204):
                print(f"✅ 用户 [{display_name}] 已成功禁用")
                return True

            print(f"❌ 禁用失败: HTTP {response.status_code}")
            return False

        except Exception as e:
            print(f"❌ 禁用用户 [{display_name}] 时发生错误: {str(e)}")
            return False

    def enable_user(self, user_id, username=None):
        """启用用户（带用户名显示）"""
        try:
            policy_url = f"{self.emby_client.server_url}/emby/Users/{user_id}/Policy"
            display_name = username or user_id
            print(f"🛡 正在启用用户 [{display_name}]")

            response = self.session.post(
                policy_url,
                json={"IsDisabled": False}
            )

            if response.status_code in (200, 204):
                print(f"✅ 用户 [{display_name}] 已启用")
                return True

            return False
        except Exception as e:
            print(f"❌ 启用用户失败: {str(e)}")
            return False