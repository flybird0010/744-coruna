# -*- coding: utf-8 -*-
"""
_v204_hotfix14v3.py ── 🔴 100% 精准算法: if __name__ 上一块反向扫描

hotfix14/14v2 的 2 个致命错误:
  (a) SF_LINE 扫到 hotfix13 残留的嵌套 server.serve_forever (缩进=4空格)
      → real_try_indent = max(0, 4-4) = 0!
      → 往回扫缩进=0 的 try: 找到文件头某 L39 (类导入后的 try/except 块)
      → 替换 L39 ~ L3954 → 几乎整文件被删 → ast.parse 缩进崩!
  (b) PATCH2 PURGE setsid 插入锚点 fallback 3500 导致插入不到位置(语法断)

修:
  PATCH1: 算法完全重写
    ① 先定 END_LINE = if __name__ == "__main__": 的 上 2 行
    ② 反向扫描 END_LINE-1 → END_LINE-80, 找缩进=8空格 的 "try:" 且下 1~20 行内出现 server.serve_forever
       → 这就是 main() 末尾那 try/except 块(保证 TRY_LINE 在 main 函数尾部, 缩进>0!)
    ③ SF_LINE = 从 TRY_LINE 向下扫描第 1 个 server.serve_forever() 行
    ④ END_LINE = 扫描 TRY_LINE 向下最近的 server.shutdown() 行 (找不到则用 ① END_LINE)
    ⑤ real_try_indent_str = TRY_LINE 行真实缩进
       real_sf_indent_str   = SF_LINE 行真实缩进
       except_indent_str    = real_sf_indent_str[:-4]  (缩进再退 4, 与 sf 外层 while 同级 = try 内部同级 except)
       要求 len(real_try_indent_str) >= 4  len(real_sf_indent_str) >= 8
  PATCH2: PURGE setsid 锚点完全重写
    ① 找 "if hasattr(os, 'setsid') and os.getpgrp() != os.getpid():" 行 = SETSID_IF_LINE
    ② 从 SETSID_IF_LINE 向下扫 15 行, 连续 2 行 "    except Exception: ..." 之后 + 1 空行之后才插 PURGE
       (保证插入位置在 setsid 整个 try/except 结构完全之外)
    ③ 不行 fallback 用 PREFLIGHT 之后 banner 之前 (startup_log= 行之前)
"""
import os, sys, time, shutil, ast, re

PROJ   = '/www/wwwroot/coruna/server'
ESFILE = os.path.join(PROJ, 'exploit_server.py')
BAKDIR = os.path.join(PROJ, 'bak_v204_hotfix14v3')
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
nlines = len(lines)
print(f'[INFO] total lines={nlines} ORIG_NL={ORIG_NL!r}')

def leading(ln: str) -> str:
    return ln[: len(ln) - len(ln.lstrip(' '))]

# ═══════════════════════════════════════════════════════════════
# PATCH1 重算法: 精准定位 main() 尾部 try: server.serve_forever
# ═══════════════════════════════════════════════════════════════
# Step ① END_LINE_candidate = if __name__ == "__main__": 上 2 行
NAME_MAIN_LINE = None
for i in range(nlines, 1, -1):
    ln = lines[i-1]
    if 'if __name__' in ln and '__main__' in ln:
        NAME_MAIN_LINE = i
        break
if not NAME_MAIN_LINE:
    print('[FATAL] 找不到 if __name__ == "__main__"!'); sys.exit(1)
END_LINE_0 = NAME_MAIN_LINE - 2
print(f'[PATCH1] if __name__ at L{NAME_MAIN_LINE}  → END_LINE_0 = L{END_LINE_0}')

# Step ② 反向扫描 [END_LINE_0-1 ... END_LINE_0-120] 找 缩进>=8 的 try: 且下面 20 行有 serve_forever
TRY_LINE = None
SF_LINE = None
for j in range(END_LINE_0 - 1, max(2, END_LINE_0 - 200), -1):
    ln = lines[j-1]
    if not ln.strip(): continue
    if ln.lstrip().startswith('#'): continue
    ind_str = leading(ln)
    ind_n   = len(ind_str)
    # 必须是 "try:" at main() function body 缩进 (应该是 8 或 4 空格)
    if not (4 <= ind_n <= 16): continue
    if not ln.rstrip().endswith('try:'): continue
    # 下面 20 行必须出现 server.serve_forever()
    found_sf = False
    sf_tmp = None
    for k in range(j+1, min(nlines, j+25)+1):
        lk = lines[k-1]
        if 'server.serve_forever()' in lk and not lk.lstrip().startswith('#'):
            found_sf = True; sf_tmp = k; break
    if not found_sf: continue
    # sf 缩进必须 >= try 缩进 + 4
    sf_ind_n = len(leading(lines[sf_tmp-1]))
    if sf_ind_n < ind_n + 4:
        continue
    # 确认这是正确的: sf_ind_n 应该在 8~16 之间 (至少 2 层缩进)
    if sf_ind_n < 8: continue
    TRY_LINE = j
    SF_LINE  = sf_tmp
    break

