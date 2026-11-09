# 目录树

第 1 步已创建目录骨架；标注为“规划”的文件在后续步骤落地。

```text
group_project/
├─ README.md
├─ .gitignore
├─ .editorconfig
├─ docker-compose.yml                  # 第 9 步；根目录满足一键启动
├─ docs/
│  ├─ architecture.md
│  ├─ data-model.md
│  ├─ tree.md
│  └─ demo-script.md                   # 第 9 步
├─ backend/
│  ├─ pyproject.toml                   # 第 2 步
│  ├─ uv.lock                          # 第 2 步
│  ├─ alembic.ini                      # 第 2 步
│  ├─ Dockerfile                       # 第 9 步
│  ├─ alembic/
│  │  ├─ env.py                        # 第 2 步
│  │  ├─ script.py.mako
│  │  └─ versions/                     # 第 2 步初始迁移
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ main.py                       # 第 2 步
│  │  ├─ core/
│  │  │  ├─ config.py                  # pydantic-settings
│  │  │  ├─ security.py                # JWT + Argon2
│  │  │  ├─ logging.py                 # structlog JSON + 脱敏
│  │  │  └─ exceptions.py              # 统一错误 envelope
│  │  ├─ api/
│  │  │  └─ v1/
│  │  │     ├─ router.py
│  │  │     ├─ auth.py                 # 第 2/4 步
│  │  │     ├─ patients.py             # 第 4 步
│  │  │     ├─ assessments.py          # 第 4 步
│  │  │     ├─ dashboard.py            # 第 4 步
│  │  │     ├─ analytics.py            # 第 4 步
│  │  │     ├─ models.py               # 第 4/8 步
│  │  │     ├─ agent.py                # 第 5/6 步
│  │  │     ├─ registry.py             # 第 3/4 步
│  │  │     └─ audit.py                # 第 4 步
│  │  ├─ models/
│  │  │  ├─ base.py                    # UUID、时间戳 mixin
│  │  │  ├─ user.py
│  │  │  ├─ patient.py
│  │  │  ├─ assessment.py
│  │  │  ├─ audit.py
│  │  │  ├─ agent.py
│  │  │  ├─ guideline.py
│  │  │  └─ rule_version.py
│  │  ├─ schemas/
│  │  │  ├─ common.py                  # Page、ErrorEnvelope
│  │  │  ├─ auth.py
│  │  │  ├─ patient.py
│  │  │  ├─ assessment.py
│  │  │  ├─ dashboard.py
│  │  │  ├─ analytics.py
│  │  │  └─ agent.py
│  │  ├─ services/
│  │  │  ├─ auth_service.py
│  │  │  ├─ patient_service.py
│  │  │  ├─ assessment_service.py
│  │  │  ├─ dashboard_service.py
│  │  │  ├─ analytics_service.py
│  │  │  ├─ audit_service.py
│  │  │  ├─ agent_service.py           # run 生命周期、审批、反馈
│  │  │  ├─ guideline_service.py       # pgvector 检索
│  │  │  ├─ deid_service.py            # 内存映射、脱敏
│  │  │  └─ ehr_adapter.py             # 演示用合成 EHR 只读适配器
│  │  ├─ rules/
│  │  │  ├─ base.py                    # 结果模型与注册协议
│  │  │  ├─ constants.py               # 阈值、来源、版本
│  │  │  ├─ ortho.py                   # 髋部骨折、膝骨关节炎
│  │  │  ├─ thoracic.py                # 肺结节、肺癌术前
│  │  │  ├─ hpb.py                     # HCC、急性胆囊炎
│  │  │  ├─ urology.py                 # 前列腺癌、上尿路结石
│  │  │  └─ registry.py
│  │  ├─ agent/
│  │  │  ├─ state.py
│  │  │  ├─ graph.py
│  │  │  ├─ tools.py
│  │  │  ├─ validators.py
│  │  │  ├─ runner.py                  # 事件桥、checkpoint、重试/预算
│  │  │  ├─ llm.py                     # 真实模型 / FakeChatModel
│  │  │  └─ prompts/
│  │  │     ├─ system.yaml
│  │  │     ├─ extract.yaml
│  │  │     ├─ draft.yaml
│  │  │     └─ verify.yaml
│  │  └─ db/
│  │     ├─ session.py
│  │     ├─ seed.py
│  │     └─ seed_data/                 # 合成患者、指南语料
│  ├─ tests/
│  │  ├─ conftest.py
│  │  ├─ rules/
│  │  │  ├─ test_hip_fracture.py
│  │  │  ├─ test_knee_oa.py
│  │  │  ├─ test_pulmonary_nodule.py
│  │  │  ├─ test_lung_cancer.py
│  │  │  ├─ test_hcc.py
│  │  │  ├─ test_cholecystitis.py
│  │  │  ├─ test_prostate.py
│  │  │  └─ test_stone.py
│  │  ├─ api/
│  │  │  ├─ test_auth.py
│  │  │  ├─ test_patients.py
│  │  │  ├─ test_assessments.py
│  │  │  └─ test_dashboard.py
│  │  └─ agent/
│  │     ├─ test_validators.py
│  │     ├─ test_tools.py
│  │     └─ test_graph_mock.py
│  └─ scripts/
│     ├─ run_migrations.py
│     └─ seed.py
├─ frontend/
│  ├─ package.json                     # 第 2/6 步
│  ├─ tsconfig.json
│  ├─ vite.config.ts
│  ├─ index.html
│  ├─ Dockerfile                       # 第 9 步
│  ├─ public/
│  ├─ e2e/
│  │  └─ main-flow.spec.ts             # Playwright
│  └─ src/
│     ├─ main.tsx
│     ├─ App.tsx
│     ├─ router.tsx
│     ├─ api/
│     │  ├─ client.ts
│     │  ├─ auth.ts
│     │  ├─ patients.ts
│     │  ├─ assessments.ts
│     │  ├─ dashboard.ts
│     │  └─ agent.ts
│     ├─ components/
│     │  ├─ RiskBadge.tsx
│     │  ├─ SeverityScale.tsx
│     │  ├─ PatientBanner.tsx
│     │  ├─ AssistantDrawer.tsx
│     │  ├─ ToolCallCard.tsx
│     │  ├─ CitationTag.tsx
│     │  ├─ DraftDiff.tsx
│     │  └─ EmptyState.tsx
│     ├─ features/
│     │  ├─ patients/
│     │  ├─ assessments/
│     │  ├─ agent/
│     │  └─ dashboard/
│     ├─ layouts/
│     │  └─ AppLayout.tsx
│     ├─ pages/
│     │  ├─ LoginPage.tsx
│     │  ├─ DashboardPage.tsx
│     │  ├─ PatientListPage.tsx
│     │  ├─ PatientDetailPage.tsx
│     │  ├─ AssessmentWizardPage.tsx
│     │  ├─ AssessmentReportPage.tsx
│     │  ├─ AnalyticsPage.tsx
│     │  ├─ ModelsPage.tsx
│     │  └─ SettingsPage.tsx
│     ├─ stores/
│     │  └─ authStore.ts
│     ├─ styles/
│     │  └─ global.css
│     └─ types/
│        └─ domain.ts
└─ deploy/
   ├─ nginx.conf                       # 第 9 步
   ├─ postgres/init.sql                # CREATE EXTENSION vector
   └─ README.md
```

## 目录约束

- `backend/app/rules/` 下所有文件不得 import `db`、`services`、`agent`、`httpx`、`sqlalchemy`。
- `backend/app/agent/tools.py` 不出现 `Session`、`select(`、原生 SQL；只接收已构造的 service 依赖。
- `frontend/src/api/` 是唯一发起 HTTP 的地方；页面不直接用 axios。
- `frontend/src/types/domain.ts` 与后端 Pydantic schema 对应，第 6 步前由手工维护并加契约测试。
