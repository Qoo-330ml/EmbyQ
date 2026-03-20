import os
import secrets
import sqlite3
import string
from datetime import datetime, timedelta


def get_data_dir():
    """获取data目录路径"""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')


class DatabaseManager:
    def __init__(self, db_name=None):
        data_dir = get_data_dir()
        os.makedirs(data_dir, exist_ok=True)

        # 从配置获取数据库名称
        self.db_path = os.path.join(data_dir, db_name) if db_name else os.path.join(data_dir, 'emby_playback.db')
        self.init_db()

    def init_db(self):
        """初始化数据库结构"""
        with sqlite3.connect(self.db_path) as conn:
            # 播放历史表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS playback_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    device_name TEXT,
                    client_type TEXT,
                    media_name TEXT,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME,
                    duration INTEGER,
                    location TEXT
                )
            ''')

            # 安全日志表（带自动迁移）
            conn.execute('''
                CREATE TABLE IF NOT EXISTS security_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    user_id TEXT,
                    username TEXT,
                    trigger_ip TEXT,
                    active_sessions INTEGER,
                    action TEXT
                )
            ''')

            try:
                cursor = conn.execute("PRAGMA table_info(security_log)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'username' not in columns:
                    conn.execute('ALTER TABLE security_log ADD COLUMN username TEXT')
            except sqlite3.OperationalError:
                pass

            # 用户到期时间表（支持永不过期）
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_expiry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL UNIQUE,
                    expiry_date DATE,
                    never_expire INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            try:
                conn.execute('SELECT never_expire FROM user_expiry LIMIT 1')
            except sqlite3.OperationalError:
                conn.execute('ALTER TABLE user_expiry ADD COLUMN never_expire INTEGER DEFAULT 0')
                conn.commit()

            # 用户组表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 用户组成员表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_group_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(group_id, user_id)
                )
            ''')

            # 邀请链接表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS invites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL UNIQUE,
                    expires_at DATETIME NOT NULL,
                    max_uses INTEGER NOT NULL,
                    used_count INTEGER DEFAULT 0,
                    group_id TEXT,
                    account_expiry_date DATE,
                    is_active INTEGER DEFAULT 1,
                    created_by TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.commit()

    def record_session_start(self, session_data):
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
                session_data['start_time'].strftime('%Y-%m-%d %H:%M:%S'),
                session_data.get('location', '未知位置')
            ))
            conn.commit()

    def get_user_playback_records(self, user_id, limit=10):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT session_id, ip_address, device_name, client_type, media_name,
                       start_time, end_time, duration, location
                FROM playback_history
                WHERE user_id = ? AND end_time IS NOT NULL
                ORDER BY start_time DESC
                LIMIT ?
            ''', (user_id, limit))
            return cursor.fetchall()

    def get_user_ban_info(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT timestamp, trigger_ip, active_sessions, action
                FROM security_log
                WHERE user_id = ? AND action = 'DISABLE'
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (user_id,))
            return cursor.fetchone()

    def get_playback_records_by_username(self, username, limit=10):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT session_id, ip_address, device_name, client_type, media_name,
                       start_time, end_time, duration, location
                FROM playback_history
                WHERE username = ? AND end_time IS NOT NULL
                ORDER BY start_time DESC
                LIMIT ?
            ''', (username, limit))
            return cursor.fetchall()

    def get_ban_info_by_username(self, username):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT timestamp, trigger_ip, active_sessions, action
                FROM security_log
                WHERE username = ? AND action = 'DISABLE'
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (username,))
            return cursor.fetchone()

    def record_session_end(self, session_id, end_time, duration):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE playback_history
                SET end_time = ?, duration = ?
                WHERE session_id = ?
            ''', (
                end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration,
                session_id
            ))
            conn.commit()

    def log_security_event(self, log_data):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO security_log
                (timestamp, user_id, username, trigger_ip, active_sessions, action)
                VALUES (?,?,?,?,?,?)
            ''', (
                log_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                log_data['user_id'],
                log_data['username'],
                log_data['trigger_ip'],
                log_data['active_sessions'],
                log_data['action']
            ))
            conn.commit()

    def set_user_expiry(self, user_id, expiry_date, never_expire=False):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO user_expiry (user_id, expiry_date, never_expire, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                expiry_date = excluded.expiry_date,
                never_expire = excluded.never_expire,
                updated_at = CURRENT_TIMESTAMP
            ''', (user_id, expiry_date, 1 if never_expire else 0))
            conn.commit()

    def set_user_never_expire(self, user_id, never_expire=True):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO user_expiry (user_id, never_expire, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                never_expire = excluded.never_expire,
                updated_at = CURRENT_TIMESTAMP
            ''', (user_id, 1 if never_expire else 0))
            conn.commit()

    def get_user_expiry(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT expiry_date, never_expire FROM user_expiry WHERE user_id = ?
            ''', (user_id,))
            result = cursor.fetchone()
            if result:
                return {'expiry_date': result[0], 'never_expire': bool(result[1])}
            return None

    def is_user_never_expire(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT never_expire FROM user_expiry WHERE user_id = ?
            ''', (user_id,))
            result = cursor.fetchone()
            return bool(result[0]) if result else False

    def get_all_expired_users(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT user_id FROM user_expiry
                WHERE expiry_date IS NOT NULL
                AND expiry_date < DATE('now')
                AND (never_expire IS NULL OR never_expire = 0)
            ''')
            return [row[0] for row in cursor.fetchall()]

    def clear_user_expiry(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM user_expiry WHERE user_id = ?', (user_id,))
            conn.commit()

    def create_user_group(self, group_id, name):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO user_groups (group_id, name, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (group_id, name))
            conn.commit()

    def delete_user_group(self, group_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM user_group_members WHERE group_id = ?', (group_id,))
            conn.execute('DELETE FROM user_groups WHERE group_id = ?', (group_id,))
            conn.commit()

    def get_all_user_groups(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT group_id, name FROM user_groups ORDER BY created_at')
            groups = []
            for row in cursor.fetchall():
                group_id, name = row
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
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute('''
                    INSERT INTO user_group_members (group_id, user_id)
                    VALUES (?, ?)
                ''', (group_id, user_id))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def remove_user_from_group(self, group_id, user_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                DELETE FROM user_group_members WHERE group_id = ? AND user_id = ?
            ''', (group_id, user_id))
            conn.commit()

    def get_group_members(self, group_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT user_id FROM user_group_members WHERE group_id = ?
            ''', (group_id,))
            return [row[0] for row in cursor.fetchall()]

    def _generate_invite_code(self, length=8):
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def create_invite(self, valid_hours, max_uses, group_id=None, account_expiry_date=None, created_by='admin'):
        expires_at = datetime.now() + timedelta(hours=int(valid_hours))
        code = None

        with sqlite3.connect(self.db_path) as conn:
            for _ in range(10):
                candidate = self._generate_invite_code(8)
                exists = conn.execute('SELECT 1 FROM invites WHERE code = ?', (candidate,)).fetchone()
                if not exists:
                    code = candidate
                    break

            if not code:
                raise RuntimeError('生成邀请链接失败，请重试')

            conn.execute('''
                INSERT INTO invites (
                    code, expires_at, max_uses, used_count, group_id,
                    account_expiry_date, is_active, created_by, updated_at
                ) VALUES (?, ?, ?, 0, ?, ?, 1, ?, CURRENT_TIMESTAMP)
            ''', (
                code,
                expires_at.strftime('%Y-%m-%d %H:%M:%S'),
                int(max_uses),
                group_id or None,
                account_expiry_date or None,
                created_by,
            ))
            conn.commit()

        return self.get_invite_by_code(code)

    def get_invite_by_code(self, code):
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
                'is_active': bool(row[6]),
                'created_by': row[7],
                'created_at': row[8],
            }

    def consume_invite(self, code):
        with sqlite3.connect(self.db_path) as conn:
            invite = self.get_invite_by_code(code)
            if not invite:
                return False

            conn.execute('''
                UPDATE invites
                SET used_count = used_count + 1,
                    is_active = CASE WHEN used_count + 1 >= max_uses THEN 0 ELSE is_active END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE code = ? AND is_active = 1
            ''', (code,))
            conn.commit()
            return True

    def is_invite_available(self, code):
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
