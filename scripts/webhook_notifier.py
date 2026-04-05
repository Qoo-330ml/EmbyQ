import json
import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)


class WebhookNotifier:
    def __init__(self, config):
        self.update_config(config or {})

    def update_config(self, config):
        self.config = config or {}
        self.enabled = bool(self.config.get('enabled', False))
        self.url = (self.config.get('url') or '').strip()
        self.timeout = int(self.config.get('timeout', 10) or 10)
        self.retry_attempts = max(int(self.config.get('retry_attempts', 1) or 1), 1)
        self.headers = self._normalize_headers(self.config.get('headers') or {})
        self.body_mode = self._resolve_body_mode(self.config)
        self.body_template = self._resolve_body_template(self.config)
        logger.info(
            'Webhook 配置已更新: enabled=%s, has_url=%s, body_mode=%s, retry_attempts=%s',
            self.enabled,
            bool(self.url),
            self.body_mode,
            self.retry_attempts,
        )

    def is_enabled(self):
        return self.enabled and bool(self.url)

    def send(self, event_type, payload):
        if not self.enabled:
            logger.info('Webhook 通知跳过: reason=disabled, event_type=%s', event_type)
            return False
        if not self.url:
            logger.warning('Webhook 通知跳过: reason=missing_url, event_type=%s', event_type)
            return False

        attempts = max(self.retry_attempts, 1)
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                response = self._post(event_type, payload)
                if 200 <= response.status_code < 300:
                    logger.info(
                        'Webhook 通知发送成功: event_type=%s, attempt=%s/%s, status_code=%s',
                        event_type,
                        attempt,
                        attempts,
                        response.status_code,
                    )
                    return True

                logger.warning(
                    'Webhook 通知发送失败: event_type=%s, attempt=%s/%s, status_code=%s, response=%s',
                    event_type,
                    attempt,
                    attempts,
                    response.status_code,
                    (response.text or '')[:300],
                )
                last_error = RuntimeError(f'HTTP {response.status_code}')
            except Exception as e:
                last_error = e
                logger.warning(
                    'Webhook 通知异常: event_type=%s, attempt=%s/%s, error=%s',
                    event_type,
                    attempt,
                    attempts,
                    e,
                )

            if attempt < attempts:
                time.sleep(min(0.5 * attempt, 2.0))

        logger.error('Webhook 通知最终失败: event_type=%s, error=%s', event_type, last_error)
        return False

    def send_ban_notification(self, user_info: dict):
        payload = self._normalize_user_payload(user_info)
        return self.send('user_disabled', payload)

    def notify_user_disabled(self, username, reason, session=None):
        session = session or {}
        payload = self._normalize_user_payload(
            {
                'username': username,
                'reason': reason,
                'user_id': session.get('user_id', ''),
                'ip_address': session.get('ip_address', ''),
                'ip_type': session.get('ip_type', ''),
                'location': session.get('location', ''),
                'session_count': session.get('session_count', 0),
                'timestamp': session.get('timestamp', ''),
                'device': session.get('device', ''),
                'client': session.get('client', ''),
                'session': session,
            }
        )
        return self.send('user_disabled', payload)

    def notify_user_recovered(self, username, user_id=''):
        payload = {
            'username': username,
            'user_id': user_id,
            'timestamp': self._now_str(),
        }
        return self.send('user_recovered', payload)

    def test_webhook(self):
        payload = {
            'title': 'Webhook 测试通知',
            'content': '这是一条来自 EmbyQ 的测试通知。',
            'username': 'test-user',
            'user_id': 'test-user-id',
            'ip_address': '127.0.0.1',
            'ip_type': 'IPv4',
            'location': '本地测试',
            'session_count': 1,
            'timestamp': self._now_str(),
            'reason': '手动测试 Webhook 配置',
            'device': 'Test Device',
            'client': 'Test Client',
        }
        return self.send('test', payload)

    def _post(self, event_type, payload):
        headers = dict(self.headers)
        if self.body_mode == 'raw':
            body = self._render_text_body(event_type, payload)
            headers.setdefault('Content-Type', 'text/plain; charset=utf-8')
            return requests.post(
                self.url,
                data=body.encode('utf-8'),
                headers=headers,
                timeout=self.timeout,
            )

        if self.body_mode == 'form':
            body = self._render_structured_body(event_type, payload)
            headers.setdefault('Content-Type', 'application/x-www-form-urlencoded; charset=utf-8')
            return requests.post(
                self.url,
                data=body,
                headers=headers,
                timeout=self.timeout,
            )

        body = self._render_structured_body(event_type, payload)
        headers.setdefault('Content-Type', 'application/json; charset=utf-8')
        return requests.post(
            self.url,
            json=body,
            headers=headers,
            timeout=self.timeout,
        )

    def _render_structured_body(self, event_type, payload):
        body = self.config.get('body')
        if isinstance(body, dict) and body:
            rendered = self._render_object(body, event_type, payload)
            if isinstance(rendered, dict):
                rendered.setdefault('event_type', event_type)
                rendered.setdefault('payload', payload)
            return rendered
        return {
            'event_type': event_type,
            'payload': payload,
        }

    def _render_text_body(self, event_type, payload):
        template = self.body_template or ''
        if template:
            return self._render_string(template, event_type, payload)
        structured = self._render_structured_body(event_type, payload)
        return json.dumps(structured, ensure_ascii=False)

    def _render_object(self, value: Any, event_type, payload):
        if isinstance(value, dict):
            return {str(k): self._render_object(v, event_type, payload) for k, v in value.items()}
        if isinstance(value, list):
            return [self._render_object(item, event_type, payload) for item in value]
        if isinstance(value, str):
            return self._render_string(value, event_type, payload)
        return value

    def _render_string(self, template, event_type, payload):
        result = str(template)
        replacements = self._build_replacements(event_type, payload)
        for key, value in replacements.items():
            result = result.replace('{' + key + '}', value)
            result = result.replace('{{' + key + '}}', value)
        return result

    def _build_replacements(self, event_type, payload):
        payload = payload or {}
        replacements = {
            'event_type': str(event_type),
            'payload': json.dumps(payload, ensure_ascii=False),
        }
        if isinstance(payload, dict):
            for key, value in payload.items():
                replacements[str(key)] = '' if value is None else str(value)
        return replacements

    def _normalize_user_payload(self, user_info):
        payload = dict(user_info or {})
        payload.setdefault('title', 'Emby用户封禁通知')
        payload.setdefault(
            'content',
            '用户 {username} 在 {location} 使用 {ip_address} ({ip_type}) 登录，检测到 {session_count} 个并发会话，已自动封禁。',
        )
        payload['content'] = self._render_string(payload.get('content') or '', 'user_disabled', payload)
        payload['title'] = self._render_string(payload.get('title') or '', 'user_disabled', payload)
        payload.setdefault('timestamp', self._now_str())
        return payload

    def _resolve_body_mode(self, config):
        body_mode = str(config.get('body_mode') or '').strip().lower()
        if body_mode in {'json', 'raw', 'form'}:
            return body_mode
        if isinstance(config.get('body'), str):
            return 'raw'
        return 'json'

    def _resolve_body_template(self, config):
        if config.get('body_template'):
            return str(config.get('body_template'))
        body = config.get('body')
        if isinstance(body, str):
            return body
        return ''

    def _normalize_headers(self, headers):
        if not isinstance(headers, dict):
            return {}
        return {str(k): '' if v is None else str(v) for k, v in headers.items()}

    def _now_str(self):
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
