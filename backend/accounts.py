"""Account APIs. PostgreSQL is opt-in and never trusts a client-supplied user id."""
import hashlib
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import psycopg
from psycopg.types.json import Jsonb
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from .config import settings

router = APIRouter(prefix='/api')
COOKIE = 'atmos_session'

def config(name):
    return getattr(settings, name.lower(), '')

def db():
    url = config('DATABASE_URL') or os.getenv('DATABASE_URL', '')
    if not url:
        raise HTTPException(503, '云端工作空间尚未配置数据库')
    try:
        return psycopg.connect(url, connect_timeout=5)
    except psycopg.Error:
        raise HTTPException(503, '云端数据库连接失败')

def migrate():
    with db() as conn:
        conn.execute((Path(__file__).parent / 'migrations/0001_accounts.sql').read_text())
        conn.execute((Path(__file__).parent / 'migrations/0002_passwords.sql').read_text())

def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()

def now():
    return datetime.now(timezone.utc)

def safe_path(path):
    return path if path.startswith('/') and not path.startswith('//') and '\\' not in path and '\r' not in path and '\n' not in path else '/'

def origin():
    value = config('PUBLIC_URL').rstrip('/')
    if not value:
        value = os.getenv('RENDER_EXTERNAL_URL', 'http://localhost:8000').rstrip('/')
    return value

def cipher():
    try:
        return Fernet(config('ENCRYPTION_KEY').encode())
    except (ValueError, TypeError):
        raise HTTPException(503, '服务端密钥加密配置不可用')

def user(request):
    token = request.cookies.get(COOKIE, '')
    if not token:
        raise HTTPException(401, '请先登录')
    with db() as conn:
        row = conn.execute('SELECT u.id,u.email FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token_hash=%s AND s.expires_at>now()', (digest(token),)).fetchone()
    if not row:
        raise HTTPException(401, '会话已过期，请重新登录')
    expected = request.headers.get('x-atmos-user')
    if expected and expected != str(row[0]):
        raise HTTPException(409, '登录账号已切换，请刷新页面')
    return row

def establish(response, uid, previous=""):
    if previous:
        with db() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash=%s", (digest(previous),))
    token = secrets.token_urlsafe(32)
    with db() as conn:
        conn.execute('INSERT INTO sessions VALUES (%s,%s,%s)', (digest(token), uid, now()+timedelta(days=14)))
    response.set_cookie(COOKIE, token, httponly=True, secure=origin().startswith('https://'), samesite='lax', max_age=14*86400, path='/')

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    value = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600_000).hex()
    return f'pbkdf2_sha256$600000${salt}${value}'

def password_matches(password, stored):
    try:
        algorithm, iterations, salt, value = stored.split('$')
        if algorithm != 'pbkdf2_sha256' or iterations != '600000':
            return False
        return secrets.compare_digest(password_hash(password, salt), stored)
    except (ValueError, AttributeError):
        return False

@router.get('/auth/me')
def me(request: Request):
    try:
        uid, email = user(request)
    except HTTPException as exc:
        if exc.status_code != 401:
            raise
        response = JSONResponse({'detail': exc.detail}, status_code=401)
        response.delete_cookie(COOKIE, path='/')
        return response
    with db() as conn:
        row = conn.execute('SELECT password_hash IS NULL FROM users WHERE id=%s', (uid,)).fetchone()
    return {'id':str(uid),'email':email,'needs_password':bool(row[0])}

@router.post('/auth/logout')
def logout(request: Request, response: Response):
    token=request.cookies.get(COOKIE, '')
    if token:
        with db() as conn:
            conn.execute('DELETE FROM sessions WHERE token_hash=%s', (digest(token),))
    response.delete_cookie(COOKIE, path='/')
    return {'ok':True}

class PasswordInput(BaseModel):
    email: str = Field(max_length=254)
    password: str

def check_password_length(password):
    if not 10 <= len(password) <= 256:
        raise HTTPException(400, '密码长度须为 10 至 256 个字符')

def normalized_email(email):
    email = email.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise HTTPException(400, '请输入有效邮箱')
    return email

@router.post('/auth/register')
def register(body: PasswordInput, request: Request, response: Response):
    from .api import rate_limit
    rate_limit(request, 'register', 5, 300)
    email = normalized_email(body.email)
    check_password_length(body.password)
    uid = uuid.uuid4()
    with db() as conn:
        row = conn.execute('INSERT INTO users (id,email,password_hash) VALUES (%s,%s,%s) ON CONFLICT (email) DO NOTHING RETURNING id', (uid,email,password_hash(body.password))).fetchone()
    if not row:
        raise HTTPException(409, '该邮箱已有账号，请登录；旧账号需在已登录的设备上设置密码')
    establish(response, uid, request.cookies.get(COOKIE, ''))
    return {'ok': True}

@router.post('/auth/login')
def password_login(body: PasswordInput, request: Request, response: Response):
    from .api import rate_limit
    rate_limit(request, 'login', 10, 300)
    email = normalized_email(body.email)
    check_password_length(body.password)
    with db() as conn:
        row = conn.execute('SELECT id,password_hash FROM users WHERE email=%s', (email,)).fetchone()
    dummy = 'pbkdf2_sha256$600000$00000000000000000000000000000000$' + '0'*64
    valid = password_matches(body.password, row[1] if row and row[1] else dummy)
    if not row or not valid:
        raise HTTPException(401, '邮箱或密码不正确；旧账号请在已登录的设备上设置密码')
    establish(response, row[0], request.cookies.get(COOKIE, ''))
    return {'ok': True}

