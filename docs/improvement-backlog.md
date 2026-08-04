# 持续改进待办清单（Improvement Backlog）

> 来源：2026-07-31 系统全面审计（4 维度并行扫描 → 逐条对抗式验证 → 汇总分档）。32 条原始发现 → **28 条验证为真** → 去重合并为 23 项。
>
> **健康度总评**：核心闭环完整、后端设计用心（服务端复判 / 幂等尝试 / SRS / 游戏化 / 四维结算），没有火灾；但有两条系统性主线要消化的——
> - **并发/原子性缺口**：非加锁的 check-then-insert 去重且无唯一约束、XP/现金 read-modify-write 无行锁、单个 async worker 上跑同步文件 I/O + eng_to_ipa → 静默腐蚀 XP/钱包、双计答题、高负载下卡死所有请求。
> - **激励送达缺失**：后端每题都算 XP/连胜/徽章/掌握度，但 store 全丢弃，游戏化引擎在它本该起作用的时刻是哑的；每次练习前后都撞配置墙/死胡同。
> - **设计**：基本已 token 化，但掌握度配色（项目 #1 视觉不变量）存在于 3+ 处、状态 pill 有 4 种画法。
>
> **最先修的三件**：(a) `submit_answer` 原子化（唯一约束 + FOR UPDATE）止住双 XP/重复记录；(b) 公开未认证 `/tts` 端点加固（同步 I/O 移出事件循环 + 限流 + 磁盘缓存上限），它是生产机上的活 DoS 向量；(c) 把游戏化（xp_delta/徽章/连胜/掌握升级）送进练习揭示与结算页，闭环「练习→奖励」是最大的留存杠杆。

---

## 🔴 P0-now（先做）

- [x] **0.1 submit_answer 去重非原子 → 双 XP + 重复记录** ✅已修复（免迁移）
  - `backend/app/services/practice_service.py:85` · backend-reliability · sev medium · effort M
  - **实际做法**：`submit_answer` 开头改用 `BaseRepo.get_by_id_for_update` 锁父 `PracticeSession` 行，使同一会话的并发提交（弱网重试 / `_bg_submit` / 双击）串行化 → 第二提交在去重查询里可靠命中已存在记录而提前返回。无需唯一约束迁移；原计划的 `UniqueConstraint('session_id','word_id')` 降级为可选防御加固（移至 P2，非必须）。
  - 做法：新增 alembic revision 给 PracticeRecord 加 `UniqueConstraint('session_id','word_id')`；`submit_answer` 从 `get_by_session_word` 改用 `get_by_session_word_for_update`（rejudge 已用），insert 包在 `begin_nested()` 里，并发插入抛 IntegrityError 时当已存在返回。
  - 触发：弱网/重放对同一 (session_id, word_id) 连发两次 submit，两条都过 `existing is None` → 重复记录 + 掌握度 correct_count+2 + 双倍 XP + daily task 槽 +2，全静默。

- [x] **0.2 TTS 在事件循环上做阻塞同步文件 I/O，且无界 + 未认证（生产公开 DoS）** ✅已修复
  - `backend/app/ai/tts_service.py` · backend-reliability · sev medium · effort M
  - **实际做法**：`cache_path.exists/read/mkdir/write` 全部经 `anyio.to_thread.run_sync` 移出事件循环；新增缓存文件数上限（`_CACHE_MAX_FILES=2000`）+ 按 mtime 淘汰；`/tts/generate` 加 per-IP 滑动窗口限流（30 次/分钟，`app/utils/rate_limit.py`，无新依赖），超限 429（走统一信封）。
  - 做法：`cache_path.exists()/read_bytes()/mkdir()/write_bytes()` 包 `await anyio.to_thread.run_sync(...)`；未认证 `/tts/generate` 加 per-IP 限流 + 缓存文件数全局上限 + LRU/TTL 清扫。
  - 触发：`/api/v1/tts/generate` 免登录（eng.webtao.cn 公网），任何人用大量不同 500 字串打它 → 同步 I/O 钉死唯一 worker，其余请求（登录/提交）全卡；不同文本还能把磁盘撑爆。

