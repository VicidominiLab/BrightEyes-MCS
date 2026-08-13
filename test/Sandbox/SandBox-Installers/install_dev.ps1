# Relaunch this script as Administrator if needed
$CurrentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$Principal = New-Object Security.Principal.WindowsPrincipal($CurrentIdentity)
$IsAdmin = $Principal.IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)

if (-not $IsAdmin) {
    Write-Host "Requesting Administrator privileges..."

    Start-Process powershell.exe `
        -Verb RunAs `
        -ArgumentList @(
            "-ExecutionPolicy", "Bypass",
            "-NoProfile",
            "-NoExit",
            "-File", "`"$PSCommandPath`""
        )

    exit
}

if (-not $IsAdmin) {
    Write-Host "Requesting Administrator privileges..."

    Start-Process powershell.exe `
        -Verb RunAs `
        -ArgumentList @(
            "-ExecutionPolicy", "Bypass",
            "-NoProfile",
            "-NoExit",
            "-File", "`"$PSCommandPath`""
        )

    exit
}

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------

$Desktop = "$env:USERPROFILE\Desktop"

$SourceRepo = "$Desktop\BrightEyes-MCS-ReadOnly"
$WorkRepo   = "$Desktop\BrightEyes-MCS"

$InstallersDir = "$Desktop\SandBox-Installers"
$PythonManager = "$InstallersDir\python-manager-26.3.msix"

$LogFile = "$Desktop\install_dev.log"

$Venv310 = "$Desktop\venv3-10"
$Venv312 = "$Desktop\venv3-12"
$Venv313 = "$Desktop\venv3-13"

Start-Transcript -Path $LogFile -Force

