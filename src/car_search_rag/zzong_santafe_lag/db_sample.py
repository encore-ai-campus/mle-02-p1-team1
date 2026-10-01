"""개인 DB 읽기와 PDF 예제의 저장 형태 미리보기를 실행합니다."""

# [프로젝트 추가] connection은 조회만, preview는 메모리 변환만 수행합니다.
# 테이블 생성·INSERT·파일 업로드 명령은 이 실행 파일에 없습니다.

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    # [프로젝트 추가] 이동한 폴더에서 src를 등록해 개인 코드와 공통 SQL 모듈을 함께 찾습니다.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main(argv=None):
    """조회 또는 변환을 실행하고, 연결 실패 시 비밀번호 없는 오류 안내를 표시합니다."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="개인 DB 연결·저장 형태 준비 (자료 저장 없음)")
    parser.add_argument("command", choices=("connection", "preview"))
    parser.add_argument("--full-text", action="store_true", help="변환한 부모의 검색용 글 전체 표시")
    args = parser.parse_args(argv)
    if args.full_text and args.command != "preview":
        parser.error("--full-text는 preview에서 사용합니다.")
    try:
        if args.command == "connection":
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
            service = ManualService().prepare(progress=lambda text: print(text, flush=True))
            preview = build_sample_rows(service)
            print(json.dumps(preview.summary(), ensure_ascii=False, indent=2))
            if args.full_text:
                for row in preview.tables["parent_records"]:
                    print(f'\n--- {row["title"]} | PDF {row["source_pages"]} ---')
                    print(row["content"])
        return 0
    except Exception as error:
        # psycopg 오류에 연결 주소가 들어갈 수 있어 원문 오류·추적 내용을 출력하지 않습니다.
        if args.command == "connection":
            print(f"DB 조회를 멈췄습니다. 오류 종류: {type(error).__name__}", file=sys.stderr)
            print("개인 .env의 ZZONG_DB_URL과 네트워크·DB 권한을 확인하세요. 비밀번호는 공유하지 마세요.", file=sys.stderr)
        else:
            print(f"변환을 멈췄습니다: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
