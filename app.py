import os
import time
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from dotenv import load_dotenv

from src.rag_engine import RAGPipeline
from src.utils_logger import get_logger

load_dotenv()
logger = get_logger("FastAPI_App")

app = FastAPI(
    title="AIA GO Shanghai AI RAG Service",
    description="支持多轮对话、带引用、优雅拒答的合规问答服务",
    version="1.0.0"
)

rag_pipeline = RAGPipeline()

# --- 极简鲁棒的请求与响应数据结构 ---

class ChatQueryRequest(BaseModel):
    query: str = Field(..., example="Does it apply to Friday?")
    # 改用通用的 Dict 列表，彻底杜绝 422 校验报错
    chat_history: List[Dict[str, Any]] = Field(default=[])

class SourceCitation(BaseModel):
    id: int
    file_name: str

class ChatQueryResponse(BaseModel):
    answer: str
    sources: List[SourceCitation]
    latency_seconds: float
    trace_id: str

@app.on_event("startup")
async def startup_event():
    logger.info("=== 正在自动加载 AIA 上海默认合规数据 ===")
    default_text = (
        "AIA GO Shanghai Employee Handbook 2026.\n"
        "The standard working hours are from 9:00 AM to 6:00 PM, Monday to Friday.\n"
        "All PII data like customer phone numbers must be encrypted using AES-256."
    )
    rag_pipeline.build_knowledge_base(default_text, file_name="AIA_Handbook_2026.txt")
    logger.info("=== 默认内部知识库加载就绪 ===")

@app.post("/api/v1/chat", response_model=ChatQueryResponse, tags=["RAG QA"])
async def chat_query(payload: ChatQueryRequest):
    start_time = time.time()
    trace_id = str(uuid.uuid4())
    
    logger.info(f"[TraceID: {trace_id}] 收到提问: '{payload.query}', 历史轮数: {len(payload.chat_history)}")
    
    try:
        # 执行带有异常隔离与默认快速返回机制的 RAG 计算
        result = rag_pipeline.query(payload.query, chat_history=payload.chat_history)
        
        latency = round(time.time() - start_time, 3)
        logger.info(f"[TraceID: {trace_id}] 处理完成，耗时: {latency}s")
        
        return ChatQueryResponse(
            answer=result["answer"],
            sources=result["sources"],
            latency_seconds=latency,
            trace_id=trace_id
        )
        
    except Exception as e:
        logger.error(f"[TraceID: {trace_id}] 运行时异常捕获: {str(e)}")
        # 即使底层报错，也必须在 10s 内优雅向客户端返回错误，绝不挂起
        return ChatQueryResponse(
            answer="抱歉，系统在处理您的请求时遭遇超时或配置限制，请稍后再试或联系系统管理员。",
            sources=[],
            latency_seconds=round(time.time() - start_time, 3),
            trace_id=trace_id
        )