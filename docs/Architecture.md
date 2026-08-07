# Architecture — English Coach

## 1. 系统架构

```
┌─────────────────────────────────────────────────────┐
│                Vue 3 Frontend (frontend-vue)         │
│   (Vue 3 + Naive UI + Pinia + ECharts + Vite)        │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP（JWT Bearer）
┌──────────────────────▼──────────────────────────────┐
│                   FastAPI Backend                     │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐  │
│  │  api/     │  │ services/ │  │      ai/         │  │
│  │ (routers) │→ │(business) │→ │ (provider abstraction)│
│  │+deps(JWT) │  └─────┬─────┘  └──────────────────┘  │
│  └──────────┘        │ │                             │
│                      │ └→ tts_service（edge-tts）     │
│                ┌─────▼─────┐                          │
│                │repositories/│                         │
│                │ (data access)│                        │
│                └─────┬─────┘                          │
│                      │                                │
│  ┌──────────┐  ┌─────▼─────┐                         │
│  │ schemas/  │  │  models/  │                         │
│  │(pydantic) │  │(SQLAlchemy)│                        │
│  └──────────┘  └───────────┘                         │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────▼────────┐
              │     MySQL 8.0    │
              └─────────────────┘
```

## 2. 目录结构

```
family-english-coach/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI 应用入口，挂载路由 + 中间件（CORS / 敏感日志）
│   │   ├── config.py               # 配置管理 (环境变量 / .env) + 启动期安全自检
│   │   ├── database.py             # SQLAlchemy 引擎、会话工厂
│   │   ├── settlement_score.py     # 每周结算四维评分（XP / 完成度 / 稳定性 / 难度）
│   │   ├── gamification.py         # 段位 / 徽章 / 难度系数 difficulty_mult
│   │   ├── cash.py                 # 现金激励：周学习现金分档 + 里程碑奖金
│   │   ├── srs.py                  # 间隔重复（错题滚动复习调度）
│   │   ├── middleware/
│   │   │   └── sensitive.py        # SensitiveDataMiddleware（请求/响应日志）
│   │   │
│   │   ├── models/                 # SQLAlchemy ORM 模型
│   │   │   ├── __init__.py         # 统一导出（见下方模型清单）
│   │   │   ├── base.py             # Base + TimestampMixin
│   │   │   ├── enums.py            # WordType / TagType / MasteryLevel / PracticeMode / Plan* 等
│   │   │   ├── member.py           # Member（含 total_xp / cash_balance）
│   │   │   ├── unit.py
│   │   │   ├── word.py             # Word + WordTag（标签在此，无独立 tag.py）
│   │   │   ├── mastery.py          # MasteryRecord
│   │   │   ├── practice.py         # PracticeSession + PracticeRecord
│   │   │   ├── plan.py             # LearningPlan + PlanUnit + DailyTask
│   │   │   ├── wrong_book.py       # WrongWordBook
│   │   │   ├── streak.py           # MemberStreak + MemberBadge
│   │   │   ├── settlement.py       # WeeklySettlement
│   │   │   └── cash_milestone.py   # CashMilestone
│   │   │
│   │   ├── schemas/                # Pydantic 请求/响应模型
│   │   │   ├── __init__.py
│   │   │   ├── common.py           # 统一响应体 ApiResponse<T>
│   │   │   ├── exceptions.py       # 统一业务异常
│   │   │   ├── unit.py
│   │   │   ├── word.py
│   │   │   ├── practice.py
│   │   │   ├── plan.py
│   │   │   └── wrong_book.py
│   │   │
│   │   ├── api/                    # FastAPI 路由
│   │   │   ├── __init__.py
│   │   │   ├── deps.py             # get_current_user（OAuth2PasswordBearer / JWT 解码）
│   │   │   ├── router.py           # 汇总注册所有 v1 路由（带 Depends(get_current_user)）
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── auth.py         # 登录（免认证）
│   │   │       ├── health.py       # 健康检查（免认证）
│   │   │       ├── tts.py          # TTS 音频（免认证：st.audio 不带 Authorization 头）
│   │   │       ├── unit.py         # 以下均 JWT 保护
│   │   │       ├── word.py
│   │   │       ├── practice.py
│   │   │       ├── review.py
│   │   │       ├── plan.py
│   │   │       ├── stats.py
│   │   │       ├── ai.py
│   │   │       └── wrong_book.py
│   │   │
│   │   ├── services/               # 业务逻辑层
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py     # JWT 签发 / 校验 + bcrypt
│   │   │   ├── unit_service.py
│   │   │   ├── word_service.py
│   │   │   ├── practice_service.py
│   │   │   ├── plan_service.py
│   │   │   ├── stats_service.py
│   │   │   ├── review_service.py
│   │   │   ├── exercise_service.py
│   │   │   ├── nl_parse_service.py
│   │   │   └── wrong_book_service.py
│   │   │
│   │   ├── repositories/           # 数据访问层
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # 通用 CRUD 基类
│   │   │   ├── unit_repo.py
│   │   │   ├── word_repo.py
│   │   │   ├── mastery_repo.py
│   │   │   ├── plan_repo.py
│   │   │   ├── practice_repo.py
│   │   │   ├── stats_repo.py
│   │   │   └── wrong_book_repo.py
│   │   │
│   │   ├── ai/                     # AI 能力抽象层（provider 可热切换）
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # AIProvider Protocol（无 generate_audio）
│   │   │   ├── base_provider.py    # 公共 HTTP/重试 基类
│   │   │   ├── claude_provider.py
│   │   │   ├── deepseek_provider.py  # deepseek + glm（智谱）复用同一实现
│   │   │   ├── tts_service.py      # 独立 TTS（edge-tts），不属 AIProvider 协议
│   │   │   └── factory.py          # 根据 config 选择 provider（claude / deepseek / glm）
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── weighting.py        # 单词出题权重算法
│   │       ├── cache.py            # Redis 缓存（可选，自动降级）
│   │       └── phonetics.py        # 音标运行时回退（eng_to_ipa）
│   │
│   ├── alembic/                    # 数据库迁移
│   │   ├── env.py
│   │   └── versions/
│   ├── alembic.ini
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── unit/
│   │   └── integration/
│   ├── requirements.txt
│   └── .env                        # 本地环境变量 (不提交)
│
├── frontend-vue/                   # Vue 3 + Naive UI + Pinia + ECharts + Vite
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.ts                 # 应用入口（挂载 Naive UI / Pinia / Router）
│       ├── App.vue
│       ├── api/                    # 后端 API 调用封装（axios + JWT 拦截器）
│       ├── views/                  # 路由页面（Dashboard / Units / Words / Practice / Stats
│       │                           #   / Plans / Search / WrongBook / WeeklySettlement / Ai
│       │                           #   / Progress / Login）
│       ├── components/             # 可复用组件
│       ├── composables/            # Vue composables
│       ├── constants/              # 常量（如 modes.ts：11 种练习模式）
│       ├── router/                 # Vue Router
│       ├── stores/                 # Pinia stores
│       ├── utils/
│       └── styles/
│
├── docs/
│   ├── PRD.md
│   ├── Architecture.md
│   ├── Tasks.md
│   ├── Database.md                 # Phase 1 后补充
│   ├── API.md                      # Phase 1 后补充
│   ├── Settlement.md               # 每周结算 + 现金激励设计
│   └── 词库导入-ECDICT.md           # ECDICT 种子词库导入流程
│
├── docker-compose.yml              # MySQL（Backend / Frontend 独立部署）
├── .gitignore
└── CLAUDE.md
```

