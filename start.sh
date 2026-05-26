#!/bin/bash
# 行程小程序 - 启动脚本
# 启动本地服务器，并提供局域网访问地址

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${1:-8765}"

echo "=============================================="
echo "  📋 行程小程序 v2.0 - 实时同步版"
echo "=============================================="
echo ""
echo "  启动服务器..."
echo ""

# 切换到目录
cd "$SCRIPT_DIR"

# 检查 Python
if ! command -v python3 &>/dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3"
    exit 1
fi

# 启动服务器
python3 server.py "$PORT" &
SERVER_PID=$!
sleep 2

# 获取局域网 IP
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || ip addr show 2>/dev/null | grep 'inet ' | grep -v 127.0.0.1 | head -1 | awk '{print $2}' | cut -d/ -f1)
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="你的电脑IP"
fi

echo ""
echo "=============================================="
echo "  ✅ 服务器已启动！"
echo "=============================================="
echo ""
echo "  📱 本机访问（电脑）："
echo "     http://localhost:$PORT"
echo ""
echo "  📱 手机访问（同一WiFi）："
echo "     http://$LOCAL_IP:$PORT"
echo ""
echo "  👀 男朋友查看端："
echo "     http://$LOCAL_IP:$PORT/view.html"
echo ""
echo "  📝 管理端："
echo "     http://$LOCAL_IP:$PORT/admin.html"
echo ""
echo "  按 Ctrl+C 停止服务器"
echo "=============================================="
echo ""

# 防止 PHP session save path 警告干扰
# 等待并保持进程
trap "kill $SERVER_PID 2>/dev/null; echo '🛑 服务器已停止'" EXIT
wait $SERVER_PID
