# -*- coding: utf-8 -*-
"""
_v204_hotfix14v2.py ── 🔴 修复 hotfix14 的 2 个致命语法错误

2 个修复:
  1) PATCH2 PURGE 段不再插入 setsid 的 try/except 对内部(会打断导致 expected 'except')
     → 改为插在 setsid 整个 try/except 块之后 (下一行)
  2) PATCH1 server.shutdown() 扫描: hotfix13 残留代码里 server.serve_forever() 嵌套在 except break 内部
     → 原 END_LINE=None 扫描崩。改为从下往上扫最后一个 "server.shutdown()"
     → 若仍 None, 取 "if __name__ == \"__main__\":" 上一行作为 END_LINE
"""
import os, sys, time, shutil, ast, re

PROJ   = '/www/wwwroot/coruna/server'
ESFILE = os.path.join(PROJ, 'exploit_server.py')
BAKDIR = os.path.join(PROJ, 'bak_v204_hotfix14v2')
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
print(f'[INFO] total lines={len(lines)} ORIG_NL={ORIG_NL!r}')

# ═══════════════════════════════════════════════════════════════
# PATCH-1: 替换 main() 末尾 server.serve_forever 的 try/except 块
#   精确算法:
#     SF_LINE = 第 1 个非注释的 "server.serve_forever()" 行号
#     TRY_LINE = 扫描 SF_LINE 向上最近的 "try:"(缩进与 SF_LINE 缩进-4 一致)
#     END_LINE = 扫描 SF_LINE 向下最近的 "server.shutdown()" 行号
#              → 若找不到, 取 "if __name__ == \"__main__\":" 上一行
# ═══════════════════════════════════════════════════════════════
SF_LINE_1IDX = None
for i, ln in enumerate(lines, 1):
    if 'server.serve_forever()' in ln and not ln.lstrip().startswith('#'):
        SF_LINE_1IDX = i
        print(f'[PATCH1-SCAN] L{i:4d}|{ln[:130]}')
        break
if SF_LINE_1IDX is None:
    print('[FATAL] SF_LINE not found!'); sys.exit(1)

# 向上找 TRY: (缩进 = SF_LINE 缩进 - 4)
sf_l = lines[SF_LINE_1IDX-1]
sf_indent = len(sf_l) - len(sf_l.lstrip(' '))
try_indent = max(0, sf_indent - 4)
TRY_LINE = None
for j in range(SF_LINE_1IDX - 1, 1, -1):
    ln = lines[j-1]
    if not ln.strip(): continue
    if ln.lstrip().startswith('#'): continue
    ind = len(ln) - len(ln.lstrip(' '))
    if ind == try_indent and ln.rstrip().endswith('try:'):
        TRY_LINE = j
        break
print(f'[PATCH1] SF_LINE={SF_LINE_1IDX}(indent={sf_indent})  TRY_LINE={TRY_LINE}(indent={try_indent})')
if TRY_LINE is None:
    # fallback: SF_LINE - 1
    TRY_LINE = SF_LINE_1IDX - 1
    print(f'[PATCH1-WARN] TRY_LINE fallback to SF_LINE-1={TRY_LINE}')

# 向下找 server.shutdown() 最后一个
SHUTDOWN_LINES = []
for j in range(SF_LINE_1IDX, len(lines) + 1):
    ln = lines[j-1]
    if 'server.shutdown()' in ln and not ln.lstrip().startswith('#'):
        SHUTDOWN_LINES.append(j)
END_LINE = SHUTDOWN_LINES[-1] if SHUTDOWN_LINES else None
print(f'[PATCH1] SHUTDOWN_LINES={SHUTDOWN_LINES}  END_LINE(pre)={END_LINE}')
if END_LINE is None:
    # fallback: 找 if __name__ == "__main__":
    for j in range(SF_LINE_1IDX, len(lines) + 1):
        if 'if __name__' in lines[j-1] and '__main__' in lines[j-1]:
            END_LINE = j - 2  # 前 2 行(空行)
            print(f'[PATCH1-FALLBACK] if __name__ at L{j}, 取 END_LINE={END_LINE}')
            break
