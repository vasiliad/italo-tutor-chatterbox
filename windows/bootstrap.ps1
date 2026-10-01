# Italo Tutor for Windows - one command (any PowerShell window):
#   irm https://raw.githubusercontent.com/vasiliad/italo-tutor-chatterbox/main/windows/bootstrap.ps1 | iex
# Asks for admin rights (click "Yes"), installs Git, clones the private app repo (GitHub login opens
# in the browser once) into C:\Projects\1italo-tutor and runs italo-tutor\tools\windows\setup.ps1,
# which installs everything else and builds the app. Messages here are ASCII on purpose (irm | iex).
$ErrorActionPreference = "Continue"  # native stderr must not abort (PowerShell 5.1); errors are thrown explicitly
$Url = "https://raw.githubusercontent.com/vasiliad/italo-tutor-chatterbox/main/windows/bootstrap.ps1"
$Root = "C:\Projects\1italo-tutor"
$Branch = "claude/funny-thompson-nhd4kq"

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
  Write-Host "Italo Tutor: asking for administrator rights - click Yes." -ForegroundColor Cyan
  Start-Process powershell -Verb RunAs -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command",
    "irm $Url | iex"
  return
}

$log = Join-Path $env:TEMP "italo-tutor-setup.log"
Start-Transcript -Path $log -Append | Out-Null
try {
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw "winget not found: install 'App Installer' from Microsoft Store and run the command again."
  }
  $git = Join-Path $env:ProgramFiles "Git\cmd\git.exe"
  if (-not (Test-Path $git)) {
    Write-Host "Installing Git..." -ForegroundColor Cyan
    winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements --silent
  }
  $env:Path = (Split-Path $git) + ";" + $env:Path

  $app = Join-Path $Root "italo-tutor"
  New-Item -ItemType Directory -Force -Path $Root | Out-Null
  if (-not (Test-Path (Join-Path $app ".git"))) {
    Write-Host "Cloning the app. A browser window will ask you to sign in to GitHub - sign in once." -ForegroundColor Yellow
    & $git clone --branch $Branch https://github.com/vasiliad/italo-tutor $app
    if ($LASTEXITCODE) { throw "git clone failed (code $LASTEXITCODE)" }
  } else {
    & $git -C $app pull --ff-only origin $Branch
  }

  # Claude Desktop - so a Claude session on this laptop can finish and fix the Windows version
  if (-not (winget list --id Anthropic.Claude -e 2>$null | Select-String "Anthropic.Claude")) {
    winget install --id Anthropic.Claude -e --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE) { Write-Host "Claude Desktop was not installed (code $LASTEXITCODE) - not critical." }
  }

  & (Join-Path $app "tools\windows\setup.ps1") -Root $Root -Branch $Branch

  $release = Join-Path $app "build\windows\x64\runner\Release"
  $keys = Join-Path $release "keys.txt"
  if ((Test-Path $release) -and -not (Test-Path $keys)) {
    Write-Host ""
    Write-Host "Paste your Gemini API keys (space separated) and press Enter, or just press Enter to skip:" -ForegroundColor Yellow
    $k = Read-Host
    if ($k.Trim()) { Set-Content -Path $keys -Value $k.Trim() -Encoding ascii }
  }
  # shortcut on the desktop
  if (Test-Path (Join-Path $release "italo_tutor.exe")) {
    $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "Italo Tutor.lnk"))
    $lnk.TargetPath = Join-Path $release "italo_tutor.exe"
    $lnk.WorkingDirectory = $release
    $lnk.Save()
    Write-Host "`nDONE. 'Italo Tutor' shortcut is on the desktop." -ForegroundColor Green
  }
} catch {
  Write-Host "`nFAILED: $_" -ForegroundColor Red
  Write-Host "Log: $log - send it to Claude."
} finally {
  Stop-Transcript | Out-Null
}
