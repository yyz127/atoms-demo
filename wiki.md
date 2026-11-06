# 产品文档

- [当前需求](docs/requirements.md)：用户最新确认的 LocalStorage、单 HTML 和 Render 交付范围。
- [最终方案与实现状态](docs/delivery-plan.md)：平台、导出、隔离、研究、定时与发布的实际行为。
- [验证记录](docs/acceptance.md)：本地通过项、真实服务依赖与线上待验收项。
- [部署说明](docs/deployment.md)：Render 资源、配置、费用与访问条件。
- [领域术语](CONTEXT.md)、[架构决策](docs/adr/)、[历史访谈](docs/decision-history.md)。

当前状态：2026-11-06 需求要求平台账号与 PostgreSQL 云工作空间，覆盖此前仅本地的决定。前后端已接入，临时兼容数据库与模拟浏览器测试已完成；Render 数据库连接和端到端验收尚未完成。现有免费 Render Web Service 已部署，当前变更未部署；暂不启用公开应用托管。源码仓库为 https://github.com/yyz127/atoms-demo 。
