"""개인 그림 표본의 업로드 전 확인과 승인한 3개 업로드를 실행합니다."""

# [프로젝트 추가] 소나타와 같은 실행 파일 → 서비스 파일 → SQL Mapper 순서입니다.
# check는 조회만, upload --confirm-upload는 개인 파일 3개 업로드와 DB 경로 연결입니다.
# 모델 실행·전체 그림 업로드·공통 테이블 변경은 없습니다.

import argparse
import json
import logging
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main(argv=None):
    """명령을 선택하고 결과를 표시합니다. 오류에 주소·비밀키·추적 내용을 출력하지 않습니다."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description="싼타페 그림 3개의 준비 확인·Storage 업로드")
    parser.add_argument("command", choices=("check", "upload"))
    parser.add_argument("--confirm-upload", action="store_true", help="승인한 개인 그림 3개만 업로드·DB 연결")
    args = parser.parse_args(argv)
    if (args.command == "upload") != args.confirm_upload:
        parser.error("실제 업로드는 사용자 확인 후 upload --confirm-upload로 실행하세요.")
    service = None
    try:
        from car_search_rag.zzong_santafe_lag.image_storage_service import SampleImageStorageService
        service = SampleImageStorageService()
        result = service.prepare() if args.command == "check" else service.upload(progress=lambda text: print(text, flush=True))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        print(json.dumps({"completed": False, "stage": service.stage if service else "imports",
                          "error_type": type(error).__name__,
                          "verified_remote_files": len(service.completed_objects) if service else 0}, ensure_ascii=False), file=sys.stderr)
        # 외부 라이브러리 오류 원문에는 요청 주소가 들어갈 수 있어 종류만 표시합니다.
        if isinstance(error, ValueError):
            print(str(error), file=sys.stderr)
        print("중단된 단계와 개인 설정을 확인하세요. 비밀키는 채팅에 보내지 마세요.", file=sys.stderr)
        if service and service.stage not in {"not_started", "preflight"}:
            print("일부 파일·DB 연결이 이미 반영됐을 수 있습니다. 다음 실행은 같은 파일을 대조해 재사용하며 삭제·덮어쓰기는 하지 않습니다.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
