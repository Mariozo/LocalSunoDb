param([switch]$NoBrowser)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Log = Join-Path $Root "RECOVER_V228.log"
Remove-Item $Log -Force -ErrorAction SilentlyContinue
function Log([string]$Text) { Add-Content -Path $Log -Value $Text -Encoding UTF8 }

Log "=== LocalSunoDb v2.28 known-good recovery ==="
Log ("Date: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Log ("Root: " + $Root)

if (-not (Test-Path (Join-Path $Root "LocalSunoDb.py"))) { throw "LocalSunoDb.py nav atrasts." }
if (-not (Test-Path (Join-Path $Root "LS_Elza\__init__.py"))) {
    throw "LS_Elza nav atrasts. Recovery apzināti Elza nepārraksta."
}

$ExpectedScript = (Join-Path $Root "LocalSunoDb.py")
$Processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and
    $_.CommandLine -like ("*" + $ExpectedScript + "*") -and
    $_.ExecutablePath -match '(?i)\\pythonw?\.exe$'
}
foreach ($Proc in $Processes) {
    Log ("Stopping old LS PID " + $Proc.ProcessId + ": " + $Proc.CommandLine)
    Stop-Process -Id ([int]$Proc.ProcessId) -Force -ErrorAction SilentlyContinue
}

for ($i=0; $i -lt 40; $i++) {
    $Listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
    if (-not $Listener) { break }
    Start-Sleep -Milliseconds 250
}
if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) {
    throw "Ports 8765 neatbrīvojās."
}

$Py = Get-Command py.exe -ErrorAction SilentlyContinue
$Python = Get-Command python.exe -ErrorAction SilentlyContinue
if ($Py) {
    $PythonExe = $Py.Source
    $Args = @("-3", "LocalSunoDb.py", "--ls-restarted")
} elseif ($Python) {
    $PythonExe = $Python.Source
    $Args = @("LocalSunoDb.py", "--ls-restarted")
} else {
    throw "Python nav atrasts."
}

$Stdout = Join-Path $Root "RECOVER_V228_STDOUT.log"
$Stderr = Join-Path $Root "RECOVER_V228_STDERR.log"
Remove-Item $Stdout,$Stderr -Force -ErrorAction SilentlyContinue

$P = Start-Process -FilePath $PythonExe -ArgumentList $Args -WorkingDirectory $Root -PassThru -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
Log ("Started PID " + $P.Id)

$Ok = $false
for ($i=0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    if ($P.HasExited) { break }
    try {
        $R = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8765/" -TimeoutSec 2
        if ($R.StatusCode -eq 200 -and $R.Content -match "LS v2\.28") {
            $Ok = $true
            break
        }
    } catch {}
}

if (-not $Ok) {
    Log "RESULT: FAIL"
    if (Test-Path $Stdout) { Get-Content $Stdout | Select-Object -Last 200 | Add-Content $Log -Encoding UTF8 }
    if (Test-Path $Stderr) { Get-Content $Stderr | Select-Object -Last 200 | Add-Content $Log -Encoding UTF8 }
    if (Test-Path (Join-Path $Root "error.log")) { Get-Content (Join-Path $Root "error.log") | Select-Object -Last 200 | Add-Content $Log -Encoding UTF8 }
    throw "LS v2.28 nestartējās. Skatīt RECOVER_V228.log."
}

Log "RESULT: PASS - LS v2.28 HTTP 200"
if (-not $NoBrowser) { Start-Process "http://127.0.0.1:8765/" }
