"""개인 DB 읽기와 PDF 예제의 저장 형태 미리보기를 실행합니다."""

# [프로젝트 추가] connection은 조회만, preview는 변환만, embed는 표본 임베딩만 수행합니다.
# [프로젝트 추가] save는 승인 후 --confirm-save로 지정할 때만 개인 표본을 저장합니다.
# 테이블 생성·파일 업로드 명령은 없습니다.

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

if __package__ in {None, ""}:
    # [프로젝트 추가] 이동한 폴더에서 src를 등록해 개인 코드와 공통 SQL 모듈을 함께 찾습니다.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main(argv=None):
    """조회 또는 변환을 실행하고, 연결 실패 시 비밀번호 없는 오류 안내를 표시합니다."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="개인 DB 연결·표본 임베딩·승인한 표본 저장")
    parser.add_argument("command", choices=("connection", "preview", "embed", "save", "inspect"))
    parser.add_argument("--confirm-save", action="store_true", help="승인한 표본 23개 행의 실제 DB 저장")
    parser.add_argument("--run-id", type=UUID, help="inspect에서 읽을 저장된 처리 작업 번호")
    parser.add_argument("--full-text", action="store_true", help="변환한 부모의 검색용 글 전체 표시")
    args = parser.parse_args(argv)
    if args.command == "save" and not args.confirm_save:
        parser.error("실제 저장은 사용자 확인 후 save --confirm-save로 실행하세요.")
    if args.confirm_save and args.command != "save":
        parser.error("--confirm-save는 save에서 사용합니다.")
    if args.command == "inspect" and args.run_id is None:
        parser.error("inspect에는 --run-id로 저장된 처리 작업 번호를 지정하세요.")
    if args.run_id is not None and args.command != "inspect":
        parser.error("--run-id는 inspect에서 사용합니다.")
    if args.full_text and args.command == "connection":
        parser.error("--full-text는 connection 이외 명령에서 사용합니다.")
    try:
        if args.command == "inspect":
            from car_search_rag.zzong_santafe_lag.sample_store import read_sample_report
            print(json.dumps(read_sample_report(args.run_id), ensure_ascii=False, indent=2))
        elif args.command == "connection":
            from car_search_rag.zzong_santafe_lag.database import ManualRepository, PersonalSqlSession
            report = ManualRepository(PersonalSqlSession(read_only=True)).connection_report()
            expected = {"documents", "processing_runs", "parent_records", "chunks", "images", "record_images"}
            if {row["table_name"] for row in report["tables"]} != expected:
                raise ValueError("개인 테이블 여섯 개를 확인해야 합니다.")
            if report["connection"]["read_only"] != "on":
                raise ValueError("읽기 전용 연결 상태를 확인해야 합니다.")
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            from car_search_rag.zzong_santafe_lag.manual_service import ManualService
            from car_search_rag.zzong_santafe_lag.db_rows import build_sample_rows
            config = None
            if args.command == "save":
                from car_search_rag.zzong_santafe_lag.config import ManualConfig
                from car_search_rag.zzong_santafe_lag.sample_store import APPROVED_REVISION
                config = ManualConfig(model_revision=APPROVED_REVISION)
            service = ManualService(config).prepare(progress=lambda text: print(text, flush=True))
            preview = build_sample_rows(service)
            if args.command in {"embed", "save"}:
                from car_search_rag.zzong_santafe_lag.sample_embedding import embed_sample_rows
                embed_sample_rows(preview, service, progress=lambda text: print(text, flush=True))
            if args.command == "save":
                from car_search_rag.zzong_santafe_lag.sample_store import save_sample_rows
                print('승인한 개인 표본만 저장하고 새 연결에서 다시 읽습니다.', flush=True)
                saved_report = save_sample_rows(preview, service)
                print(json.dumps(saved_report, ensure_ascii=False, indent=2))
            print(json.dumps(preview.summary(), ensure_ascii=False, indent=2))
            if args.full_text:
                for row in preview.tables["parent_records"]:
                    print(f'\n--- {row["title"]} | PDF {row["source_pages"]} ---')
                    print(row["content"])
        return 0
    except Exception as error:
        # psycopg 오류에 연결 주소가 들어갈 수 있어 원문 오류·추적 내용을 출력하지 않습니다.
        if args.command in {"connection", "save", "inspect"}:
            print(f"DB 작업을 멈췄습니다. 오류 종류: {type(error).__name__}", file=sys.stderr)
            print("개인 .env의 ZZONG_DB_URL과 네트워크·DB 권한을 확인하세요. 비밀번호는 공유하지 마세요.", file=sys.stderr)
            if isinstance(error, (ValueError, RuntimeError)):
                print(str(error), file=sys.stderr)
            if args.command == "save":
                print('저장 상태를 먼저 조회하세요. 같은 표본은 비교 후 재사용하며 자동 덮어쓰지 않습니다.', file=sys.stderr)
        else:
            print(f"변환을 멈췄습니다: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
