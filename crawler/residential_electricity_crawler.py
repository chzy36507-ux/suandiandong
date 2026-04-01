"""
算电通 - 全国居民分时电价爬虫
使用 OpenClaw ProSearch 搜索引擎自动获取各省居民分时电价
覆盖全国31省，包含峰/谷/平时段和价格
"""
import subprocess
import json
import re
import time
import os
import sys
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from db import init_db, upsert_residential_electricity, log_crawler, set_config

# ProSearch 接口配置
GATEWAY_PORT = os.environ.get('AUTH_GATEWAY_PORT', '19000')
PROSEARCH_URL = f'http://localhost:{GATEWAY_PORT}/proxy/prosearch/search'

# DeepSeek API（用于AI解析）
DEEPSEEK_API_KEY = 'sk-12011970ee9547e09201b8b49e83abac'
DEEPSEEK_URL = 'https://api.deepseek.com/chat/completions'

# 全国31省列表（按区域分组，便于观察）
PROVINCES = {
    '华北': ['北京', '天津', '河北', '山西', '内蒙古'],
    '东北': ['辽宁', '吉林', '黑龙江'],
    '华东': ['上海', '江苏', '浙江', '安徽', '福建', '江西', '山东'],
    '华中': ['河南', '湖北', '湖南'],
    '华南': ['广东', '广西', '海南'],
    '西南': ['重庆', '四川', '贵州', '云南', '西藏'],
    '西北': ['陕西', '甘肃', '青海', '宁夏', '新疆'],
}

# 所有省份扁平列表
ALL_PROVINCES = [p for group in PROVINCES.values() for p in group]


def prosearch(keyword, count=8):
    """调用ProSearch搜索"""
    payload = json.dumps({'keyword': keyword, 'count': count})
    try:
        r = requests.post(PROSEARCH_URL, data=payload,
                         headers={'Content-Type': 'application/json'}, timeout=20)
        data = r.json()
        if data.get('success'):
            return data.get('data', {}).get('docs', [])
        else:
            print(f'    [搜索失败] {data.get("message", "未知错误")}')
            return []
    except Exception as e:
        print(f'    [搜索异常] {e}')
        return []


def call_deepseek_parse(text, province):
    """调用DeepSeek AI解析电价文本，提取居民分时电价数据"""
    prompt = f"""从以下文本中提取{province}省的居民分时电价数据。

【重要】要找的是"居民"用电的分时电价，不是工商业电价。如果文本中没有明确说"居民"，请说明。

文本内容：
{text[:4000]}

请返回如下JSON格式（如果数据不存在填null，价格单位是元/千瓦时）：
{{
  "province": "{province}",
  "user_type": "居民",
  "has_residential": true或false（文本中是否有居民电价数据）,
  "peak_price": 峰时电价数字或null,
  "flat_price": 平时电价数字或null,
  "valley_price": 谷时电价数字或null,
  "deep_valley_price": 深谷电价数字或null（如有）,
  "peak_hours": "峰时段描述，如08:00-12:00",
  "flat_hours": "平时段描述，如12:00-17:00",
  "valley_hours": "谷时段描述，如00:00-08:00",
  "note": "补充说明，如居民阶梯电价规则",
  "effective_date": "政策生效日期YYYY-MM",
  "source": "数据来源网站"
}}

只返回JSON，不要其他文字。如果完全没有分时电价数据，返回{{"province": "{province}", "user_type": "居民", "has_residential": false}}"""

    try:
        headers = {
            'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': 'deepseek-chat',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.1,
            'max_tokens': 600
        }
        r = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=30)
        result = r.json()
        content = result['choices'][0]['message']['content'].strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {'error': 'parse_failed', 'province': province}
    except Exception as e:
        print(f'    [DeepSeek解析异常] {e}')
        return {'error': str(e), 'province': province}


