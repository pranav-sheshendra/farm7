$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonExe = Join-Path $projectRoot '.app-venv\Scripts\python.exe'
$portableOllama = Join-Path $projectRoot '.venv\ollama\ollama.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Create .app-venv and install requirements-app.txt first.' }
if (-not $env:ASSISTANT_MODEL) { $env:ASSISTANT_MODEL = 'qwen3.5:4b' }
try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 }
catch {
    if (Test-Path -LiteralPath $portableOllama) {
        $env:OLLAMA_MODELS = Join-Path $projectRoot '.venv\ollama-models'
        $env:OLLAMA_HOST = '127.0.0.1:11434'
        Start-Process -FilePath $portableOllama -ArgumentList 'serve' -WindowStyle Hidden -RedirectStandardOutput '.venv\ollama-out.log' -RedirectStandardError '.venv\ollama-err.log'
    } else { Write-Warning 'Start Ollama and pull qwen3.5:4b to enable chat.' }
}
Write-Host 'Farm AI: http://127.0.0.1:5000'
& $pythonExe serve.py
