import logging
import time

logger = logging.getLogger(__name__)


class ShadowLibrarySyncer:
    def __init__(self, emby_client, shadow_library):
        self.emby_client = emby_client
        self.shadow_library = shadow_library
        self.sync_interval = 3600
        self.last_sync_time = None

    def sync_all(self):
        """执行完整同步"""
        logger.info("🔄 开始影子库同步...")
        start_time = time.time()

        movie_result = self.sync_movies()
        series_result = self.sync_series()

        elapsed = time.time() - start_time
        self.last_sync_time = time.time()

        logger.info(f"✅ 影子库同步完成，耗时 {elapsed:.1f}秒")
        logger.info(f"   电影共 {movie_result['synced'] + movie_result['skipped']} 部，新增 {movie_result['synced']} 部")
        logger.info(f"   电视共 {series_result['synced'] + series_result['skipped']} 部，新增 {series_result['synced']} 部")

        return {
            'movies': movie_result,
            'series': series_result,
            'elapsed_seconds': elapsed
        }

    def sync_movies(self):
        """同步所有电影"""
        logger.info("📽 同步电影库...")
        movies = self.emby_client.get_movies()
        if not movies:
            logger.warning("⚠️ 未获取到任何电影")
            return {'synced': 0, 'errors': 0}

        result = self.shadow_library.sync_movies(movies)
        logger.info(f"📽 电影同步完成: {result['synced']} 部")
        return result

    def sync_series(self):
        """同步所有剧集（包含季信息）"""
        logger.info("📺 同步剧集库...")
        series_list = self.emby_client.get_series_list()
        if not series_list:
            logger.warning("⚠️ 未获取到任何剧集")
            return {'synced': 0, 'skipped': 0, 'errors': 0}

        synced = 0
        skipped = 0
        errors = 0
        for series in series_list:
            try:
                result = self._sync_single_series(series)
                if result.get('skipped'):
                    skipped += 1
                else:
                    synced += 1
            except Exception as e:
                logger.error(f"同步剧集失败 [{series.get('Name')}]: {e}")
                errors += 1

        logger.info(f"📺 剧集同步完成: 新增 {synced}, 跳过 {skipped}")
        return {'synced': synced, 'skipped': skipped, 'errors': errors}

    def _sync_single_series(self, series):
        """同步单个剧集的详细信息"""
        series_id = series.get('Id')
        series_name = series.get('Name', 'Unknown')

        self.shadow_library.sync_series([series])

        seasons = self.emby_client.get_series_seasons(series_id)
        if not seasons:
            return {'skipped': 1}

        result = self.shadow_library.sync_seasons(series_id, seasons, current_series_name=series_name)
        return result

    def get_stats(self):
        """获取影子库统计信息"""
        return self.shadow_library.get_library_stats()