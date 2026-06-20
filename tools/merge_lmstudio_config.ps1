# Merge BRAG's MCP entry into LM Studio's mcp.json - ON THE HOST (Windows).
#
# LM Studio (v0.3.17+) is an MCP host: its chat can use BRAG's search + notebook
# tools. Its config lives at %USERPROFILE%\.lmstudio\mcp.json and uses the same
# { "mcpServers": { ... } } schema as Claude Desktop. We only touch it when LM
# Studio is actually installed (the .lmstudio folder exists); we never create it
# for users who do not have LM Studio. Safe: backs up, preserves other servers,
# migrates the old key name, writes UTF-8 without a BOM. Never fails setup (LM
# Studio is the secondary host; always exits 0).
#
# NOTE: this file MUST stay ASCII-only. Windows PowerShell 5.1 reads a BOM-less
# file as ANSI, and a stray non-ASCII char (e.g. an em-dash) breaks the parser.

$ErrorActionPreference = "Stop"
$name   = "brag"
$legacy = "academic-rag-and-second-brain"
$entry  = [ordered]@{
    command = "docker"
    args    = @("exec", "-i", "brag-app", "python", "-m", "brag.mcp_server")
}

$dir = Join-Path $env:USERPROFILE ".lmstudio"
if (-not (Test-Path $dir)) {
    Write-Host "  LM Studio not detected (no .lmstudio folder) - skipped."
    exit 0
}
$cfg = Join-Path $dir "mcp.json"

try {
    $root = $null
    if (Test-Path $cfg) {
        try {
            $root = Get-Content $cfg -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
            Copy-Item $cfg "$cfg.backup" -Force
        } catch {
            Copy-Item $cfg "$cfg.broken.bak" -Force
            Write-Host "  WARNING: LM Studio mcp.json was not valid JSON (backed up to .broken.bak); writing a fresh one."
            $root = $null
        }
    }
    if ($null -eq $root) { $root = [pscustomobject]@{} }

    if (-not ($root.PSObject.Properties.Name -contains "mcpServers") -or $null -eq $root.mcpServers) {
        $root | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force
    }
    # Migrate older installs: drop the previous long key name if present.
    if ($root.mcpServers.PSObject.Properties.Name -contains $legacy) {
        $root.mcpServers.PSObject.Properties.Remove($legacy)
    }
    $root.mcpServers | Add-Member -NotePropertyName $name -NotePropertyValue ([pscustomobject]$entry) -Force

    $json = $root | ConvertTo-Json -Depth 20
    [System.IO.File]::WriteAllText($cfg, $json, (New-Object System.Text.UTF8Encoding($false)))

    $check = Get-Content $cfg -Raw | ConvertFrom-Json
    if ($check.mcpServers.$name) {
        Write-Host "  [ OK ]  BRAG is connected to LM Studio."
    } else {
        Write-Host "  [note] Could not confirm the LM Studio entry; add 'brag' to $cfg by hand if needed."
    }
} catch {
    Write-Host "  (LM Studio MCP config skipped - $($_.Exception.Message))"
}
exit 0
