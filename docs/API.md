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

## Health API

### GET /api/v1/health — 健康检查

```json
{
  "code": 200,
  "message": "success",
  "data": { "status": "ok" }
}
```
