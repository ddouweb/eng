# API — Family English Coach

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

## Unit API

### POST /api/v1/units — 创建 Unit

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
    "created_at": "2026-06-10T10:00:00",
    "updated_at": "2026-06-10T10:00:00"
  }
}
```

### GET /api/v1/units — Unit 列表

Query 参数：`page=1`, `page_size=20`

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      { "id": 1, "title": "Unit 1", "sequence": 1, "word_count": 15, "created_at": "..." }
    ],
    "total": 5,
    "page": 1,
    "page_size": 20
  }
}
```

### GET /api/v1/units/{id} — Unit 详情（含单词列表）

Query 参数：`page=1`, `page_size=50`（分页查单词）

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "title": "Unit 1 - Hello!",
    "sequence": 1,
    "word_count": 15,
    "words": [
      {
        "id": 1,
        "english": "hello",
        "chinese": "你好",
        "type": "word",
        "tags": ["favorite"],
        "mastery": { "level": "learning", "consecutive_correct": 2 },
        "created_at": "..."
      }
    ],
    "created_at": "...",
    "updated_at": "..."
  }
}
```

### PUT /api/v1/units/{id} — 更新 Unit

```json
// Request
{
  "title": "Unit 1 - Greetings",
  "sequence": 1
}
```

### DELETE /api/v1/units/{id} — 删除 Unit

级联删除关联的 Word、WordTag、MasteryRecord。

---

## Word API

### POST /api/v1/units/{unit_id}/words — 批量添加单词

```json
// Request
{
  "words": [
    { "english": "hello", "chinese": "你好", "type": "word" },
    { "english": "good morning", "chinese": "早上好", "type": "word" },
    { "english": "How are you?", "chinese": "你好吗？", "type": "sentence" }
  ]
}

// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "created_count": 3,
    "words": [
      { "id": 1, "english": "hello", "chinese": "你好", "type": "word", "tags": [], "created_at": "..." },
      { "id": 2, "english": "good morning", "chinese": "早上好", "type": "word", "tags": [], "created_at": "..." },
      { "id": 3, "english": "How are you?", "chinese": "你好吗？", "type": "sentence", "tags": [], "created_at": "..." }
    ]
  }
}
```

### GET /api/v1/units/{unit_id}/words — 单元内单词列表

Query 参数：`page=1`, `page_size=50`, `type=word|sentence`（可选筛选）

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": 1,
        "english": "hello",
        "chinese": "你好",
        "type": "word",
        "tags": ["favorite", "high_freq"],
        "mastery": { "level": "learning", "consecutive_correct": 2, "correct_count": 3, "wrong_count": 1 },
        "created_at": "..."
      }
    ],
    "total": 15,
    "page": 1,
    "page_size": 50
  }
}
```

### PUT /api/v1/words/{id} — 更新单词

```json
// Request
{
  "english": "good evening",
  "chinese": "晚上好",
  "type": "word"
}
```

### DELETE /api/v1/words/{id} — 删除单词

级联删除关联的 WordTag 和 MasteryRecord。

### POST /api/v1/words/{id}/tags — 设置标签

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

### DELETE /api/v1/words/{id}/tags/{tag} — 移除单个标签

```
DELETE /api/v1/words/1/tags/favorite
```

### GET /api/v1/words/{id}/mastery — 查询掌握状态

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

---

## Practice API

### POST /api/v1/practice/start — 开始练习会话

```json
// Request
{
  "member_id": 1,
  "mode": "flashcard",
  "unit_ids": [1, 2],
  "count": 10
}

// Response — 返回会话 ID + 第一批题目
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
        "type": "flashcard"
      }
    ]
  }
}
```

`mode` 可选值：`flashcard`（单词卡）、`spelling`（拼写）、`choice`（选择题）
- flashcard: 返回英文，用户翻转看中文
- spelling: 返回中文，用户输入英文
- choice: 返回英文 + 4 个选项（含正确答案）

### POST /api/v1/practice/{session_id}/submit — 提交单题答案

```json
// Request
{
  "word_id": 5,
  "is_correct": true,
  "user_answer": "hello"
}

// Response — 返回更新后的掌握状态
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
    }
  }
}
```

### POST /api/v1/practice/{session_id}/finish — 结束练习会话

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

### GET /api/v1/practice/{session_id} — 查询会话详情

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

---

## Plan API

### POST /api/v1/plans — 创建学习计划

```json
// Request
{
  "name": "三年级上册",
  "daily_goal": 15,
  "unit_ids": [1, 2],
  "deadline": "2026-07-31"
}

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
    "created_at": "2026-06-10T10:00:00"
  }
}
```

创建时自动根据剩余未掌握单词数、每日目标和截止日期生成 DailyTask 列表。

### GET /api/v1/plans — 查询计划列表

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
      "created_at": "2026-06-10T10:00:00"
    }
  ]
}
```

### GET /api/v1/plans/{plan_id} — 查看计划详情

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
    "tasks": [
      {
        "id": 1,
        "plan_id": 1,
        "task_date": "2026-06-10",
        "new_count": 15,
        "review_count": 4,
        "completed_new": 10,
        "completed_review": 2,
        "status": "in_progress"
      }
    ]
  }
}
```

### PUT /api/v1/plans/{plan_id}/tasks/{task_id} — 更新任务进度

```json
// Request
{
  "completed_new": 10,
  "completed_review": 3
}

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
    "status": "in_progress"
  }
}
```

任务状态自动流转：pending → in_progress（有进度） → completed（新词和复习都达标）。

### POST /api/v1/plans/{plan_id}/pause — 暂停计划

```json
// Response
{
  "code": 200,
  "message": "Plan paused",
  "data": null
}
```

### POST /api/v1/plans/{plan_id}/resume — 恢复计划

```json
// Response
{
  "code": 200,
  "message": "Plan resumed",
  "data": null
}
```

---

## Stats API

### GET /api/v1/stats/overview — 全局统计概览

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

### GET /api/v1/stats/units/{unit_id} — 单元统计

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

### GET /api/v1/stats/trend — 练习趋势

Query 参数：`days=30`（1-365）

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

---

## AI API

### POST /api/v1/ai/dialogue — 生成场景对话

```json
// Request
{
  "unit_ids": [1, 2],
  "scenario": "购物"
}

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

### POST /api/v1/ai/exercise — 生成 AI 练习题

```json
// Request
{
  "unit_ids": [1],
  "mode": "choice"
}

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

---

## TTS API

### GET /api/v1/tts/generate — 文本转语音

Query 参数：`text`（必填，最长 500 字符）、`lang=en|zh`

直接返回 MP3 音频流：

```
GET /api/v1/tts/generate?text=hello&lang=en
Content-Type: audio/mpeg
```

使用 edge-tts（免费），无需 API key。

---

## Health API

### GET /api/v1/health — 健康检查

```json
{
  "code": 200,
  "message": "success",
  "data": { "status": "ok" }
}
```
