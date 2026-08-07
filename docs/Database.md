# Database — English Coach

> 表结构以 `backend/app/models/*.py` 与 `backend/alembic/versions/*.py` 为准。下列 `CREATE TABLE` 为当前线上的等价 DDL（含全部迁移至 `019_cash_reward`）。
> 说明：**唯一约束名与索引名均与迁移真实落库一致**（见文末「索引策略」表）。外键名多为迁移未显式命名、由 MySQL 自动生成，DDL 中给出的是便于阅读的逻辑名；唯一在迁移里显式命名的外键是 `wrong_word_book` 的 `fk_wrongbook_member` / `fk_wrongbook_word`。

## ER Diagram

```
┌──────────────┐     ┌──────────┐     ┌────────────────────┐
│   member     │     │   unit   │     │        word        │
│──────────────│     │──────────│     │────────────────────│
│ id (PK)      │     │ id (PK)  │◄────│ id (PK)            │
│ name         │     │ title    │     │ unit_id (FK)──►unit │
│ avatar       │     │ sequence │     │ english / chinese  │
│ total_xp     │     │ created  │     │ type / seq         │
│ cash_balance │     │ updated  │     │ phonetic/def/pos/  │
│ created/upd  │     └──────────┘     │   example          │
└─┬────────────┘                      └─┬────────────────┬─┘
  │                                     │                │
  │              ┌──────────────┐       │                │
  │              │  word_tags   │       │                │
  │              │──────────────│       │                │
  │              │ word_id (FK) │◄──────┘                │
  │              │ tag (ENUM)   │                        │
  │              └──────────────┘                        │
  │                                                      │
  │  ┌────────────────────┐  ┌──────────────────────┐    │
  │  │   mastery_record   │  │  practice_session    │    │
  │  │────────────────────│  │──────────────────────│    │
  │  │ id (PK)            │  │ id (PK)              │    │
  │  │ member_id (FK)     │  │ member_id (FK)       │    │
  │  │ word_id (FK)────────┼──┼► word               │    │
  │  │ level (ENUM)       │  │ mode / total/correct │    │
  │  │ cc / correct/wrong │  │ question_word_ids    │    │
  │  │ SM-2 四字段        │  │ started_at/ended_at  │    │
  │  └────────────────────┘  └─────────┬────────────┘    │
  │                                    │                 │
  │                          ┌──────────────────────┐    │
  │                          │  practice_record     │    │
  │                          │──────────────────────│    │
  │                          │ id (PK)              │    │
  │                          │ session_id (FK)      │    │
  │                          │ word_id (FK)─────────┼────┘
  │                          │ is_correct/user_ans  │
  │                          └──────────────────────┘
  │
  │  ┌────────────────────┐     ┌────────────────────┐
  │  │   learning_plan    │     │     daily_task     │
  │  │────────────────────│     │────────────────────│
  │  │ id (PK)            │     │ id (PK)            │
  │  │ member_id (FK)     │     │ plan_id (FK)       │
  │  │ name / daily_goal  │     │ task_date          │
  │  │ deadline / status  │     │ new/review_count   │
  │  │ learn_weekdays     │     │ completed_new/rev  │
  │  │ monthly_review_day │     │ status / task_type │
  │  │ start_date         │     └────────────────────┘
  │  │ plan_type          │
  │  │ last_rebalanced_at │     ┌────────────────────┐
  │  └──────┬─────────────┘     │   plan_units (M:N) │
  │         └──► plan_units      │ plan_id / unit_id  │
  │                              └────────────────────┘
  │
  │  ┌────────────────────┐  ┌──────────────────┐  ┌────────────────────┐
  └──│  wrong_word_book   │  │  member_streak   │  │   member_badges    │
     │────────────────────│  │──────────────────│  │────────────────────│
     │ id (PK)            │  │ member_id (PK,FK)│  │ id (PK)            │
     │ member_id (FK)     │  │ current/longest  │  │ member_id (FK)     │
     │ word_id (FK)       │  │ freeze_balance   │  │ badge_key          │
     │ added_at           │  │ last_active_date │  │ awarded_at         │
     │ wrong_count        │  │ freeze_grant_mon │  └────────────────────┘
     └────────────────────┘  └──────────────────┘
                                                ┌────────────────────┐
                                                │  weekly_settlement │
                                                │────────────────────│
                                                │ id (PK)            │
                                                │ member_id (FK)     │
                                                │ week_key/start/end │
                                                │ 四维分 / stars     │
                                                │ bonus_xp / freeze  │
                                                │ cash_reward/tier   │
                                                │ badges/plan_health │
                                                └────────────────────┘
                                                ┌────────────────────┐
                                                │   cash_milestone   │
                                                │────────────────────│
                                                │ id (PK)            │
                                                │ member_id (FK)     │
                                                │ milestone_key/type │
                                                │ threshold / amount │
                                                │ snapshot / granted │
                                                └────────────────────┘
```

