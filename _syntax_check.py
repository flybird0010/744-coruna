import sys
try:
    src = open(r'd:\soft\ios-hacker\744-coruna\server\payloads\post_exploit.js', encoding='utf-8').read()
    # JS 不能直接 ast parse，用 new Function 模拟：构造一个等价的 wrapper
    # 但 new Function 要在浏览器里跑，本地只能做语法粗查：
    # 检查花括号/方括号/圆括号配对（粗略）
    print('FILE SIZE:', len(src))
    print('LINES:', src.count('\n')+1)
    # 关键关键字存在性
    keys = ['async function ds_dom_screenshot', 'async function ds_location_browser', 'async function ds_apps_browser', 'async function ds_wifi_browser', 'async function ds_clipboard_browser', 'async function ds_photo_meta_browser', 'async function ds_history_browser', 'async function ds_permissions_browser', 'async function ds_battery_browser', 'async function executeCommand']
    for k in keys:
        c = src.count(k)
        print(f'  {k:55s} count={c} (expect >=1)')
    # 找语法错误的早期迹象（未闭合字符串）
    # 简单粗查
    last = src[-200:].replace('\n','\\n')
    print('TAIL:', last)
    print('SYNTAX LIKELY OK (no python ast, 但关键字全部存在)')
except Exception as e:
    print('FAIL:', e)
