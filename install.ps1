<#
.SYNOPSIS
    Scryware 3D Studio - one-shot installer for Windows.
.DESCRIPTION
    Probes the PC first (RAM, CPU, GPU/VRAM, free disk) and adapts to it:
    the WSL memory/swap/processors are sized from the detected hardware
    instead of fixed numbers, the pre-flight popup shows this machine's
    actual figures, and a machine-profile.json is written next to the app
    so the Generate tab defaults to a quality this GPU can handle.

    On approval it:
      1. Ensures WSL2 + Ubuntu-22.04 are installed
      2. Writes .wslconfig sized from the probe
      3. Copies wsl/setup_wsl.sh + the patch scripts into WSL and runs setup
         (miniconda, TRELLIS.2 conda env, SDPA + DINOv3 patches, SkinTokens venv)
      4. Installs the Windows Python requirements for the GUI
      5. Writes machine-profile.json (per-machine, gitignored)
    Run from the repo root:  powershell -ExecutionPolicy Bypass -File install.ps1
#>
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

# >>> PROBE-SECTION-START
function Get-MachineProfile {
    $cs = Get-CimInstance Win32_ComputerSystem
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    $os = Get-CimInstance Win32_OperatingSystem

    $ramGB = [int][math]::Round($cs.TotalPhysicalMemory / 1GB)
    $cores = [int]$cpu.NumberOfLogicalProcessors
    $cpuName = "$($cpu.Name)".Trim()
    # VirtualizationFirmwareEnabled alone reads False on machines where a
    # hypervisor is already running (WSL2/Hyper-V active), so a running
    # hypervisor also counts as enabled - it cannot run otherwise.
    $virt = [bool]$cpu.VirtualizationFirmwareEnabled -or [bool]$cs.HypervisorPresent

    # GPU: nvidia-smi reports true VRAM. CIM's AdapterRAM caps at 4 GB and
    # under-reports every modern card, so it is only a fallback.
    $gpuName = $null
    $vramGB = 0.0
    $smi = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
    if ($smi) {
        try {
            $line = & $smi.Source --query-gpu=name,memory.total --format=csv,noheader,nounits 2>$null |
                Select-Object -First 1
            if ($line) {
                $parts = $line -split ','
                $gpuName = $parts[0].Trim()
                $vramGB = [math]::Round(([double]$parts[1].Trim()) / 1024, 1)
            }
        } catch { }
    }
    if (-not $gpuName) {
        $vc = Get-CimInstance Win32_VideoController |
            Where-Object { $_.Name -match 'NVIDIA' } | Select-Object -First 1
        if ($vc) {
            $gpuName = "$($vc.Name)".Trim()
            $vramGB = [math]::Round($vc.AdapterRAM / 1GB, 1)
        }
    }

    $sysDrive = $env:SystemDrive.Substring(0, 1)
    $freeRaw = (Get-PSDrive -Name $sysDrive).Free
    $freeGB = if ($freeRaw) { [int][math]::Round($freeRaw / 1GB) } else { 0 }

    # WSL sizing: ~70% of RAM for the models, capped so Windows keeps room.
    $wslMem = [int][math]::Min(48, [math]::Max(8, [math]::Round($ramGB * 0.7)))
    $wslSwap = [int][math]::Min(16, [math]::Max(2, [math]::Round($wslMem / 4)))
    $wslProcs = [int][math]::Min(32, [math]::Max(2, $cores - 2))

    # GPU tier -> the Generate quality the app will default to.
    if ($vramGB -ge 20) { $tier = 'high'; $recQuality = '1024' }
    elseif ($vramGB -ge 12) { $tier = 'mid'; $recQuality = '512' }
    else { $tier = 'low'; $recQuality = '512' }

    return [ordered]@{
        ram_gb              = $ramGB
        cpu_name            = $cpuName
        cpu_cores           = $cores
        virtualization      = $virt
        os_build            = [int]$os.BuildNumber
        gpu_name            = $gpuName
        vram_gb             = $vramGB
        free_disk_gb        = $freeGB
        system_drive        = $sysDrive
        wsl_memory_gb       = $wslMem
        wsl_swap_gb         = $wslSwap
        wsl_processors      = $wslProcs
        tier                = $tier
        recommended_quality = $recQuality
    }
}
# >>> PROBE-SECTION-END

$hw = Get-MachineProfile

# ---------------- pre-flight popup ----------------
if ($hw.os_build -ge 19044) { $osLine = "[OK]   Windows build $($hw.os_build) (Windows 10 21H2+ or Windows 11)" }
else { $osLine = "[FAIL] Windows build $($hw.os_build) - WSL2 needs Windows 10 21H2 (build 19044) or later" }

if ($hw.virtualization) { $virtLine = "[OK]   Virtualization enabled in BIOS/UEFI" }
else { $virtLine = "[FAIL] Virtualization not enabled in BIOS/UEFI - WSL2 cannot run until it is" }

$ramLine = "[INFO] RAM: $($hw.ram_gb) GB -> WSL will get $($hw.wsl_memory_gb) GB memory, $($hw.wsl_swap_gb) GB swap, $($hw.wsl_processors) of $($hw.cpu_cores) processors"

