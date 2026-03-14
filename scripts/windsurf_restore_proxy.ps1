# windsurf_restore_proxy.ps1
# Removes the mitmproxy system proxy settings set by windsurf_mitm_setup.ps1

Write-Host "Restoring system proxy settings..." -ForegroundColor Yellow

$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
Set-ItemProperty -Path $regPath -Name ProxyEnable -Value 0
Remove-ItemProperty -Path $regPath -Name ProxyServer   -ErrorAction SilentlyContinue
Remove-ItemProperty -Path $regPath -Name ProxyOverride -ErrorAction SilentlyContinue

$env:HTTP_PROXY  = ""
$env:HTTPS_PROXY = ""

# Kill mitmproxy if PID file exists
$pidFile = "$PSScriptRoot\mitm_pid.txt"
if (Test-Path $pidFile) {
    $pid = Get-Content $pidFile
    try {
        Stop-Process -Id $pid -Force
        Write-Host "Stopped mitmproxy (PID $pid)." -ForegroundColor Green
    } catch {
        Write-Host "mitmproxy already stopped." -ForegroundColor DarkGray
    }
    Remove-Item $pidFile
}

Write-Host "Done. Proxy settings restored." -ForegroundColor Green
