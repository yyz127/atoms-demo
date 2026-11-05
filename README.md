# Atmos

一个可实际交互的对话式 HTML 应用构建平台。React 前端、无数据库 Python 代理；平台数据全部保存在浏览器 LocalStorage，无账号系统。

通过自己的 OpenAI、Anthropic、DeepSeek、通义千问、Kimi 或兼容接口生成单个 HTML，支持实时预览、代码查看、版本恢复、克隆、带数据/空模板导出、研究报告和页面打开期间的定时检查。

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

无需数据库、注册、服务端模型密钥或加密主密钥。可复制 .env.example 为 .env 调整部署地址、搜索服务与发布文件目录。

## 数据与导出

平台工作空间保存在 atmos.workspace.v1。刷新保留，换浏览器不自动同步，清除网站数据会删除本地记录。建议用设置中的备份功能导出工作空间。

生成应用在隔离 iframe 内运行，预览数据独立保存；HTML 导出可带预览数据或使用空模板，独立打开后仍用自己的 LocalStorage 保存后续记录。

模型凭证不进入应用 HTML、代码版本或公开发布文件。公开发布可选择附带预览数据，其他平台记录不上传。服务器只持久保存公开产物及其管理凭证哈希。

定时任务只在页面打开时执行；刷新或关闭中断请求，错过的任务重开只提示、不补跑。每次只检查与汇报，绝不自动改代码或发布。

## 部署到 Render

[一键部署免费平台](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Fyyz127%2Fatoms-demo)：登录 Render，连接本仓库，检查计划为 Free 后创建。无需填写服务端模型密钥；每位使用者在浏览器中配置自己的模型。

- render.yaml：用户已选用的免费平台方案，无磁盘、无数据库，暂不启用公开应用托管；生成、研究、版本、导出和页面内定时任务保留。
- render-persistent.yaml：未来可选的付费计算与 1 GB 磁盘方案，本次不使用。
- 两种方案均没有后端数据库。

Docker 多阶段构建会生成前端并启动 Python，默认端口使用 Render 的 PORT。生产域名自动使用 RENDER_EXTERNAL_URL，健康检查为 /api/health。

免费服务可能休眠并在下次访问时冷启动。部署步骤、连接和当前状态见 [部署说明](docs/deployment.md)。源码仓库为 https://github.com/yyz127/atoms-demo 。当前尚未取得 Render 连接，尚无已验证的在线地址。

## 验证

见 docs/acceptance.md。浏览器协议测试不等于真实模型验收，本地发布不等于互联网部署。

当前交付规范：docs/requirements.md、docs/delivery-plan.md。旧访谈仅作历史记录：docs/decision-history.md。
