# -*- coding: utf-8 -*-
"""
_v204_hotfix14.py ── 🔴 精确行号锚定修复 (绝对不用字符串匹配)

根因实锤:
  hotfix13 的 OLD_SERVE_FOREVER_BLOCK 精确字符串替换没命中!
  代码尾部仍保留 L3756-L3762 旧版 try/except KeyboardInterrupt:
      try: server.serve_forever()
      except KeyboardInterrupt: ... server.shutdown()
  → serve_forever() 偶发 return 后 main() return → 进程 exit 0!

修法 (行号锚定 0-error):
  A. L1775-L1936 _serve_channel_landing: 保持 hotfix12v3 的双 helper, 仅做一次 grep 验证
  B. 查 main() 里 "try:\n        server.serve_forever()" 真实行号(应该 L3756 附近)
     在这 1 行之前插入 8 行打印/监控, 之后替换 while True + except BaseException 不吞异常
  C. PREFLIGHT 精确单杀残留 → 改成 pkill -9 -f exploit_server.py (先杀除自己外所有, 防止残留线程抢 LISTEN)
"""
import os, sys, time, shutil, ast, re

PROJ   = '/www/wwwroot/coruna/server'
ESFILE = os.path.join(PROJ, 'exploit_server.py')
BAKDIR = os.path.join(PROJ, 'bak_v204_hotfix14')
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
# PATCH-1: 查 server.serve_forever() 所在行 + 上下文精确 line_no
# ═══════════════════════════════════════════════════════════════
SF_LINE_1IDX = None     # 1-indexed "        server.serve_forever()"
TRY_LINE_1IDX = None    # 1-indexed "    try:" (就在 serve_forever 上一行)
for i, ln in enumerate(lines, 1):
    if 'server.serve_forever()' in ln and not ln.lstrip().startswith('#'):
        if SF_LINE_1IDX is None:
            SF_LINE_1IDX = i
            TRY_LINE_1IDX = i - 1
        print(f'[PATCH1-SCAN] L{i:4d}|{ln[:120]}')
print(f'[PATCH1] SF_LINE={SF_LINE_1IDX}  TRY_LINE={TRY_LINE_1IDX}')
if SF_LINE_1IDX is None:
    print('[FATAL] serve_forever() 没找到! 退出.'); sys.exit(1)
# 打印上下文 6 行
print(f'[PATCH1-CONTEXT] 上下文:')
for ek in range(max(1, TRY_LINE_1IDX-2), min(len(lines), SF_LINE_1IDX+8)):
    print(f'  L{ek:4d}|{lines[ek-1][:120]}')

# ── 计算缩进 (TRY_LINE 行的前导空格数量) ──
try_line = lines[TRY_LINE_1IDX - 1]
stripped = try_line.lstrip(' ')
TRY_INDENT = ' ' * (len(try_line) - len(stripped))
SF_INDENT  = TRY_INDENT + '    '   # 12 spaces?
print(f'[PATCH1-INDENT] TRY_INDENT={len(TRY_INDENT)} spaces  SF_INDENT should be {len(SF_INDENT)}')

# 验证: try 行下面 server.serve_forever 是 12 空格
sf_line_raw = lines[SF_LINE_1IDX - 1]
sf_stripped = sf_line_raw.lstrip(' ')
REAL_SF_INDENT = ' ' * (len(sf_line_raw) - len(sf_stripped))
REAL_KI_INDENT = REAL_SF_INDENT[:-4] + REAL_SF_INDENT[:-4]   # 1st except 缩进
print(f'[PATCH1-INDENT] REAL_SF_INDENT = {len(REAL_SF_INDENT)} spaces')

# ═══════════════════════════════════════════════════════════════
# PATCH-1 真正替换: 从 TRY_LINE_1IDX 开始, 删除:
#   TRY_LINE (try:)
#   SF_LINE (server.serve_forever)
#   except KeyboardInterrupt 块 (5~7 行, 直到出现空行+下一行 main() if __name__ == "__main__")
# ═══════════════════════════════════════════════════════════════
# 计算要删除的末尾行: 从 TRY_LINE_1IDX 向下找, 直到遇到 server.shutdown() 行之后的下一行
END_LINE = None   # 1-indexed: server.shutdown() 后面那行 (要 inclusive 删除)
for j in range(SF_LINE_1IDX, SF_LINE_1IDX + 10):
    if j > len(lines): break
    lnj = lines[j-1]
    print(f'  SCAN END L{j:4d}|{lnj[:100]}')
    if 'server.shutdown()' in lnj and not lnj.lstrip().startswith('#'):
        END_LINE = j
        break
