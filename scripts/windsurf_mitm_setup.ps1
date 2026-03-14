# windsurf_mitm_setup.ps1
# Sets up mitmproxy as a system proxy and launches Windsurf through it
# so we can capture all Codeium/Windsurf API traffic.
#
# USAGE:
#   Step 1 — Run this script (sets proxy + starts mitmweb)
#   Step 2 — Log into Windsurf with a fresh account in the launched window
#   Step 3 — Use Windsurf Chat a few times to generate traffic
#   Step 4 — Press Ctrl+C in the mitmweb terminal when done
#   Step 5 — Run .\windsurf_restore_proxy.ps1 to remove proxy settings

$PROXY_HOST = "127.0.0.1"
$PROXY_PORT = 8080
$MITM_WEB_UI = "http://127.0.0.1:8081"
$CAPTURE_SCRIPT = "$PSScriptRoot\windsurf_capture.py"
$WINDSURF_EXE = "$env:LOCALAPPDATA\Programs\Windsurf\Windsurf.exe"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Windsurf MITM Capture Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# --- 1. Set system proxy ---
Write-Host "`n[1/4] Setting system proxy to $PROXY_HOST`:$PROXY_PORT ..." -ForegroundColor Yellow
$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
Set-ItemProperty -Path $regPath -Name ProxyEnable   -Value 1
Set-ItemProperty -Path $regPath -Name ProxyServer    -Value "${PROXY_HOST}:${PROXY_PORT}"
Set-ItemProperty -Path $regPath -Name ProxyOverride  -Value "localhost;127.0.0.1;<local>"
Write-Host "   System proxy set." -ForegroundColor Green

# --- 2. Set env vars for current session (catches apps that read env, not registry) ---
$env:HTTP_PROXY  = "http://${PROXY_HOST}:${PROXY_PORT}"
$env:HTTPS_PROXY = "http://${PROXY_HOST}:${PROXY_PORT}"
$env:NO_PROXY    = "localhost,127.0.0.1"

# --- 3. Start mitmweb (web UI) in background with our capture addon ---
Write-Host "`n[2/4] Starting mitmweb on port $PROXY_PORT ..." -ForegroundColor Yellow
Write-Host "   Web UI will be at: $MITM_WEB_UI" -ForegroundColor Green
Write-Host "   Traffic log:       $PSScriptRoot\windsurf_traffic.json" -ForegroundColor Green

$mitmJob = Start-Process -FilePath "mitmdump" `
    -ArgumentList `
        "--listen-host", $PROXY_HOST, `
        "--listen-port", $PROXY_PORT, `
        "--ssl-insecure", `
        "-s", "`"$CAPTURE_SCRIPT`"" `
    -PassThru -NoNewWindow

Write-Host "   mitmproxy PID: $($mitmJob.Id)" -ForegroundColor Green

# Wait for mitmproxy to start
Write-Host "   Waiting for mitmproxy to initialize..." -ForegroundColor DarkGray
Start-Sleep -Seconds 3

# --- 4. Trust the mitmproxy root CA ---
Write-Host "`n[3/4] Installing mitmproxy root cert into Windows trust store..." -ForegroundColor Yellow
$certPath = "$env:USERPROFILE\.mitmproxy\mitmproxy-ca-cert.cer"

if (Test-Path $certPath) {
    certutil -addstore -user "Root" "$certPath" | Out-Null
    Write-Host "   Certificate installed." -ForegroundColor Green
} else {
    Write-Host "   Cert not found at $certPath — mitmproxy may still be starting." -ForegroundColor Red
    Write-Host "   Try navigating to http://mitm.it in a browser to install it manually." -ForegroundColor Yellow
    # Retry after a moment
    Start-Sleep -Seconds 5
    if (Test-Path $certPath) {
        certutil -addstore -user "Root" "$certPath" | Out-Null
        Write-Host "   Certificate installed (retry)." -ForegroundColor Green
    }
}

# --- 5. Launch Windsurf with proxy env vars ---
Write-Host "`n[4/4] Launching Windsurf through proxy..." -ForegroundColor Yellow
if (Test-Path $WINDSURF_EXE) {
    Start-Process -FilePath $WINDSURF_EXE `
        -Environment @{
            HTTP_PROXY  = "http://${PROXY_HOST}:${PROXY_PORT}"
            HTTPS_PROXY = "http://${PROXY_HOST}:${PROXY_PORT}"
            NODE_TLS_REJECT_UNAUTHORIZED = "0"
        }
    Write-Host "   Windsurf launched." -ForegroundColor Green
} else {
    Write-Host "   ERROR: Windsurf.exe not found at $WINDSURF_EXE" -ForegroundColor Red
}

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host " NEXT STEPS:" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " 1. Sign into Windsurf with a fresh Gmail/GitHub account"
Write-Host " 2. Open Windsurf Chat (Ctrl+L) and send a few messages"
Write-Host " 3. Watch the traffic appear in this terminal"
Write-Host " 4. Traffic is saved to: windsurf_traffic.json"
Write-Host " 5. When done, run: .\windsurf_restore_proxy.ps1"
Write-Host ""
Write-Host " mitmproxy PID to kill when done: $($mitmJob.Id)" -ForegroundColor DarkGray
Write-Host ""

# Save PID for cleanup
$mitmJob.Id | Out-File "$PSScriptRoot\mitm_pid.txt"