try {
    Write-Host ""
    Write-Host "========================================"
    Write-Host " BrightEyes-MCS development environment"
    Write-Host "========================================"
    Write-Host ""

    # ------------------------------------------------------------
    # Disable Smart App Control / Verified and Reputable policy
    #
    # This is intentionally done before installing Python,
    # packages, or repository dependencies because otherwise
    # Windows Sandbox can become extremely slow.
    # ------------------------------------------------------------

    Write-Host "Disabling Verified and Reputable policy..."

    $CiPolicyPath = "HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy"

    if (-not (Test-Path -LiteralPath $CiPolicyPath)) {
        New-Item `
            -Path $CiPolicyPath `
            -Force | Out-Null
    }

    Set-ItemProperty `
        -Path $CiPolicyPath `
        -Name "VerifiedAndReputablePolicyState" `
        -Type DWord `
        -Value 0

    Write-Host "Verified and Reputable policy disabled."
    Write-Host ""

    # ------------------------------------------------------------
    # Refresh Code Integrity policies
    # ------------------------------------------------------------

    Write-Host "Refreshing Code Integrity policy..."

    $CiTool = "$env:SystemRoot\System32\CiTool.exe"

    if (-not (Test-Path -LiteralPath $CiTool)) {
        throw "CiTool.exe not found: $CiTool"
    }

    Write-Host "Refreshing Code Integrity policy..."

    $CiTool = "$env:SystemRoot\System32\CiTool.exe"

    if (-not (Test-Path -LiteralPath $CiTool)) {
        throw "CiTool.exe not found: $CiTool"
    }

    cmd.exe /c "(echo.) | `"$CiTool`" -r"

    if ($LASTEXITCODE -ne 0) {
        throw "CiTool.exe failed with exit code $LASTEXITCODE"
    }

    Write-Host "Code Integrity policy refreshed."
    Write-Host ""

    # ------------------------------------------------------------
    # Enable Windows long paths
    # ------------------------------------------------------------

    Write-Host "Enabling Windows long paths..."

    Set-ItemProperty `
        -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
        -Name "LongPathsEnabled" `
        -Type DWord `
        -Value 1

    Write-Host "Windows long paths enabled."
    Write-Host ""

    # ------------------------------------------------------------
    # Check source repository
    # ------------------------------------------------------------

    if (-not (Test-Path -LiteralPath $SourceRepo)) {
        throw "Source repository not found: $SourceRepo"
    }

    # ------------------------------------------------------------
    # Copy repository to writable location
    # ------------------------------------------------------------

    Write-Host "Copying repository to writable folder..."

    if (Test-Path -LiteralPath $WorkRepo) {
        Write-Host "Removing existing writable repository..."

        Remove-Item `
            -LiteralPath $WorkRepo `
            -Recurse `
            -Force
    }

    Copy-Item `
        -LiteralPath $SourceRepo `
        -Destination $WorkRepo `
        -Recurse `
        -Force

    Write-Host "Repository copied to:"
    Write-Host "  $WorkRepo"
    Write-Host ""

    # ------------------------------------------------------------
    # Check Python Manager installer
    # ------------------------------------------------------------

    if (-not (Test-Path -LiteralPath $PythonManager)) {
        throw "Python Manager installer not found: $PythonManager"
    }

    # ------------------------------------------------------------
    # Install Python Manager
    # ------------------------------------------------------------

    Write-Host "Installing Python Manager..."

    Add-AppxPackage `
        -Path $PythonManager

    Write-Host "Python Manager installation completed."
    Write-Host ""

    # ------------------------------------------------------------
    # Refresh PATH after Python Manager installation
    # ------------------------------------------------------------

    Write-Host "Refreshing PATH..."

    $MachinePath = [Environment]::GetEnvironmentVariable(
        "Path",
        [EnvironmentVariableTarget]::Machine
    )

    $UserPath = [Environment]::GetEnvironmentVariable(
        "Path",
        [EnvironmentVariableTarget]::User
    )

    $env:Path = "$MachinePath;$UserPath"

    # ------------------------------------------------------------
    # Check py command
    # ------------------------------------------------------------

    $PyCommand = Get-Command py.exe -ErrorAction SilentlyContinue

    if (-not $PyCommand) {
        throw "The 'py' command is not available after installing Python Manager."
    }

    Write-Host "Python Manager command found:"
    Write-Host "  $($PyCommand.Source)"
    Write-Host ""

    # ------------------------------------------------------------
    # Install Python versions
    # ------------------------------------------------------------

    Write-Host "Installing Python 3.10..."

    & py install 3.10

    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.10 installation failed with exit code $LASTEXITCODE"
    }

    Write-Host ""

    Write-Host "Installing Python 3.12..."

    & py install 3.12

    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.12 installation failed with exit code $LASTEXITCODE"
    }

    Write-Host ""

    Write-Host "Installing Python 3.13..."

    & py install 3.13

    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.13 installation failed with exit code $LASTEXITCODE"
    }

    Write-Host ""
    Write-Host "Installed Python versions:"
    Write-Host ""

    & py list

    if ($LASTEXITCODE -ne 0) {
        throw "'py list' failed with exit code $LASTEXITCODE"
    }

    Write-Host ""

    # ------------------------------------------------------------
    # Remove previous virtual environments
    # ------------------------------------------------------------

    Write-Host "Preparing virtual environments..."

    if (Test-Path -LiteralPath $Venv310) {
        Write-Host "Removing existing Python 3.10 virtual environment..."

        Remove-Item `
            -LiteralPath $Venv310 `
            -Recurse `
            -Force
    }

    if (Test-Path -LiteralPath $Venv312) {
        Write-Host "Removing existing Python 3.12 virtual environment..."

        Remove-Item `
            -LiteralPath $Venv312 `
            -Recurse `
            -Force
    }

    if (Test-Path -LiteralPath $Venv313) {
        Write-Host "Removing existing Python 3.13 virtual environment..."

        Remove-Item `
            -LiteralPath $Venv313 `
            -Recurse `
            -Force
    }

    Write-Host ""

    # ------------------------------------------------------------
    # Python 3.10 environment
    # ------------------------------------------------------------

    # Write-Host "Creating Python 3.10 virtual environment..."
    #
    # & py -3.10 -m venv $Venv310
    #
    # if ($LASTEXITCODE -ne 0) {
    #     throw "Failed to create Python 3.10 virtual environment."
    # }
    #
    # Write-Host ""
    # Write-Host "Upgrading pip in Python 3.10 virtual environment..."
    #
    # & "$Venv310\Scripts\python.exe" `
    #     -m pip install --upgrade pip
    #
    # if ($LASTEXITCODE -ne 0) {
    #     throw "Failed to upgrade pip in Python 3.10 virtual environment."
    # }
    #
    # Write-Host ""
    # Write-Host "Installing BrightEyes-MCS into Python 3.10 virtual environment..."
    #
    # & "$Venv310\Scripts\python.exe" `
    #     -m pip install "$WorkRepo"
    #
    # if ($LASTEXITCODE -ne 0) {
    #     throw "Failed to install BrightEyes-MCS using Python 3.10."
    # }

    # ------------------------------------------------------------
    # Python 3.12 environment
    # ------------------------------------------------------------

    Write-Host "Creating Python 3.12 virtual environment..."

    & py -3.12 -m venv $Venv312

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create Python 3.12 virtual environment."
    }

    Write-Host ""
    Write-Host "Upgrading pip in Python 3.12 virtual environment..."

    & "$Venv312\Scripts\python.exe" `
        -m pip install --upgrade pip

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upgrade pip in Python 3.12 virtual environment."
    }

    Write-Host ""
    Write-Host "Installing BrightEyes-MCS into Python 3.12 virtual environment..."

    & "$Venv312\Scripts\python.exe" `
        -m pip install "$WorkRepo"

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install BrightEyes-MCS using Python 3.12."
    }

    # ------------------------------------------------------------
    # Python 3.13 environment
    # ------------------------------------------------------------

    # Write-Host ""
    # Write-Host "Creating Python 3.13 virtual environment..."
    #
    # & py -3.13 -m venv $Venv313
    #
    # if ($LASTEXITCODE -ne 0) {
    #     throw "Failed to create Python 3.13 virtual environment."
    # }
    #
    # Write-Host ""
    # Write-Host "Upgrading pip in Python 3.13 virtual environment..."
    #
    # & "$Venv313\Scripts\python.exe" `
    #     -m pip install --upgrade pip
    #
    # if ($LASTEXITCODE -ne 0) {
    #     throw "Failed to upgrade pip in Python 3.13 virtual environment."
    # }
    #
    # Write-Host ""
    # Write-Host "Installing BrightEyes-MCS into Python 3.13 virtual environment..."
    #
    # & "$Venv313\Scripts\python.exe" `
    #     -m pip install "$WorkRepo"
    #
    # if ($LASTEXITCODE -ne 0) {
    #     throw "Failed to install BrightEyes-MCS using Python 3.13."
    # }

    # ------------------------------------------------------------
    # Installation completed
    # ------------------------------------------------------------

    Write-Host ""
    Write-Host "========================================"
    Write-Host " Installation completed successfully"
    Write-Host "========================================"
    Write-Host ""
    Write-Host "Repository:"
    Write-Host "  $WorkRepo"
    Write-Host ""
    Write-Host "Python 3.12 virtual environment:"
    Write-Host "  $Venv312"
    Write-Host ""
    Write-Host "Log file:"
    Write-Host "  $LogFile"
    Write-Host ""

    # ------------------------------------------------------------
    # Start BrightEyes-MCS
    # ------------------------------------------------------------

    Write-Host "Starting BrightEyes-MCS..."
    Write-Host ""

    & "$Venv312\Scripts\python.exe" `
        -m brighteyes_mcs

    if ($LASTEXITCODE -ne 0) {
        throw "BrightEyes-MCS exited with code $LASTEXITCODE"
    }
}
catch {
    Write-Host ""
    Write-Host "========================================"
    Write-Host " ERROR"
    Write-Host "========================================"
    Write-Host ""
    Write-Host $_.Exception.Message
    Write-Host ""

    if ($_.ScriptStackTrace) {
        Write-Host "Stack:"
        Write-Host $_.ScriptStackTrace
        Write-Host ""
    }
}
finally {
    try {
        Stop-Transcript
    }
    catch {
        # Ignore transcript shutdown errors
    }
}

Write-Host ""
Read-Host "Press ENTER to close"