- [ ] **0.3 游戏化奖励数据后端已返回但被 store 丢弃；掌握升级从不庆祝（合并）** ✅最大留存杠杆
  - `frontend-vue/src/stores/practice.ts:173` · learning-attraction · sev medium · effort M
  - 做法：`submitOne` 捕获 `r.data.xp_delta/total_xp/new_badges/streak` 与答题前后掌握度到 store；各 mode 揭示位加紧凑奖励行（`+5 XP · 段位 N→N+1 · 🔥 连胜 · 🎉 升级到已掌握`）；PracticeSummary 顶部加本局 XP + 新徽章块；可选让 `finish_practice` 回传累计 xp_delta/new_badges 使结算页刷新后仍权威。
  - 触发：20 题赚 ~40 XP、过段、解锁 7 天徽章、2 词到 permanent，用户只看到 `is_correct` 和 3 个数字；XP/连胜/徽章只在另一 Dashboard tab，练习从不触发多巴胺；毕业词随后静默消失无任何提示。

- [ ] **0.4 每次练习前必选 模式+单元+数量 的配置墙 + 无首跑引导（合并）**
  - `frontend-vue/src/views/practice/PracticeConfig.vue` · learning-attraction · sev medium · effort M
  - 做法：localStorage 持久化上次 (mode, units, count)，主按钮变一键「继续上次练习」（全配置降为「自定义」）；首跑（`total_questions===0`/无掌握记录）空状态换成单一 CTA「开始第一次练习 (10 张单词卡)」预选 flashcard + 首单元 + count 10，首卡加一行教练提示解释 认识/不认识。
  - 触发：新人点「去练习」撞 11 个陌生模式 + 单元网格 + 数量 + 开关，无默认无指引；无 plan 的老用户每次练习都重复这套 3 步决策税。

---

## 🟠 P1-next

- [ ] **1.1 Member.total_xp / cash_balance read-modify-write 无行锁，4 处丢失更新** ⚠️含原子性改动
  - `backend/app/services/practice_service.py:697`（及 rejudge L276、stats `_settle_one_week` L286、`_maybe_grant_milestones` L337）· backend · sev low · effort M
  - 做法：四处统一改成单条原子 `UPDATE member SET total_xp=total_xp+:delta, cash_balance=ROUND(cash_balance+:cash,2) WHERE id=:mid`（不客户端读），或 `select(Member).with_for_update()` 后再算。与 0.1 同文件可一起做。

- [ ] **1.2 `_build_questions` 物化全部所选单元词 + 每个候选跑同步 eng_to_ipa（事件循环上）**
  - `backend/app/services/practice_service.py:355` · backend · sev medium · effort M
  - 做法：到期/权重过滤与 LIMIT 下推到 DB；`phonetic()` 延后到最终抽中的题；eng_to_ipa 回退走 `anyio.to_thread.run_sync`（DB phonetic 列全空，回退每次都跑）。

- [ ] **1.3 无 catch-all Exception handler：意外错误返回非信封 `{detail:Internal Server Error}`**
  - `backend/app/main.py:44` · backend · sev low · effort S
  - 做法：在三个特定 handler 之后再注册 `Exception` handler，记 traceback 并返回 `JSONResponse(500, _envelope(500,'服务器内部错误'))`；AppException/HTTPException 用 `raise` 保持特定 handler 权威。

- [ ] **1.4 `get_current_user` 对缺 `sub` 的合法签名 JWT 抛 KeyError → 500（应 401）**
  - `backend/app/api/deps.py:13` · backend · sev low · effort S
  - 做法：`payload.get('sub')` 为 None 时 raise 401。（catch-all 上线后症状缓解，但仍需独立 401。）

