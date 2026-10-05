param(
    [Parameter(Mandatory = $true)][string]$Rx,
    [Parameter(Mandatory = $true)][string]$Tx,
    [Parameter(Mandatory = $true)][string]$Out
)

$ErrorActionPreference = "Stop"
$Image = if ($env:GIGAAM_IMAGE) { $env:GIGAAM_IMAGE } else { "voice-transcription" }
$CacheVol = if ($env:GIGAAM_CACHE_VOLUME) { $env:GIGAAM_CACHE_VOLUME } else { "voice-transcription-cache" }

function Convert-DockerMountPath([string]$Path) {
    $resolved = (Resolve-Path $Path).Path
    if ($resolved -match "^([A-Za-z]):\\(.*)$") {
        $drive = $Matches[1].ToLower()
        $rest = $Matches[2] -replace "\\", "/"
        return "/${drive}/${rest}"
    }
    return $resolved
}

$rxHost = Convert-DockerMountPath $Rx
$txHost = Convert-DockerMountPath $Tx
$outHost = Convert-DockerMountPath $Out
$outDirHost = Convert-DockerMountPath (Split-Path $Out -Parent)

if (-not (Test-Path $Rx)) { throw "Нет файла: $Rx" }
if (-not (Test-Path $Tx)) { throw "Нет файла: $Tx" }
New-Item -ItemType Directory -Force -Path (Split-Path $Out -Parent) | Out-Null

docker volume inspect $CacheVol 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { docker volume create $CacheVol | Out-Null }

docker run --rm `
  -v "${CacheVol}:/app/.cache" `
  -v "${rxHost}:${rxHost}:ro" `
  -v "${txHost}:${txHost}:ro" `
  -v "${outDirHost}:${outDirHost}" `
  $Image `
  --rx $rxHost --tx $txHost --output-file $outHost --quiet
