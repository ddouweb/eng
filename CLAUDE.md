# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Family English Coach (家庭英语学习系统)** — helps family members learn English. Users create Units and add words manually or via AI-powered natural-language parsing (paste any text, the system extracts word/sentence entries), then drives practice via flashcards, spelling, dictation, and AI-generated scenario dialogues. Includes learning plans, daily goals, and mastery tracking.

## Tech Stack

- **Backend**: Python 3.11+ / FastAPI
- **Frontend**: Streamlit
- **Database**: MySQL 8.0
- **ORM**: SQLAlchemy 2.0 (async via aiomysql)
- **Migrations**: Alembic
- **AI** (optional, swappable): Claude / Minimax / 智谱 / DeepSeek — all AI calls must be behind an abstraction so models can be swapped without changing business logic

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
| Frontend | Streamlit UI |
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
    models/              # SQLAlchemy ORM models
    schemas/             # Pydantic request/response schemas
      common.py          # Unified ApiResponse[T] envelope
    api/
      router.py          # Aggregates all v1 routers
      v1/                # Route handlers (unit, word, practice, plan, stats)
    services/            # Business logic
    repositories/        # Data access layer
    ai/                  # AI provider abstraction (swappable)
      base.py            # AIProvider Protocol
      factory.py         # Provider selection via config
    utils/
      weighting.py       # Word selection weight algorithm
  alembic/               # DB migrations
  tests/
    unit/
    integration/
  requirements.txt
frontend/
  app.py                 # Streamlit entry
  pages/                 # Streamlit multi-page app
  components/            # Reusable UI components
  api_client/            # Backend API call wrapper
docs/
  PRD.md                 # Product requirements
  Architecture.md        # System architecture design
  Tasks.md               # Phase-by-phase development checklist
  Database.md            # DB schema (Phase 1+)
  API.md                 # API spec (Phase 1+)
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

# Frontend (Phase 4+)
cd frontend
pip install -r requirements.txt
streamlit run app.py --server.port 8501

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

Concrete implementations (Claude, Minimax, Zhipu, DeepSeek) are registered via `ai/factory.py`. Switching providers requires only changing `.env`.

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
