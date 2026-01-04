#!/usr/bin/expect -f

# Set timeout for startup (60 seconds), then no timeout for running game
set timeout 60

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

# 4) Wait for Minecraft to fully load, then connect to server
set connected 0
expect {
  -re {Client thread/INFO\]: Created: (1024|512)x(1024|512) textures-atlas} {
    # Once we see textures loaded, switch to no timeout for game runtime
    set timeout -1
    # Wait for game to fully initialize before connecting
    after 5000
    # Parse SERVER environment variable (format: host:port or just host)
    set server $env(SERVER)
    if {[regexp {^([^:]+):?(\d+)?$} $server match host port]} {
      if {$port == ""} {
        set port "25565"
      }
      puts "Connecting to $host:$port"
      send "connect $host $port\r"
      set connected 1
    } else {
      # Fallback: try to use SERVER as-is, but split on colon
      set parts [split $server ":"]
      if {[llength $parts] == 2} {
        send "connect [lindex $parts 0] [lindex $parts 1]\r"
        set connected 1
      } else {
        send "connect $server 25565\r"
        set connected 1
      }
    }
    # Wait for connection to establish before sending chat
    after 3000
    if {$connected == 1} {
      send "say Hello, world!\r"
    }
    exp_continue
  }
  -re {.*} {
    exp_continue
  }
  eof {
    puts "Minecraft process ended"
  }
  timeout {
    puts "ERROR: Timeout waiting for Minecraft to start (60 seconds)."
    puts "This usually means Minecraft is hanging during initialization."
    puts "Common causes:"
    puts "  1. USE_XVFB=false - Minecraft needs a virtual framebuffer. Set USE_XVFB=true"
    puts "  2. Graphics/display initialization failure"
    puts "  3. Missing dependencies or configuration issues"
    exit 1
  }
}
