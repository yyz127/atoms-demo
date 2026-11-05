# Render 免费部署

状态：用户已选择免费方案。源码、Dockerfile 和默认 Blueprint 已准备，本地验收通过。Render 尚未安装连接，尚未创建线上服务，没有已验证的在线链接。

## 本次配置

根目录 render.yaml 创建一个 Free Docker Web Service，区域 Singapore，健康检查 /api/health。无数据库、无磁盘、无 Worker、无付费实例。

ATMOS_PRODUCTION=true，ATMOS_PUBLISH_DURABLE=false。模型转发、研究、版本、预览、HTML 导出、文件夹及页面内定时任务保留；公开应用托管暂不启用。浏览器 LocalStorage 保存平台工作空间，服务器不保存密钥或聊天。

免费服务闲置 15 分钟后休眠，再访问约需一分钟启动。每工作空间每月 750 免费实例小时，流量和构建另有额度；若绑定支付方式，超额可能收费。当前不配置任何付费资源。见 [官方免费方案](https://render.com/docs/free)。

## 部署步骤

快捷入口：[部署本仓库](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Fyyz127%2Fatoms-demo)。登录后连接 GitHub，授权 yyz127/atoms-demo，使用默认 main 分支及根目录 render.yaml。确认创建页面只包含 Free Web Service、没有数据库和磁盘，再点击 Deploy。

1. 安装并连接 Render，取得实际部署入口。当前未连接，不把配置准备完毕视为上线。
2. 源码仓库使用用户指定的 https://github.com/yyz127/atoms-demo ，分支 main。Render 连接 GitHub 时仅授权此仓库即可。
3. 创建 Blueprint，使用根目录 render.yaml。检查计划为 Free、没有磁盘或数据库再创建。
4. 等待 Docker 构建和服务启动，检查日志及 /api/health。Render 自动提供 PORT 和 RENDER_EXTERNAL_URL，无需复制本地 .env。
5. 打开生成的正式域名，执行下面的线上验收，并记录确切 URL。

也可手动创建 Docker Web Service：选择目标仓库、Dockerfile 路径 ./Dockerfile、Free 计划，设置上述两个环境变量及健康检查路径。自定义域名时显式设置 ATMOS_PUBLIC_URL。

## 线上验收

- /api/health 返回 ok=true、database=false、publishing_enabled=false。
- 页面、静态资源与刷新路由正常，发布按钮禁用；服务端也拒绝发布请求。
- 配置用户自己的模型，真实生成单个 HTML；验证预览、迭代、计划确认及版本恢复。
- 两种 HTML 导出可独立打开，刷新保留各自 LocalStorage 数据。
- 研究取得公开资料、标记来源与读取状态，生成可导出的报告。
- 定时任务只在页面打开期间执行，关闭期间错过只提示。
- 冷启动后可继续操作，本地对话和数据保留。

本机没有 Docker，镜像尚未实际构建；Render 的真实构建与上述网络验收仍待连接后执行。DeepSeek Flash 已通过本地真实连接、计划、生成、迭代和研究验证，其他厂商仍未实测。

## 后续公开托管

render-persistent.yaml 是未来可选方案，本次不使用。它需要付费计算与持久磁盘，只保存显式公开的 HTML、可选数据种子与管理凭证哈希。用户本次选择暂缓此项，不再次请求付费确认。

## 与 Zeabur 的比较

2026-11-05 查询官方资料：Render 明确提供免费 Python Web Service；Zeabur 当前 Free 价格页主要列出管理一台自有服务器，其公告已停止新建共享集群项目，并将原免费集群转为付费。Zeabur 的免费计划文档仍提到休眠服务，与部署入口变化需结合阅读，不能据此承诺提供免费运行服务器。本项目暂保留 Render 配置。

来源：[Render Free](https://render.com/docs/free)、[Blueprint](https://render.com/docs/blueprint-spec)、[环境变量](https://render.com/docs/environment-variables)、[Zeabur 价格](https://zeabur.com/pricing)、[共享集群调整](https://zeabur.com/changelogs/phasing-out-shared-cluster)、[Zeabur Free](https://zeabur.com/docs/en-US/pricing/free-plan)。
