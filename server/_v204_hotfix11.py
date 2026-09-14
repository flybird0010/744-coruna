# -*- coding: utf-8 -*-
"""
_v204_hotfix11.py  ─── 修复 /ch/<slug> 404 根因（ch_obj=None 没 fallback 302）

修法: 完全不用 regex (之前 9/10 失败原因)。改用 Python src.splitlines() 行号锚定 + 真实前导空白提取,
在 L=2407 ② 行前面插入 if ch_obj is None 块(每行严格 12 空格缩进,与 dev_uuid 赋值同层)。

执行: 上传服务器覆盖 /www/wwwroot/coruna/server/_v204_hotfix11.py
      python3 -m py_compile _v204_hotfix11.py && echo OK
      python3 _v204_hotfix11.py
"""

import os, sys, time, shutil, ast, traceback, re

PROJ   = '/www/wwwroot/coruna/server'
ESFILE = os.path.join(PROJ, 'exploit_server.py')
BAKDIR = os.path.join(PROJ, 'bak_v204_hotfix11')
os.makedirs(BAKDIR, exist_ok=True)

# ── 行号锚定 (0-indexed splitlines → 1-indexed) ──
TARGET_LINE = 2407   # ② 安全校验全部通过 → 才正式注册设备 + 递增访问量  这行
INSERT_BEFORE_LINE = TARGET_LINE  # 在 ② 这行前面插入 if ch_obj is None 块

# ── 备份 (覆盖前先备份原文件) ──
ts = time.strftime('%Y%m%d%H%M%S')
bak = os.path.join(BAKDIR, f'exploit_server.py.bak-{ts}')
shutil.copy2(ESFILE, bak)
print(f'[BAK] {bak} (size={os.path.getsize(ESFILE)})')

# ── 读源文件 (二进制读, 避免 Windows/Linux 换行错乱) ──
with open(ESFILE, 'rb') as f:
    src_bytes = f.read()

# 兼容 CRLF / LF
if src_bytes.count(b'\r\n') > src_bytes.count(b'\n') * 0.5:
    NL = b'\r\n'
else:
    NL = b'\n'

lines = src_bytes.split(NL)
print(f'[INFO] total lines={len(lines)} NL={NL!r}')

if len(lines) < INSERT_BEFORE_LINE:
    print(f'[FATAL] source has only {len(lines)} lines, INSERT_BEFORE_LINE={INSERT_BEFORE_LINE} out of range')
    sys.exit(1)

# ── 读 ② 行的真实前导空白 (从原始字节算, 不被注释 # 干扰) ──
target_line_bytes = lines[INSERT_BEFORE_LINE - 1]
# 字节级前导空白 = 从左到右连续 b' '
stripped = target_line_bytes.lstrip(b' ')
real_indent_bytes = target_line_bytes[:len(target_line_bytes) - len(stripped)]
real_indent = real_indent_bytes.decode('ascii', errors='replace')
INDENT = real_indent if real_indent else '            '   # fallback 12 空格
if not real_indent:
    # awk 之前给 0 (因为 # 注释被当 stripped), 用 12 空格兜底
    INDENT = '            '
    print(f'[INDENT] ⚠ target line starts with non-space (probably #), using fallback 12 spaces')
else:
    print(f'[INDENT] target line leading spaces = {len(real_indent)} (raw={real_indent!r})')

# ── 组装插入块 (每行严格 INDENT 缩进) ──
INSERT_BLOCK = f'''{INDENT}# PATCH v20.4-HOTFIX11: channels/TrafficChannel 表不存在或 slug 未注册时(ch_obj=None), fallback 强制 302 /e/group.html (17.2.0 及以下→ /e/index.html, 三处分流对齐 DARKSWORD_CUTOFF_FULL=170201)
{INDENT}if ch_obj is None:
{INDENT}    try:
{INDENT}        dev_uuid, log_cid, log_tid = self._ensure_device_registered(query_params)
{INDENT}        from admin.database import _parse_version_full, DARKSWORD_CUTOFF_FULL
{INDENT}        _osv, _, _, _, _, _, _ = parse_user_agent(user_agent)
{INDENT}        _vf = _parse_version_full(_osv) if _parse_version_full and _osv else None
{INDENT}        _isds = (_vf is None) or (_vf > DARKSWORD_CUTOFF_FULL)
{INDENT}        _hdr = self.headers.get('Host') or '127.0.0.1:7070'
{INDENT}        _sch = 'https' if (self.headers.get('X-Forwarded-Proto','')=='https' or self.headers.get('X-Forwarded-Ssl','')=='on') else 'http'
{INDENT}        _tgt = f"{{_sch}}://{{_hdr}}/e/group.html" if _isds else f"{{_sch}}://{{_hdr}}/e/index.html"
{INDENT}        self.send_response(302)
{INDENT}        self.send_header('Location', _tgt)
{INDENT}        self._write_ds_ids(channel_id=log_cid, template_id=log_tid)
{INDENT}        self.send_header('Cache-Control','no-store, no-cache, must-revalidate, max-age=0, private')
{INDENT}        self.send_header('Vary', 'User-Agent, X-Forwarded-Proto')
{INDENT}        self.end_headers()
{INDENT}        return
{INDENT}    except Exception as _chfallback:
{INDENT}        try: log_to_file(f'[CH-FALLBACK] err={{_chfallback}}')
{INDENT}        except Exception: pass
{INDENT}
'''

INSERT_BLOCK_BYTES = INSERT_BLOCK.encode('utf-8')

# ── 在 INSERT_BEFORE_LINE 前面插入 ──
new_lines = lines[:INSERT_BEFORE_LINE - 1] + INSERT_BLOCK_BYTES.split(NL) + lines[INSERT_BEFORE_LINE - 1:]

new_src_bytes = NL.join(new_lines)

# ── ast.parse 校验 ──
try:
    ast.parse(new_src_bytes.decode('utf-8', errors='replace'))
    print('[SYNTAX] ast.parse ✅ OK')
except SyntaxError as e:
    print(f'[SYNTAX] ❌ FAIL: {e.msg} line={e.lineno} offset={e.offset}')
    # 回滚
    shutil.copy2(bak, ESFILE)
    print(f'[ROLLBACK] restored from {bak}')
    sys.exit(1)

# ── 写回 ──
with open(ESFILE, 'wb') as f:
    f.write(new_src_bytes)

print(f'[WRITE] {ESFILE} (size before={os.path.getsize(bak)} after={os.path.getsize(ESFILE)})')
print(f'[FINAL RESULT] ✅ /ch/<slug> fallback 302 PATCHED at L={INSERT_BEFORE_LINE} (INDENT={len(INDENT)} spaces)')
