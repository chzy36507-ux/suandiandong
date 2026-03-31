"""
算电通 - DeepSeek API 价格爬虫
每3天自动爬取 DeepSeek 官方定价页面，BeautifulSoup 解析
"""
import requests
from bs4 import BeautifulSoup
import re
import sys
import os
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from db import init_db, upsert_deepseek_price, log_crawler, set_config

PRICING_URL = 'https://api-docs.deepseek.com/quick_start/pricing'
USD_TO_CNY = 7.25  # 汇率

def parse_price_str(text):
    """从文本中提取价格数字（美元）"""
    if not text:
        return None
    text = text.strip().replace(',', '')
    match = re.search(r'\$?([\d.]+)', text)
    if match:
        return float(match.group(1))
    return None

def crawl_deepseek_prices():
    """
    爬取DeepSeek定价页面
    表格结构说明：
    - 第一行: ['MODEL', 'deepseek-chat', 'deepseek-reasoner']
    - PRICING区域: cell[0]=PRICING(rowspan=3), cell[1]=字段名, cell[2]=价格(colspan=2表示两模型同价)
    - 后续行: cell[0]=字段名, cell[1]=价格(colspan=2同价 或 两个不同价格)
    """
    print(f'\n[DeepSeek] 开始爬取价格页面...')
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0'
    }

    try:
        r = requests.get(PRICING_URL, headers=headers, timeout=15)
        r.raise_for_status()
        print(f'  [OK] 状态码: {r.status_code}, 内容长度: {len(r.text)} bytes')
    except Exception as e:
        print(f'  [失败] 请求异常: {e}')
        return None

    soup = BeautifulSoup(r.text, 'html.parser')
    tables = soup.find_all('table')
    print(f'  [解析] 找到 {len(tables)} 个表格')

    # 提取模型名称和价格
    model_names = []
    price_data = {}  # {字段名: [价格1, 价格2, ...]}
    in_pricing = False

    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if not cells:
                continue
            texts = [c.get_text(strip=True) for c in cells]
            colspans = [int(c.get('colspan', 1)) for c in cells]

            # 提取模型名称行
            if texts[0].upper() == 'MODEL':
                model_names = texts[1:]
                continue

            # 检测PRICING区域开始
            if texts[0].upper() == 'PRICING' and len(cells) >= 3:
                in_pricing = True
                # 这行格式: ['PRICING', '字段名', '价格']
                field_name = texts[1]
                price_vals = texts[2:]
                price_data[field_name] = _expand_prices(price_vals, colspans[2:], len(model_names))
                continue

            # PRICING区域后续行（只有字段名和价格，没有PRICING列）
            if in_pricing and len(cells) >= 2:
                # 检查是否还在PRICING区域（字段名包含TOKEN或PRICE相关词）
                field_key = texts[0].upper()
                if 'TOKEN' in field_key or 'INPUT' in field_key or 'OUTPUT' in field_key or 'CACHE' in field_key:
                    field_name = texts[0]
                    price_vals = texts[1:]
                    price_data[field_name] = _expand_prices(price_vals, colspans[1:], len(model_names))
                else:
                    in_pricing = False

    if not model_names:
        model_names = ['deepseek-chat', 'deepseek-reasoner']

    print(f'  [模型] {model_names}')
    print(f'  [价格字段] {list(price_data.keys())}')

    # 组装每个模型的价格
    results = []
    for i, model in enumerate(model_names):
        cached_input = None
        cache_miss_input = None
        output = None

        for field, prices in price_data.items():
            val = prices[i] if i < len(prices) else (prices[0] if prices else None)
            price = parse_price_str(str(val)) if val else None
            field_upper = field.upper()
            if 'CACHE HIT' in field_upper:
                cached_input = price
            elif 'CACHE MISS' in field_upper:
                cache_miss_input = price
            elif 'OUTPUT' in field_upper:
                output = price

        if cache_miss_input or output:
            results.append({
                'model': model,
                'cached_input_usd': cached_input,
                'input_usd': cache_miss_input,
                'output_usd': output,
            })

    print(f'  [结果] 提取到 {len(results)} 个模型价格')
    return results

def _expand_prices(price_vals, colspans, num_models):
    """根据colspan展开价格列表，使其与模型数量对应"""
    expanded = []
    for val, span in zip(price_vals, colspans):
        expanded.extend([val] * span)
    # 补齐到模型数量
    while len(expanded) < num_models:
        expanded.append(expanded[-1] if expanded else None)
    return expanded[:num_models]

def run_deepseek_crawler():
    """主任务"""
    start_time = time.time()
    print(f'\n{"="*50}')
    print(f'算电通 - DeepSeek价格更新任务')
    print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'{"="*50}')

    init_db()
    results = crawl_deepseek_prices()

    if not results:
        log_crawler('deepseek', 'failed', error='未提取到价格数据')
        print('[失败] 未获取到价格数据')
        return None

    updated = []
    for item in results:
        model = item['model']
        upsert_deepseek_price(
            model=model,
            input_usd=item.get('input_usd'),
            output_usd=item.get('output_usd'),
            cached_input_usd=item.get('cached_input_usd'),
            usd_to_cny=USD_TO_CNY
        )
        updated.append(model)
        print(f'  [更新] {model}:')
        print(f'         缓存命中输入 = ${item.get("cached_input_usd")}/M tokens')
        print(f'         缓存未命中输入 = ${item.get("input_usd")}/M tokens  (CNY: ¥{round(item.get("input_usd",0)*USD_TO_CNY,4) if item.get("input_usd") else "N/A"}/M)')
        print(f'         输出 = ${item.get("output_usd")}/M tokens  (CNY: ¥{round(item.get("output_usd",0)*USD_TO_CNY,4) if item.get("output_usd") else "N/A"}/M)')

    duration = round(time.time() - start_time, 1)
    log_crawler('deepseek', 'success',
                provinces_updated=updated,
                changes={'models_updated': len(updated)},
                duration=duration)
    set_config('deepseek_last_run', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    print(f'\n[完成] 更新 {len(updated)} 个模型价格，耗时 {duration}s')
    return updated

if __name__ == '__main__':
    run_deepseek_crawler()
