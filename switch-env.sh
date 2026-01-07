#!/bin/bash
# =============================================================================
# 环境切换脚本 (Environment Switcher)
# =============================================================================
# 用法：
#   ./switch-env.sh local      # 切换到开发环境
#   ./switch-env.sh staging    # 切换到测试环境
#   ./switch-env.sh production # 切换到生产环境
#   ./switch-env.sh status     # 查看当前环境
# =============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 环境配置文件映射
declare -A ENV_FILES=(
    ["local"]=".env.local"
    ["staging"]=".env.staging"
    ["production"]=".env.production"
)

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# 显示当前环境
show_status() {
    if [ -f .env ]; then
        CURRENT_ENV=$(grep "^ENVIRONMENT=" .env | cut -d '=' -f2)
        PROJECT_NAME=$(grep "^PROJECT_NAME=" .env | cut -d '=' -f2 | tr -d '"')

        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo -e "${BLUE}当前环境状态${NC}"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo -e "环境:     ${GREEN}${CURRENT_ENV}${NC}"
        echo -e "项目:     ${PROJECT_NAME}"
        echo -e "配置文件: .env"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""

        # 显示关键配置
        echo "关键配置："
        echo "  - 数据库: $(grep "^POSTGRES_DB=" .env | cut -d '=' -f2)"
        echo "  - Workers: $(grep "^GUNICORN_WORKERS=" .env | cut -d '=' -f2)"
        echo "  - 连接池: $(grep "^DB_POOL_SIZE=" .env | cut -d '=' -f2)"
        echo ""
    else
        print_warning "未找到 .env 文件"
        print_info "请运行: ./switch-env.sh <环境名称>"
    fi
}

# 切换环境
switch_env() {
    local target_env=$1
    local env_file="${ENV_FILES[$target_env]}"

    # 验证环境名称
    if [ -z "$env_file" ]; then
        print_error "无效的环境名称: $target_env"
        print_info "可用环境: local, staging, production"
        exit 1
    fi

    # 检查环境文件是否存在
    if [ ! -f "$env_file" ]; then
        print_error "环境配置文件不存在: $env_file"
        exit 1
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BLUE}切换环境${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # 备份当前 .env（如果存在）
    if [ -f .env ]; then
        CURRENT_ENV=$(grep "^ENVIRONMENT=" .env | cut -d '=' -f2 2>/dev/null || echo "unknown")
        BACKUP_FILE=".env.backup.${CURRENT_ENV}.$(date +%Y%m%d_%H%M%S)"
        cp .env "$BACKUP_FILE"
        print_info "已备份当前配置到: $BACKUP_FILE"
    fi

    # 复制新环境配置
    cp "$env_file" .env
    print_success "已切换到 ${target_env} 环境"

    # 生产环境安全检查
    if [ "$target_env" = "production" ]; then
        echo ""
        print_warning "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_warning "生产环境安全检查"
        print_warning "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        # 检查是否修改了默认密码
        if grep -q "CHANGE_THIS" .env; then
            print_error "❌ 检测到未修改的默认配置！"
            print_error "请修改 .env 文件中所有包含 'CHANGE_THIS' 的配置项"
            echo ""
            print_info "需要修改的配置："
            grep "CHANGE_THIS" .env | sed 's/^/  - /'
            echo ""
            print_warning "建议运行: vim .env"
            exit 1
        fi

        if grep -q "changethis" .env; then
            print_error "❌ 检测到弱密码 'changethis'！"
            print_error "请修改所有密码为强密码"
            exit 1
        fi

        print_success "✓ 安全检查通过"
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    print_success "环境切换完成！"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # 显示新环境状态
    show_status

    # 提示重启服务
    echo ""
    print_info "下一步操作："
    echo "  1. 检查配置: cat .env"
    echo "  2. 重启服务: docker-compose down && docker-compose up -d"
    echo "  3. 查看日志: docker-compose logs -f backend"
    echo ""
}

# 显示帮助信息
show_help() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BLUE}环境切换脚本使用说明${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "用法: ./switch-env.sh <命令>"
    echo ""
    echo "可用命令:"
    echo "  local       - 切换到开发环境"
    echo "  staging     - 切换到测试环境"
    echo "  production  - 切换到生产环境"
    echo "  status      - 查看当前环境状态"
    echo "  help        - 显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  ./switch-env.sh local       # 切换到开发环境"
    echo "  ./switch-env.sh status      # 查看当前环境"
    echo ""
    echo "环境说明:"
    echo "  local       - 本地开发环境（小内存、调试模式）"
    echo "  staging     - 测试环境（中等配置）"
    echo "  production  - 生产环境（高性能配置）"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

# 主逻辑
main() {
    local command=${1:-help}

    case "$command" in
        local|staging|production)
            switch_env "$command"
            ;;
        status)
            show_status
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
