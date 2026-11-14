# docflow · 理赔影像件归档 RPA 与命名归一工作台

> 一句话：把共享盘/邮箱里命名乱七八糟的理赔影像件，扫一遍、认类型、按「保单号_材料类型_日期_序号」改名落盘，拿不准的单独排队等人工，最后导出一份 60 行的移交清单。

- 短名：`docflow` ｜ 端口：前端 `18253` / 后端 `19253` / 数据库 `17753`
- 技术栈：Vue 3 + TypeScript + Vite + Pinia ｜ FastAPI + SQLAlchemy 2.0 + Celery + Redis ｜ PostgreSQL 16
- 5 个服务：`frontend`(Nginx) / `backend`(FastAPI) / `worker`(Celery) / `db`(PostgreSQL 16) / `redis`(7)

---

## 1. 真实场景

**模拟客户**：恒安保险经纪 · 理赔受理组（14 人），日均处理 200+ 封邮件附件与共享盘投件。

**现有工作流**：受理员从共享盘（`\\fileserver\claims-drop`）和理赔邮箱下载附件（扫描件、手机拍照、PDF），
按「保单号_材料类型_日期」手工重命名，再逐单上传理赔系统录字段。一份工单的材料常混在一个文件夹里，
名字长这样：`IMG_2043.jpg`、`微信图片_20261030144022.jpg`、`扫描全能王 2026-10-29 14.02.pdf`。

**三个痛点**

1. 命名五花八门，回头找不到件（同一份诊断书可能叫 `IMG_2043.jpg` 也可能叫 `诊断书(1).jpg`）；
2. 身份证/发票/诊断书混放，靠肉眼分，新人根本分不清出院小结和诊断证明；
3. 重名覆盖，材料丢失无法追溯（同名 `新建文档.pdf` 覆盖后连原片都找不回）。

**上下游**：上游 = 3 个投件源（共享盘 / 理赔邮箱 / 移动盘补件，本地 fixture 目录 + 元数据表）；
本系统替代「手工重命名 + 肉眼分类 + 逐单录入」；下游 = 理赔系统的案件材料包与稽核抽查的移交清单。

**一天的工作剧本**

| 时间 | 动作 | 真实数据 |
|---|---|---|
| 08:40 | 共享盘批量投件，受理员点「试运行」 | 扫描 210 件，199 件可自动命名，7 件待确认，4 件未识别 |
| 09:05 | 正式归档 | 归档 190 件、重复 9 件不落盘，`archive_store` 落 190 个文件 |
| 09:40 | 复核待确认队列 | 把 `IMG_2043.jpg` 判为诊断书并补保单号 `P202600000003`，随即落盘 |
| 10:10 | 改命名规则 v2 | 主管把模板改成「保单号-类型-日期-序号」试算，看不到问题才启用 |
| 11:30 | 稽核抽查 | 稽核导出稽核清单 CSV，只读案件与批次，不能改件 |
| 17:50 | 收工移交 | 导出移交清单 CSV：60 行，含每案附件数与缺失材料提示 |

**角色权限**

| 角色 | 账号 | 主要页面 | 权限 | 典型动作 |
|---|---|---|---|---|
| `admin` 受理主管 | `admin@docflow.io` | 全部 | 规则版本、发起批次、改判、移交导出、审计日志 | 改命名模板、看审计、发批次 |
| `analyst` 受理员 | `analyst@docflow.io` | 工作台/详情/队列 | 发起批次、改判待确认件、移交导出 | 跑批次、补保单号、改判类型 |
| `auditor` 稽核 | `auditor@docflow.io` | 工作台/详情/队列/批次 | **只读** + 稽核清单导出 | 抽查材料、导出稽核清单；改件/发起批次/改规则会被 **403** 拦下 |

---

## 2. 功能（业务链路）

配置 → 运行/采集 → 解析/计算 → 复核/归因 → 导出，五个模块串成一条链路：

