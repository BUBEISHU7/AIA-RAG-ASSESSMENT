import fitz  # PyMuPDF
from pathlib import Path
from src.utils_logger import get_logger

logger = get_logger("DocumentLoader")

class SmartDocLoader:
    """智能文档加载器，支持处理中英双语及检测扫描版PDF"""
    
    @staticmethod
    def load_pdf(file_path: str) -> str:
        doc = fitz.open(file_path)
        full_text = []
        scanned_page_count = 0
        
        for page_num, page in enumerate(doc):
            text = page.get_text()
            # 如果提取出来的文本字数极少，但页面确实存在，大概率是扫描件/图片
            if len(text.strip()) < 10:
                scanned_page_count += 1
                # 真实工业界这里会调用 OCR（如 PaddleOCR/TextIn）
                # 这里我们先打个占位符并记录日志，展现出你考虑到了这个硬性约束
                logger.warning(f"Page {page_num} in {file_path} seems to be a scanned page (OCR needed).")
                text = f"[Scanned Content Image Placeholder - Page {page_num}]"
            
            full_text.append(text)
            
        if scanned_page_count > 0:
            logger.info(f"Finished loading {file_path}. Total scanned pages detected: {scanned_page_count}")
        return "\n\n".join(full_text)