if TRY_LINE is None:
    print('[FATAL] PATCH1 TRY_LINE 扫描失败!'); sys.exit(1)

# Step ③ END_LINE_real = 从 SF_LINE 向下扫最近的 server.shutdown() 行
END_LINE_real = None
for j in range(SF_LINE+1, min(nlines, SF_LINE+40)+1):
    ln = lines[j-1]
    if 'server.shutdown()' in ln and not ln.lstrip().startswith('#'):
        END_LINE_real = j
        break
if END_LINE_real is None or END_LINE_real > END_LINE_0 + 5:
    END_LINE_real = END_LINE_0
    print(f'[PATCH1-WARN] END_LINE fallback 到 END_LINE_0={END_LINE_0}')

TRY_STR  = lines[TRY_LINE-1];  TRY_IND  = leading(TRY_STR);   TRY_IND_N  = len(TRY_IND)
SF_STR   = lines[SF_LINE-1];   SF_IND   = leading(SF_STR);    SF_IND_N   = len(SF_IND)
EXCEPT_IND_N = SF_IND_N - 4
if EXCEPT_IND_N < TRY_IND_N:
    EXCEPT_IND_N = TRY_IND_N
EXCEPT_IND = ' ' * EXCEPT_IND_N
REAL_SF_IND = SF_IND
print(f'[PATCH1] TRY_LINE=L{TRY_LINE} indent={TRY_IND_N}')
print(f'[PATCH1] SF_LINE =L{SF_LINE}  indent={SF_IND_N}')
print(f'[PATCH1] END_LINE=L{END_LINE_real}  (name_main L{NAME_MAIN_LINE})')
print(f'[PATCH1] EXCEPT indent = {EXCEPT_IND_N}')
if TRY_IND_N < 4 or SF_IND_N < 8:
    print(f'[FATAL] 缩进异常! TRY_IND_N={TRY_IND_N} SF_IND_N={SF_IND_N} (应 >=4 / >=8)')
    for ek in range(TRY_LINE-2, min(nlines, TRY_LINE+12)+1):
        print(f'  L{ek:4d}|{lines[ek-1][:140]}')
    sys.exit(1)

# Context dump
print(f'[PATCH1-CONTEXT] L{TRY_LINE} ~ L{min(nlines, END_LINE_real+2)}:')
for ek in range(TRY_LINE, min(nlines, END_LINE_real+2)+1):
    print(f'  L{ek:4d}|{lines[ek-1][:150]}')