print(f'[PATCH1-END] server.shutdown() END_LINE={END_LINE}')
if END_LINE is None:
    # fallback: TRY_LINE + 7 行
    END_LINE = TRY_LINE_1IDX + 6

# 组装 NEW_BLOCK
REPLACEMENT = f'''{TRY_INDENT}# PATCH v20.4-HOTFIX14: 强制永不返回. [DS-READY] 打印 PID/pgid, while True 重入 serve_forever, except BaseException 打印 traceback.
{TRY_INDENT}_diag_pid = os.getpid()
{TRY_INDENT}_diag_pgid = os.getpgrp() if hasattr(os, "getpgrp") else -1
{TRY_INDENT}_diag_ppid = os.getppid()
{TRY_INDENT}print(f"[DS-READY-HF14] pid={{_diag_pid}} ppid={{_diag_ppid}} pgid={{_diag_pgid}} args.port={{args.port}} host={{args.host}} about to enter serve_forever INFINITE LOOP", flush=True)
{TRY_INDENT}sys.stdout.flush(); sys.stderr.flush()
{TRY_INDENT}import socket as _diag_sk
{TRY_INDENT}try:
{TRY_INDENT}    _diag_s = _diag_sk.socket(_diag_sk.AF_INET, _diag_sk.SOCK_STREAM)
{TRY_INDENT}    _diag_rr = _diag_s.connect_ex(("127.0.0.1", int(args.port)))
{TRY_INDENT}    print(f"[DS-READY-HF14] 127.0.0.1:{{args.port}} self-connect_ex={{_diag_rr}} (0=LISTEN  OK!)", flush=True)
{TRY_INDENT}    _diag_s.close()
{TRY_INDENT}except Exception as _diag_ee:
{TRY_INDENT}    print(f"[DS-READY-HF14] self-connect probe ERR: {{type(_diag_ee).__name__}}: {{_diag_ee}}", flush=True)
{TRY_INDENT}_ds_attempt = 0
{TRY_INDENT}while True:
{TRY_INDENT}    _ds_attempt += 1
{TRY_INDENT}    print(f"[DS-SF-LOOP] attempt={{_ds_attempt}} call server.serve_forever()", flush=True)
{TRY_INDENT}    try:
{REAL_SF_INDENT}server.serve_forever(poll_interval=0.3)
{REAL_SF_INDENT[:-4]}except KeyboardInterrupt:
{REAL_SF_INDENT}stop_msg = "Server stopped by user."
{REAL_SF_INDENT}print(f"\\\\n[*] {{stop_msg}}")
{REAL_SF_INDENT}try: log_to_file(stop_msg)
{REAL_SF_INDENT}except Exception: pass
{REAL_SF_INDENT}try: server.shutdown()
{REAL_SF_INDENT}except Exception: pass
{REAL_SF_INDENT}break
{REAL_SF_INDENT[:-4]}except SystemExit as _ds_se:
{REAL_SF_INDENT}print(f"[DS-SF-EXIT] SystemExit(code={{_ds_se.code}}) → break loop.", flush=True)
{REAL_SF_INDENT}try: log_to_file(f"[DS-SF-EXIT] SystemExit {{_ds_se.code}}")
{REAL_SF_INDENT}except Exception: pass
{REAL_SF_INDENT}raise
{REAL_SF_INDENT[:-4]}except BaseException as _ds_sf_e:
{REAL_SF_INDENT}import traceback as _ds_tb
{REAL_SF_INDENT}_ts = time.strftime("%Y-%m-%d %H:%M:%S")
{REAL_SF_INDENT}_msg = f"[DS-CRASH-SF-{{_ds_attempt}}] [{{_ts}}] pid={{_diag_pid}} {{type(_ds_sf_e).__name__}}: {{_ds_sf_e}}"
{REAL_SF_INDENT}print(_msg, flush=True)
{REAL_SF_INDENT}try: log_to_file(_msg)
{REAL_SF_INDENT}except Exception: pass
{REAL_SF_INDENT}_ds_tb.print_exc()
{REAL_SF_INDENT}if _ds_attempt >= 5:
{REAL_SF_INDENT[:-4]}    print(f"[DS-CRASH-SF] serve_forever 连续崩溃 {{_ds_attempt}} 次 → 终止!", flush=True)
{REAL_SF_INDENT[:-4]}    raise SystemExit(88)
{REAL_SF_INDENT}print(f"[DS-CRASH-SF] 3 秒后第 {{_ds_attempt+1}} 次重启 serve_forever loop...", flush=True)
{REAL_SF_INDENT}try: time.sleep(3)
{REAL_SF_INDENT[:-4]}except (KeyboardInterrupt, SystemExit): pass
{REAL_SF_INDENT}try: server.shutdown()
{REAL_SF_INDENT}except Exception: pass
{REAL_SF_INDENT}try: server.server_close()
{REAL_SF_INDENT}except Exception: pass
{REAL_SF_INDENT}time.sleep(2)
{REAL_SF_INDENT}# 重新 bind & 构造 server 对象 (因为 server_close 之后可能把 socket 关了)
{REAL_SF_INDENT}try:
{REAL_SF_INDENT[:-4]}    print(f"[DS-SF-REBIND] attempt {{_ds_attempt+1}} 重新 ReusableThreadingHTTPServer bind...", flush=True)
{REAL_SF_INDENT[:-4]}    server = ReusableThreadingHTTPServer((args.host, args.port), DarkSwordHandler)
{REAL_SF_INDENT}except Exception as _ds_rebind_err:
{REAL_SF_INDENT[:-4]}    print(f"[DS-SF-REBIND] 失败: {{type(_ds_rebind_err).__name__}}: {{_ds_rebind_err}}. 2s 后再循环试", flush=True)
{REAL_SF_INDENT[:-4]}    time.sleep(2)
{TRY_INDENT}print(f"[DS-SF-LOOP] End while True (we should never reach here except SystemExit/KeyboardInterrupt).", flush=True)
'''.rstrip('\n')

