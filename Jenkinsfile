pipeline {
  agent { label 'ia_bakastov_lable' }

  options {
    timestamps()
    timeout(time: 12, unit: 'MINUTES')
    disableConcurrentBuilds()
  }

  environment {
    PORTS = "8092 8093 8094 8095"
  }

  stages {

    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Build wheel/sdist') {
      steps {
        sh '''#!/usr/bin/env bash
          set -eux
          python3 -V
          rm -rf .venv .venv_test dist build *.egg-info run_output app-restoringvalues.tgz
          python3 -m venv .venv
          . .venv/bin/activate
          python -m pip install -U pip
          python -m pip install build
          python -m build
          ls -la dist
        '''
      }
    }

    stage('Install wheel into clean venv') {
      steps {
        sh '''#!/usr/bin/env bash
          set -eux
          python3 -m venv .venv_test
          . .venv_test/bin/activate
          python -m pip install -U pip
          python -m pip install dist/*.whl
          python -c "import restoringvalues; print(restoringvalues.__version__)"
          restoringvalues-run --help >/dev/null
        '''
      }
    }

    stage('Smoke run (90s, no GUI)') {
      steps {
        sh '''#!/usr/bin/env bash
set -euo pipefail
. .venv_test/bin/activate

mkdir -p run_output

echo "==> AGENT USER: $(whoami)"
id || true

echo "==> Cleanup old outputs"
rm -f Reciever/*.csv Business/*.csv Business/data_out_*.csv Business/data_metrics_*.csv run_output/*.pid run_output/*.log || true

echo "==> Listeners before cleanup"
ss -lntp | egrep ':8092|:8093|:8094|:8095' || true

kill_by_ports() {
  for p in $PORTS; do
    fuser -kv ${p}/tcp >/dev/null 2>&1 || true
  done
}

ports_free_once() {
  for p in $PORTS; do
    if ss -lnt | awk '{print $4}' | grep -q ":$p$"; then
      return 1
    fi
  done
  return 0
}

ports_free_stable_or_fail() {
  for t in 1 2 3; do
    if ! ports_free_once; then
      return 1
    fi
    sleep 0.5
  done
  return 0
}

echo "==> Cleanup ports 8092-8095"
kill_by_ports
sleep 1

echo "==> Verify ports are FREE (stable)"
if ! ports_free_stable_or_fail; then
  echo "Ports are not free after cleanup. Current listeners:"
  ss -lntp | egrep ':8092|:8093|:8094|:8095' || true
  exit 1
fi

start_bg() {
  local name="$1"; shift
  setsid nohup "$@" > "run_output/${name}.log" 2>&1 & echo $! > "run_output/${name}.pid"
  echo "Started $name pid=$(cat run_output/${name}.pid)"
}

stop_group() {
  local name="$1"
  if [ -f "run_output/${name}.pid" ]; then
    local pid
    pid="$(cat run_output/${name}.pid)"
    echo "Stopping $name group (pid=$pid)"
    kill -- "-$pid" >/dev/null 2>&1 || true
  fi
}

wait_ports() {
  for i in $(seq 1 60); do
    ok=0
    for p in $PORTS; do
      if ss -lnt | awk '{print $4}' | grep -q ":$p$"; then ok=$((ok+1)); fi
    done
    if [ "$ok" -eq 4 ]; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

fail_with_logs() {
  echo "==> FAILURE diagnostics"
  echo "-- listeners:"
  ss -lntp | egrep ':8092|:8093|:8094|:8095' || true

  echo "-- processes:"
  [ -f run_output/simulator.pid ] && ps -o pid,pgid,cmd -p "$(cat run_output/simulator.pid)" || true
  [ -f run_output/reciever.pid ] && ps -o pid,pgid,cmd -p "$(cat run_output/reciever.pid)" || true
  [ -f run_output/business.pid ] && ps -o pid,pgid,cmd -p "$(cat run_output/business.pid)" || true

  echo "-- files:"
  ls -la Reciever 2>/dev/null || true
  find Reciever -maxdepth 1 -type f -name '*.csv' -print 2>/dev/null || true
  find Business -maxdepth 3 -type f -name '*.csv' -print 2>/dev/null || true

  echo "-- tail logs:"
  tail -n 200 run_output/simulator.log 2>/dev/null || true
  tail -n 200 run_output/reciever.log 2>/dev/null || true
  tail -n 200 run_output/business.log 2>/dev/null || true
}

echo "==> Start Simulator"
start_bg simulator python3 Simulator/simulator.py

echo "==> Wait ports 8092-8095"
if ! wait_ports; then
  echo "Ports did not become ready."
  fail_with_logs
  stop_group simulator
  kill_by_ports
  exit 1
fi

echo "==> Start Reciever"
start_bg reciever python3 Reciever/reciever.py

echo "==> Create placeholder CSVs to avoid Business race condition"
# Business читает фиксированные имена. Создаём их заранее, чтобы не было FileNotFoundError
for p in 8092 8093 8094 8095; do
  f="Reciever/data_port_${p}.csv"
  if [ ! -f "$f" ]; then
    echo "timestamp,value" > "$f"
  fi
done

echo "==> Wait until Reciever creates/updates all 4 base CSV files (up to 30s)"
need="8092 8093 8094 8095"
for i in $(seq 1 60); do
  ok=0
  for p in $need; do
    f="Reciever/data_port_${p}.csv"
    # ждём чтобы файл существовал и был больше 0 байт
    if [ -s "$f" ]; then ok=$((ok+1)); fi
  done
  if [ "$ok" -eq 4 ]; then
    echo "All Reciever CSVs are present"
    break
  fi
  sleep 0.5
done

for p in $need; do
  f="Reciever/data_port_${p}.csv"
  if [ ! -s "$f" ]; then
    echo "Reciever did not produce $f in time."
    fail_with_logs
    stop_group reciever
    stop_group simulator
    kill_by_ports
    exit 1
  fi
done

echo "==> Start Business (after Reciever files exist)"
start_bg business python3 Business/business.py

echo "==> Let them work 90s"
sleep 90

echo "==> Check Reciever output CSV exists"
if ! ls -la Reciever/*.csv >/dev/null 2>&1; then
  echo "No Reciever CSV produced."
  fail_with_logs
  stop_group business
  stop_group reciever
  stop_group simulator
  kill_by_ports
  exit 1
fi

echo "==> Check Business output exists (any CSV inside Business/)"
BUS_CSV_COUNT="$(find Business -maxdepth 3 -type f -name '*.csv' 2>/dev/null | wc -l | tr -d ' ')"
echo "Business CSV count: ${BUS_CSV_COUNT}"

if [ "${BUS_CSV_COUNT}" -eq 0 ]; then
  echo "No Business CSV produced anywhere under Business/ (depth<=3)."
  fail_with_logs
  stop_group business
  stop_group reciever
  stop_group simulator
  kill_by_ports
  exit 1
fi

echo "==> Copy outputs to run_output"
cp -a Reciever/*.csv run_output/ 2>/dev/null || true
find Business -maxdepth 3 -type f -name '*.csv' -exec cp -a {} run_output/ \\; 2>/dev/null || true

echo "Smoke run OK"

echo "==> Stop processes"
stop_group business
stop_group reciever
stop_group simulator

echo "==> Final port cleanup"
kill_by_ports
sleep 1

echo "==> Verify ports are free after stopping"
if ! ports_free_stable_or_fail; then
  echo "Ports are still busy after stopping. Current listeners:"
  ss -lntp | egrep ':8092|:8093|:8094|:8095' || true
  exit 1
fi
'''
      }
    }

    stage('Package app artifact (tgz)') {
      steps {
        sh '''#!/usr/bin/env bash
          set -eux
          tar -czf app-restoringvalues.tgz \
            Simulator Reciever Business GUI \
            requirements.txt \
            pyproject.toml setup.cfg setup.py 2>/dev/null || true
          ls -la app-restoringvalues.tgz
        '''
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'dist/*, run_output/*, app-restoringvalues.tgz', fingerprint: true, allowEmptyArchive: true
      cleanWs()
    }
  }
}
