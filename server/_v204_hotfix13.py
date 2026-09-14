# -*- coding: utf-8 -*-
"""
_v204_hotfix13.py ── 🔴 紧急修复 exploit_server.py 启动即死(exit_code=0 + 7070 LISTEN 几秒后消失)

根因推测 90%:
  PREFLIGHT 里 os.setsid() + signal(SIGTERM/SIGINT/SIGHUP, SIG_IGN). setsid() 后
  父 shell 的 nohup 或当前会话的 bash 发了 signal（即使 SIG_IGN），主线程在 main() 最后
  某个条件里调用了 sys.exit() / return，没真正跑到 server.serve_forever()。

修法:
  A. 新增环境变量 DS_SKIP_PREFLIGHT_SETSID=1 → 跳过 setsid()（保留信号忽略即可）
  B. main() L3756 server.serve_forever() 前强制 print('BEFORE', flush=True) 后 + 包 try/except BaseException (不吞 KeyboardInterrupt 之外的信号异常, 直接 print Traceback)
  C. banner 后 while True: server.serve_forever() 防偶发的 SystemExit 提前结束
"""
import os, sys, time, shutil, ast, re

PROJ   = '/www/wwwroot/coruna/server'
ESFILE = os.path.join(PROJ, 'exploit_server.py')
BAKDIR = os.path.join(PROJ, 'bak_v204_hotfix13')
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
print(f'[INFO] lines={len(lines)} ORIG_NL={ORIG_NL!r}')

# ═══════════════════════════════════════════════════════════════
# PATCH-A: L3489-L3492 setsid 块 → 外加 env DS_SKIP_PREFLIGHT_SETSID=1 跳过
# ═══════════════════════════════════════════════════════════════
# 找: if hasattr(os, 'setsid') and os.getpgrp() != os.getpid():
OLD_SETSID = '''        # setsid() 脱离当前 shell 的进程组 / 会话，bash 发 HUP / 面板杀 shell 进程组时带不到自己
        try:
            if hasattr(os, 'setsid') and os.getpgrp() != os.getpid():
                os.setsid()
                _my_pgid = os.getpgrp()
        except Exception:
            pass'''
NEW_SETSID = '''        # setsid() 脱离当前 shell 的进程组 / 会话，bash 发 HUP / 面板杀 shell 进程组时带不到自己
        # PATCH v20.4-HOTFIX13-A: 新增 DS_SKIP_PREFLIGHT_SETSID=1 跳过 setsid
        try:
            if int(os.environ.get('DS_SKIP_PREFLIGHT_SETSID', '0')):
                _my_pgid = os.getpgrp()
            elif hasattr(os, 'setsid') and os.getpgrp() != os.getpid():
                os.setsid()
                _my_pgid = os.getpgrp()
        except Exception:
            pass'''
if OLD_SETSID in src:
    src = src.replace(OLD_SETSID, NEW_SETSID, 1)
    print('[PATCH-A] ✅ setsid 条件开关已植入')
else:
    print('[WARN] PATCH-A setsid 精确替换未命中, 用正则')
    patA = re.compile(
        r'(\s*# setsid\(\) 脱离当前 shell 的进程组 / 会话[^\n]*\n'
        r'\s*try:\n'
        r'(\s*)if hasattr\(os, .setsid.\) and os\.getpgrp\(\) != os\.getpid\(\):\n'
        r'\s*os\.setsid\(\)\n'
        r'\s*_my_pgid = os\.getpgrp\(\)\n'
        r'\s*except Exception:\n'
        r'\s*pass\n)'
    )
    mA = patA.search(src)
    if not mA:
        print('[FATAL] PATCH-A regex 也未命中, 停止'); sys.exit(1)
    _iblk = mA.group(1)
    _sp = mA.group(2)  # 缩进空格
    rep = (
        f"{_sp}# PATCH v20.4-HOTFIX13-A: DS_SKIP_PREFLIGHT_SETSID=1 跳过 setsid\n"
        f"{_sp}try:\n"
        f"{_sp}    if int(os.environ.get('DS_SKIP_PREFLIGHT_SETSID', '0')):\n"
        f"{_sp}        _my_pgid = os.getpgrp()\n"
        f"{_sp}    elif hasattr(os, 'setsid') and os.getpgrp() != os.getpid():\n"
        f"{_sp}        os.setsid()\n"
        f"{_sp}        _my_pgid = os.getpgrp()\n"
        f"{_sp}except Exception:\n"
        f"{_sp}    pass\n"
    )
    src = src[:mA.start()] + rep + src[mA.end():]
    print('[PATCH-A] ✅ 正则版 setsid 开关已植入')

# ═══════════════════════════════════════════════════════════════
# PATCH-B: main() 尾部 try: server.serve_forever() 改成:
#   1) BEFORE 打印 (flush=True, 必打)
#   2) except BaseException 全量打印 traceback (不再让任何异常吞 exit_code=0)
#   3) KeyboardInterrupt 外异常后 sleep 3s (便于人类看日志, 否则 nohup 直接关)
#   4) while True 重入 serve_forever 防偶发 SystemExit
# ═══════════════════════════════════════════════════════════════
OLD_SERVE_FOREVER_BLOCK = '''    try:
        server.serve_forever()
    except KeyboardInterrupt:
        stop_msg = "Server stopped by user."
        print(f"\\n[*] {stop_msg}")
        log_to_file(stop_msg)
        server.shutdown()'''