1. **配置**：命名规则按版本落库（模板 + 冲突策略 + 日期来源）；3 个投件源（共享盘/邮箱/移动盘）与计数。
2. **运行/采集**：发起归档批次（试运行 / 正式归档），批次记录扫描、新增、归档、重复、待确认、未识别、未变、人工计数与逐行日志。
3. **解析/计算**：算法 1 材料类型识别（四路特征加权），算法 2 命名归一与冲突消解（SHA-256 判重复、序号递增）。
4. **复核/归因**：待确认队列（低置信 7 件 / 未识别 4 件），逐件看候选分数与分类依据，人工改判并补保单号。
5. **导出**：移交清单 CSV（按案件 60 行）+ 稽核清单 CSV（审计日志），都写审计。

### 页面（5 个）

| 路由 | 页面 | 说明 |
|---|---|---|
| `/login` | 登录 | 借阅登记单；三个演示账号可一键回填 |
| `/cases` | 案件工作台 | 待收件/已归档/异常三个抽屉 + 材料分布 SVG + 异常抽屉 + 投件源 |
| `/cases/:id` | 案件详情 | 应收材料清单 + 附件逐件「原名 → 归档名」对照 + 分类依据四路特征条 |
| `/rules` | 命名规则与归档批次 | 模板编辑/预览/版本历史 + 发起批次 + 批次台账/日志 + 投件源 + 最近审计 |
| `/pending` | 待确认队列 | 低置信/未识别队列 + 人工改判 + 两个 CSV 导出 |

### 算法（后端 Python 真算，前端只展示回传值）

**算法 1：材料类型识别**（`backend/src/services/material_classifier.py`）

```
score(类型) = 0.45×文件名关键词 + 0.35×内容抽样关键词 + 0.15×正则校验 + 0.05×扩展名先验
```

- 文件名：强命中 1.0 / 弱命中 0.55；
- 内容：强命中 0.80 起、弱命中 0.55 起，带边际递减（上限 1.0）；
- 正则：发票代码 12 位、身份证 18 位 GB11643 校验位、银行卡 16–19 位、ICD-10 编码、住院天数；
- 扩展名：pdf/jpg/tif 对不同材料有不同先验；
- 判定：除扩展名外三路全零 → `unknown`（不自动归档）；最高分 < **0.60** → `pending`；否则 `classified`。

**算法 2：命名归一与冲突消解**（`backend/src/services/naming_engine.py`）

- 模板：`{保单号}_{材料类型}_{YYYYMMDD}_{序号:02d}`，扩展名自动保留；
- 保单号优先级：文件名 > 内容抽样 > 案件绑定；抽不到 → 保留原名进待确认；
- 冲突：目标名空 → 落盘；目标名已存在且内容 **SHA-256 相同** → `duplicate`（不落盘）；不同 → 序号递增至空位；序号耗尽 → 待确认；
- 落盘写进命名卷 `archive_store`（demo 用内容抽样代替二进制原件），重复件不写文件。

**seed 契约**：`SEED_SUMMARY brand=docflow cases=60 attachments=210 duplicates=9 pending=7 rules=1 users=3`
其中 `duplicates` = 同案件同 SHA-256 的多余份数、`pending` = seed 阶段低置信件数，二者都不随批次执行变化，因此归档后再跑 seed 仍是同一行。

---

## 3. 快速启动

```bash
cd projects/gb-580
cp .env.example .env          # 已自带 .env 时可直接用
docker compose config --quiet
docker compose up -d --build  # 首次构建约 2-4 分钟（前端走 npmmirror）
# 等 5/5 healthy
docker compose ps
```

启动后 backend 的 `SEED_DEMO=true` 会自动跑一次幂等 seed（失败只记日志不阻塞）。

| 地址 | 用途 |
|---|---|
| http://localhost:18253 | 前端（Nginx，`/api/` 反代 backend:8000） |
| http://localhost:19253/api/health | 后端健康检查（含 archive_store 文件数） |
| http://localhost:19253/docs | FastAPI 文档 |
| localhost:17753 | PostgreSQL（docflow/docflow） |

手动重跑 seed（幂等）：

```bash
docker compose exec backend python -m scripts.seed_demo
```

### 演示账号（口令统一 `Demo@2026`）

