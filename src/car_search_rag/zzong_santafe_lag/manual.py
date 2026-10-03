"""개인 싼타페 PDF 실험의 실행 파일입니다. 터미널 명령으로 사용할 수 있습니다."""

# [프로젝트 추가] 터미널 실행 명령: preview/search/evaluate/db-search/storage-plan.
# preview는 청킹 확인, search는 전체 메모리 검색, evaluate는 기존 질문으로 검색 방식 비교입니다.
# db-search는 저장된 표본 검색이며 질문만 임베딩합니다.
# storage-plan은 전체 자료 저장 범위 조사이며 토큰 계산만 합니다.
# full-preview/full-embed/full-save는 전체 행 준비·메모리 임베딩·승인 후 저장입니다.

import argparse
import json
import re
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


# [프로젝트 추가] DB에서 찾은 원문·필수 각주·그림을 함께 표시하는 출력 함수입니다.
# 이 함수는 글을 새로 요약하거나 답변을 생성하지 않습니다.
def print_db_result(result, full_text=False):
    """저장된 자료의 검색 근거를 읽기 쉬운 순서로 표시합니다."""
    print(f'\n질문: {result["question"]}')
    print(f'질문 벡터: {result["query_vector_shape"]} | 질문 토큰: {result["query_token_count"]}')
    for hit in result["candidates"]:
        print(f'\n근거 후보 {hit["rank"]}: {hit["title"]} | 코사인 유사도 {hit["similarity"]:.3f}')
        if result["search_method"] != "pgvector_cosine_only":
            print(f'  결합 점수: {hit["ranking_score"]:.3f} | 질문 목적: {hit["routing"]["intents"]}')
        for record in hit["context_records"]:
            print(f'  연결 원문: {record["title"]} | PDF {record["source_pages"]} | 매뉴얼 {record["manual_page_number"]}')
            print(f'  원문 ID: {record["record_id"]} | 검토 상태: {record["verification_status"]}')
            text = record["content"]
            print(text if full_text else text[:800])
            if not full_text and len(text) > 800:
                print("  (앞 800자만 표시합니다. --full-text로 연결 원문 전체를 확인하세요.)")
        # [프로젝트 추가] 긴 주제의 그림 참조를 전부 출력하지 않고 화면에는 처음 5개를 표시합니다.
        # 전체 참조는 반환 결과·JSON 출력에 유지합니다. 업로드 전 자료도 검토 상태와 함께 남깁니다.
        for image in hit["image_parts"][:5]:
            print(f'  그림: PDF {image["pdf_page_number"]} | {image["file_name"] or image["pdf_image_key"]} | {image["width"]} × {image["height"]}')
            for link in image["descriptions"]:
                print("  그림 설명:", link["description"], "| 연결 상태:", link["linkage_status"])
            print("  그림 주소:", image["public_url"] or (
                "공개 주소 설정 확인 필요" if image["upload_status"] == "uploaded" else "파일 업로드 전 — DB 참조만 연결됨"))
        if len(hit["image_parts"]) > 5:
            print(f'  그림 참조 총 {len(hit["image_parts"])}개 중 화면에는 5개만 표시합니다.')
        if hit["pending_review_record_ids"]:
            print("  원본 대조 필요:", hit["pending_review_record_ids"])
        if hit["unreviewed_continuation_record_ids"]:
            print("  이어지는 미검토 자료:", hit["unreviewed_continuation_record_ids"])
    print("\n", result["coverage_notice"])
    print("DB 조회만 했으며 문서 벡터 재계산·저장·파일 업로드·답변 생성은 하지 않았습니다.")


def print_answer(result):
    """설명서 발췌와 사용할 수 있는 그림 주소를 표시합니다. 내부 메타데이터는 JSON 옵션으로 봅니다."""
    print(f'\n질문: {result["question"]}')
    print(result["answer"])
    if result.get("reason"):
        print("이유:", result["reason"])
    if result.get("generation_notice"):
        print("생성 안내:", result["generation_notice"])
    for image in result["images"]:
        print(f'\n관련 그림: PDF {image["pdf_page_number"]}쪽 · {image["file_name"]}')
        for description in image["descriptions"]:
            print(description["description"])
        print("그림 주소:", image["public_url"])
    if result["pending_image_references"]:
        print(f'\n파일 업로드 또는 연결 확인 전인 그림 참조: {len(result["pending_image_references"])}개')


