#!/usr/bin/env python3
"""_v204_hotfix15v7.py — ONLY fix expires block (PATCH1 already applied by hotfix15v6).
NOTE: exploit_server.py already has PATCH1 (no-suicide) applied. This patch only modifies
the DO_GET expires UnboundLocalError block (L~2586-L~2594 original).
"""
import os, sys, re, shutil, ast, py_compile, time as _bt

ESFILE = os.path.abspath(__file__).replace('_v204_hotfix15v7.py', 'exploit_server.py')
if not os.path.isfile(ESFILE):
    print(f'[FATAL] exploit_server.py not found: {ESFILE}'); sys.exit(1)

# 0) self AST check
_self_src = open(__file__, 'r', encoding='utf-8').read()
try:
    ast.parse(_self_src)
    py_compile.compile(__file__, doraise=True)
    print('[SELF-AST-OK] hotfix15v7 self AST PASS')
except SyntaxError as e:
    print(f'[SELF-AST-FAIL] L{e.lineno} off={e.offset}: {e.msg}'); sys.exit(2)

# 1) read current file (it already has PATCH1 baked in — do NOT touch that)
src_b = open(ESFILE, 'rb').read()
ORIG_SIZE = len(src_b)
for ORIG_NL in (b'\r\n', b'\n', b'\r'):
    if ORIG_NL in src_b: break
else: ORIG_NL = b'\n'
src = src_b.decode('utf-8', errors='replace')
if ORIG_NL == b'\r\n':
    src = src.replace('\r\n', '\n')
lines = src.split('\n')
print(f'[INFO] ORIG_NL={ORIG_NL!r} total lines={len(lines)} size={ORIG_SIZE}')

# Backup
BAKDIR = os.path.join(os.path.dirname(ESFILE), 'bak_v204_hotfix15v7')
os.makedirs(BAKDIR, exist_ok=True)
bak = os.path.join(BAKDIR, f'exploit_server.py.bak-{_bt.strftime("%Y%m%d%H%M%S")}')
shutil.copy2(ESFILE, bak)
print(f'[BAK] {bak} (size={ORIG_SIZE})')

# 2) PATCH-EXPIRES: exact block based on CMD C actual structure:
#   if tpl_slug:
#       expires = "Expires=" + __import__("datetime").datetime.utcfromtimestamp(__import__("time").time() + 86400).strftime("%a, %d-%b-%Y %H:%M:%S GMT")
#       self.send_header("Set-Cookie", f"tpl={urllib.parse.quote(tpl_slug)}; Path=/; {expires}; SameSite=Lax")
#   # Preserve channel info for legacy Coruna
#   if log_cid:
#       self.send_header("Set-Cookie", f"ds_chid={log_cid}; Path=/; {expires}; SameSite=Lax")
#   if log_tid:
#       self.send_header("Set-Cookie", f"ds_tpid={log_tid}; Path=/; {expires}; SameSite=Lax")
#   self.end_headers()
#
# Strategy: find line with "ds_chid={log_cid}.*{expires}" (f-string + "ds_tpid={log_tid}.*{expires}" as anchors. Then expand
# start boundary backwards to "if tpl_slug:" and forward to "self.end_headers()".

# First: Locate all candidate regions via lines containing the EXACT two cookie strings
chid_re = re.compile(
    r'(?m)^(?P<indent> {12,20})if tpl_slug\s*:\s*\n'
    r'(?P=indent)    expires\s*=\s*"Expires="\s*\+\s*__import__\("datetime"\)\.datetime\.utcfromtimestamp\(.*?\.strftime\(.*?\)\s*\n'
    r'(?P=indent)    self\.send_header\("Set-Cookie",\s*f?"tpl=.*?\n'
    r'(?P=indent)#\s*Preserve\s+channel[^\n]*\n'
    r'(?P=indent)if\s+log_cid\s*:\s*\n'
    r'(?P=indent)    self\.send_header\("Set-Cookie",\s*f?"ds_chid=\{log_cid\}.*?\{expires\}.*?SameSite=Lax"\s*\)\s*\n'
    r'(?P=indent)if\s+log_tid\s*:\s*\n'
    r'(?P=indent)    self\.send_header\("Set-Cookie",\s*f?"ds_tpid=\{log_tid\}.*?\{expires\}.*?SameSite=Lax"\s*\)\s*\n'
    r'(?P=indent)self\.end_headers\(\)\s*\n',
    re.MULTILINE
)
matches = list(chid_re.finditer(src))
print(f'[PATCH3-LOC-STRICT] candidates: {len(matches)}')
if len(matches) == 1:
    m = matches[0]
