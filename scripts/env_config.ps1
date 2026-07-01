param (
    [string]$VarName,
    [string]$VarValue
)

if (-not $VarName -or -not $VarValue) {
    Write-Host "Error: Se requieren los parámetros -VarName y -VarValue"
    exit 1
}

try {
    Write-Host "Inyectando variable de entorno: $VarName = $VarValue"
    [Environment]::SetEnvironmentVariable($VarName, $VarValue, [EnvironmentVariableTarget]::Machine)
    Write-Host "Variable de entorno configurada exitosamente."
    exit 0
} catch {
    Write-Host "Error configurando variable de entorno: $_"
    exit 1
}
