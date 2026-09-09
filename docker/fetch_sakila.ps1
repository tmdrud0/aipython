# Sakila 샘플 DB 덤프를 docker/initdb/ 로 내려받는다.
# 공식 downloads.mysql.com 은 스크립트 다운로드를 403 차단하므로 jOOQ 미러를 쓴다.
$ErrorActionPreference = 'Stop'

$base   = 'https://raw.githubusercontent.com/jOOQ/sakila/main/mysql-sakila-db'
$outDir = Join-Path $PSScriptRoot 'initdb'

$files = @(
    @{ Url = "$base/mysql-sakila-schema.sql";      Out = '01-schema.sql'; MinBytes = 20000   },
    @{ Url = "$base/mysql-sakila-insert-data.sql"; Out = '02-data.sql';   MinBytes = 8000000 }
)

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

foreach ($f in $files) {
    $dest = Join-Path $outDir $f.Out
    if ((Test-Path $dest) -and ((Get-Item $dest).Length -ge $f.MinBytes)) {
        Write-Host ("SKIP  {0}  ({1:N0} bytes, already present)" -f $f.Out, (Get-Item $dest).Length)
        continue
    }
    Write-Host ("GET   {0}  <- {1}" -f $f.Out, $f.Url)
    Invoke-WebRequest -Uri $f.Url -OutFile $dest -UseBasicParsing -TimeoutSec 120

    $size = (Get-Item $dest).Length
    if ($size -lt $f.MinBytes) {
        throw ("{0} download too small ({1:N0} bytes). Check the mirror URL." -f $f.Out, $size)
    }
    Write-Host ("OK    {0}  ({1:N0} bytes)" -f $f.Out, $size)
}

Write-Host ''
Write-Host 'Done. Next: docker compose -f docker/docker-compose.yml up -d'