> **没有 `learning_streak` 表。** 连续学习状态持久化在 `member_streak`（每个 member 一行），不再每次从 PracticeSession 聚合。

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

### practice_mode（12 个，与 `PracticeMode` 枚举一致；`practice_session.mode` 列同序）
| 值 | 说明 |
|---|---|
| `flashcard` | 单词卡（看英翻中） |
| `spelling` | 拼写（中→英） |
| `choice` | 选择题（英→中） |
| `cn2en_choice` | 中→英选择 |
| `en2cn_write` | 英→中默写 |
| `dictation` | 听写 |
| `matching` | 连线配对 |
| `timed_challenge` | 限时挑战 |
| `scramble` | 字母重排 |
| `memory_flash` | 记忆闪卡 |
| `flip_match` | 翻牌配对 |
| `dialogue` | 场景对话 |

### task_type
| 值 | 说明 |
|---|---|
| `learn` | 学习日（学新词 + 滚动复习） |
| `weekly_review` | 周复习任务 |
| `monthly_review` | 月复习任务 |
| `wrong_word_drill` | 错题刷任务（三轮） |

### plan_type
| 值 | 说明 |
|---|---|
| `forward` | 首轮：学新词 |
| `review_only` | 二轮：不学新词，纯滚动复习 |
| `wrong_word_drill` | 三轮：错题优先刷 |

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
  `id`           BIGINT AUTO_INCREMENT PRIMARY KEY,
  `name`         VARCHAR(50)  NOT NULL,
  `avatar`       VARCHAR(255) DEFAULT NULL,
  `total_xp`     INT          NOT NULL DEFAULT 0          COMMENT '累计 XP（答对得分），驱动段位。迁移 015',
  `cash_balance` FLOAT        NOT NULL DEFAULT 0.0        COMMENT '现金激励虚拟钱包（周现金+里程碑奖金）。迁移 019',
  `created_at`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** 用户表（单人）。单人模式恒为一条记录（id=1）。`total_xp`（015）由答对累加驱动段位；`cash_balance`（019）累加周学习现金与里程碑奖金，线下兑现、系统只记账。

---

### 2. unit

```sql
CREATE TABLE `unit` (
  `id`         BIGINT AUTO_INCREMENT PRIMARY KEY,
  `title`      VARCHAR(100) NOT NULL,
  `sequence`   INT          NOT NULL COMMENT '排序序号，对应 Unit 1, 2, ...',
  `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `sequence` (`sequence`)   -- 迁移 001 声明，未显式命名
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** `sequence` 保证唯一排序。历史上的 `image_url` 列已在迁移 012 删除。

---

### 3. word

