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

    # 替换原本的 ts1/t.m3u8 为真实存在的 s1/a.m3u8 (视频画面流)
    real_m3u8 = info[str(bh)]["addr"].replace("ts1/t.m3u8", "s1/a.m3u8")
    
    try:
        asyncio.run(mainfunc(real_m3u8, out_file, oss_auth=oss_auth))
    except Exception as e:
        print(f"画面流下载异常...({e})")
        try:
            # 尝试备用音频流 a1/a.m3u8
            audio_m3u8 = info[str(bh)]["addr"].replace("ts1/t.m3u8", "a1/a.m3u8")
            print("尝试下载备用流...")
            asyncio.run(mainfunc(audio_m3u8, out_file, oss_auth=oss_auth))
        except Exception as ex:
            print(f"{info[str(bh)]['classname']} {info[str(bh)]['classdate']} 下载出错：{ex}\n请稍后重试或手动操作。")

print(f"\n视频转换完成，请到指定目录 [{path}] 查看。\n感谢您的使用！")
