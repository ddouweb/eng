# 考研词库导入（ECDICT）

把开源 ECDICT 中的考研大纲词导入数据库，按词频拆成 3 个 Unit，自动打上高频/考试标签，纳入日常训练闭环。

> 数据来源合法：ECDICT（MIT/CC 协议，可商用），与「不背单词」等商业 App 无关，无版权风险。
> 实测导入：考研词 **4801** 个 → 高频核心 865 / 常用 2797 / 基础 1139。

## 1. 下载 ECDICT 数据（一次性）

GitHub 仓库：https://github.com/skywind3000/ECDICT

1. 打开仓库 → **Releases**（当前版本 1.0.28）
2. 下载 **`ecdict-sqlite-28.zip`**（约 207MB，解压得到 `stardict.db`，内含 `stardict` 数据表）
   - ⚠️ **不要下 `ecdict-stardict-*.zip`** —— 那是 StarDict 词典软件的二进制格式（`.dict`/`.idx`/`.ifo`），不是数据表，本脚本读不了。要数据表必须下 **sqlite** 版。
3. 解压后把 `stardict.db` 放到任意路径，例如 `backend/data/stardict.db`

## 2. 运行导入

```bash
cd backend

# 先预览分组数量，不写库
python scripts/import_ecdict.py --source ./data/stardict.db --dry-run

# 确认无误后实际导入
python scripts/import_ecdict.py --source ./data/stardict.db
```

> 数据库连接读 `backend/.env` 的 `DATABASE_URL`（默认 `root:root123` 是占位，需改成你的真实密码）。
> 脚本同时支持 `.csv`（ECDICT stardict.csv）和 `.db`（SQLite），自动识别；当前 release 只直接提供 sqlite 版。

## 3. 导入规则

| 项 | 规则 |
|---|---|
| 筛选 | ECDICT `tag` 含 `ky`（考研大纲词，实测 4801 个） |
| 分组（Unit） | 按 collins 词频星拆 3 个：高频核心(`≥4`) 865 / 常用(`2-3`) 2797 / 基础(`≤1`或缺失) 1139 |
| 标签 | 全部打 `exam_focus`；`collins≥4` 或 `oxford=1` 加打 `high_freq`（实测 2027 个高频标签） |
| 中文释义 | 取 ECDICT `translation` 字段（UTF-8，正常无乱码） |
| 幂等 | 按 `(unit_id, english)` 去重，重复运行不产生重复词 |
| Unit 序号 | `sequence` 接在现有最大值之后，不与已有 Unit 冲突 |

## 4. 与训练闭环的对接

- 导入后词即挂在对应 Unit 下，可直接进入 flashcard / spelling / dictation 等练习。
- `weighting.py` 已设 `high_freq = exam_focus = 1.5`，高频考研词在练习中自动优先出现。
- 在 `LearningPlan` 中先选「考研·高频核心」Unit，背完再切「常用」「基础」。

## 5. 常见问题

- **报错连不上数据库**：确认 MySQL 已启动、`backend/.env` 的 `DATABASE_URL` 改成你的真实密码。
- **报错 "不支持的文件格式"**：确认下的是 `ecdict-sqlite-*.zip`（解压出 `.db`），不是 `ecdict-stardict-*.zip`。
- **想重新分组**：先删除 3 个「考研·」Unit，再重跑脚本（幂等，已导入的词会跳过）。
- **磁盘占用**：导入完成后 `stardict.db`（811MB）和 zip 可删除，数据已在 MySQL 中；保留 `stardict.db` 可供重跑。
