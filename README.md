# Atoms

一个对话式 HTML 应用构建平台。最新需求为平台账号与 PostgreSQL 云工作空间；前后端已接入，并已部署至 Render；当前认证改为邮箱和密码，不发送验证邮件；部署状态以实际环境为准。

通过自己的 OpenAI、Anthropic、DeepSeek、通义千问、Kimi 或兼容接口生成单个 HTML，支持实时预览、代码查看、版本恢复、克隆、带数据/空模板导出和研究报告。

## 本地运行

需要 Python 3.12+、Node.js 22+ 和 uv。

```sh
uv sync --frozen
cd frontend
npm ci
npm run build
cd ..
uv run uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

打开 http://127.0.0.1:8000，在“设置与模型”配置自己的凭证。生成和研究会产生厂商模型调用，不提供假生成回退。开发时可在 frontend/ 执行 npm run dev，Vite 将 /api 转发到 Python 服务。

游客模式不依赖数据库或账号。云端功能需要 PostgreSQL、邮件服务和加密密钥；配置项和迁移步骤见 [部署说明](docs/deployment.md)。

## 深度研究

选择“深度研究”并输入主题后，先生成研究计划。可直接编辑计划，或继续在深度研究模式中输入修改要求；只有点击“开始研究”才会按最新计划检索和生成报告。计划、报告分别保存在工作台的 Markdown 文件中，可切换源码与安全预览、复制或下载。已有聊天内的历史报告仍可查看、导出和用于构建。停止或失败不会保存不完整报告；保留计划以便重试。

报告记录实际检索词、来源和正文读取状态；部分检索失败或仅有摘要会标明。模型生成的结论仍需根据来源核验。计划和报告随游客工作空间保存在浏览器，登录用户随账号工作空间同步，云端同步失败时请查看顶部提示。

OpenAI 兼容接口不再主动设置输出 token 上限；Anthropic 协议要求提供 max_tokens，当前请求值为 64000，具体上限仍由模型服务决定。模型返回长度截断时运行失败，不会把不完整内容标为完成。

## 数据与导出

游客工作空间保存在 atmos.workspace.v1。登录用户的平台记录按账号同步；迁移需预览确认，模型密钥和预览业务数据不自动迁移。

生成应用在隔离 iframe 内运行，预览数据独立保存；HTML 导出可带预览数据或使用空模板，独立打开后仍用自己的 LocalStorage 保存后续记录。

模型凭证不进入应用 HTML 或代码版本。可通过导出 HTML 分享；已有发布链接仍可访问，并可在项目菜单或删除对话时下线。云端模型密钥加密保存在服务端。

## 部署到 Render

[一键部署免费平台](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Fyyz127%2Fatoms-demo)：登录 Render，连接本仓库，检查计划为 Free 后创建。无需填写服务端模型密钥；每位使用者在浏览器中配置自己的模型。

- render.yaml：用户已选用的免费平台方案，无磁盘、无数据库，暂不启用公开应用托管；生成、研究、版本和导出保留。
- render-persistent.yaml：未来可选的付费计算与 1 GB 磁盘方案，本次不使用。
- 使用一套免费 PostgreSQL，已连接现有免费服务。

Docker 多阶段构建会生成前端并启动 Python，默认端口使用 Render 的 PORT。生产域名自动使用 RENDER_EXTERNAL_URL，健康检查为 /api/health。

免费服务可能休眠并在下次访问时冷启动。部署步骤、连接和当前状态见 [部署说明](docs/deployment.md)。源码仓库为 https://github.com/yyz127/atoms-demo 。

## 验证

见 docs/acceptance.md。浏览器协议测试不等于真实模型验收，本地发布不等于互联网部署。

当前交付规范：docs/requirements.md、docs/delivery-plan.md。旧访谈仅作历史记录：docs/decision-history.md。
