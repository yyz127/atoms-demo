# 账号与云端工作空间部署（实现中）

2026-11-06 的需求覆盖旧的“平台无账号、全部本地保存”决策。账号接口、前端云同步、迁移入口和模型密钥加密代码已实现；临时 PostgreSQL 兼容数据库与模拟接口完成部分验证，Render 连接和线上端到端验收尚未完成。现有免费 Web Service 不启用公开应用托管。

## 目标架构与迁移

浏览器 → FastAPI 认证/数据接口 → 一套 PostgreSQL。会话使用随机令牌、HttpOnly cookie，数据库存令牌哈希；平台账号统一使用邮箱验证注册和登录，不提供 Google 第三方登录。使用 Resend 官方 Python 异步 SDK 发送 15 分钟有效、一次性的验证链接，并绑定发起请求的浏览器；新邮箱验证后创建账号，已注册邮箱验证后登录。服务端使用 Fernet 加密模型 Key，只返回末四位。工作空间以 user_id 隔离、版本号检测并发修改。生成应用的业务数据不写云端；游客本地工作空间保持独立，旧数据迁移须先预览、确认并追加而不覆盖。

运行 `uv run python -m backend.migrate` 创建初始表及索引。此命令必须在配置数据库之后运行。Render Free 不提供预部署命令或远程 Shell；Docker 启动入口在配置数据库时会自动执行幂等迁移，失败则停止启动并提示，不依赖外部连接。当前初始 SQL 已在本机 PGlite PostgreSQL 兼容库验收，尚未在 Render PostgreSQL 验收。定时任务仍仅页面打开期间执行。

## 配置项

仅在实际部署环境提供，不提交真实值：

- `ATMOS_DATABASE_URL`：PostgreSQL 连接字符串，或使用 `DATABASE_URL`。
- `ATMOS_ENCRYPTION_KEY`：持久保存的 Fernet 密钥，可用 `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'` 生成；丢失或替换会导致原模型 Key 无法解密。
- `ATMOS_PUBLIC_URL`：实际 HTTPS 站点地址，不能以斜杠结尾；Render 可使用 `RENDER_EXTERNAL_URL` 默认值。
- `ATMOS_RESEND_API_KEY`、`ATMOS_EMAIL_FROM`、`ATMOS_RESEND_TEMPLATE_ID`：Resend API Key、已验证发件地址和已发布的登录邮件模板 ID；邮箱回调为 `https://<实际站点域名>/api/auth/email/verify`。此前部署域名对应 `https://atmos-demo-9uuv.onrender.com/api/auth/email/verify`。需在发起验证的同一浏览器打开链接。缺少配置时返回错误，不能假装发送成功。`onboarding@resend.dev` 仅用于给 Resend 账户自己的邮箱做测试；面向其他用户需验证自有发件域名。

Render 免费 Web Service 无法对外连接 SMTP 常用端口，故使用 HTTPS 邮件 API；邮件供应商的实际免费额度与发件域验证需另行核实，当前不创建付费服务。

## 免费 PostgreSQL 限制

[Render 官方免费方案](https://render.com/docs/free)：每工作空间最多一个免费 PostgreSQL，1 GB，创建后 30 天到期，到期后不可访问，14 天宽限期后删除。它适合临时测试，不能称为长期免费持久存储。现有授权仅限免费资源，不创建或升级付费数据库、磁盘或邮件服务；使用前需要明确备份和到期处理。免费 Web Service 的用量和超额计费条件也应检查。

## 验收状态

2026-11-06 已在 My Workspace 创建 `atmos-demo-postgres`，Free、Singapore、PostgreSQL 18，创建后 30 天到期：北京时间 2026-12-06 10:16。现有 Web Service 尚未连接此数据库，账号更改尚未部署。真实 Resend 仅验证向注册邮箱发信；其他用户需要已验证发件域名。账号隔离、跨客户端读取和退出已在本机 PostgreSQL 兼容测试库验证，迁移和账号切换已用浏览器模拟接口验证；仍需实际 Render PostgreSQL 和多浏览器线上验收。原有公开托管仍不自动启用。
