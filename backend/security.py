import ipaddress
import socket
from urllib.parse import urlsplit
from fastapi import HTTPException


def public_url(url: str) -> str:
    """Reject local/internal endpoints before sending any BYOK secret or reading a URL."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.fragment:
        raise HTTPException(400, "地址必须为不含账号信息的 HTTPS 公网地址")
    try:
        addresses = socket.getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
    except (OSError, ValueError):
        raise HTTPException(400, "无法解析此地址，请检查域名")
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise HTTPException(400, "不能访问本机、内网或保留地址")
    return url.rstrip("/")
