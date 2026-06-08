param(
  [switch]$Tunnel
)

$ErrorActionPreference = "Stop"

$Root = $PSScriptRoot
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$EnvFile = Join-Path $Root ".env"
$EnvExample = Join-Path $Root ".env.example"
$FrontendEnv = Join-Path $FrontendDir ".env.local"
$LogDir = Join-Path $Root ".logs"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Processes = New-Object System.Collections.Generic.List[System.Diagnostics.Process]

function Test-CommandExists {
  param([string]$Name)
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Start-LoggedProcess {
  param(
    [string]$FilePath,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory,
    [string]$Name
  )

  $stdout = Join-Path $LogDir "$Name.out.log"
  $stderr = Join-Path $LogDir "$Name.err.log"
  Remove-Item -LiteralPath $stdout, $stderr -ErrorAction SilentlyContinue

  $process = Start-Process `
    -FilePath $FilePath `
    -ArgumentList $ArgumentList `
    -WorkingDirectory $WorkingDirectory `
    -PassThru `
    -NoNewWindow `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr

  $Processes.Add($process)
  return $process
}

function Wait-Http {
  param(
    [string]$Url,
    [int]$Seconds = 30
  )

  for ($i = 0; $i -lt $Seconds; $i++) {
    try {
      Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 | Out-Null
      return $true
    } catch {
      Start-Sleep -Seconds 1
    }
  }
  return $false
}

function Wait-TunnelUrl {
  param(
    [string]$LogFile,
    [int]$Seconds = 30
  )

  for ($i = 0; $i -lt $Seconds; $i++) {
    if (Test-Path $LogFile) {
      $content = Get-Content -LiteralPath $LogFile -Raw -ErrorAction SilentlyContinue
      $match = [regex]::Match($content, "https://[a-z0-9-]+\.trycloudflare\.com")
      if ($match.Success) {
        return $match.Value
      }
    }
    Start-Sleep -Seconds 1
  }
  return $null
}

function Stop-All {
  foreach ($process in $Processes) {
    try {
      if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
      }
    } catch {
    }
  }
}

try {
  Write-Host "========================================"
  Write-Host "  MockMate starting on Windows..."
  Write-Host "========================================"

  if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
      Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
      Write-Host "[env] Created .env from .env.example. Fill API keys for full AI/audio features."
    } else {
      New-Item -ItemType File -Path $EnvFile | Out-Null
      Write-Host "[env] Created empty .env."
    }
  }

  $VenvPython = Join-Path $BackendDir "venv\Scripts\python.exe"
  if (-not (Test-Path $VenvPython)) {
    if (-not (Test-CommandExists "python")) {
      throw "Python was not found in PATH."
    }
    Write-Host "[backend] Creating virtual environment..."
    & python -m venv (Join-Path $BackendDir "venv")
  }

  Write-Host "[backend] Checking Python dependencies..."
  & $VenvPython -m pip install -r (Join-Path $BackendDir "requirements.txt")

  Write-Host "[backend] Starting FastAPI on http://localhost:8000 ..."
  Start-LoggedProcess `
    -FilePath $VenvPython `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000") `
    -WorkingDirectory $BackendDir `
    -Name "backend" | Out-Null

  if (-not (Wait-Http "http://localhost:8000/docs" 30)) {
    Write-Host "[backend] Failed to start. See logs:"
    Write-Host "  $LogDir\backend.out.log"
    Write-Host "  $LogDir\backend.err.log"
    exit 1
  }

  $BackendUrl = "http://localhost:8000"
  $FrontendUrl = "http://localhost:3001"
  $Cloudflared = Get-Command "cloudflared" -ErrorAction SilentlyContinue

  if ($Tunnel) {
    if (-not $Cloudflared) {
      Write-Host "[tunnel] cloudflared was not found. Continuing with local URLs only."
    } else {
      Write-Host "[tunnel] Opening backend tunnel..."
      $backendTunnel = Start-LoggedProcess `
        -FilePath $Cloudflared.Source `
        -ArgumentList @("tunnel", "--url", "http://localhost:8000") `
        -WorkingDirectory $Root `
        -Name "backend-tunnel"

      $BackendUrl = Wait-TunnelUrl (Join-Path $LogDir "backend-tunnel.err.log") 30
      if (-not $BackendUrl) {
        $BackendUrl = Wait-TunnelUrl (Join-Path $LogDir "backend-tunnel.out.log") 5
      }
      if (-not $BackendUrl) {
        throw "Backend tunnel did not produce a trycloudflare URL."
      }
      Write-Host "[tunnel] Backend: $BackendUrl"
    }
  }

  Set-Content -LiteralPath $FrontendEnv -Encoding UTF8 -Value @(
    "NEXT_PUBLIC_API_URL=$BackendUrl",
    "NEXT_PUBLIC_AUDIO_URL=$BackendUrl"
  )

  $Npm = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
  if (-not $Npm) {
    $Npm = Get-Command "npm" -ErrorAction SilentlyContinue
  }
  if (-not $Npm) {
    throw "npm was not found in PATH."
  }

  if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "[frontend] Installing npm dependencies..."
    & $Npm.Source install --prefix $FrontendDir
  }

  Write-Host "[frontend] Starting Next.js on http://localhost:3001 ..."
  Start-LoggedProcess `
    -FilePath $Npm.Source `
    -ArgumentList @("run", "dev", "--", "--port", "3001") `
    -WorkingDirectory $FrontendDir `
    -Name "frontend" | Out-Null

  if (-not (Wait-Http "http://localhost:3001" 60)) {
    Write-Host "[frontend] Failed to start. See logs:"
    Write-Host "  $LogDir\frontend.out.log"
    Write-Host "  $LogDir\frontend.err.log"
    exit 1
  }

  if ($Tunnel -and $Cloudflared) {
    Write-Host "[tunnel] Opening frontend tunnel..."
    Start-LoggedProcess `
      -FilePath $Cloudflared.Source `
      -ArgumentList @("tunnel", "--url", "http://localhost:3001") `
      -WorkingDirectory $Root `
      -Name "frontend-tunnel" | Out-Null

    $publicFrontendUrl = Wait-TunnelUrl (Join-Path $LogDir "frontend-tunnel.err.log") 30
    if (-not $publicFrontendUrl) {
      $publicFrontendUrl = Wait-TunnelUrl (Join-Path $LogDir "frontend-tunnel.out.log") 5
    }
    if ($publicFrontendUrl) {
      $FrontendUrl = $publicFrontendUrl
    } else {
      Write-Host "[tunnel] Frontend tunnel did not produce a URL; using local URL."
    }
  }

  Write-Host ""
  Write-Host "========================================"
  Write-Host "  MockMate is running"
  Write-Host "========================================"
  Write-Host "  Frontend: $FrontendUrl"
  Write-Host "  Backend:  $BackendUrl"
  Write-Host "  Docs:     http://localhost:8000/docs"
  Write-Host ""
  Write-Host "  Press Ctrl+C to stop all services."
  Write-Host "  Logs are in: $LogDir"
  Write-Host "========================================"

  while ($true) {
    foreach ($process in $Processes) {
      if ($process.HasExited) {
        throw "A child process exited. Check logs in $LogDir."
      }
    }
    Start-Sleep -Seconds 2
  }
} finally {
  Stop-All
}
