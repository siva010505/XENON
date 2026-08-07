<# 
.SYNOPSIS
    Install Browser Use native messaging host for Chrome
    
.DESCRIPTION
    This script registers the native messaging host manifest with Chrome on Windows.
    Run as Administrator for system-wide install, or without for user-only install.
    
.PARAMETER SystemWide
    Install for all users (requires Administrator). Default: Current user only.
    
.PARAMETER ChromeVersion
    Chrome version folder name (e.g., "Chrome", "Chrome Beta", "Chrome Dev", "Chrome Canary").
    Default: "Chrome"
#>

param(
    [switch]$SystemWide,
    [string]$ChromeVersion = "Chrome"
)

$ErrorActionPreference = "Stop"

# Get paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$hostDir = $scriptDir
$manifestPath = Join-Path $hostDir "manifest.json"
$bridgePath = Join-Path $hostDir "bridge.py"

# Verify files exist
if (-not (Test-Path $manifestPath)) {
    Write-Error "Manifest not found: $manifestPath"
    exit 1
}

if (-not (Test-Path $bridgePath)) {
    Write-Error "Bridge script not found: $bridgePath"
    exit 1
}

# Read manifest
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json

# Determine registry path
if ($SystemWide) {
    $regPath = "HKLM:\SOFTWARE\Google\$ChromeVersion\NativeMessagingHosts"
    Write-Host "Installing system-wide (requires Administrator)..."
} else {
    $regPath = "HKCU:\SOFTWARE\Google\$ChromeVersion\NativeMessagingHosts"
    Write-Host "Installing for current user..."
}

# Create registry key if needed
if (-not (Test-Path $regPath)) {
    New-Item -Path $regPath -Force | Out-Null
}

# Create host key
$hostName = $manifest.name
$hostRegPath = Join-Path $regPath $hostName
New-Item -Path $hostRegPath -Force | Out-Null

# Set manifest path (use absolute path)
$absManifestPath = Resolve-Path $manifestPath
Set-ItemProperty -Path $hostRegPath -Name "(default)" -Value $absManifestPath -Type String -Force | Out-Null

Write-Host "Native messaging host registered: $hostName"
Write-Host "Manifest: $absManifestPath"
Write-Host ""
Write-Host "IMPORTANT: Chrome must be launched with remote debugging enabled:"
Write-Host "  chrome.exe --remote-debugging-port=9222 --user-data-dir=\"C:\ChromeDebugProfile\""
Write-Host ""
Write-Host "Then reload the extension in chrome://extensions/"

# Also create a shortcut for easy Chrome launch
$chromeExe = "${env:ProgramFiles}\Google\$ChromeVersion\Application\chrome.exe"
if (-not (Test-Path $chromeExe)) {
    $chromeExe = "${env:ProgramFiles(x86)}\Google\$ChromeVersion\Application\chrome.exe"
}
if (-not (Test-Path $chromeExe)) {
    $chromeExe = "${env:LocalAppData}\Google\$ChromeVersion\Application\chrome.exe"
}

if (Test-Path $chromeExe) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktop "Chrome with Debugging.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $chromeExe
    $shortcut.Arguments = "--remote-debugging-port=9222 --user-data-dir=`"C:\ChromeDebugProfile`""
    $shortcut.Description = "Chrome with remote debugging for Browser Use extension"
    $shortcut.Save()
    Write-Host "Created desktop shortcut: $shortcutPath"
} else {
    Write-Warning "Chrome executable not found. Create shortcut manually."
}