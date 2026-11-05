import asyncio
import re
import base64
from urllib.parse import urlencode, urlsplit, parse_qs
import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from .config import settings
from .network import pinned_url

SEARCH_TIMEOUT = 35
PAGE_TIMEOUT = 15


async def read_page(url):
    """Read a limited public document, following only revalidated public redirects."""
    for _ in range(4):
        pinned, headers, extensions = await pinned_url(url)
        headers["User-Agent"] = "AtmosResearch/0.1 (+public-document-reader)"
        async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False) as client:
            async with client.stream("GET", pinned, headers=headers, extensions=extensions) as response:
                if response.is_redirect:
                    from urllib.parse import urljoin
                    url = urljoin(url, response.headers["location"])
                    continue
                response.raise_for_status()
                if "text/" not in response.headers.get("content-type", ""):
                    raise ValueError("当前仅支持公开网页与文本资料")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 1_500_000:
                        raise ValueError("页面超过读取大小限制")
        soup = BeautifulSoup(bytes(body), "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))
        return text[:18000]
    raise ValueError("页面跳转次数过多")


async def search_web(query):
    if settings.search_url:
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            response = await client.get(settings.search_url.rstrip("/") + "/search", params={"q": query, "format": "json"})
            response.raise_for_status()
            results = response.json().get("results", [])[:7]
            return [{"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("content", "")} for x in results]
    def search():
        return list(DDGS(timeout=20).text(query, max_results=7))
    try:
        raw = await asyncio.wait_for(asyncio.to_thread(search), 18)
        if raw:
            return [{"title": x.get("title", ""), "url": x.get("href", ""), "snippet": x.get("body", "")} for x in raw]
    except Exception:
        pass
    # Fetch the search HTML with the same DNS-pinned transport, retaining anchors.
    pinned, headers, extensions = await pinned_url("https://www.bing.com/search?" + urlencode({"q": query}))
    async with httpx.AsyncClient(timeout=25, follow_redirects=False, trust_env=False) as client:
        response = await client.get(pinned, headers={**headers,"User-Agent":"Mozilla/5.0"}, extensions=extensions)
        response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    for row in soup.select("li.b_algo"):
        link = row.select_one("h2 a")
        if not link:
            continue
        url = link.get("href", "")
        encoded = parse_qs(urlsplit(url).query).get("u", [""])[0]
        if encoded.startswith("a1"):
            try:
                url = base64.urlsafe_b64decode(encoded[2:] + "=" * (-len(encoded[2:]) % 4)).decode()
            except Exception:
                continue
        if not url.startswith("https://"):
            continue
        snippet = row.select_one(".b_caption p")
        results.append({"title": link.get_text(" ", strip=True), "url": url, "snippet": snippet.get_text(" ", strip=True) if snippet else ""})
    if not results:
        raise ValueError("搜索服务暂时不可用，可配置私有 SearXNG 或稍后重试")
    return results[:7]


async def gather_sources(query, log):
    await log("正在检索公开资料")
    try:
        results = await asyncio.wait_for(search_web(query), SEARCH_TIMEOUT)
    except asyncio.TimeoutError as exc:
        raise ValueError("公开资料检索超时，请稍后重试或配置 SearXNG") from exc
    if not results:
        raise ValueError("没有检索到可核实的资料，请调整主题或稍后重试")
    semaphore = asyncio.Semaphore(3)

    async def read_result(result):
        # An HTTP inactivity timeout cannot stop a server trickling bytes forever.
        # Bound the whole read, and keep other sources moving independently.
        result = dict(result)
        async with semaphore:
            await log(f"读取：{result['title'][:90]}")
            try:
                content = await asyncio.wait_for(read_page(result["url"]), PAGE_TIMEOUT)
                if not content.strip():
                    raise ValueError("页面正文为空")
                result.update(content=content, read=True)
            except Exception:
                result.update(content=result.get("snippet", ""), read=False)
        return result

    sources = await asyncio.gather(*(read_result(x) for x in results[:6]))
    if not any(x["read"] for x in sources):
        raise ValueError("已检索到链接，但网页读取全部失败，未生成未经核实的报告")
    return sources