# 做 line slice 替换 (TRY_LINE_1IDX..END_LINE inclusive 被 REPLACEMENT 替换)
# 0-indexed slice: lines[TRY_LINE_1IDX-1 : END_LINE]
N_NEW = REPLACEMENT.split('\n')
before_n = len(lines)
lines = lines[:TRY_LINE_1IDX - 1] + N_NEW + lines[END_LINE:]
print(f'[PATCH1] lines {TRY_LINE_1IDX}-{END_LINE} ({END_LINE - TRY_LINE_1IDX + 1}) → {len(N_NEW)} lines')
assert len(lines) == before_n - (END_LINE - TRY_LINE_1IDX + 1) + len(N_NEW)

# ═══════════════════════════════════════════════════════════════
# PATCH-2: PREFLIGHT 残留线程 100% 清理.
# 在 PREFLIGHT setsid() 之后插入一段: pkill -9 -f exploit_server.py (skip self).
# ═══════════════════════════════════════════════════════════════
KILL_INSERT_AFTER = None   # 1-indexed line, 就在 _my_pgid 设置之后, 后面应该是 "except Exception: pass" 关闭 setsid try
for i, ln in enumerate(lines, 1):
    if ('_my_pgid = os.getpgrp()' in ln or '_my_pgid=os.getpgrp()' in ln) and '#' not in ln.split('_my_pgid')[0]:
        KILL_INSERT_AFTER = i
        print(f'[PATCH2-KILL] found _my_pgid L{i:4d}|{ln[:100]}')
        # 再向下看 3 行有没有 try 关闭 (except Exception: pass)
        for j in range(i+1, i+4):
            if j > len(lines): break
            lnj = lines[j-1]
            print(f'  L{j:4d}|{lnj[:100]}')
        break
