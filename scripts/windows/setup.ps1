<#
 setup.ps1 · Prepara el .env en Windows (una sola vez).
 Uso (PowerShell, en C:\Users\MATIZ\workshop-2):
     powershell -ExecutionPolicy Bypass -File .\scripts\windows\setup.ps1
 Qué hace: copia .env.example -> .env y genera AIRFLOW_JWT_SECRET y AIRFLOW_FERNET_KEY aleatorias.
#>
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
if (Test-Path ".env") { Write-Host ".env ya existe: no se sobrescribe." -ForegroundColor Yellow; exit 0 }
Copy-Item ".env.example" ".env"

function New-RandomBytes($n) { $b = New-Object byte[] $n; [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); return $b }
$jwt    = -join ((New-RandomBytes 32) | ForEach-Object { $_.ToString("x2") })
$fernet = [Convert]::ToBase64String((New-RandomBytes 32)).Replace("+","-").Replace("/","_")

$lines = Get-Content ".env" | ForEach-Object {
    if     ($_ -like "AIRFLOW_JWT_SECRET=*")  { "AIRFLOW_JWT_SECRET=$jwt" }
    elseif ($_ -like "AIRFLOW_FERNET_KEY=*")  { "AIRFLOW_FERNET_KEY=$fernet" }
    else   { $_ }
}
# UTF-8 sin BOM (Docker Compose no tolera BOM en .env)
[System.IO.File]::WriteAllLines((Join-Path (Get-Location) ".env"), $lines, (New-Object System.Text.UTF8Encoding($false)))
Write-Host ".env creado con claves nuevas. Siguiente paso: docker compose up -d --build" -ForegroundColor Green