else:
    # Fallback: use a looser regex — tpl_slug if line followed (ds_chid cookie + ds_tpid cookie)
    looser = re.compile(
        r'(?m)^(?P<indent> {12,20})if tpl_slug\s*:\s*\n'
        r'(?P=indent)    expires[^\n]*\n'
        r'(?P=indent)    self\.send_header\("Set-Cookie",[^\n]*tpl=[^\n]*\n'
        r'(?P=indent)#[^\n]*Preserve[^\n]*\n'
        r'(?P=indent)if\s+log_cid[^\n]*:\s*\n'
        r'(?P=indent)    self\.send_header\("Set-Cookie",[^\n]*ds_chid=[^\n]*SameSite=Lax"[^\n]*\)\s*\n'
        r'(?P=indent)if\s+log_tid[^\n]*:\s*\n'
        r'(?P=indent)    self\.send_header\("Set-Cookie",[^\n]*ds_tpid=[^\n]*SameSite=Lax"[^\n]*\)\s*\n'
        r'(?P=indent)self\.end_headers\(\)\s*\n',
        re.MULTILINE
    )
    matches = list(looser.finditer(src))
    print(f'[PATCH3-LOC-LOOSER] candidates: {len(matches)}')
    if len(matches) != 1:
        # FINAL fallback: line-number based approach (absolute last resort — from CMD C = original L2586-L2594):
        print('[PATCH3-LOC] falling back to LINE-BASED anchor. First print lines 2580-2600 of CURRENT src:')
        for ln in range(2579, min(2601, len(lines))):
            print(f'  L{ln+1:4d}| {lines[ln][:160]}')
        # Compute OFFSET: if tpl_slug: at line 2586 (index 2585):
        L_START = 2586
        # walk backward/forward: find actual "if tpl_slug:" around L2580-L2590 then "self.end_headers()" ~+10 lines
        a = None; z = None
        for li in range(max(0,L_START-15), min(len(lines), L_START+30)):
            if a is None and re.search(r'if\s+tpl_slug\s*:', lines[li]):
                # must have leading spaces 12-20
                if 12 <= len(lines[li]) - len(lines[li].lstrip()) <= 20:
                    a = li
            if a is not None and 'self.end_headers()' in lines[li] and (li - a) < 20:
                # check leading spaces match tpl indent
                ind_a = len(lines[a]) - len(lines[a].lstrip())
                ind_z = len(lines[li]) - len(lines[li].lstrip())
                if ind_z == ind_a:
                    z = li + 1  # exclusive, because end_headers line 本身算1行, 再加1变成exclusive (包含end_headers后换行)
                    break
        if a is None or z is None:
            print('[FATAL] cannot locate expires block even by line-fallback.'); sys.exit(4)
        # compute byte offsets in src:
        start_off = sum(len(x)+1 for x in lines[:a])  # lines[:a] = 所有行a-1之前的所有行字符长度+1换行
        end_off = start_off
        for li in range(a, z):
            end_off += len(lines[li]) + 1
        # (no indent capture; compute it
        indent_sp = len(lines[a]) - len(lines[a].lstrip())
        print(f'[PATCH3-LOC-FB] line-based a=L{a+1} z_before=L{z} (exclusive) indent={indent_sp}')
        # Fake a regex match object-ish tuple (span):
        class _M: pass
        m = _M()
        m.span = lambda: (start_off, end_off)
        m.group = lambda g, ind=indent_sp: ' ' * ind if g == 'indent' else src[start_off:end_off]
        OLD_P3 = src[start_off:end_off]
    else:
        m = matches[0]

