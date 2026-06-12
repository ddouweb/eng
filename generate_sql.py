import json
import re

with open(r'C:\Users\root\Desktop\work-en\parsed_words_final.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

sql_lines = []
sql_lines.append("-- ============================================")
sql_lines.append("-- Family English Coach - 数据库初始化脚本")
sql_lines.append("-- 自动从 18章答案.pdf 提取，共 18 个单元")
sql_lines.append("-- ============================================")
sql_lines.append("")
sql_lines.append("SET NAMES utf8mb4;")
sql_lines.append("SET FOREIGN_KEY_CHECKS = 0;")
sql_lines.append("")
sql_lines.append("-- -------------------------------------------")
sql_lines.append("-- 1. 清空旧数据（按外键依赖逆序）")
sql_lines.append("-- -------------------------------------------")
sql_lines.append("DELETE FROM word_tags;")
sql_lines.append("DELETE FROM mastery_record;")
sql_lines.append("DELETE FROM practice_record;")
sql_lines.append("DELETE FROM practice_session;")
sql_lines.append("DELETE FROM daily_task;")
sql_lines.append("DELETE FROM plan_units;")
sql_lines.append("DELETE FROM learning_plan;")
sql_lines.append("DELETE FROM word;")
sql_lines.append("DELETE FROM unit;")
sql_lines.append("DELETE FROM member;")
sql_lines.append("")
sql_lines.append("-- -------------------------------------------")
sql_lines.append("-- 2. 插入默认家庭成员")
sql_lines.append("-- -------------------------------------------")
sql_lines.append("INSERT INTO member (id, name, avatar, created_at, updated_at) VALUES")
sql_lines.append("  (1, '默认用户', NULL, NOW(), NOW());")
sql_lines.append("")

# Units
sql_lines.append("-- -------------------------------------------")
sql_lines.append("-- 3. 插入单元 (Unit 1 ~ 18)")
sql_lines.append("-- -------------------------------------------")
sql_lines.append("INSERT INTO unit (id, title, sequence, image_url, created_at, updated_at) VALUES")
unit_values = []
for i in range(1, 19):
    unit_values.append(f"  ({i}, 'Unit {i}', {i}, NULL, NOW(), NOW())")
sql_lines.append(",\n".join(unit_values) + ";")
sql_lines.append("")

# Words
sql_lines.append("-- -------------------------------------------")
sql_lines.append("-- 4. 插入单词")
sql_lines.append("-- -------------------------------------------")

word_id = 1
word_values = []
word_count = 0
seen_english = set()  # track duplicates across units

for unit_num, words in data:
    sorted_entries = sorted(words.items(), key=lambda x: int(x[0]))
    for no, (english, chinese) in sorted_entries:
        # Escape SQL special chars
        english_clean = english.replace("'", "''").strip()
        chinese_clean = chinese.replace("'", "''").strip()

        # Remove stray number prefixes from cleanup artifacts
        chinese_clean = re.sub(r'\s+', ' ', chinese_clean).strip()

        # Determine type
        # Phrases with spaces and common function words are still "word" type
        # Only multi-word expressions > 20 chars are "sentence"
        word_type = "sentence" if " " in english and len(english) > 20 else "word"

        word_values.append(
            f"  ({word_id}, {unit_num}, '{english_clean}', '{chinese_clean}', '{word_type}', NOW(), NOW())"
        )
        word_id += 1
        word_count += 1

# Split into batches of 500 for readability
batch_size = 500
for batch_start in range(0, len(word_values), batch_size):
    batch = word_values[batch_start:batch_start + batch_size]
    sql_lines.append("INSERT INTO word (id, unit_id, english, chinese, type, created_at, updated_at) VALUES")
    sql_lines.append(",\n".join(batch) + ";")
    sql_lines.append("")

sql_lines.append("-- -------------------------------------------")
sql_lines.append("-- 统计信息")
sql_lines.append("-- -------------------------------------------")
sql_lines.append(f"-- 单元数: 18")
sql_lines.append(f"-- 单词总数: {word_count}")
sql_lines.append("")
sql_lines.append("SET FOREIGN_KEY_CHECKS = 1;")
sql_lines.append("")

output_path = r'C:\Users\root\Desktop\work-en\backend\init_data.sql'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(sql_lines))

print(f"SQL written: {output_path}")
print(f"Units: 18, Words: {word_count}")
