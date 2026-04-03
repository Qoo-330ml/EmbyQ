from __future__ import annotations

import argparse
import importlib
import shutil
from typing import Iterable

from config_loader import load_config
from database import DatabaseManager
from emby_client import EmbyClient
from logger import setup_logging, info, error
from monitor import EmbyMonitor
from security import EmbySecurity
from session_manager import update_proxy_config
from shadow_library import ShadowLibrary
from shadow_library_syncer import ShadowLibrarySyncer
from tmdb_client import TMDBClient
from web_server import WebServer
from wish_store import WishStore


def _check_python_packages(packages: Iterable[str]) -> list[str]:
    errors: list[str] = []
    for package in packages:
        try:
            importlib.import_module(package)
        except Exception as exc:
            errors.append(f'Python 包缺失/不可用: {package} ({exc})')
    return errors


def _check_cli_commands(commands: Iterable[str]) -> list[str]:
    errors: list[str] = []
    for cmd in commands:
        if shutil.which(cmd) is None:
            errors.append(f'CLI 命令缺失: {cmd}')
    return errors


def run_startup_self_check() -> bool:
    info('🔎 启动自检中...')

    errors: list[str] = []
    errors.extend(
        _check_python_packages(
            [
                'requests',
                'flask',
                'yaml',
                'werkzeug',
                'flask_login',
                'waitress',
            ]
        )
    )
    # 跳过 qoo-ip138 命令检查，因为它可能在 Python 脚本目录中
    # errors.extend(_check_cli_commands(['qoo-ip138']))

    if errors:
        error('❌ 启动自检失败：')
        for item in errors:
            error(f'  - {item}')
        return False

    info('✅ 启动自检通过')
    return True


def main() -> int:
    setup_logging()

    parser = argparse.ArgumentParser(description='EmbyQ')
    parser.add_argument('--self-check', action='store_true', help='仅执行启动自检并退出')
    args = parser.parse_args()

    try:
        config = load_config()
        update_proxy_config(config.get('proxy', {}))
    except Exception as exc:
        error(f'❌ 配置加载失败: {exc}')
        return 1

    if not run_startup_self_check():
        return 1

    if args.self_check:
        return 0

    db_manager = DatabaseManager(config['database']['name'])
    wish_store = WishStore(db_manager.db_path)
    emby_client = EmbyClient(server_url=config['emby']['server_url'], api_key=config['emby']['api_key'])
    security = EmbySecurity(emby_client)
    tmdb_client = TMDBClient(config.get('tmdb', {}))

    shadow_library = ShadowLibrary(db_manager.db_path)
    shadow_syncer = ShadowLibrarySyncer(emby_client, shadow_library)

    from location_service import LocationService

    use_geocache = config.get('ip_location', {}).get('use_geocache', False)
    emby_server_info = emby_client.get_server_info()
    location_service = LocationService(use_hiofd=use_geocache, db_manager=db_manager, emby_server_info=emby_server_info)

    monitor = EmbyMonitor(
        db_manager=db_manager,
        emby_client=emby_client,
        security_client=security,
        config=config,
        location_service=location_service,
    )

    web_server = WebServer(
        db_manager=db_manager,
        emby_client=emby_client,
        security_client=security,
        config=config,
        location_service=location_service,
        monitor=monitor,
        tmdb_client=tmdb_client,
        wish_store=wish_store,
        shadow_library=shadow_library,
        shadow_syncer=shadow_syncer,
    )

    web_server.start()
    monitor.run()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
