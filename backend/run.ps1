Set-Location -Path $PSScriptRoot
$env:USERPROFILE = "C:\paddlex_home"
$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "venv를 찾을 수 없습니다: $venvPython"
    exit 1
}

Write-Host "venv 파이썬 사용: $venvPython"
& $venvPython -m uvicorn server:app --reload --port 8000