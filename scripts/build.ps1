<#
.SYNOPSIS
    Build Jobot Docker images.
#>
param(
    [ValidateSet("prod", "dev")]
    [string]$Mode = "prod"
)

$ErrorActionPreference = "Stop"

if ($Mode -eq "dev") {
    docker build -f Dockerfile.dev -t jobot:dev .
} else {
    docker build -t jobot:latest .
}
docker image prune -f --filter "dangling=true" | Out-Null