| 邮箱 | 角色 | 能做什么 |
|---|---|---|
| `admin@docflow.io` | 受理主管 admin | 改命名规则版本、发起批次、改判、导出、看审计 |
| `analyst@docflow.io` | 受理员 analyst | 发起批次、改判待确认件、导出移交清单 |
| `auditor@docflow.io` | 稽核 auditor | 只读 + 导出稽核清单；改件/发起批次/改规则 → 403 |

### 本地开发

```bash
# 只起依赖
docker compose up -d db redis
# 后端
cd backend && pip install -r requirements.txt && uvicorn src.main:app --reload --port 19253
# worker（可选）
PYTHONPATH=.:.. celery -A worker_src.config.celery_app worker -B -l info
# 前端
cd frontend && npm install && npm run dev   # http://localhost:18253，/api 代理到 19253
```

---

## 4. 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 前端 | Vue 3.4 + TypeScript + Vite 5 + Pinia + vue-router | 组合式 API，无 UI 框架，SVG 自绘图表 |
| 后端 | Python 3.11 + FastAPI 0.115 + SQLAlchemy 2.0 + Pydantic v2 | JWT（PyJWT）+ passlib(bcrypt) |
| 异步 | Celery 5.4 + Redis 7 | `docflow.archive_run` / heartbeat / drop_sweep |
| 数据库 | PostgreSQL 16（schema `docflow`） | 6 张表：users / claim_cases / attachments / naming_rules / archive_runs / audit_logs |
| 前端托管 | Nginx 1.27 | `location /api/ → backend:8000/` + SPA 回落 |
| 字体 | Noto Serif SC + Courier Prime | 离线时回退系统衬线/等宽字体（见 TESTING.md） |

---

## 5. 目录

```
gb-580/
├── docker-compose.yml          # 5 服务 / 命名卷 / 全部 healthcheck
├── .env / .env.example
├── db/init/00-init.sql         # 建 schema
├── backend/
│   ├── Dockerfile  entrypoint.sh  requirements.txt  alembic.ini
│   ├── migrations/             # 0001_initial + env.py
│   ├── scripts/
│   │   ├── bootstrap_db.py     # 幂等 create_all
│   │   ├── fixtures.py         # 确定性演示数据（60 案 / 210 件）
│   │   └── seed_demo.py        # 幂等 seed + SEED_SUMMARY
│   └── src/
│       ├── config/             # settings / database / celery_app / app
│       ├── constants/          # enums / roles / error_codes / limits / log_templates
│       ├── models/             # 4 实体 + user + audit_log
│       ├── schemas/            # auth / case / attachment / rule / run
│       ├── services/           # material_classifier / naming_engine / archive / case / run / rule / pending / export / audit / auth
│       ├── controllers/        # 薄控制器
│       ├── routes/             # /api/* 与根路径各挂一次
│       ├── middlewares/        # auth / rbac / rate_limit / login_guard / audit_logger / error_handler
│       └── utils/              # jwt / password / textutils / redis_client / errors / logger
├── worker/
│   ├── Dockerfile  healthcheck.sh
│   └── src/{config,core,tasks} # archive_task / heartbeat_task / sweep_task
└── frontend/
    ├── Dockerfile  nginx.conf  package.json  vite.config.ts  tsconfig.json
    └── src/
        ├── api/                # auth/cases/attachments/rules/runs/pending/exports/audit/health
        ├── stores/             # auth / cases / rules / runs / pending
        ├── types/              # user / domain / api / ui
        ├── constants/          # enums / roles / messages / nav
        ├── components/common/  # AppShell / FolderTabs / StatusStamp / ConfidenceMeter / RenameCompare / MaterialTag / DistributionBar / EmptyState / ErrorNotice / PageHeader / SealMark / ConfirmAttachmentDialog
        ├── hooks/              # useAsync / usePagination / useRunPoll
        ├── pages/              # 5 个页面
        ├── router/  styles/  utils/
```