if END_LINE is None or END_LINE <= TRY_LINE:
    END_LINE = TRY_LINE + 10
    print(f'[PATCH1-EMERGENCY] END_LINE fallback {END_LINE}')
print(f'[PATCH1-CONTEXT] TRY_LINE={TRY_LINE} to END_LINE={END_LINE} (共 {END_LINE-TRY_LINE+1} lines):')
for ek in range(TRY_LINE, min(END_LINE+4, len(lines))+1):
    print(f'  L{ek:4d}|{lines[ek-1][:140]}')

# 取 TRY_LINE 行的真实前导空白
real_try_indent_str = ' ' * (len(lines[TRY_LINE-1]) - len(lines[TRY_LINE-1].lstrip(' ')))
real_sf_indent_str = ' ' * sf_indent
except_indent_str = real_sf_indent_str[:-4] + real_sf_indent_str[:-4]
if len(except_indent_str) < 8:
    except_indent_str = real_try_indent_str + '    '
print(f'[PATCH1-INDENT] try={len(real_try_indent_str)}  sf={len(real_sf_indent_str)}  except={len(except_indent_str)}')

REPLACEMENT = f'''{real_try_indent_str}# PATCH v20.4-HOTFIX14v2-PATCH1: 永不返回. [DS-READY-HF14v2] 打印 + while True 重入 + except BaseException 不吞 Traceback.
{real_try_indent_str}_diag_pid = os.getpid()
{real_try_indent_str}_diag_pgid = os.getpgrp() if hasattr(os, "getpgrp") else -1
{real_try_indent_str}_diag_ppid = os.getppid()
{real_try_indent_str}print(f"[DS-READY-HF14v2] pid={{_diag_pid}} ppid={{_diag_ppid}} pgid={{_diag_pgid}} args.port={{args.port}} host={{args.host}} → enter INFINITE serve_forever LOOP", flush=True)
{real_try_indent_str}sys.stdout.flush(); sys.stderr.flush()
{real_try_indent_str}import socket as _diag_sk
{real_try_indent_str}try:
{real_try_indent_str}    _diag_s = _diag_sk.socket(_diag_sk.AF_INET, _diag_sk.SOCK_STREAM)
{real_try_indent_str}    _diag_rr = _diag_s.connect_ex(("127.0.0.1", int(args.port)))
{real_try_indent_str}    print(f"[DS-READY-HF14v2] 127.0.0.1:{{args.port}} self-connect_ex={{_diag_rr}} (0 = LISTEN OK!)", flush=True)
{real_try_indent_str}    _diag_s.close()
{real_try_indent_str}except Exception as _diag_ee:
{real_try_indent_str}    print(f"[DS-READY-HF14v2] self-connect probe ERR: {{type(_diag_ee).__name__}}: {{_diag_ee}}", flush=True)
{real_try_indent_str}_ds_attempt = 0
{real_try_indent_str}while True:
{real_try_indent_str}    _ds_attempt += 1
{real_try_indent_str}    print(f"[DS-SF-LOOP] attempt={{_ds_attempt}} → server.serve_forever()", flush=True)
{real_try_indent_str}    try:
{real_sf_indent_str}server.serve_forever(poll_interval=0.3)
{except_indent_str}except KeyboardInterrupt:
{real_sf_indent_str}stop_msg = "Server stopped by user."
{real_sf_indent_str}print(f"\\\\n[*] {{stop_msg}}")
{real_sf_indent_str}try: log_to_file(stop_msg)
{real_sf_indent_str}except Exception: pass
{real_sf_indent_str}try: server.shutdown()
{real_sf_indent_str}except Exception: pass
{real_sf_indent_str}break
{except_indent_str}except SystemExit as _ds_se:
{real_sf_indent_str}print(f"[DS-SF-EXIT] SystemExit(code={{_ds_se.code}}) → propagate.", flush=True)
{real_sf_indent_str}try: log_to_file(f"[DS-SF-EXIT] SystemExit {{_ds_se.code}}")
{real_sf_indent_str}except Exception: pass
{real_sf_indent_str}raise
{except_indent_str}except BaseException as _ds_sf_e:
{real_sf_indent_str}import traceback as _ds_tb
{real_sf_indent_str}_ts = time.strftime("%Y-%m-%d %H:%M:%S")
{real_sf_indent_str}_msg = f"[DS-CRASH-SF-{{_ds_attempt}}] [{{_ts}}] pid={{_diag_pid}} {{type(_ds_sf_e).__name__}}: {{_ds_sf_e}}"
{real_sf_indent_str}print(_msg, flush=True)
{real_sf_indent_str}try: log_to_file(_msg)
{real_sf_indent_str}except Exception: pass
{real_sf_indent_str}_ds_tb.print_exc()
{real_sf_indent_str}if _ds_attempt >= 5:
{real_sf_indent_str[:-4]}    print(f"[DS-CRASH-SF] serve_forever 连续崩溃 {{_ds_attempt}} 次 → 终止! SystemExit(88)", flush=True)
{real_sf_indent_str[:-4]}    raise SystemExit(88)
{real_sf_indent_str}print(f"[DS-CRASH-SF] 3 秒后第 {{_ds_attempt+1}} 次重启 serve_forever loop...", flush=True)
{real_sf_indent_str}try: time.sleep(3)
{real_sf_indent_str[:-4]}except (KeyboardInterrupt, SystemExit): pass
{real_sf_indent_str}try: server.shutdown()
{real_sf_indent_str}except Exception: pass
{real_sf_indent_str}try: server.server_close()
{real_sf_indent_str}except Exception: pass
{real_sf_indent_str}time.sleep(2)
{real_sf_indent_str}try:
{real_sf_indent_str[:-4]}    print(f"[DS-SF-REBIND] attempt {{_ds_attempt+1}} 重新 bind...", flush=True)
{real_sf_indent_str[:-4]}    server = ReusableThreadingHTTPServer((args.host, args.port), DarkSwordHandler)
{real_sf_indent_str}except Exception as _ds_rebind_err:
{real_sf_indent_str[:-4]}    print(f"[DS-SF-REBIND] 失败: {{type(_ds_rebind_err).__name__}}: {{_ds_rebind_err}}. 2s 后循环再试", flush=True)
{real_sf_indent_str[:-4]}    time.sleep(2)
{real_try_indent_str}print(f"[DS-SF-LOOP-END] (应该永远到不了这里, 除非 KeyboardInterrupt/SystemExit).", flush=True)
'''.rstrip('\n')

