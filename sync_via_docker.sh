#!/bin/bash
# 数据库同步脚本 - 通过 Docker 容器执行
# 用法: ./sync_via_docker.sh

set -e

echo "================================"
echo "数据库同步: 3307 -> 3306"
echo "================================"

# 源数据库 (3307) - 可能是独立的 MySQL 实例
SOURCE_HOST="host.docker.internal"
SOURCE_PORT=3307
SOURCE_USER="root"
SOURCE_PASS="root123"
SOURCE_DB="english_coach"

# 目标数据库 (3306) - docker-compose 中的数据库
TARGET_HOST="db"
TARGET_PORT=3306
TARGET_USER="root"
TARGET_PASS="root123"
TARGET_DB="english_coach"

echo ""
echo "正在通过 docker 容器执行同步..."
echo ""

# 使用 backend 容器执行 mysqldump
docker exec -i english_coach_backend bash -c "
    # 安装 mysql 客户端（如果需要）
    # apk add --no-cache mysql-client

    # 从源数据库导出数据
    echo \"从源数据库导出数据...\"
    mysqldump -h ${SOURCE_HOST} -P ${SOURCE_PORT} -u${SOURCE_USER} -p${SOURCE_PASS} \
        --single-transaction \
        --quick \
        --lock-tables=false \
        ${SOURCE_DB} 2>/dev/null | \
    # 导入到目标数据库
    mysql -h ${TARGET_HOST} -P ${TARGET_PORT} -u${TARGET_USER} -p${TARGET_PASS} ${TARGET_DB} 2>/dev/null

    if [ \$? -eq 0 ]; then
        echo \"✓ 同步完成！\"
    else
        echo \"✗ 同步失败\"
        exit 1
    fi
"

echo ""
echo "验证目标数据库..."
docker exec -i english_coach_backend bash -c "
    mysql -h ${TARGET_HOST} -P ${TARGET_PORT} -u${TARGET_USER} -p${TARGET_PASS} ${TARGET_DB} -e \"
        SELECT CONCAT('Table: ', table_name, ', Rows: ', table_rows)
        FROM information_schema.tables
        WHERE table_schema = '${TARGET_DB}';
    \" 2>/dev/null
"

echo ""
echo "================================"
echo "同步完成！"
echo "================================"