## 6. 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `COMPOSE_PROJECT_NAME` | `docflow` | 容器名前缀 |
| `FRONTEND_PORT` | `18253` | 前端映射端口 |
| `BACKEND_PORT` | `19253` | 后端映射端口 |
| `DB_PORT` | `17753` | PostgreSQL 映射端口 |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | `docflow` / `docflow` / `docflow_pw_2026` | 库与账号 |
| `JWT_SECRET` | `docflow-jwt-secret-2026-hangan` | JWT 签名密钥（生产必须替换） |
| `REDIS_URL` | `redis://redis:6379/0` | Celery broker/backend |
| `SEED_DEMO` | `true` | 启动时跑一次幂等 seed |
| `NPM_REGISTRY` | `https://registry.npmmirror.com` | 前端构建 registry |
| `RATE_LIMIT_RUN_PER_MINUTE` | `8` | 每用户每分钟可发起批次数 |
| `RATE_LIMIT_CONFIRM_PER_MINUTE` | `40` | 每分钟改判次数 |
| `LOGIN_ATTEMPT_PER_MINUTE` | `12` | 单 IP 每分钟登录尝试 |

## 7. Docker 说明

- 恰好 5 个服务，全部有 healthcheck：db(`pg_isready`) / redis(`redis-cli ping`) / backend(`GET /api/health`) / worker(Redis 心跳 + celery ping 兜底) / frontend(`wget /`)。
- 依赖全部 `service_healthy`（worker 依赖 db/redis healthy + backend started）。
- 3 个命名卷：`db_data`、`redis_data`、`archive_store`（backend/worker 共享归档产物）。
- 构建期走清华 pip 源与 npmmirror；基础镜像只用本机已有 tag（python:3.11-slim / node:20-alpine / nginx:1.27-alpine / postgres:16-alpine / redis:7-alpine）。
- `backend` 的 entrypoint 先 `bootstrap_db`（建 schema + create_all）再起 uvicorn；`worker` 复用 backend 源码（同一套模型与算法）。

## 8. 枚举出现位置（前后端各一份）

**前端** `frontend/src/constants/enums.ts`：`MATERIAL_TYPES` / `MATERIAL_LABELS` / `MATERIAL_SHORT`、`CASE_STATUSES` / `CASE_STATUS_LABELS`、`ATTACHMENT_STATUSES` / `ATTACHMENT_STATUS_LABELS`、`RUN_STATUSES` / `RUN_STATUS_LABELS`、`RUN_MODES` / `RUN_MODE_LABELS`、`INSURANCE_TYPES` / `INSURANCE_LABELS`、`SOURCE_LABELS` / `SOURCE_SHORT`、`FEATURE_WEIGHTS`、`TEMPLATE_TOKENS`。
引用点：`types/domain.ts`、`components/common/{StatusStamp,MaterialTag,DistributionBar,ConfirmAttachmentDialog}.vue`、`pages/{CaseWorkbenchPage,CaseDetailPage,PendingQueuePage,RulesRunsPage}.vue`、`stores/*`、`api/*`。

**后端** `backend/src/constants/enums.py`：`MaterialType`、`CaseStatus`、`AttachmentStatus`、`RunStatus`、`RunMode`、`InsuranceType`、`IngestSource` + 各 `*_LABELS` + `EXPECTED_MATERIALS` + `FEATURE_WEIGHTS`。
引用点：`services/material_classifier.py`、`services/naming_engine.py`、`services/archive_service.py`、`services/case_service.py`、`services/pending_service.py`、`services/export_service.py`、`services/run_service.py`、`models/*`、`schemas/*`、`scripts/seed_demo.py`、`scripts/fixtures.py`。

**角色枚举**：前端 `frontend/src/constants/roles.ts` ↔ 后端 `backend/src/constants/roles.py`（`admin` / `analyst` / `auditor` + 权限矩阵）。

## 9. 横切关注点

1. **认证授权**：JWT（`middlewares/auth.py`）+ 角色能力矩阵（`middlewares/rbac.py`，`require_permission`），低权角色调高权接口真实返回 403。
2. **审计日志**：`services/audit_service.py` 写入 `audit_logs`（登录、发起批次、批次执行/失败、人工改判、规则版本、导出、审计读取），`middlewares/audit_logger.py` 提供 trace_id 与访问日志。
3. **限流/防爆破**：`middlewares/rate_limit.py`（run/confirm/default 三桶）+ `middlewares/login_guard.py`（单 IP 登录窗口）+ `middlewares/error_handler.py` 统一错误体。

## 10. License

MIT（演示项目，数据均为虚构；`Demo@2026` 仅用于本地演示）。
