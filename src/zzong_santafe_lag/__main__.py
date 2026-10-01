"""python -m으로 실행할 때도 같은 개인 실행 파일을 사용합니다."""

# [프로젝트 추가] -m 실행도 manual.py와 같은 시작 함수를 사용합니다.

from .manual import main

if __name__ == "__main__":
    raise SystemExit(main())
