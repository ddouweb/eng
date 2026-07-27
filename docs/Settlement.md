# Settlement — 每周结算与现金激励

家庭英语学习系统的奖励结算机制。两套并行激励：

- **XP（虚拟经验）**：答对逐题得 XP（含难度系数）+ 每周结算发 bonus XP。
- **现金（真实激励，`CASH_ENABLED` 开启后）**：周学习现金 + 里程碑奖金，累计进虚拟钱包，线下兑现。

> 单人模式（member_id=1）；全流程懒触发（无 cron），打开结算页即结算上周并发放到期奖励。

---

## 1. 总览

### 懒触发
用户打开 `/weekly-settlement`（或首页 profile 卡片）时，后端 `StatsService`：

1. `_maybe_settle_week`：回算最近 `SETTLE_BACKFILL_WEEKS = 4` 个**已完整结束且未结算**的 ISO 周，每周一张快照落 `weekly_settlement`；
2. （`CASH_ENABLED` 时）`_maybe_grant_milestones`：检测三类里程碑，幂等发放到 `cash_milestone`。

### 幂等
- 周：`weekly_settlement` 表 `UNIQUE(member_id, week_key)` —— 一人一周一行，重复结算安全跳过。
- 里程碑：`cash_milestone` 表 `UNIQUE(member_id, milestone_key)` —— 每个里程碑终身一次。
- 写入均在 `begin_nested()` savepoint 内，命中唯一约束即整体回滚、下次自愈。

### snapshot 语义
结算/发放时的数据原样落快照，**不保证与并发 rejudge 强一致**；发放后词/周回退**不回扣**（同 `bonus_xp`）。详见 §6。

---

## 2. 四维评分公式（满分 100）

每周由 `settlement_score.py` 的纯函数算出四维：

| 维度 | 满分 | 公式 | 数据源（`stats_repo`） |
|---|---|---|---|
| 坚持分 login | 25 | `round(25 * clamp(active_days / expected_days, 0, 1))` | `get_week_active_days` |
| 难度分 | 25 | `round(25 * clamp((hard/correct) / 0.6, 0, 1))`，correct≤0→0 | `get_week_correct_breakdown`（hard=wrong≥2 且 ease<2.3） |
| 新词分 | 20 | `round(20 * clamp(new_words / target, 0, 1))`，target=daily_goal×expected_days | `get_week_new_word_count` |
| 计划分 | 30 | `round(30 * clamp(completed/planned, 0, 1))`，planned≤0→0 | `get_week_task_stats`（仅 forward 计划） |

- `total = login + difficulty + new + plan`
- `stars = round(total / 20)`，clamp[0, 5]（银行家舍入：50 分 → 2 星）
- `expected_days`：本周 [ws,we] 内落在 `learn_weekdays` 的学习日数；无活跃 plan 时回退 5。

---

## 3. XP 奖励

- **逐题 XP**：答对得 `round((新词 5 / 复习 2) × difficulty_mult)`，难度系数 ∈ [0.5, 2.0]（见 `gamification.difficulty_mult`）。
- **bonus XP**（周结算）：`compute_bonus(login, plan)` = `round((login+plan)/55 × 30)`，封顶 30/周，<5 → 0。
  - **仅坚持+计划两维**派生——逐题 XP 已付难度/新词，刻意不重叠（防通胀根本）。

---

## 4. 周学习现金（CASH_ENABLED 开启后）

`compute_weekly_cash(stars, plan_completion)` 分档制（`app/cash.py` `WEEKLY_CASH_TIERS`，顺序敏感：更严的档在前）：

| stars | plan_completion | 金额 | tier_label |
|---|---|---|---|
| 5 | ≥ 100% | ¥50 | `5star_full` |
| 5 | 任意 | ¥40 | `5star` |
| 4 | ≥ 100% | ¥30 | `4star_full` |
| 4 | 任意 | ¥20 | `4star` |
| 3 | 任意 | ¥10 | `3star` |
| ≤ 2 | — | ¥0 | `null` |

- 封顶 `CASH_WEEKLY_CAP = 50` 元/周（双保险 clamp）。
- 与 bonus XP **独立**（阶跃分档 vs 线性比例），不回收 bonus 数值。
- 与 bonus XP **同 savepoint 原子**累加进 `member.cash_balance`。

> `plan_completion` 是浮点，`>= 1.0` 边界敏感：0.99 落普通档，1.0 落 `_full` 档。

---

## 5. 里程碑奖金（CASH_ENABLED 开启后）

`build_milestone_candidates()`（纯函数，`app/cash.py`）按当下状态生成全部「已达成」候选，`StatsService._maybe_grant_milestones` 幂等发放。三类：

