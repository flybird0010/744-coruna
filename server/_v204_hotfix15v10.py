#!/usr/bin/env python3
"""_v204_hotfix15v10.py — TINY TARGETED FIX: add 22 missing ds_* prefixes to SAFE_SAFARI_PREFIXES (exploit_server.py L1013).
"""
import os, sys, re, shutil, ast, py_compile, time as _bt

ESFILE = os.path.abspath(__file__).replace('_v204_hotfix15v10.py', 'exploit_server.py')
if not os.path.isfile(ESFILE):
    print(f'[FATAL] exploit_server.py missing at {ESFILE}'); sys.exit(1)

_self_src = open(__file__, 'r', encoding='utf-8').read()
try:
    ast.parse(_self_src)
    py_compile.compile(__file__, doraise=True)
    print('[SELF-AST-OK] hotfix15v10 self AST PASS')
except SyntaxError as e:
    print(f'[SELF-AST-FAIL] L{e.lineno} off={e.offset}: {e.msg}'); sys.exit(2)

src_b = open(ESFILE, 'rb').read()
ORIG_SIZE = len(src_b)
for ORIG_NL in (b'\r\n', b'\n', b'\r'):
    if ORIG_NL in src_b: break
else: ORIG_NL = b'\n'
src = src_b.decode('utf-8', errors='replace')
if ORIG_NL == b'\r\n': src = src.replace('\r\n', '\n')
lines = src.split('\n')
print(f'[INFO] lines={len(lines)} size={ORIG_SIZE}')

BAKDIR = os.path.join(os.path.dirname(ESFILE), 'bak_v204_hotfix15v10')
os.makedirs(BAKDIR, exist_ok=True)
bak = os.path.join(BAKDIR, f'exploit_server.py.bak-{_bt.strftime("%Y%m%d%H%M%S")}')
shutil.copy2(ESFILE, bak)
print(f'[BAK] {bak} ({ORIG_SIZE})')

OLD_ANCHOR_START = '            SAFE_SAFARI_PREFIXES = (\n'
OLD_ANCHOR_END   = '            filtered = []\n'
S = src.find(OLD_ANCHOR_START)
if S < 0:
    print('[FATAL] anchor SAFE_SAFARI_PREFIXES = ( NOT FOUND'); sys.exit(4)
E = src.find(OLD_ANCHOR_END, S + 100)
if E < 0:
    print('[FATAL] "filtered = []" after SAFE_SAFARI_PREFIXES NOT FOUND'); sys.exit(5)
L_s = 1 + src[:S].count('\n')
L_e = 1 + src[:E].count('\n')
OLD = src[S:E]
print(f'[PATCHX-LOC] SAFE_SAFARI_PREFIXES L{L_s}:{S} -> L{L_e}:{E} len={len(OLD)}')
if len(OLD) < 400 or len(OLD) > 4000:
    print(f'[FATAL] size bad {len(OLD)}'); sys.exit(6)

EXTRA_PREFIXES_LINES = (
    '                # v20.4-HF15v10: BROWSER-ONLY commands (web APIs, Safari sandbox compatible)\n'
    '                "ds_storage_grep", "ds_dom_screenshot", "ds_dom_query",\n'
    '                "ds_js_eval", "ds_reload_page", "ds_exec_cmd",\n'
    '                "ds_location_browser", "ds_apps_browser", "ds_wifi_browser",\n'
    '                "ds_clipboard_browser", "ds_photo_meta_browser", "ds_history_browser",\n'
    '                "ds_permissions_browser", "ds_battery_browser",\n'
    '                "ds_wallet_browser", "ds_keychain_browser", "ds_sms_browser",\n'
    '                "ds_contacts_browser", "ds_notes_browser", "ds_voice_memos_browser",\n'
    '                # v20.4-HF15v10: aliases\n'
    '                "ds_shot", "ds_dom", "ds_refresh", "ds_reload",\n'
)

# Insert EXTRA_PREFIXES_LINES right BEFORE the closing "            )\n            filtered = []\n"
# Find "                # misc" -> actually we want to insert before line: "                # misc" OR before the closing parenthesis tuple
# Simpler: Insert right after "# screenshot ... # misc" block -> before "                # misc" comment or just insert as new comment block before closing parenthesis
INJECT_MARKER = '                # misc\n'
if INJECT_MARKER in OLD:
    NEW = OLD.replace(INJECT_MARKER, EXTRA_PREFIXES_LINES + INJECT_MARKER)
else:
    # fallback: insert before ") tuple close"
    CLOSE_MARKER = '            )\n'
    NEW = OLD.replace(CLOSE_MARKER, EXTRA_PREFIXES_LINES + CLOSE_MARKER, 1)

if NEW == OLD:
    print('[FATAL] INJECT_MARKER / CLOSE_MARKER missing, noop'); sys.exit(7)

print(f'[PATCHX] replaced {len(OLD)} -> {len(NEW)} delta {len(NEW)-len(OLD):+}')
new_src = src[:S] + NEW + src[E:]

# Verify 4 inserted prefix lines exist
for probe in ('"ds_storage_grep"', '"ds_js_eval"', '"ds_dom_screenshot"', '"ds_reload_page"', '"ds_contacts_browser"', '"ds_clipboard_browser"'):
    if probe not in new_src:
        print(f'[FATAL] verify marker {probe} MISSING after patch'); sys.exit(8)
    print(f'[VERIFY] prefix marker {probe} inserted OK')

try:
    ast.parse(new_src)
    compile(new_src, 'es_new.py', 'exec')
    print('[FINAL AST] PASS hotfix15v10 complete AST/compile PASS')
except SyntaxError as e:
    print(f'[FINAL AST FAIL] L{e.lineno} off={e.offset}: {e.msg}')
    nlines = new_src.split('\n')
    for i in range(max(0, e.lineno-7), min(len(nlines), e.lineno+8)):
        print(f'  {i+1:5d}| {nlines[i][:220]}')
    sys.exit(9)

OUT = (new_src.encode('utf-8') if ORIG_NL != b'\r\n' else new_src.replace('\n', '\r\n').encode('utf-8'))
with open(ESFILE, 'wb') as fh: fh.write(OUT)
FINAL_SIZE = os.path.getsize(ESFILE)
print(f'[WRITE] {ORIG_SIZE} -> {FINAL_SIZE} (delta {FINAL_SIZE-ORIG_SIZE:+})')
print('[OK] HF15v10 SAFE_SAFARI_PREFIXES inject DONE')