def crawl_province_residential(province):
    """爬取单个省份的居民分时电价数据"""
    print(f'\n[{province}] 开始搜索居民分时电价...')

    # 搜索关键词策略：精准定位居民电价
    search_queries = [
        f'{province}居民分时电价 峰谷平 元/kWh 2024 2025',
        f'{province}居民用电峰谷电价 时段 价格 2025',
    ]

    all_docs = []
    for query in search_queries[:2]:
        docs = prosearch(query)
        if docs:
            all_docs.extend(docs)
        if len(all_docs) >= 8:
            break
        time.sleep(0.5)

    if not all_docs:
        print(f'  [跳过] {province} 未找到搜索结果')
        return None

    # 合并前6个文档的文本内容
    combined_text = f'{province}居民分时电价数据\n\n'
    for doc in all_docs[:6]:
        combined_text += f"【来源: {doc.get('site', '未知')}】\n"
        combined_text += f"标题: {doc.get('title', '')}\n"
        combined_text += f"内容: {doc.get('passage', '')}\n\n"

    # AI解析
    print(f'  [解析] 调用AI提取居民电价数据...')
    parsed = call_deepseek_parse(combined_text, province)

    if parsed.get('error'):
        print(f'  [失败] {province} 解析失败: {parsed["error"]}')
        return None

    if not parsed.get('has_residential'):
        print(f'  [跳过] {province} 未找到居民分时电价数据（只有工商业电价）')
        return None

    # 验证关键字段
    has_price = any([parsed.get('peak_price'), parsed.get('flat_price'), parsed.get('valley_price')])
    if not has_price:
        print(f'  [跳过] {province} 未提取到有效电价数据')
        return None

    print(f'  [成功] {province}: 峰={parsed.get("peak_price")} 平={parsed.get("flat_price")} 谷={parsed.get("valley_price")} 元/kWh')
    print(f'         时段: 峰={parsed.get("peak_hours")} 谷={parsed.get("valley_hours")}')
    return parsed


def run_residential_crawler():
    """主爬虫任务：全国居民分时电价数据"""
    start_time = time.time()
    print(f'\n{"="*60}')
    print(f'算电通 - 全国居民分时电价爬虫')
    print(f'开始时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'覆盖省份: {len(ALL_PROVINCES)} 个（全国）')
    print(f'{"="*60}')

    init_db()

    updated_provinces = []
    failed_provinces = []
    no_residential = []

    for i, province in enumerate(ALL_PROVINCES):
        region = next((r for r, ps in PROVINCES.items() if province in ps), '')
        print(f'\n[{i+1}/{len(ALL_PROVINCES)}][{region}] 处理 {province}...')
        try:
            result = crawl_province_residential(province)
            if result and result.get('has_residential'):
                upsert_residential_electricity(
                    province=result.get('province', province),
                    peak=result.get('peak_price'),
                    flat=result.get('flat_price'),
                    valley=result.get('valley_price'),
                    deep_valley=result.get('deep_valley_price'),
                    peak_hours=result.get('peak_hours', ''),
                    flat_hours=result.get('flat_hours', ''),
                    valley_hours=result.get('valley_hours', ''),
                    note=result.get('note', ''),
                    source=result.get('source', ''),
                    effective_date=result.get('effective_date', ''),
                    raw_data=json.dumps(result, ensure_ascii=False)
                )
                updated_provinces.append(province)
            elif result:
                no_residential.append(province)
            else:
                failed_provinces.append(province)
        except Exception as e:
            print(f'  [异常] {province}: {e}')
            failed_provinces.append(province)

        # 避免请求过快
        time.sleep(1.5)

    duration = round(time.time() - start_time, 1)

    # 记录日志
    log_crawler(
        task_type='residential_electricity',
        status='success' if updated_provinces else 'failed',
        provinces_updated=updated_provinces,
        changes={
            'updated': len(updated_provinces),
            'no_residential': len(no_residential),
            'failed': len(failed_provinces),
            'failed_list': failed_provinces
        },
        duration=duration
    )

    # 更新最后运行时间
    set_config('residential_last_run', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    print(f'\n{"="*60}')
    print(f'任务完成！耗时: {duration}秒')
    print(f'成功获取: {len(updated_provinces)} 个省份')
    print(f'无居民分时: {len(no_residential)} 个省份: {", ".join(no_residential)}')
    print(f'搜索失败: {len(failed_provinces)} 个省份: {", ".join(failed_provinces)}')
    if updated_provinces:
        print(f'\n已获取数据的省份: {", ".join(updated_provinces)}')
    print(f'{"="*60}\n')

    return {
        'updated': updated_provinces,
        'no_residential': no_residential,
        'failed': failed_provinces,
        'duration': duration
    }


if __name__ == '__main__':
    run_residential_crawler()
