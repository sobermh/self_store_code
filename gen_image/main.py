import os
import random
import httpx
import base64
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Optional

from volcenginesdkarkruntime import AsyncArk 


# --- 1. 初始化与配置 ---
logger = logging.getLogger(Path(__file__).name)

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

setup_logging()
load_dotenv()

# 并发限制与客户端初始化
sem = asyncio.Semaphore(5)
client = AsyncArk(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.environ.get("ARK_API_KEY"),
)

# --- 2. 工具层 (Utilities) ---
def image_localpath_to_base64(filename: str) -> Optional[str]:
    """【解耦】仅负责：本地文件 -> Base64"""
    target_path = Path(__file__).resolve().parent / "input" / filename
    try:
        if not target_path.exists():
            logger.error(f"找不到输入文件: {target_path}")
            return None
        encoded = base64.b64encode(target_path.read_bytes()).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception as e:
        logger.error(f"Base64转换失败: {e}")
        return None

async def image_url_to_localpath(url: str, subdir: Optional[str] = None) -> Optional[Path]:
    """【解耦】仅负责: 远程URL -> 本地文件存储"""
    output_dir = Path(__file__).resolve().parent / "output" if subdir is None else Path(__file__).resolve().parent / "output" / subdir

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        target_path = output_dir / f"{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.png"
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(url, timeout=60)
            resp.raise_for_status()
            target_path.write_bytes(resp.content)
            return target_path
    except Exception as e:
        logger.error(f"网络下载失败: {e}")
        return None

# --- 3. 原子功能层 (API Core) ---
async def image_generate_api(prompt:str, ref_image: Optional[str] = None) -> Optional[str]:
    """【解耦】仅负责：输入数据 -> 调用接口 -> 返回URL"""
    async with sem:  # 在此处控制并发
        try:
            response = await client.images.generate(
                model=os.environ.get("ARK_GEN_IMAGE_MODEL"), 
                prompt=prompt,
                image=ref_image,
                sequential_image_generation="disabled",
                response_format="url",
                size="2K",
                stream=False,
                watermark=True
            ) 
            return response.data[0].url
        except Exception as e:
            logger.error(f"Ark 图片生成 API 调用异常: {e}")
            return None

# --- 4. 业务流层 (核心解耦点) ---
async def run_single_task(task_config: Dict[str, str]):
    """处理单个任务：提取参数 -> 转换 -> 生成 -> 保存"""
    prompt = task_config.get("prompt")
    ref_file = task_config.get("ref_file")
    batch_subdir = task_config.get("batch_subdir")
    
    # 1. 预处理
    b64_data = image_localpath_to_base64(ref_file) if ref_file else None
    
    # 2. 执行生成
    logger.info(f"🚀 启动任务: {prompt}")
    url = await image_generate_api(prompt, b64_data)
    
    # 3. 后处理
    if url:
        await image_url_to_localpath(url, subdir=batch_subdir)

# --- 5. 执行入口 ---
async def main():
    ref_name_list = ["刘亦菲","肖战","赵露思","王嘉尔","杨幂","杨紫","蔡徐坤","迪丽热巴","赵丽颖","权志龙"]
    ref_image_name_list = [name for name in os.listdir("input") if os.path.isfile(os.path.join("input", name))]
    # ref_image_name_list = ["lv nfc 卡其色.png"]
    run_batch_name = datetime.now().strftime("%Y%m%d_%H%M%S")
    tasks_to_run = [
        {
            "prompt": f"{name}将参考图中的围巾随意地绕在脖子上，背景在{random.choice(['机场', '高铁站', '广场', '商场', '咖啡厅','公园','街头','艺术展厅','酒店大堂'])},人物{random.choice(['正面', '侧面', '四分之三侧面','微微侧身'])}朝向镜头,围巾中的图案和字母可以不用太清晰,时尚街拍风格浅景深，背景虚化，真实摄影。,比例1:1", 
            "ref_file": img,
            "batch_subdir":img.replace('.', '_')
        }
        for name in ref_name_list
        for img in ref_image_name_list
    ]
    # 并发启动所有任务
    logger.info(f"🔥 开始并发执行 {len(tasks_to_run)} 个任务...")
    await asyncio.gather(*(run_single_task(task) for task in tasks_to_run))
    logger.info("✨ 所有任务处理完毕")

if __name__ == "__main__":
    asyncio.run(main())