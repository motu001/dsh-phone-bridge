# stop-bridges.ps1 - stop all phone_bridge processes (Telegram/QQ/media)
$names = 'telegram_bridge.py', 'qq_bridge.py', 'media_server.py'
$hit = $false
Get-CimInstance Win32_Process -Filter "Name like 'python%'" | ForEach-Object {
  $cl = $_.CommandLine
  foreach ($n in $names) {
    if ($cl -like "*$n*") {
      Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
      Write-Host ("stopped PID {0} ({1})" -f $_.ProcessId, $n)
      $hit = $true
      break
    }
  }
}
if (-not $hit) { Write-Host "no phone_bridge process running." }