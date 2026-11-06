"""Opt-in PostgreSQL wire-protocol integration; use only a disposable database."""
import os
import uuid
from datetime import timedelta
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from backend import accounts
from backend.api import app, limits
from backend.config import settings


@pytest.fixture
def database(monkeypatch):
    url = os.getenv('ATMOS_TEST_DATABASE_URL')
    if not url:
        pytest.skip('set ATMOS_TEST_DATABASE_URL to a disposable PostgreSQL test database')
    monkeypatch.setattr(settings, 'database_url', url)
    monkeypatch.setattr(settings, 'encryption_key', Fernet.generate_key().decode())
    accounts.migrate()
    ids = [uuid.uuid4(), uuid.uuid4()]
    with accounts.db() as conn:
        for uid, name in zip(ids, ['alice', 'bob']):
            conn.execute('INSERT INTO users (id,email) VALUES (%s,%s)',(uid, f'{uid}@example.invalid'))
            conn.execute('INSERT INTO sessions VALUES (%s,%s,%s)', (accounts.digest(name+'-token'),uid,accounts.now()+timedelta(hours=1)))
    with accounts.db() as conn:
        conn.execute('INSERT INTO sessions VALUES (%s,%s,%s)', (accounts.digest('alice-second-token'),ids[0],accounts.now()+timedelta(hours=1)))
    yield ids
    with accounts.db() as conn:
        for uid in ids: conn.execute('DELETE FROM users WHERE id=%s',(uid,))


def test_postgres_accounts_data_profiles_and_logout(database, monkeypatch):
    with TestClient(app) as a, TestClient(app) as b, TestClient(app) as second_browser:
        a.cookies.set('atmos_session','alice-token');b.cookies.set('atmos_session','bob-token');second_browser.cookies.set('atmos_session','alice-second-token')
        base={'schema':1,'profiles':[],'profileId':'','chats':[{'id':'shared-id','title':'Alice private','previewData':{}}], 'folders':[], 'runs':[], 'schedules':[], 'notices':[]}
        assert a.put('/api/workspace',json={'revision':0,'data':base}).status_code==200
        assert second_browser.get('/api/workspace').json()['data']['chats'][0]['title']=='Alice private'
        assert b.get('/api/workspace').json()['data'] is None
        assert a.put('/api/workspace',json={'revision':0,'data':base}).status_code==409
        assert b.put('/api/workspace',json={'revision':0,'data':{**base,'chats':[{'id':'shared-id','title':'Bob private','previewData':{}}]}}).status_code==200
        assert a.get('/api/workspace').json()['data']['chats'][0]['title']=='Alice private'
        profile={'id':'same','name':'test','provider':'openai','protocol':'openai','base_url':'https://example.com/v1','model':'test','key':'integration-secret-1234'}
        assert a.put('/api/profiles/same',json=profile).status_code==200
        assert b.get('/api/profiles').json()==[]
        assert b.post('/api/profiles/same/test').status_code==404
        from backend import api
        async def mock_complete(profile, messages, **kwargs):
            assert profile.key == 'integration-secret-1234'
            return 'model completed'
        monkeypatch.setattr(api, 'complete', mock_complete)
        assert a.post('/api/run',json={'profile_id':'same','mode':'plan','prompt':'test'}).status_code==200
        assert b.post('/api/run',json={'profile_id':'same','mode':'plan','prompt':'test'}).status_code==404
        assert 'integration-secret' not in str(a.get('/api/profiles').json())
        with accounts.db() as conn:
            ciphertext=conn.execute('SELECT encrypted_key FROM model_profiles WHERE user_id=%s AND id=%s',(database[0],'same')).fetchone()[0]
        assert b'integration-secret' not in bytes(ciphertext)
        assert a.get('/api/workspace',headers={'X-Atmos-User':str(database[1])}).status_code==409
        assert a.post('/api/auth/logout').status_code==200
        assert a.get('/api/auth/me').status_code==401
        assert second_browser.get('/api/auth/me').status_code==200
        assert b.get('/api/auth/me').status_code==200



def test_password_registration_on_disposable_database(database):
    email = f'{uuid.uuid4()}@example.invalid'
    password = 'integration-password-only'
    limits.clear()
    try:
        with TestClient(app) as first, TestClient(app) as second:
            assert first.post('/api/auth/register', json={'email':email, 'password':password}).status_code == 200
            assert second.post('/api/auth/login', json={'email':email, 'password':password}).status_code == 200
            assert first.get('/api/auth/me').json()['id'] == second.get('/api/auth/me').json()['id']
            with accounts.db() as conn:
                stored = conn.execute('SELECT password_hash FROM users WHERE email=%s', (email,)).fetchone()[0]
            assert password not in stored and accounts.password_matches(password, stored)
            assert first.post('/api/auth/logout').status_code == 200
            assert second.get('/api/auth/me').status_code == 200
    finally:
        with accounts.db() as conn:
            conn.execute('DELETE FROM users WHERE email=%s', (email,))
