import subprocess
from pathlib import Path

import m3u8
import aiohttp
from tqdm.asyncio import tqdm_asyncio


async def load_m3u8(s, m3u8_url):
    async with s.get(m3u8_url) as r:
        text = await r.text()
        if r.status != 200:
            raise Exception(f"Failed to load M3U8: HTTP {r.status}\n{text[:500]}")
        if "#EXTM3U" not in text:
            raise Exception(f"Invalid M3U8 format received (HTTP 200), possibly intercepted by WAF:\n{text[:500]}")
        return m3u8.loads(text, uri=m3u8_url)


async def fetch(s, index, segment):
    ts_name = f'{index}.ts'
    with open(f'ts/{ts_name}', 'wb') as f:
        async with s.get(segment.absolute_uri) as r:
            if r.status != 200:
                raise Exception(f"Failed to fetch TS {ts_name}: HTTP {r.status}")
            async for chunk in r.content.iter_chunked(64 * 1024):
                f.write(chunk)


async def download_ts(s, playlist):
    Path('ts').mkdir(exist_ok=True)
    tasks = (fetch(s, index, segment) for index, segment in enumerate(playlist.segments))
    await tqdm_asyncio.gather(*tasks)


def new_m3u8(playlist):
    for index, segment in enumerate(playlist.segments):
        segment.uri = f"ts/{index}.ts"
    playlist.dump('new.m3u8')


def m3u82mp4(capture_output=False, mp4_path='output.mp4'):
    try:
        subprocess.run(['./ffmpeg.exe',
                        '-allowed_extensions', 'ALL',
                        '-i', 'new.m3u8',
                        '-c', 'copy',
                        mp4_path
                        ], check=True, capture_output=capture_output)
    except subprocess.CalledProcessError as e:
        if e.stderr:
            print(f"FFmpeg Error: {e.stderr.decode('utf-8', errors='ignore')}")
        raise


def clean_up():
    for ts_file in Path('ts').iterdir():
        ts_file.unlink()
    Path('ts').rmdir()
    Path('new.m3u8').unlink()


async def mainfunc(m3u8_url, mp4path, headers=None):
    connector = aiohttp.TCPConnector(limit=8)
    async with aiohttp.ClientSession(connector=connector, headers=headers) as s:
        print(f'正在读取m3u8链接：{m3u8_url}')
        playlist = await load_m3u8(s, m3u8_url)
        # logging.info('正在下载ts文件')
        await download_ts(s, playlist)
    # logging.info('正在生成新的m3u8文件')
    new_m3u8(playlist)
    # logging.info('正在转换新的m3u8文件为mp4文件')
    m3u82mp4(mp4_path=mp4path)
    # logging.info('正在清理临时文件')
    clean_up()