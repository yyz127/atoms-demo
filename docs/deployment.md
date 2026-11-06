# 账号与云端工作空间部署（实现中）

2026-11-06 的需求覆盖旧的“平台无账号、全部本地保存”决策。账号接口、前端云同步、迁移入口和模型密钥加密代码已实现并部署；Render 服务通过内网连接免费 PostgreSQL，公开应用托管保持关闭。

## 目标架构与迁移

浏览器 → FastAPI 认证/数据接口 → 一套 PostgreSQL。账号使用邮箱与密码注册、登录，不发送邮件，也不验证邮箱归属；密码使用随机盐的 PBKDF2-SHA256 哈希保存，不保存明文。会话使用随机令牌、HttpOnly cookie，数据库存令牌哈希。旧邮箱验证账号必须在仍已登录的浏览器设置密码，不能仅凭邮箱接管；无有效会话时目前没有自助找回。模型 Key 使用 Fernet 加密，工作空间按 user_id 隔离并检测并发修改。游客工作空间与生成应用业务数据保持本地，旧数据迁移须预览确认。

运行 `uv run python -m backend.migrate` 创建初始表及索引。此命令必须在配置数据库之后运行。Render Free 不提供预部署命令或远程 Shell；Docker 启动入口在配置数据库时会自动执行幂等迁移，失败则停止启动并提示，不依赖外部连接。当前初始 SQL 已在本机 PGlite PostgreSQL 兼容库验收，尚未在 Render PostgreSQL 验收。定时任务功能已移除。

## 配置项

仅在实际部署环境提供，不提交真实值：

- `ATMOS_DATABASE_URL`：PostgreSQL 连接字符串，或使用 `DATABASE_URL`。
- `ATMOS_ENCRYPTION_KEY`：持久保存的 Fernet 密钥，可用 `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'` 生成；丢失或替换会导致原模型 Key 无法解密。
- `ATMOS_PUBLIC_URL`：实际 HTTPS 站点地址，不能以斜杠结尾；Render 可使用 `RENDER_EXTERNAL_URL` 默认值。


## 免费 PostgreSQL 限制

[Render 官方免费方案](https://render.com/docs/free)：每工作空间最多一个免费 PostgreSQL，1 GB，创建后 30 天到期，到期后不可访问，14 天宽限期后删除。它适合临时测试，不能称为长期免费持久存储。现有授权仅限免费资源，不创建或升级付费数据库、磁盘或邮件服务；使用前需要明确备份和到期处理。免费 Web Service 的用量和超额计费条件也应检查。

## 验收状态

2026-11-06 已在 My Workspace 创建 `atmos-demo-postgres`，Free、Singapore、PostgreSQL 18，创建后 30 天到期：北京时间 2026-12-06 10:16。账号代码部署 551b2bc，状态 live；Web Service 已通过内部地址连接数据库，健康检查报告 database=true。线上使用两个隔离浏览器完成真实邮箱验证、同账号记录读取、退出与临时模型配置检查；实际迁移排除游客密钥及预览业务数据，临时验收记录已清理。真实 Resend 仅验证向注册邮箱发信；其他用户需要已验证发件域名。不同账号隔离和密文存储在本机 PostgreSQL 兼容测试库验证，未在 Render 数据库直接读取密文。原有公开托管仍不自动启用。

当前代码已改为邮箱密码方案；历史线上测试使用的邮件登录描述仅供参考，部署新版本后不再发送登录邮件。部署后请在仍有效的旧登录会话中设置密码；没有有效会话的旧账号需要由管理员安全地另行恢复，不能自动认领。
