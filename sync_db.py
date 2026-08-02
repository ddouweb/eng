#!/usr/bin/env python3
"""
数据库同步脚本 - 从 3307 端口同步到 3306 端口
用法: python sync_db.py
"""

import pymysql
import sys

# 源数据库配置 (3307)
SOURCE_CONFIG = {
    'host': 'localhost',
    'port': 3307,
    'user': 'root',
    'password': '123456',
    'database': 'english_coach',
    'charset': 'utf8mb4'
}

# 目标数据库配置 (3306)
TARGET_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'database': 'english_coach',
    'charset': 'utf8mb4'
}

# 需要同步的表（按依赖顺序 - 从无依赖到有依赖）
TABLES = [
    'member',           # 基础表，无依赖
    'unit',             # 基础表，无依赖
    'word',             # 依赖 unit
    'word_tags',        # 依赖 word
    'learning_plan',    # 依赖 member
    'daily_task',       # 依赖 learning_plan
    'plan_units',       # 依赖 learning_plan, unit
    'practice_session', # 依赖 member
    'practice_record',  # 依赖 practice_session, word
    'mastery_record',   # 依赖 member, word
    'alembic_version',  # 独立表
]


def sync_table(source_cur, target_cur, table_name):
    """同步单个表的数据"""
    print(f"\n同步表: {table_name}")

    # 1. 清空目标表（注意：这会删除目标表的所有数据！）
    try:
        target_cur.execute(f"SET FOREIGN_KEY_CHECKS=0")
        target_cur.execute(f"TRUNCATE TABLE `{table_name}`")
        target_cur.execute(f"SET FOREIGN_KEY_CHECKS=1")
        print(f"  ✓ 已清空目标表 {table_name}")
    except Exception as e:
        print(f"  ✗ 清空目标表失败: {e}")
        # 如果 TRUNCATE 失败，尝试 DELETE
        try:
            target_cur.execute(f"DELETE FROM `{table_name}`")
            print(f"  ✓ 已用 DELETE 清空目标表 {table_name}")
        except Exception as e2:
            print(f"  ✗ DELETE 也失败: {e2}")
            return False

    # 2. 获取源表数据
    source_cur.execute(f"SELECT * FROM `{table_name}`")
    rows = source_cur.fetchall()

    # 3. 获取列名
    if not rows:
        print(f"  - 源表为空，跳过")
        return True

    source_cur.execute(f"DESCRIBE `{table_name}`")
    columns = [col[0] for col in source_cur.fetchall()]
    print(f"  列: {columns}")

    # 4. 构建并执行 INSERT 语句
    placeholders = ', '.join(['%s'] * len(columns))
    columns_str = ', '.join([f"`{col}`" for col in columns])
    insert_sql = f"INSERT INTO `{table_name}` ({columns_str}) VALUES ({placeholders})"

    try:
        target_cur.executemany(insert_sql, rows)
        affected = target_cur.rowcount
        print(f"  ✓ 已同步 {affected} 行")
        return True
    except Exception as e:
        print(f"  ✗ 插入数据失败: {e}")
        return False


def check_databases():
    """检查两个数据库的连接状态"""
    print("=== 检查数据库连接 ===\n")

    # 检查源数据库 (3307)
    try:
        source_conn = pymysql.connect(**SOURCE_CONFIG)
        source_cur = source_conn.cursor()
        source_cur.execute("SHOW TABLES")
        source_tables = [t[0] for t in source_cur.fetchall()]
        print(f"✓ 源数据库 (3307) 连接成功")
        print(f"  表: {source_tables}")
        for t in source_tables:
            source_cur.execute(f"SELECT COUNT(*) FROM `{t}`")
            cnt = source_cur.fetchone()[0]
            print(f"    {t}: {cnt} 行")
        source_cur.close()
        source_conn.close()
    except Exception as e:
        print(f"✗ 源数据库 (3307) 连接失败: {e}")
        return False

    print()

    # 检查目标数据库 (3306)
    try:
        target_conn = pymysql.connect(**TARGET_CONFIG)
        target_cur = target_conn.cursor()
        target_cur.execute("SHOW TABLES")
        target_tables = [t[0] for t in target_cur.fetchall()]
        print(f"✓ 目标数据库 (3306) 连接成功")
        print(f"  表: {target_tables}")
        target_cur.close()
        target_conn.close()
    except Exception as e:
        print(f"✗ 目标数据库 (3306) 连接失败: {e}")
        return False

    return True


def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description='数据库同步工具')
    parser.add_argument('-y', '--yes', action='store_true', help='自动确认，跳过提示')
    args = parser.parse_args()

    print("=" * 50)
    print("数据库同步工具: 3307 → 3306")
    print("=" * 50)

    # 1. 检查连接
    if not check_databases():
        print("\n数据库连接检查失败，请确保:")
        print("  1. 两个 MySQL 服务都在运行")
        print("  2. root 用户密码正确")
        print("  3. english_coach 数据库已存在")
        sys.exit(1)

    # 2. 确认操作
    print("\n" + "=" * 50)
    print("⚠️  警告: 此操作会清空目标数据库 (3306) 的所有数据并覆盖！")
    print("=" * 50)

    if not args.yes:
        response = input("\n确认继续? (yes/no): ").strip().lower()
        if response not in ('yes', 'y'):
            print("已取消")
            sys.exit(0)
    else:
        print("\n使用 -y 参数，自动确认...")

    # 3. 连接数据库
    try:
        source_conn = pymysql.connect(**SOURCE_CONFIG)
        target_conn = pymysql.connect(**TARGET_CONFIG)
        source_cur = source_conn.cursor()
        target_cur = target_conn.cursor()
    except Exception as e:
        print(f"连接数据库失败: {e}")
        sys.exit(1)

    # 4. 同步每个表
    print("\n=== 开始同步 ===")
    success_count = 0
    fail_count = 0

    for table in TABLES:
        if sync_table(source_cur, target_cur, table):
            success_count += 1
        else:
            fail_count += 1

    # 5. 提交事务
    try:
        target_conn.commit()
        print("\n✓ 事务已提交")
    except Exception as e:
        target_conn.rollback()
        print(f"\n✗ 事务回滚: {e}")

    # 6. 关闭连接
    source_cur.close()
    target_cur.close()
    source_conn.close()
    target_conn.close()

    # 7. 汇总
    print("\n=== 同步完成 ===")
    print(f"成功: {success_count} 个表")
    print(f"失败: {fail_count} 个表")


if __name__ == '__main__':
    main()
