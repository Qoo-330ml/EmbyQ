import logging
import sqlite3

logger = logging.getLogger(__name__)


class ShadowLibrary:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS shadow_library (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    emby_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    year TEXT,
                    tmdb_id TEXT,
                    emby_series_id TEXT,
                    season_number INTEGER DEFAULT 0
                )
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_shadow_library_type
                ON shadow_library(media_type)
            ''')

            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_shadow_library_series
                ON shadow_library(emby_series_id)
            ''')

            conn.commit()

    def exists_emby_id(self, emby_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM shadow_library WHERE emby_id = ?",
                (emby_id,)
            )
            return cursor.fetchone() is not None

    def exists_season(self, emby_series_id, season_number):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM shadow_library WHERE emby_series_id = ? AND season_number = ? AND media_type = 'Season'",
                (emby_series_id, season_number)
            )
            return cursor.fetchone() is not None

    def get_by_emby_id(self, emby_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM shadow_library WHERE emby_id = ?",
                (emby_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_season_by_slot(self, emby_series_id, season_number):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM shadow_library WHERE emby_series_id = ? AND season_number = ? AND media_type = 'Season'",
                (emby_series_id, season_number)
            ).fetchone()
            return dict(row) if row else None

    def get_all_emby_ids(self, media_type=None):
        with sqlite3.connect(self.db_path) as conn:
            if media_type:
                cursor = conn.execute(
                    "SELECT emby_id FROM shadow_library WHERE media_type = ?",
                    (media_type,)
                )
            else:
                cursor = conn.execute("SELECT emby_id FROM shadow_library")
            return {row[0] for row in cursor.fetchall()}

    def sync_movies(self, movies):
        synced = 0
        skipped = 0
        errors = 0
        for movie in movies:
            try:
                if self.exists_emby_id(movie.get('Id')):
                    skipped += 1
                    continue
                self._upsert_movie(movie)
                synced += 1
            except Exception as e:
                logger.error(f"同步电影失败 [{movie.get('Name') or movie.get('Id')}]: {e}")
                errors += 1
        return {'synced': synced, 'skipped': skipped, 'errors': errors}

    def _upsert_movie(self, movie):
        with sqlite3.connect(self.db_path) as conn:
            provider_ids = movie.get('ProviderIds') or {}
            tmdb_id = provider_ids.get('Tmdb') or provider_ids.get('TheMovieDb')
            conn.execute('''
                INSERT INTO shadow_library (
                    emby_id, name, media_type, year, tmdb_id, emby_series_id, season_number
                ) VALUES (?, ?, ?, ?, ?, NULL, 0)
            ''', (
                movie.get('Id'),
                movie.get('Name'),
                'Movie',
                movie.get('ProductionYear'),
                tmdb_id
            ))
            conn.commit()

    def sync_series(self, series_list):
        synced = 0
        skipped = 0
        errors = 0
        for series in series_list:
            try:
                if self.exists_emby_id(series.get('Id')):
                    skipped += 1
                    continue
                self._upsert_series(series)
                synced += 1
            except Exception as e:
                logger.error(f"同步剧集失败 [{series.get('Name') or series.get('Id')}]: {e}")
                errors += 1
        return {'synced': synced, 'skipped': skipped, 'errors': errors}

    def _upsert_series(self, series):
        with sqlite3.connect(self.db_path) as conn:
            provider_ids = series.get('ProviderIds') or {}
            tmdb_id = provider_ids.get('Tmdb') or provider_ids.get('TheMovieDb')
            conn.execute('''
                INSERT INTO shadow_library (
                    emby_id, name, media_type, year, tmdb_id, emby_series_id, season_number
                ) VALUES (?, ?, ?, ?, ?, NULL, 0)
            ''', (
                series.get('Id'),
                series.get('Name'),
                'Series',
                series.get('ProductionYear'),
                tmdb_id
            ))
            conn.commit()

    def sync_seasons(self, emby_series_id, seasons, current_series_name=''):
        synced = 0
        skipped = 0
        errors = 0
        current_series_id = str(emby_series_id or '')
        current_series_name = current_series_name or ''
        for season in seasons:
            try:
                season_id = str(season.get('Id') or '')
                season_name = season.get('Name') or ''
                season_number = season.get('IndexNumber', 0)
                season_series_id = str(season.get('SeriesId') or season.get('ParentId') or current_series_id)
                season_series_name = season.get('SeriesName') or ''
                existing_by_id = self.get_by_emby_id(season_id) if season_id else None
                existing_same_slot = self.get_season_by_slot(season_series_id, season_number)

                if not season_id:
                    logger.warning(
                        f"跳过无效季记录: 当前剧集={current_series_name or current_series_id}({current_series_id}), 原始季数据={season}"
                    )
                    skipped += 1
                    continue

                if season_series_id != current_series_id:
                    logger.warning(
                        "检测到Emby季归属异常: "
                        f"当前剧集={current_series_name or current_series_id}({current_series_id}) | "
                        f"返回季={season_name} [season_id={season_id}, season_number={season_number}] | "
                        f"季自带归属剧集={season_series_name or season_series_id}({season_series_id}) | "
                        f"已存在同ID记录={existing_by_id}"
                    )

                if existing_by_id:
                    skipped += 1
                    continue
                if existing_same_slot:
                    logger.warning(
                        "检测到Emby季槽位重复: "
                        f"当前剧集={current_series_name or current_series_id}({current_series_id}) | "
                        f"返回季={season_name} [season_id={season_id}, season_number={season_number}] | "
                        f"季自带归属剧集={season_series_name or season_series_id}({season_series_id}) | "
                        f"已存在同槽位记录={existing_same_slot}"
                    )
                    skipped += 1
                    continue

                self._upsert_season(season_series_id, season)
                synced += 1
            except Exception as e:
                logger.error(
                    "同步季失败: "
                    f"当前剧集={current_series_name or current_series_id}({current_series_id}) | "
                    f"返回季={season.get('Name')} [season_id={season.get('Id')}, season_number={season.get('IndexNumber', 0)}] | "
                    f"季自带归属剧集={season.get('SeriesName') or season.get('SeriesId') or season.get('ParentId') or current_series_id}"
                    f"({season.get('SeriesId') or season.get('ParentId') or current_series_id}) | "
                    f"错误={e}"
                )
                errors += 1
        return {'synced': synced, 'skipped': skipped, 'errors': errors}

    def _upsert_season(self, emby_series_id, season):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO shadow_library (
                    emby_id, name, media_type, year, tmdb_id, emby_series_id, season_number
                ) VALUES (?, ?, ?, ?, NULL, ?, ?)
            ''', (
                season.get('Id'),
                season.get('Name'),
                'Season',
                season.get('PremiereDate', '')[:10] if season.get('PremiereDate') else None,
                str(emby_series_id or ''),
                season.get('IndexNumber', 0)
            ))
            conn.commit()

    def get_library_stats(self):
        with sqlite3.connect(self.db_path) as conn:
            movie_count = conn.execute(
                "SELECT COUNT(*) FROM shadow_library WHERE media_type = 'Movie'"
            ).fetchone()[0]
            series_count = conn.execute(
                "SELECT COUNT(*) FROM shadow_library WHERE media_type = 'Series'"
            ).fetchone()[0]
            season_count = conn.execute(
                "SELECT COUNT(*) FROM shadow_library WHERE media_type = 'Season'"
            ).fetchone()[0]

            return {
                'movie_count': movie_count,
                'series_count': series_count,
                'season_count': season_count,
                'total_items': movie_count + series_count
            }

    def get_movies(self, page=1, page_size=20):
        offset = (page - 1) * page_size
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                "SELECT COUNT(*) FROM shadow_library WHERE media_type = 'Movie'"
            ).fetchone()[0]
            rows = conn.execute('''
                SELECT * FROM shadow_library
                WHERE media_type = 'Movie'
                ORDER BY name
                LIMIT ? OFFSET ?
            ''', (page_size, offset)).fetchall()
            return {
                'items': [dict(row) for row in rows],
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': (total + page_size - 1) // page_size if total else 1
            }

    def get_series_list(self, page=1, page_size=20):
        offset = (page - 1) * page_size
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute(
                "SELECT COUNT(*) FROM shadow_library WHERE media_type = 'Series'"
            ).fetchone()[0]
            rows = conn.execute('''
                SELECT * FROM shadow_library
                WHERE media_type = 'Series'
                ORDER BY name
                LIMIT ? OFFSET ?
            ''', (page_size, offset)).fetchall()
            return {
                'items': [dict(row) for row in rows],
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': (total + page_size - 1) // page_size if total else 1
            }

    def get_series_detail(self, emby_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            series = conn.execute(
                "SELECT * FROM shadow_library WHERE emby_id = ? AND media_type = 'Series'",
                (emby_id,)
            ).fetchone()

            if not series:
                return None

            seasons = conn.execute('''
                SELECT * FROM shadow_library
                WHERE emby_series_id = ? AND media_type = 'Season'
                ORDER BY season_number
            ''', (emby_id,)).fetchall()

            return {
                'series': dict(series),
                'seasons': [dict(row) for row in seasons]
            }

    def search_library(self, query, media_type=None):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if media_type:
                rows = conn.execute('''
                    SELECT * FROM shadow_library
                    WHERE name LIKE ?
                    AND media_type = ?
                    ORDER BY name
                    LIMIT 50
                ''', (f'%{query}%', media_type)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM shadow_library
                    WHERE name LIKE ?
                    ORDER BY name
                    LIMIT 50
                ''', (f'%{query}%',)).fetchall()
            return [dict(row) for row in rows]

    def check_tmdb(self, tmdb_id, media_type=None):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            db_media_type = None
            if media_type:
                if media_type.lower() == 'tv':
                    db_media_type = 'Series'
                elif media_type.lower() == 'movie':
                    db_media_type = 'Movie'
                else:
                    db_media_type = media_type
                rows = conn.execute('''
                    SELECT * FROM shadow_library
                    WHERE tmdb_id = ? AND media_type = ?
                ''', (str(tmdb_id), db_media_type)).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM shadow_library
                    WHERE tmdb_id = ?
                ''', (str(tmdb_id),)).fetchall()
            return [dict(row) for row in rows]

    def get_series_seasons_by_tmdb(self, tmdb_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            series = conn.execute('''
                SELECT emby_id FROM shadow_library
                WHERE tmdb_id = ? AND media_type = 'Series'
            ''', (str(tmdb_id),)).fetchone()

            if not series:
                return []

            series_emby_id = series[0]
            rows = conn.execute('''
                SELECT * FROM shadow_library
                WHERE emby_series_id = ? AND media_type = 'Season'
                ORDER BY season_number
            ''', (series_emby_id,)).fetchall()
            return [dict(row) for row in rows]