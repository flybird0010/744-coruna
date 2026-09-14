# -*- coding: utf-8 -*-
import sqlite3
c = sqlite3.connect('server/darksword.db')
cs = c.execute('PRAGMA table_info(command_scripts)').fetchall()
print('command_scripts columns:')
for r in cs: print(' ', r)
print()
rs = c.execute('SELECT * FROM command_scripts ORDER BY id ASC').fetchall()
cols = [x[1] for x in cs]
print('command_scripts total rows =', len(rs))
for r in rs:
    d = dict(zip(cols, r))
    name = d.get('name') or 'NULL_NAME'
    slug = d.get('slug') or 'NULL_SLUG'
    cat = d.get('category') or 'NULL_CAT'
    cmd = d.get('command') or ''
    if cmd is None: cmd = ''
    cmd_snippet = repr(cmd[:120]) if cmd else '(empty or null command content)'
    print(f'  id={d.get("id"):>3} | name={name!r:<24} | slug={slug!r:<24} | cat={cat!r:<12} | use_cnt={d.get("use_count")!r:<6} | command[:120]={cmd_snippet}')
print()
print('Now also check DS_CMD_ALIASES in post_exploit.js (command dispatch actions) + validate_command()白名单：')
import re
f = open('server/payloads/post_exploit.js', 'r', encoding='utf-8').read()
aliases = re.findall(r"'ds_[a-zA-Z0-9_]+'\s*:\s*\{[^}]*action\s*:\s*'([^']+)'", f)
print(f'  DS_CMD_ALIASES: total {len(aliases)} alias entries found')
print()
import subprocess
# 看 commands.py _validate_command 白名单：用 grep
