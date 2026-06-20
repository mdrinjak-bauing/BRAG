# Merge BRAG's MCP entry into Claude Desktop's config — ON THE HOST.
#
# Why host-side: writing this Claude-managed file from INSIDE the Docker
# container does NOT reliably reach the host on Windows (the write silently
# no-ops, while write_claude_config still reports success). A host-side write
# works and persists. setup.bat calls this after the wizard.
#
# Safe: backs up the existing config, preserves every other key (incl. other
# MCP servers), writes UTF-8 WITHOUT a BOM (Claude's parser dislikes a BOM),
# and verifies the entry landed.

$ErrorActionPreference = "Stop"
$name  = "brag"
$entry = [ordered]@{
    command = "docker"
    args    = @("exec", "-i", "brag-app", "python", "-m", "brag.mcp_server")
}

$dir = Join-Path $env:APPDATA "Claude"
$cfg = Join-Path $dir "claude_desktop_config.json"
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }

$root = $null
if (Test-Path $cfg) {
    try {
        $root = Get-Content $cfg -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        Copy-Item $cfg "$cfg.backup" -Force
    } catch {
        Copy-Item $cfg "$cfg.broken.bak" -Force
        Write-Host "  WARNING: existing Claude config was not valid JSON (backed up to .broken.bak); writing a fresh one."
        $root = $null
    }
}
if ($null -eq $root) { $root = [pscustomobject]@{} }

# Ensure an mcpServers object exists, then add/replace ONLY our entry.
if (-not ($root.PSObject.Properties.Name -contains "mcpServers") -or $null -eq $root.mcpServers) {
    $root | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force
}
# Migrate older installs: drop the previous long key name if present, so the user
# isn't left with a duplicate/orphan connection under the old name.
if ($root.mcpServers.PSObject.Properties.Name -contains "academic-rag-and-second-brain") {
    $root.mcpServers.PSObject.Properties.Remove("academic-rag-and-second-brain")
}
$root.mcpServers | Add-Member -NotePropertyName $name -NotePropertyValue ([pscustomobject]$entry) -Force

# Write UTF-8 without BOM.
$json = $root | ConvertTo-Json -Depth 20
[System.IO.File]::WriteAllText($cfg, $json, (New-Object System.Text.UTF8Encoding($false)))

# Verify the entry is actually present on disk.
$check = Get-Content $cfg -Raw | ConvertFrom-Json
if ($check.mcpServers.$name) {
    Write-Host "  [ OK ]  BRAG is connected to Claude Desktop."
    exit 0
} else {
    Write-Host "  [FAIL] Could not confirm the entry. Add it manually to:"
    Write-Host "         $cfg"
    Write-Host "         under mcpServers -> $name"
    exit 1
}
