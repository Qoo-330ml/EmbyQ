from __future__ import annotations

import json
import shutil
import subprocess
import time
from typing import Any

from geocache_client import GeoCacheClient


class LocationService:
    """IP 归属地查询服务：支持 qoo-ip138 和自建库两种方式切换。"""

    def __init__(self, timeout_sec: int = 45, use_hiofd: bool = False, db_manager=None, emby_server_info: dict = None):
        self.timeout_sec = timeout_sec
        self.use_hiofd = use_hiofd
        self.cache: dict[str, dict[str, Any]] = {}
        self.hiofd_retries = 3
        self.hiofd_retry_delay_sec = 1.0
        self.db_manager = db_manager
        self.emby_server_info = emby_server_info or {}
        
        self.geocache_client = None
        self.geocache_enabled = self.use_hiofd
        if self.geocache_enabled:
            self.geocache_client = GeoCacheClient(emby_server_info=self.emby_server_info)
            print(f"🌍 GeoCache 已启用")

    def update_config(self, use_hiofd: bool):
        """更新配置并清空缓存"""
        old_provider = "自建库" if self.use_hiofd else "ip138"
        new_provider = "自建库" if use_hiofd else "ip138"
        old_geocache_enabled = self.geocache_enabled
        new_geocache_enabled = use_hiofd
        
        if old_provider != new_provider:
            print(f"📍 IP解析方式已切换: {old_provider} -> {new_provider}")
            self.use_hiofd = use_hiofd
            self.geocache_enabled = new_geocache_enabled
            
            # 更新 GeoCache 客户端
            if new_geocache_enabled and not old_geocache_enabled:
                self.geocache_client = GeoCacheClient(emby_server_info=self.emby_server_info)
                print(f"🌍 GeoCache 已启用")
            elif not new_geocache_enabled and old_geocache_enabled:
                self.geocache_client = None
                print(f"🌍 GeoCache 已禁用")
            
            self.cache.clear()
            print(f"📍 已清空IP解析缓存")

    def _format_location(self, location: str, district: str, street: str, isp: str) -> str:
        parts = []

        if location:
            clean = location.replace(" ", "")
            parts.append(clean.replace("·", ""))

        if district:
            parts.append(district.strip())
        if street:
            parts.append(street.strip())

        left = "·".join(parts) if parts else "未知位置"
        return f"{left} | {isp.strip()}" if isp else left

    def _run_cmd(self, cmd: list[str]) -> str:
        if not cmd:
            raise ValueError("空命令")

        if shutil.which(cmd[0]) is None:
            raise FileNotFoundError(f"命令未找到: {cmd[0]}")

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout_sec,
            check=False,
        )

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            stdout = (proc.stdout or "").strip()
            detail = stderr or stdout or f"exit={proc.returncode}"
            raise RuntimeError(f"命令执行失败: {' '.join(cmd)} | {detail}")

        return (proc.stdout or "").strip()

    def _query_ip138(self, ip_address: str) -> dict[str, Any]:
        output = self._run_cmd(["qoo-ip138", f"--ip={ip_address}"])

        location = ""
        isp = ""
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            for key in ("归属地", "归属地理位置", "location", "Location"):
                if key in line and (":" in line or "：" in line):
                    sep = "：" if "：" in line else ":"
                    location = line.rsplit(sep, 1)[1].strip()

            for key in ("运营商", "isp", "ISP"):
                if key in line and (":" in line or "：" in line):
                    sep = "：" if "：" in line else ":"
                    isp = line.rsplit(sep, 1)[1].strip()

        return {
            "provider": "ip138",
            "ip": ip_address,
            "location": location,
            "district": "",
            "street": "",
            "isp": isp,
            "latitude": None,
            "longitude": None,
            "formatted": self._format_location(location, "", "", isp),
            "ts": int(time.time()),
        }

    def _query_hiofd(self, ip_address: str) -> dict[str, Any]:
        last_err: Exception | None = None

        for attempt in range(1, self.hiofd_retries + 1):
            try:
                output = self._run_cmd(["ip-hiofd", "--ip", ip_address, "--json"])
                data = json.loads(output)

                result_ip = str(data.get("result_ip") or "").strip()
                if result_ip and result_ip != ip_address:
                    raise RuntimeError(
                        f"自建库 返回 IP 不一致: query={ip_address}, result={result_ip}"
                    )

                location = str(data.get("location") or "").strip()
                district = str(data.get("district") or "").strip()
                street = str(data.get("street") or "").strip()
                isp = str(data.get("isp") or "").strip()
                
                # 处理经纬度，转换为浮点数
                latitude = data.get("latitude")
                if latitude:
                    try:
                        latitude = float(latitude)
                    except (ValueError, TypeError):
                        latitude = None
                        
                longitude = data.get("longitude")
                if longitude:
                    try:
                        longitude = float(longitude)
                    except (ValueError, TypeError):
                        longitude = None

                return {
                    "provider": "自建库",
                    "ip": ip_address,
                    "location": location,
                    "district": district,
                    "street": street,
                    "isp": isp,
                    "latitude": latitude,
                    "longitude": longitude,
                    "formatted": self._format_location(location, district, street, isp),
                    "ts": int(time.time()),
                }
            except Exception as e:
                last_err = e
                if attempt < self.hiofd_retries:
                    print(
                        f"📍 自建库 查询重试({attempt}/{self.hiofd_retries}) {ip_address}: {e}"
                    )
                    time.sleep(self.hiofd_retry_delay_sec)

        raise RuntimeError(
            f"自建库 多次查询失败({self.hiofd_retries}次): {last_err}"
        )

    def lookup(self, ip_address: str) -> dict[str, Any]:
        if not ip_address:
            return {
                "provider": "none",
                "ip": "",
                "location": "",
                "district": "",
                "street": "",
                "isp": "",
                "latitude": None,
                "longitude": None,
                "formatted": "未知位置",
                "ts": int(time.time()),
            }

        current_provider = "自建库" if self.use_hiofd else "ip138"
        
        if ip_address in self.cache:
            cached_info = self.cache[ip_address]
            if cached_info.get("provider") == current_provider:
                return cached_info
            else:
                print(f"📍 解析方式已切换，重新查询 {ip_address}")

        info = None
        
        if self.db_manager:
            db_info = self.db_manager.get_ip_location(ip_address)
            if db_info and db_info.get("provider") == current_provider:
                info = db_info
                self.cache[ip_address] = info
                return info
            elif db_info:
                print(f"📍 数据库中IP归属地数据源已切换，重新查询 {ip_address}")

        try:
            if self.use_hiofd:
                info = self._query_hiofd(ip_address)
            else:
                info = self._query_ip138(ip_address)
        except Exception as e:
            provider = "自建库" if self.use_hiofd else "ip138"
            print(f"📍 {provider} 查询失败({ip_address}): {e}")
            info = {
                "provider": "none",
                "ip": ip_address,
                "location": "",
                "district": "",
                "street": "",
                "isp": "",
                "latitude": None,
                "longitude": None,
                "formatted": "解析失败",
                "ts": int(time.time()),
            }

        self.cache[ip_address] = info
        
        if info.get("provider") != "none" and self.db_manager:
            self.db_manager.save_ip_location(info)
        
        if info.get("provider") != "none" and self.geocache_enabled:
            self.geocache_client.report_location_info(info)
        
        return info