N_NEW_LINES = REPLACEMENT.split('\n')
lines = lines[:TRY_LINE-1] + N_NEW_LINES + lines[END_LINE:]
print(f'[PATCH1] ✅ 替换 L{TRY_LINE}-L{END_LINE} ({END_LINE-TRY_LINE+1}行) → {len(N_NEW_LINES)}行')

# ═══════════════════════════════════════════════════════════════
# PATCH-2: [PREFLIGHT-PURGE] 杀残留.
#   精确找到 setsid 整个 try/except 块的"之后"第 1 行.
#   先找 "os.setsid()" 行号. 再向下找第一个 "except Exception: pass" 行 = SETSID_BLOCK_END
#   → 插入 SETSID_BLOCK_END 之后
# ═══════════════════════════════════════════════════════════════
SETSID_CALL_LINE = None
for i, ln in enumerate(lines, 1):
    if 'os.setsid()' in ln and not ln.lstrip().startswith('#'):
        SETSID_CALL_LINE = i
        print(f'[PATCH2-SCAN] os.setsid() at L{i:4d}|{ln[:100]}')
        break
SETSID_BLOCK_END = None
if SETSID_CALL_LINE:
    for j in range(SETSID_CALL_LINE, min(len(lines), SETSID_CALL_LINE + 15) + 1):
        ln = lines[j-1]
        # setsid try/except 块最后是 except Exception: pass (或 except Exception: xxx=0 之类)
        if ln.strip().startswith('except') and 'Exception' in ln:
            # 再看它后面是不是 pass / _my_pgid = 0
            nxt = lines[j] if j < len(lines) else ''
            if 'pass' in nxt or '_my_pgid' in nxt or '_my_ppid' in nxt:
                SETSID_BLOCK_END = j + 1 if 'pass' in nxt else j + 1
                # 如果 except 行本身包含 pass (one-liner)
                if 'pass' in ln:
                    SETSID_BLOCK_END = j
                print(f'[PATCH2-SCAN] except at L{j:4d}|{ln[:80]}  next L{j+1:4d}|{nxt[:80]}')
                print(f'[PATCH2]       SETSID_BLOCK_END (插入前的锚行) = {SETSID_BLOCK_END}')
                break
