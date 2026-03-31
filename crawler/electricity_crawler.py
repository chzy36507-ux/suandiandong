"""
算电通 - 全国电价数据爬虫
使用 OpenClaw ProSearch 搜索引擎自动获取各省分时电价
每12天运行一次，AI解析结构化数据存入本地SQLite
"""
import subprocess
import json
import re
import time
import os
import sys
import requests
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(__file__))
from db import init_db, upsert_electricity_price, log_crawler, set_config, get_config

# ProSearch 接口配置
GATEWAY_PORT = os.environ.get('AUTH_GATEWAY_PORT', '19000')
PROSEARCH_URL = f'http://localhost:{GATEWAY_PORT}/proxy/prosearch/search'

# DeepSeek API（用于AI解析）
DEEPSEEK_API_KEY = 'sk-12011970ee9547e09201b8b49e83abac'
DEEPSEEK_URL = 'https://api.deepseek.com/chat/completions'

# 全国主要省份列表（覆盖全国）
PROVINCES = [
    '广东', '北京', '上海', '浙江', '江苏', '山东', '河南', '四川',
    '湖北', '湖南', '安徽', '福建', '河北', '陕西', '重庆', '天津',
    '辽宁', '吉林', '黑龙江', '江西', '广西', '云南', '贵州', '山西',
    '内蒙古', '新疆', '甘肃', '海南', '宁夏', '青海', '西藏'
]

def prosearch(keyword, industry=None):
    """调用ProSearch搜索"""
    payload = {'keyword': keyword}
    if industry:
        payload['industry'] = industry
    try:
        r = requests.post(PROSEARCH_URL, json=payload, timeout=15)
        data = r.json()
        if data.get('success'):
            return data.get('data', {}).get('docs', [])
        else:
            print(f'  [搜索失败] {data.get("message", "未知错误")}')
            return []
    except Exception as e:
        print(f'  [搜索异常] {e}')
        return []

def call_deepseek_parse(text, province):
    """调用DeepSeek AI解析电价文本"""
    prompt = f"""从以下文本中提取{province}的工商业分时电价数据，返回JSON格式。

文本内容：
{text[:3000]}

请提取并返回以下JSON格式（如果某项数据不存在则填null）：
{{
  "province": "{province}",
  "user_type": "工商业",
  "peak_price": 峰时电价(元/千瓦时，数字),
  "normal_price": 平时电价(元/千瓦时，数字),
  "valley_price": 谷时电价(元/千瓦时，数字),
  "deep_valley_price": 深谷电价(元/千瓦时，数字或null),
  "peak_hours": "峰时时段描述",
  "normal_hours": "平时时段描述",
  "valley_hours": "谷时时段描述",
  "effective_date": "生效日期(YYYY-MM格式)",
  "source": "数据来源网站"
}}

只返回JSON，不要其他文字。如果文本中没有明确的分时电价数据，返回 {{"error": "no_data"}}"""

    try:
        headers = {
            'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': 'deepseek-chat',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.1,
            'max_tokens': 500
        }
        r = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=30)
        result = r.json()
        content = result['choices'][0]['message']['content'].strip()
        # 提取JSON
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {'error': 'parse_failed'}
    except Exception as e:
        print(f'  [DeepSeek解析异常] {e}')
        return {'error': str(e)}

def crawl_province_electricity(province):
    """爬取单个省份的电价数据"""
    print(f'\n[{province}] 开始搜索电价数据...')

    # 搜索策略：多关键词组合（精准搜索含价格数字的内容）
    search_queries = [
        f'{province}工商业电价 峰时 元/千瓦时 2024 2025',
        f'{province}分时电价标准 峰谷平 元/度 工商业',
        f'{province}电网代理购电 峰谷电价 元/kWh',
    ]

    all_docs = []
    for query in search_queries[:2]:  # 最多搜2次
        # 先不限行业搜索（覆盖更广）
        docs = prosearch(query)
        if not docs:
            docs = prosearch(query, industry='gov')
        all_docs.extend(docs)
        if len(all_docs) >= 5:
            break
        time.sleep(1)

    if not all_docs:
        print(f'  [跳过] {province} 未找到搜索结果')
        return None

    # 合并文本内容
    combined_text = f'{province}分时电价数据\n\n'
    for doc in all_docs[:5]:
        combined_text += f"来源: {doc.get('site', '')}\n"
        combined_text += f"标题: {doc.get('title', '')}\n"
        combined_text += f"内容: {doc.get('passage', '')}\n\n"

    # AI解析
    print(f'  [解析] 调用AI提取结构化数据...')
    parsed = call_deepseek_parse(combined_text, province)

    if parsed.get('error'):
        print(f'  [失败] {province} 解析失败: {parsed["error"]}')
        return None

    # 验证关键字段
    if not parsed.get('peak_price') and not parsed.get('normal_price'):
        print(f'  [跳过] {province} 未提取到有效电价数据')
        return None

    print(f'  [成功] {province}: 峰={parsed.get("peak_price")} 平={parsed.get("normal_price")} 谷={parsed.get("valley_price")} 元/kWh')
    return parsed

def run_electricity_crawler():
    """主爬虫任务：全国电价数据更新"""
    start_time = time.time()
    print(f'\n{"="*60}')
    print(f'算电通 - 全国电价数据更新任务')
    print(f'开始时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'覆盖省份: {len(PROVINCES)} 个')
    print(f'{"="*60}')

    init_db()

    updated_provinces = []
    failed_provinces = []

    for i, province in enumerate(PROVINCES):
        print(f'\n[{i+1}/{len(PROVINCES)}] 处理 {province}...')
        try:
            result = crawl_province_electricity(province)
            if result:
                upsert_electricity_price(
                    province=result.get('province', province),
                    user_type=result.get('user_type', '工商业'),
                    peak=result.get('peak_price'),
                    normal=result.get('normal_price'),
                    valley=result.get('valley_price'),
                    deep_valley=result.get('deep_valley_price'),
                    peak_hours=result.get('peak_hours', ''),
                    normal_hours=result.get('normal_hours', ''),
                    valley_hours=result.get('valley_hours', ''),
                    source=result.get('source', ''),
                    effective_date=result.get('effective_date', ''),
                    raw_data=json.dumps(result, ensure_ascii=False)
                )
                updated_provinces.append(province)
            else:
                failed_provinces.append(province)
        except Exception as e:
            print(f'  [异常] {province}: {e}')
            failed_provinces.append(province)

        # 避免请求过快
        time.sleep(2)

    duration = round(time.time() - start_time, 1)

    # 记录日志
    log_crawler(
        task_type='electricity',
        status='success' if updated_provinces else 'failed',
        provinces_updated=updated_provinces,
        changes={'updated': len(updated_provinces), 'failed': len(failed_provinces)},
        duration=duration
    )

    # 更新最后运行时间
    set_config('electricity_last_run', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    set_config('electricity_next_run', '')

    print(f'\n{"="*60}')
    print(f'任务完成！耗时: {duration}秒')
    print(f'成功更新: {len(updated_provinces)} 个省份: {", ".join(updated_provinces)}')
    print(f'未获取到: {len(failed_provinces)} 个省份: {", ".join(failed_provinces)}')
    print(f'{"="*60}\n')

    return {
        'updated': updated_provinces,
        'failed': failed_provinces,
        'duration': duration
    }

if __name__ == '__main__':
    run_electricity_crawler()