- [ ] **1.5 所有异步列表/趋势加载器存在过期响应竞态（合并：表格视图 + Stats/Progress 趋势）**
  - `frontend-vue/src/views/WordsView.vue:212`（及 WrongBook/Search/Units、Stats/Progress loadTrend+loadHeatmap）· frontend · sev medium · effort M
  - 做法：每个 loader 加单调请求 token：`const t=++lastReqId; const r=await…; if(t!==lastReqId) return;` 再写 state；或每调用一个 AbortController 并 abort 上一个。

- [ ] **1.6 `useTtsAudio.play` 每次 new Audio 且无 cancel/dispose → 重叠回声 + 播放超出组件生命周期**
  - `frontend-vue/src/composables/useTtsAudio.ts:35` · frontend · sev medium · effort S
  - 做法：composable 内置模块级 `let current`；起播前 `current?.pause()`；暴露 `stop()/dispose()`，宿主 mode 在 `onBeforeUnmount` 调（对齐 WordsView 的 `ensureAudio()` 单实例）。

- [ ] **1.7 MatchingMode 进度显示重复计数（进度条半程就到 100%）**
  - `frontend-vue/src/views/practice/modes/MatchingMode.vue:44` · frontend · sev medium · effort S
  - 做法：L44 改 `const overall = computed(()=>Math.min(batch.value*BATCH + matched.value.size, store.total))`（对齐 syncProgress/FlipMatchMode）。仅显示，`advanceIfBatchDone` 不受影响。

- [ ] **1.8 `PracticeConfig.ensureEnoughForMode` 在 start() 后孤立后端 in_progress 会话**
  - `frontend-vue/src/views/practice/PracticeConfig.vue:45` · frontend · sev medium · effort M
  - 做法：因返回题数<2 退出时（ensureEnoughForMode），对刚 start 的会话调 `store.finish()`/专用 abort，而非裸 `restart()`；或起跑前用轻量 count 端点预校验。

- [ ] **1.9 FlashcardMode（主循环）2-click 且只能鼠标、无键盘**
  - `frontend-vue/src/views/practice/modes/FlashcardMode.vue:117` · learning · sev medium · effort S
  - 做法：注册 keydown：Space/1=认识、2/Backspace=不认识、Enter=下一题（'p'=peek）；flashcard 下 `fcAutoNext` 默认 true；缺键盘的其他输入 mode（Memory）补同样绑定。

- [ ] **1.10 PracticeSummary 死胡同回到配置页——无「下一步」也无完成信号**
  - `frontend-vue/src/views/practice/PracticeSummary.vue:140` · learning · sev medium · effort M
  - 做法：finish 后重取 reviewDue/今日任务快照，显示上下文横幅：任务完成则「✅ 今日学习完成」，否则「🔁 还有 N 个到期复习 →」一键开始；「再来一轮」降为次级。

- [ ] **1.11 错答反馈只给答案，无字符 diff / 无主动回忆 / 无重错升级**
  - `frontend-vue/src/views/practice/modes/SpellingMode.vue:75`（及 Dictation/Scramble/En2CnWrite）· learning · sev medium · effort M
  - 做法：错拼/听写时渲染用户输入与正确答案的字符级 diff；`wrong_count>=2` 的词要求手敲一遍正确拼写才放开「下一题」；红横幅改建设性措辞（「差一个字母 — 再试一次」）。

- [ ] **1.12 周结算/星星/现金里程碑埋在单独 tab，练习中从不浮现**
  - `frontend-vue/src/views/WeeklySettlementView.vue:17` · learning · sev medium · effort M
  - 做法：Dashboard 加「本周」瓦片显示本周星数 + 距下一现金档进度（复用 ScoreRing/stars）；里程碑/现金档新达成时（经 submit/finish 或廉价状态端点检测）在 PracticeSummary 浮一行庆祝（`🏆 Unit 3 完成 · +¥X 进钱包`）。

