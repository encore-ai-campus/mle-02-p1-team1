"""팀 DB 선택과 배포 임베딩 버전의 고정 여부를 확인합니다."""
import unittest
from unittest.mock import patch
from uuid import UUID
from car_search_rag.zzong_santafe_lag.database import PersonalDatabaseManager


class ConnectionTests(unittest.TestCase):
    @patch('car_search_rag.zzong_santafe_lag.database.dotenv_values', return_value={'DB_URL': 'root-team', 'ZZONG_DB_URL': 'old'})
    def test_team_environment_wins(self, _):
        with patch.dict('os.environ', {'DB_URL': 'cloud-team', 'ZZONG_DB_URL': 'old'}, clear=True):
            self.assertEqual(PersonalDatabaseManager()._dsn, 'cloud-team')
            self.assertEqual(PersonalDatabaseManager('explicit')._dsn, 'explicit')

    @patch('car_search_rag.zzong_santafe_lag.database.dotenv_values', return_value={'ZZONG_DB_URL': 'old'})
    def test_no_fallback_to_old_database(self, _):
        with patch.dict('os.environ', {'ZZONG_DB_URL': 'old'}, clear=True):
            self.assertIsNone(PersonalDatabaseManager()._dsn)

    def test_shared_embedding_selection(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from car_search_rag.zzong_santafe_lag.openai_search_service import active_embedding_run
        with TemporaryDirectory() as folder, patch.dict('os.environ', {}, clear=True), patch('car_search_rag.zzong_santafe_lag.openai_search_service.OUTPUT_FOLDER', Path(folder)):
            self.assertEqual(active_embedding_run(), UUID('ca3e71ef-8d77-4cdb-b4d2-9d48753dbb4e'))

if __name__ == '__main__':
    unittest.main()
