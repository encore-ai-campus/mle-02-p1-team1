"""전체 그림의 준비 확인 또는 승인한 개인 그림 업로드를 실행합니다."""

# [프로젝트 추가] 실행 파일은 단계 선택·진행 기록, 서비스는 파일 대조·업로드를 담당합니다.
# check는 원격 조회만, upload --confirm-upload는 요청한 개인 그림을 실제 추가합니다.

import argparse
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import sys
from time import sleep

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main(argv=None):
    """진행 보고서를 개인 폴더에 남깁니다. 오류 원문·연결 정보·비밀키는 출력하지 않습니다."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description="싼타페 개인 그림 전체 업로드와 실제 용량 확인")
    parser.add_argument("command", choices=("check", "upload"))
    parser.add_argument("--confirm-upload", action="store_true")
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 5))
    parser.add_argument("--report", required=True, help="data/zzong_santafe_lag/reports 아래의 JSON 보고서")
    args = parser.parse_args(argv)
    if (args.command == "upload") != args.confirm_upload:
        parser.error("실제 추가는 사용자 요청 후 upload --confirm-upload로 실행하세요.")
    root = Path(__file__).resolve().parents[3]
    report = (root / args.report).resolve()
    if not report.is_relative_to((root / "data/zzong_santafe_lag/reports").resolve()) or report.suffix != ".json":
        parser.error("보고서는 개인 reports 폴더의 JSON으로 지정하세요.")
    if report.exists():
        parser.error("기존 보고서는 덮어쓰지 않습니다. 새 보고서 이름을 지정하세요.")
    report.parent.mkdir(parents=True, exist_ok=True)
    failure_path = report.with_name(report.stem + "_failures.json")
    state = {"pid": os.getpid(), "started_at": datetime.now().astimezone().isoformat(),
             "command": args.command, "phase": "starting", "remote_writes_authorized": args.confirm_upload}
    service = None

    def save(required=True):
        """쓰기 중 중단돼도 이전 진행 기록을 읽을 수 있게 같은 폴더에서 교체합니다."""
        state["updated_at"] = datetime.now().astimezone().isoformat()
        temporary = report.with_suffix(".tmp")
        # [프로젝트 추가] Windows에서 다른 프로그램이 보고서를 잠깐 읽는 동안
        # 파일 교체가 거절될 수 있어 짧게 재시도합니다. 진행 기록 오류로 업로드를 중단하지 않습니다.
        for attempt in range(10):
            try:
                temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
                temporary.replace(report)
                return
            except PermissionError:
                sleep(0.1 * (attempt + 1))
        state["checkpoint_write_errors"] = state.get("checkpoint_write_errors", 0) + 1
        if required:
            raise PermissionError("개인 진행 보고서 저장을 완료하지 못했습니다.")

    def progress(event):
        """전체 건수·완료·실패를 기록하고 25개마다 간단히 표시합니다."""
        state["phase"] = event["stage"]
        state["progress"] = event
        save(required=False)
        count = event.get("completed")
        if count is None or count % 25 == 0 or count == event.get("total") or event.get("failures", 0):
            print(json.dumps(event, ensure_ascii=False), flush=True)

    try:
        save()
        from car_search_rag.zzong_santafe_lag.full_image_storage_service import FullImageStorageService
        service = FullImageStorageService(progress=progress)
        state["preflight"] = service.prepare()
        save()
        if args.command == "upload":
            state["result"] = service.upload(workers=args.workers)
        else:
            state["result"] = {**state["preflight"], "completed": True, "remote_writes": False}
        state["phase"] = "completed"
        failure_path.write_text(json.dumps(service.failures, ensure_ascii=False, indent=2), encoding="utf-8")
        state["failure_report"] = str(failure_path.relative_to(root))
        save()
        summary = {key: value for key, value in state["result"].items() if key not in {"files", "protected_state"}}
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str), flush=True)
        return 0
    except Exception as error:
        state["phase"] = "failed"
        state["error_type"] = type(error).__name__
        state["failed_stage"] = service.stage if service else "imports"
        state["verified_count"] = len(service.verified) if service else 0
        state["failures"] = service.failures if service else []
        failure_path.write_text(json.dumps(state["failures"], ensure_ascii=False, indent=2), encoding="utf-8")
        save()
        print(json.dumps({key: state[key] for key in ("phase", "error_type", "failed_stage", "verified_count")}, ensure_ascii=False), file=sys.stderr)
        if isinstance(error, ValueError):
            print(str(error), file=sys.stderr)
        print("개인 보고서를 확인하세요. 업로드한 파일은 삭제하지 않으며 다음 실행에서 원본 대조 후 재사용합니다.", file=sys.stderr)
        return 1
    finally:
        if service:
            service.close()


if __name__ == "__main__":
    raise SystemExit(main())
