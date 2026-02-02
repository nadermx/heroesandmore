#!/bin/bash
# HeroesAndMore Debug Script
# Usage: ./debug.sh [command]

SERVER="heroesandmore@174.138.33.140"
APP_LOGS="/home/www/heroesandmore/logs"
SYS_LOGS="/var/log/heroesandmore"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

show_help() {
    echo -e "${BLUE}HeroesAndMore Debug Script${NC}"
    echo ""
    echo "Usage: ./debug.sh [command] [options]"
    echo ""
    echo "Commands:"
    echo "  errors [n]       Show last n error log entries (default: 50)"
    echo "  stripe [n]       Show last n Stripe/payment log entries"
    echo "  app [n]          Show last n application log entries"
    echo "  celery [n]       Show last n Celery task log entries"
    echo "  security [n]     Show last n security log entries"
    echo "  api [n]          Show last n API log entries"
    echo "  db [n]           Show last n database log entries"
    echo "  web [n]          Show last n web server (gunicorn) entries"
    echo "  all              Show recent entries from all logs"
    echo "  status           Check service status"
    echo "  restart          Restart all services"
    echo "  deploy           Quick deploy (git pull + restart)"
    echo "  tail [log]       Live tail a log (errors|stripe|app|celery|web)"
    echo "  grep [pattern]   Search all logs for pattern"
    echo "  disk             Check disk space"
    echo "  ps               Show running processes"
    echo ""
    echo "Examples:"
    echo "  ./debug.sh errors 100      # Last 100 error entries"
    echo "  ./debug.sh tail stripe     # Live tail stripe log"
    echo "  ./debug.sh grep 'PermissionError'"
}

log_errors() {
    local lines=${1:-50}
    echo -e "${RED}=== ERRORS LOG (last $lines) ===${NC}"
    ssh $SERVER "sudo tail -$lines $APP_LOGS/errors.log 2>/dev/null || echo 'No errors logged yet'"
}

log_stripe() {
    local lines=${1:-50}
    echo -e "${YELLOW}=== STRIPE LOG (last $lines) ===${NC}"
    ssh $SERVER "sudo tail -$lines $APP_LOGS/stripe.log 2>/dev/null || echo 'No stripe logs yet'"
}

log_app() {
    local lines=${1:-50}
    echo -e "${GREEN}=== APP LOG (last $lines) ===${NC}"
    ssh $SERVER "sudo tail -$lines $APP_LOGS/app.log 2>/dev/null || echo 'No app logs yet'"
}

log_celery() {
    local lines=${1:-50}
    echo -e "${BLUE}=== CELERY TASKS LOG (last $lines) ===${NC}"
    ssh $SERVER "sudo tail -$lines $APP_LOGS/celery_tasks.log 2>/dev/null || echo 'No celery task logs yet'"
}

log_security() {
    local lines=${1:-50}
    echo -e "${RED}=== SECURITY LOG (last $lines) ===${NC}"
    ssh $SERVER "sudo tail -$lines $APP_LOGS/security.log 2>/dev/null || echo 'No security logs yet'"
}

log_api() {
    local lines=${1:-50}
    echo -e "${BLUE}=== API LOG (last $lines) ===${NC}"
    ssh $SERVER "sudo tail -$lines $APP_LOGS/api.log 2>/dev/null || echo 'No API logs yet'"
}

log_db() {
    local lines=${1:-50}
    echo -e "${YELLOW}=== DATABASE LOG (last $lines) ===${NC}"
    ssh $SERVER "sudo tail -$lines $APP_LOGS/db.log 2>/dev/null || echo 'No DB logs yet'"
}

log_web() {
    local lines=${1:-50}
    echo -e "${GREEN}=== WEB SERVER LOG (last $lines) ===${NC}"
    ssh $SERVER "sudo tail -$lines $SYS_LOGS/heroesandmore.log"
}