_S = lambda n: '    ' * n
if 'OLD_P3' not in dir():
    OLD_P3 = m.group(0)
U3_N = len(m.group('indent'))
assert U3_N % 4 == 0
U3 = U3_N // 4
S3 = lambda lv: _S(U3 + lv - 1)
P3_START, P3_END = m.span()
print(f'[PATCH3-SELECT] start={P3_START} end={P3_END} len_old={len(OLD_P3)} indent_units={U3} (spaces={U3_N})')
print('[PATCH3 OLD block top 6 lines:')
for _i, _l in enumerate(OLD_P3.splitlines()[:6], 1):
    print(f'  OLD{_i:2d}| {_l[:180]}')
print('[PATCH3 OLD block bottom 6 lines:')
for _i, _l in enumerate(OLD_P3.splitlines()[-6:], 1):
    print(f'  OLD{_i:2d}| {_l[:180]}')

# Build NEW_P3: (exact same line structure)
NEW_P3 = (
    S3(1) + 'expires = ""\n'
    + S3(1) + 'try:\n'
    + S3(2) + 'if tpl_slug:\n'
    + S3(3) + 'try:\n'
    + S3(4) + 'expires = "Expires=" + __import__("datetime").datetime.utcfromtimestamp(__import__("time").time() + 86400).strftime("%a, %d-%b-%Y %H:%M:%S GMT")\n'
    + S3(4) + 'self.send_header("Set-Cookie", f"tpl={__import__(urllib.parse.quote(tpl_slug)}; Path=/; {expires}; SameSite=Lax")\n'
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

# NEW_P3 syntax self-test inside fake class
def _TEST_NEW_P3():
    fake_body = (
        'def _fake_do_GET(self):\n'
        '    import urllib.parse, time, datetime\n'
        '    tpl_slug=None; log_cid=2; log_tid=3\n'
        '    def send_header(self, *a): pass\n'
        '    def end_headers(self): pass\n'
        '    import sys\n'
        + NEW_P3
    )
    try:
        ast.parse(fake_body); compile(fake_body, '<p3>', 'exec')
        print('[PATCH3 NEW_P3 SYNTAX-SELFTEST] OK')
    except SyntaxError as e:
        print(f'[PATCH3 NEW_P3 SYNTAX-SELFTEST FAIL L{e.lineno} off={e.offset}: {e.msg}')
        mls = fake_body.split('\n')
        for k in range(max(0,e.lineno-6), min(len(mls), e.lineno+6)):
            print(f'  L{k+1:4d}| {mls[k][:200]}')
        shutil.copy2(bak, ESFILE); sys.exit(66)
_TEST_NEW_P3()

src = src[:P3_START] + NEW_P3 + src[P3_END:]
print(f'[PATCH3] replaced {len(OLD_P3)} chars -> {len(NEW_P3)} chars (delta {len(NEW_P3)-len(OLD_P3):+d})')
try:
    ast.parse(src); print('[PATCH3 AST] PASS')
except SyntaxError as e:
    print(f'[PATCH3 AST FAIL L{e.lineno} off={e.offset}: {e.msg}')
    mls = src.split('\n')
    for k in range(max(0,e.lineno-10), min(len(mls), e.lineno+10)):
        print(f'  L{k+1:4d}| {mls[k][:220]}')
    shutil.copy2(bak, ESFILE); sys.exit(7)

# FINAL AST + compile
try:
    ast.parse(src); compile(src, ESFILE, 'exec')
    print('[FINAL AST] PASS hotfix15v7 complete AST/compile both PASS')
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
print('[VERIFY] EXPIRES-FALLBACK   L=', gr(r'EXPIRES-FALLBACK'))
print('[VERIFY] DS-READY-HF15v6   L=', gr(r'DS-READY-HF15v6'))
print('[VERIFY] DS-SF-LOOP         L=', gr(r'DS-SF-LOOP'))
print('[VERIFY] PREFLIGHT-PURGE  L=', gr(r'PREFLIGHT-PURGE'))
print('\n✅ HF15v7 APPLY DONE (expires-fix only)')
