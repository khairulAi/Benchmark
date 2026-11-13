$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
$taskPython = @((Join-Path $PWD '.venv\Scripts\python.exe'),(Join-Path $env:USERPROFILE 'anaconda3\python.exe')) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (!$taskPython) { $taskPython = (Get-Command python.exe -ErrorAction SilentlyContinue).Source }
if (!$taskPython) { throw 'Install Python from python.org first, then run setup again.' }
if (!(Test-Path -LiteralPath '.bootstrap\bin\uv.exe')) { & $taskPython -m pip install --target .bootstrap uv; if ($LASTEXITCODE) { throw 'uv installation failed' } }
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PWD '.runtime'
$taskModels = & $taskPython -c "from pathlib import Path; import re; p=Path('.env'); t=p.read_text(encoding='utf-8-sig') if p.exists() else ''; m=re.search(r'(?m)^MODELS_DIR=(.+)$',t); print(m.group(1).strip().strip(chr(34)).strip(chr(39)) if m else str(Path.cwd()/'models'))"
$taskModelParent = Split-Path ([IO.Path]::GetFullPath($taskModels)) -Parent
$env:UV_CACHE_DIR = Join-Path $taskModelParent '.package-cache'
& .\.bootstrap\bin\uv.exe venv --python 3.11 .venv --allow-existing
if ($LASTEXITCODE) { throw 'Python environment setup failed' }
& .\.bootstrap\bin\uv.exe pip install --python .venv\Scripts\python.exe -r requirements.txt
if ($LASTEXITCODE) { throw 'Dependency setup failed' }
# Default ONNX setup needs no Torch/Transformers conversion environment.
& .\.venv\Scripts\python.exe scripts\prepare_models.py --profile zipformer
if ($LASTEXITCODE) { throw 'Model preparation failed' }
& .\.venv\Scripts\python.exe scripts\prepare_feature_models.py
if ($LASTEXITCODE) { throw 'Feature model preparation failed' }
Write-Host 'Setup complete. Run START-BENCHMARK.cmd.'
