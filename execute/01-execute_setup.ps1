Write-Host "============================================"
Write-Host "  Install Python dependencies"
Write-Host "============================================"
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pip install -e 03-evidence-vault
.\.venv\Scripts\python -m pip install -r 07-block-indexer/requirements.txt

Write-Host ""
Write-Host "=== Setup complete ==="
