# 前端设计契约（Design Contract）

> 这是一把"尺子"，不是风格指南。目的是把"好看/好用"从主观感觉，变成**可数、可复核、换人判断也一样**的硬规则。每次改 UI，先用第 1–7 条核一遍。

适用范围：`frontend-vue/`（Vue3 + Naive UI + ECharts）。单人模式，用户量极小，**不靠埋点/A/B 做判定**，靠本契约的量化规则 + 真实目测。

---

## 一、七大可量化规则（改 UI 前先核这张表）

| # | 规则 | 量化判据 | 怎么查 | 参考实现 |
|---|---|---|---|---|
| 1 | **主任务一屏可达** | 每页主任务在 ≤1 屏（fold count ≤ 1）内触达 | 滚动屏数；关键操作首屏可见 | Dashboard |
| 2 | **远程表可排序** | 远程分页的表格都能按其自然维度排序；关键列在最前 | 有 `remote` 的 `NDataTable` 是否带 `sorter` + 服务端 `sort_by/order` | `WrongBookView` |
| 3 | **统计字号全站统一** | 所有 `NStatistic` 数字用同一字号 token，**无 per-page 写死大号** | grep：用 `NStatistic` 的页是否 `:theme-overrides="STAT_THEME_OVERRIDES"` | `StatsView`/`ProgressView` |
| 4 | **间距走刻度、图表有上限** | 间距取自 8pt 刻度 token；section 间距定值；图表高度取自 `CHART_HEIGHT` 档位（上限 240px，除非该页主体就是大图） | grep `height="数字px"` 是否硬编码；间距是否用 `var(--*)` | `tokens.css` / `constants/ui.ts` |
| 5 | **异步视图三态齐全** | 每个异步数据视图具备 loading / empty / error-retry 三态 | 看每块数据是否有 `NSpin` + `NEmpty` + `NResult(重试)` | `StatsView`/`ProgressView` |
| 6 | **可读可点** | 文本对比度 ≥ 4.5:1（WCAG AA）；可点目标 ≥ 36px | 用 `--text-secondary` 等已校准 token，勿用 #999/#ccc | `tokens.css` |
| 7 | **同一数据跨页一致** | 同一数据在任何页都同一渲染（掌握度配色、统计字号、日期格式） | 掌握度必须用 `var(--mastery-*)` / `MASTERY_META` | `constants/mastery.ts` |

> 判定方式：**不问"我觉得这页太长吗"，问"它违反第几条"**。规则当裁判，人只当发现者。

---

## 二、背后的 UX 定律（为什么是这几条）

| 规则 | 定律 | 含义 |
|---|---|---|
| 1 紧致 | Aesthetic & Minimalist（Nielsen）、信噪比、Gestalt 接近性 | 只留任务相关信息；留白服务于分组，不是空旷 |
| 2 排序 | Hick's Law、Recognition over recall | 让用户"认"而非"扫全表找" |
| 3/4 一致 | Jakob's Law、Consistency & Standards | 用户预期来自其它页面/其它站点 |
| 5 三态 | Error Recovery、Doherty Threshold（<400ms 像瞬时）、Visibility of system status | 任何异常路径都要有恢复入口；状态要可见 |
| 交互位置 | Fitts's Law（耗时 ∝ 距离 / 反比大小）、User Control & Freedom | 高频操作又大又近当前视线（如"再来一轮"放答题回顾前） |

---

## 三、令牌（Token）参考

> 改这里 = 改全站。**禁止在单页写死字号/图表高度/section 间距。**

### CSS 令牌 —— `frontend-vue/src/styles/tokens.css`（`:root`）
- `--mastery-unlearned/learning/familiar/permanent`：掌握度四色（必须统一用这套）
- `--text-primary` / `--text-secondary`：文本色（已过 WCAG AA）
- `--section-margin`（`12px 0 4px`）：区块标题外边距
- `--section-title-size`（`15px`）：区块标题字号
- `--card-gap`（`8px`）/ `--card-min`（`140px`）：卡片网格间距与最小列宽
- `--tap-min`（`36px`）：可点目标最小尺寸

### JS 令牌 —— `frontend-vue/src/constants/ui.ts`
- `STAT_THEME_OVERRIDES`：`NStatistic` 数字/标签字号（经 `NConfigProvider :theme-overrides` 应用，一处覆盖整页）
- `CHART_HEIGHT = { sm: 170px, md: 200px, lg: 220px, xl: 240px }`：EChart 高度档位，所有 `:height` 取自此

### 复用范式
- 缩小统计数字：`<NConfigProvider :theme-overrides="STAT_THEME_OVERRIDES">` 包裹整页
- 远程表排序：`sorter: true` + 受控 `sortOrder` + `@update:sorter` 回源（见 `WrongBookView`）
- 紧凑分布 chip 行：`.dist` / `.dist-chip`（见 `StatsView` / `PracticeSummary`）

---

## 四、改 UI 时的流程

1. 改之前：先想这次动的是第几条规则。
2. 改之中：字号/高度/间距一律用令牌；不新增第四套间距/字号。
3. 改之后：用第 1–7 条自查；同类页面一起改（见 `proactive-ui-extrapolation` 记忆）。
4. 拿不准：以"是否违反上述可量化规则"为准，而非个人审美。
