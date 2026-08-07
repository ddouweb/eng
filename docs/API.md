# API — English Coach

所有接口前缀：`/api/v1`

统一响应格式：

```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

---

## 鉴权（JWT）

**除登录 / 健康检查 / TTS 外，所有接口都需 JWT Bearer Token。**

- 登录：`POST /api/v1/auth/login`，返回 `token`（HS256，有效期 `JWT_EXPIRE_MINUTES`，`.env` 配置）。
- 后续请求头：`Authorization: Bearer <token>`（FastAPI `OAuth2PasswordBearer`，tokenUrl=`/api/v1/auth/login`，由 `app/api/deps.py:get_current_user` 校验）。
- 缺失 / 过期 / 非法 → `401 Invalid or expired token`。
- **免鉴权**：`auth`、`health`、`tts`（TTS 免登录：浏览器 `audio` 标签加载音频时不带 `Authorization` 头，且音频内容无敏感性）。
- 需鉴权：`units`、`words`、`practice`、`review`、`plans`、`stats`、`ai`、`wrong-book`（在 `app/api/router.py` 统一挂 `Depends(get_current_user)`）。

下文每个需鉴权接口的标题前均标 🔒。

---

## Auth API

### POST /api/v1/auth/login — 登录拿 token（免鉴权）

```json
// Request
{
  "username": "admin",
  "password": "admin123"
}

// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
  }
}
```

用户名匹配 `.env` 的 `AUTH_USERNAME`；密码校验 `AUTH_PASSWORD`——推荐存 bcrypt 哈希（`$2` 开头走恒定时间 bcrypt 校验），明文则 `hmac.compare_digest` 兜底（迁移期，不推荐长期）。失败 → `401 用户名或密码错误`。

---

## Unit API

### 🔒 POST /api/v1/units — 创建 Unit

```json
// Request
{
  "title": "Unit 1 - Hello!",
  "sequence": 1
}

// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "title": "Unit 1 - Hello!",
    "sequence": 1,
    "word_count": 0,
    "created_at": "2026-06-10T10:00:00",
    "updated_at": "2026-06-10T10:00:00"
  }
}
```

`sequence` 全局唯一，冲突 → `409`。

### 🔒 GET /api/v1/units — Unit 列表

Query 参数：`page=1`、`page_size=20`（≤100）

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      { "id": 1, "title": "Unit 1", "sequence": 1, "word_count": 15, "created_at": "...", "updated_at": "..." }
    ],
    "total": 5,
    "page": 1,
    "page_size": 20
  }
}
```

### 🔒 GET /api/v1/units/{unit_id} — Unit 详情（元数据，不含单词）

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "title": "Unit 1 - Hello!",
    "sequence": 1,
    "created_at": "2026-06-10T10:00:00",
    "updated_at": "2026-06-10T10:00:00"
  }
}
```

> 详情接口只返回 Unit 元数据，**不含单词列表**。查某 Unit 的单词用 [`GET /api/v1/words/units/{unit_id}/words`](#-get-api-v1-words-units-unit_id-words--单元内单词列表)。

### 🔒 PUT /api/v1/units/{unit_id} — 更新 Unit

```json
// Request
{
  "title": "Unit 1 - Greetings",
  "sequence": 1
}
```

### 🔒 DELETE /api/v1/units/{unit_id} — 删除 Unit

级联删除关联的 Word、WordTag、MasteryRecord。

---

## Word API

> 路由前缀 `/words`，故单元内单词的真实路径是 `/api/v1/words/units/{unit_id}/words`（不是 `/units/{unit_id}/words`）。

### 🔒 POST /api/v1/words/units/{unit_id}/words — 批量添加单词

```json
// Request
{
  "words": [
    { "english": "hello", "chinese": "你好", "type": "word" },
    { "english": "good morning", "chinese": "早上好", "type": "word" },
    { "english": "How are you?", "chinese": "你好吗？", "type": "sentence" }
  ]
}
```

每个 word 可选富字段（全部可空，按可用性提供）：`seq`（单元内序号）、`phonetic`（裸 IPA，不含包裹斜杠）、`definition`（英文释义）、`pos`（词性）、`example`（例句）。

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "created_count": 3,
    "words": [
      {
        "id": 1, "unit_id": 1, "english": "hello", "chinese": "你好",
        "type": "word", "seq": null,
        "phonetic": "həˈloʊ", "definition": null, "pos": null, "example": null,
        "created_at": "...", "updated_at": "..."
      }
    ]
  }
}
```

