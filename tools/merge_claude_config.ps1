# Merge BRAG's MCP connectors into Claude Desktop's config - ON THE HOST.
#
# Why host-side: an in-container write to this Claude-managed file does NOT
# reliably reach the host on Windows. This is a THIN pipe - it sends the current
# config through the container's brag.claude_sync (the single source of truth for
# the connector set + sync rules: one entry per project, drop removed brag-*,
# keep the user's other servers, migrate the legacy key) and writes the result
# back. brag-app must be running (setup.bat / the add-project launcher start it).
#
# ASCII-only: Windows PowerShell 5.1 reads a BOM-less file as ANSI, so a stray
# non-ASCII char (e.g. an em-dash) breaks the parser.
$ErrorActionPreference = "Stop"
$dir = Join-Path $env:APPDATA "Claude"
$cfg = Join-Path $dir "claude_desktop_config.json"
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }

$current = ""
if (Test-Path $cfg) {
    $current = Get-Content $cfg -Raw
    Copy-Item $cfg "$cfg.backup" -Force
}

# Pipe the current config through the container as UTF-8 (PS 5.1 would otherwise
# encode native-command stdin/stdout as ANSI and mangle non-ASCII paths).
$enc = New-Object System.Text.UTF8Encoding $false
$prevConsole = [Console]::OutputEncoding
$prevOut = $OutputEncoding
$synced = $null
try {
    [Console]::OutputEncoding = $enc
    $OutputEncoding = $enc
    $synced = $current | docker exec -i brag-app python -m brag.claude_sync
} catch {
    Write-Host "  (Could not reach brag-app for the Claude entry; skipped - re-run setup.)"
    exit 0
} finally {
    [Console]::OutputEncoding = $prevConsole
    $OutputEncoding = $prevOut
}
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$synced)) {
    Write-Host "  (Claude entry not written - is brag-app running? Re-run setup.)"
    exit 0
}
# Native stdout comes back as an array of lines; rejoin into one JSON document.
if ($synced -is [array]) { $synced = $synced -join "`n" }
[System.IO.File]::WriteAllText($cfg, $synced, $enc)
Write-Host "  [ OK ]  BRAG connected to Claude Desktop."
exit 0
