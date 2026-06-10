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
  "sequence": 1,
  "image_url": "/uploads/unit1.jpg"
}

// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "title": "Unit 1 - Hello!",
    "sequence": 1,
    "image_url": "/uploads/unit1.jpg",
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
    "image_url": "/uploads/unit1.jpg",
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

## OCR API

### POST /api/v1/units/{unit_id}/upload-image — 上传图片并 OCR 解析

Content-Type: `multipart/form-data`

表单字段：`file`（图片文件）

```json
// Response — 返回草稿单词列表（未入库）
{
  "code": 200,
  "message": "success",
  "data": {
    "unit_id": 1,
    "image_url": "/uploads/unit_1.jpg",
    "draft_words": [
      { "english": "hello", "chinese": "你好", "type": "word" },
      { "english": "good morning", "chinese": "早上好", "type": "word" },
      { "english": "How are you?", "chinese": "你好吗？", "type": "sentence" }
    ],
    "parsed_count": 3
  }
}
```

### GET /api/v1/units/{unit_id}/ocr-result — 获取 OCR 草稿结果

```json
// Response
{
  "code": 200,
  "message": "success",
  "data": {
    "unit_id": 1,
    "draft_words": [
      { "english": "hello", "chinese": "你好", "type": "word" }
    ],
    "parsed_count": 1,
    "confirmed": false
  }
}
```

如果没有上传过图片，`draft_words` 为空数组。

### POST /api/v1/units/{unit_id}/confirm-ocr — 确认 OCR 结果并入库

```json
// Request — 用户可编辑草稿后提交
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
    "unit_id": 1,
    "saved_count": 3,
    "words": [
      { "id": 1, "english": "hello", "chinese": "你好", "type": "word", "tags": [] },
      { "id": 2, "english": "good morning", "chinese": "早上好", "type": "word", "tags": [] },
      { "id": 3, "english": "How are you?", "chinese": "你好吗？", "type": "sentence", "tags": [] }
    ]
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

## Health API

### GET /api/v1/health — 健康检查

```json
{
  "code": 200,
  "message": "success",
  "data": { "status": "ok" }
}
```
