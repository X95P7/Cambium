#!/usr/bin/expect -f

# Never timeout
set timeout -1

# 1) Wait for the Minecraft server to be up
puts "Waiting for mc-forge to start..."
spawn sh -c {
  until nc -z -v -w30 mc-forge 25565; do
    echo "Waiting for mc-forge on port 25565..."
    sleep 5
  done
}
expect eof

# 2) Login to HeadlessMC
puts "Logging into HeadlessMC..."
spawn xvfb-run -a java -Dhmc.check.xvfb=true \
  -jar headlessmc-launcher-${env(HMC_VERSION)}.jar \
  --command login ${env(EMAIL)} ${env(PASSWORD)}
expect eof

# 3) Enter the interactive HeadlessMC prompt
puts "Entering HeadlessMC prompt..."
spawn xvfb-run -a java -Dhmc.check.xvfb=true \
  -jar headlessmc-launcher-${env(HMC_VERSION)}.jar \
  --command launch forge:${env(MC_VERSION)}

# 4) Send launch and connect commands
# 1) Wait for that unique “Sound engine started” line
expect {
  -re {Client thread/INFO\]: Created: 1024x512 textures-atlas} {
  send "connect $env(SERVER)\r"
    send "say Hello, world!\r"
    # once we see it, fall through to next step
  }
}

expect eof