from __future__ import annotations

import requests
from requests import exceptions as requests_exceptions


class TMDBClient:
    def __init__(self, config=None):
        self.session = requests.Session()
        self.update_config(config or {})

    def update_config(self, config):
        config = config or {}
        self.enabled = bool(config.get('enabled', False))
        self.api_key = (config.get('api_key') or '').strip()
        self.language = (config.get('language') or 'zh-CN').strip() or 'zh-CN'
        self.include_adult = bool(config.get('include_adult', False))
        self.image_base_url = (config.get('image_base_url') or 'https://image.tmdb.org/t/p/w342').rstrip('/')

    def is_ready(self):
        return self.enabled and bool(self.api_key)

    def search_multi(self, query, page=1):
        query = (query or '').strip()
        if not query:
            return {'results': [], 'page': 1, 'total_pages': 1, 'total_results': 0}
        if not self.enabled:
            raise RuntimeError('TMDB 搜索未启用')
        if not self.api_key:
            raise RuntimeError('TMDB API Key 未配置')

        try:
            page = max(int(page or 1), 1)
        except Exception:
            page = 1

        try:
            response = self.session.get(
                'https://api.themoviedb.org/3/search/multi',
                params={
                    'api_key': self.api_key,
                    'query': query,
                    'language': self.language,
                    'include_adult': str(self.include_adult).lower(),
                    'page': page,
                },
                timeout=15,
            )
        except requests_exceptions.Timeout as exc:
            raise RuntimeError('TMDB 搜索超时，请稍后重试') from exc
        except requests_exceptions.RequestException as exc:
            raise RuntimeError(f'TMDB 请求失败: {exc}') from exc

        if response.status_code != 200:
            if response.status_code == 401:
                raise RuntimeError('TMDB API Key 无效')
            raise RuntimeError(f'TMDB 搜索失败: HTTP {response.status_code}')

        payload = response.json() or {}
        results = []
        for item in payload.get('results') or []:
            media_type = item.get('media_type')
            if media_type not in {'movie', 'tv'}:
                continue

            title = (item.get('title') or item.get('name') or '').strip()
            if not title:
                continue

            original_title = (
                item.get('original_title')
                or item.get('original_name')
                or item.get('title')
                or item.get('name')
                or ''
            ).strip()
            release_date = (item.get('release_date') or item.get('first_air_date') or '').strip()
            poster_path = item.get('poster_path') or ''
            backdrop_path = item.get('backdrop_path') or ''

            results.append(
                {
                    'tmdb_id': item.get('id'),
                    'media_type': media_type,
                    'title': title,
                    'original_title': original_title,
                    'release_date': release_date,
                    'year': release_date[:4] if release_date else '',
                    'overview': (item.get('overview') or '').strip(),
                    'poster_path': poster_path,
                    'poster_url': self._build_image_url(poster_path),
                    'backdrop_path': backdrop_path,
                    'backdrop_url': self._build_image_url(backdrop_path),
                }
            )

        results.sort(
            key=lambda current: (
                1 if current.get('poster_url') else 0,
                current.get('release_date') or '',
                current.get('title') or '',
            ),
            reverse=True,
        )
        return {
            'results': results,
            'page': int(payload.get('page') or page or 1),
            'total_pages': int(payload.get('total_pages') or 1),
            'total_results': int(payload.get('total_results') or len(results)),
        }

    def _build_image_url(self, path):
        if not path:
            return ''
        return f'{self.image_base_url}{path}'
