<#
.SYNOPSIS
    Start the Jobot Docker stack.
#>
param(
    [ValidateSet("prod", "dev", "host-ollama")]
    [string]$Mode = "prod"
)

$ErrorActionPreference = "Stop"

$composeFile = "docker-compose.yml"
if ($Mode -eq "dev") {
    $composeFile = "docker-compose.dev.yml"
} elseif ($Mode -eq "host-ollama") {
    $composeFile = "docker-compose.host-ollama.yml"
}

docker compose -f $composeFile up --build -d
docker image prune -f --filter "dangling=true" | Out-Null
Write-Host "Jobot is running at http://localhost:8000 (Mode: $Mode)"
