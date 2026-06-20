# Native folder picker for the BRAG knowledge folder (RAG connection folder),
# run on the HOST by setup.bat. A browser-based wizard cannot open a real folder
# dialog that returns an absolute path, so this required, prominent step is done
# here. Writes (or replaces) VAULT_PATH in the project's .env. On cancel or any
# error it leaves .env untouched so setup falls back to the default folder -
# it must NEVER block or crash setup.
param([string]$ProjectDir = ".")

try {
    Add-Type -AssemblyName System.Windows.Forms
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.Description = "Choose your BRAG knowledge folder (RAG connection folder) - where your documents and notes live. This step is required."
    try { $dlg.UseDescriptionForTitle = $true } catch {}
    try { $dlg.SelectedPath = [Environment]::GetFolderPath('MyDocuments') } catch {}

    if ($dlg.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK -or
            [string]::IsNullOrWhiteSpace($dlg.SelectedPath)) {
        Write-Host "  No folder chosen - the default folder (RAG-Verbindungsordner\ next to this program) will be used."
        exit 0
    }

    $chosen  = $dlg.SelectedPath
    $envPath = Join-Path $ProjectDir ".env"
    $lines = @()
    if (Test-Path $envPath) {
        $lines = @(Get-Content $envPath | Where-Object { $_ -notmatch '^\s*VAULT_PATH\s*=' })
    }
    $lines += "VAULT_PATH=$chosen"
    [System.IO.File]::WriteAllLines($envPath, $lines, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "  RAG connection folder: $chosen"
} catch {
    Write-Host "  (Folder dialog unavailable - the default folder will be used.) $($_.Exception.Message)"
    exit 0
}
