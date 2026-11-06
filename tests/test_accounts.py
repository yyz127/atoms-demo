import uuid
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from backend.api import app, limits
from backend import accounts
from backend.config import settings


def test_unconfigured_auth_and_removed_google_login_fail_closed(monkeypatch):
    monkeypatch.setattr(settings, 'database_url', '')
    limits.clear()
    with TestClient(app) as client:
        assert client.get('/api/auth/me').status_code == 401
        assert client.get('/api/auth/google/start').status_code == 404
        assert client.get('/api/auth/google/callback?state=forged&code=forged').status_code == 404
        assert client.post('/api/auth/register', json={'email': 'person@example.com', 'password': 'long-enough-password'}).status_code == 503
        assert client.post('/api/auth/email', json={'email': 'person@example.com'}).status_code in (404, 405)
        assert client.get('/api/workspace').status_code == 401
        assert client.get('/api/profiles').status_code == 401


def test_workspace_rejects_preview_and_profiles_before_writing(monkeypatch):
    monkeypatch.setattr(accounts, 'user', lambda request: (uuid.uuid4(), 'user@example.com'))
    monkeypatch.setattr(accounts, 'db', lambda: (_ for _ in ()).throw(AssertionError('must not write')))
    with TestClient(app) as client:
        for data in [
            {'schema': 1, 'chats': [{'previewData': {'business': 'secret'}}], 'profiles': []},
            {'schema': 1, 'chats': [], 'profiles': [{'key': 'secret'}]},
            {'schema': 1, 'chats': [None], 'profiles': []},
        ]:
            assert client.put('/api/workspace', json={'revision': 0, 'data': data}).status_code == 400


def test_key_encryption_and_redirect_validation(monkeypatch):
    monkeypatch.setattr(settings, 'encryption_key', Fernet.generate_key().decode())
    encrypted = accounts.cipher().encrypt(b'model-secret')
    assert b'model-secret' not in encrypted
    assert accounts.cipher().decrypt(encrypted) == b'model-secret'
    assert accounts.safe_path('//evil.example') == '/'
    assert accounts.safe_path('/\\evil.example') == '/'
    assert accounts.safe_path('/?chat=1#section') == '/?chat=1#section'


def test_password_registration_login_and_legacy_protection(monkeypatch):
    users, sessions = {}, {}
    legacy_id = uuid.uuid4()
    users['legacy@example.com'] = (legacy_id, None)
    class Cursor:
        def __init__(self, row=None): self.row = row
        def fetchone(self): return self.row
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def execute(self, sql, params):
            if sql.startswith('INSERT INTO users'):
                uid, email, hashed = params
                if email in users: return Cursor()
                users[email] = (uid, hashed)
                return Cursor((uid,))
            if sql.startswith('SELECT id,password_hash'):
                return Cursor(users.get(params[0]))
            if sql.startswith('INSERT INTO sessions'):
                token, uid, expires = params
                sessions[token] = uid
            elif sql.startswith('DELETE FROM sessions'):
                sessions.pop(params[0], None)
            elif sql.startswith('SELECT u.id,u.email'):
                uid = sessions.get(params[0])
                return Cursor(next(((u, email) for email, (u, _) in users.items() if u == uid), None))
            elif sql.startswith('SELECT password_hash IS NULL'):
                return Cursor(next(((hashed is None,) for uid, hashed in users.values() if uid == params[0]), None))
            elif sql.startswith('UPDATE users SET password_hash'):
                hashed, uid = params
                for email, (u, old) in users.items():
                    if u == uid and old is None:
                        users[email] = (uid, hashed)
                        return Cursor((uid,))
            return Cursor()
    monkeypatch.setattr(accounts, 'db', Connection)
    limits.clear()
    with TestClient(app) as a, TestClient(app) as b:
        invalid = a.post('/api/auth/register', json={'email':'person@example.com','password':'short'})
        assert invalid.status_code == 400 and 'short' not in invalid.text
        body = {'email': 'PERSON@example.com', 'password': 'correct-horse-battery'}
        assert a.post('/api/auth/register', json=body).status_code == 200
        assert users['person@example.com'][1] != body['password']
        assert body['password'] not in users['person@example.com'][1]
        assert b.post('/api/auth/register', json=body).status_code == 409
        assert b.post('/api/auth/login', json={**body, 'password':'incorrect-password'}).status_code == 401
        assert b.post('/api/auth/login', json=body).status_code == 200
        assert a.get('/api/auth/me').json()['id'] == b.get('/api/auth/me').json()['id']
        assert a.post('/api/auth/logout').status_code == 200
        assert a.get('/api/auth/me').status_code == 401
        assert b.get('/api/auth/me').status_code == 200
        assert a.post('/api/auth/register', json={'email':'legacy@example.com', 'password':body['password']}).status_code == 409
        assert a.post('/api/auth/login', json={'email':'legacy@example.com', 'password':body['password']}).status_code == 401
        assert a.post('/api/auth/set-password', json={'password':body['password']}).status_code == 401
        sessions[accounts.digest('legacy-session')] = legacy_id
        a.cookies.set('atmos_session', 'legacy-session')
        assert a.get('/api/auth/me').json()['needs_password'] is True
        assert a.post('/api/auth/set-password', json={'password':body['password']}).status_code == 200
        assert a.post('/api/auth/set-password', json={'password':'another-password'}).status_code == 409
        assert b.post('/api/auth/login', json={'email':'legacy@example.com','password':body['password']}).status_code == 200
        assert b.get('/api/auth/me').json()['id'] == str(legacy_id)


