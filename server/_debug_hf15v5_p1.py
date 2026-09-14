import ast
_S = lambda n: '    '*n
U = 1
T = lambda lv: _S(U + lv - 1)

NEW_P1_PARTS = []
NEW_P1_PARTS.extend([
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
T(1), 'print(banner)\n',
T(1), 'startup_log = f"Exploit server started on http://{args.host}:{args.port} | DB={DB_AVAILABLE}"\n',
T(1), 'log_to_file(startup_log)\n',
T(1), 'import socket as _diag_sk, os as _diag_os, sys as _diag_sys, time as _diag_tm\n',
T(1), 'try:\n',
T(2), '_ds_pid = _diag_os.getpid()\n',
T(2), 'print(f"[DS-READY-HF15v5] pid={_ds_pid} port={args.port}", flush=True)\n',
T(2), '_s1 = _diag_sk.socket(_diag_sk.AF_INET, _diag_sk.SOCK_STREAM)\n',
T(2), '_rr = _s1.connect_ex(("127.0.0.1", int(args.port)))\n',
T(2), 'print(f"[DS-READY-HF15v5] self-connect_ex={_rr}", flush=True)\n',
T(2), '_s1.close()\n',
T(1), 'except Exception as _diag_e:\n',
T(2), 'print(f"[DS-READY-HF15v5] probe err {type(_diag_e).__name__}: {_diag_e}", flush=True)\n',
T(1), '_ds_attempt = 0\n',
T(1), 'while True:\n',
T(2), '_ds_attempt += 1\n',
T(2), 'print(f"[DS-SF-LOOP] attempt={_ds_attempt}", flush=True)\n',
T(2), 'try:\n',
T(3), 'server.serve_forever(poll_interval=0.3)\n',
T(2), 'except KeyboardInterrupt:\n',
T(3), 'stop_msg = "Stop by user."\n',
T(3), 'break\n',
T(2), 'except SystemExit as _ds_se:\n',
T(3), 'raise\n',
T(2), 'except BaseException as _ds_sf_e:\n',
T(3), 'import traceback as _ds_tb\n',
T(3), '_ts = _diag_tm.strftime("%Y-%m-%d %H:%M:%S")\n',
T(3), '_msg = f"[DS-CRASH-SF-{_ds_attempt}] [{_ts}] pid={_ds_pid} {type(_ds_sf_e).__name__}: {_ds_sf_e}"\n',
T(3), 'print(_msg, flush=True)\n',
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
T(1), 'server.shutdown()\n',
])
NEW_P1 = ''.join(NEW_P1_PARTS)

# Print NEW_P1 line-by-line with character-level indent info
lines = NEW_P1.splitlines()
print(f'NEW_P1 total lines in splitlines(): {len(lines)}')
for i, ln in enumerate(lines[:20], 1):
    print(f'  L{i:3d}: len={len(ln):3d} indent_spaces={len(ln)-len(ln.lstrip())} | {ln[:120]}')
print('  ...')
for i, ln in enumerate(lines[-25:], len(lines)-24):
    print(f'  L{i:3d}: len={len(ln):3d} indent_spaces={len(ln)-len(ln.lstrip())} | {ln[:120]}')

mock = (
    'def _mock_main():\n'
    '    import os, time, sys, socket\n'
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
    '    ReusableThreadingHTTPServer = None\n'
    '    DarkSwordHandler = None\n'
    + NEW_P1
)

print('\n=== AST parse mock ===')
try:
    tree = ast.parse(mock)
    compile(mock, '<m>', 'exec')
    print('OK: MOCK AST / compile PASS')
except SyntaxError as e:
    print(f'SYNTAX L{e.lineno} off={e.offset}: {e.msg}')
    mls = mock.split('\n')
    for i in range(max(0,e.lineno-8), min(len(mls), e.lineno+8)):
        print(f'  L{i+1:4d}| {mls[i][:220]}')
