"""Public HTTPS fetching with DNS pinning and TLS hostname verification."""
import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit
import httpx


async def pinned_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("只能读取不含账号信息的 HTTPS 公网地址")
    addresses = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, parsed.port or 443, 0, socket.SOCK_STREAM)
    public = [x[4][0] for x in addresses if ipaddress.ip_address(x[4][0]).is_global]
    if len(public) != len(addresses) or not public:
        # Some local VPNs synthesize benchmark/private DNS answers. Resolve via a
        # fixed trusted HTTPS resolver, then pin a globally routable answer. Never
        # connect to the private address or merely disable the SSRF check.
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get("https://cloudflare-dns.com/dns-query", params={"name": parsed.hostname, "type": "A"}, headers={"Accept": "application/dns-json"})
            response.raise_for_status()
            public = []
            for answer in response.json().get("Answer", []):
                if answer.get("type") in {1, 28} and ipaddress.ip_address(answer["data"]).is_global:
                    public.append(answer["data"])
        if not public:
            raise ValueError("不能访问本机、内网或保留地址")
    address = public[0]
    host = f"[{address}]" if ":" in address else address
    host += f":{parsed.port}" if parsed.port else ""
    pinned = urlunsplit(("https", host, parsed.path or "/", parsed.query, ""))
    return pinned, {"Host": parsed.netloc}, {"sni_hostname": parsed.hostname}
