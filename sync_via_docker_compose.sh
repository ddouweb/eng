#!/bin/bash
# 数据库同步脚本 - 使用 mysqldump 通过管道直接传输
#
# 此脚本需要 sudo 权限来访问 docker
#
# 用法: sudo ./sync_via_docker_compose.sh

set -e

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}================================"
echo "数据库同步: 3307 -> 3306"
echo -e "================================${NC}"
echo ""

# 检查 docker 是否可用
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: docker 不可用${NC}"
    echo "请先安装 docker 或使用 sudo 权限"
    exit 1
fi

# 检查 mysqldump 是否可用
if ! command -v mysqldump &> /dev/null; then
    echo -e "${RED}错误: mysqldump 不可用${NC}"
    echo "请安装 mysql-client: sudo apt-get install mysql-client"
    exit 1
fi

# 数据库配置
SOURCE_HOST="127.0.0.1"
SOURCE_PORT=3307
SOURCE_USER="root"
SOURCE_PASS="root123"
SOURCE_DB="english_coach"

TARGET_HOST="127.0.0.1"
TARGET_PORT=3306
TARGET_USER="root"
TARGET_PASS="root123"
TARGET_DB="english_coach"

echo "源数据库: ${SOURCE_HOST}:${SOURCE_PORT}/${SOURCE_DB}"
echo "目标数据库: ${TARGET_HOST}:${TARGET_PORT}/${TARGET_DB}"
echo ""

# 测试源数据库连接
echo -n "测试源数据库连接... "
if mysql -h${SOURCE_HOST} -P${SOURCE_PORT} -u${SOURCE_USER} -p${SOURCE_PASS} -e "USE ${SOURCE_DB};" 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ 失败${NC}"
    echo "请检查源数据库是否运行，密码是否正确"
    exit 1
fi

# 测试目标数据库连接
echo -n "测试目标数据库连接... "
if mysql -h${TARGET_HOST} -P${TARGET_PORT} -u${TARGET_USER} -p${TARGET_PASS} -e "USE ${TARGET_DB};" 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗ 失败${NC}"
    echo "请检查目标数据库是否运行，密码是否正确"
    exit 1
fi

echo ""
echo -e "${YELLOW}警告: 此操作会覆盖目标数据库 (3306) 的所有数据！${NC}"
echo ""

# 询问确认
read -p "确认继续? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "已取消"
    exit 0
fi

echo ""
echo "开始同步..."

# 使用 mysqldump 通过管道直接传输数据
# --single-transaction: 对于 InnoDB，保证一致性而不锁定表
# --quick: 逐行读取，避免内存问题
# --lock-tables=false: 不锁定表（与 single-transaction 配合）

mysqldump \
    -h${SOURCE_HOST} \
    -P${SOURCE_PORT} \
    -u${SOURCE_USER} \
    -p${SOURCE_PASS} \
    --single-transaction \
    --quick \
    --lock-tables=false \
    --set-gtid-purged=OFF \
    ${SOURCE_DB} 2>/dev/null | \
mysql \
    -h${TARGET_HOST} \
    -P${TARGET_PORT} \
    -u${TARGET_USER} \
    -p${TARGET_PASS} \
    ${TARGET_DB} 2>/dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 同步完成！${NC}"
else
    echo -e "${RED}✗ 同步失败${NC}"
    exit 1
fi

# 验证数据
echo ""
echo "验证目标数据库:"
mysql -h${TARGET_HOST} -P${TARGET_PORT} -u${TARGET_USER} -p${TARGET_PASS} ${TARGET_DB} -e "
    SELECT
        CONCAT('Table: ', table_name, ', Rows: ', table_rows)
    FROM information_schema.tables
    WHERE table_schema = '${TARGET_DB}'
    ORDER BY table_name;
" 2>/dev/null

echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}同步完成！${NC}"
echo -e "${GREEN}================================${NC}"