```sql
CREATE TABLE `word` (
  `id`         BIGINT AUTO_INCREMENT PRIMARY KEY,
  `unit_id`    BIGINT       NOT NULL,
  `english`    VARCHAR(500) NOT NULL COMMENT '英文单词或句子',
  `chinese`    VARCHAR(500) NOT NULL COMMENT '中文释义',
  `type`       ENUM('word', 'sentence') NOT NULL DEFAULT 'word',
  `seq`        INT          DEFAULT NULL COMMENT '单元内印刷序号 NO，可空。迁移 006',
  `phonetic`   VARCHAR(200) DEFAULT NULL COMMENT '裸 IPA 音标（不含包裹斜杠）。迁移 014',
  `definition` VARCHAR(1000) DEFAULT NULL COMMENT '英文释义。迁移 014',
  `pos`        VARCHAR(100) DEFAULT NULL COMMENT '词性。迁移 014',
  `example`    TEXT         DEFAULT NULL COMMENT '例句。迁移 014',
  `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY `ix_word_unit` (`unit_id`),
  CONSTRAINT `fk_word_unit` FOREIGN KEY (`unit_id`) REFERENCES `unit`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** 单词/句子条目，富字段全部 nullable——旧数据与手动录入无需提供；ECDICT 导入（`import_ecdict.py`）与 AI 解析按可用性回填 `phonetic/definition/pos`，`example` 多由 AI 补齐。

> **音标运行时回退（部署关键依赖）：** 前端音标优先读 `word.phonetic`；缺省时由 `app/utils/phonetics.py` 调 `eng_to_ipa` 本地词典实时转换（零网络、有进程内缓存）。**生产部署须 `pip install eng-to-ipa`**，否则库存无音标的词（含 SQL 种子导入的词）将不显示音标（不报错，仅降级）。

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

**说明：** 多对多中间表，联合主键防重复打标。

---

### 5. mastery_record

```sql
CREATE TABLE `mastery_record` (
  `id`                  BIGINT AUTO_INCREMENT PRIMARY KEY,
  `member_id`           BIGINT NOT NULL,
  `word_id`             BIGINT NOT NULL,
  `level`               ENUM('unlearned', 'learning', 'familiar', 'permanent') NOT NULL DEFAULT 'unlearned',
  `consecutive_correct` INT NOT NULL DEFAULT 0 COMMENT '当前连续正确次数，答错重置为0',
  `correct_count`       INT NOT NULL DEFAULT 0,
  `wrong_count`         INT NOT NULL DEFAULT 0,
  -- SM-2 间隔重复字段（迁移 016，由 app/srs.py update_srs 维护）
  `interval_days`       INT NOT NULL DEFAULT 0,
  `ease_factor`         FLOAT NOT NULL DEFAULT 2.5,
  `last_reviewed_at`    DATETIME DEFAULT NULL,
  `next_review_date`    DATE DEFAULT NULL,
  `created_at`          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_member_word_mastery` (`member_id`, `word_id`),  -- 迁移 011（模型声明）
  KEY `ix_mastery_member` (`member_id`),                          -- 迁移 004
  KEY `ix_mastery_word` (`word_id`),                              -- 迁移 004
  KEY `ix_mastery_member_due` (`member_id`, `next_review_date`),  -- 迁移 016（到期查询）
  CONSTRAINT `fk_mastery_member` FOREIGN KEY (`member_id`) REFERENCES `member`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_mastery_word` FOREIGN KEY (`word_id`) REFERENCES `word`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** 每个用户对每个单词只有一条掌握记录（`uk_member_word_mastery`，迁移 011 去重后加）。`level` 不再由计数阈值写入，改由 SM-2 `interval_days` 派生（见 `app/srs.py`）。

> 历史迁移 004 曾在相同列上建过名为 `uk_member_word` 的唯一约束（未显式删除，与 011 的 `uk_member_word_mastery` 并存、同列冗余）；模型与代码引用的canonical 名是 `uk_member_word_mastery`。

**状态升级规则（在 Service 层 / `srs.update_srs` 实现）：**

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
  `id`                 BIGINT AUTO_INCREMENT PRIMARY KEY,
  `member_id`          BIGINT NOT NULL,
  `mode`               ENUM('flashcard','spelling','choice','cn2en_choice','en2cn_write',
                            'dictation','matching','timed_challenge','scramble',
                            'memory_flash','flip_match','dialogue') NOT NULL,
  `total_count`        INT NOT NULL DEFAULT 0,
  `correct_count`      INT NOT NULL DEFAULT 0,
  `question_word_ids`  JSON DEFAULT NULL COMMENT '本次题集 word_id 列表，提交时校验归属防刷分；旧会话 NULL 跳过校验。迁移 010',
  `started_at`         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `ended_at`           DATETIME DEFAULT NULL COMMENT 'NULL=未结束',
  `created_at`         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY `ix_practice_session_member_id` (`member_id`),
  KEY `ix_practice_session_started_at` (`started_at`),
  KEY `ix_practice_member_date` (`member_id`, `started_at`),
  CONSTRAINT `fk_session_member` FOREIGN KEY (`member_id`) REFERENCES `member`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** `mode` ENUM 在迁移 005 扩到全部 12 个值（原 002 只放了 5 个）。`question_word_ids`（010）用于提交时校验 `word_id` 归属本会话。

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
  `updated_at`  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY `ix_practice_record_session_id` (`session_id`),
  KEY `ix_practice_record_word_id` (`word_id`),
  KEY `ix_practice_record_created_at` (`created_at`),   -- 迁移 013：周/月复习选题与首次判定区间扫描
  CONSTRAINT `fk_record_session` FOREIGN KEY (`session_id`) REFERENCES `practice_session`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_record_word` FOREIGN KEY (`word_id`) REFERENCES `word`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

