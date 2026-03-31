"""
算电通 - 云端全国电价爬虫（GitHub Actions 版）
使用 Tavily API 替代 ProSearch，完全脱离本地 QClaw
"""
import requests
import json
import re
import time
import os
import sys
from datetime import datetime

TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY', '')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_URL = 'https://api.deepseek.com/chat/completions'
TAVILY_URL = 'https://api.tavily.com/search'

PROVINCES = [
    '广东', '北京', '上海', '浙江', '江苏', '山东', '河南', '四川',
    '湖北', '湖南', '安徽', '福建', '河北', '陕西', '重庆', '天津',
    '辽宁', '吉林', '黑龙江', '江西', '广西', '云南', '贵州', '山西',
    '内蒙古', '新疆', '甘肃', '海南', '宁夏', '青海', '西藏'
]

def tavily_search(query, max_results=5):
    """Tavily 搜索"""
    if not TAVILY_API_KEY:
        print('  [错误] TAVILY_API_KEY 未设置')
        return []
    try:
        payload = {
            'api_key': TAVILY_API_KEY,
            'query': query,
            'search_depth': 'basic',
            'max_results': max_results,
            'include_answer': False,
            'include_raw_content': False,
        }
        r = requests.post(TAVILY_URL, json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()
        results = data.get('results', [])
        print(f'  [Tavily] "{query}" -> {len(results)} 条结果')
        return results
    except Exception as e:
        print(f'  [Tavily 异常] {e}')
        return []

def call_deepseek_parse(text, province):
    """DeepSeek AI 解析电价文本"""
    prompt = f"""从以下文本中提取{province}的工商业分时电价数据，返回JSON格式。

文本内容：
{text[:3000]}

请提取并返回以下JSON格式（数字类型，不存在填null）：
{{
  "province": "{province}",
  "user_type": "工商业",
  "peak_price": 峰时电价(元/千瓦时),
  "normal_price": 平时电价(元/千瓦时),
  "valley_price": 谷时电价(元/千瓦时),
  "deep_valley_price": 深谷电价(元/千瓦时或null),
  "peak_hours": "峰时时段",
  "normal_hours": "平时时段",
  "valley_hours": "谷时时段",
  "effective_date": "生效日期YYYY-MM或null",
  "source": "数据来源"
}}

只返回JSON，不要其他文字。没有明确分时电价数据则返回 {{"error": "no_data"}}"""

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
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {'error': 'parse_failed'}
    except Exception as e:
        print(f'  [DeepSeek 异常] {e}')
        return {'error': str(e)}

def crawl_province(province):
    """爬取单省电价"""
    queries = [
        f'{province}工商业电价 峰时 元/千瓦时 2024 2025',
        f'{province}分时电价标准 峰谷平 元/度 工商业',
    ]

    all_docs = []
    for query in queries[:2]:
        docs = tavily_search(query, max_results=5)
        all_docs.extend(docs)
        if len(all_docs) >= 5:
            break
        time.sleep(1)

    if not all_docs:
        return None

    combined = f'{province}分时电价数据\n\n'
    for doc in all_docs[:5]:
        combined += f"来源: {doc.get('url', '')}\n"
        combined += f"标题: {doc.get('title', '')}\n"
        combined += f"内容: {doc.get('content', '')[:400]}\n\n"

    parsed = call_deepseek_parse(combined, province)
    if parsed.get('error'):
        return None
    if not parsed.get('peak_price') and not parsed.get('normal_price') and not parsed.get('valley_price'):
        return None

    parsed['crawled_at'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    return parsed

def run():
    print(f'\n{"="*60}')
    print(f'算电通 - 全国电价数据更新（云端版）')
    print(f'时间: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC')
    print(f'Tavily Key: {"已配置" if TAVILY_API_KEY else "未配置！"}')
    print(f'DeepSeek Key: {"已配置" if DEEPSEEK_API_KEY else "未配置！"}')
    print(f'{"="*60}')

    if not TAVILY_API_KEY or not DEEPSEEK_API_KEY:
        print('[致命错误] API Key 未配置，退出')
        sys.exit(1)

    # 读取已有数据（增量更新）
    output_path = os.path.join(os.path.dirname(__file__), '..', 'data_output', 'electricity.json')
    existing = {}
    if os.path.exists(output_path):
        with open(output_path, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
            existing = {item['province']: item for item in old_data.get('data', [])}
        print(f'[增量] 已有 {len(existing)} 条旧数据，本次全量刷新')

    results = []
    success_list = []
    failed_list = []

    for i, province in enumerate(PROVINCES):
        print(f'\n[{i+1}/{len(PROVINCES)}] {province}...')
        try:
            data = crawl_province(province)
            if data:
                results.append(data)
                success_list.append(province)
                print(f'  [OK] 峰={data.get("peak_price")} 平={data.get("normal_price")} 谷={data.get("valley_price")} 元/kWh')
            else:
                # 保留旧数据
                if province in existing:
                    results.append(existing[province])
                    print(f'  [保留旧数据] {province}')
                else:
                    failed_list.append(province)
                    print(f'  [失败] 无数据')
        except Exception as e:
            print(f'  [异常] {e}')
            if province in existing:
                results.append(existing[province])
            else:
                failed_list.append(province)
        time.sleep(2)

    # 写出 JSON
    output = {
        'updated_at': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'total': len(results),
        'success_count': len(success_list),
        'failed_provinces': failed_list,
        'data': results
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'\n{"="*60}')
    print(f'完成！成功: {len(success_list)} 省，失败: {len(failed_list)} 省')
    print(f'数据已写入: {output_path}')
    print(f'{"="*60}')

if __name__ == '__main__':
    run()
