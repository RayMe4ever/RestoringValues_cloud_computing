import argparse
import subprocess
import sys
import time
from typing import List


def start(cmd: List[str]) -> subprocess.Popen:
    # Запускаем процесс и НЕ блокируемся
    return subprocess.Popen(cmd)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["prod", "test"], default="prod")
    p.add_argument("--no-gui", action="store_true")
    p.add_argument("--duration", type=int, default=0,
                   help="Сколько секунд работать и завершиться. 0 = работать бесконечно.")
    args = p.parse_args()

    procs: List[subprocess.Popen] = []

    # Важно: после добавления __init__.py можно запускать как модуль: python -m Simulator.simulator
    # Это стабильнее, чем по пути к файлу.
    procs.append(start([sys.executable, "-m", "Simulator.simulator"]))
    time.sleep(0.5)

    procs.append(start([sys.executable, "-m", "Reciever.reciever"]))
    time.sleep(0.5)

    procs.append(start([sys.executable, "-m", "Business.business"]))
    time.sleep(0.5)

    if not args.no_gui:
        gui_mod = "GUI.dash_app_prod" if args.mode == "prod" else "GUI.dash_app_test"
        procs.append(start([sys.executable, "-m", gui_mod]))

    start_ts = time.time()

    try:
        while True:
            # Если задана длительность — выходим по таймеру (для Jenkins/smoke)
            if args.duration and (time.time() - start_ts) >= args.duration:
                break

            # Если любой процесс упал — считаем это ошибкой
            for pr in procs:
                code = pr.poll()
                if code is not None:
                    raise RuntimeError(f"Process exited: {pr.args} code={code}")

            time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        # Корректно гасим процессы
        for pr in procs:
            if pr.poll() is None:
                pr.terminate()
        for pr in procs:
            try:
                pr.wait(timeout=5)
            except Exception:
                pr.kill()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
