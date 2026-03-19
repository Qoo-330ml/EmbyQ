from __future__ import annotations

import argparse
import importlib
import shutil
import sys
from typing import Iterable

from config_loader import load_config
from database import DatabaseManager
from emby_client import EmbyClient
from monitor import EmbyMonitor
from security import EmbySecurity
from web_server import WebServer


def _check_python_packages(packages: Iterable[str]) -> list[str]:
    errors: list[str] = []
    for package in packages:
        try:
            importlib.import_module(package)
        except Exception as exc:
            errors.append(f"Python 包缺失/不可用: {package} ({exc})")
    return errors


def _check_cli_commands(commands: Iterable[str]) -> list[str]:
    errors: list[str] = []
    for cmd in commands:
        if shutil.which(cmd) is None:
            errors.append(f"CLI 命令缺失: {cmd}")
    return errors



def run_startup_self_check() -> bool:
    print("🔎 启动自检中...")

    errors: list[str] = []
    errors.extend(
        _check_python_packages(
            [
                "requests",
                "flask",
                "yaml",
                "werkzeug",
                "flask_login",
                "waitress",
            ]
        )
    )
    errors.extend(_check_cli_commands(["qoo-ip138"]))

    if errors:
        print("❌ 启动自检失败：")
        for item in errors:
            print(f"  - {item}")
        return False

    print("✅ 启动自检通过")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Emby IPLimit")
    parser.add_argument("--self-check", action="store_true", help="仅执行启动自检并退出")
    args = parser.parse_args()

    # 先验证配置文件可读取
    try:
        config = load_config()
    except Exception as exc:
        print(f"❌ 配置加载失败: {exc}")
        return 1

    # 每次启动都执行自检
    if not run_startup_self_check():
        return 1

    if args.self_check:
        return 0

    # 初始化核心组件
    db_manager = DatabaseManager(config["database"]["name"])
    emby_client = EmbyClient(server_url=config["emby"]["server_url"], api_key=config["emby"]["api_key"])
    security = EmbySecurity(server_url=config["emby"]["server_url"], api_key=config["emby"]["api_key"])

    # 启动监控服务
    monitor = EmbyMonitor(
        db_manager=db_manager,
        emby_client=emby_client,
        security_client=security,
        config=config,
    )

    # 初始化并启动Web服务器
    web_server = WebServer(
        db_manager=db_manager,
        emby_client=emby_client,
        security_client=security,
        config=config,
    )
    web_server.start()

    # 运行监控服务
    monitor.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
