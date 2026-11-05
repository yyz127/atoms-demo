---
status: accepted
---

# 自然语言生成的应用统一产出单个 HTML

平台自身是 React 与 Python 工程，用户生成的应用则统一为单个 HTML，内联 CSS 与 JavaScript，不生成应用账号或后端数据库。应用数据通过标准 LocalStorage API 保存；预览使用不允许同源访问的 iframe 与限定的存储消息桥，避免生成脚本读到平台模型凭证或其他项目数据。导出是可独立打开的一个 HTML，选择附带预览数据或空模板；不再导出 React/Python 工程 ZIP。
