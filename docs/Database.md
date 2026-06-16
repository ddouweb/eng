# Database — Family English Coach

## ER Diagram

```
┌──────────┐       ┌──────────┐       ┌──────────┐
│  Member  │       │   Unit   │       │   Word   │
│──────────│       │──────────│       │──────────│
│ id  (PK) │       │ id  (PK) │◄──────│ id  (PK) │
│ name     │       │ title    │       │ unit_id  │──►┐
│ avatar   │       │ sequence │       │ english  │   │
│ created  │       │ created  │       │ chinese  │   │
└────┬─────┘       │ updated  │       │ type     │   │
     │             └──────────┘       │ created  │   │
     │                                └────┬─────┘   │
     │                                     │         │
     │              ┌──────────────┐       │         │
     │              │  word_tags   │       │         │
     │              │──────────────│       │         │
     │              │ word_id (FK) │◄──────┘         │
     │              │ tag (ENUM)   │                 │
     │              └──────────────┘                 │
     │                                              │
     │  ┌──────────────┐     ┌────────────────┐     │
     │  │MasteryRecord │     │PracticeSession │     │
     │  │──────────────│     │────────────────│     │
     │  │ id  (PK)     │     │ id  (PK)       │     │
     │  │ member_id(FK)│◄───►│ member_id (FK) │     │
     │  │ word_id (FK) │     │ mode           │     │
     │  │ level (ENUM) │     │ total_count    │     │
     │  │ updated      │     │ correct_count  │     │
     │  └──────────────┘     │ started_at     │     │
     │                       │ ended_at       │     │
     │                       └───────┬────────┘     │
     │                               │              │
     │                       ┌────────────────┐     │
     │                       │PracticeRecord  │     │
     │                       │────────────────│     │
     │                       │ id  (PK)       │     │
     │                       │ session_id(FK) │     │
     │                       │ word_id  (FK)  │◄────┘
     │                       │ is_correct     │
     │                       │ user_answer    │
     │                       │ created        │
     │                       └────────────────┘
     │
     │  ┌──────────────┐     ┌──────────────┐
     │  │LearningPlan  │     │  DailyTask   │
     │  │──────────────│     │──────────────│
     │  │ id  (PK)     │     │ id  (PK)     │
     │  │ member_id(FK)│     │ plan_id (FK) │
     │  │ name         │     │ task_date    │
     │  │ daily_goal   │     │ new_count    │
     │  │ deadline     │     │ review_count │
     │  │ status       │     │ completed    │
     │  │ created      │     │ status       │
     │  └──────┬───────┘     └──────────────┘
     │         │
     │         └──► plan_units (M:N 中间表)
     │               plan_id (FK)
     │               unit_id (FK)
     │
     │  ┌──────────────────┐
     └──│  LearningStreak  │
        │──────────────────│
        │ id  (PK)         │
        │ member_id (FK)   │
        │ streak_date      │
        │ words_learned    │
        │ accuracy         │
        └──────────────────┘
```

## ENUM 定义

### word_type
| 值 | 说明 |
|---|---|
| `word` | 单词 |
| `sentence` | 句子 |

### tag_type
| 值 | 说明 | 权重倍率 |
|---|---|---|
| `favorite` | ⭐ 收藏 | 1.2 |
| `high_freq` | 🔥 高频 | 1.5 |
| `exam_focus` | 📚 考试重点 | 1.5 |
| `excluded` | ❌ 不再练习 | 0.0 |
| `memorized` | ✅ 已记忆 | 0.3 |

### mastery_level
| 值 | 说明 | 颜色 | 出题权重 |
|---|---|---|---|
| `unlearned` | 未学习 | Gray `#9CA3AF` | 1.5 |
| `learning` | 学习中 | Orange `#F97316` | 1.3 |
| `familiar` | 熟悉 | Blue `#3B82F6` | 1.0 |
| `permanent` | 永久记忆 | Green `#22C55E` | 0.1 |

### practice_mode
| 值 | 说明 |
|---|---|
| `flashcard` | 单词卡 |
| `spelling` | 拼写练习 |
| `choice` | 选择题 |
| `dictation` | 听写 (P1) |
| `dialogue` | 场景对话 (P1) |

### plan_status
| 值 | 说明 |
|---|---|
| `active` | 进行中 |
| `completed` | 已完成 |
| `paused` | 已暂停 |

### task_status
| 值 | 说明 |
|---|---|
| `pending` | 未开始 |
| `in_progress` | 进行中 |
| `completed` | 已完成 |
| `skipped` | 已跳过 |

---

## Table Definitions

### 1. member

```sql
CREATE TABLE `member` (
  `id`         BIGINT AUTO_INCREMENT PRIMARY KEY,
  `name`       VARCHAR(50)  NOT NULL,
  `avatar`     VARCHAR(255) DEFAULT NULL,
  `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** 家庭成员表。MVP 阶段可只建一条记录，但预留多用户扩展能力。使用 `member` 避免 MySQL 保留字冲突。

