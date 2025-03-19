$botCount = 5  # Change this to the number of bots you want to launch

for ($i = 1; $i -lt $botCount; $i++) {
      $commandNumber = $i + 1
    Write-Host "Launching bot $i"
    Start-Process "C:\Cambium\bots\PrismLauncher\prismlauncher.exe" -ArgumentList "--launch Bot$i"

}

# Default case
#Write-Host "Unknown bot ID: $botCount. Default launching..."
#Start-Process "C:\Cambium\bots\PrismLauncher\prismlauncher.exe" -ArgumentList "--launch Bot3"