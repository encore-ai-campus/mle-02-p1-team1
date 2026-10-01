import logging
import re
from pathlib import Path

from langchain_openai import OpenAIEmbeddings
from pgvector.utils import Vector
from pypdf import PdfReader

from car_search_rag.common.sql_session import SqlSession
from car_search_rag.common import document_reader

SYSTEM_USER_ID = "SYSTEM"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
machine_logger = logging.getLogger("car_search_rag.car_manual")

#=========================================================
# 검색 서비스
#=========================================================
class CarManualSearchService:

    sql_session : SqlSession
    embedding_model : OpenAIEmbeddings

    def __init__(self,sql_session):
        self.sql_session = sql_session

        self.embedding_model = OpenAIEmbeddings(
            model=EMBEDDING_MODEL
        )
