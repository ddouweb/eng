# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Family English Coach (家庭英语学习系统)** — helps family members learn English. Users create Units and add words manually or via AI-powered natural-language parsing (paste any text, the system extracts word/sentence entries), then drives practice via flashcards, spelling, dictation, and AI-generated scenario dialogues. Includes learning plans, daily goals, and mastery tracking.

> **当前实现：单人模式** —— 单成员账户（member id=1），词库经 ECDICT 脚本/SQL 种子维护；多成员切换、`/members` API、家庭排行榜已移除（排行榜页改为「我的进步趋势」单人页）。加词入口（AI 文本解析/手动录入）保持只读是有意业务决策，不是 bug。member 表与各表 member_id 外键保留（外键根 + 迁移引用）。

## Tech Stack

- **Backend**: Python 3.11+ / FastAPI
- **Frontend**: Vue 3 + Naive UI + Pinia + ECharts + Vite（`frontend-vue/`；旧 Streamlit `frontend/` 已停止支持）
- **Database**: MySQL 8.0
- **ORM**: SQLAlchemy 2.0 (async via aiomysql)
- **Migrations**: Alembic
- **AI** (optional, swappable): Claude / DeepSeek / GLM(智谱) — all AI calls must be behind an abstraction so models can be swapped without changing business logic

## Development Workflow — MANDATORY

### Modular Iteration

- Work on **one module or interface at a time**. Never generate the entire system in one pass.
- Each module output must include: module name, description, input/output JSON schema, function/interface spec, and dependency list.
- After completing a module, run a self-review (Review Agent) before proceeding to the next.

### MVP First

The first deliverable is the closed loop:

```
Word bank generation (manual entry / AI text parse) → Flashcard practice → Mastery status record
```

Advanced features (AI scenario dialogues, pronunciation scoring, Redis caching) are implemented only after the MVP is stable.

### Phase Workflow

Development follows the phased plan in `docs/Tasks.md`. Each Phase completes before the next begins. See `docs/Tasks.md` for the full checklist and current progress.

### Agent Roles

When implementing features, follow this simulated role pattern:

| Role | Responsibility |
|---|---|
| Leader | Receives requirements, splits tasks, delegates, consolidates |
| Product | Breaks requirements into deliverable feature modules |
| Architecture | System architecture, module dependencies, DB schema |
| Backend | API logic and database operations |
| Frontend | Vue 3 + Naive UI 界面 |
| AI | Generate dialogues, exercises, pronunciation content |
| Test | Unit and integration tests |
| Review | Code/interface/logic compliance check |

All module interfaces must include example API calls. Naming must be clear and extensible.

## Project Structure

```
backend/
  app/
    main.py              # FastAPI app entry
    config.py            # Settings / env vars (pydantic-settings)
    database.py          # Async engine, session factory, get_db dependency
    settlement_score.py  # 每周结算四维评分（XP / 完成度 / 稳定性 / 难度）
    gamification.py      # 段位 / 徽章 / 难度系数（difficulty_mult）
    cash.py              # 现金激励：周学习现金分档 + 里程碑奖金（虚拟钱包）
    srs.py               # 间隔重复（错题本滚动复习调度）
    middleware/          # 横切中间件
      sensitive.py       # SensitiveDataMiddleware（请求/响应日志）
    models/              # SQLAlchemy ORM models
      enums.py           # MasteryLevel / TagType / PracticeMode / Plan* 等枚举
      member.py          # Member（含 total_xp / cash_balance）
      settlement.py      # WeeklySettlement
      cash_milestone.py  # CashMilestone
      streak.py          # MemberStreak / MemberBadge
      wrong_book.py      # WrongWordBook
      unit.py / word.py（含 WordTag）/ mastery.py / practice.py / plan.py
    schemas/             # Pydantic 请求/响应模型
      common.py          # Unified ApiResponse[T] envelope
      exceptions.py      # 统一业务异常
    api/
      deps.py            # get_current_user（OAuth2PasswordBearer / JWT）
      router.py          # Aggregates all v1 routers（带 Depends(get_current_user)）
      v1/                # Route handlers
        auth.py health.py tts.py          # 免认证（登录 / 健康检查 / TTS 音频）
        unit.py word.py practice.py       # 业务路由（JWT 保护）
        review.py plan.py stats.py
        ai.py wrong_book.py
    services/            # Business logic（auth/exercise/nl_parse/plan/practice/review/stats/unit/word/wrong_book）
    repositories/        # Data access layer（含 stats_repo / wrong_book_repo / mastery_repo 等）
    ai/                  # AI provider abstraction (swappable)
      base.py            # AIProvider Protocol（无 generate_audio）
      base_provider.py   # 公共 HTTP / 重试基类
      claude_provider.py deepseek_provider.py  # deepseek + glm(智谱) 复用同一实现
      factory.py         # Provider selection via config（claude / deepseek / glm）
      tts_service.py     # 独立 TTS（edge-tts），不属 AIProvider 协议
    utils/
      weighting.py       # Word selection weight algorithm
      cache.py           # Redis 缓存（可选，自动降级）
      phonetics.py       # 音标运行时回退（eng_to_ipa）
  alembic/               # DB migrations
  tests/
    unit/
    integration/
  requirements.txt
frontend-vue/
  package.json           # Vue 3 + Naive UI + Pinia + ECharts 依赖
  vite.config.ts         # Vite 构建 / 代理配置
  tsconfig.json
  index.html
  src/
    main.ts App.vue
    api/                 # 后端 API 调用封装（axios 拦截器）
    views/               # 路由页面（Dashboard / Units / Words / Practice / Stats / Plans / Search / WrongBook / WeeklySettlement / Ai / Progress / Login）
    components/          # 可复用组件
    composables/         # Vue composables
    constants/           # 常量（如 modes.ts：11 种练习模式）
    router/ stores/      # Vue Router + Pinia
    utils/ styles/
docs/
  PRD.md                 # Product requirements
  Architecture.md        # System architecture design
  Tasks.md               # Phase-by-phase development checklist
  Database.md            # DB schema (Phase 1+)
  API.md                 # API spec (Phase 1+)
  Settlement.md          # 每周结算 + 现金激励设计（XP 四维 / bonus / freeze / 现金奖）
  词库导入-ECDICT.md      # ECDICT 种子词库导入流程
docker-compose.yml       # MySQL service
```