# 组装 REPLACEMENT (缩进严格匹配)
TI = TRY_IND
SI = REAL_SF_IND
EI = EXCEPT_IND
REPLACEMENT = f'''{TI}# PATCH v20.4-HOTFIX14v3-P1: 永不返回. [DS-READY-HF14v3] 打印 + while True 重入 serve_forever.
{TI}_diag_pid  = os.getpid()
{TI}_diag_ppid = os.getppid()
{TI}_diag_pgid = os.getpgrp() if hasattr(os, "getpgrp") else -1
{TI}print(f"[DS-READY-HF14v3] pid={{_diag_pid}} ppid={{_diag_ppid}} pgid={{_diag_pgid}} args.port={{args.port}} → ENTER INFINITE serve_forever LOOP", flush=True)
{TI}sys.stdout.flush(); sys.stderr.flush()
{TI}import socket as _diag_sk
{TI}try:
{TI}    _diag_s  = _diag_sk.socket(_diag_sk.AF_INET, _diag_sk.SOCK_STREAM)
{TI}    _diag_rr = _diag_s.connect_ex(("127.0.0.1", int(args.port)))
{TI}    print(f"[DS-READY-HF14v3] 127.0.0.1:{{args.port}} self-connect_ex={{_diag_rr}} (0 = LISTEN OK!)", flush=True)
{TI}    _diag_s.close()
{TI}except Exception as _diag_ee:
{TI}    print(f"[DS-READY-HF14v3] self-connect probe ERR: {{type(_diag_ee).__name__}}: {{_diag_ee}}", flush=True)
{TI}_ds_attempt = 0
{TI}while True:
{TI}    _ds_attempt += 1
{TI}    print(f"[DS-SF-LOOP] attempt={{_ds_attempt}} → server.serve_forever(poll=0.3)", flush=True)
{TI}    try:
{SI}server.serve_forever(poll_interval=0.3)
{EI}except KeyboardInterrupt:
{SI}stop_msg = "Server stopped by user."
{SI}print(f"\\\\n[*] {{stop_msg}}")
{SI}try: log_to_file(stop_msg)
{SI}except Exception: pass
{SI}try: server.shutdown()
{SI}except Exception: pass
{SI}break
{EI}except SystemExit as _ds_se:
{SI}print(f"[DS-SF-EXIT] SystemExit(code={{_ds_se.code}}) → propagate.", flush=True)
{SI}try: log_to_file(f"[DS-SF-EXIT] SystemExit {{_ds_se.code}}")
{SI}except Exception: pass
{SI}raise
{EI}except BaseException as _ds_sf_e:
{SI}import traceback as _ds_tb
{SI}_ts = time.strftime("%Y-%m-%d %H:%M:%S")
{SI}_msg = f"[DS-CRASH-SF-{{_ds_attempt}}] [{{_ts}}] pid={{_diag_pid}} {{type(_ds_sf_e).__name__}}: {{_ds_sf_e}}"
{SI}print(_msg, flush=True)
{SI}try: log_to_file(_msg)
{SI}except Exception: pass
{SI}_ds_tb.print_exc()
{SI}if _ds_attempt >= 5:
{SI[:-4]}    print(f"[DS-CRASH-SF] serve_forever 连续崩溃 {{_ds_attempt}} 次 → 终止 SystemExit(88).", flush=True)
{SI[:-4]}    raise SystemExit(88)
{SI}print(f"[DS-CRASH-SF] 3s 后第 {{_ds_attempt+1}} 次重启 serve_forever loop...", flush=True)
{SI}try: time.sleep(3)
{SI[:-4]}except (KeyboardInterrupt, SystemExit): pass
{SI}try: server.shutdown()
{SI}except Exception: pass
{SI}try: server.server_close()
{SI}except Exception: pass
{SI}time.sleep(2)
{SI}try:
{SI[:-4]}    print(f"[DS-SF-REBIND] attempt {{_ds_attempt+1}} 重新 ReusableThreadingHTTPServer bind...", flush=True)
{SI[:-4]}    server = ReusableThreadingHTTPServer((args.host, args.port), DarkSwordHandler)
{SI}except Exception as _ds_rebind_err:
{SI[:-4]}    print(f"[DS-SF-REBIND] 失败: {{type(_ds_rebind_err).__name__}}: {{_ds_rebind_err}}. 2s 后循环再试", flush=True)
{SI[:-4]}    time.sleep(2)
{TI}print(f"[DS-SF-LOOP-END] (应该永远到不了这里, 除非 KeyboardInterrupt/SystemExit).", flush=True)
'''.rstrip('\n')
NEW_LINES = REPLACEMENT.split('\n')

# Slice 替换 lines
before_n = len(lines)
lines_new = lines[:TRY_LINE-1] + NEW_LINES + lines[END_LINE_real:]
assert len(lines_new) == before_n - (END_LINE_real - TRY_LINE + 1) + len(NEW_LINES), f"slice mismatch {len(lines_new)} vs expected"
lines = lines_new
print(f'[PATCH1] ✅ 替换 L{TRY_LINE}-L{END_LINE_real} ({END_LINE_real-TRY_LINE+1}行) → {len(NEW_LINES)}行  (现在 total lines={len(lines)})')
nlines = len(lines)

# ═══════════════════════════════════════════════════════════════
# PATCH2: [PREFLIGHT-PURGE] 杀残留 (精确定位 setsid try/except 结构的之后)
#   算法: 找 SETSID_IF_LINE = "if hasattr(os, 'setsid') ... getpgrp() != getpid():"
#         向后扫, 找到 "if" 所匹配的同级 "except Exception:" 行 (缩进与 SETSID_IF 同级)
#         再往后扫到 except Exception: 同级块的最后一个 pass/赋值行 → PURGE 锚 = 下一行
# ═══════════════════════════════════════════════════════════════
SETSID_IF_LINE = None
for i, ln in enumerate(lines, 1):
    if ('hasattr(os' in ln or 'hasattr(os,' in ln) and 'setsid' in ln and 'getpgrp' in ln and 'getpid' in ln):
        SETSID_IF_LINE = i; break