## 3. 分层职责

| 层 | 目录 | 职责 | 依赖方向 |
|---|---|---|---|
| Router | `api/v1/` | 参数校验、调用 Service、返回响应 | → Service |
| Service | `services/` | 业务逻辑编排、事务管理 | → Repository, AI |
| Repository | `repositories/` | 数据库 CRUD，不包含业务逻辑 | → Model |
| Model | `models/` | ORM 映射，纯数据结构 | — |
| Schema | `schemas/` | Pydantic 模型，接口契约 | — |
| AI | `ai/` | 统一 AI 能力抽象 | → 外部 API |

**依赖规则：** Router → Service → Repository → Model。禁止跨层调用（Router 不直接操作 Repository）。

### 3.1 认证横切层（Auth / JWT）

全量业务路由受 JWT 保护，认证以 FastAPI 依赖注入横切，不侵入业务层：

- `api/deps.py`：`OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")` + `get_current_user(token)` → 校验 JWT 并返回 `payload["sub"]`（= 用户名，当前单人即 `admin`）。
- `services/auth_service.py`：bcrypt 密码校验 + JWT 签发/解码（`JWT_SECRET_KEY` / `JWT_EXPIRE_MINUTES`）。
- `api/router.py` 装配策略：
  - **免认证**：`auth`（登录）、`health`（健康检查）、`tts`（音频流，因 `st.audio`/`<audio>` 不带 Authorization 头且内容无敏感性）。
  - **JWT 保护**：`unit / word / practice / review / plan / stats / ai / wrong_book`，统一 `include_router(r, dependencies=[Depends(get_current_user)])`。
