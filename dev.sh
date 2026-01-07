#!/bin/bash
# =============================================================================
# 开发环境快速启动脚本
# =============================================================================
# 用法：
#   ./dev.sh start   - 启动开发环境
#   ./dev.sh stop    - 停止开发环境
#   ./dev.sh restart - 重启开发环境
#   ./dev.sh logs    - 查看日志
#   ./dev.sh build   - 重新构建
#   ./dev.sh shell   - 进入后端容器
#   ./dev.sh db      - 进入数据库
#   ./dev.sh clean   - 清理并重新开始
# =============================================================================

set -e

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Docker Compose 配置
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.dev.yml"

# 打印信息
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# 显示帮助
show_help() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BLUE}开发环境快速启动脚本${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "用法: ./dev.sh <命令>"
    echo ""
    echo "可用命令:"
    echo "  start    - 启动开发环境"
    echo "  stop     - 停止开发环境"
    echo "  restart  - 重启开发环境"
    echo "  logs     - 查看日志 (Ctrl+C 退出)"
    echo "  build    - 重新构建镜像"
    echo "  shell    - 进入后端容器 Shell"
    echo "  db       - 进入数据库 Shell"
    echo "  clean    - 清理并重新开始（删除所有数据）"
    echo "  status   - 查看服务状态"
    echo "  help     - 显示此帮助信息"
    echo ""
    echo "特点:"
    echo "  ✓ 代码热重载（修改即生效，无需重启）"
    echo "  ✓ 使用阿里云镜像源（国内加速）"
    echo "  ✓ 暴露所有端口（方便调试）"
    echo ""
    echo "访问地址:"
    echo "  Backend API: http://localhost:8000"
    echo "  API 文档:    http://localhost:8000/docs"
    echo "  Adminer:     http://localhost:8080"
    echo "  PostgreSQL:  localhost:5432"
    echo "  Redis:       localhost:6379"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

# 启动服务
start_service() {
    print_info "启动开发环境..."

    # 检查是否需要构建
    if ! docker images | grep -q "backend.*dev"; then
        print_warning "首次启动需要构建镜像..."
        docker-compose $COMPOSE_FILES build
    fi

    # 启动服务
    docker-compose $COMPOSE_FILES up -d

    print_success "开发环境已启动！"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}服务访问地址${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Backend API: http://localhost:8000"
    echo "  API 文档:    http://localhost:8000/docs"
    echo "  Adminer:     http://localhost:8080"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    print_info "查看日志: ./dev.sh logs"
    print_info "进入容器: ./dev.sh shell"
}

# 停止服务
stop_service() {
    print_info "停止开发环境..."
    docker-compose $COMPOSE_FILES down
    print_success "开发环境已停止"
}

# 重启服务
restart_service() {
    print_info "重启开发环境..."
    docker-compose $COMPOSE_FILES restart
    print_success "开发环境已重启"
}

# 查看日志
view_logs() {
    print_info "查看日志（按 Ctrl+C 退出）..."
    docker-compose $COMPOSE_FILES logs -f
}

# 重新构建
rebuild() {
    print_info "重新构建镜像..."
    docker-compose $COMPOSE_FILES build --no-cache
    print_success "构建完成"
}

# 进入后端容器
enter_shell() {
    print_info "进入后端容器 Shell..."
    docker-compose $COMPOSE_FILES exec backend bash
}

# 进入数据库
enter_db() {
    print_info "进入数据库 Shell..."
    docker-compose $COMPOSE_FILES exec db psql -U postgres -d app_dev
}

# 清理并重新开始
clean_restart() {
    print_warning "⚠️  警告：这将删除所有数据！"
    read -p "确定要继续吗？(y/N): " confirm

    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "已取消"
        exit 0
    fi

    print_info "停止并删除容器..."
    docker-compose $COMPOSE_FILES down -v

    print_info "重新构建..."
    docker-compose $COMPOSE_FILES build

    print_info "启动服务..."
    docker-compose $COMPOSE_FILES up -d

    print_success "环境已清理并重新启动"
}

# 查看状态
view_status() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BLUE}服务状态${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    docker-compose $COMPOSE_FILES ps
    echo ""
}

# 主逻辑
main() {
    local command=${1:-help}

    case "$command" in
        start)
            start_service
            ;;
        stop)
            stop_service
            ;;
        restart)
            restart_service
            ;;
        logs)
            view_logs
            ;;
        build)
            rebuild
            ;;
        shell)
            enter_shell
            ;;
        db)
            enter_db
            ;;
        clean)
            clean_restart
            ;;
        status)
            view_status
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
