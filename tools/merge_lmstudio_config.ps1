# Merge BRAG's MCP connectors into LM Studio's mcp.json - ON THE HOST (Windows).
#
# LM Studio is an MCP host too; its config uses the same { "mcpServers": {...} }
# schema as Claude, so the SAME container command (brag.claude_sync) computes the
# synced result. Thin pipe; only touches it when LM Studio is installed (the
# .lmstudio folder exists). brag-app must be running.
#
# ASCII-only: PS 5.1 reads a BOM-less file as ANSI; a stray non-ASCII char breaks
# the parser.
$ErrorActionPreference = "Stop"
$dir = Join-Path $env:USERPROFILE ".lmstudio"
if (-not (Test-Path $dir)) {
    Write-Host "  LM Studio not detected (no .lmstudio folder) - skipped."
    exit 0
}
$cfg = Join-Path $dir "mcp.json"

$current = ""
if (Test-Path $cfg) {
    $current = Get-Content $cfg -Raw
    Copy-Item $cfg "$cfg.backup" -Force
}

$enc = New-Object System.Text.UTF8Encoding $false
$prevConsole = [Console]::OutputEncoding
$prevOut = $OutputEncoding
$synced = $null
try {
    [Console]::OutputEncoding = $enc
    $OutputEncoding = $enc
    $synced = $current | docker exec -i brag-app python -m brag.claude_sync
} catch {
    Write-Host "  (Could not reach brag-app for the LM Studio entry; skipped.)"
    exit 0
} finally {
    [Console]::OutputEncoding = $prevConsole
    $OutputEncoding = $prevOut
}
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$synced)) {
    Write-Host "  (LM Studio entry not written - is brag-app running?)"
    exit 0
}
if ($synced -is [array]) { $synced = $synced -join "`n" }
[System.IO.File]::WriteAllText($cfg, $synced, $enc)
Write-Host "  [ OK ]  BRAG connected to LM Studio."
exit 0
