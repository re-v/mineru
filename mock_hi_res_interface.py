"""
模拟及高级解析接口调用入口
"""

import asyncio
import os
import json
import aiohttp
from aiohttp import ClientTimeout
from tenacity import retry, wait_fixed, stop_after_attempt
from tqdm import tqdm

SERVER = "http://192.168.110.125:8000"

# @retry(wait=wait_fixed(2), stop=stop_after_attempt(5))  # 每次等待2秒，重试5次
async def single_process_pdf(single_file_path):
    url = SERVER + "/pre_process_pdf"
    payload = {
        "file_list": [{
            'content': '',
            'content_path': '/test',
            'file_id': 'bb865ee190cf48b69ed504cda4b75cad',
            'target_path': single_file_path
        }],
        "token": 'eyJhbGciOiJIUzUxMiJ9.eyJsb2dpbl91c2VyX2tleSI6ImVjY2YyN2IzZTdiYTRmYmRiZDlhMmM0NGFhZjNhZWQyIn0.tL2WIIBrYWnKd-R01-v3OrJoMl9LAyZV3tS4a5YRsEQYhZoR0gFR17ZwzrlKA6aLEGkTvZj7P9_G28wYmNxYmg',
        "strategy": "fast",
        "callback_url": "http://localhost:8000/callback"
    }
    filename = os.path.basename(single_file_path)

    try:
        # async with aiohttp.ClientSession(timeout=ClientTimeout(total=1)) as session:
        async with aiohttp.ClientSession() as session:
            with open(single_file_path, 'rb') as file:
                form_data = aiohttp.FormData()
                form_data.add_field('file', file, filename=filename, content_type='application/pdf')
                form_data.add_field('file_list', json.dumps(payload))
                try:
                    async with session.post(url, data=form_data,timeout=aiohttp.ClientTimeout(total=2)) as response:
                        if response.status == 200:
                            print("请求成功")
                        else:
                            print(f"请求失败，状态码: {response.status}")
                except asyncio.TimeoutError:
                    print("传输参数:", payload)
                    print("请求超时")
    except Exception as e:
        import traceback
        msg = traceback.format_exc()
        print("msg: ", msg)
        print(f"请求过程中出错: {str(e)}")
    print(f"处理完成: {single_file_path}")


async def multi_process_pdf(file_list):
    count = 0
    tasks = []
    for file in tqdm(os.listdir(file_list), desc="file_list"):
        if file.endswith('.pdf'):
            count += 1
            task = asyncio.create_task(single_process_pdf(os.path.join(file_list, file)))
            # task.add_done_callback(lambda t: print(f"Task {t} done"))
            tasks.append(task)
            if count >=10:
                break

    await asyncio.gather(*tasks)
    print(f"总共有{count}个pdf文件")


if __name__ == '__main__':
    asyncio.run(single_process_pdf("/Users/wuguanlin/wgl/langchain-chatchat/first_page.pdf"))
    # multi_file_path = "/Users/wuguanlin/Downloads"
    # # multi_process_pdf(multi_file_path)
    # asyncio.run(multi_process_pdf(multi_file_path))
