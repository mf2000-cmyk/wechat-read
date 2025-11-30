# main.py - 模拟微信读书自动阅读（持续约2小时）
import re
import json
import time
import random
import logging
import hashlib
import requests
import urllib.parse
from push import push
from config import data, headers, cookies, PUSH_METHOD, book, chapter

# -----------------------
# 基础设置
# -----------------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)-8s - %(message)s')

KEY = "3c5c8717f3daf09iop3423zafeqoi"
COOKIE_DATA = {"rq": "%2Fweb%2Fbook%2Fread"}
READ_URL = "https://weread.qq.com/web/book/read"
RENEW_URL = "https://weread.qq.com/web/login/renewal"
FIX_SYNCKEY_URL = "https://weread.qq.com/web/book/chapterInfos"

# 模拟阅读时间（秒）
READ_DURATION = 2 * 60 * 60   # 2小时
# 每次翻页间隔（秒）— 随机范围
PAGE_INTERVAL = (15, 45)      # 每次随机等待15~45秒之间

# -----------------------
# 函数定义
# -----------------------

def encode_data(data):
    """对 data 参数进行编码"""
    return '&'.join(f"{k}={urllib.parse.quote(str(data[k]), safe='')}" for k in sorted(data.keys()))


def cal_hash(input_string):
    """计算哈希值"""
    _7032f5 = 0x15051505
    _cc1055 = _7032f5
    length = len(input_string)
    _19094e = length - 1

    while _19094e > 0:
        _7032f5 = 0x7fffffff & (_7032f5 ^ ord(input_string[_19094e]) << (length - _19094e) % 30)
        _cc1055 = 0x7fffffff & (_cc1055 ^ ord(input_string[_19094e - 1]) << _19094e % 30)
        _19094e -= 2

    return hex(_7032f5 + _cc1055)[2:].lower()


def get_wr_skey():
    """刷新cookie密钥"""
    response = requests.post(RENEW_URL, headers=headers, cookies=cookies,
                             data=json.dumps(COOKIE_DATA, separators=(',', ':')))
    for cookie in response.headers.get('Set-Cookie', '').split(';'):
        if "wr_skey" in cookie:
            return cookie.split('=')[-1][:8]
    return None


def fix_no_synckey():
    """修复缺失 synckey 的问题"""
    requests.post(FIX_SYNCKEY_URL, headers=headers, cookies=cookies,
                  data=json.dumps({"bookIds": ["3300060341"]}, separators=(',', ':')))


def refresh_cookie():
    """刷新 cookie 逻辑"""
    logging.info(f"🍪 刷新cookie中...")
    new_skey = get_wr_skey()
    if new_skey:
        cookies['wr_skey'] = new_skey
        logging.info(f"✅ 密钥刷新成功，新密钥：{new_skey}")
    else:
        ERROR_CODE = "❌ 无法获取新密钥或者 WXREAD_CURL_BASH 配置有误，终止运行。"
        logging.error(ERROR_CODE)
        push(ERROR_CODE, PUSH_METHOD)
        raise Exception(ERROR_CODE)


# -----------------------
# 主循环逻辑
# -----------------------

refresh_cookie()

start_time = time.time()
last_time = int(start_time) - 30
index = 1

logging.info(f"🚀 开始模拟阅读，总时长约2小时（7200秒）...")

while time.time() - start_time < READ_DURATION:
    data.pop('s', None)
    data['b'] = random.choice(book)
    data['c'] = random.choice(chapter)
    this_time = int(time.time())
    data['ct'] = this_time
    data['rt'] = this_time - last_time
    data['ts'] = int(this_time * 1000) + random.randint(0, 1000)
    data['rn'] = random.randint(0, 1000)
    data['sg'] = hashlib.sha256(f"{data['ts']}{data['rn']}{KEY}".encode()).hexdigest()
    data['s'] = cal_hash(encode_data(data))

    logging.info(f"⏱️ 第 {index} 次阅读请求...")
    try:
        response = requests.post(READ_URL, headers=headers, cookies=cookies,
                                 data=json.dumps(data, separators=(',', ':')))
        resData = response.json()
        logging.info(f"📘 返回结果: {resData}")
    except Exception as e:
        logging.warning(f"⚠️ 请求失败：{e}")
        time.sleep(10)
        continue

    if 'succ' in resData:
        if 'synckey' in resData:
            last_time = this_time
            index += 1
            wait_time = random.randint(*PAGE_INTERVAL)
            logging.info(f"✅ 阅读成功，等待 {wait_time} 秒后翻页...")
            time.sleep(wait_time)
        else:
            logging.warning("❌ 无 synckey, 尝试修复中...")
            fix_no_synckey()
    else:
        logging.warning("⚠️ cookie 可能已过期，尝试刷新...")
        refresh_cookie()

logging.info(f"🎉 模拟阅读结束，总阅读时长约 {(time.time() - start_time) / 60:.1f} 分钟，共 {index} 页。")

# -----------------------
# 推送通知
# -----------------------
if PUSH_METHOD not in (None, ''):
    msg = f"🎉 微信读书自动阅读完成！\n📚 共阅读 {index} 页。\n⏱️ 阅读时长约 {(time.time() - start_time) / 60:.1f} 分钟。"
    logging.info("⏱️ 开始推送结果...")
    push(msg, PUSH_METHOD)
