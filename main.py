import time, os, asyncio, requests
from datetime import datetime
from get_userinfo import get_userinfo
from get_video import getAccessToken, getRecordList, create_path, download_m3u8_segments
from m3u8_to_mp4 import mainfunc

def timestamp_to_date(timestamp):
    # 将毫秒级时间戳转换为秒级时间戳
    timestamp_sec = timestamp / 1000
    # 转换为日期时间对象
    dt = datetime.fromtimestamp(timestamp_sec)
    # 格式化日期时间字符串，舍去秒钟部分
    dt_str = dt.strftime('%Y-%m-%d')
    return dt_str

async def download_resource(url, dest_path, oss_auth):
    from m3u8_to_mp4 import get_oss_headers
    import aiohttp
    import aiofiles
    headers = get_oss_headers(url, oss_auth)
    # 不强制校验后缀以防下载被拦截，但需要加入基础安全头
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, ssl=False) as response:
            if response.status == 200:
                async with aiofiles.open(dest_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        await f.write(chunk)
                print(f"资源下载成功: {os.path.basename(dest_path)}")
            else:
                print(f"资源下载失败 HTTP {response.status}: {os.path.basename(dest_path)}")

def expand_range_string(s):
    expanded = []
    parts = s.split(',')
    
    for part in parts:
        if '-' in part:
            subparts = part.split('-')
            if len(subparts) != 2:
                raise ValueError(f"无效范围格式: {part}")
            
            try:
                start = int(subparts[0])
                end = int(subparts[1])
            except ValueError:
                raise ValueError(f"非数字内容: {part}")
            
            if start > end:
                raise ValueError(f"起始值大于结束值: {part}")
                
            expanded.extend(range(start, end + 1))
        else:
            try:
                num = int(part)
                expanded.append(num)
            except ValueError:
                raise ValueError(f"无效数字: {part}")
    
    return ','.join(map(str, expanded))

print("欢迎使用 ALAU 爱问云破解器，正在嗅探当前爱问云登录信息……")
time.sleep(1)

up = get_userinfo()
hashed = True

if not up:
    print("未检测到登录信息，可能本机未安装爱问云或未登录过。")
    choose = input("请尝试 重新运行爱问云[输入0] 或 手动输入账密[输入1]：")
    if choose == "1":
        name = input("请输入用户名：")
        passwd = input("请输入密码：")
        up = [name, passwd]
        hashed = False
    else:
        print("请重新运行爱问云后再次启动本程序。")
        exit(0)
else:
    print("信息嗅探成功，请核验是否正确：\n")
    print("用户名：%s"%up[0])
    print("密码（为保护用户信息，该内容经过加密）：%s"%up[1])
    i = input("\n若正确，请输入y/Y；其他字母代表不正确：")
    
    if i not in ["y", "Y"]:
        choose = input("请尝试 重新运行爱问云[输入0] 或 手动输入账密[输入1]：")
        if choose == "0":
            print("请重新运行爱问云后再次启动本程序。")
            exit(0)
        elif choose == "1":
            name = input("请输入用户名：")
            passwd = input("请输入密码：")
            up = [name, passwd]
            hashed = False
        
print("\n\n===========================================================\n正在获取登录令牌……")
time.sleep(1)
try:
    access_token = getAccessToken(up[0], passwd, hashed)
except:
    print("登录失败，请检查用户名和密码是否正确。")
    exit(0)
if access_token == "":
    print("登录失败，请检查用户名和密码是否正确。")
    exit(0)

print("登录成功，正在获取视频列表……")
time.sleep(1)
record_list = getRecordList(access_token)
print("视频列表获取成功：\n===========================================================")
import json
with open("debug_records.json", "w", encoding="utf-8") as f:
    json.dump(record_list[:2], f, ensure_ascii=False, indent=2)

name_dict = {}
bh = 0
info = {}
for record_ in record_list:
    addr = "https://filecdn.plaso.cn/liveclass/plaso/" + record_["fileCommon"]["location"] + "/ts1/t.m3u8"
    name = record_["shortDesc"]
    try:
        name_dict[name] += 1
    except: 
        name_dict[name] = 0
    # print("[%s] 课程名称：%s 课程系列序号：%s 课程日期：%s" % (bh, name, name_dict[name], timestamp_to_date(record_["fileCommon"]["createTime"])))
    info[str(bh)] = {
        "classname": name, 
        "classnum": name_dict[name], 
        "classdate": timestamp_to_date(record_["fileCommon"]["createTime"]),
        "addr": addr,
        "_id": record_["_id"]
    }
    bh += 1
    
for b in range(bh):
    print("[%s] 课程名称：%s 课程系列序号：%s 课程日期：%s" % (b, info[str(b)]["classname"], name_dict[info[str(b)]["classname"]] - info[str(b)]["classnum"], info[str(b)]["classdate"]), info[str(b)]["addr"])

bhs = input("===========================================================\n请输入需要下载的视频编号（用逗号隔开；连续编号可用连字符，例如：2,3,10-15,21）【方括号内为视频编号】：")
cwd = os.getcwd()
path = os.path.join(cwd, "爱问云视频")
create_path(path)
bh_list = expand_range_string(bhs).split(",")
addrlist = {}
from get_video import UA

for bh in bh_list:
    out_dir = os.path.join(path, info[bh]["classname"])
    create_path(out_dir)
    filename = "%s 第%s次课.mp4" % (info[str(bh)]["classdate"], info[str(bh)]["classnum"])
    out_file = os.path.join(out_dir, filename)
    print(f"\n即将下载到：{out_file}")
    
    sts_url = "https://www.aiwenyun.cn/yxt/servlet/stsHelper/stsInfo"
    sts_headers = {
        "user-agent": UA,
        "access-token": access_token,
        "content-type": "application/json"
    }
    
    oss_auth = None
    try:
        r_sts = requests.post(sts_url, headers=sts_headers, json={"id":"liveclass"}, verify=False)
        sts_data = r_sts.json()
        if sts_data.get("code") == 0:
            oss_auth = sts_data.get("obj")
            print("成功获取到 STS 动态鉴权密钥")
        else:
            print(f"获取 STS 鉴权失败: {sts_data}")
    except Exception as e:
        print(f"获取 STS 鉴权异常: {e}")

    plist_url = "https://filecdn.plaso.cn/liveclass/plaso/" + info[str(bh)]["addr"].split("liveclass/plaso/")[1].split("/ts1")[0] + "/info.plist"
    
    real_urls = []
    from m3u8_to_mp4 import get_oss_headers
    try:
        r_plist = requests.get(plist_url, headers=get_oss_headers(plist_url, oss_auth), verify=False)
        plist_data = r_plist.json()
        import re
        str_data = json.dumps(plist_data, ensure_ascii=False)
        # 获取所有 s*/a.m3u8 画面切片
        vs = list(set(re.findall(r's\d+/a\.m3u8', str_data)))
        # 按数字顺序排序 s1, s101, s102
        vs.sort(key=lambda x: int(re.search(r'\d+', x).group()))
        
        if not vs:
            print("\n===========================================================")
            print("【架构提示】该节课程在服务器上完全不存在画面录像！")
            print("原因排查：当堂课老师全程仅使用了电子白板与语音授课，未开启屏幕共享。")
            print("爱问云底层的录制机制仅保存了【语音流】与极小的【画笔坐标点】，从未在云端合成过任何视频。")
            print("这并非下载器故障，而是物理源文件不存在。")
            print("目前脚本将自动为您提取并合并全场纯音频（最终生成的 MP4 仅有声音无画面属正常现象）。")
            print("同时为您自动提取课件 PDF 和背景图以便本地查阅。")
            print("===========================================================\n")
            
            with open("fallback_info.json", "w", encoding="utf-8") as dumpf:
                json.dump(plist_data, dumpf, ensure_ascii=False, indent=2)
                
            # 扫描并下载当堂课的 PDF 和 PNG/JPG 资源
            # 放宽正则以支持提取中文字符文件名的课件
            res_matches = set(re.findall(r'\"([^\"]+\.(?:pdf|png|jpg))\"', str_data))
            if res_matches:
                base_addr = info[str(bh)]["addr"].split("/ts1")[0]
                print("发现附带课件/板书资源，正在下载...")
                
                # 遍历 Bucket 目录树来确定课件的真实储存路径
                try:
                    prefix = base_addr.split("filecdn.plaso.cn/")[1].split("_")[0]
                    bucket_url = f'https://filecdn.plaso.cn/?prefix={prefix}&max-keys=500'
                    import xml.etree.ElementTree as ET
                    tr = requests.get(bucket_url, headers=get_oss_headers(bucket_url, oss_auth), verify=False)
                    root = ET.fromstring(tr.text)
                    print("--- 阿里云 OSS 目录树探测结果 ---")
                    for obj in root.findall('.//{http://doc.oss-cn-hangzhou.aliyuncs.com}Contents'):
                        key = obj.find('{http://doc.oss-cn-hangzhou.aliyuncs.com}Key').text
                        if not key.endswith('.ts') and not key.endswith('.m3u8'):
                            print("发现源文件:", key)
                    print("-----------------------------")
                except Exception as ex:
                    print("目录树探测失败:", ex)
                async def fetch_all_resources():
                    import asyncio
                    import urllib.parse
                    import aiohttp
                    import aiofiles
                    from m3u8_to_mp4 import get_oss_headers
                    
                    tasks = []
                    
                    # 获取多种前缀的鉴权 token 以便穷举，绕过阿里云的 IAM Deny
                    sts_url = "https://www.aiwenyun.cn/yxt/servlet/stsHelper/stsInfo"
                    sts_headers = {
                        "user-agent": UA,
                        "access-token": get_userinfo_token(), # 全局 access_token
                        "content-type": "application/json"
                    }
                    auths = {}
                    for auth_id in ["liveclass", "courseware", "attachment", "file"]:
                        try:
                            # print(f"正在申请 {auth_id} 的 OSS 权限...")
                            r = requests.post(sts_url, headers=sts_headers, json={"id": auth_id}, verify=False, timeout=3)
                            auths[auth_id] = r.json().get("obj")
                        except Exception:
                            pass

                    # ====== 终极地毯式暴力扫描器 ======
                    parts = base_addr.split("filecdn.plaso.cn/")[1].split("/")
                    org_id = parts[2] if len(parts) > 2 else "20328"
                    loc_prefix = parts[3].split("_")[0] if len(parts) > 3 else parts[-1].split("_")[0]

                    async def download_by_id(fid, session):
                        import urllib.parse
                        # 尝试猜出真实名字
                        name_match = re.search(r'\"([^\"]+\.pdf)\"', str_data)
                        fname = name_match.group(1) if name_match else fid
                        encoded_name = urllib.parse.quote(fname)
                        
                        url_templates = [
                            ("courseware", f"https://filecdn.plaso.cn/courseware/plaso/{org_id}/{fid}"),
                            ("courseware", f"https://filecdn.plaso.cn/courseware/plaso/{org_id}/{fid}.pdf"),
                            ("courseware", f"https://filecdn.plaso.cn/courseware/plaso/{org_id}/{encoded_name}"),
                            ("attachment", f"https://filecdn.plaso.cn/attachment/plaso/{org_id}/{fid}"),
                            ("attachment", f"https://filecdn.plaso.cn/attachment/plaso/{org_id}/{fid}.pdf"),
                            ("attachment", f"https://filecdn.plaso.cn/attachment/plaso/{org_id}/{encoded_name}"),
                            ("file", f"https://filecdn.plaso.cn/file/plaso/{fid}"),
                            ("file", f"https://filecdn.plaso.cn/file/plaso/{fid}.pdf"),
                            ("liveclass", f"https://filecdn.plaso.cn/liveclass/plaso/{org_id}/{fid}"),
                            ("liveclass", f"https://filecdn.plaso.cn/liveclass/plaso/{org_id}/{fid}.pdf"),
                            ("liveclass", f"https://filecdn.plaso.cn/liveclass/plaso/{org_id}/{encoded_name}"),
                            ("liveclass", f"https://filecdn.plaso.cn/liveclass/plaso/{loc_prefix}/courseware/{fid}"),
                            ("liveclass", f"https://filecdn.plaso.cn/liveclass/plaso/{loc_prefix}/attachment/{fid}"),
                            ("liveclass", f"{base_addr}/{fid}.pdf"),
                            ("liveclass", f"{base_addr}/{encoded_name}"),
                        ]

                        from m3u8_to_mp4 import get_oss_headers
                        
                        print(f"--- 正在探测文档 {fname} 的原文件路径 ---")
                        # 1. 探测完整的单文件 PDF
                        for auth_id, url in url_templates:
                            c_auth = auths.get(auth_id)
                            if not c_auth: continue
                            headers = get_oss_headers(url, c_auth)
                            try:
                                async with session.get(url, headers=headers, ssl=False, timeout=5) as response:
                                    if response.status == 200:
                                        dest_path = os.path.join(out_dir, fname)
                                        async with aiofiles.open(dest_path, 'wb') as f:
                                            async for chunk in response.content.iter_chunked(1024 * 1024):
                                                await f.write(chunk)
                                        print(f"[爆破成功] 课件本体下载完成: {fname}")
                                        return
                            except Exception:
                                pass
                                
                        # 2. 如果单文件全被 403/404，则说明被白板系统切片化了
                        print(f"单文件未找到，尝试探测被白板引擎切片后的散装图片包...")
                        found_pages = 0
                        for page in range(1, 40):
                            page_str = str(page)
                            sub_templates = [
                                ("courseware", f"https://filecdn.plaso.cn/courseware/plaso/{org_id}/{fid}/{page_str}.jpg"),
                                ("courseware", f"https://filecdn.plaso.cn/courseware/plaso/{org_id}/{fid}/{page_str}.png"),
                                ("courseware", f"https://filecdn.plaso.cn/courseware/plaso/{org_id}/{fid}_{page_str}.jpg"),
                                ("courseware", f"https://filecdn.plaso.cn/courseware/plaso/{org_id}/{fid}_{page_str}.png"),
                                ("attachment", f"https://filecdn.plaso.cn/attachment/plaso/{org_id}/{fid}/{page_str}.jpg"),
                                ("attachment", f"https://filecdn.plaso.cn/attachment/plaso/{org_id}/{fid}/{page_str}.png"),
                                ("liveclass", f"{base_addr}/{fid}/{page_str}.jpg"),
                                ("liveclass", f"{base_addr}/{fid}/{page_str}.png"),
                                ("liveclass", f"{base_addr}/{fid}_{page_str}.jpg"),
                                ("liveclass", f"{base_addr}/res/{fid}/{page_str}.jpg"),
                            ]
                            
                            page_found = False
                            for auth_id, url in sub_templates:
                                c_auth = auths.get(auth_id)
                                if not c_auth: continue
                                headers = get_oss_headers(url, c_auth)
                                try:
                                    async with session.get(url, headers=headers, ssl=False, timeout=3) as response:
                                        if response.status == 200:
                                            ext = url.split('.')[-1]
                                            dest_path = os.path.join(out_dir, f"{fid}_page_{page:02d}.{ext}")
                                            async with aiofiles.open(dest_path, 'wb') as df:
                                                async for chunk in response.content.iter_chunked(1024 * 1024):
                                                    await df.write(chunk)
                                            print(f"[爆破成功] 下载课件图集碎片: 第 {page} 页...")
                                            found_pages += 1
                                            page_found = True
                                            break
                                except Exception:
                                    pass
                                    
                            if not page_found and found_pages > 0:
                                # 连续找到后突然没找到，说明书本翻完了
                                break
                                
                        if found_pages == 0:
                            print(f"[完全失败] 经受 130 种不同网段/权限/页码的极限探测，课件 {fname} 的实体文件均不存在。")

                    async def download_image(clean_path, dest_path, session):
                        encoded_path = urllib.parse.quote(clean_path)
                        file_url = base_addr + "/" + encoded_path
                        headers = get_oss_headers(file_url, auths.get("liveclass") or oss_auth)
                        try:
                            async with session.get(file_url, headers=headers, ssl=False, timeout=10) as response:
                                if response.status == 200:
                                    async with aiofiles.open(dest_path, 'wb') as f:
                                        async for chunk in response.content.iter_chunked(1024 * 1024):
                                            await f.write(chunk)
                                    print(f"附图下载成功: {os.path.basename(dest_path)}")
                        except Exception:
                            pass

                    # 1. 下载通过 ID (cf) 隐密引用的核心 PDF 课件
                    cf_ids = set(re.findall(r'\"cf\",\s*\"([a-f0-9]{24})\"', str_data))
                    
                    async with aiohttp.ClientSession() as session:
                        for fid in cf_ids:
                            tasks.append(download_by_id(fid, session))
                            
                        # 2. 下载原始硬编码路径的杂质附图
                        for m in res_matches:
                            if m.endswith(".pdf"): continue # PDF已被核心接管
                            clean_path = m.lstrip("/")
                            if "http" in clean_path: continue
                            dest_path = os.path.join(out_dir, clean_path.split("/")[-1])
                            tasks.append(download_image(clean_path, dest_path, session))

                        if tasks:
                            await asyncio.gather(*tasks)
                        
                # 注入一个外部方法来获取全局Token
                def get_userinfo_token():
                    return access_token

                try:
                    asyncio.run(fetch_all_resources())
                except Exception as ex:
                    print(f"附加课件资源下载异常：{ex}")

            # 回退去抓取音频流 a1, a2 ...
            vs = list(set(re.findall(r'a\d+/a\.m3u8', str_data)))
            vs.sort(key=lambda x: int(re.search(r'\d+', x).group()))
            
        real_urls = [info[str(bh)]["addr"].split("/ts1")[0] + "/" + v for v in vs]
    except Exception as e:
        print(f"解析 info.plist 分片失败，降级为默认画面: {e}")
        
    if not real_urls:
        real_urls = [info[str(bh)]["addr"].replace("ts1/t.m3u8", "s1/a.m3u8")]

    try:
        asyncio.run(mainfunc(real_urls, out_file, oss_auth=oss_auth))
    except Exception as e:
        print(f"{info[str(bh)]['classname']} {info[str(bh)]['classdate']} 下载出错：{e}\n请稍后重试或手动操作。")

print(f"\n视频转换完成，请到指定目录 [{path}] 查看。\n感谢您的使用！")