class SetPasswordInput(BaseModel):
    password: str

@router.post('/auth/set-password')
def set_initial_password(body: SetPasswordInput, request: Request):
    from .api import rate_limit
    rate_limit(request, 'set-password', 5, 300)
    uid, _ = user(request)
    check_password_length(body.password)
    with db() as conn:
        row = conn.execute('UPDATE users SET password_hash=%s WHERE id=%s AND password_hash IS NULL RETURNING id', (password_hash(body.password), uid)).fetchone()
    if not row:
        raise HTTPException(409, '账号已经设置密码')
    return {'ok': True}

class Workspace(BaseModel):
    revision: int = Field(ge=0)
    data: dict

@router.get('/workspace')
def get_workspace(request: Request):
    uid,_=user(request)
    with db() as conn:
        row=conn.execute('SELECT revision,data FROM workspaces WHERE user_id=%s',(uid,)).fetchone()
    return {'revision':row[0], 'data':row[1]} if row else {'revision':0,'data':None}

@router.put('/workspace')
def put_workspace(body: Workspace, request: Request):
    uid,_=user(request)
    data=body.data
    if len(str(data))>10_000_000 or data.get('schema')!=1 or not isinstance(data.get('chats'),list):
        raise HTTPException(400,'工作空间格式无效或超过大小限制')
    if any(not isinstance(c, dict) for c in data['chats']):
        raise HTTPException(400, '工作空间对话格式无效')
    if data.get('profiles') or any(c.get('previewData') for c in data['chats']):
        raise HTTPException(400,'工作空间不能包含模型凭证或应用业务数据')
    with db() as conn:
        conn.execute('INSERT INTO workspaces (user_id,revision,data) VALUES (%s,0,%s) ON CONFLICT DO NOTHING',(uid,Jsonb({})))
        row=conn.execute('UPDATE workspaces SET revision=revision+1,data=%s WHERE user_id=%s AND revision=%s RETURNING revision',(Jsonb(data),uid,body.revision)).fetchone()
        if not row:
            raise HTTPException(409,'云端工作空间已被其他页面修改，请重新加载后处理冲突')
    return {'revision':row[0]}

class ModelInput(BaseModel):
    id: str = Field(min_length=1,max_length=100)
    name: str = Field(max_length=150)
    provider: str = Field(max_length=32)
    protocol: str
    base_url: str = Field(max_length=1000)
    model: str = Field(min_length=1,max_length=150)
    key: str = Field(default='',max_length=5000)

@router.get('/profiles')
def profiles(request: Request):
    uid,_=user(request)
    with db() as conn:
        rows=conn.execute('SELECT id,name,provider,protocol,base_url,model,key_last4 FROM model_profiles WHERE user_id=%s ORDER BY id',(uid,)).fetchall()
    return [dict(zip(('id','name','provider','protocol','base_url','model','key_last4'),row)) for row in rows]

@router.put('/profiles/{ident}')
def save_profile(ident: str, body: ModelInput, request: Request):
    uid,_=user(request)
    if ident!=body.id or body.protocol not in ('openai','anthropic') or not body.base_url.startswith('https://'):
        raise HTTPException(400,'模型配置无效')
    with db() as conn:
        old=conn.execute('SELECT encrypted_key,key_last4 FROM model_profiles WHERE user_id=%s AND id=%s',(uid,ident)).fetchone()
        if not body.key and not old:
            raise HTTPException(400,'请填写 API Key')
        encrypted=cipher().encrypt(body.key.encode()) if body.key else old[0]
        last=body.key[-4:] if body.key else old[1]
        conn.execute('INSERT INTO model_profiles VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (user_id,id) DO UPDATE SET name=excluded.name,provider=excluded.provider,protocol=excluded.protocol,base_url=excluded.base_url,model=excluded.model,encrypted_key=excluded.encrypted_key,key_last4=excluded.key_last4',(uid,ident,body.name,body.provider,body.protocol,body.base_url,body.model,encrypted,last))
    return {'ok':True}

@router.delete('/profiles/{ident}')
def delete_profile(ident: str, request: Request):
    uid,_=user(request)
    with db() as conn:
        conn.execute('DELETE FROM model_profiles WHERE user_id=%s AND id=%s',(uid,ident))
    return {'ok':True}

def resolve_profile(request, ident):
    uid,_=user(request)
    with db() as conn:
        row=conn.execute('SELECT provider,protocol,base_url,model,encrypted_key FROM model_profiles WHERE user_id=%s AND id=%s',(uid,ident)).fetchone()
    if not row:
        raise HTTPException(404,'模型配置不存在')
    try:
        key=cipher().decrypt(bytes(row[4])).decode()
    except (InvalidToken, UnicodeError):
        raise HTTPException(503,'模型密钥无法解密')
    from .api import Profile
    return Profile(provider=row[0],protocol=row[1],base_url=row[2],model=row[3],key=key)
