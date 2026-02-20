#!/usr/bin/env bash
set -e
mkdir -p /opt/restoringvalues/run

cd /opt/restoringvalues/current/app

# на всякий случай
rm -f /opt/restoringvalues/run/*.pid || true

start_bg() {
  local name="$1"; shift
  nohup python "$@" > "/opt/restoringvalues/run/${name}.log" 2>&1 &
  echo $! > "/opt/restoringvalues/run/${name}.pid"
}

start_bg simulator Simulator/simulator.py
sleep 1
start_bg reciever Reciever/reciever.py
start_bg business Business/business.py

# чтобы контейнер не завершился — ждём
touch /opt/restoringvalues/run/simulator.log \
      /opt/restoringvalues/run/reciever.log \
      /opt/restoringvalues/run/business.log

# чтобы контейнер не завершился — стримим логи во stdout
tail -n 0 -F /opt/restoringvalues/run/simulator.log \
          /opt/restoringvalues/run/reciever.log \
          /opt/restoringvalues/run/business.log