- 前端（`frontend-vue/src/api/`）axios 拦截器自动注入 `Authorization: Bearer <token>`；401 时回到登录页。
- 启动期安全自检（`config.prepare_security`）：生产环境（`APP_ENV=production`）遇到弱/空 `JWT_SECRET_KEY` 或 `AUTH_PASSWORD` 直接拒绝启动；开发环境兜底为可用配置并告警。

## 4. AI 抽象层设计

```python
# ai/base.py
from typing import Protocol

class AIProvider(Protocol):
    async def generate_dialogue(self, words: list[str], scenario: str) -> DialogueResult: ...
    async def generate_exercise(self, words: list[str], mode: str) -> ExerciseResult: ...
    async def parse_natural_language(self, text: str) -> ParseNLResult: ...

# ai/factory.py
def get_ai_provider() -> AIProvider:
    # 根据 config.settings.AI_PROVIDER 返回对应实现（claude / deepseek / glm）
```

模型切换只需修改 `.env` 中的 `AI_PROVIDER` 值，不改动任何业务代码。TTS 语音合成不属此协议，由独立的 `ai/tts_service.py`（edge-tts）承担。

## 5. 统一响应格式

```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

错误响应：

```json
{
  "code": 400,
  "message": "具体错误描述",
  "data": null
}
```

## 6. 单词出题权重算法

每个单词的出题权重 `W` 计算：

```
W = base_weight × tag_multiplier × mastery_multiplier

base_weight    = 1.0
tag_multiplier = ⭐ 1.2, 🔥 1.5, 📚 1.5, ❌ 0.0, ✅ 0.3
mastery_multiplier = unlearned 1.5, learning 1.3, familiar 1.0, permanent 0.1
```

最终按 `W` 加权随机抽题。

## 7. 技术选型明细

| 组件 | 选型 | 说明 |
|---|---|---|
| Web 框架 | FastAPI | 异步、自动 OpenAPI 文档 |
| ORM | SQLAlchemy 2.0 (async) | 声明式模型 + async session |
| 数据库迁移 | Alembic | 版本化管理 schema 变更 |
| 数据校验 | Pydantic v2 | 请求/响应模型 |
| AI 解析 | AI Provider | 文本词条解析、对话/练习生成（Claude / DeepSeek / GLM） |
| 前端 | Vue 3 + Naive UI + Pinia + ECharts + Vite | 组件化 SPA，`frontend-vue/`（旧 Streamlit 已停支持） |
| 数据库 | MySQL 8.0 | InnoDB，utf8mb4 |
| 容器化 | Docker Compose | 本地开发环境 |

## 8. 开发环境配置

```env
# backend/.env
DATABASE_URL=mysql+aiomysql://root:password@localhost:3306/english_coach?charset=utf8mb4
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_RECYCLE=3600

# AI（claude / deepseek / glm）
AI_PROVIDER=claude
AI_API_KEY=sk-xxx
AI_MODEL=

# 缓存（可选，未连自动降级）
REDIS_URL=redis://localhost:6379/0

# 部署环境：dev（兜底弱配置+告警）| production（拒绝弱配置启动）
APP_ENV=dev
CORS_ORIGINS=http://localhost:5173,http://localhost:8501

# 认证（AUTH_PASSWORD 存 bcrypt 哈希；生产必须配强随机 JWT_SECRET_KEY）
AUTH_USERNAME=admin
AUTH_PASSWORD=
JWT_SECRET_KEY=
JWT_EXPIRE_MINUTES=1440

# 现金激励（默认关；CASH_ENABLED=true 开启；详见 docs/Settlement.md）
CASH_ENABLED=false
CASH_CURRENCY=CNY
CASH_WEEKLY_CAP=50.0
# ...其余 CASH_TIER_* / CASH_MS_* 分档见 app/config.py
```
