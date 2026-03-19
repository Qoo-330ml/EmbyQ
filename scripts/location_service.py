from __future__ import annotations

import shutil
import subprocess
import time
from typing import Any


class LocationService:
    """IP 归属地查询服务：仅使用 qoo-ip138（在线 pip 包 CLI）。"""

    def __init__(self, timeout_sec: int = 45):
        self.timeout_sec = timeout_sec
        self.cache: dict[str, dict[str, Any]] = {}

    def _format_location(self, location: str, district: str, street: str, isp: str) -> str:
        parts = []

        if location:
            # 页面常见返回如 "中国 · 浙江 · 金华"，统一清理后拼接
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
        # 按约定使用安装后 CLI：qoo-ip138 --ip=<ip>
        output = self._run_cmd(["qoo-ip138", f"--ip={ip_address}"])

        location = ""
        isp = ""
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            for key in ("归属地", "location", "Location"):
                if line.startswith(f"{key}:") or line.startswith(f"{key}："):
                    location = line.split(":", 1)[1].strip() if ":" in line else line.split("：", 1)[1].strip()

            for key in ("运营商", "isp", "ISP"):
                if line.startswith(f"{key}:") or line.startswith(f"{key}："):
                    isp = line.split(":", 1)[1].strip() if ":" in line else line.split("：", 1)[1].strip()

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
            info = self._query_ip138(ip_address)
        except Exception as e:
            print(f"📍 ip138 查询失败({ip_address}): {e}")
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