ANCHOR = None
if SETSID_IF_LINE:
    if_str = lines[SETSID_IF_LINE-1]; if_ind = leading(if_str); if_ind_n = len(if_ind)
    print(f'[PATCH2] SETSID_IF_LINE=L{SETSID_IF_LINE}  indent={if_ind_n}')
    # 向后找同级 except Exception 行
    EXC_LINE = None
    for j in range(SETSID_IF_LINE+1, min(nlines, SETSID_IF_LINE+25)+1):
        ln = lines[j-1]
        ind_s = leading(ln)
        if len(ind_s) == if_ind_n and ln.strip().startswith('except') and 'Exception' in ln:
            EXC_LINE = j; break
    if EXC_LINE:
        exc_ind_str = leading(lines[EXC_LINE-1])
        # 再从 EXC_LINE+1 开始, 往下缩进 > if_ind_n 的第一行空行 or 同级行之前 = except 块末尾
        for j in range(EXC_LINE+1, min(nlines, EXC_LINE+12)+1):
            ln = lines[j-1]
            if not ln.strip():
                ANCHOR = j; break
            inds = leading(ln)
            if len(inds) <= if_ind_n and ln.strip():
                ANCHOR = j; break
        if ANCHOR is None:
            ANCHOR = min(nlines, EXC_LINE+12)
if ANCHOR is None:
    # Fallback: banner = f""" 前一行
    for i in range(1, nlines+1):
        ln = lines[i-1]
        if ln.strip().startswith('banner = f"""') or (ln.strip().startswith('banner =') and 'Access URL' in ln):
            ANCHOR = max(1, i-1); print(f'[PATCH2-WARN] setsid fallback → banner 前 L{ANCHOR}'); break
if ANCHOR is None:
    ANCHOR = min(nlines, 3700)
    print(f'[PATCH2-EMERGENCY] ANCHOR fallback L{ANCHOR}')

# 取 ANCHOR 行缩进 (PURGE 块缩进要 >= ANCHOR 缩进至少 4 级? 不: PURGE 应该是在 main() 函数体内部, 与 setsid try/except 同级 = 8 或 4 空格)
anchor_ln = lines[ANCHOR-1] if 0 < ANCHOR <= nlines else ''
anchor_ind_s = leading(anchor_ln); anchor_ind_n = len(anchor_ind_s)
purge_ind_n = max(4, anchor_ind_n if 4 <= anchor_ind_n <= 12 else 8)
PI = ' ' * purge_ind_n
print(f'[PATCH2] ANCHOR=L{ANCHOR}  PURGE indent={purge_ind_n}')

PURGE = f'''{PI}# PATCH v20.4-HOTFIX14v3-P2: 100% 清理除 self 外所有 exploit_server.py 残留进程
{PI}try:
{PI}    import subprocess as _ds_sp, signal as _ds_sg
{PI}    _my_pid_now = os.getpid()
{PI}    try:
{PI}        _ps_out = _ds_sp.run(["pgrep", "-af", "exploit_server.py"],
{PI}                              stdout=_ds_sp.PIPE, stderr=_ds_sp.DEVNULL, timeout=4, check=False).stdout.decode("utf-8","ignore")
{PI}    except Exception:
{PI}        _ps_out = ""
{PI}    _kill_list = []
{PI}    for _pln in _ps_out.splitlines():
{PI}        try:
{PI}            _parts = _pln.split(None, 1)
{PI}            if not _parts: continue
{PI}            _pp = int(_parts[0])
{PI}            if _pp != _my_pid_now and _pp > 1 and _pp != os.getppid():
{PI}                _cmd = (_parts[1] if len(_parts) > 1 else '').lower()
{PI}                if ('exploit_server' in _cmd) and ('nginx' not in _cmd) and ('mysqld' not in _cmd):
{PI}                    _kill_list.append(_pp)
{PI}        except Exception:
{PI}            continue
{PI}    if _kill_list:
{PI}        print(f"[PREFLIGHT-PURGE] 🔴 清理残留 exploit_server.py PIDs={{sorted(_kill_list)}} (self={{_my_pid_now}})", flush=True)
{PI}        for _kp in _kill_list:
{PI}            try: os.kill(_kp, _ds_sg.SIGKILL)
{PI}            except Exception: pass
{PI}        time.sleep(1.5)
{PI}except Exception:
{PI}    pass
'''
PURGE_LINES = PURGE.split('\n')
lines = lines[:ANCHOR] + PURGE_LINES + lines[ANCHOR:]
nlines = len(lines)
print(f'[PATCH2] ✅ PURGE 插入 {len(PURGE_LINES)} 行 于 L{ANCHOR} 之后 (现在 total lines={nlines})')

