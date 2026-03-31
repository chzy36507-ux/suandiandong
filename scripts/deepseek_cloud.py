"""
算电通 - 云端 DeepSeek 价格爬虫（GitHub Actions 版）
BeautifulSoup 解析官方定价页面，完全独立运行
"""
import requests
from bs4 import BeautifulSoup
import re
import json
import os
import sys
from datetime import datetime

PRICING_URL = 'https://api-docs.deepseek.com/quick_start/pricing'
USD_TO_CNY = 7.25

def parse_price_str(text):
    if not text:
        return None
    text = text.strip().replace(',', '')
    match = re.search(r'\$?([\d.]+)', text)
    return float(match.group(1)) if match else None

def _expand_prices(price_vals, colspans, num_models):
    expanded = []
    for val, span in zip(price_vals, colspans):
        expanded.extend([val] * span)
    while len(expanded) < num_models:
        expanded.append(expanded[-1] if expanded else None)
    return expanded[:num_models]

def crawl():
    print('[DeepSeek] 爬取定价页面...')
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0'}
    r = requests.get(PRICING_URL, headers=headers, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')

    model_names = []
    price_data = {}
    in_pricing = False

    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            cells = row.find_all(['td', 'th'])
            if not cells:
                continue
            texts = [c.get_text(strip=True) for c in cells]
            colspans = [int(c.get('colspan', 1)) for c in cells]

            if texts[0].upper() == 'MODEL':
                model_names = texts[1:]
                continue
            if texts[0].upper() == 'PRICING' and len(cells) >= 3:
                in_pricing = True
                price_data[texts[1]] = _expand_prices(texts[2:], colspans[2:], len(model_names))
                continue
            if in_pricing and len(cells) >= 2:
                key = texts[0].upper()
                if any(k in key for k in ['TOKEN', 'INPUT', 'OUTPUT', 'CACHE']):
                    price_data[texts[0]] = _expand_prices(texts[1:], colspans[1:], len(model_names))
                else:
                    in_pricing = False

    if not model_names:
        model_names = ['deepseek-chat', 'deepseek-reasoner']

    results = []
    for i, model in enumerate(model_names):
        cached_input = cache_miss = output = None
        for field, prices in price_data.items():
            val = prices[i] if i < len(prices) else (prices[0] if prices else None)
            price = parse_price_str(str(val)) if val else None
            fu = field.upper()
            if 'CACHE HIT' in fu:
                cached_input = price
            elif 'CACHE MISS' in fu:
                cache_miss = price
            elif 'OUTPUT' in fu:
                output = price

        if cache_miss or output:
            results.append({
                'model': model,
                'cached_input_usd': cached_input,
                'input_usd': cache_miss,
                'output_usd': output,
                'input_cny': round(cache_miss * USD_TO_CNY, 4) if cache_miss else None,
                'output_cny': round(output * USD_TO_CNY, 4) if output else None,
                'cached_input_cny': round(cached_input * USD_TO_CNY, 4) if cached_input else None,
                'usd_to_cny': USD_TO_CNY,
                'crawled_at': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            })
            print(f'  [OK] {model}: 输入=${cache_miss}/M 输出=${output}/M (¥{round(cache_miss*USD_TO_CNY,4) if cache_miss else "N/A"}/M)')

    return results

def run():
    print(f'\n{"="*50}')
    print(f'算电通 - DeepSeek价格更新（云端版）')
    print(f'时间: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC')
    print(f'{"="*50}')

    results = crawl()
    if not results:
        print('[失败] 未提取到价格数据')
        sys.exit(1)

    output_path = os.path.join(os.path.dirname(__file__), '..', 'data_output', 'deepseek_prices.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    output = {
        'updated_at': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'usd_to_cny': USD_TO_CNY,
        'data': results
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'[完成] {len(results)} 个模型价格已写入 {output_path}')

if __name__ == '__main__':
    run()
