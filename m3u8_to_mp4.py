import subprocess
from pathlib import Path

import m3u8
import aiohttp
from tqdm.asyncio import tqdm_asyncio
import base64
import hmac
import hashlib
from email.utils import formatdate
from urllib.parse import urlparse, unquote

def get_oss_headers(url, oss_auth):
    """根据阿里云 OSS V1 计算当前请求的签名并返回 Headers"""
    if not oss_auth:
        return {
            "user-agent": "Mozilla/5.0",
            "Referer": "https://www.aiwenyun.cn/"
        }
    
    ak_id = oss_auth['id']
    ak_secret = oss_auth['secret']
    sts_token = oss_auth['token']
    
    parsed = urlparse(url)
    bucket = "file-plaso" # 爱问云目前的 bucket
    object_key = unquote(parsed.path.lstrip('/'))
    
    date_str = formatdate(timeval=None, localtime=False, usegmt=True)
    oss_headers = f"x-oss-security-token:{sts_token}\n"
    resource = f"/{bucket}/{object_key}"
    
    string_to_sign = f"GET\n\n\n{date_str}\n{oss_headers}{resource}"
    h = hmac.new(ak_secret.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1)
    signature = base64.b64encode(h.digest()).decode('utf-8')
    
    return {
        "Date": date_str,
        "x-oss-security-token": sts_token,
        "Authorization": f"OSS {ak_id}:{signature}",
        "user-agent": "Mozilla/5.0",
        "Referer": "https://www.aiwenyun.cn/"
    }


async def load_m3u8(s, m3u8_url, oss_auth):
    headers = get_oss_headers(m3u8_url, oss_auth)
    async with s.get(m3u8_url, headers=headers) as r:
        text = await r.text()
        if r.status != 200:
            raise Exception(f"Failed to load M3U8: HTTP {r.status}\n{text[:500]}")
        if "#EXTM3U" not in text:
            raise Exception(f"Invalid M3U8 format received (HTTP 200), possibly intercepted by WAF:\n{text[:500]}")
        return m3u8.loads(text, uri=m3u8_url)


async def fetch(s, index, segment, oss_auth, ts_dir="ts"):
    ts_name = f'{index}.ts'
    fetch_url = segment.absolute_uri
    headers = get_oss_headers(fetch_url, oss_auth)

    async with s.get(fetch_url, headers=headers) as r:
        if r.status != 200:
            raise Exception(f"Failed to fetch TS {ts_name} from {fetch_url}: HTTP {r.status}")
        with open(f'{ts_dir}/{ts_name}', 'wb') as f:
            async for chunk in r.content.iter_chunked(64 * 1024):
                f.write(chunk)


async def download_ts(s, playlist, oss_auth, ts_dir="ts"):
    Path(ts_dir).mkdir(exist_ok=True)
    tasks = (fetch(s, index, segment, oss_auth, ts_dir) for index, segment in enumerate(playlist.segments))
    await tqdm_asyncio.gather(*tasks)


def new_m3u8(playlist, ts_dir="ts", out_name="new.m3u8"):
    for index, segment in enumerate(playlist.segments):
        segment.uri = f"{ts_dir}/{index}.ts"
    playlist.dump(out_name)


def m3u82mp4(m3u8_path='new.m3u8', capture_output=False, mp4_path='output.mp4'):
    try:
        subprocess.run(['./ffmpeg.exe',
                        '-y',
                        '-allowed_extensions', 'ALL',
                        '-i', m3u8_path,
                        '-c', 'copy',
                        mp4_path
                        ], check=True, capture_output=capture_output)
    except subprocess.CalledProcessError as e:
        if e.stderr:
            print(f"FFmpeg Error: {e.stderr.decode('utf-8', errors='ignore')}")
        raise


async def mainfunc(m3u8_urls, mp4path, oss_auth=None):
    import uuid
    import time
    uid = uuid.uuid4().hex[:8]
    
    if isinstance(m3u8_urls, str):
        m3u8_urls = [m3u8_urls]
        
    connector = aiohttp.TCPConnector(limit=8)
    part_files = []
    ts_dirs = []
    m3u8_files = []
    
    async with aiohttp.ClientSession(connector=connector) as s:
        for idx, m3u8_url in enumerate(m3u8_urls):
            print(f'正在读取切片 [{idx+1}/{len(m3u8_urls)}]：{m3u8_url}')
            playlist = await load_m3u8(s, m3u8_url, oss_auth)
            
            ts_dir = f'ts_{uid}_{idx}'
            await download_ts(s, playlist, oss_auth, ts_dir)
            
            out_m3u8 = f'new_{uid}_{idx}.m3u8'
            new_m3u8(playlist, ts_dir, out_m3u8)
            
            out_mp4 = f'part_{uid}_{idx}.mp4'
            m3u82mp4(out_m3u8, capture_output=False, mp4_path=out_mp4)
            
            part_files.append(out_mp4)
            ts_dirs.append(ts_dir)
            m3u8_files.append(out_m3u8)
            
    # 等待一秒以彻底释放文件锁（杀毒软件扫描等）
    time.sleep(1)
    
    concat_list = f'concat_list_{uid}.txt'
    if len(part_files) == 1:
        import shutil
        if Path(mp4path).exists():
            try:
                Path(mp4path).unlink()
            except Exception:
                pass
        
        # 带有重试逻辑的移动文件，防止偶发的 WinError 32
        for _ in range(5):
            try:
                shutil.move(part_files[0], mp4path)
                break
            except Exception as e:
                time.sleep(1)
    else:
        print("正在拼接多个视频分段...")
        with open(concat_list, 'w', encoding='utf-8') as f:
            for pf in part_files:
                f.write(f"file '{pf}'\n")
        subprocess.run(['./ffmpeg.exe', '-y', '-f', 'concat', '-safe', '0', '-i', concat_list, '-c', 'copy', mp4path], check=True)
        try:
            Path(concat_list).unlink(missing_ok=True)
        except Exception:
            pass
        
    # 清理所有临时文件
    for pf in part_files:
        try:
            Path(pf).unlink(missing_ok=True)
        except Exception:
            pass
    for td_str in ts_dirs:
        td = Path(td_str)
        if td.exists():
            for ts_file in td.iterdir():
                try:
                    ts_file.unlink(missing_ok=True)
                except Exception:
                    pass
            try:
                td.rmdir()
            except Exception:
                pass
    for mf in m3u8_files:
        try:
            Path(mf).unlink(missing_ok=True)
        except Exception:
            pass