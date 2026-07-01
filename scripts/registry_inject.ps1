param (
    [string]$RegPath,
    [string]$KeyName,
    [string]$KeyValue,
    [string]$PropertyType = "String"
)

if (-not $RegPath -or -not $KeyName -or -not $KeyValue) {
    Write-Host "Error: Se requieren los parámetros -RegPath, -KeyName, y -KeyValue"
    exit 1
}

try {
    Write-Host "Asegurando que la ruta del registro exista: $RegPath"
    if (-not (Test-Path -Path "Registry::$RegPath")) {
        New-Item -Path "Registry::$RegPath" -Force | Out-Null
    }

    Write-Host "Configurando valor del registro: $KeyName = $KeyValue"
    Set-ItemProperty -Path "Registry::$RegPath" -Name $KeyName -Value $KeyValue -Type $PropertyType
    Write-Host "Clave de registro configurada exitosamente."
    exit 0
} catch {
    Write-Host "Error configurando clave de registro: $_"
    exit 1
}
