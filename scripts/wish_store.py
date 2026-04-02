from __future__ import annotations

import sqlite3
from datetime import datetime


class WishStore:
    ALLOWED_STATUSES = {'pending', 'approved', 'rejected'}
    SELECT_FIELDS = '''
        id, tmdb_id, media_type, title, original_title, release_date, year,
        overview, poster_path, poster_url, backdrop_path, backdrop_url,
        request_count, status, submit_ip, created_at, updated_at
    '''

    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS media_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tmdb_id INTEGER NOT NULL,
                    media_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    original_title TEXT,
                    release_date TEXT,
                    year TEXT,
                    overview TEXT,
                    poster_path TEXT,
                    poster_url TEXT,
                    backdrop_path TEXT,
                    backdrop_url TEXT,
                    request_count INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'pending',
                    submit_ip TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(tmdb_id, media_type)
                )
                '''
            )
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS media_request_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    tmdb_id INTEGER NOT NULL,
                    media_type TEXT NOT NULL,
                    submit_ip TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(request_id) REFERENCES media_requests(id) ON DELETE CASCADE
                )
                '''
            )
            conn.execute("UPDATE media_requests SET status = 'approved' WHERE status = 'fulfilled'")
            conn.commit()

    def count_recent_submissions_by_ip(self, submit_ip, since_time):
        submit_ip = (submit_ip or '').strip()
        if not submit_ip:
            return 0
        since_text = self._format_datetime(since_time)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                '''
                SELECT COUNT(1)
                FROM media_request_submissions
                WHERE submit_ip = ? AND created_at >= ?
                ''',
                (submit_ip, since_text),
            ).fetchone()
            return int(row[0] or 0) if row else 0

    def add_request(self, item, submit_ip=''):
        submit_ip = (submit_ip or '').strip()
        tmdb_id = int(item.get('tmdb_id'))
        media_type = (item.get('media_type') or '').strip()
        if media_type not in {'movie', 'tv'}:
            raise ValueError('媒体类型错误')

        payload = {
            'tmdb_id': tmdb_id,
            'media_type': media_type,
            'title': (item.get('title') or '').strip(),
            'original_title': (item.get('original_title') or '').strip(),
            'release_date': (item.get('release_date') or '').strip(),
            'year': (item.get('year') or '').strip(),
            'overview': (item.get('overview') or '').strip(),
            'poster_path': (item.get('poster_path') or '').strip(),
            'poster_url': (item.get('poster_url') or '').strip(),
            'backdrop_path': (item.get('backdrop_path') or '').strip(),
            'backdrop_url': (item.get('backdrop_url') or '').strip(),
        }
        if not payload['title']:
            raise ValueError('标题不能为空')

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            existing = conn.execute(
                f'''
                SELECT {self.SELECT_FIELDS}
                FROM media_requests
                WHERE tmdb_id = ? AND media_type = ?
                ''',
                (payload['tmdb_id'], payload['media_type']),
            ).fetchone()
            if existing:
                existing_record = dict(existing)
                if existing_record.get('status') != 'rejected':
                    existing_record['created'] = False
                    return existing_record

                conn.execute(
                    '''
                    UPDATE media_requests
                    SET title = ?,
                        original_title = ?,
                        release_date = ?,
                        year = ?,
                        overview = ?,
                        poster_path = ?,
                        poster_url = ?,
                        backdrop_path = ?,
                        backdrop_url = ?,
                        status = 'pending',
                        submit_ip = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    ''',
                    (
                        payload['title'],
                        payload['original_title'],
                        payload['release_date'],
                        payload['year'],
                        payload['overview'],
                        payload['poster_path'],
                        payload['poster_url'],
                        payload['backdrop_path'],
                        payload['backdrop_url'],
                        submit_ip or None,
                        existing_record['id'],
                    ),
                )
                conn.execute(
                    '''
                    INSERT INTO media_request_submissions (
                        request_id, tmdb_id, media_type, submit_ip
                    ) VALUES (?, ?, ?, ?)
                    ''',
                    (existing_record['id'], payload['tmdb_id'], payload['media_type'], submit_ip or None),
                )
                conn.commit()

                record = self.get_request(existing_record['id'])
                if not record:
                    raise RuntimeError('恢复求片记录失败')
                record['created'] = True
                return record

            cursor = conn.execute(
                '''
                INSERT INTO media_requests (
                    tmdb_id, media_type, title, original_title, release_date, year,
                    overview, poster_path, poster_url, backdrop_path, backdrop_url,
                    request_count, status, submit_ip, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'pending', ?, CURRENT_TIMESTAMP)
                ''',
                (
                    payload['tmdb_id'],
                    payload['media_type'],
                    payload['title'],
                    payload['original_title'],
                    payload['release_date'],
                    payload['year'],
                    payload['overview'],
                    payload['poster_path'],
                    payload['poster_url'],
                    payload['backdrop_path'],
                    payload['backdrop_url'],
                    submit_ip or None,
                ),
            )
            request_id = int(cursor.lastrowid)
            conn.execute(
                '''
                INSERT INTO media_request_submissions (
                    request_id, tmdb_id, media_type, submit_ip
                ) VALUES (?, ?, ?, ?)
                ''',
                (request_id, payload['tmdb_id'], payload['media_type'], submit_ip or None),
            )
            conn.commit()

        record = self.get_request(request_id)
        if not record:
            raise RuntimeError('保存求片记录失败')
        record['created'] = True
        return record

    def get_request(self, request_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                f'''
                SELECT {self.SELECT_FIELDS}
                FROM media_requests
                WHERE id = ?
                ''',
                (request_id,),
            ).fetchone()
            if not row:
                return None
            return dict(row)

    def list_requests(self, status=''):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if status and status in self.ALLOWED_STATUSES:
                rows = conn.execute(
                    f'''
                    SELECT {self.SELECT_FIELDS}
                    FROM media_requests
                    WHERE status = ?
                    ORDER BY updated_at DESC, created_at DESC
                    ''',
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    f'''
                    SELECT {self.SELECT_FIELDS}
                    FROM media_requests
                    ORDER BY updated_at DESC, created_at DESC
                    '''
                ).fetchall()
            return [dict(row) for row in rows]

    def list_public_requests(self, page=1, page_size=25):
        try:
            page = max(int(page or 1), 1)
        except Exception:
            page = 1
        try:
            page_size = max(min(int(page_size or 25), 50), 1)
        except Exception:
            page_size = 25

        offset = (page - 1) * page_size
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            total_row = conn.execute(
                '''
                SELECT COUNT(1)
                FROM media_requests
                WHERE status != 'rejected'
                '''
            ).fetchone()
            total_results = int(total_row[0] or 0) if total_row else 0
            rows = conn.execute(
                f'''
                SELECT {self.SELECT_FIELDS}
                FROM media_requests
                WHERE status != 'rejected'
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ? OFFSET ?
                ''',
                (page_size, offset),
            ).fetchall()

        total_pages = ((total_results - 1) // page_size) + 1 if total_results else 1
        requests = []
        for row in rows:
            record = dict(row)
            record['requested'] = True
            record['request_status'] = record.get('status')
            requests.append(record)

        return {
            'requests': requests,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            'total_results': total_results,
        }

    def get_request_map(self, items, include_rejected=False):
        mapping = {}
        if not items:
            return mapping

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            for item in items:
                try:
                    tmdb_id = int(item.get('tmdb_id'))
                except Exception:
                    continue
                media_type = (item.get('media_type') or '').strip()
                if media_type not in {'movie', 'tv'}:
                    continue

                if include_rejected:
                    row = conn.execute(
                        f'''
                        SELECT {self.SELECT_FIELDS}
                        FROM media_requests
                        WHERE tmdb_id = ? AND media_type = ?
                        ''',
                        (tmdb_id, media_type),
                    ).fetchone()
                else:
                    row = conn.execute(
                        f'''
                        SELECT {self.SELECT_FIELDS}
                        FROM media_requests
                        WHERE tmdb_id = ? AND media_type = ? AND status != 'rejected'
                        ''',
                        (tmdb_id, media_type),
                    ).fetchone()

                if row:
                    mapping[f'{media_type}:{tmdb_id}'] = dict(row)
        return mapping

    def update_request_status(self, request_id, status):
        status = (status or '').strip()
        if status not in self.ALLOWED_STATUSES:
            raise ValueError('状态错误')
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                '''
                UPDATE media_requests
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (status, request_id),
            )
            conn.commit()
            if cursor.rowcount <= 0:
                return None
        return self.get_request(request_id)

    def delete_request(self, request_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM media_request_submissions WHERE request_id = ?', (request_id,))
            cursor = conn.execute('DELETE FROM media_requests WHERE id = ?', (request_id,))
            conn.commit()
            return cursor.rowcount > 0

    def _format_datetime(self, value):
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d %H:%M:%S')
        return str(value)
