import json
import hashlib
from pathlib import Path
import asyncio
from types import SimpleNamespace
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.api import app, limits
from backend.config import settings
from backend import models


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "publish_dir", str(tmp_path / "published"))
    limits.clear()
    with TestClient(app) as c:
        yield c


def test_publication_lifecycle_capability_and_seed_data(client):
    ident = "a" * 32
    body = {"html": "<!doctype html><html><body>Real app</body></html>", "title": "Test app", "secret": "owner-" * 8, "data": {"items": '["preview record"]'}}
    assert client.put(f"/api/publications/{ident}", json=body).status_code == 410
    path = Path(settings.publish_dir) / f"{ident}.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"owner": hashlib.sha256(body["secret"].encode()).hexdigest(), "html": body["html"], "title": body["title"], "data": body["data"], "updated": 1}))
    public = client.get(f"/api/publications/{ident}").json()
    assert public["data"] == body["data"]
    assert "owner" not in public and "secret" not in public
    assert client.post(f"/api/publications/{ident}/unpublish", json={"secret": "wrong-" * 8}).status_code == 403
    assert client.post(f"/api/publications/{ident}/unpublish", json={"secret": body["secret"]}).status_code == 200
    assert client.get(f"/api/publications/{ident}").status_code == 404
    assert client.put(f"/api/publications/{ident}", json=body).status_code == 410