### 8. learning_plan

```sql
CREATE TABLE `learning_plan` (
  `id`                  BIGINT AUTO_INCREMENT PRIMARY KEY,
  `member_id`           BIGINT NOT NULL,
  `name`                VARCHAR(100) NOT NULL,
  `daily_goal`          INT NOT NULL DEFAULT 30,
  `deadline`            DATE DEFAULT NULL,
  `status`              ENUM('active', 'completed', 'paused') NOT NULL DEFAULT 'active',
  `learn_weekdays`      VARCHAR(64) NOT NULL DEFAULT '[0,1,2,3,4]' COMMENT 'JSON 数组 0=Mon..6=Sun。迁移 007',
  `monthly_review_day`  INT DEFAULT NULL COMMENT 'None/1-28/31(月末)；不支持 29/30。迁移 007',
  `start_date`          DATE NOT NULL DEFAULT (CURRENT_DATE) COMMENT '计划生效起始日。迁移 008',
  `plan_type`           ENUM('forward', 'review_only', 'wrong_word_drill') NOT NULL DEFAULT 'forward' COMMENT '迁移 008',
  `last_rebalanced_at`  DATETIME DEFAULT NULL COMMENT '最近一次重新平衡计划时间。迁移 018',
  `created_at`          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY `ix_learning_plan_member_id` (`member_id`),
  KEY `ix_learning_plan_status` (`status`),
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
  KEY `ix_plan_units_unit` (`unit_id`),
  CONSTRAINT `fk_plan_units_plan` FOREIGN KEY (`plan_id`) REFERENCES `learning_plan`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_plan_units_unit` FOREIGN KEY (`unit_id`) REFERENCES `unit`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

### 10. daily_task

