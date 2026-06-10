# Architecture — Family English Coach

## 1. 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   Streamlit Frontend                 │
│              (app.py + pages/ + components/)          │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────┐
│                   FastAPI Backend                     │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐  │
│  │  api/     │  │ services/ │  │      ai/         │  │
│  │ (routers) │→ │(business) │→ │ (provider abstraction)│
│  └──────────┘  └─────┬─────┘  └──────────────────┘  │
│                      │                                │
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
│   │   ├── main.py                 # FastAPI 应用入口，挂载路由
│   │   ├── config.py               # 配置管理 (环境变量 / .env)
│   │   ├── database.py             # SQLAlchemy 引擎、会话工厂
│   │   │
│   │   ├── models/                 # SQLAlchemy ORM 模型
│   │   │   ├── __init__.py
│   │   │   ├── unit.py
│   │   │   ├── word.py
│   │   │   ├── mastery.py
│   │   │   ├── tag.py
│   │   │   ├── plan.py
│   │   │   └── practice.py
│   │   │
│   │   ├── schemas/                # Pydantic 请求/响应模型
│   │   │   ├── __init__.py
│   │   │   ├── word.py
│   │   │   ├── unit.py
│   │   │   ├── practice.py
│   │   │   ├── plan.py
│   │   │   └── common.py           # 统一响应体 ApiResponse<T>
│   │   │
│   │   ├── api/                    # FastAPI 路由
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── unit.py
│   │   │   │   ├── word.py
│   │   │   │   ├── practice.py
│   │   │   │   ├── plan.py
│   │   │   │   └── stats.py
│   │   │   └── router.py           # 汇总注册所有 v1 路由
│   │   │
│   │   ├── services/               # 业务逻辑层
│   │   │   ├── __init__.py
│   │   │   ├── unit_service.py
│   │   │   ├── word_service.py
│   │   │   ├── practice_service.py
│   │   │   ├── plan_service.py
│   │   │   ├── stats_service.py
│   │   │   └── ocr_service.py
│   │   │
│   │   ├── repositories/           # 数据访问层
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # 通用 CRUD 基类
│   │   │   ├── unit_repo.py
│   │   │   ├── word_repo.py
│   │   │   ├── mastery_repo.py
│   │   │   ├── plan_repo.py
│   │   │   └── practice_repo.py
│   │   │
│   │   ├── ai/                     # AI 能力抽象层
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # AIProvider Protocol
│   │   │   ├── claude_provider.py
│   │   │   ├── minimax_provider.py
│   │   │   ├── zhipu_provider.py
│   │   │   ├── deepseek_provider.py
│   │   │   └── factory.py          # 根据 config 选择 provider
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── weighting.py        # 单词出题权重算法
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
├── frontend/
│   ├── app.py                      # Streamlit 入口
│   ├── pages/                      # Streamlit 多页面
│   │   ├── 1_📚_Units.py
│   │   ├── 2_🔤_Words.py
│   │   ├── 3_🎯_Practice.py
│   │   ├── 4_📊_Stats.py
│   │   └── 5_📅_Plan.py
│   ├── components/                 # 可复用组件
│   │   ├── word_card.py
│   │   ├── spelling_input.py
│   │   ├── choice_quiz.py
│   │   └── mastery_badge.py
│   ├── api_client/                 # 后端 API 调用封装
│   │   ├── __init__.py
│   │   └── client.py
│   └── requirements.txt
│
├── docs/
│   ├── PRD.md
│   ├── Architecture.md
│   ├── Tasks.md
│   ├── Database.md                 # Phase 1 后补充
│   └── API.md                      # Phase 1 后补充
│
├── docker-compose.yml              # MySQL + Backend + Frontend
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

## 4. AI 抽象层设计

```python
# ai/base.py
from typing import Protocol

class AIProvider(Protocol):
    async def parse_image(self, image_bytes: bytes) -> OCRResult: ...
    async def generate_dialogue(self, words: list[str], scenario: str) -> DialogueResult: ...
    async def generate_exercise(self, words: list[str], mode: str) -> ExerciseResult: ...
    async def generate_audio(self, text: str) -> bytes: ...

# ai/factory.py
def get_provider() -> AIProvider:
    # 根据 config.settings.AI_PROVIDER 返回对应实现
```

模型切换只需修改 `.env` 中的 `AI_PROVIDER` 值，不改动任何业务代码。

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
| OCR (MVP) | AI Provider | 调用 AI 解析图片 |
| 前端 | Streamlit | 快速原型，适合内部工具 |
| 数据库 | MySQL 8.0 | InnoDB，utf8mb4 |
| 容器化 | Docker Compose | 本地开发环境 |

## 8. 开发环境配置

```env
# backend/.env
DATABASE_URL=mysql+aiomysql://root:password@localhost:3306/english_coach
AI_PROVIDER=claude
AI_API_KEY=sk-xxx
```
