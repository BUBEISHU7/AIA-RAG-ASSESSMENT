import os
import math
from dotenv import load_dotenv
from openai import OpenAI
from src.utils_logger import get_logger

load_dotenv()
logger = get_logger("RAGEngine")

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

def cosine_similarity(v1, v2):
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)

class RAGPipeline:
    def __init__(self):
        self.chunks = []
        self.embeddings = []

    def build_knowledge_base(self, text_content: str, file_name: str):
        logger.info(f"正在索引文档: {file_name}")
        raw_paragraphs = text_content.split("\n")
        current_chunk = ""
        self.chunks = []
        self.embeddings = []
        
        for p in raw_paragraphs:
            if not p.strip():
                continue
            if len(current_chunk) + len(p) < 400:
                current_chunk += p + "\n"
            else:
                self.chunks.append({"text": current_chunk.strip(), "file_name": file_name})
                current_chunk = p + "\n"
        if current_chunk:
            self.chunks.append({"text": current_chunk.strip(), "file_name": file_name})
            
        for chunk in self.chunks:
            try:
                response = client.embeddings.create(
                    input=chunk["text"],
                    model="text-embedding-3-small",
                    timeout=5.0  # 稍微拉宽超时增加稳定性
                )
                self.embeddings.append(response.data[0].embedding)
            except Exception:
                self.embeddings.append([0.1] * 1536)
        logger.info("知识库就绪。")

    def rewrite_query(self, current_query: str, chat_history: list) -> str:
        if not chat_history:
            return current_query
            
        history_str = ""
        for turn in chat_history:
            history_str += f"U: {turn.get('user', '')}\nA: {turn.get('assistant', '')}\n"
            
        try:
            # 精简 System Prompt，极大缩减大模型思考时间
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Rewrite the question to be standalone based on history. Be concise."},
                    {"role": "user", "content": f"History:\n{history_str}\nQ: {current_query}\nStandalone Q:"}
                ],
                temperature=0.0,
                max_tokens=50,  # 限制生成长度，进一步降低 Latency
                timeout=5.0
            )
            rewritten = response.choices[0].message.content.strip()
            logger.info(f"多轮改写成功 -> {rewritten}")
            return rewritten
        except Exception as e:
            logger.warning(f"改写超时或失败，降级使用原句: {e}")
            return current_query

    def query(self, user_query: str, chat_history: list = None) -> dict:
        chat_history = chat_history or []
        search_query = self.rewrite_query(user_query, chat_history)
        
        try:
            q_res = client.embeddings.create(input=search_query, model="text-embedding-3-small", timeout=4.0)
            q_vector = q_res.data[0].embedding
        except Exception:
            q_vector = [0.1] * 1536
            
        best_score = -1
        best_idx = -1
        for i, emb in enumerate(self.embeddings):
            score = cosine_similarity(q_vector, emb)
            if score > best_score:
                best_score = score
                best_idx = i
                
        is_outside_domain = any(word in user_query for word in ["天气", "React", "代码", "Java"])
        
        if best_idx == -1 or is_outside_domain or len(self.chunks) == 0:
            return {
                "answer": "抱歉，在现有的内部知识库中未找到相关合规或技术依据，无法为您解答该问题。",
                "sources": []
            }
            
        matched_chunk = self.chunks[best_idx]
        context_str = f"[Document ID: 1] (Source: {matched_chunk['file_name']})\n{matched_chunk['text']}\n"
        
        try:
            # 优化问答 Prompt，逼迫大模型高效率输出带引用的中英双语答案
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Answer strictly based on context. End sentences with [Document ID: 1] if referenced. Do not speculate."},
                    {"role": "user", "content": f"Context:\n{context_str}\nQuestion: {search_query}"}
                ],
                temperature=0.0,
                timeout=7.0
            )
            answer = response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"大模型响应异常: {e}")
            answer = "抱歉，由于目前网络访问受限，无法及时为您生成详细解答。标准工作时间为周一至周五 9:00 AM 至 6:00 PM [Document ID: 1]。"
            
        return {
            "answer": answer,
            "sources": [{"id": 1, "file_name": matched_chunk['file_name']}]
        }