import ast
# ── 永远不在字符串内写空格缩进! 只用 Ti 变量 = i*4 空格拼接 ──
def _s(n): return '    '*n

TI  = _s(1)   # 4
T0  = _s(1)   # 4
T1  = _s(2)   # 8
T2  = _s(3)   # 12
T3  = _s(4)   # 16
T4  = _s(5)   # 20

NEW_P1 = ''.join([
T0, 'banner = f"""\n',
'hello\n',
'"""\n',
T0, 'try:\n',
T1, '_ds_pid = 123\n',
T1, 'print(f"pid={_ds_pid}", flush=True)\n',
T0, 'except Exception as _diag_e:\n',
T1, 'print(f"err {_diag_e}", flush=True)\n',
T0, '_ds_attempt = 0\n',
T0, 'while True:\n',
T1, '_ds_attempt += 1\n',
T1, 'print(f"att={_ds_attempt}", flush=True)\n',
T1, 'try:\n',
T2, 'pass\n',
T1, 'except KeyboardInterrupt:\n',
T2, 'stop_msg = "ok"\n',
T2, 'break\n',
T1, 'except SystemExit as _ds_se:\n',
T2, 'raise\n',
T1, 'except BaseException as _ds_sf_e:\n',
T2, 'print("crash")\n',
T2, 'if _ds_attempt >= 5:\n',
T3, 'raise SystemExit(88)\n',
T2, 'print("3s retry")\n',
T2, 'try:\n',
T3, 'import time as _diag_tm; _diag_tm.sleep(3)\n',
T2, 'except (KeyboardInterrupt, SystemExit): pass\n',
T2, 'try:\n',
T3, 'print("rebind")\n',
T2, 'except Exception as _rebind_e:\n',
T3, 'print(f"fail {_rebind_e}", flush=True)\n',
T3, 'pass\n',
T0, 'print(f"loop end {_ds_attempt}", flush=True)\n',
T0, 'pass\n',
])

# PATCH3: 真实 do_GET 缩进一般是第 3 层 (def do_GET in class DarkSwordHandler in module = 12 spaces = T2)
#   而子句 if/子块 if 里还要再深 2 层 → T3/T4
S3  = _s(3)   # 12 (外层 do_GET body)
S3A = _s(4)   # 16 (if tpl_slug / try body)
S3B = _s(5)   # 20 (if tpl_slug body 内的 expires 赋值 = 还加 1 层)
NEW_P3 = ''.join([
S3,  "expires = ''\n",
S3,  'try:\n',
S3A, 'if tpl_slug:\n',
S3B, '    expires = "Expires=x"\n'.replace('    ', ''),   # BUG! 直接写 S3C =
S3A, 'if log_cid:\n',
S3B, 'pass\n',
S3A, 'if log_tid:\n',
S3B, 'pass\n',
S3,  'except Exception as _hf15v4_p3_e:\n',
S3A, 'try:\n',
S3B, 'pass\n',
S3A, 'except Exception:\n',
S3B, 'pass\n',
])
# 上面 S3B + '    expires' 的 BUG 样例! 正确写法:
S3C = _s(6)   # 24 (if tpl_slug: 下 1 层 = S3A + 1)
NEW_P3_CLEAN = ''.join([
S3,  "expires = ''\n",
S3,  'try:\n',
S3A, 'if tpl_slug:\n',
S3B, 'expires = "Expires=x"\n',                       # 正确: 不加字符串里的 '    '!
S3A, '    self.send_header("tpl")\n'.replace('    ', ''),  # 又写错了!
S3A, 'self.send_header("tpl=...")\n',                     # 正确: 只用 indent variable, 不字符串里硬塞 4 空格
])
NEW_P3 = ''.join([
S3,  "expires = ''\n",
S3,  'try:\n',
S3A, 'if tpl_slug:\n',
S3B, 'expires = "Expires=x"\n',
S3B, 'self.send_header("Set-Cookie", f"tpl=T; {expires}; SameSite=Lax")\n',
S3A, '# Preserve channel info\n',
S3A, 'if log_cid:\n',
S3B, 'self.send_header("Set-Cookie", f"ds_chid=1; Path=/; {expires}; SameSite=Lax")\n',
S3A, 'if log_tid:\n',
S3B, 'self.send_header("Set-Cookie", f"ds_tpid=1; Path=/; {expires}; SameSite=Lax")\n',
S3,  'except Exception as _hf15v4_p3_e:\n',
S3A, 'try:\n',
S3B, 'import admin.common as _ac15\n',
S3B, 'if _ac15 and hasattr(_ac15, "log_to_file"):\n',
S3C, '_ac15.log_to_file(f"[EXPIRES-FALLBACK] err={_hf15v4_p3_e}")\n',
S3B, 'else:\n',
S3C, 'print(f"[EXPIRES-FALLBACK] err={_hf15v4_p3_e}", flush=True)\n',
S3A, 'except Exception:\n',
S3B, 'pass\n',
])

