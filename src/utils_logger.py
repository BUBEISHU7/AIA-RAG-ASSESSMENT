import logging
import sys

def get_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        # 格式化输出：时间 - 名字 - 级别 - 线程信息/追踪ID - 消息
        formatter = logging.Formatter(
            '[%(asctime)s] [%(name)s] [%(levelname)s] [TraceID: %(tags)s] %(message)s' if hasattr(logging, 'tags') 
            else '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s'
        )
        
        # 输出到控制台
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    return logger