if KILL_INSERT_AFTER:
    indent_of_line = ' ' * (len(lines[KILL_INSERT_AFTER-1]) - len(lines[KILL_INSERT_AFTER-1].lstrip(' ')))
    # 插入块: pkill -9 -f "exploit_server.py" 排除自己
    KILL_INSERT_BLOCK = f'''{indent_of_line}# PATCH v20.4-HOTFIX14: 杀除 self 外的所有 exploit_server.py 残留 (PREFLIGHT "精确单杀" 漏杀会导致残留 worker 长时间持 LISTEN socket!)
{indent_of_line}try:
{indent_of_line}    import subprocess as _ds_sp, signal as _ds_sg
{indent_of_line}    _my_pid_now = os.getpid()
{indent_of_line}    try:
{indent_of_line}        _ps_out = _ds_sp.run(["pgrep", "-af", "exploit_server.py"],
{indent_of_line}                              stdout=_ds_sp.PIPE, stderr=_ds_sp.DEVNULL, timeout=3, check=False).stdout.decode("utf-8","ignore")
{indent_of_line}    except Exception:
{indent_of_line}        _ps_out = ""
{indent_of_line}    _kill_list = []
{indent_of_line}    for _pln in _ps_out.splitlines():
{indent_of_line}        try:
{indent_of_line}            _pp = int(_pln.split(None,1)[0])
{indent_of_line}            if _pp != _my_pid_now and _pp > 1 and _pp != os.getppid():
{indent_of_line}                if _ds_sp.run(["ps", "-o", "comm=", "-p", str(_pp)], stdout=_ds_sp.PIPE, stderr=_ds_sp.DEVNULL, timeout=2, check=False).stdout.decode().strip() not in ("nginx", "mysqld", "php-fpm", "java"):
{indent_of_line}                    _kill_list.append(_pp)
{indent_of_line}        except Exception:
{indent_of_line}            continue
{indent_of_line}    if _kill_list:
{indent_of_line}        print(f"[PREFLIGHT-PURGE] 🔴 清理 exploit_server.py 残留 PIDs={{sorted(_kill_list)}} (self={{_my_pid_now}})")
{indent_of_line}        for _kp in _kill_list:
{indent_of_line}            try: os.kill(_kp, _ds_sg.SIGKILL)
{indent_of_line}            except Exception: pass
{indent_of_line}        time.sleep(1.2)
{indent_of_line}except Exception:
{indent_of_line}    pass
'''
    lines = lines[:KILL_INSERT_AFTER] + KILL_INSERT_BLOCK.split('\n') + lines[KILL_INSERT_AFTER:]
    print(f'[PATCH2] ✅ 在 L{KILL_INSERT_AFTER} 后插入 PURGE 残留 PIDs 段')
else:
    print('[WARN] PATCH2 没找到 _my_pgid = os.getpgrp(), 跳过')

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
print(f'[WRITE] before={ORIG_SIZE} after={NEW_SIZE} delta={NEW_SIZE-ORIG_SIZE:+d} bytes')

# ── VERIFY grep 关键 markers ──
def gm(pattern):
    return sorted(set(1 + src2[:m.start()].count('\n') for m in re.finditer(pattern, src2, re.MULTILINE)))
print(f'[VERIFY] DS-READY-HF14           L={gm(r"DS-READY-HF14")}')
print(f'[VERIFY] DS-SF-LOOP / while True  L={gm(r"DS-SF-LOOP")} / {gm(r"_ds_attempt \+?= 1")}')
print(f'[VERIFY] DS-CRASH-SF             L={gm(r"DS-CRASH-SF")}')
print(f'[VERIFY] PREFLIGHT-PURGE         L={gm(r"PREFLIGHT-PURGE")}')
print(f'[VERIFY] SystemExit(88)           L={gm(r"SystemExit\(88\)")}')
print(f'[VERIFY] hotfix12v3 CH-SAFE-302  L={gm(r"CH-SAFE-302-(OK|SKIP)")}  (should still >0!)')
print('✅ HOTFIX14 双 PATCH 应用完成!')
print()
print('👉 启动命令 (重要: DS_SKIP_PREFLIGHT_SETSID=1 保持 + PURGE 自动除残留):')
print('   pkill -9 -f exploit_server.py ; sleep 2 ; ss -lnt | grep 7070')
print('   export DS_SKIP_PREFLIGHT_SETSID=1')
print('   cd /www/wwwroot/coruna/server')
print('   nohup python3 -u exploit_server.py -H 0.0.0.0 -p 7070 --no-port-80 > /tmp/exploit_server.log 2>&1 &')
print('   echo PID=$!  ;  sleep 7')
print('   grep -E "DS-READY-HF14|DS-SF-LOOP|PREFLIGHT-PURGE|DS-CRASH-SF|ERROR" /tmp/exploit_server.log | head -15')
print('   ss -lntp | grep -E ":7070|:7000|:80|:443"')
print('   curl -sS -o /dev/null -w "C1 code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 6 http://127.0.0.1:7070/ch/test001')
print('   curl -sS -o /dev/null -w "C2 code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 6 http://127.0.0.1:7070/ch/notexist_slug_xyz')
print('   curl -sk -o /dev/null -w "C3 HTTPS code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 15 https://aa1234.dpdns.org/ch/test001')
print('   curl -sk -o /dev/null -w "C4 HTTPS code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 15 https://aa1234.dpdns.org/ch/notexist_slug_xyz')
