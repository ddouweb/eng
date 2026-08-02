#!/usr/bin/env python3
"""
在 Docker 容器内执行的数据库同步脚本
此脚本应在 english_coach_backend 容器内运行

用法: sudo docker exec -i english_coach_backend python3 - < sync_via_backend.py
"""

import pymysql
import sys
import subprocess

# 源数据库 (3307) - 通过 host.docker.internal 访问主机
SOURCE_CONFIG = {
    'host': 'host.docker.internal',
    'port': 3307,
    'user': 'root',
    'password': 'root123',
    'database': 'english_coach',
    'charset': 'utf8mb4'
}

# 目标数据库 (3306) - docker-compose 中的服务
TARGET_CONFIG = {
    'host': 'db',
    'port': 3306,
    'user': 'root',
    'password': 'root123',
    'database': 'english_coach',
    'charset': 'utf8mb4'
}


def get_tables(cursor):
    """获取所有表名"""
    cursor.execute("SHOW TABLES")
    return [t[0] for t in cursor.fetchall()]


def get_table_count(cursor, table):
    """获取表的行数"""
    cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
    return cursor.fetchone()[0]


def dump_table(cursor, table):
    """导出表数据"""
    cursor.execute(f"SELECT * FROM `{table}`")

    # 获取列信息
    cursor.execute(f"DESCRIBE `{table}`")
    columns = [col[0] for col in cursor.fetchall()]

    # 获取所有行
    cursor.execute(f"SELECT * FROM `{table}`")
    rows = cursor.fetchall()

    return columns, rows


def load_table(cursor, table, columns, rows):
    """加载表数据"""
    if not rows:
        return 0

    # 清空表
    cursor.execute("SET FOREIGN_KEY_CHECKS=0")
    try:
        cursor.execute(f"TRUNCATE TABLE `{table}`")
    except:
        cursor.execute(f"DELETE FROM `{table}`")
    cursor.execute("SET FOREIGN_KEY_CHECKS=1")

    # 构建插入语句
    placeholders = ', '.join(['%s'] * len(columns))
    columns_str = ', '.join([f"`{col}`" for col in columns])
    insert_sql = f"INSERT INTO `{table}` ({columns_str}) VALUES ({placeholders})"

    cursor.executemany(insert_sql, rows)
    return cursor.rowcount


def main():
    print("=" * 50)
    print("数据库同步: 3307 -> 3306")
    print("在 Docker 容器内运行")
    print("=" * 50)

    # 连接源数据库
    print("\n连接源数据库 (3307)...")
    try:
        source_conn = pymysql.connect(**SOURCE_CONFIG)
        source_cur = source_conn.cursor()
        print("✓ 源数据库连接成功")
    except Exception as e:
        print(f"✗ 源数据库连接失败: {e}")
        return 1

    # 连接目标数据库
    print("连接目标数据库 (3306)...")
    try:
        target_conn = pymysql.connect(**TARGET_CONFIG)
        target_cur = target_conn.cursor()
        print("✓ 目标数据库连接成功")
    except Exception as e:
        print(f"✗ 目标数据库连接失败: {e}")
        source_conn.close()
        return 1

    # 获取表列表
    print("\n获取表列表...")
    tables = get_tables(source_cur)
    print(f"发现 {len(tables)} 个表: {tables}")

    # 显示源数据统计
    print("\n源数据库 (3307):")
    for table in tables:
        count = get_table_count(source_cur, table)
        print(f"  {table}: {count} 行")

    # 显示目标数据统计（同步前）
    print("\n目标数据库 (3306) - 同步前:")
    for table in tables:
        try:
            count = get_table_count(target_cur, table)
            print(f"  {table}: {count} 行")
        except:
            print(f"  {table}: 不存在")

    # 开始同步
    print("\n开始同步...")
    success_count = 0
    fail_count = 0

    for table in tables:
        print(f"\n处理表: {table}")
        try:
            columns, rows = dump_table(source_cur, table)
            count = load_table(target_cur, table, columns, rows)
            print(f"  ✓ 已同步 {count} 行")
            success_count += 1
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            fail_count += 1

    # 提交事务
    try:
        target_conn.commit()
        print("\n✓ 事务已提交")
    except Exception as e:
        target_conn.rollback()
        print(f"\n✗ 事务回滚: {e}")

    # 显示目标数据统计（同步后）
    print("\n目标数据库 (3306) - 同步后:")
    for table in tables:
        try:
            count = get_table_count(target_cur, table)
            print(f"  {table}: {count} 行")
        except:
            print(f"  {table}: 错误")

    # 关闭连接
    source_cur.close()
    target_cur.close()
    source_conn.close()
    target_conn.close()

    # 汇总
    print("\n" + "=" * 50)
    print(f"同步完成: 成功 {success_count} 个, 失败 {fail_count} 个")
    print("=" * 50)

    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
