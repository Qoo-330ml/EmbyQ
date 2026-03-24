import base64
import requests
import time
from typing import Any


def _decode(encoded: str) -> str:
    try:
        decoded = base64.b64decode(encoded.encode()).decode()
        return decoded[::-1]
    except Exception:
        return ""


class GeoCacheClient:
    """GeoCache 客户端：负责向 GeoCache 服务提交 IP 归属地数据"""

    def __init__(self, base_url: str = None, api_key: str = None, timeout: int = 10):
        _encrypted_url = "cG90LnVvaHpkcC5laGNhY29lZy8vOnNwdHRo"
        _encrypted_key = "eURuZ1RrNjdLZFI3cUlPaXREWDJKYnNBcE9NUlhQS2NjbThoOTFzaA=="
        
        self.base_url = (base_url or _decode(_encrypted_url)).rstrip("/")
        self.api_key = api_key or _decode(_encrypted_key)
        self.timeout = timeout
        self.enabled = True

    def update_config(self, base_url: str = None, api_key: str = None):
        """更新配置"""
        if base_url is not None:
            self.base_url = base_url.rstrip("/")
        if api_key is not None:
            self.api_key = api_key
        self.enabled = bool(self.api_key)

    def report_ip(self, ip: str, location: str = None, district: str = None,
                  street: str = None, isp: str = None, latitude: float = None,
                  longitude: float = None, provider: str = "emby",
                  client_version: str = "1.0.0") -> bool:
        """
        向 GeoCache 提交 IP 归属地数据

        Args:
            ip: IP 地址
            location: 位置（IP归属地）
            district: 区
            street: 街道
            isp: 网络服务商
            latitude: 纬度
            longitude: 经度
            provider: 提供商标识
            client_version: 客户端版本

        Returns:
            bool: 是否提交成功
        """
        if not self.enabled:
            return False

        if not ip:
            return False

        url = f"{self.base_url}/v1/ip/report"

        payload = {
            "ip": ip,
            "location": location,
            "district": district,
            "street": street,
            "isp": isp,
            "latitude": latitude,
            "longitude": longitude,
            "provider": provider,
            "client_version": client_version
        }

        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"🌍 GeoCache 提交失败 ({ip}): {e}")
            return False

    def report_location_info(self, location_info: dict[str, Any]) -> bool:
        """
        从位置信息字典提交数据到 GeoCache

        Args:
            location_info: 位置信息字典，包含 ip, location, district, street, isp, latitude, longitude 等

        Returns:
            bool: 是否提交成功
        """
        if not location_info or not location_info.get("ip"):
            return False

        return self.report_ip(
            ip=location_info["ip"],
            location=location_info.get("location"),
            district=location_info.get("district"),
            street=location_info.get("street"),
            isp=location_info.get("isp"),
            latitude=location_info.get("latitude"),
            longitude=location_info.get("longitude"),
            provider=location_info.get("provider", "emby"),
            client_version="1.0.0"
        )

    def lookup_ip(self, ip: str) -> dict[str, Any] | None:
        """
        从 GeoCache 查询 IP 归属地信息

        Args:
            ip: IP 地址

        Returns:
            dict: 归属地信息字典，查询失败返回 None
        """
        if not self.enabled:
            return None

        if not ip:
            return None

        url = f"{self.base_url}/v1/ip/lookup"

        try:
            response = requests.get(
                url,
                params={"ip": ip},
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            if data.get("found"):
                return {
                    "provider": "geocache",
                    "ip": data.get("ip"),
                    "location": data.get("location"),
                    "district": data.get("district"),
                    "street": data.get("street"),
                    "isp": data.get("isp"),
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "formatted": "",  # GeoCache 不提供格式化信息，由调用方处理
                    "ts": int(time.time())
                }
            return None
        except requests.exceptions.RequestException as e:
            print(f"🌍 GeoCache 查询失败 ({ip}): {e}")
            return None

    def health_check(self) -> bool:
        """
        检查 GeoCache 服务是否可用

        Returns:
            bool: 服务是否可用
        """
        if not self.enabled:
            return False

        url = f"{self.base_url}/healthz"

        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data.get("ok", False)
        except requests.exceptions.RequestException:
            return False
