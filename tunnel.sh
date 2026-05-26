#!/bin/bash
# ==============================================
#  行程小程序 - 公网隧道（自动重连版）
#  用 localhost.run 免费 SSH 隧道，断了自动接回
# ==============================================

set -e

LOCAL_PORT="${1:-8765}"
TUNNEL_HOST="nokey@localhost.run"
REMOTE_PORT="80"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=============================================="
echo "  🌐 行程小程序 - 公网隧道（守护模式）"
echo "=============================================="
echo ""
echo "  本地端口: $LOCAL_PORT"
echo "  隧道服务: localhost.run（免费）"
echo "  断开自动重连，可长期运行"
echo ""
echo "  按 Ctrl+C 停止"
echo "=============================================="
echo ""

RECONNECT_DELAY=5
MAX_DELAY=60
CONNECT_COUNT=0

while true; do
    CONNECT_COUNT=$((CONNECT_COUNT + 1))
    
    echo -e "${GREEN}[$(date '+%H:%M:%S')] 正在建立隧道 (第 $CONNECT_COUNT 次)...${NC}"
    
    # SSH 隧道，带 keepalive 防止空闲断开
    ssh -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=3 \
        -o ConnectTimeout=10 \
        -o TCPKeepAlive=yes \
        -o ExitOnForwardFailure=yes \
        -tt \
        -R ${REMOTE_PORT}:localhost:${LOCAL_PORT} \
        ${TUNNEL_HOST} 2>&1
    
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ] || [ $EXIT_CODE -eq 130 ]; then
        # 正常退出（Ctrl+C）
        echo ""
        echo -e "${YELLOW}🛑 隧道已手动停止${NC}"
        exit 0
    fi
    
    echo ""
    echo -e "${RED}[$(date '+%H:%M:%S')] ⚠️  隧道断开（退出码: $EXIT_CODE），${RECONNECT_DELAY}秒后重连...${NC}"
    sleep $RECONNECT_DELAY
    
    # 递增等待时间，最多60秒
    RECONNECT_DELAY=$(( (RECONNECT_DELAY * 4) / 3 ))
    if [ $RECONNECT_DELAY -gt $MAX_DELAY ]; then
        RECONNECT_DELAY=$MAX_DELAY
    fi
done
