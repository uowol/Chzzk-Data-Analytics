"""크롤러 프로세스 관리"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PID_FILE = PROJECT_ROOT / "dashboard" / ".crawler_pids.json"


def _load_pids() -> dict[str, int]:
    if PID_FILE.exists():
        try:
            return json.loads(PID_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def _save_pids(pids: dict[str, int]):
    PID_FILE.write_text(json.dumps(pids))


def _is_running(pid: int) -> bool:
    """프로세스가 실제로 살아있는지 확인 (Windows: exit code 체크)."""
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        exit_code = ctypes.c_ulong()
        kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        kernel32.CloseHandle(handle)
        return exit_code.value == 259  # STILL_ACTIVE
    else:
        import os
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def start_crawler(streamer_id: str, streamer_name: str) -> bool:
    """크롤러 시작. 이미 실행 중이면 False 반환."""
    if is_crawler_running(streamer_id):
        return False

    # pipelines YAML 생성
    pipeline_file = f"__dash_{streamer_id[:8]}.yaml"
    pipeline_path = PROJECT_ROOT / "pipelines" / pipeline_file
    pipeline_path.write_text(
        f'streamer_id: "{streamer_id}"\nstreamer_name: "{streamer_name}"\n'
    )

    # 로그 파일에 stdout/stderr 기록
    log_dir = PROJECT_ROOT / "logs" / "crawler"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{streamer_id[:8]}.log"
    log_fp = open(log_file, "w", encoding="utf-8")  # noqa: SIM115

    proc = subprocess.Popen(
        [sys.executable, "run_pipeline.py", "--pipeline", pipeline_file],
        cwd=str(PROJECT_ROOT),
        stdout=log_fp,
        stderr=log_fp,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )

    pids = _load_pids()
    pids[streamer_id] = proc.pid
    _save_pids(pids)
    return True


def stop_crawler(streamer_id: str) -> bool:
    """크롤러 중지. 실행 중이 아니면 False 반환."""
    pids = _load_pids()
    pid = pids.get(streamer_id)

    if pid is None:
        return False

    if _is_running(pid):
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True)
        else:
            import os
            import signal
            os.kill(pid, signal.SIGTERM)

    pids.pop(streamer_id, None)
    _save_pids(pids)
    return True


def is_crawler_running(streamer_id: str) -> bool:
    """크롤러 실행 여부 확인."""
    pids = _load_pids()
    pid = pids.get(streamer_id)
    if pid is None:
        return False
    if _is_running(pid):
        return True
    # 죽은 PID 정리
    pids.pop(streamer_id, None)
    _save_pids(pids)
    return False