### 5.1 unit_complete —— 背完一个 Unit
- 触发：该 unit 所有词 `level ∈ {familiar, permanent}`（`mastered == total_words` 且 `total > 0`）
- key：`unit_complete:{unit_id}`
- 金额按词数分档（`unit_complete_amount`）：

| Unit 词数 | 金额 |
|---|---|
| ≥ 200 | ¥100 |
| 100 ~ 199 | ¥50 |
| < 100 | ¥30 |

### 5.2 cumulative_words —— 累计掌握词数
- 触发：全局 `mastered_total`（familiar+permanent）≥ 阈值
- key：`cumulative_words:{threshold}`

| 阈值（词） | 金额 |
|---|---|
| 100 | ¥10 |
| 500 | ¥20 |
| 1000 | ¥50 |
| 2000 | ¥100 |

### 5.3 attendance_streak —— 连续全勤周
- 触发：连续 `real_days >= 7` 的已结算周数 ≥ 阈值（`get_full_attendance_week_streak`，从最近一周往回数，遇首个非全勤即停）
- key：`attendance_streak:{threshold}`

| 阈值（周） | 金额 |
|---|---|
| 4 | ¥20 |
| 8 | ¥50 |
| 12 | ¥100 |

> 金额全部 `.env` 可调（见 §8）。各类 milestone_key 不同，可同周并发（如背完某 Unit 同时让累计词数跨阈值，两条都发——奖励不同的离散成就）。

---

## 6. 防通胀设计

1. **不重复支付**：周现金奖「每周质量」（星+完成度）、里程碑奖「离散成就」（首达）——奖励不同维度。
2. **snapshot 不回扣**：里程碑发放后，词因 rejudge `correct→wrong` 回退或掌握度衰减，**不回收** milestone 行、不扣 `cash_balance`；`uq_member_milestone_key` 也防重发。
3. **开关切换的非对称（重要）**：
   - 历史**已结算周**：`CASH_ENABLED` false→true 后**不补发**周现金（snapshot；只对未来周生效）。
   - 历史**里程碑**：首次开启后打开页面，会**一次性发放**所有当下已达成的里程碑（里程碑 = 「首达」非「持续」；`snapshot` 记发放时刻）。
   - 两者语义相反，FAQ 详述。
4. **浮点精度**：所有金额 `round(_, 2)`；`cash_balance` 每次累加后 `round(_, 2)`。用 Float（非 Decimal，与现有列一致）。
5. **并发竞态**：每周/每里程碑独立 savepoint，`IntegrityError` → 回滚跳过、下次自愈。
6. **懒回算局限**：连续全勤周仅基于**已落表行**；超 `SETTLE_BACKFILL_WEEKS=4` 周未打开的旧周不入表 → 不计入（与现有 streak/bonus 同局限）。

---

## 7. 数据模型

### `member` 新增列
| 列 | 类型 | 含义 |
|---|---|---|
| `cash_balance` | FLOAT NOT NULL default 0.0 | 虚拟钱包累计额（周现金 + 里程碑奖金） |

### `weekly_settlement` 新增列
| 列 | 类型 | 含义 |
|---|---|---|
| `cash_reward` | FLOAT NOT NULL default 0.0 | 本周学习现金 |
| `cash_tier_label` | VARCHAR(40) NULL | 命中档位标签（如 `5star_full`）；未启用/≤2星 → NULL |

### `cash_milestone` 新表
| 列 | 类型 | 含义 |
|---|---|---|
| `id` | BIGINT PK | |
| `member_id` | BIGINT FK→member(id) CASCADE | |
| `milestone_key` | VARCHAR(80) | `unit_complete:5` / `cumulative_words:500` / `attendance_streak:8` |
| `milestone_type` | VARCHAR(40) | `unit_complete` / `cumulative_words` / `attendance_streak` |
| `threshold` | INT | unit_complete 存 unit_id；其余存阈值 |
| `amount` | FLOAT | 发放金额 |
| `snapshot` | JSON NULL | 发放时刻证据（审计，如 `{unit_id,total_words,mastered}`） |
| `granted_at` | DATETIME | 发放时刻 |
| `created_at` / `updated_at` | DATETIME | TimestampMixin |

约束：`UNIQUE(member_id, milestone_key)` = `uq_member_milestone_key`；索引 `ix_cash_milestone_member_id`。

迁移：`019_cash_reward`（`down_revision = 018_plan_rebalanced`）。`id`/`member_id` 用 `BigInteger` 匹配 `member.id`（bigint），否则 MariaDB errno 150。

---

## 8. `.env` 配置