### 🔒 GET /api/v1/words/units/{unit_id}/words — 单元内单词列表

Query 参数：`page=1`、`page_size=50`（≤5000）、`type=word|sentence`（可选筛选）、`member_id=1`（掌握度按 member 过滤）

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "unit_id": 1,
        "english": "hello",
        "chinese": "你好",
        "type": "word",
        "seq": 1,
        "phonetic": "həˈloʊ",
        "definition": "say hello to",
        "pos": "v.",
        "example": "Hello, how are you?",
        "tags": ["favorite", "high_freq"],
        "mastery": { "level": "learning", "consecutive_correct": 2, "correct_count": 3, "wrong_count": 1 },
        "created_at": "...",
        "updated_at": "..."
      }
    ],
    "total": 15,
    "page": 1,
    "page_size": 50
  }
}
```

### 🔒 GET /api/v1/words/search — 全局搜词（跨所有 Unit）

Query 参数（均可选）：`q`（英文/中文模糊匹配，自动转义 `%` `_`，≤200 字符）、`member_id=1`、`tag=favorite|high_freq|exam_focus|excluded|memorized`、`level=unlearned|learning|familiar|permanent`（按该 member 的掌握度过滤；`unlearned` 含「无记录」）、`unit_id`、`type=word|sentence`、`page=1`、`page_size=50`（≤5000）

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 12,
        "unit_id": 3,
        "unit_title": "Unit 3 - Fruits",
        "english": "apple",
        "chinese": "苹果",
        "type": "word",
        "seq": 1,
        "phonetic": "ˈæpəl",
        "definition": null,
        "pos": null,
        "example": null,
        "tags": ["favorite"],
        "mastery": { "level": "learning", "consecutive_correct": 1, "correct_count": 2, "wrong_count": 0 }
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 50
  }
}
```

### 🔒 PUT /api/v1/words/{word_id} — 更新单词

```json
// Request（字段均可选，partial update）
{
  "english": "good evening",
  "chinese": "晚上好",
  "type": "word",
  "seq": 2,
  "phonetic": "ɡʊd ˈiːvnɪŋ",
  "definition": null,
  "pos": null,
  "example": null
}
```

### 🔒 DELETE /api/v1/words/{word_id} — 删除单词

级联删除关联的 WordTag 和 MasteryRecord。

### 🔒 POST /api/v1/words/{word_id}/tags — 设置标签（覆盖式）

```json
// Request
{
  "tags": ["favorite", "high_freq"]
}

// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "word_id": 1,
    "tags": ["favorite", "high_freq"]
  }
}
```

### 🔒 DELETE /api/v1/words/{word_id}/tags/{tag} — 移除单个标签

```
DELETE /api/v1/words/1/tags/favorite
```

### 🔒 GET /api/v1/words/{word_id}/mastery — 查询掌握状态

