<#
.SYNOPSIS
    Scryware 3D Studio - one-shot installer for Windows.
.DESCRIPTION
    Shows a pre-flight checklist popup first. On approval it:
      1. Ensures WSL2 + Ubuntu-22.04 are installed
      2. Writes .wslconfig (24 GB RAM / 8 GB swap for the 3D models)
      3. Copies wsl/setup_wsl.sh + wsl/patch_sdpa.py into WSL and runs setup
         (miniconda, TRELLIS.2 conda env, SDPA patch, SkinTokens venv)
      4. Installs the Windows Python requirements for the GUI
    Run from the repo root:  powershell -ExecutionPolicy Bypass -File install.ps1
#>
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# ---------------- pre-flight popup ----------------
$form = New-Object System.Windows.Forms.Form
$form.Text = "Scryware 3D Studio - Setup"
$form.Size = New-Object System.Drawing.Size(640, 620)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

$title = New-Object System.Windows.Forms.Label
$title.Text = "Before we install: read this first"
$title.Font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
$title.Location = New-Object System.Drawing.Point(20, 15)
$title.Size = New-Object System.Drawing.Size(580, 35)
$form.Controls.Add($title)

$body = New-Object System.Windows.Forms.RichTextBox
$body.ReadOnly = $true
$body.Location = New-Object System.Drawing.Point(20, 55)
$body.Size = New-Object System.Drawing.Size(580, 420)
$body.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$body.Text = @"
WHAT THIS INSTALLER DOES
- Enables/installs WSL2 and the Ubuntu-22.04 distro (may need a reboot)
- Writes %USERPROFILE%\.wslconfig giving WSL 24 GB RAM / 8 GB swap
- Inside WSL: installs miniconda, creates the 'trellis2' conda env,
  clones + patches TRELLIS.2, clones SkinTokens and builds its venv
- Installs the Windows Python packages for the GUI (PyQt6, rembg, ...)

WHAT YOU NEED BEFORE YOU CLICK INSTALL
[ ] Windows 10 (21H2+) or Windows 11, 64-bit
[ ] Virtualization enabled in BIOS/UEFI (required for WSL2)
[ ] NVIDIA GPU with ~24 GB VRAM (e.g. RTX 4090) + current Game Ready /
    Studio driver with WSL CUDA support
[ ] ~50 GB free disk space (models + conda envs are large)
[ ] Administrator rights on this PC (WSL install needs it)
[ ] Stable internet: ~35 GB of downloads (PyTorch, model weights)
[ ] 30-60 minutes of unattended time
[ ] HuggingFace account + accepted the gated model licenses:
    - https://huggingface.co/microsoft/TRELLIS.2
    - https://huggingface.co/facebook/dinov3-vit7b16-pretrain-sat493m
    Visit both in your browser and click through the license approvals
    BEFORE installing. The weight downloads fail without these, and the
    errors are cryptic.

APPROVALS THIS INSTALLER WILL ASK FOR
- UAC elevation for WSL feature install (Windows will prompt you)
- Your sudo password inside WSL for apt packages (you type it in WSL)
- Nothing is uploaded anywhere. Everything stays on your machine.

If any box above is unchecked, click Cancel and come back when ready.
"@
$form.Controls.Add($body)

$cancel = New-Object System.Windows.Forms.Button
$cancel.Text = "Cancel"
$cancel.Location = New-Object System.Drawing.Point(340, 500)
$cancel.Size = New-Object System.Drawing.Size(130, 40)
$cancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$form.Controls.Add($cancel)

$install = New-Object System.Windows.Forms.Button
$install.Text = "I meet the requirements - Install"
$install.Location = New-Object System.Drawing.Point(480, 500)
$install.Size = New-Object System.Drawing.Size(120, 40)
$install.DialogResult = [System.Windows.Forms.DialogResult]::OK
$form.Controls.Add($install)

$form.AcceptButton = $install
$form.CancelButton = $cancel

if ($form.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
    Write-Host "Install cancelled by user."
    exit 0
}

# ---------------- helpers ----------------
function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

# ---------------- 1. WSL2 + Ubuntu ----------------
Step "Checking WSL2"
$wslList = wsl.exe -l -q 2>$null
if ($LASTEXITCODE -ne 0 -or -not $wslList) {
    Write-Host "WSL not found - installing (this needs admin, accept the UAC prompt)..."
    wsl.exe --install --no-distribution
    Write-Host ""
    Write-Host "WSL core installed. A REBOOT is required before continuing." -ForegroundColor Yellow
    Write-Host "Reboot, then re-run install.ps1 to continue."
    exit 0
}

$distros = (wsl.exe -l -q) -join "`n"
if ($distros -notmatch "Ubuntu-22.04") {
    Step "Installing Ubuntu-22.04"
    wsl.exe --install -d Ubuntu-22.04
    Write-Host "Ubuntu installed. If this was a fresh install, create your Linux user when prompted, then re-run install.ps1."
} else {
    Write-Host "Ubuntu-22.04 already installed."
}

# ---------------- 2. .wslconfig ----------------
Step "Writing .wslconfig (24 GB RAM / 8 GB swap)"
$wslconfig = @"
[wsl2]
memory=24GB
swap=8GB
"@
$wslconfigPath = Join-Path $env:USERPROFILE ".wslconfig"
$wslconfig | Out-File -FilePath $wslconfigPath -Encoding ascii
Write-Host "Wrote $wslconfigPath - restarting WSL to apply..."
wsl.exe --shutdown

# ---------------- 3. WSL-side setup ----------------
Step "Copying setup scripts into WSL"
$wslSetupDir = "/tmp/scryware-setup"
wsl.exe -d Ubuntu-22.04 -- bash -lc "mkdir -p $wslSetupDir"
Get-ChildItem (Join-Path $RepoRoot "wsl" "*") | ForEach-Object {
    $dest = "$wslSetupDir/$($_.Name)"
    # copy via stdin to avoid path quoting issues
    Get-Content $_.FullName -Raw | wsl.exe -d Ubuntu-22.04 -- bash -lc "cat > $dest"
}
wsl.exe -d Ubuntu-22.04 -- bash -lc "chmod +x $wslSetupDir/setup_wsl.sh"

Step "Running WSL setup (30-60 min, sudo password will be asked inside WSL)"
wsl.exe -d Ubuntu-22.04 -- bash -lc "$wslSetupDir/setup_wsl.sh"
if ($LASTEXITCODE -ne 0) {
    Write-Host "WSL setup reported an error. Re-run install.ps1 to retry (it skips finished steps)." -ForegroundColor Red
    exit 1
}

# ---------------- 4. Windows Python deps ----------------
Step "Installing Windows GUI requirements"
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "Python not found on PATH. Install Python 3.10+ from python.org, then re-run install.ps1." -ForegroundColor Red
    exit 1
}
python -m pip install --upgrade pip
python -m pip install -r (Join-Path $RepoRoot "requirements.txt")

Step "Done"
Write-Host ""
Write-Host "Scryware 3D Studio is ready. Launch with:" -ForegroundColor Green
Write-Host "    cd $RepoRoot"
Write-Host "    python main.py"