if SETSID_BLOCK_END is None:
    # fallback: setsid call + 10
    SETSID_BLOCK_END = (SETSID_CALL_LINE or 3490) + 10
    print(f'[PATCH2-WARN] 没精确找到 except,  fallback SETSID_BLOCK_END={SETSID_BLOCK_END}')
# 插入块缩进 = 取锚行缩进
anchor_line = lines[SETSID_BLOCK_END - 1] if 0 < SETSID_BLOCK_END <= len(lines) else ''
anchor_indent_n = len(anchor_line) - len(anchor_line.lstrip(' '))
if anchor_indent_n < 4:
    # fallback 主函数体缩进 4 空格
    anchor_indent_n = 4
IN2 = ' ' * anchor_indent_n
KILL_INSERT = f'''{IN2}# PATCH v20.4-HOTFIX14v2-PATCH2: 100% 清理除 self 外所有 exploit_server.py 残留进程/PIDs (避免残留 worker 持 LISTEN socket → 7070 c=000/52)
{IN2}try:
{IN2}    import subprocess as _ds_sp, signal as _ds_sg
{IN2}    _my_pid_now = os.getpid()
{IN2}    try:
{IN2}        _ps_out = _ds_sp.run(["pgrep", "-af", "exploit_server.py"],
{IN2}                              stdout=_ds_sp.PIPE, stderr=_ds_sp.DEVNULL, timeout=4, check=False).stdout.decode("utf-8","ignore")
{IN2}    except Exception:
{IN2}        _ps_out = ""
{IN2}    _kill_list = []
{IN2}    for _pln in _ps_out.splitlines():
{IN2}        try:
{IN2}            _parts = _pln.split(None, 1)
{IN2}            if not _parts:
{IN2}                continue
{IN2}            _pp = int(_parts[0])
{IN2}            if _pp != _my_pid_now and _pp > 1 and _pp != os.getppid():
{IN2}                _cmd = _parts[1] if len(_parts) > 1 else ''
{IN2}                if 'nginx' not in _cmd and 'mysqld' not in _cmd and 'php-fpm' not in _cmd:
{IN2}                    _kill_list.append(_pp)
{IN2}        except Exception:
{IN2}            continue
{IN2}    if _kill_list:
{IN2}        print(f"[PREFLIGHT-PURGE] 🔴 清理残留 exploit_server.py PIDs={{sorted(_kill_list)}} (self={{_my_pid_now}})", flush=True)
{IN2}        for _kp in _kill_list:
{IN2}            try: os.kill(_kp, _ds_sg.SIGKILL)
{IN2}            except Exception: pass
{IN2}        time.sleep(1.5)
{IN2}except Exception:
{IN2}    pass
'''
N_KILL = KILL_INSERT.split('\n')
lines = lines[:SETSID_BLOCK_END] + N_KILL + lines[SETSID_BLOCK_END:]
print(f'[PATCH2] ✅ 插入 PURGE 段 {len(N_KILL)}行 于 L{SETSID_BLOCK_END} 之后')

# ── ast.parse 校验 ──
src2 = '\n'.join(lines)
try:
    ast.parse(src2)
    print('[SYNTAX] ✅ ast.parse PASS')