Query 参数：`member_id=1`（默认 1）

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "word_id": 1,
    "member_id": 1,
    "level": "learning",
    "consecutive_correct": 2,
    "correct_count": 3,
    "wrong_count": 1,
    "updated_at": "..."
  }
}
```

> **关于 `mastery` 字典**：所有返回 `mastery` 的接口（单词列表 / 搜索 / submit / rejudge 等）只暴露 `level / consecutive_correct / correct_count / wrong_count` 四个计数字段，**不含 SM-2 间隔重复字段**（`interval_days / ease_factor / next_review_date / last_reviewed_at`）。需要「到期复习」视图请用 [`GET /api/v1/review/due`](#-get-api-v1-review-due--今日到期复习)。

---

## Practice API

### 🔒 POST /api/v1/practice/start — 开始练习会话

```json
// Request
{
  "member_id": 1,
  "mode": "flashcard",
  "unit_ids": [1, 2],
  "count": 10,
  "task_type": "learn"
}
```

- `unit_ids`：选中的 Unit 列表，**可含虚拟错题本单元 ID `0`**（与真实 Unit 多选混合）。
- `count`：1~2000，默认 10。
- `task_type`（可选，默认 `learn`）：`learn`（学习日默认选题，按 unit_id 抽取）/ `weekly_review`（按本周练习记录的 word_id 选题）/ `monthly_review`（本月）/ `wrong_word_drill`（错题优先刷）。候选为空时按类型返回 400（如「暂无错题可刷」）。

```json
// Response — 返回会话 ID + 题集（question_word_ids 落库，用于提交校验防刷分）
{
  "code": 200,
  "message": "success",
  "data": {
    "session_id": 1,
    "mode": "flashcard",
    "total": 10,
    "questions": [
      {
        "question_id": 0,
        "word_id": 5,
        "english": "hello",
        "chinese": "你好",
        "type": "word",
        "tags": ["favorite"],
        "mastery_level": "learning",
        "is_due": true,
        "is_new": false,
        "overdue_days": 2,
        "wrong_count": 1,
        "phonetic": "həˈloʊ",
        "definition": null,
        "pos": null,
        "example": null
      }
    ]
  }
}
```

> 题目里的 `type` 是**词条类型**（`word` / `sentence`），练习模式看会话级 `mode`。`weight` 为内部抽题权重（也会随题返回，前端可忽略）。

`mode` 可选值（`PracticeMode` 枚举，共 12 个，与 `practice_session.mode` ENUM 一致）：

| 值 | 说明 | 判定方式 |
|---|---|---|
| `flashcard` | 单词卡（看英翻中） | 主观，回退客户端 |
| `spelling` | 拼写（中→英） | 客观，答案=word.english |
| `choice` | 选择题（英→中） | 客观，答案=word.chinese |
| `cn2en_choice` | 中→英选择 | 客观，答案=word.english |
| `en2cn_write` | 英→中默写 | 客观，答案=word.chinese |
| `dictation` | 听写 | 客观，答案=word.english |
| `matching` | 连线配对 | 主观 |
| `timed_challenge` | 限时挑战（同 choice） | 客观，答案=word.chinese |
| `scramble` | 字母重排 | 客观，答案=word.english |
| `memory_flash` | 记忆闪卡 | 主观 |
| `flip_match` | 翻牌配对 | 主观 |
| `dialogue` | 场景对话 | 主观 |

> 客观题由服务端按答案复判 `is_correct`（忽略客户端传入值，防伪造刷分）；主观题无客观答案，回退客户端。`choice` 模式响应里每题额外带 `options`（4 选项，含正确答案）。

### 🔒 POST /api/v1/practice/{session_id}/submit — 提交单题答案

```json
// Request
{
  "word_id": 5,
  "is_correct": true,
  "user_answer": "hello"
}
```

- `word_id` 必须在本会话题集内（旧会话 `question_word_ids` 为 NULL 时跳过校验，向后兼容）。
- 同一会话同一词幂等：重复提交只回读既有记录，不重复计数 / 改掌握度。
- 会话已 `finish` → `400 Session already ended`（结束页改判请用 rejudge）。

```json
// Response — 返回更新后的掌握状态 + 坚持机制快照
{
  "code": 200,
  "message": "success",
  "data": {
    "is_correct": true,
    "correct_answer": "hello",
    "mastery": {
      "level": "learning",
      "consecutive_correct": 1,
      "correct_count": 1,
      "wrong_count": 0
    },
    "streak": {
      "current_streak": 3,
      "longest_streak": 5,
      "freeze_balance": 2,
      "last_active_date": "2026-07-28"
    },
    "xp_delta": 5,
    "total_xp": 120,
    "new_badges": ["streak_7"]
  }
}
```

> `streak / xp_delta / total_xp / new_badges` 仅在「新提交」时返回；命中幂等去重（重复提交）时响应只含 `is_correct / correct_answer / mastery`。
> - `xp_delta`：答对才得，`round((新词 5 / 复习 2) × 难度系数)`，难度系数 ∈ [0.5, 2.0]；答错为 0。
> - `streak`：仅「今日首次该成员练习」推进一次（天然幂等）。
> - `new_badges`：本次新发放的徽章 key（streak / XP 阈值 / `first_permanent`）。

### 🔒 POST /api/v1/practice/{session_id}/rejudge — 结束页改判某题正误

允许在会话 `finish` 之后调用；绕过 submit 的 `ended_at` 拒绝、幂等去重与客观题服务端复判，按人工判定覆盖更新 PracticeRecord / 会话计数 / mastery / SRS / 错题本 / 每日任务 / XP。徽章正向补发、不回收。

```json
// Request
{
  "word_id": 5,
  "is_correct": true
}
```

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "is_correct": true,
    "changed": true,
    "correct_count": 8,
    "accuracy": 80.0,
    "xp_delta": 4,
    "total_xp": 124,
    "mastery": {
      "level": "familiar",
      "consecutive_correct": 3,
      "correct_count": 3,
      "wrong_count": 0
    },
    "new_badges": ["first_permanent"]
  }
}
```

