$ErrorActionPreference = "Stop"
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
Set-Location $PSScriptRoot\..
uv run ruff check
uv run pytest -q
$p = Start-Process uv -ArgumentList "run","ventude" -PassThru -WindowStyle Hidden
Start-Sleep 9
$p.Refresh()
if ($p.HasExited) { throw "Ventude saiu cedo (exit $($p.ExitCode))" }
taskkill /T /F /PID $p.Id | Out-Null
Write-Host "Smoke OK"