| 配置项 | 默认 | 含义 |
|---|---|---|
| `CASH_ENABLED` | `false` | **总开关**：false 完全不发钱；true 启用两层现金 |
| `CASH_CURRENCY` | `CNY` | 展示符号 |
| `CASH_WEEKLY_CAP` | `50.0` | 周现金硬上限 |
| `CASH_TIER_5_FULL` / `CASH_TIER_5` / `CASH_TIER_4_FULL` / `CASH_TIER_4` / `CASH_TIER_3` | 50/40/30/20/10 | 周现金分档金额 |
| `CASH_MS_UNIT_BIG` / `_MID` / `_SMALL` | 100/50/30 | 背完 Unit 金额（≥200/100~199/<100 词） |
| `CASH_MS_WORDS_100` / `_500` / `_1000` / `_2000` | 10/20/50/100 | 累计词数里程碑金额 |
| `CASH_MS_STREAK_4` / `_8` / `_12` | 20/50/100 | 连续全勤周里程碑金额 |

改 `.env` 后需重启后端（启动期读一次）。

---

## 9. API

### `GET /api/v1/stats/weekly-settlement`

打开即懒结算上周 +（开启时）发放里程碑。返回周报历史 + 钱包 + 里程碑。

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "history": [
      {
        "week_key": "2026-W29",
        "week_start": "2026-07-13",
        "week_end": "2026-07-19",
        "login_score": 25, "difficulty_score": 12, "new_score": 1,
        "plan_score": 30, "total_score": 68, "stars": 3,
        "real_days": 7, "new_words_learned": 5, "plan_completion": 1.0,
        "bonus_xp": 30, "freeze_granted": 1,
        "cash_reward": 10.0, "cash_tier_label": "3star",
        "badges_granted": ["week_login_7"],
        "plan_health": null,
        "settled_at": "2026-07-20T10:00:00"
      }
    ],
    "latest": { "...": "同上" },
    "cash_balance": 60.0,
    "cash_enabled": true,
    "milestones": [
      {
        "milestone_key": "unit_complete:5",
        "milestone_type": "unit_complete",
        "threshold": 5,
        "amount": 50.0,
        "snapshot": { "unit_id": 5, "total_words": 120, "mastered": 120 },
        "granted_at": "2026-07-15T08:00:00"
      }
    ]
  }
}
```

---

## 10. 时序

```
打开 /weekly-settlement
        │
        ▼
StatsService.get_weekly_settlement(member_id)
        │
        ├─ _maybe_settle_week ─── 回算近 4 周（升序）
        │       └─ 每周 _settle_one_week:
        │            savepoint { row + bonus_xp→total_xp + cash_reward→cash_balance + freeze + 徽章 }
        │            命中 uq_member_week_settlement → 回滚跳过（自愈）
        │       └─ 末尾 commit
        │
        ├─ if CASH_ENABLED:
        │     _maybe_grant_milestones ── 三类候选
        │       └─ 每候选: SELECT 预过滤 → savepoint { milestone 行 + amount→cash_balance }
        │                  命中 uq_member_milestone_key → 回滚跳过（自愈）
        │       └─ granted_any 时 commit
        │
        ▼
返回 { history, latest, cash_balance, cash_enabled, milestones }
```

---

## 11. FAQ / 边界

**Q：开启现金后，上周我 5 星满分，怎么没现金？**
A：该周在开启前已结算（snapshot）。周现金**不补发**历史已结算周，只对未来周生效。下周起进入现金周期。

**Q：我在现金功能上线前就背完了 Unit 5，上线后能拿到钱吗？**
A：能。里程碑 = 「首达」非「持续」——首次开启后打开页面时，一次性发放所有当下已达成的历史里程碑（`snapshot` 记发放时刻，非达成时刻）。

**Q：发放后某词被改判 correct→wrong，Unit 不再「全背完」，要扣回吗？**
A：不扣。snapshot 语义：发放即定局，不回扣（同 `bonus_xp`）。里程碑判定是「曾经达到」。

**Q：连续全勤周数为什么比我实际全勤的周少？**
A：里程碑的连续全勤周**仅基于已 settlement 落表的行**。懒结算只回算最近 4 周——若某段历史周长期没打开页面、未触发结算，则不入表、不计入。打开页面会补结算最近 4 周。

**Q：浮点会不会越累越偏？**
A：每次累加都 `round(_, 2)`；Float64 尾数 52 位，家庭级金额（百元量级）终身累积无精度问题。

**Q：怎么关掉现金？**
A：`.env` 设 `CASH_ENABLED=false` 重启。已发放的 `cash_balance` / 里程碑行保留（历史记录），不再新增。

**Q：单人模式能多人对比吗？**
A：不能。member_id 恒为 1，无排行榜/多人对比（业务约束）。
