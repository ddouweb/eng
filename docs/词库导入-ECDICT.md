# 考研词库导入（ECDICT）

把开源 ECDICT 中的考研大纲词导入数据库，按词频拆成 3 个 Unit，自动打上高频/考试标签，纳入日常训练闭环。

> 数据来源合法：ECDICT（MIT/CC 协议，可商用），与「不背单词」等商业 App 无关，无版权风险。
> 词数口径以 `scripts/import_ecdict.py` / `ecdict_to_seed_sql.py` 注释为准：筛选 `tag` 含 `ky` 的考研大纲词，约 **5500** 个（随 ECDICT release 浮动），按 collins 词频运行时分到 3 个 Unit（高频核心 `≥4` / 常用 `2-3` / 基础 `≤1` 或缺失），具体每组数量以脚本 `--dry-run` 实测为准。

## 1. 下载 ECDICT 数据（一次性）

GitHub 仓库：https://github.com/skywind3000/ECDICT

1. 打开仓库 → **Releases**（当前版本 1.0.28）
2. 下载 **`ecdict-sqlite-28.zip`**（约 207MB，解压得到 `stardict.db`，内含 `stardict` 数据表）
   - ⚠️ **不要下 `ecdict-stardict-*.zip`** —— 那是 StarDict 词典软件的二进制格式（`.dict`/`.idx`/`.ifo`），不是数据表，本脚本读不了。要数据表必须下 **sqlite** 版。
3. 解压后把 `stardict.db` 放到任意路径，例如 `backend/data/stardict.db`

## 2. 方式 A：直接连库导入（import_ecdict.py）

```bash
cd backend

# 先预览分组数量，不写库
python scripts/import_ecdict.py --source ./data/stardict.db --dry-run

# 确认无误后实际导入
python scripts/import_ecdict.py --source ./data/stardict.db
```

> 数据库连接读 `backend/.env` 的 `DATABASE_URL`（默认 `root:root123` 是占位，需改成你的真实密码）。
> 脚本同时支持 `.csv`（ECDICT stardict.csv）和 `.db`（SQLite），自动识别；当前 release 只直接提供 sqlite 版。

## 2.1 方式 B：生成可复用 SQL 种子文件（ecdict_to_seed_sql.py）

不连数据库，只读 ECDICT 生成一个幂等 `.sql` 文件，可入 MySQL、可提交进 git 反复使用（风格同 `seed_18_units.sql`）。

```bash
cd backend
# 生成 backend/seed_kaoyan_english2.sql
python scripts/ecdict_to_seed_sql.py --source ./data/stardict.db

# 导入 MySQL（PowerShell 不支持 < 重定向，用下面任一方式）
Get-Content seed_kaoyan_english2.sql -Raw | mysql -uroot -p<数据库名>
# 或
cmd /c "mysql -uroot -p<数据库名> < seed_kaoyan_english2.sql"
```

> 分组、标签规则与方式 A 一致（见第 3 节）。**但 SQL 种子只写 `english / chinese / seq / type`，不写 `phonetic / definition / pos` 富字段**（与 `import_ecdict.py` 不同）——这些词在库中无音标，前端展示**完全依赖 `eng_to_ipa` 运行时回退**（见第 6 节部署依赖）。脚本只依赖 Python 标准库，不连库、不依赖 `app/SQLAlchemy`。
> 幂等：SQL 开头 `DELETE FROM unit WHERE title LIKE '考研·%'`，word / word_tags 随外键级联删除，可安全重跑。

## 3. 导入规则

| 项 | 规则 |
|---|---|
| 筛选 | ECDICT `tag` 含 `ky`（考研大纲词，约 5500 个，随 release 浮动） |
| 分组（Unit） | 按 collins 词频星拆 3 个：高频核心(`≥4`) / 常用(`2-3`) / 基础(`≤1` 或缺失)；每组数量以 `--dry-run` 实测为准 |
| 标签 | 全部打 `exam_focus`；`collins≥4` 或 `oxford=1` 加打 `high_freq` |
| 中文释义 | 取 ECDICT `translation` 字段（UTF-8，正常无乱码），超长截断到 500 字符 |
| 富字段（仅方式 A `import_ecdict.py`） | 一并写入 ECDICT 自带的 `phonetic`(音标) / `definition`(英文释义) / `pos`(词性)。音标统一存**裸 IPA**（去包裹斜杠，前端展示时统一加 `/.../`）。ECDICT 无可靠例句，`example` 留空，后续由 AI 解析/生成补齐。**方式 B 的 SQL 种子不写富字段**（见 §2.1）。 |
| 序号 | `word.seq` = 该 Unit 内递增序号（1,2,3...） |
| 幂等 | 按 `(unit_id, english)` 去重，重复运行不产生重复词 |
| Unit 序号 | `sequence` 接在现有最大值之后，不与已有 Unit 冲突 |

## 4. 与训练闭环的对接

- 导入后词即挂在对应 Unit 下，可直接进入 flashcard / spelling / dictation 等练习。
- `weighting.py` 已设 `high_freq = exam_focus = 1.5`，高频考研词在练习中自动优先出现。
- 在 `LearningPlan` 中先选「考研·高频核心」Unit，背完再切「常用」「基础」。

## 5. 音标运行时回退（部署关键依赖）

前端展示音标采用「库存优先、缺省现算」单一来源（`backend/app/utils/phonetics.py`）：

1. 优先读 `word.phonetic`（方式 A `import_ecdict.py` 导入的裸 IPA，已去包裹斜杠）；
2. 库存为空时，回退 `eng_to_ipa` 本地词典**实时转换**（零网络、有进程内缓存），末尾 `*`（词典未命中）不展示。

**部署必须 `pip install eng-to-ipa`**（生产 venv 同样），否则：

- 方式 A 导入的词：多数有 `phonetic`，仍可显示（库存命中）；
- 方式 B 的 SQL 种子词：**完全不写 `phonetic`**，缺 `eng_to_ipa` 时将全部不显示音标（不报错，仅静默降级为空）。

`eng_to_ipa` 为可选依赖（未安装时 `phonetics.py` 优雅降级为「仅返回库存」），但 ECDICT 词库场景下强烈建议安装。

## 6. 常见问题

- **报错连不上数据库**：确认 MySQL 已启动、`backend/.env` 的 `DATABASE_URL` 改成你的真实密码。
- **报错 "不支持的文件格式"**：确认下的是 `ecdict-sqlite-*.zip`（解压出 `.db`），不是 `ecdict-stardict-*.zip`。
- **想重新分组**：先删除 3 个「考研·」Unit，再重跑脚本（幂等，已导入的词会跳过）。
- **磁盘占用**：导入完成后 `stardict.db`（811MB）和 zip 可删除，数据已在 MySQL 中；保留 `stardict.db` 可供重跑。
- **导入后词没有音标**：方式 B 的 SQL 种子不写 `phonetic`，音标靠 `eng_to_ipa` 运行时回退——确认后端 venv 已 `pip install eng-to-ipa`（见第 5 节）。方式 A 导入的词无音标则是 ECDICT 本身该词缺 `phonetic` 字段且 `eng_to_ipa` 词典未命中（OOV）。
