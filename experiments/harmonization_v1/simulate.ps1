param(
    [ValidateSet('clean','trojan')][string]$Side,
    [ValidateSet('S','xS')][string]$Unit
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Resolve-Path (Join-Path $PSScriptRoot '../..'))
$tag = if ($Side -eq 'clean') { 'TjFree' } else { 'TjIn' }
$folder = "runs/harmonization_v1/rom_validation/$Side"
$source = "trusthub/AES_unzipped/AES-T100/AES-T100/src/$tag/table.v"
& 'C:/iverilog/bin/iverilog.exe' -g2012 -s tb -o "$folder/$Unit.vvp" $source "$folder/${Unit}_mapped.v" "$folder/${Unit}_test.v"
$compileCode = $LASTEXITCODE
$simulationCode = $null
if ($compileCode -eq 0) {
    & 'C:/iverilog/bin/vvp.exe' "$folder/$Unit.vvp" 2>&1 | Out-File "$folder/${Unit}_simulation.log"
    $simulationCode = $LASTEXITCODE
}
$passed = $compileCode -eq 0 -and $simulationCode -eq 0 -and (Select-String -LiteralPath "$folder/${Unit}_simulation.log" -Pattern 'PASS 256' -Quiet)
@{ compile_returncode=$compileCode; simulation_returncode=$simulationCode; passed=[bool]$passed } | ConvertTo-Json | Set-Content "$folder/${Unit}_simulation_status.json"
if (-not $passed) { exit 1 }
