# MedRisk · 专科疾病智能风险分级系统

面向专科医生的疾病风险分级与可解释报告助手。医生录入结构化指标，确定性规则引擎给出严重程度、手术/恶性风险与预后建议；评估报告必须由医生复核签核后方视为生效。

> 本项目是演示原型，只使用虚构数据，不连接真实医院系统，不替代医生决策。所有概率均为 **“演示模型，未经校准”**。

## 当前可运行范围

手工评估闭环已经可以端到端运行：

- 医生 / 管理员登录，JWT 存放在 httpOnly Cookie。
- 患者列表、筛选、分页、CSV 导出与患者详情。
- 八个专科病种的结构化评估录入，字段约束来自规则注册表。
- 确定性规则输出严重程度、风险概率、预后参考、红旗预警、处置建议与引用。
- 医生逐项复核并显式签核；创建与签核均写入审计日志。
- 工作台、风险构成、患者风险趋势、数据分析与病种质量概览。
- 模型与规则版本页，以及管理员系统设置页。
- 评估报告内嵌 AI 解读抽屉：LangGraph Agent 流式展示工具调用与节点进度，生成带规则引用的草稿，经医生批准/拒绝后留痕。
- 模型层可在离线 Mock 与 DeepSeek（OpenAI 兼容 JSON 模式）之间切换；外发前完成脱敏与数值/引用校验。

默认 `LLM_MOCK=1`，Agent 使用离线脚本模型，不会向外部模型供应商发送数据。设置 `LLM_MOCK=0` 并配置 `LLM_API_KEY` 后，草稿由 DeepSeek 生成，但仍需通过同一套结构、数值与引用校验，并进入医生复核。指南 RAG、Redis 限流与 Docker Compose 仍待接入。

## 快速启动

### 1. 后端

```powershell
uv sync --project backend --dev
uv run --project backend uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

- 当前 `backend/.env` 指向本机 PostgreSQL 16：`postgresql+asyncpg://medrisk:medrisk@127.0.0.1:5432/medrisk`，首次启动自动建表并写入演示数据。
- PostgreSQL 以 Windows 服务 `postgresql-x64-16` 运行，端口 `5432`，数据目录 `C:\Program Files\PostgreSQL\16\data`。
- 新机器初始化角色与数据库（需 postgres 超级用户密码；`psql` 未加入 PATH，使用完整路径）：

  ```powershell
  & 'C:\Program Files\PostgreSQL\16\bin\psql.exe' -U postgres -f backend/scripts/init_postgres.sql
  ```

- 不配置 `DATABASE_URL` 时回退到 SQLite：`backend/medrisk_dev.db`，适合零依赖演示。
- 健康检查：<http://127.0.0.1:8000/health>；OpenAPI 文档：<http://127.0.0.1:8000/docs>。
- 可复制 `backend/.env.example` 为 `backend/.env` 调整配置。
- Alembic 迁移尚未接入，当前由 `AUTO_CREATE_TABLES` 建表；pgvector 尚未安装（RAG 阶段再启用）。

### 2. 前端

```powershell
npm install --prefix frontend
npm run dev --prefix frontend
```

打开 <http://127.0.0.1:5173>。Vite 已将 `/api` 与 `/health` 代理到 `http://127.0.0.1:8000`。

### 3. 演示账号

| 角色 | 账号 | 密码 | 说明 |
| --- | --- | --- | --- |
| 医生 | `doctor` | `MedRisk2026!` | 可创建评估、签核报告 |
| 管理员 | `admin` | `Admin2026!` | 只读系统信息；越权签核返回 403 |

### 4. 接入 DeepSeek（可选）

在 `backend/.env` 中设置：

```dotenv
LLM_MOCK=0
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=<在服务端填写，不要提交到仓库>
LLM_MODEL=deepseek-flash
LLM_MAX_OUTPUT_TOKENS=2048
LLM_THINKING=0
LLM_TRACING=0
```

重启后端后，创建 AI 运行会调用 `POST {LLM_BASE_URL}/chat/completions`（`response_format=json_object`）。约束：

- 只有脱敏后的假名、规则结果、证据白名单会外发；姓名、病历号、电话不会离开服务端。
- API key 仅从环境变量读取，不写日志、不返回前端；缺失时创建运行返回 422。
- 默认关闭 thinking 与第三方追踪；供应商须承诺不用于训练，或改用私有化部署端点。
- 模型与提示词版本（`prompts-2026.11.2`）随每次运行记录；升级前先跑回归集。

## 验证状态

