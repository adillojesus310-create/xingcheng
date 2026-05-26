#!/bin/bash
# ==============================================
#  行程小程序 - 公网模式 (bore 隧道版)
#  bore 比 SSH 隧道稳定，自动重连，长期可用
# ==============================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_PORT="${1:-8765}"
BORE_BIN="/home/sevengali/bore"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "=============================================="
echo "  📋 行程小程序 - 公网模式（bore 隧道）"
echo "=============================================="
echo ""

# ── 检查 bore ──
if [ ! -f "$BORE_BIN" ]; then
    echo -e "${RED}❌ 找不到 bore，正在安装...${NC}"
    curl -sL https://github.com/ekzhang/bore/releases/download/v0.5.2/bore-v0.5.2-x86_64-unknown-linux-musl.tar.gz -o /tmp/bore.tar.gz
    cd /tmp && tar xzf bore.tar.gz
    cp bore "$BORE_BIN"
    chmod +x "$BORE_BIN"
    echo -e "${GREEN}✅ bore 安装完成${NC}"
fi

cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 正在关闭...${NC}"
    kill $SERVER_PID 2>/dev/null
    kill $BORE_PID 2>/dev/null
    rm -f /tmp/xingcheng_url.txt
    exit 0
}
trap cleanup INT TERM

# ── 1. 启动服务器 ──
echo "🔧 启动本地服务器 (端口 $LOCAL_PORT)..."
cd "$SCRIPT_DIR"
python3 server.py "$LOCAL_PORT" > /tmp/xingcheng_server.log 2>&1 &
SERVER_PID=$!
sleep 2

# 获取局域网 IP
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "你的电脑IP")

echo ""
echo "=============================================="
echo "  ✅ 服务器已启动"
echo "=============================================="
echo ""
echo "  📱 同一WiFi直接访问："
echo -e "     ${CYAN}http://$LOCAL_IP:$LOCAL_PORT${NC}          ← 你"
echo -e "     ${CYAN}http://$LOCAL_IP:$LOCAL_PORT/view.html${NC} ← 男朋友"
echo ""

# ── 2. 启动 bore 隧道 ──
echo "🌐 启动公网隧道..."
echo ""

RECONNECT_DELAY=3
MAX_DELAY=30
BORE_PID=""
TUNNEL_COUNT=0

while true; do
    TUNNEL_COUNT=$((TUNNEL_COUNT + 1))
    
    # 先杀掉旧的 bore 进程
    [ -n "$BORE_PID" ] && kill $BORE_PID 2>/dev/null
    
    # 启动 bore
    $BORE_BIN local "$LOCAL_PORT" --to bore.pub > /tmp/bore_output.log 2>&1 &
    BORE_PID=$!
    
    # 等待 bore 连接
    sleep 4
    
    # 提取端口和 URL
    REMOTE_PORT=$(grep -oP 'bore\.pub:\K\d+' /tmp/bore_output.log | tail -1)
    
    if [ -z "$REMOTE_PORT" ]; then
        # 可能没连上，重试
        echo -e "${RED}[$(date '+%H:%M:%S')] ⚠️  隧道连接失败，重试中...${NC}"
        sleep 2
        continue
    fi
    
    PUBLIC_URL="http://bore.pub:$REMOTE_PORT"
    echo "$PUBLIC_URL" > /tmp/xingcheng_url.txt
    
    echo -e "${GREEN}==============================================${NC}"
    echo -e "${GREEN}  🌐 公网地址（发给男朋友）：${NC}"
    echo -e "  ${CYAN}$PUBLIC_URL${NC}           ← 你的首页"
    echo -e "  ${CYAN}$PUBLIC_URL/view.html${NC}  ← 男朋友查看"
    echo -e "${GREEN}==============================================${NC}"
    echo ""
    echo "  💡 隧道运行中，断开自动重连"
    echo "  💡 当前公网地址已保存到 /tmp/xingcheng_url.txt"
    echo "  按 Ctrl+C 停止"
    echo ""
    
    # 等待 bore 进程结束（如果它死了就重连）
    wait $BORE_PID 2>/dev/null
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 130 ] || [ $EXIT_CODE -eq 143 ]; then
        cleanup
    fi
    
    echo ""
    echo -e "${YELLOW}[$(date '+%H:%M:%S')] 🔄 隧道断开，${RECONNECT_DELAY}秒后自动重连...${NC}"
    sleep $RECONNECT_DELAY
    
    # 递增等待
    RECONNECT_DELAY=$(( RECONNECT_DELAY + 3 ))
    [ $RECONNECT_DELAY -gt $MAX_DELAY ] && RECONNECT_DELAY=$MAX_DELAY
done