> 幂等：该题 record 已是目标态 → `changed=false`，此时响应只含 `is_correct / changed / correct_count / accuracy / mastery`（不重复加减 XP / 徽章）。该题尚未作答 → `404 该题尚未作答，无法改判`。

### 🔒 POST /api/v1/practice/{session_id}/finish — 结束练习会话

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "session_id": 1,
    "mode": "flashcard",
    "total_count": 10,
    "correct_count": 8,
    "accuracy": 80.0,
    "started_at": "2026-06-10T10:00:00",
    "ended_at": "2026-06-10T10:15:00"
  }
}
```

### 🔒 GET /api/v1/practice/{session_id} — 查询会话详情

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "session_id": 1,
    "mode": "flashcard",
    "total_count": 10,
    "correct_count": 8,
    "status": "in_progress",
    "records": [
      {"word_id": 5, "is_correct": true, "user_answer": "hello", "created_at": "..."},
      {"word_id": 6, "is_correct": false, "user_answer": "helo", "created_at": "..."}
    ]
  }
}
```

`status`：`in_progress`（`ended_at` 为空）/ `completed`（已 finish）。

---

## Review API

### 🔒 GET /api/v1/review/due — 今日到期复习

首页 / 练习页「今日复习」入口。基于 SM-2 `next_review_date` 给出到期 / 逾期 / 新词计数与到期词列表（按「逾期多、错得多」优先排序）。

Query 参数：`member_id=1`、`unit_ids=1,2`（逗号分隔，不传=全部）、`limit=50`（1~500）

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "due_today": 6,
    "overdue": 2,
    "new_available": 12,
    "items": [
      {
        "word_id": 5,
        "english": "hello",
        "chinese": "你好",
        "phonetic": "həˈloʊ",
        "pos": "v.",
        "definition": "say hello to",
        "example": "Hello, how are you?",
        "mastery_level": "learning",
        "next_review_date": "2026-07-27",
        "days_overdue": 1,
        "wrong_count": 1
      }
    ]
  }
}
```

- `due_today`：有 mastery 行、`next_review_date <= today`、`level != permanent`。
- `overdue`：其中 `next_review_date < today`（已逾期）。
- `new_available`：范围内无 mastery 行的新词。
- `permanent` 词两边都不计（到期概念不适用；其低频回炉由 weighting 负责）。

---

## Wrong-Book API

> 路由前缀 `/wrong-book`。错题本是 member 维度的全局错题集合（跨所有 Unit）：答错自动 upsert（`wrong_count + 1`），答对时刻意不动，需用户手动移除。练习页可用虚拟 Unit ID `0` 把错题本词加入候选池。

### 🔒 GET /api/v1/wrong-book — 错题本列表

Query 参数：`member_id=1`、`page=1`、`page_size=50`（≤500）

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 3,
        "word_id": 5,
        "english": "hello",
        "chinese": "你好",
        "unit_id": 1,
        "unit_title": "Unit 1 - Hello!",
        "word_type": "word",
        "added_at": "2026-07-20T10:00:00",
        "wrong_count": 2,
        "mastery_level": "learning",
        "mastery_wrong_count": 2,
        "mastery_correct_count": 1
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 50
  }
}
```

### 🔒 GET /api/v1/wrong-book/count — 错题总数

