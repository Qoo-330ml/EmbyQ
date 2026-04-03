import requests


class ProxySession:
    _instance = None
    _session = None
    _proxy_config = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._session = requests.Session()
        return cls._instance

    def update_proxy(self, config):
        enabled = config.get('enabled', False)
        url = config.get('url', '').strip()

        self._proxy_config = {}

        if not enabled or not url:
            self._session.proxies.clear()
            return

        # Auto-detect protocol by prefix
        if url.startswith('socks5://') or url.startswith('socks5h://'):
            self._proxy_config['http'] = url
            self._proxy_config['https'] = url
        elif url.startswith('https://'):
            self._proxy_config['http'] = url
            self._proxy_config['https'] = url
        elif url.startswith('http://'):
            self._proxy_config['http'] = url
            self._proxy_config['https'] = url
        else:
            # No scheme provided, treat as http
            self._proxy_config['http'] = 'http://' + url
            self._proxy_config['https'] = 'http://' + url

        self._session.proxies.update(self._proxy_config)

    def get_session(self):
        return self._session

    def is_enabled(self):
        return bool(self._proxy_config)


def get_session():
    return ProxySession().get_session()


def update_proxy_config(config):
    ProxySession().update_proxy(config)


def is_proxy_enabled():
    return ProxySession().is_enabled()