log_all() {
    echo -e "${RED}========== RECENT ERRORS ==========${NC}"
    ssh $SERVER "sudo tail -20 $APP_LOGS/errors.log 2>/dev/null | grep -v '^$' || echo 'None'"
    echo ""
    echo -e "${YELLOW}========== RECENT STRIPE ==========${NC}"
    ssh $SERVER "sudo tail -20 $APP_LOGS/stripe.log 2>/dev/null | grep -v '^$' || echo 'None'"
    echo ""
    echo -e "${GREEN}========== RECENT APP ==========${NC}"
    ssh $SERVER "sudo tail -20 $APP_LOGS/app.log 2>/dev/null | grep -v '^$' || echo 'None'"
    echo ""
    echo -e "${BLUE}========== RECENT CELERY ==========${NC}"
    ssh $SERVER "sudo tail -10 $SYS_LOGS/celery.log 2>/dev/null | grep -v '^$' || echo 'None'"
}

check_status() {
    echo -e "${BLUE}=== SERVICE STATUS ===${NC}"
    ssh $SERVER "sudo supervisorctl status"
    echo ""
    echo -e "${BLUE}=== NGINX STATUS ===${NC}"
    ssh $SERVER "sudo systemctl status nginx --no-pager -l | head -10"
    echo ""
    echo -e "${BLUE}=== REDIS STATUS ===${NC}"
    ssh $SERVER "sudo systemctl status redis --no-pager -l | head -5"
    echo ""
    echo -e "${BLUE}=== POSTGRES STATUS ===${NC}"
    ssh $SERVER "sudo systemctl status postgresql --no-pager -l | head -5"
}

do_restart() {
    echo -e "${YELLOW}Restarting services...${NC}"
    ssh $SERVER "sudo supervisorctl restart heroesandmore:*"
    echo -e "${GREEN}Done!${NC}"
}

do_deploy() {
    echo -e "${YELLOW}Deploying...${NC}"
    cd "$(dirname "$0")"
    /home/john/heroesandmore/venv/bin/ansible-playbook -i servers gitpull.yml
}

do_tail() {
    local log=${1:-errors}
    case $log in
        errors)  ssh $SERVER "sudo tail -f $APP_LOGS/errors.log" ;;
        stripe)  ssh $SERVER "sudo tail -f $APP_LOGS/stripe.log" ;;
        app)     ssh $SERVER "sudo tail -f $APP_LOGS/app.log" ;;
        celery)  ssh $SERVER "sudo tail -f $APP_LOGS/celery_tasks.log" ;;
        web)     ssh $SERVER "sudo tail -f $SYS_LOGS/heroesandmore.log" ;;
        security) ssh $SERVER "sudo tail -f $APP_LOGS/security.log" ;;
        api)     ssh $SERVER "sudo tail -f $APP_LOGS/api.log" ;;
        *)       echo "Unknown log: $log. Use: errors|stripe|app|celery|web|security|api" ;;
    esac
}

do_grep() {
    local pattern=$1
    if [ -z "$pattern" ]; then
        echo "Usage: ./debug.sh grep <pattern>"
        exit 1
    fi
    echo -e "${BLUE}Searching all logs for: $pattern${NC}"
    ssh $SERVER "sudo grep -r '$pattern' $APP_LOGS/ $SYS_LOGS/ 2>/dev/null | tail -50"
}

check_disk() {
    echo -e "${BLUE}=== DISK USAGE ===${NC}"
    ssh $SERVER "df -h | grep -E '/$|/home'"
    echo ""
    echo -e "${BLUE}=== LOG SIZES ===${NC}"
    ssh $SERVER "sudo du -sh $APP_LOGS $SYS_LOGS 2>/dev/null"
}

show_processes() {
    echo -e "${BLUE}=== HEROESANDMORE PROCESSES ===${NC}"
    ssh $SERVER "ps aux | grep -E 'gunicorn|celery|heroesandmore' | grep -v grep"
}

# Main
case ${1:-help} in
    errors)   log_errors $2 ;;
    stripe)   log_stripe $2 ;;
    app)      log_app $2 ;;
    celery)   log_celery $2 ;;
    security) log_security $2 ;;
    api)      log_api $2 ;;
    db)       log_db $2 ;;
    web)      log_web $2 ;;
    all)      log_all ;;
    status)   check_status ;;
    restart)  do_restart ;;
    deploy)   do_deploy ;;
    tail)     do_tail $2 ;;
    grep)     do_grep "$2" ;;
    disk)     check_disk ;;
    ps)       show_processes ;;
    help|*)   show_help ;;
esac
