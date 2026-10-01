"""개인 싼타페 PDF 실험의 실행 파일입니다. 터미널 명령으로 사용할 수 있습니다."""

# [프로젝트 추가] 같은 작업을 터미널에서 실행하도록 preview/search/evaluate 명령을 제공합니다.
# preview는 청킹 확인, search는 근거 조회, evaluate는 기존 질문으로 검색 방식 비교입니다.

import argparse
import sys
from pathlib import Path

# 파일을 직접 실행해도 src 폴더의 car_search_rag 패키지를 찾을 수 있게 합니다.
# 현재 작업 폴더에 의존하지 않으므로 notebooks에서 실행해도 PDF 경로가 달라지지 않습니다.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from car_search_rag.zzong_santafe_lag.manual_service import ManualService


def report(message):
    """오래 걸리는 단계에서도 진행 상황을 즉시 화면에 표시합니다."""
    print(message, flush=True)


def print_summary(service):
    """미리보기 결과를 표시합니다. 파일이나 DB에는 쓰지 않습니다."""
    info = service.summary()
    print(f'PDF: {info["pdf_pages"]}쪽 | 이미지 참조: {info["image_references"]}개')
    print(f'부모 원문: {info["parent_records"]}개 | 검색 조각: {info["search_chunks"]}개')
    print(f'입력 한도: {info["token_budget"]}토큰 | 가장 긴 조각: {info["largest_chunk_tokens"]}토큰')
    print("검토 상태:", info["verification_status"])


# [프로젝트 추가] 출처·그림 연결·검토 상태를 함께 표시합니다. --full-text로 원문 전체를 볼 수 있습니다.
def print_hits(engine, question, top_k, full_text=False):
    """검색 후보와 출처·검토 상태를 표시합니다. 표시한 글은 생성 답변이 아닙니다."""
    print(f"\n질문: {question}")
    hits = engine.search(question, top_k=top_k)
    for index, hit in enumerate(hits, start=1):
        parent = hit["parent_record"]
        meta = parent["metadata"]
        print(f'\n후보 {index}: {meta["title"]} | 결합 점수 {hit["score"]:.3f}')
        print("질문 목적:", ", ".join(hit["routing"]["intents"]))
        print("PDF 쪽:", meta["source_pages"], "| 매뉴얼 시작 쪽:", meta["manual_page_number"])
        print("원문 ID:", meta["record_id"], "| 검토 상태:", meta["verification_status"])
        if hit["used_fallback"]:
            print("목적에 맞는 후보가 부족해 다른 유형의 후보도 포함했습니다.")
        package = engine.evidence(hit)
        for record in package["context_records"]:
            context_meta = record["metadata"]
            print(f'  연결 원문: {context_meta["title"]} | PDF {context_meta["source_pages"]}')
            text = record["content"]
            print(text if full_text else text[:800])
            if not full_text and len(text) > 800:
                print("  (화면에는 앞 800자만 표시합니다. --full-text로 전체를 확인할 수 있습니다.)")
        for image in package["image_parts"]:
            print("  그림 참조:", image["pdf_page_number"], image.get("name") or image.get("pdf_image_key"),
                  "| 연결:", image.get("local_path") or "현재 이미지 파일 경로 없음")
        if package["pending_review_record_ids"]:
            print("  원본 대조 필요:", package["pending_review_record_ids"])
        if package["unreviewed_continuation_record_ids"]:
            print("  이어지는 미검토 자료:", package["unreviewed_continuation_record_ids"])
    print("\n현재 기능은 근거 검색입니다. 답변 생성과 근거 부족 판단은 다음 단계입니다.")


def main(argv=None):
    """명령을 해석하고 미리보기, 근거 검색 또는 기존 30문항 비교를 실행합니다."""
    # Windows에서 한글 출력이 깨지지 않도록 실행 명령의 출력 인코딩을 통일합니다.
    # 이 파일을 다른 코드에서 가져오기만 할 때는 출력 설정을 바꾸지 않습니다.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="개인 싼타페 PDF 청킹·로컬 임베딩 실험")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preview", help="PDF와 청킹 개수 확인 (임베딩 모델 실행 없음)")
    search = commands.add_parser("search", help="전체 임베딩 후 질문의 PDF 근거 검색")
    search.add_argument("--question", action="append", required=True, help="질문. 반복하여 여러 질문 입력 가능")
    search.add_argument("--top-k", type=int, default=3, help="표시할 후보 개수 (기본 3)")
    search.add_argument("--full-text", action="store_true", help="연결 원문 전체 표시")
    commands.add_parser("evaluate", help="노트북과 같은 30개 질문으로 세 검색 방식 비교")
    args = parser.parse_args(argv)
    if args.command == "search" and args.top_k < 1:
        parser.error("--top-k는 1 이상이어야 합니다.")
    service = ManualService()
    try:
        service.prepare(progress=report)
        print_summary(service)
        if args.command == "preview":
            return 0
        # 잘못된 질문 때문에 전체 임베딩을 먼저 계산하지 않도록 입력부터 확인합니다.
        if args.command == "search":
            if args.top_k > len(service.parents):
                raise ValueError("후보 개수는 전체 부모 기록 수를 넘을 수 없습니다.")
            for question in args.question:
                if not question.strip() or service.token_counter.count(question) > service.token_counter.budget:
                    raise ValueError("질문을 비우지 말고 128토큰 이내로 짧게 입력하세요.")
        engine = service.build_search(progress=report)
        if args.command == "search":
            for question in args.question:
                print_hits(engine, question, args.top_k, args.full_text)
        else:
            from car_search_rag.zzong_santafe_lag.evaluation import compare_search
            compare_search(engine, progress=report)
        return 0
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as error:
        print(f"실행을 멈췄습니다: {error}", file=sys.stderr)
        print("모델이 없다는 오류라면 기존 노트북에서 사용한 .venv와 모델 캐시를 확인하세요.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