Query 参数：`member_id=1`

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": { "total": 12 }
}
```

### 🔒 DELETE /api/v1/wrong-book — 清空错题本

Query 参数：`member_id=1`

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": { "removed": 12 }
}
```

### 🔒 POST /api/v1/wrong-book/{word_id} — 手动加入错题本

Query 参数：`member_id=1`（必填）

```json
// Response（首次加入）
{
  "code": 200,
  "message": "success",
  "data": { "word_id": 5, "already_existed": false }
}
```

> 已在错题本中 → `{"id": ..., "already_existed": true}`，不重复加。词不存在 → `404`。

### 🔒 DELETE /api/v1/wrong-book/{word_id} — 移除单个错题

Query 参数：`member_id=1`（必填）

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": { "word_id": 5 }
}
```

> 该词不在错题本 → `404`。

---

## Plan API

### 🔒 POST /api/v1/plans — 创建学习计划

```json
// Request
{
  "name": "三年级上册",
  "daily_goal": 15,
  "unit_ids": [1, 2],
  "deadline": "2026-07-31",
  "start_date": "2026-06-10",
  "learn_weekdays": [0, 1, 2, 3, 4],
  "monthly_review_day": 31,
  "plan_type": "forward"
}
```

字段说明（除 `name`/`unit_ids` 外均可选）：

- `daily_goal`：1~200，默认 30。
- `start_date`：计划生效起始日，默认今天；二/三轮可设未来日期，到期前不产出任务。
- `learn_weekdays`：学习日（`0=Mon..6=Sun`），默认 `[0,1,2,3,4]`，自动去重排序。
- `monthly_review_day`：月复习日，`None`/`1-28`/`31`（月末）；不支持 29/30。
- `plan_type`：`forward`（首轮学新词）/ `review_only`（二轮纯复习）/ `wrong_word_drill`（三轮错题刷），默认 `forward`。

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "member_id": 1,
    "name": "三年级上册",
    "daily_goal": 15,
    "deadline": "2026-07-31",
    "status": "active",
    "created_at": "2026-06-10T10:00:00",
    "learn_weekdays": [0, 1, 2, 3, 4],
    "monthly_review_day": 31,
    "start_date": "2026-06-10",
    "plan_type": "forward"
  }
}
```

创建时按剩余未掌握单词数、每日目标和截止日期生成 DailyTask 列表（含 learn / 周复习 / 月复习任务，按 `learn_weekdays` 落学习日）。

### 🔒 GET /api/v1/plans — 查询计划列表

Query 参数：`status=active|paused|completed`（可选筛选）

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "id": 1,
      "member_id": 1,
      "name": "三年级上册",
      "daily_goal": 15,
      "deadline": "2026-07-31",
      "status": "active",
      "created_at": "2026-06-10T10:00:00",
      "learn_weekdays": [0, 1, 2, 3, 4],
      "monthly_review_day": 31,
      "start_date": "2026-06-10",
      "plan_type": "forward"
    }
  ]
}
```

### 🔒 GET /api/v1/plans/{plan_id} — 查看计划详情

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "member_id": 1,
    "name": "三年级上册",
    "daily_goal": 15,
    "deadline": "2026-07-31",
    "status": "active",
    "created_at": "2026-06-10T10:00:00",
    "learn_weekdays": [0, 1, 2, 3, 4],
    "monthly_review_day": 31,
    "start_date": "2026-06-10",
    "plan_type": "forward",
    "unit_ids": [1, 2],
    "tasks": [
      {
        "id": 1,
        "plan_id": 1,
        "task_date": "2026-06-10",
        "new_count": 15,
        "review_count": 4,
        "completed_new": 10,
        "completed_review": 2,
        "status": "in_progress",
        "task_type": "learn"
      }
    ]
  }
}
```

### 🔒 PUT /api/v1/plans/{plan_id}/tasks/{task_id} — 更新任务进度

