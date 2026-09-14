with open(r'd:\soft\ios-hacker\744-coruna\server\exploit_server.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'from admin.database import _parse_version_tuple' in line:
        lines[i] = '            from admin.database import _parse_version_tuple\n'
    elif 'ver = _parse_version_tuple(os_version)' in line:
        lines[i] = '            ver = _parse_version_tuple(os_version)\n'
    elif '# Legacy Coruna supports up to iOS 17.2 (1702)' in line:
        lines[i] = '            # Legacy Coruna supports up to iOS 17.2 (1702)\n'
    elif '# DarkSword is used for iOS 17.3+ (1703 and above)' in line:
        lines[i] = '            # DarkSword is used for iOS 17.3+ (1703 and above)\n'
    elif 'is_darksword = (ver is not None and ver > 1702)' in line:
        lines[i] = '            is_darksword = (ver is not None and ver > 1702)\n'
    elif 'host_hdr = self.headers.get("Host") or "127.0.0.1:7070"' in line:
        lines[i] = '            host_hdr = self.headers.get("Host") or "127.0.0.1:7070"\n'

with open(r'd:\soft\ios-hacker\744-coruna\server\exploit_server.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