def main(argv=None):
    """명령을 해석하고 미리보기·전체 검색·표본 DB 검색·기존 30문항 비교 중 하나를 실행합니다."""
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
    # [프로젝트 추가] db-search는 저장된 11개 청크를 사용합니다. 전체 PDF prepare를 거치지 않습니다.
    db_search = commands.add_parser("db-search", help="저장된 DB 표본 검색 (질문만 임베딩)")
    db_search.add_argument("--question", action="append", required=True, help="질문. 반복하여 여러 질문 입력 가능")
    db_search.add_argument("--top-k", type=int, default=3, choices=range(1, 5), help="표시할 근거 묶음 수 (기본 3, 최대 4)")
    db_search.add_argument("--full-text", action="store_true", help="필수 각주를 포함한 연결 원문 전체 표시")
    db_search.add_argument("--json", action="store_true", dest="json_output", help="결과를 JSON으로 화면 출력 (파일 저장 없음)")
    commands.add_parser("evaluate", help="노트북과 같은 30개 질문으로 세 검색 방식 비교")
    # [프로젝트 추가] M6는 저장한 전체 벡터를 재사용합니다. 기본 실행은 질문 목록 조회입니다.
    # --run-evaluation을 지정해야 30문항을 검색합니다. DB 쓰기·문서 재임베딩은 없습니다.
    db_evaluate = commands.add_parser("db-evaluate", help="전체 DB의 기존 30문항 평가 준비·실행 (읽기 전용)")
    db_evaluate.add_argument("--run-id", required=True, help="평가할 전체 저장 작업 번호")
    db_evaluate.add_argument("--method", choices=("purpose", "semantic", "purpose_specific"), default="purpose", help="비교할 검색 방식")
    db_evaluate.add_argument("--run-evaluation", action="store_true", help="질문 목록 조회를 넘어 30문항을 실제 검색·채점")
    db_evaluate.add_argument("--json", action="store_true", dest="json_output", help="질문 목록 또는 평가 결과를 JSON으로 표시")
    # [프로젝트 추가] 전체 저장 범위를 정하기 위한 조사입니다. 실제 저장 명령이 아닙니다.
    storage_plan = commands.add_parser("storage-plan", help="전체 자료의 저장 범위·검토 목록 조사 (임베딩·저장 없음)")
    storage_plan.add_argument("--json", action="store_true", dest="json_output", help="조사 결과를 JSON으로 화면 출력")
    # [프로젝트 추가] 준비·계산·쓰기 명령을 구분해 노트북처럼 작은 단계로 진행합니다.
    commands.add_parser("full-preview", help="전체 저장 행 미리보기 (읽기 전용, 임베딩 없음)")
    commands.add_parser("full-embed", help="전체 새 청크 임베딩 (메모리만, DB 저장 없음)")
    # [프로젝트 추가] 전체 저장 결과의 run_id를 지정해 질문만 계산하고 DB를 읽습니다.
    full_search = commands.add_parser("db-full-search", help="저장 완료된 전체 PDF 검색 (읽기 전용)")
    full_search.add_argument("--run-id", required=True, help="전체 저장 결과에 표시된 작업 번호")
    full_search.add_argument("--method", choices=("purpose", "semantic", "purpose_specific"), default="purpose",
                             help="기존 글자·목적 결합 검색(기본) 또는 pgvector 의미 검색")
    full_search.add_argument("--question", action="append", required=True, help="질문. 반복 입력 가능")
    full_search.add_argument("--top-k", type=int, default=3, choices=range(1, 11), help="근거 묶음 수 (최대 10)")
    full_search.add_argument("--full-text", action="store_true", help="연결 원문 전체 표시")
    full_search.add_argument("--json", action="store_true", dest="json_output", help="JSON 화면 출력")
    # [프로젝트 추가] M5 첫 단계: 검색 후보와 설명서 발췌 답변을 별도 명령으로 구분합니다.
    answer = commands.add_parser("answer", help="확인한 PDF 내용·출처·그림을 발췌 (LLM 없음, 읽기 전용)")
    answer.add_argument("--run-id", required=True, help="전체 저장 작업 번호")
    answer.add_argument("--method", choices=("purpose", "purpose_specific"), default="purpose_specific",
                        help="M7 구체 표현 검색(기본) 또는 변경 전 검색")
    answer.add_argument("--question", action="append", required=True, help="질문. 반복 입력 가능")
    answer.add_argument("--top-k", type=int, default=3, choices=range(1, 11), help="검색 후보 수 (기본 3)")
    answer.add_argument("--json", action="store_true", dest="json_output", help="발췌·출처·검토 상태를 JSON으로 표시")
    # [프로젝트 적용] 같은 PDF 검색을 사용하되 생성 실행은 별도 옵션으로 구별합니다.
    # 기본 명령은 근거·준비 상태를, --json은 프롬프트도 보여줍니다. --run-generation은 API 호출입니다.
    llm_answer = commands.add_parser("answer-llm", help="LangChain·OpenAI 답변 준비 또는 명시적 생성 실행")
    llm_answer.add_argument("--run-id", required=True, help="전체 저장 작업 번호")
    llm_answer.add_argument("--question", required=True, help="답변할 질문 한 개")
    llm_answer.add_argument("--top-k", type=int, default=5, choices=range(1, 11), help="항목마다 검색할 후보 수 (기본 5)")
    llm_answer.add_argument("--run-generation", action="store_true", help="준비한 근거로 OpenAI API를 실제 호출")
    llm_answer.add_argument("--json", action="store_true", dest="json_output", help="프롬프트 미리보기 또는 답변을 JSON으로 표시")
    full_save = commands.add_parser("full-save", help="승인 식별값의 전체 자료 임베딩 후 개인 DB에 저장")
    full_save.add_argument("--confirm-save", action="store_true", help="검토한 전체 DB 저장 실행 승인")
    full_save.add_argument("--manifest-sha256", required=True, help="full-preview에서 확인한 입력 식별값 64자리")
    args = parser.parse_args(argv)
    if args.command == "db-evaluate":
        try:
            from car_search_rag.zzong_santafe_lag.db_evaluation_service import DbRetrievalEvaluationService
            evaluator = DbRetrievalEvaluationService(args.run_id, method=args.method)
            cases = evaluator.prepare_cases()
            if not args.run_evaluation:
                if args.json_output:
                    print(json.dumps({"phase": "prepared", "question_count": len(cases),
                        "dataset_sha256": evaluator.dataset_sha256, "cases": cases}, ensure_ascii=False, indent=2))
                else:
                    print(f"평가 질문 {len(cases)}개 준비. 아직 검색·채점하지 않았습니다.")
                    for case in cases:
                        print(f"{case['case_id']}: {case['question']}")
                        for source in case["expected_sources"]:
                            print(f"  기대 출처: PDF {source['pdf_pages']} | {source['title']}")
                    print("목록을 확인한 뒤 --run-evaluation을 붙이면 실제 평가합니다.")
                return 0
            result = evaluator.evaluate_all(top_k=5, progress=None if args.json_output else report)
            if args.json_output:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"\n{result['question_count']}문항 | 검색 방식: {result['search_method']}")
                print(f"Hit@5: {result['metrics']['Hit@5']:.3f} | MRR@5: {result['metrics']['MRR@5']:.3f}")
                print("주의: 기존 질문의 근거 묶음 검색 평가이며 답변·그림 이해의 정확도는 아닙니다.")
            return 0
        except (ValueError, FileNotFoundError) as error:
            print(f"DB 검색 평가를 멈췄습니다: {error}", file=sys.stderr)
        except Exception as error:
            print(f"DB 검색 평가를 멈췄습니다. 오류 종류: {type(error).__name__}", file=sys.stderr)
            print("개인 DB 연결·저장 작업·로컬 모델을 확인하세요. 비밀번호는 출력하지 않습니다.", file=sys.stderr)
        return 1
    if args.command == "answer-llm":
        try:
            from car_search_rag.zzong_santafe_lag.llm_answer_service import LlmManualAnswerService
            llm_service = LlmManualAnswerService(args.run_id)
            evidence = llm_service.prepare_evidence(args.question, top_k=args.top_k,
                                                   progress=None if args.json_output else report)
            if args.run_generation:
                result = llm_service.generate(evidence)
                if args.json_output:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                else:
                    print_answer(result)
                    print("생성 모델:", result["generation_model"], "| API 호출 시도:", result["llm_called"])
            else:
                preview = llm_service.preview(evidence)
                if args.json_output:
                    print(json.dumps({"settings": llm_service.settings(), "preview": preview,
                                      "evidence": evidence}, ensure_ascii=False, indent=2))
                else:
                    print_answer(evidence)
                    print("\n생성 준비 상태:", preview["ready_for_generation"])
                    print("입력 글자 수:", preview["prompt_characters"])
                    print(preview["reason"] or "근거를 확인한 뒤 --run-generation으로 답변 생성을 실행할 수 있습니다.")
                    print("현재 명령은 OpenAI를 호출하지 않았습니다.")
            return 0
        except Exception as error:
            print(f"LLM 답변 단계를 멈췄습니다. 오류 종류: {type(error).__name__}", file=sys.stderr)
            print("개인 DB·로컬 모델·생성 설정을 확인하세요. 인증 정보는 출력하지 않습니다.", file=sys.stderr)
        return 1
    if args.command == "answer":
        try:
            from car_search_rag.zzong_santafe_lag.answer_service import ManualAnswerService
            answer_service = ManualAnswerService(args.run_id, method=args.method)
            results = []
            for question in args.question:
                result = answer_service.answer(question, top_k=args.top_k,
                                               progress=None if args.json_output else report)
                results.append(result)
                if not args.json_output:
                    print_answer(result)
            if args.json_output:
                print(json.dumps(results, ensure_ascii=False, indent=2))
            return 0
        except (ValueError, FileNotFoundError) as error:
            print(f"발췌 답변을 멈췄습니다: {error}", file=sys.stderr)
        except Exception as error:
            print(f"발췌 답변을 멈췄습니다. 오류 종류: {type(error).__name__}", file=sys.stderr)
            print("개인 DB 연결·로컬 모델을 확인하세요. 비밀번호는 출력하지 않습니다.", file=sys.stderr)
        return 1
    if args.command in {"full-preview", "full-embed", "full-save"}:
        # 저장 승인 옵션은 PDF·모델을 읽기 전에 확인합니다.
        if args.command == "full-save" and (not args.confirm_save or not re.fullmatch(r"[0-9a-f]{64}", args.manifest_sha256)):
            parser.error("전체 저장은 --confirm-save와 검토한 --manifest-sha256 64자리가 필요합니다.")
        try:
            from car_search_rag.zzong_santafe_lag.full_store_service import FullManualStoreService
            full_service = FullManualStoreService().prepare(progress=report)
            info = full_service.summary()
            if args.command == "full-save" and info["input_manifest_sha256"] != args.manifest_sha256:
                raise ValueError("전체 미리보기와 승인한 식별값이 다릅니다. 임베딩·저장을 실행하지 않았습니다.")
            if args.command != "full-preview":
                full_service.embed(progress=report)
                info = full_service.summary()
                info["embedding_report"] = full_service.preview.embedding_report
            if args.command == "full-save":
                info["save_result"] = full_service.save(approved_manifest=args.manifest_sha256, progress=report)
                info["db_written"] = True
            print(json.dumps(info, ensure_ascii=False, indent=2))
            return 0
        except (ValueError, FileNotFoundError) as error:
            print(f"전체 저장 단계를 멈췄습니다: {error}", file=sys.stderr)
        except Exception as error:
            print(f"전체 저장 단계를 멈췄습니다. 오류 종류: {type(error).__name__}", file=sys.stderr)
            print("개인 DB 연결·PDF·로컬 모델을 확인하세요. DB 확정 후 조회 실패라면 저장 상태를 먼저 확인하세요.", file=sys.stderr)
        return 1
    if args.command == "storage-plan":
        try:
            from car_search_rag.zzong_santafe_lag.storage_plan import build_storage_plan, print_storage_plan
            plan = build_storage_plan(progress=None if args.json_output else report)
            if args.json_output:
                print(json.dumps(plan, ensure_ascii=False, indent=2))
            else:
                print_storage_plan(plan)
            return 0
        except (ValueError, FileNotFoundError) as error:
            print(f"저장 범위 조사를 멈췄습니다: {error}", file=sys.stderr)
        except Exception as error:
            print(f"저장 범위 조사를 멈췄습니다. 오류 종류: {type(error).__name__}", file=sys.stderr)
            print("개인 DB 연결·PDF·로컬 토크나이저를 확인하세요. 비밀번호는 출력하지 않습니다.", file=sys.stderr)
        return 1
    if args.command == "search" and args.top_k < 1:
        parser.error("--top-k는 1 이상이어야 합니다.")
    if args.command in {"db-search", "db-full-search"}:
        # [프로젝트 적용] 같은 실행의 질문들은 로컬 모델 한 번 준비 후 재사용합니다.
        # DB 비밀번호가 오류 내용에 섞이지 않도록 예상하지 못한 오류는 종류만 표시합니다.
        try:
            from car_search_rag.zzong_santafe_lag.db_search_service import DbSampleSearchService, DbFullSearchService
            db_service = (DbFullSearchService(args.run_id, method=args.method) if args.command == "db-full-search"
                          else DbSampleSearchService())
            results = []
            for question in args.question:
                result = db_service.search(question, top_k=args.top_k,
                                           progress=None if args.json_output else report)
                results.append(result)
                if not args.json_output:
                    print_db_result(result, args.full_text)
            if args.json_output:
                print(json.dumps(results, ensure_ascii=False, indent=2))
            return 0
        except (ValueError, FileNotFoundError) as error:
            print(f"DB 검색을 멈췄습니다: {error}", file=sys.stderr)
        except Exception as error:
            print(f"DB 검색을 멈췄습니다. 오류 종류: {type(error).__name__}", file=sys.stderr)
            print("개인 DB 연결·로컬 모델 캐시를 확인하세요. 비밀번호는 출력하지 않습니다.", file=sys.stderr)
        return 1
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
