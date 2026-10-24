$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
& $pythonPath scripts/doctor.py
if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed. Follow the repair instructions above.' }
& $pythonPath -m streamlit run app.py --server.address 127.0.0.1 --server.port 8503 --server.headless true