---

### 2. unit

```sql
CREATE TABLE `unit` (
  `id`         BIGINT AUTO_INCREMENT PRIMARY KEY,
  `title`      VARCHAR(100) NOT NULL,
  `sequence`   INT          NOT NULL DEFAULT 0 COMMENT '排序序号，对应 Unit 1, 2, ...',
  `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_sequence` (`sequence`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** `sequence` 保证唯一排序；一个 Unit 对应一组关联的单词。

---

### 3. word

```sql
CREATE TABLE `word` (
  `id`         BIGINT AUTO_INCREMENT PRIMARY KEY,
  `unit_id`    BIGINT       NOT NULL,
  `english`    VARCHAR(500) NOT NULL COMMENT '英文单词或句子',
  `chinese`    VARCHAR(500) NOT NULL COMMENT '中文释义',
  `type`       ENUM('word', 'sentence') NOT NULL DEFAULT 'word' COMMENT 'word=单词, sentence=句子',
  `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY `ix_word_unit_id` (`unit_id`),
  CONSTRAINT `fk_word_unit` FOREIGN KEY (`unit_id`) REFERENCES `unit`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** 单词/句子条目。`type` 区分单词和句子，两者共用同一张表，练习时可按类型筛选。

---

### 4. word_tags

```sql
CREATE TABLE `word_tags` (
  `word_id` BIGINT NOT NULL,
  `tag`     ENUM('favorite', 'high_freq', 'exam_focus', 'excluded', 'memorized') NOT NULL,
  PRIMARY KEY (`word_id`, `tag`),
  CONSTRAINT `fk_word_tags_word` FOREIGN KEY (`word_id`) REFERENCES `word`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** 多对多中间表，一个单词可以有多个标签。联合主键防止重复打标。

---

### 5. mastery_record

```sql
CREATE TABLE `mastery_record` (
  `id`                  BIGINT AUTO_INCREMENT PRIMARY KEY,
  `member_id`           BIGINT NOT NULL,
  `word_id`             BIGINT NOT NULL,
  `level`               ENUM('unlearned', 'learning', 'familiar', 'permanent') NOT NULL DEFAULT 'unlearned',
  `consecutive_correct` INT NOT NULL DEFAULT 0 COMMENT '当前连续正确次数，答错重置为0',
  `correct_count`       INT NOT NULL DEFAULT 0 COMMENT '累计正确次数',
  `wrong_count`         INT NOT NULL DEFAULT 0 COMMENT '累计错误次数',
  `updated_at`          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_member_word` (`member_id`, `word_id`),
  KEY `ix_mastery_member_level` (`member_id`, `level`),
  CONSTRAINT `fk_mastery_member` FOREIGN KEY (`member_id`) REFERENCES `member`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_mastery_word` FOREIGN KEY (`word_id`) REFERENCES `word`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** 每个用户对每个单词只有一条掌握记录。`consecutive_correct` 用于跟踪连续正确次数，支持状态升级规则中的"连续正确 N 次"判断，无需回查历史记录。

**状态升级规则（在 Service 层实现）：**

| 当前状态 | 升级条件 | 目标状态 |
|---|---|---|
| unlearned | 首次练习 | learning |
| learning | 连续正确 3 次 | familiar |
| familiar | 连续正确 5 次（累计正确 ≥ 8） | permanent |
| familiar | 答错 | 回退到 learning |
| permanent | 答错 2 次以上 | 回退到 familiar |

---

### 6. practice_session

```sql
CREATE TABLE `practice_session` (
  `id`             BIGINT AUTO_INCREMENT PRIMARY KEY,
  `member_id`      BIGINT NOT NULL,
  `mode`           ENUM('flashcard', 'spelling', 'choice', 'dictation', 'dialogue') NOT NULL,
  `total_count`    INT NOT NULL DEFAULT 0 COMMENT '本次练习题目数',
  `correct_count`  INT NOT NULL DEFAULT 0 COMMENT '本次正确数',
  `started_at`     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `ended_at`       DATETIME DEFAULT NULL COMMENT 'NULL=未结束',
  KEY `ix_session_member` (`member_id`),
  KEY `ix_session_started` (`started_at`),
  CONSTRAINT `fk_session_member` FOREIGN KEY (`member_id`) REFERENCES `member`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** 一次练习会话，包含模式、开始/结束时间、总题数和正确数。

---

### 7. practice_record

```sql
CREATE TABLE `practice_record` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `session_id`  BIGINT NOT NULL,
  `word_id`     BIGINT NOT NULL,
  `is_correct`  TINYINT(1) NOT NULL COMMENT '1=正确, 0=错误',
  `user_answer` VARCHAR(500) DEFAULT NULL COMMENT '用户作答内容',
  `created_at`  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY `ix_record_session` (`session_id`),
  KEY `ix_record_word` (`word_id`),
  CONSTRAINT `fk_record_session` FOREIGN KEY (`session_id`) REFERENCES `practice_session`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_record_word` FOREIGN KEY (`word_id`) REFERENCES `word`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** 每一道题的作答记录。`user_answer` 保存用户的实际输入（拼写题的文本、选择题的选项等）。

---

### 8. learning_plan

```sql
CREATE TABLE `learning_plan` (
  `id`         BIGINT AUTO_INCREMENT PRIMARY KEY,
  `member_id`  BIGINT NOT NULL,
  `name`       VARCHAR(100) NOT NULL COMMENT '计划名称，如"三年级上册"',
  `daily_goal` INT NOT NULL DEFAULT 30 COMMENT '每日目标单词数',
  `deadline`   DATE DEFAULT NULL COMMENT '截止日期',
  `status`     ENUM('active', 'completed', 'paused') NOT NULL DEFAULT 'active',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY `ix_plan_member` (`member_id`),
  KEY `ix_plan_status` (`status`),
  CONSTRAINT `fk_plan_member` FOREIGN KEY (`member_id`) REFERENCES `member`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

### 9. plan_units

```sql
CREATE TABLE `plan_units` (
  `plan_id` BIGINT NOT NULL,
  `unit_id` BIGINT NOT NULL,
  PRIMARY KEY (`plan_id`, `unit_id`),
  CONSTRAINT `fk_plan_units_plan` FOREIGN KEY (`plan_id`) REFERENCES `learning_plan`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_plan_units_unit` FOREIGN KEY (`unit_id`) REFERENCES `unit`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** 计划与单元的多对多关系，一个计划可以包含多个 Unit。

---

### 10. daily_task

```sql
CREATE TABLE `daily_task` (
  `id`             BIGINT AUTO_INCREMENT PRIMARY KEY,
  `plan_id`        BIGINT NOT NULL,
  `task_date`      DATE NOT NULL COMMENT '任务日期',
  `new_count`      INT NOT NULL DEFAULT 0 COMMENT '新词数量',
  `review_count`   INT NOT NULL DEFAULT 0 COMMENT '复习数量',
  `completed_new`  INT NOT NULL DEFAULT 0 COMMENT '已完成新词数',
  `completed_review` INT NOT NULL DEFAULT 0 COMMENT '已完成复习数',
  `status`         ENUM('pending', 'in_progress', 'completed', 'skipped') NOT NULL DEFAULT 'pending',
  `created_at`     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_plan_date` (`plan_id`, `task_date`),
  CONSTRAINT `fk_task_plan` FOREIGN KEY (`plan_id`) REFERENCES `learning_plan`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

### 11. learning_streak

```sql
CREATE TABLE `learning_streak` (
  `id`             BIGINT AUTO_INCREMENT PRIMARY KEY,
  `member_id`      BIGINT NOT NULL,
  `streak_date`    DATE NOT NULL COMMENT '学习日期',
  `words_learned`  INT NOT NULL DEFAULT 0 COMMENT '当日学习单词数',
  `accuracy`       DECIMAL(5,2) DEFAULT NULL COMMENT '当日正确率 0.00~100.00',
  `created_at`     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_member_date` (`member_id`, `streak_date`),
  CONSTRAINT `fk_streak_member` FOREIGN KEY (`member_id`) REFERENCES `member`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** 每日学习汇总，用于统计连续学习天数和趋势图。由 PracticeSession 结束时自动更新。

---

## MVP 范围表

Phase 1（当前）实现：`member`, `unit`, `word`, `word_tags`, `mastery_record`

Phase 3 实现：`practice_session`, `practice_record`

Phase 5 实现：`learning_plan`, `plan_units`, `daily_task`

Phase 6 实现：`learning_streak`

---

## 索引策略

| 索引 | 表 | 目的 |
|---|---|---|
| `uk_sequence` | unit | 保证单元序号唯一 |
| `ix_word_unit_id` | word | 按单元查询单词列表 |
| `PK (word_id, tag)` | word_tags | 按单词查标签，防重复 |
| `uk_member_word` | mastery_record | 每人每词一条记录 |
| `ix_mastery_member_level` | mastery_record | 按掌握状态筛选（统计用） |
| `ix_session_member` | practice_session | 按用户查练习历史 |
| `ix_session_started` | practice_session | 按时间查练习记录 |
| `ix_record_session` | practice_record | 按会话查答题明细 |
| `ix_record_word` | practice_record | 按单词查被练习历史 |
| `uk_plan_date` | daily_task | 每个计划每天只有一条任务 |
| `uk_member_date` | learning_streak | 每人每天一条汇总 |
