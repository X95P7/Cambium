#!/usr/bin/expect -f


# Never timeout
set timeout -1


# 0) Ensure mods directory exists and copy mods if needed
# Since /opt/hmc/run is a volume, we need to ensure mods are there at runtime
puts "Ensuring mods directory exists..."
set modCmd {mkdir -p /opt/hmc/run/mods}
spawn sh -c $modCmd
expect eof


# Copy mods from build location to runtime location if they exist
set copyModsCmd {if [ -d /root/.minecraft/mods ] && [ "$(ls -A /root/.minecraft/mods 2>/dev/null)" ]; then echo "Copying mods from /root/.minecraft/mods to /opt/hmc/run/mods..."; cp -n /root/.minecraft/mods/* /opt/hmc/run/mods/ 2>/dev/null || true; echo "Mods copied. Found $(ls -1 /opt/hmc/run/mods 2>/dev/null | wc -l) mod(s) in /opt/hmc/run/mods"; else echo "No mods found in /root/.minecraft/mods"; fi}
spawn sh -c $copyModsCmd
expect eof


# 1) Wait for the Minecraft server to be up
puts "Waiting for mc-forge to start..."
spawn sh -c {
  until nc -z -v -w30 mc-forge 25565; do
    echo "Waiting for mc-forge on port 25565..."
    sleep 5
  done
}
expect eof


# 1.5) Check if we should use xvfb (virtual framebuffer)
set useXvfb 1
if {[info exists env(USE_XVFB)]} {
  set useXvfbStr [string tolower [string trim $env(USE_XVFB)]]
  if {$useXvfbStr == "false" || $useXvfbStr == "0" || $useXvfbStr == "no"} {
    set useXvfb 0
  }
}


# 1.6) Clear cached accounts for offline mode and set username in config
set username "Player"
if {[info exists env(USERNAME)] && [string length $env(USERNAME)] > 0} {
  set username $env(USERNAME)
}


puts "Setting offline username to: $username"
set cmd "mkdir -p /opt/hmc/run && if \[ -d /opt/hmc/HeadlessMC/auth \]; then rm -f /opt/hmc/HeadlessMC/auth/.accounts.json 2>/dev/null || true; fi && if \[ -f /opt/hmc/config.properties \]; then sed -i '/^hmc.offline.username=/d' /opt/hmc/config.properties 2>/dev/null || true; echo 'hmc.offline.username=$username' >> /opt/hmc/config.properties; fi"
spawn sh -c $cmd
expect eof


# 2) Clear cached accounts and login to HeadlessMC (skip if offline mode)
set doLogin 0
if {[info exists env(EMAIL)] && [info exists env(PASSWORD)]} {
  set email [string trim $env(EMAIL)]
  set password [string trim $env(PASSWORD)]
  if {[string length $email] > 0 && [string length $password] > 0 && $email != "" && $password != ""} {
    set doLogin 1
  }
}


# Clear cached accounts if in offline mode
if {!$doLogin} {
  puts "Clearing cached accounts and setting offline mode..."
  set clearCmd "if \[ -d /opt/hmc/HeadlessMC/auth \]; then rm -f /opt/hmc/HeadlessMC/auth/.accounts.json 2>/dev/null || true; fi && if \[ -f /opt/hmc/config.properties \]; then sed -i '/^hmc.email=/d' /opt/hmc/config.properties 2>/dev/null || true; sed -i '/^hmc.password=/d' /opt/hmc/config.properties 2>/dev/null || true; sed -i '/^hmc.offline=/d' /opt/hmc/config.properties 2>/dev/null || true; echo 'hmc.offline=true' >> /opt/hmc/config.properties; fi"
  spawn sh -c $clearCmd
  expect eof
}


if {$doLogin} {
  puts "Logging into HeadlessMC with account..."
  if {$useXvfb} {
    spawn xvfb-run -a java -Dhmc.check.xvfb=true \
      -jar headlessmc-launcher-${env(HMC_VERSION)}.jar \
      --command login ${env(EMAIL)} ${env(PASSWORD)}
  } else {
    spawn java -Dhmc.check.xvfb=false \
      -jar headlessmc-launcher-${env(HMC_VERSION)}.jar \
      --command login ${env(EMAIL)} ${env(PASSWORD)}
  }
  expect eof
} else {
  puts "Skipping login (offline mode - using username: $username)"
}


# 3) Enter the interactive HeadlessMC prompt
puts "Entering HeadlessMC prompt..."
if {$useXvfb} {
  puts "Using virtual framebuffer (xvfb) for headless rendering"
} else {
  puts "Running without virtual framebuffer (xvfb disabled)"
}


# For offline mode, use the -offline flag and username is handled by the game profile
if {$doLogin} {
  # Online mode: launch normally
  if {$useXvfb} {
    spawn xvfb-run -a java -Dhmc.check.xvfb=true \
      -jar headlessmc-launcher-${env(HMC_VERSION)}.jar \
      --command launch forge:${env(MC_VERSION)}
  } else {
    spawn java -Dhmc.check.xvfb=false \
      -jar headlessmc-launcher-${env(HMC_VERSION)}.jar \
      --command launch forge:${env(MC_VERSION)}
  }
} else {
  # Offline mode: use -offline flag and pass username as system property
  if {$useXvfb} {
    spawn xvfb-run -a java -Dhmc.check.xvfb=true -Dhmc.offline.username=$username \
      -jar headlessmc-launcher-${env(HMC_VERSION)}.jar \
      --command launch forge:${env(MC_VERSION)} -offline
  } else {
    spawn java -Dhmc.check.xvfb=false -Dhmc.offline.username=$username \
      -jar headlessmc-launcher-${env(HMC_VERSION)}.jar \
      --command launch forge:${env(MC_VERSION)} -offline
  }
}


# 4) Wait for game to fully load and then send connect commands
# Wait for the FINAL textures-atlas message (512x512) which indicates the game is fully loaded
# There are two texture atlas messages: 16x16 (early) and 512x512 (final)
# The log format is: [HH:MM:SS] [Client thread/INFO]: Created: 512x512 textures-atlas
set gameLoaded 0
# Set a longer timeout for this expect block (60 seconds)
set timeout 60
expect {
   # Wait specifically for the 512x512 textures-atlas (not the early 16x16 one)
   -re {\[.*\] \[Client thread/INFO\]: Created: 1024x512 textures-atlas} {
    set gameLoaded 1
    puts "Game fully loaded (1024x512 textures-atlas detected), waiting for mods to initialize..."
    # Give the game more time to fully initialize and load mods (especially hmc-specifics)
    sleep 8
  }
  timeout {
    puts "Warning: Did not see 512x512 textures-atlas message within 60 seconds, but proceeding anyway..."
    sleep 10
  }
}
# Reset timeout to infinite for the rest of the script
set timeout -1


# Additional wait to ensure hmc-specifics mod is loaded and command system is ready
if {$gameLoaded} {
  puts "Waiting for command system to be ready..."
  sleep 5
} else {
  puts "Game load status uncertain, waiting extra time..."
  sleep 10
}


# Wait a bit more for the game to be fully in the main menu and ready to accept commands
puts "Waiting for game to be in main menu..."
sleep 5


# Parse SERVER environment variable (format: host:port or just host)
if {[info exists env(SERVER)] && [string length $env(SERVER)] > 0} {
  set server $env(SERVER)
  if {[regexp {^([^:]+):?(\d+)?$} $server match host port]} {
    if {$port == ""} {
      set port "25565"
    }
    puts "Attempting to connect to $host:$port"
    # Send connect command - ensure we're sending to the right process
    sleep 1
    send "connect $host $port\r"
    send_user "Sent connect command: connect $host $port\n"
   
    # Wait for connection to establish - look for connection messages or wait
    puts "Waiting for connection to establish..."
    sleep 15
   
    # Send chat message - wait a bit more to ensure we're connected
    puts "Sending chat message..."
    sleep 2
    send "say Hello, world!\r"
    send "gui"
    send_user "Sent say command: say Hello, world!\n"
  } else {
    # Fallback: try to use SERVER as-is, but split on colon
    set parts [split $server ":"]
    if {[llength $parts] == 2} {
      puts "Attempting to connect to [lindex $parts 0]:[lindex $parts 1]"
      sleep 1
      send "connect [lindex $parts 0] [lindex $parts 1]\r"
      send_user "Sent connect command: connect [lindex $parts 0] [lindex $parts 1]\n"
      puts "Waiting for connection to establish..."
      sleep 15
      puts "Sending chat message..."
      sleep 2
      send "say Hello, world!\r"
      send_user "Sent say command: say Hello, world!\n"
    } else {
      puts "Attempting to connect to $server:25565"
      sleep 1
      send "connect $server 25565\r"
      send_user "Sent connect command: connect $server 25565\n"
      puts "Waiting for connection to establish..."
      sleep 15
      puts "Sending chat message..."
      sleep 2
      send "say Hello, world!\r"
      send_user "Sent say command: say Hello, world!\n"
    }
  }
} else {
  puts "No SERVER environment variable set, skipping connection"
}


expect eof