```sql
CREATE TABLE `daily_task` (
  `id`               BIGINT AUTO_INCREMENT PRIMARY KEY,
  `plan_id`          BIGINT NOT NULL,
  `task_date`        DATE NOT NULL,
  `new_count`        INT NOT NULL DEFAULT 0,
  `review_count`     INT NOT NULL DEFAULT 0,
  `completed_new`    INT NOT NULL DEFAULT 0,
  `completed_review` INT NOT NULL DEFAULT 0,
  `status`           ENUM('pending', 'in_progress', 'completed', 'skipped') NOT NULL DEFAULT 'pending',
  `task_type`        ENUM('learn', 'weekly_review', 'monthly_review', 'wrong_word_drill') NOT NULL DEFAULT 'learn' COMMENT '迁移 007+008',
  `created_at`       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_plan_date_type` (`plan_id`, `task_date`, `task_type`),  -- 迁移 007：替换原 uk_plan_date
  KEY `ix_daily_task_plan` (`plan_id`),
  KEY `ix_daily_task_type` (`task_type`),
  CONSTRAINT `fk_task_plan` FOREIGN KEY (`plan_id`) REFERENCES `learning_plan`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** 唯一约束在迁移 007 从 `(plan_id, task_date)` 改为 `(plan_id, task_date, task_type)`，使同一天可并存 learn / 周复习 / 月复习任务。

---

### 11. member_streak（替代旧的 learning_streak，迁移 015）

