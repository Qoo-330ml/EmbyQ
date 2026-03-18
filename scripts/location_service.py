from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any


class LocationService:
    """IP 归属地查询服务：优先 IP-hiofd，失败回退 ip138。"""

    def __init__(self, timeout_sec: int = 45):
        self.timeout_sec = timeout_sec
        self.cache: dict[str, dict[str, Any]] = {}

        project_dir = os.environ.get("IP_HIOFD_PROJECT_DIR", "/home/pdz/Fnos/项目/IP-hiofd")
        self.hiofd_script = os.path.join(project_dir, "hiofd_browser.js")

    def _format_location(self, location: str, district: str, street: str, isp: str) -> str:
        parts = []

        if location:
            # 页面默认返回 "中国 · 浙江 · 金华"，统一替换为空格再按 "·" 拼接
            clean = location.replace(" ", "")
            parts.append(clean.replace("·", ""))

        if district:
            parts.append(district.strip())
        if street:
            parts.append(street.strip())

        left = "·".join(parts) if parts else "未知位置"
        return f"{left} | {isp.strip()}" if isp else left

    def _query_hiofd(self, ip_address: str) -> dict[str, Any]:
        if not os.path.exists(self.hiofd_script):
            raise FileNotFoundError(f"hiofd script not found: {self.hiofd_script}")

        proc = subprocess.run(
            ["node", self.hiofd_script, ip_address],
            capture_output=True,
            text=True,
            timeout=self.timeout_sec,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "hiofd query failed").strip())

        data = json.loads((proc.stdout or "").strip())
        result_ip = str(data.get("resultIp") or "").strip()
        if result_ip and result_ip != ip_address:
            raise RuntimeError(f"resultIp mismatch: {result_ip} != {ip_address}")

        location = str(data.get("location") or "").strip()
        district = str(data.get("district") or "").strip()
        street = str(data.get("street") or "").strip()
        isp = str(data.get("isp") or "").strip()

        return {
            "provider": "hiofd",
            "ip": ip_address,
            "location": location,
            "district": district,
            "street": street,
            "isp": isp,
            "formatted": self._format_location(location, district, street, isp),
            "ts": int(time.time()),
        }

    def _query_ip138(self, ip_address: str) -> dict[str, Any]:
        from ip138.ip138 import ip138

        result = ip138(ip_address)
        location = str(result.get("归属地") or "").strip()
        isp = str(result.get("运营商") or "").strip()

        # ip138 没有稳定区/街道字段，这里保持空
        return {
            "provider": "ip138",
            "ip": ip_address,
            "location": location,
            "district": "",
            "street": "",
            "isp": isp,
            "formatted": self._format_location(location, "", "", isp),
            "ts": int(time.time()),
        }

    def lookup(self, ip_address: str) -> dict[str, Any]:
        if not ip_address:
            return {
                "provider": "none",
                "ip": "",
                "location": "",
                "district": "",
                "street": "",
                "isp": "",
                "formatted": "未知位置",
                "ts": int(time.time()),
            }

        if ip_address in self.cache:
            return self.cache[ip_address]

        try:
            info = self._query_hiofd(ip_address)
        except Exception as e:
            print(f"📍 Hiofd 查询失败({ip_address}): {e}，回退 ip138")
            try:
                info = self._query_ip138(ip_address)
            except Exception as e2:
                print(f"📍 ip138 查询也失败({ip_address}): {e2}")
                info = {
                    "provider": "none",
                    "ip": ip_address,
                    "location": "",
                    "district": "",
                    "street": "",
                    "isp": "",
                    "formatted": "解析失败",
                    "ts": int(time.time()),
                }

        self.cache[ip_address] = info
        return info
