import subprocess, sys, json
fp = r'd:\soft\ios-hacker\744-coruna\server\payloads\post_exploit.js'
# 方法 1: 用 node --check
try:
    r = subprocess.run(['node', '--check', fp], capture_output=True, text=True, timeout=30)
    print('NODE --check exit_code:', r.returncode)
    if r.stdout: print('STDOUT:', r.stdout[:500])
    if r.stderr: print('STDERR:', r.stderr[:1500])
except FileNotFoundError as e:
    print('Node not installed locally, fallback to esprima python lib')
    try:
        import esprima
        src = open(fp, encoding='utf-8').read()
        esprima.parseScript(src)
        print('ESPRIMA OK')
    except ImportError:
        print('No esprima; trying acorn')
        try:
            import acorn
            src = open(fp, encoding='utf-8').read()
            acorn.parse(src, ecma='latest')
            print('ACORN OK')
        except ImportError:
            print('No acorn either. Skipping strict JS parse. Just checking structure.')
            src = open(fp, encoding='utf-8').read()
            print('SIZE:', len(src))
            # 关键 case 关键字
            for kw in ['ds_dom_screenshot', 'ds_storage_grep', 'ds_location_browser', 'ds_apps_browser', 'ds_wifi_browser', 'ds_clipboard_browser', 'ds_photo_meta_browser', 'ds_history_browser', 'ds_permissions_browser', 'ds_battery_browser', 'html2canvas', 'toDataURL', 'navigator.geolocation', 'navigator.clipboard', 'navigator.mediaDevices', 'navigator.permissions', 'navigator.connection', 'navigator.getBattery']:
                cnt = src.count(kw)
                print(f'  {kw:30s} count={cnt}')