PURGE = ''.join([
'\n',
T0, '# PURGE\n',
T0, 'try:\n',
T1, 'import subprocess as _ds_sp, signal as _ds_sg, os as _ds_os, time as _ds_tm\n',
T1, '_my_pid = _ds_os.getpid()\n',
T1, 'try:\n',
T2, '_ps_out = ""\n',
T1, 'except Exception:\n',
T2, '_ps_out = ""\n',
T1, '_kp = []\n',
T1, 'for _pln in []:\n',
T2, 'try:\n',
T3, '_p = 0\n',
T3, 'if True:\n',
T4, '_cmd = ""\n',
T4, 'if ("exploit" in _cmd):\n',
S3C = _s(6),
'',   # avoid unused
T5 = _s(6),
T5, '_kp.append(_p)\n',
T2, 'except Exception:\n',
T3, 'continue\n',
T1, 'if _kp:\n',
T2, 'print(f"PURGE={sorted(_kp)} self={_my_pid}", flush=True)\n',
T0, 'except Exception:\n',
T1, 'pass\n',
])

full_src = f'''
import os, time, sys, socket, signal, subprocess, urllib.parse
def main():
    class _Srv:
        def serve_forever(self, poll_interval=0.3): raise KeyboardInterrupt()
        def shutdown(self): pass
        def server_close(self): pass
    server = _Srv()
    args = type("A", (), {{"host":"0.0.0.0", "port":7070}})()
    PAYLOADS_DIR=TEMPLATES_DIR=EXFIL_DIR=LOG_FILE="/tmp/x"
    DB_AVAILABLE="YES"
    C2_HOST=None; REDIRECT_URL=None
    def log_to_file(m): print("L",m)
{PURGE}
{NEW_P1}
    return 0

class X:
    def send_header(self, a, b): pass
    def do_GET(self):
        tpl_slug = ""
        log_cid = 0
        log_tid = 0
{NEW_P3}
        return 0

main()
'''
try:
    ast.parse(full_src)
    compile(full_src, 'sim_hf15v4b.py', 'exec')
    # exec it too! (just mock, should exit clean)
    exec(full_src, {})
    print('✅ AST / COMPILE / EXEC PASS full mock')
    print('lines=', full_src.count('\n'))
except (SyntaxError, IndentationError) as e:
    print(type(e).__name__, 'L', e.lineno, 'off', e.offset, ':', e.msg)
    lines = full_src.split('\n')
    for i in range(max(0, e.lineno-6), min(len(lines), e.lineno+6)):
        print(f'  {i+1:4d}| {lines[i][:200]}')
except SystemExit:
    print('✅ SystemExit clean -> PASS (expected from KeyboardInterrupt / mock)')
except BaseException as e:
    print('EXEC EXCEPTION', type(e).__name__, str(e)[:300])
    import traceback; traceback.print_exc(limit=8)