except SyntaxError as e:
    print(f'[SYNTAX] ❌ FAIL L{e.lineno} off={e.offset}: {e.msg}')
    for ek in range(max(1, e.lineno-4), min(len(lines), e.lineno+4)):
        print(f'  L{ek:4d}|{lines[ek-1][:160]}')
    shutil.copy2(bak, ESFILE)
    sys.exit(1)

# ── 写回 ──
if ORIG_NL == b'\r\n':
    fb = src2.replace('\n', '\r\n').encode('utf-8')
else:
    fb = src2.encode('utf-8')
with open(ESFILE, 'wb') as f:
    f.write(fb)
NEW_SIZE = os.path.getsize(ESFILE)
print(f'[WRITE] before={ORIG_SIZE} after={NEW_SIZE} delta={NEW_SIZE-ORIG_SIZE:+d}')

# ── VERIFY grep markers ──
def gm(p):
    return sorted(set(1 + src2[:m.start()].count('\n') for m in re.finditer(p, src2, re.MULTILINE)))
print(f'[VERIFY] DS-READY-HF14v2         L={gm(r"DS-READY-HF14v2")}')
print(f'[VERIFY] DS-SF-LOOP              L={gm(r"DS-SF-LOOP")} (应 ≥1)')
print(f'[VERIFY] DS-CRASH-SF             L={gm(r"DS-CRASH-SF")}')
print(f'[VERIFY] PREFLIGHT-PURGE         L={gm(r"PREFLIGHT-PURGE")} (应 ≥1)')
print(f'[VERIFY] SystemExit(88)           L={gm(r"SystemExit\(88\)")} (应 ≥1)')
print(f'[VERIFY] CH-SAFE-302 (hotfix12v3 保持) L={gm(r"CH-SAFE-302-(OK|SKIP)")} (应 ≥2)')
print(f'[VERIFY] 重复 old [DS-READY] (非 -HF14v2) L={gm(r"DS-READY[^-]")} (应 0!)')
print('✅ HOTFIX14v2 双 PATCH 完成!')
print()
print('👉 启动步骤:')
print('   pkill -9 -f exploit_server.py')
print('   sleep 3 ; pgrep -af exploit_server.py  # 应空')
print('   ss -lntp | grep 7070  # 应空 (残留全清!)')
print('   export DS_SKIP_PREFLIGHT_SETSID=1')
print('   cd /www/wwwroot/coruna/server')
print('   nohup /www/server/pyporject_evn/versions/3.12.13/bin/python3 -u exploit_server.py -H 0.0.0.0 -p 7070 --no-port-80 > /tmp/exploit_server.log 2>&1 &')
print('   echo NEW_PID=$!; sleep 8')
print('   grep -E "PREFLIGHT-PURGE|DS-READY-HF14v2|DS-SF-LOOP|DS-CRASH-SF|self-connect_ex=0" /tmp/exploit_server.log  # 必须看到 3 条!')
print('   ss -lntp | grep -E ":7070|:7000|:80|:443"')
print('   curl -sS -o /dev/null -w "C1 code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 8 http://127.0.0.1:7070/ch/test001')
print('   curl -sS -o /dev/null -w "C2 code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 8 http://127.0.0.1:7070/ch/notexist_slug_xyz')
print('   curl -sk -o /dev/null -w "C3 HTTPS code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 15 https://aa1234.dpdns.org/ch/test001')
print('   curl -sk -o /dev/null -w "C4 HTTPS code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 15 https://aa1234.dpdns.org/ch/notexist_slug_xyz')
print()
print('👉 验收 3 个 grep marker 必须同时存在:')
print('   [PREFLIGHT-PURGE] 🔴 清理残留 exploit_server.py PIDs=[...] (self=XXX)')
print('   [DS-READY-HF14v2] pid=XXX ... → enter INFINITE serve_forever LOOP')
print('   [DS-SF-LOOP] attempt=1 → server.serve_forever()')