- [ ] **1.13 掌握度状态 pill 在各视图有 4 种画法（守 #1 配色不变量）**
  - `frontend-vue/src/views/UnitsView.vue:82` · design · sev low · effort S
  - 做法：抽一个共享 `<MasteryTag level>`（固定 size:small/round/borderColor:transparent），替换 WordsView/SearchView/WrongBookView 的 render 与 UnitsView 的内联 `<span>`。

- [ ] **1.14 Stats/Progress 图表构建器 + MASTERY_HEX 重复（掌握配色现落 3 处）（合并）**
  - `frontend-vue/src/views/StatsView.vue:97` · design · sev low · effort M
  - 做法：trendOption/heatmapOption/masteryDistOption + formatDate 移入 `composables/useStatsCharts.ts` 双视图共用；MASTERY_HEX 移入 `constants/mastery.ts` 作为 EChart 消费者唯一源。删两处本地副本，去 ~120 行重复。

---

## 🟡 P2-later

- [ ] **2.1 `BaseRepo.update` 跳过 None → PUT 永远清不掉可选字段**
  - `backend/app/repositories/base.py:38` · backend · sev low · effort S
  - 做法：去掉 `if value is not None` 守卫，靠上游 `model_dump(exclude_unset=True)` 决定改哪些字段（或用 sentinel）；使 `PUT /words/{id} {"example":null}` 真正清空。

- [ ] **2.2 选择题选项按钮 + 样式在两个 choice mode 逐字节重复**
  - `frontend-vue/src/views/practice/modes/ChoiceMode.vue:196` · design · sev low · effort S
  - 做法：抽 `<ChoiceOption :opt :state :key-letter @click>`（或共享 practice-option.css），两 mode 导入，删两处重复 `<style>`。

- [ ] **2.3 `.section/.cards` 各视图重定义且有漂移（Dashboard 硬编 200px / 漏底间距）**
  - `frontend-vue/src/views/DashboardView.vue:312` · design · sev low · effort S
  - 做法：`.section`/`.cards`（用 `--card-min(140px)`/`--card-gap`/`--section-margin`）移入全局样式，main.ts 引一次；删 Dashboard/Stats/Progress 各自副本。

- [ ] **2.4 内联硬编 `#6B7280`/`#18a058`/`#1f2329` 数十处 + 一个游离紫色维度色（合并）**
  - `frontend-vue/src/views/WordsView.vue:300` · design · sev low · effort M
  - 做法：sweep-replace 内联 `color:#6B7280`→`var(--text-secondary)`、`#18a058`→`var(--success)`、`#1f2329`→`var(--text-primary)`；结算维度配色抽成 `constants/ui.ts` 的 `DIM_COLORS`（取自 --success/--warning/--info + 一个约定强调色），替换游离 `#7c3aed`。⚠️ECharts 配色用 JS 常量，不能吃 CSS 变量。

- [ ] **2.5 border-radius 刻度散乱（7 种）；同一文件两张卡片不一致**
  - `frontend-vue/src/views/practice/PracticeConfig.vue:407` · design · sev low · effort S
  - 做法：tokens.css 定 3 档（`--radius-sm:6px`/`--radius-md:10px`/`--radius-lg:14px`），所有表面映射（chip/button→sm，card→md，hero/flashcard→lg）；去 3/5/12/16 一次性字面量。

---

## Loop 消费规则
1. 按 **P0 → P1 → P2** 顺序取第一个未勾选项。
2. **安全项**（单文件、无迁移、无大重构）：直接实现 → 类型检查/测试 → `git add`+`commit`（**不 push**）→ 勾选 → 留一行记录。
3. **风险项**（标 ⚠️：含 alembic 迁移 / 原子性改动 / 多文件重构）：跳过自动提交，记录到本文件「待人工确认」并在主对话报方案。
4. 全清单见底 → 再跑一轮 `system-audit` 工作流补货。