```json
// Request
{
  "completed_new": 10,
  "completed_review": 3
}
```

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "plan_id": 1,
    "task_date": "2026-06-10",
    "new_count": 15,
    "review_count": 4,
    "completed_new": 10,
    "completed_review": 3,
    "status": "in_progress",
    "task_type": "learn"
  }
}
```

任务状态自动流转：pending → in_progress（有进度） → completed（新词和复习都达标）。

### 🔒 POST /api/v1/plans/{plan_id}/pause — 暂停计划

```json
// Response
{
  "code": 200,
  "message": "Plan paused",
  "data": null
}
```

### 🔒 POST /api/v1/plans/{plan_id}/resume — 恢复计划

```json
// Response
{
  "code": 200,
  "message": "Plan resumed",
  "data": null
}
```

### 🔒 POST /api/v1/plans/{plan_id}/rebalance — 手动重新平衡计划

把剩余未掌握词重新摊到 deadline 前的未来学习日。仅对 **active forward** 计划生效；单日新词硬上限 `cap = round(daily_goal × 1.5)`（过载护栏）；救不回 deadline 时 `feasible=false` 告警但不越界。重平衡时间写入 `learning_plan.last_rebalanced_at`。单人模式 member_id 从计划本身取（恒为 1）。

```
curl -X POST http://localhost:8000/api/v1/plans/1/rebalance \
     -H 'Authorization: Bearer <token>'
```

```json
// Response（重建成功）
{
  "code": 200,
  "message": "success",
  "data": {
    "plan_id": 1,
    "feasible": true,
    "reason": null,
    "remaining_unmastered": 42,
    "remaining_learn_days": 6,
    "effective_learn_days": 6,
    "new_per_day": 7,
    "daily_goal": 15,
    "cap": 22,
    "deadline": "2026-07-31",
    "last_rebalanced_at": "2026-07-28T09:00:00"
  }
}
```

> 短路时 `feasible=false` 且不动任何任务，`reason` 标明原因：`not_rebalanceable`（非 forward / 非 active）/ `no_deadline` / `nothing_to_rebalance`（已无未掌握词）/ `deadline_passed`（deadline 已过或其前无学习日）/ `no_free_learn_days`（未来学习日全被手动占用）/ `infeasible`（即便 cap 也救不回，仍按 cap 重建不越界、只告警）/ `conflict`（并发 rebalance 撞唯一约束，已回滚可重试）。

---

## Stats API

### 🔒 GET /api/v1/stats/overview — 全局统计概览

Query 参数：`member_id=1`

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "total_words": 100,
    "mastery_distribution": {
      "unlearned": 50,
      "learning": 20,
      "familiar": 15,
      "permanent": 15
    },
    "mastered_count": 30,
    "mastery_rate": 30.0,
    "practice_session_count": 10,
    "total_questions": 100,
    "total_correct": 80,
    "accuracy": 80.0,
    "streak_days": 5
  }
}
```

### 🔒 GET /api/v1/stats/units/{unit_id} — 单元统计

Query 参数：`member_id=1`

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "unit_id": 1,
    "total_words": 15,
    "mastery_distribution": {
      "unlearned": 5,
      "learning": 3,
      "familiar": 4,
      "permanent": 3
    },
    "mastered_count": 7,
    "mastery_rate": 46.7
  }
}
```

### 🔒 GET /api/v1/stats/trend — 练习趋势

Query 参数：`days=30`（1~365）、`member_id=1`

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "days": 7,
    "daily": [
      { "date": "2026-06-09", "total": 20, "correct": 16 },
      { "date": "2026-06-10", "total": 15, "correct": 12 }
    ]
  }
}
```

### 🔒 GET /api/v1/stats/profile — 坚持机制画像

首页坚持机制卡片：连续学习 / 最长 / freeze 余额 / XP 段位 / 徽章。**入口先懒结算上周**（`_maybe_settle_week`），故 bonus 入账后 XP / 段位 / 徽章即时反映。

