# Native folder picker, run on the HOST by setup.bat / "Projekt hinzufuegen.bat".
# The caller passes the dialog prompt as the first argument (which folder to pick:
# the BRAG Assistent program location, or a project folder). On cancel/error it
# writes NOTHING, so the caller can fall back or abort.
#
# Writes the chosen ABSOLUTE path to <program dir>\.ragpick (one line, UTF-8, no
# BOM).
#
# The program dir is derived from THIS script's own location ($PSScriptRoot is
# ...\tools, its parent is the program dir) so it never depends on a passed
# argument: a batch "%~dp0" ends with "\", and "\"" would escape the closing
# quote and corrupt the path ("Illegal characters in path").
#
# MUST stay ASCII-only: Windows PowerShell 5.1 reads a BOM-less file as ANSI, and
# a stray non-ASCII char (e.g. an em-dash) breaks the parser.

$proj = Split-Path -Parent $PSScriptRoot
$desc = "Choose a folder."
if ($args.Count -ge 1 -and -not [string]::IsNullOrWhiteSpace([string]$args[0])) {
    $desc = [string]$args[0]
}

try {
    Add-Type -AssemblyName System.Windows.Forms
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.Description = $desc
    try { $dlg.UseDescriptionForTitle = $true } catch {}
    try { $dlg.SelectedPath = [Environment]::GetFolderPath('MyDocuments') } catch {}

    if ($dlg.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK -or
            [string]::IsNullOrWhiteSpace($dlg.SelectedPath)) {
        Write-Host "  No location chosen - BRAG will be set up in the current folder."
        exit 0
    }

    # Reject characters that would break the batch .env writer (& % ^ !) or
    # Docker Compose variable interpolation ($) in the .env path. Writing
    # nothing makes setup.bat fall back to an in-place install instead of
    # silently corrupting the path.
    if ($dlg.SelectedPath -match '[&%^!$]') {
        Write-Host '  That folder path contains a character BRAG cannot use safely (& % ^ ! $).'
        Write-Host '  Please re-run setup and choose a folder without those characters.'
        exit 0
    }

    $pick = Join-Path $proj ".ragpick"
    [System.IO.File]::WriteAllText($pick, $dlg.SelectedPath.TrimEnd('\'), (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "  Location: $($dlg.SelectedPath)"
} catch {
    Write-Host "  (Folder dialog unavailable - setting up in the current folder.) $($_.Exception.Message)"
    exit 0
}