```sql
CREATE TABLE `member_streak` (
  `member_id`         BIGINT NOT NULL,
  `current_streak`    INT NOT NULL DEFAULT 0,
  `longest_streak`    INT NOT NULL DEFAULT 0,
  `freeze_balance`    INT NOT NULL DEFAULT 2 COMMENT '可用冻结数：新成员 2，每月补 1，上限 5',
  `last_active_date`  DATE DEFAULT NULL,
  `freeze_grant_month` VARCHAR(7) DEFAULT NULL COMMENT '上次发放月度 freeze 的月份 YYYY-MM',
  `created_at`        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`member_id`),
  CONSTRAINT `fk_streak_member` FOREIGN KEY (`member_id`) REFERENCES `member`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** 持久化每个成员的连续学习状态（替代每次聚合）。每次 `submit_answer` 且为「今天首次该成员练习」时推进一次；断签时优先消耗 `freeze_balance` 把缺口补上，补不满才重置为 1。`member_id` 用 BigInteger 以匹配 `member.id`（否则 MariaDB errno 150）。

> 旧的 `learning_streak`（按日聚合 `words_learned` / `accuracy` 的表）**已不存在**——那是早期设计，从未在迁移中落地。

---

### 12. member_badges（迁移 015）

```sql
CREATE TABLE `member_badges` (
  `id`         BIGINT AUTO_INCREMENT PRIMARY KEY,
  `member_id`  BIGINT NOT NULL,
  `badge_key`  VARCHAR(50) NOT NULL,
  `awarded_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `uq_member_badge` (`member_id`, `badge_key`),
  CONSTRAINT `fk_badges_member` FOREIGN KEY (`member_id`) REFERENCES `member`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** 徽章发放记录，`(member_id, badge_key)` 唯一保证幂等（streak 阈值 / XP 阈值 / `first_permanent` / 周徽章 `week_login_7` / `week_full_score`）。

---

### 13. wrong_word_book（迁移 009）

```sql
CREATE TABLE `wrong_word_book` (
  `id`          BIGINT NOT NULL AUTO_INCREMENT,
  `member_id`   BIGINT NOT NULL,
  `word_id`     BIGINT NOT NULL,
  `added_at`    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '首次加入时间',
  `wrong_count` INT NOT NULL DEFAULT 1 COMMENT '累计答错次数（已有记录则 +1）',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_member_word_wrongbook` (`member_id`, `word_id`),
  KEY `ix_wrongbook_member` (`member_id`),
  KEY `ix_wrongbook_word` (`word_id`),
  CONSTRAINT `fk_wrongbook_member` FOREIGN KEY (`member_id`) REFERENCES `member`(`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_wrongbook_word` FOREIGN KEY (`word_id`) REFERENCES `word`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** member 维度的全局错题集合（跨所有 Unit）。答错自动 upsert：联合唯一保证同一 `(member, word)` 一条记录，`wrong_count + 1`，`added_at` 保留首次加入时间。答对时刻意不动，仅由用户在错题本页手动移除。练习页可用虚拟 Unit ID `0` 把错题本词加入候选池。

---

### 14. weekly_settlement（迁移 017 + 019）

```sql
CREATE TABLE `weekly_settlement` (
  `id`               BIGINT NOT NULL AUTO_INCREMENT,
  `member_id`        BIGINT NOT NULL,
  `week_key`         VARCHAR(10) NOT NULL COMMENT 'ISO 周号，如 2026-W30',
  `week_start`       DATE NOT NULL,
  `week_end`         DATE NOT NULL,
  `login_score`      INT NOT NULL DEFAULT 0,
  `difficulty_score` INT NOT NULL DEFAULT 0 COMMENT '已停用（四维→三维重构）：新行恒 0，历史行保留旧值',
  `new_score`        INT NOT NULL DEFAULT 0,
  `plan_score`       INT NOT NULL DEFAULT 0,
  `total_score`      INT NOT NULL DEFAULT 0,
  `stars`            INT NOT NULL DEFAULT 0,
  `real_days`        INT NOT NULL DEFAULT 0,
  `new_words_learned` INT NOT NULL DEFAULT 0,
  `plan_completion`  FLOAT NOT NULL DEFAULT 0.0,
  `bonus_xp`         INT NOT NULL DEFAULT 0,
  `freeze_granted`   INT NOT NULL DEFAULT 0,
  `cash_reward`      FLOAT NOT NULL DEFAULT 0.0 COMMENT '本周学习现金。迁移 019',
  `cash_tier_label`  VARCHAR(40) DEFAULT NULL COMMENT '命中档位标签，如 5star_full；未启用/≤2星→NULL。迁移 019',
  `badges_granted`   JSON DEFAULT NULL,
  `plan_health`      JSON DEFAULT NULL,
  `settled_at`       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_at`       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_member_week_settlement` (`member_id`, `week_key`),
  KEY `ix_weekly_settlement_member_id` (`member_id`),
  CONSTRAINT `fk_weekly_member` FOREIGN KEY (`member_id`) REFERENCES `member`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** 每周结算幂等快照（一人一周一行）。`bonus_xp` 与 `cash_reward` 同 savepoint 原子累加进 `member.total_xp` / `member.cash_balance`。评分公式 / 现金分档详见 [Settlement.md](./Settlement.md)。

---

### 15. cash_milestone（迁移 019）

```sql
CREATE TABLE `cash_milestone` (
  `id`             BIGINT NOT NULL AUTO_INCREMENT,
  `member_id`      BIGINT NOT NULL,
  `milestone_key`  VARCHAR(80) NOT NULL COMMENT 'unit_complete:5 / cumulative_words:500 / attendance_streak:8',
  `milestone_type` VARCHAR(40) NOT NULL COMMENT 'unit_complete / cumulative_words / attendance_streak',
  `threshold`      INT NOT NULL DEFAULT 0 COMMENT 'unit_complete 存 unit_id；其余存阈值',
  `amount`         FLOAT NOT NULL DEFAULT 0.0,
  `snapshot`       JSON DEFAULT NULL COMMENT '发放时刻证据（审计），不回扣',
  `granted_at`     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_at`     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_member_milestone_key` (`member_id`, `milestone_key`),
  KEY `ix_cash_milestone_member_id` (`member_id`),
  CONSTRAINT `fk_cash_milestone_member` FOREIGN KEY (`member_id`) REFERENCES `member`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

**说明：** 现金里程碑幂等台账（一人一里程碑一行，达标即发、终身一次）。`snapshot` 语义：发放后词/周回退不回扣（同 `bonus_xp`）。完整规则见 [Settlement.md](./Settlement.md)。

---

## 迁移与阶段

| 迁移 | 内容 |
|---|---|
| 001 | member / unit / word / word_tags / mastery_record |
| 002 | practice_session / practice_record（mode 仅 5 值） |
| 003 | learning_plan / plan_units / daily_task |
| 004 | 补全索引与唯一约束（mastery / word / session / task / plan_units） |
| 005 | `practice_session.mode` ENUM 扩到全部 12 值 |
| 006 | word.seq |
| 007 | daily_task.task_type + learning_plan.learn_weekdays/monthly_review_day；`uk_plan_date`→`uk_plan_date_type` |
| 008 | learning_plan.start_date / plan_type；task_type 追加 `wrong_word_drill` |
| 009 | wrong_word_book |
| 010 | practice_session.question_word_ids |
| 011 | mastery_record 去重 + `uk_member_word_mastery` |
| 012 | 删除 unit.image_url |
| 013 | practice_record.created_at 索引 |
| 014 | word 富字段 phonetic / definition / pos / example |
| 015 | member_streak / member_badges / member.total_xp |
| 016 | mastery_record SM-2 四字段 + `ix_mastery_member_due` |
| 017 | weekly_settlement |
| 018 | learning_plan.last_rebalanced_at |
| 019 | member.cash_balance / weekly_settlement.cash_reward/cash_tier_label / cash_milestone |

> 生产裸跑无自动迁移：合入新 revision 后须手动 `alembic upgrade head`（带 `PYTHONPATH`）。

---

## 索引策略

| 索引 / 约束 | 表 | 目的 | 来源迁移 |
|---|---|---|---|
| `sequence` UNIQUE | unit | 序号唯一 | 001 |
| `ix_word_unit` | word | 按单元查单词 | 004 |
| `PK (word_id, tag)` | word_tags | 按单词查标签，防重复 | 001 |
| `uk_member_word_mastery` UNIQUE | mastery_record | 每人每词一条记录 | 011（004 另有 `uk_member_word` 同列冗余） |
| `ix_mastery_member` / `ix_mastery_word` | mastery_record | 按 member / word 查 | 004 |
| `ix_mastery_member_due` | mastery_record | 到期复习（member, next_review_date） | 016 |
| `ix_practice_session_member_id` / `ix_practice_session_started_at` | practice_session | 按用户 / 时间查历史 | 002 |
| `ix_practice_member_date` | practice_session | 按用户+时间范围聚合（stats） | 004 |
| `ix_practice_record_session_id` / `ix_practice_record_word_id` | practice_record | 按会话 / 单词查明细 | 002 |
| `ix_practice_record_created_at` | practice_record | 周/月复习选题与首次判定区间扫描 | 013 |
| `ix_learning_plan_member_id` / `ix_learning_plan_status` | learning_plan | 按用户 / 状态筛计划 | 003 |
| `PK (plan_id, unit_id)` + `ix_plan_units_unit` | plan_units | 反向按 unit 查计划 | 003 / 004 |
| `uk_plan_date_type` UNIQUE | daily_task | 每计划每天每类型一条任务 | 007（替换 `uk_plan_date`） |
| `ix_daily_task_plan` / `ix_daily_task_type` | daily_task | 按计划范围 / 按类型查 | 004 / 007 |
| `PK member_id` | member_streak | 一人一行 | 015 |
| `uq_member_badge` UNIQUE | member_badges | 幂等发徽章 | 015 |
| `uk_member_word_wrongbook` UNIQUE | wrong_word_book | 一人一词一条错题（upsert） | 009 |
| `ix_wrongbook_member` / `ix_wrongbook_word` | wrong_word_book | 列表分页 / 按 word 删除 / 计数 | 009 |
| `uq_member_week_settlement` UNIQUE + `ix_weekly_settlement_member_id` | weekly_settlement | 一人一周一行 / 按用户查历史 | 017 |
| `uq_member_milestone_key` UNIQUE + `ix_cash_milestone_member_id` | cash_milestone | 幂等发里程碑 / 按用户查 | 019 |
