$currentFolder = Split-Path -Leaf $PWD.Path

if ($currentFolder -ne 'Sandbox') {
    Write-Error "Must be run from a folder named 'Sandbox'. Current folder: $($PWD.Path)"
    exit 1
}

$sourceRepo = Resolve-Path '..\..'
$destinationRepo = '.\BrightEyes-MCS'

$currentBranch = git -C $sourceRepo branch --show-current

if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($currentBranch)) {
    Write-Error "Unable to determine the current Git branch in '$sourceRepo'."
    exit 1
}

Write-Host "Source repository: $sourceRepo"
Write-Host "Current branch: $currentBranch"

Remove-Item -Path $destinationRepo -Recurse -Force -ErrorAction SilentlyContinue

git clone --branch $currentBranch $sourceRepo $destinationRepo

if ($LASTEXITCODE -ne 0) {
    Write-Error "git clone failed for branch '$currentBranch'."
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