Query 参数：`member_id=1`

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "current_streak": 5,
    "longest_streak": 12,
    "freeze_balance": 2,
    "last_active_date": "2026-07-28",
    "total_xp": 1200,
    "level": {
      "level_index": 4,
      "level_name": "钻石",
      "level_icon": "💎",
      "level_min_xp": 1000,
      "next_level_min_xp": 2000,
      "next_level_name": "大师",
      "progress": 0.2
    },
    "badges": ["streak_7", "xp_1000", "first_permanent", "week_login_7"]
  }
}
```

> `freeze_balance` 新成员默认 2，每月补充 1 个（上限 5）。该接口**只懒结算上周**（bonus XP / freeze / 周徽章），**不发放现金里程碑**——里程碑仅在 [`/stats/weekly-settlement`](#-get-api-v1-stats-weekly-settlement--每周结算含现金激励) 入口发放。

### 🔒 GET /api/v1/stats/weekly-settlement — 每周结算（含现金激励）

打开即懒结算上周 +（`CASH_ENABLED` 时）发放里程碑奖金。返回周报历史 + 虚拟钱包 + 里程碑。
评分公式 / 周现金分档 / 里程碑清单 / 防通胀设计 / `.env` 配置 **详见 [Settlement.md](./Settlement.md)**。

```json
// Response（节选关键字段）
{
  "code": 200,
  "data": {
    "history": [
      {
        "week_key": "2026-W29", "week_start": "2026-07-13", "week_end": "2026-07-19",
        "total_score": 65, "stars": 3,
        "login_score": 35, "new_score": 10, "plan_score": 20,
        "bonus_xp": 22, "freeze_granted": 1,
        "cash_reward": 10.0, "cash_tier_label": "3star",
        "badges_granted": ["week_login_7"], "plan_health": null,
        "settled_at": "2026-07-20T10:00:00"
      }
    ],
    "latest": { "...": "同上" },
    "cash_balance": 60.0,
    "cash_enabled": true,
    "milestones": [
      { "milestone_key": "unit_complete:5", "milestone_type": "unit_complete",
        "threshold": 5, "amount": 50.0,
        "snapshot": { "unit_id": 5, "total_words": 120, "mastered": 120 },
        "granted_at": "2026-07-15T08:00:00" }
    ]
  }
}
```

---

## AI API

### 🔒 POST /api/v1/ai/dialogue — 生成场景对话

```json
// Request
{
  "unit_ids": [1, 2],
  "scenario": "购物"
}
```

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "scenario": "在超市购物",
    "lines": [
      {"role": "teacher", "english": "Good morning! Can I help you?", "chinese": "早上好！需要帮忙吗？"},
      {"role": "student", "english": "Yes, I want to buy some apples.", "chinese": "是的，我想买些苹果。"}
    ]
  }
}
```

### 🔒 POST /api/v1/ai/exercise — 生成 AI 练习题

```json
// Request
{
  "unit_ids": [1],
  "mode": "choice"
}
```

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "mode": "choice",
    "items": [
      {
        "question": "「你好」的英文是？",
        "options": ["hello", "goodbye", "sorry", "thanks"],
        "answer": "hello",
        "explanation": "hello 是最常用的打招呼用语"
      }
    ]
  }
}
```

`mode` 可选值：`choice`（选择题）、`fill`（填空题）。

### 🔒 POST /api/v1/ai/parse-words — 自然语言解析为单词草稿

粘贴任意文本（中英混排），AI 解析出 `英中对译` 草稿条目，供人工确认后批量入库（单人模式下加词入口只读，此接口仅返回草稿，不落库）。

```json
// Request
{
  "text": "apple 苹果，banana 香蕉，How are you 你好吗"
}
```

- `text`：1~10000 字符。
- 解析失败（AI 异常）→ `500 AI 解析失败: ...`。

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "draft_words": [
      { "english": "apple", "chinese": "苹果", "type": "word", "phonetic": null, "pos": null, "example": null },
      { "english": "banana", "chinese": "香蕉", "type": "word", "phonetic": null, "pos": null, "example": null },
      { "english": "How are you", "chinese": "你好吗", "type": "sentence", "phonetic": null, "pos": null, "example": null }
    ],
    "parsed_count": 3
  }
}
```

---

## TTS API（免鉴权）

### GET /api/v1/tts/generate — 文本转语音

Query 参数：`text`（必填，最长 500 字符）、`lang=en|zh`

直接返回 MP3 音频流：

```
GET /api/v1/tts/generate?text=hello&lang=en
Content-Type: audio/mpeg
```

使用 edge-tts（免费），无需 API key。免登录原因见顶部「鉴权」。

---

## Health API（免鉴权）

### GET /api/v1/health — 健康检查

```json
{
  "code": 200,
  "message": "success",
  "data": { "status": "ok" }
}
```