if (-not $hw.gpu_name) {
    $gpuLine = "[FAIL] GPU: no NVIDIA GPU detected - TRELLIS.2 needs NVIDIA CUDA, generation will not run on this PC"
} elseif ($hw.tier -eq 'high') {
    $gpuLine = "[OK]   GPU: $($hw.gpu_name), $($hw.vram_gb) GB VRAM - Generate will default to Medium (1024)"
} elseif ($hw.tier -eq 'mid') {
    $gpuLine = "[OK]   GPU: $($hw.gpu_name), $($hw.vram_gb) GB VRAM - Generate will default to Fast (512)"
} else {
    $gpuLine = "[LOW]  GPU: $($hw.gpu_name), $($hw.vram_gb) GB VRAM - under 12 GB: Fast (512) only, and large inputs may run out of memory"
}

if ($hw.free_disk_gb -ge 60) { $diskLine = "[OK]   Free disk on $($hw.system_drive): $($hw.free_disk_gb) GB (about 50 GB needed)" }
elseif ($hw.free_disk_gb -ge 50) { $diskLine = "[LOW]  Free disk on $($hw.system_drive): $($hw.free_disk_gb) GB - enough, but tight (about 50 GB needed)" }
else { $diskLine = "[FAIL] Free disk on $($hw.system_drive): $($hw.free_disk_gb) GB - about 50 GB needed for models and environments" }

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = "Scryware 3D Studio - Setup"
$form.Size = New-Object System.Drawing.Size(640, 620)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

$title = New-Object System.Windows.Forms.Label
$title.Text = "Before we install: what we found on this PC"
$title.Font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
$title.Location = New-Object System.Drawing.Point(20, 15)
$title.Size = New-Object System.Drawing.Size(580, 35)
$form.Controls.Add($title)

$body = New-Object System.Windows.Forms.RichTextBox
$body.ReadOnly = $true
$body.Location = New-Object System.Drawing.Point(20, 55)
$body.Size = New-Object System.Drawing.Size(580, 420)
$body.Font = New-Object System.Drawing.Font("Consolas", 9.5)
$body.Text = @"
DETECTED ON THIS PC
$osLine
$virtLine
$ramLine
$gpuLine
$diskLine

WHAT THIS INSTALLER DOES
- Enables/installs WSL2 and the Ubuntu-22.04 distro (may need a reboot)
- Writes %USERPROFILE%\.wslconfig sized from the RAM above
  ($($hw.wsl_memory_gb) GB RAM / $($hw.wsl_swap_gb) GB swap for the 3D models)
- Inside WSL: installs miniconda, creates the 'trellis2' conda env,
  clones + patches TRELLIS.2, clones SkinTokens and builds its venv
- Installs the Windows Python packages for the GUI (PyQt6, rembg, ...)
- Writes machine-profile.json next to the app with the detected
  hardware, so the Generate tab defaults to a quality this GPU
  can handle (yours: $($hw.recommended_quality))

STILL ON YOU (the installer cannot check these)
[ ] Administrator rights on this PC (WSL install needs it)
[ ] Stable internet: ~35 GB of downloads (PyTorch, model weights)
[ ] 30-60 minutes of unattended time
[ ] HuggingFace account + accepted the gated DINOv3 model license:
    - https://huggingface.co/facebook/dinov3-vitl16-pretrain-lvd1689m
    Visit it in your browser and click through the license approval
    BEFORE installing. The weight download fails without this, and the
    error is cryptic. (The TRELLIS.2 weights themselves are not gated.)

APPROVALS THIS INSTALLER WILL ASK FOR
- UAC elevation for WSL feature install (Windows will prompt you)
- Your sudo password inside WSL for apt packages (you type it in WSL)
- Nothing is uploaded anywhere. Everything stays on your machine.

A [FAIL] line means that part will not work on this PC as it stands.
You can Cancel, fix it, and re-run - or install anyway and fix it later.
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

# ---------------- 2. .wslconfig (sized from the probe) ----------------
Step "Writing .wslconfig ($($hw.wsl_memory_gb) GB RAM / $($hw.wsl_swap_gb) GB swap / $($hw.wsl_processors) processors)"
$wslconfig = @"
[wsl2]
memory=$($hw.wsl_memory_gb)GB
swap=$($hw.wsl_swap_gb)GB
processors=$($hw.wsl_processors)
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

# ---------------- 5. Machine profile ----------------
Step "Writing machine profile (machine-profile.json)"
$profileOut = [ordered]@{
    generated_by        = "install.ps1"
    date                = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    ram_gb              = $hw.ram_gb
    cpu_cores           = $hw.cpu_cores
    gpu_name            = $hw.gpu_name
    vram_gb             = $hw.vram_gb
    tier                = $hw.tier
    wsl_memory_gb       = $hw.wsl_memory_gb
    wsl_swap_gb         = $hw.wsl_swap_gb
    wsl_processors      = $hw.wsl_processors
    recommended_quality = $hw.recommended_quality
}
$profileOut | ConvertTo-Json | Out-File -FilePath (Join-Path $RepoRoot "machine-profile.json") -Encoding ascii
Write-Host "Profile written: tier '$($hw.tier)', Generate default $($hw.recommended_quality)."

Step "Done"
Write-Host ""
Write-Host "Scryware 3D Studio is ready. Launch with:" -ForegroundColor Green
Write-Host "    cd $RepoRoot"
Write-Host "    python main.py"