def test_invalid_artifact_and_cross_origin_requests_rejected(client):
    body = {"html": "not an html document", "title": "Invalid", "secret": "owner-" * 8}
    assert client.put("/api/publications/" + "b" * 32, json=body).status_code == 410
    assert client.put("/api/publications/../secrets", json=body).status_code != 200
    assert client.post("/api/test", json={}, headers={"Origin": "https://untrusted.invalid"}).status_code == 403
    assert client.get("/api/health").json()["database"] is False
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("protocol,provider", [("openai", "custom"), ("anthropic", "anthropic"), ("openai", "deepseek")])
async def test_real_protocol_adapters_parse_streams_and_headers(monkeypatch, protocol, provider):
    seen = []
    def handler(request):
        seen.append(request)
        if protocol == "anthropic":
            payload = 'data: {"type":"content_block_delta","delta":{"text":"Hello"}}\n\ndata: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}\n\n'
        else:
            payload = 'data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}\n\ndata: [DONE]\n\n'
        return httpx.Response(200, text=payload, headers={"content-type": "text/event-stream"})
    original = httpx.AsyncClient
    monkeypatch.setattr(models.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    async def pinned(url):
        return url, {}, {}
    monkeypatch.setattr(models, "pinned_url", pinned)
    profile = SimpleNamespace(key="fake-test-key", provider=provider, protocol=protocol, base_url="https://model.invalid/v1", model="test-model")
    assert await models.complete(profile, [{"role": "user", "content": "Test"}]) == "Hello"
    assert seen[0].headers.get("x-api-key" if protocol == "anthropic" else "authorization") == ("fake-test-key" if protocol == "anthropic" else "Bearer fake-test-key")
    body = json.loads(seen[0].content)
    assert body["stream"] is True and body["model"] == "test-model"
    if provider == "deepseek":
        assert body["thinking"] == {"type": "disabled"}
    else:
        assert "thinking" not in body


def test_private_addresses_rejected(monkeypatch):
    import socket
    from backend.security import public_url
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(Exception):
        public_url("https://attacker.invalid/v1")


def test_free_production_disables_public_hosting(client, monkeypatch):
    monkeypatch.setattr(settings, "production", True)
    monkeypatch.setattr(settings, "publish_durable", False)
    assert client.get("/api/health").json()["publishing_enabled"] is False
    body = {"html": "<!doctype html><html><body>App</body></html>", "title": "App", "secret": "x" * 40}
    assert client.put("/api/publications/" + "c" * 32, json=body).status_code == 410


async def test_research_slow_source_cannot_block_other_sources(monkeypatch):
    from backend import research
    cancelled = asyncio.Event()

    async def search(query):
        return [{"title": x, "url": x, "snippet": "Search summary"} for x in ["slow", "fast"]]

    async def read(url):
        if url == "slow":
            try:
                await asyncio.sleep(60)
            finally:
                cancelled.set()
        return "Actual page text"

    async def log(text):
        pass

    monkeypatch.setattr(research, "search_web", search)
    monkeypatch.setattr(research, "read_page", read)
    monkeypatch.setattr(research, "PAGE_TIMEOUT", 0.02)
    sources = await asyncio.wait_for(research.gather_sources("test", log), 1)
    assert cancelled.is_set()
    assert sources[0]["read"] is False and sources[0]["content"] == "Search summary"
    assert sources[1]["read"] is True and sources[1]["content"] == "Actual page text"


async def test_saved_profile_never_returns_model_key_in_stream(client, monkeypatch):
    from backend import api
    secret = 'private-model-secret'
    profile = SimpleNamespace(key=secret, provider='openai', protocol='openai', base_url='https://example.com', model='test')
    monkeypatch.setattr(api, 'resolve_profile', lambda request, ident: profile)
    async def fake_complete(profile, messages, **kwargs):
        await kwargs['on_delta']('result: private-model-')
        await kwargs['on_delta']('secret')
        return 'result: ' + secret
    monkeypatch.setattr(api, 'complete', fake_complete)
    response = client.post('/api/run', json={'profile_id':'personal','mode':'plan','prompt':'test'})
    assert response.status_code == 200
    assert secret not in response.text
    assert '[redacted]' in response.text


def test_research_requires_confirmed_plan_and_plan_never_searches(client, monkeypatch):
    from backend import api
    calls = []
    async def fake_complete(profile, messages, **kwargs):
        calls.append(messages)
        await kwargs['on_delta']('# 研究计划\n目标、范围、问题、检索方向、报告结构')
        return '# 研究计划\n目标、范围、问题、检索方向、报告结构'
    async def forbidden(*args):
        raise AssertionError('planning must not search')
    monkeypatch.setattr(api, 'complete', fake_complete)
    monkeypatch.setattr(api, 'gather_sources', forbidden)
    profile = {'provider':'custom','protocol':'openai','base_url':'https://model.invalid','model':'test','key':'key'}
    assert client.post('/api/run', json={'profile':profile,'mode':'research','prompt':'topic'}).status_code == 400
    result = client.post('/api/run', json={'profile':profile,'mode':'research_plan','prompt':'topic'})
    assert '研究计划' in result.text and '"type": "done"' in result.text
    assert len(calls) == 1


def test_research_uses_confirmed_plan_and_records_sources(client, monkeypatch):
    from backend import api
    calls, queries = [], []
    async def fake_complete(profile, messages, **kwargs):
        calls.append(messages[0]['content'])
        if 'on_delta' not in kwargs:
            return '["specific query", "failed query"]'
        await kwargs['on_delta']('发现 [1](https://example.com)')
        return '发现 [1](https://example.com)'
    async def gather(query, log):
        queries.append(query)
        if query == 'failed query':
            raise ValueError('搜索不可用')
        return [{'title':'A','url':'https://example.com','content':'正文','read':True}, {'title':'B','url':'https://example.org','content':'摘要','read':False}]
    monkeypatch.setattr(api, 'complete', fake_complete)
    monkeypatch.setattr(api, 'gather_sources', gather)
    profile = {'provider':'custom','protocol':'openai','base_url':'https://model.invalid','model':'test','key':'secret'}
    result = client.post('/api/run', json={'profile':profile,'mode':'research','prompt':'topic','plan':'最终计划：只研究水资源'})
    assert queries == ['specific query','failed query']
    assert all('最终计划：只研究水资源' in x for x in calls)
    assert '仅读取搜索摘要' in result.text and '搜索不可用' in result.text and '"type": "done"' in result.text


def test_removed_check_mode_is_rejected(client):
    profile = {"provider": "custom", "protocol": "openai", "base_url": "https://model.invalid", "model": "test", "key": "key"}
    response = client.post("/api/run", json={"profile": profile, "mode": "check", "prompt": "test"})
    assert response.status_code == 400
    assert response.json()["detail"] == "无效运行模式"
