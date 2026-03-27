# 导入必要的模块
import os      # 用于文件路径和目录操作
import secrets # 用于生成安全的随机邀请码
import sqlite3 # 用于操作SQLite数据库
import string  # 用于生成邀请码的字符集
from datetime import datetime, timedelta  # 用于处理日期和时间


def get_data_dir():
    """获取data目录路径
    
    通过获取当前文件的绝对路径，然后向上两级目录，再添加data目录，得到data目录的路径
    例如：如果当前文件是 scripts/database.py，那么data目录就是 EmbyQ/data/
    """
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')


class DatabaseManager:
    """数据库管理器类，用于处理所有与数据库相关的操作"""
    
    def __init__(self, db_name=None):
        """初始化数据库管理器
        
        Args:
            db_name: 数据库文件名，如果不指定则使用默认名称 'emby_playback.db'
        """
        # 获取data目录路径
        data_dir = get_data_dir()
        # 确保data目录存在，如果不存在则创建
        os.makedirs(data_dir, exist_ok=True)

        # 从配置获取数据库名称
        self.db_path = os.path.join(data_dir, db_name) if db_name else os.path.join(data_dir, 'emby_playback.db')
        # 初始化数据库结构
        self.init_db()

    def init_db(self):
        """初始化数据库结构
        
        创建所有必要的数据库表，包括：
        1. playback_history: 播放历史表
        2. security_log: 安全日志表
        3. user_expiry: 用户到期时间表
        4. user_groups: 用户组表
        5. user_group_members: 用户组成员表
        6. invites: 邀请链接表
        7. ip_location_cache: IP归属地缓存表
        
        同时处理表结构的自动迁移，确保旧版本数据库也能正常使用
        """
        # 连接到SQLite数据库
        with sqlite3.connect(self.db_path) as conn:
            # 播放历史表：记录用户的播放会话信息
            conn.execute('''
                CREATE TABLE IF NOT EXISTS playback_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
                    session_id TEXT NOT NULL,  -- 会话ID
                    user_id TEXT NOT NULL,  -- 用户ID
                    username TEXT NOT NULL,  -- 用户名
                    ip_address TEXT NOT NULL,  -- IP地址
                    device_name TEXT,  -- 设备名称
                    client_type TEXT,  -- 客户端类型
                    media_name TEXT,  -- 媒体名称
                    start_time DATETIME NOT NULL,  -- 开始时间
                    end_time DATETIME,  -- 结束时间
                    duration INTEGER,  -- 播放时长（秒）
                    location TEXT  -- 位置信息
                )
            ''')

            # 安全日志表（带自动迁移）：记录安全相关的事件
            conn.execute('''
                CREATE TABLE IF NOT EXISTS security_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
                    timestamp DATETIME,  -- 时间戳
                    user_id TEXT,  -- 用户ID
                    username TEXT,  -- 用户名
                    trigger_ip TEXT,  -- 触发IP
                    active_sessions INTEGER,  -- 活跃会话数
                    action TEXT  -- 执行的操作
                )
            ''')

            # 自动迁移：如果security_log表没有username字段，则添加
            try:
                cursor = conn.execute("PRAGMA table_info(security_log)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'username' not in columns:
                    conn.execute('ALTER TABLE security_log ADD COLUMN username TEXT')
            except sqlite3.OperationalError:
                pass

            # 用户到期时间表（支持永不过期）：管理用户账号的过期时间
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_expiry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
                    user_id TEXT NOT NULL UNIQUE,  -- 用户ID（唯一）
                    expiry_date DATE,  -- 到期日期
                    never_expire INTEGER DEFAULT 0,  -- 是否永不过期（0=否，1=是）
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP  -- 更新时间
                )
            ''')

            # 自动迁移：如果user_expiry表没有never_expire字段，则添加
            try:
                conn.execute('SELECT never_expire FROM user_expiry LIMIT 1')
            except sqlite3.OperationalError:
                conn.execute('ALTER TABLE user_expiry ADD COLUMN never_expire INTEGER DEFAULT 0')
                conn.commit()

            # 用户组表：管理用户组信息
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
                    group_id TEXT NOT NULL UNIQUE,  -- 组ID（唯一）
                    name TEXT NOT NULL,  -- 组名称
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP  -- 更新时间
                )
            ''')

            # 用户组成员表：管理用户组的成员
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_group_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
                    group_id TEXT NOT NULL,  -- 组ID
                    user_id TEXT NOT NULL,  -- 用户ID
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
                    UNIQUE(group_id, user_id)  -- 确保每个用户在每个组中只存在一次
                )
            ''')

            # 邀请链接表：管理用户邀请码
            conn.execute('''
                CREATE TABLE IF NOT EXISTS invites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
                    code TEXT NOT NULL UNIQUE,  -- 邀请码（唯一）
                    expires_at DATETIME NOT NULL,  -- 过期时间
                    max_uses INTEGER NOT NULL,  -- 最大使用次数
                    used_count INTEGER DEFAULT 0,  -- 已使用次数
                    group_id TEXT,  -- 关联的用户组ID
                    account_expiry_date DATE,  -- 账号过期日期
                    is_active INTEGER DEFAULT 1,  -- 是否有效（0=无效，1=有效）
                    created_by TEXT,  -- 创建者
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP  -- 更新时间
                )
            ''')

            # IP归属地缓存表：缓存IP地址的地理位置信息
            conn.execute('''
                CREATE TABLE IF NOT EXISTS ip_location_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
                    ip_address TEXT NOT NULL UNIQUE,  -- IP地址（唯一）
                    provider TEXT NOT NULL,  -- 数据提供方
                    location TEXT,  -- 位置信息
                    district TEXT,  -- 区域
                    street TEXT,  -- 街道
                    isp TEXT,  -- 互联网服务提供商
                    latitude REAL,  -- 纬度
                    longitude REAL,  -- 经度
                    formatted TEXT,  -- 格式化的位置信息
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP  -- 更新时间
                )
            ''')

            # 提交所有更改
            conn.commit()

    def record_session_start(self, session_data):
        """记录会话开始
        
        Args:
            session_data: 会话数据字典，包含以下键：
                - session_id: 会话ID
                - user_id: 用户ID
                - username: 用户名
                - ip: IP地址
                - device: 设备名称
                - client: 客户端类型
                - media: 媒体名称
                - start_time: 开始时间（datetime对象）
                - location: 位置信息（可选）
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO playback_history (
                    session_id, user_id, username, ip_address,
                    device_name, client_type, media_name,
                    start_time, location
                ) VALUES (?,?,?,?,?,?,?,?,?)
            ''', (
                session_data['session_id'],
                session_data['user_id'],
                session_data['username'],
                session_data['ip'],
                session_data['device'],
                session_data['client'],
                session_data['media'],
                session_data['start_time'].strftime('%Y-%m-%d %H:%M:%S'),  # 格式化时间为字符串
                session_data.get('location', '未知位置')  # 如果没有位置信息，使用默认值
            ))
            conn.commit()

    def get_user_playback_records(self, user_id, limit=10):
        """获取用户的播放记录
        
        Args:
            user_id: 用户ID
            limit: 返回记录的数量限制，默认10条
        
        Returns:
            播放记录列表，每条记录包含会话ID、IP地址、设备名称、客户端类型、媒体名称、开始时间、结束时间、播放时长和位置信息
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT session_id, ip_address, device_name, client_type, media_name,
                       start_time, end_time, duration, location
                FROM playback_history
                WHERE user_id = ? AND end_time IS NOT NULL  -- 只返回已结束的会话
                ORDER BY start_time DESC  -- 按开始时间降序排列
                LIMIT ?
            ''', (user_id, limit))
            return cursor.fetchall()

    def get_user_ban_info(self, user_id):
        """获取用户的封禁信息
        
        Args:
            user_id: 用户ID
        
        Returns:
            最近一次的封禁记录，包含时间戳、触发IP、活跃会话数和操作
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT timestamp, trigger_ip, active_sessions, action
                FROM security_log
                WHERE user_id = ? AND action = 'DISABLE'  -- 只返回禁用操作
                ORDER BY timestamp DESC  -- 按时间戳降序排列
                LIMIT 1  -- 只返回最近一次记录
            ''', (user_id,))
            return cursor.fetchone()

    def get_playback_records_by_username(self, username, limit=10):
        """通过用户名获取播放记录
        
        Args:
            username: 用户名
            limit: 返回记录的数量限制，默认10条
        
        Returns:
            播放记录列表，每条记录包含会话ID、IP地址、设备名称、客户端类型、媒体名称、开始时间、结束时间、播放时长和位置信息
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT session_id, ip_address, device_name, client_type, media_name,
                       start_time, end_time, duration, location
                FROM playback_history
                WHERE username = ? AND end_time IS NOT NULL  -- 只返回已结束的会话
                ORDER BY start_time DESC  -- 按开始时间降序排列
                LIMIT ?
            ''', (username, limit))
            return cursor.fetchall()

    def get_ban_info_by_username(self, username):
        """通过用户名获取封禁信息
        
        Args:
            username: 用户名
        
        Returns:
            最近一次的封禁记录，包含时间戳、触发IP、活跃会话数和操作
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT timestamp, trigger_ip, active_sessions, action
                FROM security_log
                WHERE username = ? AND action = 'DISABLE'  -- 只返回禁用操作
                ORDER BY timestamp DESC  -- 按时间戳降序排列
                LIMIT 1  -- 只返回最近一次记录
            ''', (username,))
            return cursor.fetchone()

    def record_session_end(self, session_id, end_time, duration):
        """记录会话结束
        
        Args:
            session_id: 会话ID
            end_time: 结束时间（datetime对象）
            duration: 播放时长（秒）
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE playback_history
                SET end_time = ?, duration = ?
                WHERE session_id = ? AND end_time IS NULL  -- 只更新未结束的会话
            ''', (
                end_time.strftime('%Y-%m-%d %H:%M:%S'),  # 格式化时间为字符串
                duration,
                session_id
            ))
            conn.commit()

    def log_security_event(self, log_data):
        """记录安全事件
        
        Args:
            log_data: 日志数据字典，包含以下键：
                - timestamp: 时间戳（datetime对象）
                - user_id: 用户ID
                - username: 用户名
                - trigger_ip: 触发IP
                - active_sessions: 活跃会话数
                - action: 执行的操作
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO security_log
                (timestamp, user_id, username, trigger_ip, active_sessions, action)
                VALUES (?,?,?,?,?,?)
            ''', (
                log_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),  # 格式化时间为字符串
                log_data['user_id'],
                log_data['username'],
                log_data['trigger_ip'],
                log_data['active_sessions'],
                log_data['action']
            ))
            conn.commit()

    def set_user_expiry(self, user_id, expiry_date, never_expire=False):
        """设置用户的到期时间
        
        Args:
            user_id: 用户ID
            expiry_date: 到期日期
            never_expire: 是否永不过期，默认False
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO user_expiry (user_id, expiry_date, never_expire, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                expiry_date = excluded.expiry_date,
                never_expire = excluded.never_expire,
                updated_at = CURRENT_TIMESTAMP
            ''', (user_id, expiry_date, 1 if never_expire else 0))  # 将布尔值转换为整数（0或1）
            conn.commit()

    def set_user_never_expire(self, user_id, never_expire=True):
        """设置用户永不过期
        
        Args:
            user_id: 用户ID
            never_expire: 是否永不过期，默认True
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO user_expiry (user_id, never_expire, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                never_expire = excluded.never_expire,
                updated_at = CURRENT_TIMESTAMP
            ''', (user_id, 1 if never_expire else 0))  # 将布尔值转换为整数（0或1）
            conn.commit()

    def get_user_expiry(self, user_id):
        """获取用户的到期信息
        
        Args:
            user_id: 用户ID
        
        Returns:
            包含到期日期和是否永不过期的字典，如果用户不存在则返回None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT expiry_date, never_expire FROM user_expiry WHERE user_id = ?
            ''', (user_id,))
            result = cursor.fetchone()
            if result:
                return {'expiry_date': result[0], 'never_expire': bool(result[1])}  # 将整数转换为布尔值
            return None

    def is_user_never_expire(self, user_id):
        """检查用户是否永不过期
        
        Args:
            user_id: 用户ID
        
        Returns:
            如果用户永不过期则返回True，否则返回False
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT never_expire FROM user_expiry WHERE user_id = ?
            ''', (user_id,))
            result = cursor.fetchone()
            return bool(result[0]) if result else False  # 将整数转换为布尔值

    def get_all_expired_users(self):
        """获取所有已过期的用户
        
        Returns:
            已过期用户的ID列表
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT user_id FROM user_expiry
                WHERE expiry_date IS NOT NULL  -- 有到期日期的用户
                AND expiry_date < DATE('now')  -- 到期日期早于当前日期
                AND (never_expire IS NULL OR never_expire = 0)  -- 不是永不过期的用户
            ''')
            return [row[0] for row in cursor.fetchall()]

    def clear_user_expiry(self, user_id):
        """清除用户的到期信息
        
        Args:
            user_id: 用户ID
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM user_expiry WHERE user_id = ?', (user_id,))
            conn.commit()

    def create_user_group(self, group_id, name):
        """创建用户组
        
        Args:
            group_id: 组ID
            name: 组名称
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO user_groups (group_id, name, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (group_id, name))
            conn.commit()

    def delete_user_group(self, group_id):
        """删除用户组
        
        Args:
            group_id: 组ID
        """
        with sqlite3.connect(self.db_path) as conn:
            # 先删除用户组成员
            conn.execute('DELETE FROM user_group_members WHERE group_id = ?', (group_id,))
            # 再删除用户组
            conn.execute('DELETE FROM user_groups WHERE group_id = ?', (group_id,))
            conn.commit()

    def get_all_user_groups(self):
        """获取所有用户组信息
        
        Returns:
            用户组列表，每个用户组包含ID、名称和成员列表
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT group_id, name FROM user_groups ORDER BY created_at')
            groups = []
            for row in cursor.fetchall():
                group_id, name = row
                # 获取该用户组的成员
                member_cursor = conn.execute(
                    'SELECT user_id FROM user_group_members WHERE group_id = ?',
                    (group_id,),
                )
                members = [m[0] for m in member_cursor.fetchall()]
                groups.append({
                    'id': group_id,
                    'name': name,
                    'members': members,
                })
            return groups

    def add_user_to_group(self, group_id, user_id):
        """将用户添加到用户组
        
        Args:
            group_id: 组ID
            user_id: 用户ID
        
        Returns:
            如果添加成功则返回True，如果用户已经在组中则返回False
        """
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute('''
                    INSERT INTO user_group_members (group_id, user_id)
                    VALUES (?, ?)
                ''', (group_id, user_id))
                conn.commit()
                return True
            except sqlite3.IntegrityError:  # 如果用户已经在组中，会触发唯一约束错误
                return False

    def remove_user_from_group(self, group_id, user_id):
        """从用户组中移除用户
        
        Args:
            group_id: 组ID
            user_id: 用户ID
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                DELETE FROM user_group_members WHERE group_id = ? AND user_id = ?
            ''', (group_id, user_id))
            conn.commit()

    def get_group_members(self, group_id):
        """获取用户组的成员
        
        Args:
            group_id: 组ID
        
        Returns:
            成员用户ID列表
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT user_id FROM user_group_members WHERE group_id = ?
            ''', (group_id,))
            return [row[0] for row in cursor.fetchall()]

    def _generate_invite_code(self, length=8):
        """生成邀请码
        
        Args:
            length: 邀请码长度，默认8位
        
        Returns:
            生成的邀请码字符串
        """
        alphabet = string.ascii_letters + string.digits  # 包含大小写字母和数字
        return ''.join(secrets.choice(alphabet) for _ in range(length))  # 随机选择字符生成邀请码

    def create_invite(self, valid_hours, max_uses, group_id=None, account_expiry_date=None, created_by='admin'):
        """创建邀请链接
        
        Args:
            valid_hours: 邀请有效期（小时）
            max_uses: 最大使用次数
            group_id: 关联的用户组ID（可选）
            account_expiry_date: 账号过期日期（可选）
            created_by: 创建者，默认'admin'
        
        Returns:
            创建的邀请信息字典
        
        Raises:
            RuntimeError: 如果生成邀请码失败
        """
        # 计算过期时间
        expires_at = datetime.now() + timedelta(hours=int(valid_hours))
        code = None

        with sqlite3.connect(self.db_path) as conn:
            # 尝试生成唯一的邀请码，最多尝试10次
            for _ in range(10):
                candidate = self._generate_invite_code(8)
                # 检查邀请码是否已存在
                exists = conn.execute('SELECT 1 FROM invites WHERE code = ?', (candidate,)).fetchone()
                if not exists:
                    code = candidate
                    break

            if not code:
                raise RuntimeError('生成邀请链接失败，请重试')

            # 插入邀请记录
            conn.execute('''
                INSERT INTO invites (
                    code, expires_at, max_uses, used_count, group_id,
                    account_expiry_date, is_active, created_by, updated_at
                ) VALUES (?, ?, ?, 0, ?, ?, 1, ?, CURRENT_TIMESTAMP)
            ''', (
                code,
                expires_at.strftime('%Y-%m-%d %H:%M:%S'),  # 格式化时间为字符串
                int(max_uses),
                group_id or None,
                account_expiry_date or None,
                created_by,
            ))
            conn.commit()

        # 返回创建的邀请信息
        return self.get_invite_by_code(code)

    def get_invite_by_code(self, code):
        """通过邀请码获取邀请信息
        
        Args:
            code: 邀请码
        
        Returns:
            邀请信息字典，如果邀请不存在则返回None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT code, expires_at, max_uses, used_count, group_id,
                       account_expiry_date, is_active, created_by, created_at
                FROM invites
                WHERE code = ?
            ''', (code,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                'code': row[0],
                'expires_at': row[1],
                'max_uses': row[2],
                'used_count': row[3],
                'group_id': row[4],
                'account_expiry_date': row[5],
                'is_active': bool(row[6]),  # 将整数转换为布尔值
                'created_by': row[7],
                'created_at': row[8],
            }

    def consume_invite(self, code):
        """使用邀请码
        
        Args:
            code: 邀请码
        
        Returns:
            总是返回True
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE invites
                SET used_count = used_count + 1,
                    is_active = CASE WHEN used_count + 1 >= max_uses THEN 0 ELSE is_active END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE code = ? AND is_active = 1
            ''', (code,))
            conn.commit()
            return True

    def list_invites(self):
        """列出所有邀请
        
        Returns:
            邀请列表，每个邀请包含完整的邀请信息
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT code, expires_at, max_uses, used_count, group_id,
                       account_expiry_date, is_active, created_by, created_at
                FROM invites
                ORDER BY created_at DESC  -- 按创建时间降序排列
            ''')
            rows = cursor.fetchall()
            return [
                {
                    'code': row[0],
                    'expires_at': row[1],
                    'max_uses': row[2],
                    'used_count': row[3],
                    'group_id': row[4],
                    'account_expiry_date': row[5],
                    'is_active': bool(row[6]),  # 将整数转换为布尔值
                    'created_by': row[7],
                    'created_at': row[8],
                }
                for row in rows
            ]

    def delete_invite(self, code):
        """删除邀请（将其标记为无效）
        
        Args:
            code: 邀请码
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'UPDATE invites SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE code = ?',
                (code,),
            )
            conn.commit()

    def is_invite_available(self, code):
        """检查邀请是否可用
        
        Args:
            code: 邀请码
        
        Returns:
            元组 (是否可用, 消息)，如果可用则消息为空字符串
        """
        invite = self.get_invite_by_code(code)
        if not invite:
            return False, '邀请不存在'
        if not invite['is_active']:
            return False, '邀请已失效'
        if invite['used_count'] >= invite['max_uses']:
            return False, '邀请名额已用完'
        try:
            expires_at = datetime.strptime(invite['expires_at'], '%Y-%m-%d %H:%M:%S')
            if expires_at < datetime.now():
                return False, '邀请已过期'
        except Exception:
            return False, '邀请时间异常'
        return True, ''

    def get_ip_location(self, ip_address):
        """从数据库查询IP归属地
        
        Args:
            ip_address: IP地址
        
        Returns:
            IP归属地信息字典，如果不存在则返回None
        """
        if not ip_address:
            return None
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT provider, ip_address, location, district, street, isp,
                       latitude, longitude, formatted
                FROM ip_location_cache
                WHERE ip_address = ?
            ''', (ip_address,))
            row = cursor.fetchone()
            if row:
                return {
                    'provider': row[0],
                    'ip': row[1],
                    'location': row[2],
                    'district': row[3],
                    'street': row[4],
                    'isp': row[5],
                    'latitude': row[6],
                    'longitude': row[7],
                    'formatted': row[8],
                    'ts': int(datetime.now().timestamp())  # 添加时间戳
                }
            return None

    def save_ip_location(self, location_info):
        """保存IP归属地到数据库
        
        Args:
            location_info: IP归属地信息字典，包含以下键：
                - ip: IP地址
                - provider: 数据提供方
                - location: 位置信息
                - district: 区域
                - street: 街道
                - isp: 互联网服务提供商
                - latitude: 纬度
                - longitude: 经度
                - formatted: 格式化的位置信息
        
        Returns:
            如果保存成功则返回True，否则返回False
        """
        if not location_info or not location_info.get('ip'):
            return False
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO ip_location_cache (
                    ip_address, provider, location, district, street, isp,
                    latitude, longitude, formatted, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(ip_address) DO UPDATE SET
                    provider = excluded.provider,
                    location = excluded.location,
                    district = excluded.district,
                    street = excluded.street,
                    isp = excluded.isp,
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    formatted = excluded.formatted,
                    updated_at = CURRENT_TIMESTAMP
            ''', (
                location_info.get('ip'),
                location_info.get('provider'),
                location_info.get('location'),
                location_info.get('district'),
                location_info.get('street'),
                location_info.get('isp'),
                location_info.get('latitude'),
                location_info.get('longitude'),
                location_info.get('formatted')
            ))
            conn.commit()
            return True

    def cleanup_old_ip_locations(self, days=30):
        """清理指定天数前的IP归属地缓存记录
        
        Args:
            days: 天数，默认30天
        
返回：
            删除的记录数量
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                DELETE FROM ip_location_cache
                WHERE created_at < datetime('now', '-' || ? || ' days')
            ''', (days,))
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count

    def get_security_logs(self, limit=100):
        """获取安全日志，按照时间正序排列
        
参数：
limit：返回记录的数量限制，默认100条
        
返回：
            安全日志列表，每条日志包含完整的日志信息
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT id, timestamp, user_id, username, trigger_ip, active_sessions, action
                FROM security_log
按时间戳正序排列 -- 按时间戳正序排列
限制 ?
            ''', (限制,))
            logs = []
            for row in cursor.fetchall():
                logs.append({
                    'id': row[0],
                    'timestamp': row[1],
                    'user_id': 行[2],
                    'username': 行[3],
                    'trigger_ip': 行[4],
                    'active_sessions': row[5],
                    'action': row[6]
                })
            返回日志