## Commands

```bash
# Start MySQL
docker-compose up -d

# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (Vue 3 + Naive UI)
cd frontend-vue
npm install
npm run dev      # Vite dev server（默认 http://localhost:5173）

# DB migration
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head

# Tests
cd backend
pytest                          # all tests
pytest tests/unit/test_word.py  # single test file
pytest -k "test_create_unit"     # by test name pattern

# Lint
ruff check . --fix
```

## Data Model — Key Entities

- **Unit**: corresponds to one uploaded textbook image (Unit 1..n)
- **Word**: English word/sentence with Chinese translation, belongs to a Unit
- **WordTag**: enum — ⭐ favorite, 🔥 high-frequency, 📚 exam-focus, ❌ excluded, ✅ memorized
- **MasteryLevel**: enum — `unlearned`, `learning`, `familiar`, `permanent`
- **LearningPlan**: daily goal (word count), selected units, deadline date
- **PracticeRecord**: timestamped log of practice attempts and results
- **WrongWordBook**: 错题本，练习中答错自动收录，由 `srs.py` 调度滚动复习
- **MemberStreak / MemberBadge**: 连续学习天数与获得的徽章（gamification）
- **WeeklySettlement / CashMilestone**: 每周结算记录与现金里程碑奖金（虚拟钱包 `Member.cash_balance`）；详见 `docs/Settlement.md`
- **Member.total_xp / cash_balance**: 累计 XP（驱动段位）与现金激励虚拟钱包余额

## Word Display Strategy

- Permanently memorized words (✅) do not appear in active practice by default.
- High-frequency (🔥) and exam-focus (📚) words appear more often in practice rounds.
- Word selection for practice sessions uses a weighted algorithm based on tags and mastery level.

## API Design Conventions

- RESTful endpoints under `/api/v1/`
- Request/response bodies are Pydantic models in `schemas/`
- All responses follow `{ "code": int, "message": str, "data": ... }` envelope
- Each endpoint must have a docstring with an example `curl` call

## AI Provider Abstraction

All AI calls go through a common interface in `backend/app/ai/`:

```python
class AIProvider(Protocol):
    async def generate_dialogue(self, words: list[str], scenario: str) -> DialogueResult: ...
    async def generate_exercise(self, words: list[str], mode: str) -> ExerciseResult: ...
    async def parse_natural_language(self, text: str) -> ParseNLResult: ...
```

Concrete implementations (Claude / DeepSeek / GLM(智谱)) are registered via `ai/factory.py`. GLM 复用 DeepSeek 实现（仅替换 `base_url` 与默认 model）。Switching providers requires only changing `.env`. TTS 不属此协议，由独立的 `ai/tts_service.py`（edge-tts）承担。

## Mastery Status Colors (Frontend)

| Status | Color |
|---|---|
| unlearned | Gray |
| learning | Orange |
| familiar | Blue |
| permanent | Green |

Same status = same color everywhere (cards, stats, progress bars).

# 其它说明
 - 除非明确指定语言，一律使用中文回复
 - 前端已经全部切换到vue版本： @frontend-vue
 - @frontend 已经不再提供支持

# 生产服务器说明
 - 可以用过ssh jd 访问生产服务器。
 - 生产服务器部署目录在： /data/eng 是直接部署的。并非使用docker
 - 访问数据库使用： mysql -h127.0.0.1 -uroot -p english_coach
 - nginx配置文件：/data/video_root/cfg/nginx-default.conf
 - nginx访问域名配置: eng.webtao.cn
 - 重启nginx: docker compose -f /data/video_root/docker-compose.yml restart nginx
 - 不要在生产环境自动安装任何内容，若需要安装，需要我确认
 - 不要在生产环境启动、停止、重启我的任何服务，除非明确告知我，并经过我同意
 - 生成环境的python运行在 /data/eng/backend/.venv下
 - 除非明确说明。否则不能直接修改服务器文件



