import os
import glob
import re

target_dir = r'd:\soft\ios-hacker\744-coruna\server\admin'
files = glob.glob(os.path.join(target_dir, '**/*.py'), recursive=True)

for file in files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'get_client_ip(request)' in content:
        if 'from admin.utils.network import get_client_ip' not in content:
            content = 'from admin.utils.network import get_client_ip\n' + content
        
        # Replace complex ones first
        content = re.sub(r'request\.client\.host\s+if\s+request\.client\s+else\s+(None|["\']unknown["\'])', 'get_client_ip(request)', content)
        # Replace simple ones
        content = re.sub(r'request\.client\.host', 'get_client_ip(request)', content)
        
        with open(file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Updated {file}')
