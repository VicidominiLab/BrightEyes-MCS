$currentFolder = Split-Path -Leaf $PWD.Path

if ($currentFolder -ne 'Sandbox') {
    Write-Error "Must be run from a folder named 'Sandbox'. Current folder: $($PWD.Path)"
    exit 1
}

Remove-Item -Path '.\BrightEyes-MCS' -Recurse -Force -ErrorAction SilentlyContinue

git clone '..\..\' '.\BrightEyes-MCS'

if ($LASTEXITCODE -ne 0) {
    Write-Error 'git clone failed.'
    exit 1
}

$wsb = Get-ChildItem -Path '.' -Filter '*.wsb' -Recurse |
    Select-Object -First 1

if (-not $wsb) {
    Write-Error 'No .wsb file was found.'
    exit 1
}

Write-Host "Starting: $($wsb.FullName)"
Start-Process $wsb.FullName