#!/bin/sh
echo "Starting Mineflayer bots from start.sh..."
#for i in $(seq 1 ${BOT_COUNT}); do
for i in $(seq 1 1); do
  node bot.js localhost Bot$i &
done
wait