# Installs or updates Inkspire on Windows from the latest GitHub release.
#   irm https://raw.githubusercontent.com/Maksim-Nikolaev/inkspire/main/install.ps1 | iex
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/Maksim-Nikolaev/inkspire/main/install.ps1))) -Uninstall
# $env:INKSPIRE_VERSION = "v0.6.0" installs that release instead of the latest one.
param(
    [switch]$Uninstall,
    [string]$Version = $(if ($env:INKSPIRE_VERSION) { $env:INKSPIRE_VERSION } else { "latest" })
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

$Repo = "Maksim-Nikolaev/inkspire"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\Inkspire"
$Exe = Join-Path $InstallDir "inkspire.exe"
$Shortcut = Join-Path ([Environment]::GetFolderPath("Programs")) "Inkspire.lnk"

function Install-Inkspire {
    if (Get-Process -Name inkspire -ErrorAction SilentlyContinue) {
        throw "Close Inkspire first, then run the installer again."
    }

    $Url = if ($Version -eq "latest") {
        "https://github.com/$Repo/releases/latest/download/inkspire.exe"
    } else {
        "https://github.com/$Repo/releases/download/$Version/inkspire.exe"
    }
    $Download = "$Exe.download"

    Write-Host "Downloading $Url"
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Invoke-WebRequest -Uri $Url -OutFile $Download -UseBasicParsing
    Move-Item -Force $Download $Exe
    Unblock-File $Exe

    $Shell = New-Object -ComObject WScript.Shell
    $Link = $Shell.CreateShortcut($Shortcut)
    $Link.TargetPath = $Exe
    $Link.WorkingDirectory = $InstallDir
    $Link.Description = "Trace line art by moving the mouse along extracted contours"
    $Link.Save()

    Write-Host "Installed Inkspire to $Exe and added it to the Start menu."
}

function Uninstall-Inkspire {
    if (Get-Process -Name inkspire -ErrorAction SilentlyContinue) {
        throw "Close Inkspire first, then run the uninstaller again."
    }

    Remove-Item -Force -ErrorAction SilentlyContinue $Shortcut
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $InstallDir

    Write-Host "Removed Inkspire. Settings in $HOME\.config\inkspire are kept; delete that folder to remove them too."
}

if ($Uninstall) {
    Uninstall-Inkspire
} else {
    Install-Inkspire
}
