<#
 trigger.ps1 · Dispara el DAG con parámetros SIN problemas de comillas en PowerShell.
 Ejemplos (en C:\Users\MATIZ\workshop-2):
   .\scripts\windows\trigger.ps1                                                   # Prueba A  (batch_001)
   .\scripts\windows\trigger.ps1 -BatchId batch_fail_001 -Fault spotify_null_track_id    # Prueba B
   .\scripts\windows\trigger.ps1 -BatchId batch_fail_002 -Fault grammy_invalid_year      # Prueba B (Grammy)
   .\scripts\windows\trigger.ps1 -Transient extract_grammys                        # retry selectivo en extracción
   .\scripts\windows\trigger.ps1 -Transient load_dw                                # falla a mitad de carga + retry
 (Si PowerShell bloquea el script:  powershell -ExecutionPolicy Bypass -File .\scripts\windows\trigger.ps1 ...)
 Por qué base64: PowerShell 5.1 elimina las comillas dobles al pasar JSON a programas externos.
#>
param(
  [string]$BatchId   = "batch_001",
  [ValidateSet("none","spotify_null_track_id","grammy_invalid_year")][string]$Fault = "none",
  [ValidateSet("none","extract_grammys","load_dw")][string]$Transient = "none"
)
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
$json = (@{ batch_id = $BatchId; fault_injection = $Fault; simulate_transient = $Transient } | ConvertTo-Json -Compress)
$b64  = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json))
Write-Host "Disparando DAG con conf: $json" -ForegroundColor Cyan
docker compose exec -e CONF_B64=$b64 airflow-scheduler bash -c 'airflow dags trigger reliable_music_pipeline --conf "$(echo $CONF_B64 | base64 -d)"'
Write-Host "Sigue la ejecución en http://localhost:8080  (o: docker compose exec airflow-scheduler airflow dags list-runs reliable_music_pipeline)" -ForegroundColor Green
