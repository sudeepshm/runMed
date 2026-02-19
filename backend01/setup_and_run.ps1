
Write-Host "Setting up Backend..."
$venvPath = "$PSScriptRoot\venv"
$python = "$venvPath\Scripts\python.exe"

if (Test-Path $venvPath) {
    Write-Host "Removing existing venv..."
    Remove-Item -Recurse -Force $venvPath
}
Write-Host "Creating new venv..."
python -m venv $venvPath

Write-Host "Installing dependencies..."
& $python -m pip install -r requirements.txt

Write-Host "Starting server..."
& $python -m uvicorn app.main:app --reload