async def test_resend_retry_reuses_idempotency_key(monkeypatch):
    from backend import mail
    import httpx
    attempts = []
    async def send(params, options):
        attempts.append((params.copy(), options.copy()))
        if len(attempts) == 1:
            raise httpx.ConnectError('unavailable')
        return {'id': 'test-message-id'}
    async def no_wait(delay): pass
    monkeypatch.setattr(mail.resend.Emails, 'send_async', send)
    monkeypatch.setattr(mail.asyncio, 'sleep', no_wait)
    await mail.send_login_link('test-key', 'test@example.com', 'user@example.com', 'https://example.com/link', 'attempt')
    assert len(attempts) == 2
    assert attempts[0] == attempts[1]
    assert attempts[0][1]['idempotency_key'] == 'login/attempt'


async def test_resend_does_not_retry_invalid_request(monkeypatch):
    import pytest
    from backend import mail
    from resend.exceptions import ResendError
    attempts = []
    async def send(params, options):
        attempts.append(options)
        raise ResendError(400, 'validation_error', 'invalid', 'fix')
    monkeypatch.setattr(mail.resend.Emails, 'send_async', send)
    with pytest.raises(ResendError):
        await mail.send_login_link('test-key', 'test@example.com', 'user@example.com', 'https://example.com/link', 'attempt')
    assert len(attempts) == 1


async def test_resend_template_receives_login_url(monkeypatch):
    from backend import mail
    sent = []
    async def send(params, options):
        sent.append((params, options))
        return {'id': 'message'}
    monkeypatch.setattr(mail.resend.Emails, 'send_async', send)
    await mail.send_login_link('test-key', 'test@example.com', 'user@example.com', 'https://example.com/verify', 'attempt', 'template-id')
    params, options = sent[0]
    assert params['template'] == {'id': 'template-id', 'variables': {'LOGIN_URL': 'https://example.com/verify'}}
    assert 'text' not in params and 'html' not in params
    assert options['idempotency_key'] == 'login/attempt'


def test_profiles_are_scoped_to_authenticated_user_and_keys_are_masked(monkeypatch):
    from types import SimpleNamespace
    from cryptography.fernet import Fernet
    alice, bob = uuid.uuid4(), uuid.uuid4()
    sessions = {accounts.digest('alice-session'): (alice, 'alice@example.com'), accounts.digest('bob-session'): (bob, 'bob@example.com')}
    rows = {}
    class Result:
        def __init__(self, row=None, rows=None): self.row, self.rows = row, rows or []
        def fetchone(self): return self.row
        def fetchall(self): return self.rows
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def execute(self, sql, args):
            if sql.startswith('SELECT u.id,u.email'):
                return Result(sessions.get(args[0]))
            if sql.startswith('SELECT encrypted_key,key_last4'):
                row=rows.get((args[0],args[1]));return Result((row[6],row[7]) if row else None)
            if sql.startswith('INSERT INTO model_profiles'):
                uid, ident, name, provider, protocol, base, model, encrypted, last = args
                rows[uid,ident]=(ident,name,provider,protocol,base,model,encrypted,last);return Result()
            if sql.startswith('SELECT id,name,provider'):
                return Result(rows=[r[:6]+(r[7],) for (uid,_),r in rows.items() if uid==args[0]])
            if sql.startswith('SELECT provider,protocol,base_url'):
                row=rows.get((args[0],args[1]));return Result((row[2],row[3],row[4],row[5],row[6]) if row else None)
            raise AssertionError(sql)
    monkeypatch.setattr(accounts, 'db', Connection)
    monkeypatch.setattr(settings, 'encryption_key', Fernet.generate_key().decode())
    with TestClient(app) as a, TestClient(app) as b:
        a.cookies.set('atmos_session','alice-session');b.cookies.set('atmos_session','bob-session')
        body={'id':'same-id','name':'personal','provider':'openai','protocol':'openai','base_url':'https://example.com/v1','model':'model','key':'super-secret-1234'}
        assert a.put('/api/profiles/same-id',json=body).status_code==200
        assert b.get('/api/profiles').json()==[]
        assert b.post('/api/profiles/same-id/test').status_code==404
        result=a.get('/api/profiles').json()
        assert result[0]['key_last4']=='1234' and 'super-secret' not in str(result)
        assert b'super-secret' not in rows[alice,'same-id'][6]
        assert a.get('/api/profiles',headers={'X-Atmos-User':str(bob)}).status_code==409