# ═══════════════════════════════════════════════════════════════
# SYNTAX CHECK
# ═══════════════════════════════════════════════════════════════
src2 = '\n'.join(lines)
try:
    ast.parse(src2)
    print('[SYNTAX] ✅ ast.parse PASS')
except SyntaxError as e:
    print(f'[SYNTAX] ❌ FAIL L{e.lineno} off={e.offset}: {e.msg}')
    for ek in range(max(1, e.lineno-4), min(nlines, e.lineno+4)):
        print(f'  L{ek:4d}|{lines[ek-1][:160]}')
    shutil.copy2(bak, ESFILE)
    sys.exit(1)

# 写回
if ORIG_NL == b'\r\n':
    fb = src2.replace('\n', '\r\n').encode('utf-8')
else:
    fb = src2.encode('utf-8')
with open(ESFILE, 'wb') as f:
    f.write(fb)
NEW_SIZE = os.path.getsize(ESFILE)
print(f'[WRITE] before={ORIG_SIZE} after={NEW_SIZE} delta={NEW_SIZE-ORIG_SIZE:+d}')

# VERIFY markers
def gm(p):
    return sorted(set(1 + src2[:m.start()].count('\n') for m in re.finditer(p, src2, re.MULTILINE)))
print(f'[VERIFY] DS-READY-HF14v3    L={gm(r"DS-READY-HF14v3")}')
print(f'[VERIFY] DS-SF-LOOP         L={gm(r"DS-SF-LOOP")}')
print(f'[VERIFY] DS-CRASH-SF        L={gm(r"DS-CRASH-SF")}')
print(f'[VERIFY] PREFLIGHT-PURGE    L={gm(r"PREFLIGHT-PURGE")}')
print(f'[VERIFY] SystemExit\(88\)    L={gm(r"SystemExit\(88\)")}')
print(f'[VERIFY] CH-SAFE-302(hot12) L={gm(r"CH-SAFE-302-(OK|SKIP)")}')
old_ds_ready = gm(r"DS-READY[^-]")
print(f'[VERIFY] 重复 old DS-READY   L={old_ds_ready} (应 0!)')
if old_ds_ready:
    print('[VERIFY-WARN] 仍存在旧 [DS-READY] (hotfix13 残留), 需继续清理; 但新代码已经在 if __name__ 上方正确运行, 通常不会触发旧的')
print('✅ HOTFIX14v3 双 PATCH 完成!')
print()
print('👉 启动步骤:')
print('   pkill -9 -f exploit_server.py')
print('   fuser -k 7070/tcp 2>/dev/null ; sleep 3')
print('   ss -lntp | grep 7070 ; pgrep -af exploit_server.py  # 应都空!')
print('   export DS_SKIP_PREFLIGHT_SETSID=1')
print('   cd /www/wwwroot/coruna/server')
print('   nohup /www/server/pyporject_evn/versions/3.12.13/bin/python3 -u exploit_server.py -H 0.0.0.0 -p 7070 --no-port-80 > /tmp/exploit_server.log 2>&1 &')
print('   echo NEW_PID=$!; sleep 8')
print('   grep -nE "PREFLIGHT-PURGE|DS-READY-HF14v3|DS-SF-LOOP|self-connect_ex=|DS-CRASH-SF" /tmp/exploit_server.log')
print('   ss -lntp | grep -E ":7070|:7000|:80|:443"')
print('   curl -sS -o /dev/null -w "C1 test001    code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 8 http://127.0.0.1:7070/ch/test001')
print('   curl -sS -o /dev/null -w "C2 nonexist   code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 8 http://127.0.0.1:7070/ch/notexist_xyz')
print('   curl -sk -o /dev/null -w "C3 HTTPS t001 code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 15 https://aa1234.dpdns.org/ch/test001')
print('   curl -sk -o /dev/null -w "C4 HTTPS nex  code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 15 https://aa1234.dpdns.org/ch/notexist_xyz')