2026-11-06 已完成以下验证：

- `npm run typecheck --prefix frontend` 通过。
- `npm run build --prefix frontend` 通过（Vite 生产构建）。
- 浏览器实测：登录 → 工作台 → 患者列表 → 新建评估 → 生成报告 → 医生签核 → 审计记录更新。
- 浏览器实测 Agent 全流程：报告页打开 AI 解读 → 生成草稿 → 流式节点/工具时间线 → 医生复核批准 → 审计与运行记录更新；SSE 经 Vite 代理正常工作。
- 后端 `pytest backend/tests`：26 项通过，覆盖脱敏、提示词注入包裹、数值/引用校验、重写上限、审批/拒绝、编辑稿复检、医生/管理员权限，以及 DeepSeek 适配器的请求格式、JSON 解析、重试边界与密钥缺失。
- PostgreSQL 16 实测：自动建表与种子数据（18 名患者、20 份评估）写入成功；登录、患者列表、模型页正常；DeepSeek Agent 运行与医生批准落库，`agent_runs` / `agent_steps` 中不含患者姓名与病历号。
- 分析、模型与规则、患者详情、管理员设置页面均可正常加载。
- 管理员调用医生签核接口返回 403。
- 390px 手机宽度下无页面级横向溢出，侧边栏可抽屉打开。
- 浏览器控制台无运行时错误。

界面截图见 [`docs/screenshots/`](docs/screenshots/)：

- [登录页](docs/screenshots/01-login.png)
- [临床工作台](docs/screenshots/02-dashboard.png)
- [患者管理](docs/screenshots/03-patients.png)
- [评估报告](docs/screenshots/04-report.png)
- [移动端工作台](docs/screenshots/05-dashboard-phone.png)
- [数据分析](docs/screenshots/08-analytics.png)
- [模型与规则](docs/screenshots/09-models.png)
- [AI 解读 · 等待医生复核](docs/screenshots/12-agent-waiting.png)
- [AI 解读 · 医生批准](docs/screenshots/13-agent-approved.png)

## 设计文档

- [系统架构](docs/architecture.md)：容器/组件图、手工评估流程、Agent 人在环流程、部署拓扑、安全边界
- [数据模型](docs/data-model.md)：ER 图、表约束、索引、状态迁移、JSONB 契约、审计与保留策略
- [目录树](docs/tree.md)：后端、前端、部署与文档的完整规划

## 技术基线

| 层 | 选型 |
| --- | --- |
| 后端 | Python 3.12、FastAPI、SQLAlchemy 2.0 async、Pydantic v2、Argon2 |
| 本地数据 | PostgreSQL 16（本机 Windows 服务）；SQLite 作为零依赖回退 |
| 规则 | 八个病种的纯 Python 确定性规则，输出版本化结果 |
| 前端 | React 19、TypeScript strict、Vite 6、Ant Design 5、TanStack Query 5、ECharts 5 |
| Agent | LangGraph 1.2（SQLite checkpoint）、tools → services、数值/引用校验器、SSE、DeepSeek（OpenAI 兼容 JSON 模式） |
| 规划中的生产依赖 | pgvector、Alembic 迁移、Redis、langgraph-checkpoint-postgres、DeepSeek 生产配额与合规确认 |

## 五条不可破坏的边界

1. `rules/` 是纯函数：不访问数据库、网络或全局可变状态，可独立单测。
2. Agent 节点不接触业务写操作；所有读写经 `tools → services`。
3. 任何写入（草稿、提交评估、确认签字）必须由医生在界面确认。
4. 路由层只做解析、鉴权与响应映射，业务逻辑在 `services/`。
5. 发给外部模型前必须脱敏；病历文本按不可信数据包裹，日志与步骤记录落库前同样脱敏。

## 已知限制

- 业务数据已落在 PostgreSQL 16；pgvector 向量检索与 Alembic 迁移尚未接入，当前由 `AUTO_CREATE_TABLES` 建表，Agent checkpoint 仍在 SQLite。
- 后端已有 Agent 校验、脱敏、人审与权限集成测试（`uv run --project backend pytest backend/tests`）；前端尚无自动化测试，依赖类型检查、生产构建与浏览器实测。
- Agent 默认仍运行 Mock 模型；DeepSeek 适配器已实现但需配置密钥后启用，尚未完成针对真实模型的语义回归集。
- Redis 限流、CSRF / Origin 加固、用户管理写操作尚未实现。
- 禁止录入真实患者信息；所有风险百分比仅用于产品演示。