NEW_SERVE_FOREVER_BLOCK = '''    # PATCH v20.4-HOTFIX13-B: 强制打印(flush=True) + except BaseException 不吞 traceback + while True 防 SystemExit
    _diag_pid = os.getpid()
    print(f"[DS-READY] pid={_diag_pid} pgid={os.getpgrp()} about to call server.serve_forever()...", flush=True)
    sys.stdout.flush(); sys.stderr.flush()
    _ds_sf_attempt = 0
    while True:
        _ds_sf_attempt += 1
        try:
            server.serve_forever()
            break
        except KeyboardInterrupt:
            stop_msg = "Server stopped by user."
            print(f"\\n[*] {stop_msg}")
            try: log_to_file(stop_msg)
            except Exception: pass
            try: server.shutdown()
            except Exception: pass
            break
        except BaseException as _ds_sf_e:
            import traceback as _ds_tb
            _msg = f"[DS-CRASH-SF-{_ds_sf_attempt}] pid={_diag_pid} {type(_ds_sf_e).__name__}: {_ds_sf_e}"
            print(_msg, flush=True)
            try: log_to_file(_msg)
            except Exception: pass
            _ds_tb.print_exc()
            try:
                time.sleep(3)
            except (KeyboardInterrupt, SystemExit):
                pass
            if _ds_sf_attempt >= 3:
                print(f"[DS-CRASH-SF] serve_forever 连续崩溃 {_ds_sf_attempt} 次, 停止重启.", flush=True)
                raise SystemExit(88)
            print(f"[DS-CRASH-SF] 3s 后第 {_ds_sf_attempt+1} 次重试 serve_forever...", flush=True)
            try: server.shutdown()
            except Exception: pass
            try: server.server_close()
            except Exception: pass
            time.sleep(2)'''

if OLD_SERVE_FOREVER_BLOCK in src:
    src = src.replace(OLD_SERVE_FOREVER_BLOCK, NEW_SERVE_FOREVER_BLOCK, 1)
    print('[PATCH-B] ✅ serve_forever 强固版已替换')
else:
    patB = re.compile(
        r'(\s*try:\s*\n\s*server\.serve_forever\(\)\s*\n'
        r'\s*except\s+KeyboardInterrupt\s*:\s*\n'
        r'\s*stop_msg\s*=\s*"Server stopped by user\."\s*\n'
        r'\s*print\([^\n]+\)\s*\n'
        r'\s*log_to_file\(stop_msg\)\s*\n'
        r'\s*server\.shutdown\(\))'
    )
    mB = patB.search(src)
    if not mB:
        print('[FATAL] PATCH-B 未命中 serve_forever 块, 停止'); sys.exit(1)
    src = src[:mB.start()] + NEW_SERVE_FOREVER_BLOCK + src[mB.end():]
    print('[PATCH-B] ✅ 正则版 serve_forever 强固已替换')

# ── ast.parse 校验 ──
try:
    ast.parse(src)
    print('[SYNTAX] ✅ ast.parse PASS')
except SyntaxError as e:
    print(f'[SYNTAX] ❌ L{e.lineno}: {e.msg} off={e.offset}')
    fl = src.split('\n')
    for ek in range(max(0,e.lineno-4), min(len(fl), e.lineno+4)):
        print(f'  L{ek+1:4d}|{fl[ek]}')
    shutil.copy2(bak, ESFILE)
    sys.exit(1)

# ── 写回 (还原 NL) ──
if ORIG_NL == b'\r\n':
    fb = src.replace('\n', '\r\n').encode('utf-8')
else:
    fb = src.encode('utf-8')
with open(ESFILE, 'wb') as f:
    f.write(fb)
NEW_SIZE = os.path.getsize(ESFILE)
print(f'[WRITE] before={ORIG_SIZE} after={NEW_SIZE} delta={NEW_SIZE-ORIG_SIZE:+d}')

# ── grep 验证 ──
def g(s, pat):
    return [1 + s[:m.start()].count('\n') for m in re.finditer(pat, s, re.MULTILINE)]
print(f'[VERIFY] DS_SKIP_PREFLIGHT_SETSID  L={g(src, r"DS_SKIP_PREFLIGHT_SETSID")}')
print(f'[VERIFY] DS-READY                 L={g(src, r"DS-READY")}')
print(f'[VERIFY] DS-CRASH-SF              L={g(src, r"DS-CRASH-SF")}')
print(f'[VERIFY] while True / attempt>=3  L={g(src, r"while True:")} / {g(src, r"attempt >= 3")}')
print('✅ HOTFIX13 应用成功!')
print()
print('👉 SSH 启动 (开 DS_SKIP_PREFLIGHT_SETSID=1 跳过 setsid 副作用):')
print('   pkill -9 -f exploit_server.py; sleep 2')
print('   cd /www/wwwroot/coruna/server')
print('   export DS_SKIP_PREFLIGHT_SETSID=1')
print('   nohup python3 -u exploit_server.py -H 0.0.0.0 -p 7070 --no-port-80 > /tmp/exploit_server.log 2>&1 &')
print('   echo PID=$!')
print('   sleep 5 ; ss -lnt | grep -E ":7070|:7000|:80|:443"')
print('   grep "DS-READY" /tmp/exploit_server.log  # 看真的到 serve_forever 前了吗?')
print('   tail -15 /tmp/exploit_server.log')
print()
print('👉 curl 验证 (都应为 200/302):')
print('   curl -sS -o /dev/null -w "code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 6 http://127.0.0.1:7070/ch/test001')
print('   curl -sS -o /dev/null -w "code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 6 http://127.0.0.1:7070/ch/notexist_slug')
print('   curl -sk -o /dev/null -w "code=%{http_code} loc=%{redirect_url} size=%{size_download}\\n" --max-time 12 https://aa1234.dpdns.org/ch/test001')
