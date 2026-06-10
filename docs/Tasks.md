# Tasks — Family English Coach

## 开发阶段规划

### Phase 0: 项目基础设施 ✅ 已完成

- [x] PRD.md
- [x] Architecture.md
- [x] Tasks.md
- [x] CLAUDE.md 更新
- [x] 项目目录结构创建
- [x] Docker Compose (MySQL)
- [x] FastAPI 骨架 + 健康检查接口
- [x] SQLAlchemy 连接配置
- [x] Alembic 初始化
- [x] 统一响应体封装
- [x] `.gitignore` + `.env.example`

**交付物：** `docker-compose up` 后 MySQL 运行，`/api/v1/health` 返回 200。

---

### Phase 1: 数据模型 + 单词管理

**目标：** 建立 Unit 和 Word 的完整 CRUD。

- [ ] Database.md 文档
- [ ] API.md 文档（Word + Unit 部分）
- [ ] 数据库模型：Unit, Word, WordTag, MasteryRecord
- [ ] Alembic 迁移脚本
- [ ] Repository 层：unit_repo, word_repo, mastery_repo
- [ ] Service 层：unit_service, word_service
- [ ] Router 层：/api/v1/units, /api/v1/words
- [ ] Pydantic Schemas
- [ ] 单元测试
- [ ] Review

**交付物：** 可通过 API 创建 Unit、添加 Word、设置 Tag、查询 Mastery。

---

### Phase 2: OCR 解析

**目标：** 上传教材图片，自动生成单词库。

- [ ] OCR 接口设计（/api/v1/units/{id}/upload-image）
- [ ] AI Provider 抽象层实现（至少一个 Provider）
- [ ] OCR 结果结构化解析逻辑
- [ ] 用户确认/编辑 OCR 结果的接口
- [ ] 单元测试 + 集成测试
- [ ] Review

**交付物：** 上传图片 → AI 解析 → 返回单词列表 → 用户确认 → 存入数据库。

---

### Phase 3: 练习模块（MVP 核心）

**目标：** 实现单词卡、拼写练习、选择题三种模式。

- [ ] Practice 数据模型：PracticeSession, PracticeRecord
- [ ] 出题权重算法实现（utils/weighting.py）
- [ ] 单词卡模式 Service + API
- [ ] 拼写练习模式 Service + API
- [ ] 选择题模式 Service + API
- [ ] 练习结果提交 + Mastery 自动更新
- [ ] 单元测试
- [ ] Review

**交付物：** 前端可发起练习，后端按权重出题，提交答案后自动更新掌握状态。

---

### Phase 4: Streamlit 前端

**目标：** 完成完整的前端交互界面。

- [ ] API Client 封装
- [ ] Units 页面（上传图片、查看 Unit 列表）
- [ ] Words 页面（单词列表、标签管理、编辑）
- [ ] Practice 页面（选择模式 → 练习 → 提交）
- [ ] Stats 页面（掌握率统计）
- [ ] 组件：word_card, spelling_input, choice_quiz, mastery_badge
- [ ] Review

**交付物：** 完整的浏览器交互体验，覆盖 MVP 全流程。

---

### Phase 5: 学习计划

**目标：** 自动规划每日学习任务。

- [ ] Plan 数据模型：LearningPlan, DailyTask
- [ ] 计划创建接口（目标、截止日期、单元范围）
- [ ] 每日任务自动生成算法
- [ ] 任务完成状态追踪
- [ ] 前端 Plan 页面
- [ ] 单元测试
- [ ] Review

---

### Phase 6: 数据统计

**目标：** 学习数据可视化和趋势分析。

- [ ] 统计接口设计（全局、按 Unit、按时间）
- [ ] Stats Service 实现
- [ ] 连续学习天数计算
- [ ] 前端 Stats 页面增强（图表）
- [ ] Review

---

### Phase 7: AI 增强

**目标：** 接入 AI 能力，生成场景对话和练习题。

- [ ] AI Provider 具体实现（Claude / Minimax / 智谱 / DeepSeek）
- [ ] 场景对话生成接口
- [ ] AI 练习题生成接口
- [ ] 前端场景对话页面
- [ ] Review

---

### Phase 8: 高级功能（P2）

- [ ] 听写模式（TTS）
- [ ] 跟读评分（STT + 评分）
- [ ] Redis 缓存层
- [ ] 多用户支持
- [ ] 移动端适配

---

## 当前进度

| 阶段 | 状态 |
|---|---|
| Phase 0: 基础设施 | ✅ 已完成 |
| Phase 1: 数据模型 | ⚪ 待开始 |
| Phase 2: OCR 解析 | ⚪ 待开始 |
| Phase 3: 练习模块 | ⚪ 待开始 |
| Phase 4: 前端界面 | ⚪ 待开始 |
| Phase 5: 学习计划 | ⚪ 待开始 |
| Phase 6: 数据统计 | ⚪ 待开始 |
| Phase 7: AI 增强 | ⚪ 待开始 |
| Phase 8: 高级功能 | ⚪ 待开始 |

## 迭代规则

1. 每个 Phase 内按 Tasks 顺序执行，逐项完成
2. 每个 Phase 结束前必须通过 Review
3. Review 通过后才能进入下一个 Phase
4. 发现问题随时回退修正，不累积技术债
