"""공통 UI와 차종별 에이전트 사이의 연결 목록입니다."""
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
import sys

# 저장소 루트의 팀원 진입 파일도 화면 없이 import할 수 있도록 합니다.
ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from typing import Protocol


class VehicleBackend(Protocol):
    """팀원의 차종별 모듈이 제공해야 할 공통 함수입니다."""
    def start_session(self, is_test: bool = False) -> str: ...
    def end_session(self, session_id: str) -> None: ...
    def chat(self, session_id: str, question: str, request_id: str | None = None, on_event=None) -> dict: ...
    def is_session_active(self, session_id: str) -> bool: ...
    def get_related_images(self, packet: dict) -> list[dict]: ...


@dataclass(frozen=True)
class Vehicle:
    label: str
    module: str | None


# 다른 차종 이름과 모듈은 팀에서 확정한 후 여기에 등록합니다.
VEHICLES = {
    'ioniq5': Vehicle('현대 아이오닉 5', 'car_search_rag.anna_rag.chatbot.ioniq5_backend'),
    'santafe': Vehicle('산타페', 'car_search_rag.zzong_santafe_lag.app'),
    'sonata': Vehicle('쏘나타', 'app_kbj'),
    'casper': Vehicle('캐스퍼', None),
}


def load_backend(vehicle_id: str) -> VehicleBackend:
    vehicle = VEHICLES[vehicle_id]
    if vehicle.module is None:
        raise ValueError('아직 연결되지 않은 차종입니다.')
    return import_module(vehicle.module).create_backend()
