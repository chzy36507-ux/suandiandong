"""
算电通 - 数据查询工具
命令行查询本地数据库中的电价和DeepSeek价格
"""
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from db import get_all_electricity_prices, get_deepseek_prices, get_config

def show_deepseek_prices():
    """展示DeepSeek价格"""
    prices = get_deepseek_prices()
    last_run = get_config('deepseek_last_run', '从未运行')
    print(f'\n{"="*60}')
    print(f'DeepSeek API 价格  (最后更新: {last_run})')
    print(f'{"="*60}')
    if not prices:
        print('暂无数据，等待首次爬取')
        return
    for p in prices:
        print(f'\n模型: {p["model"]}')
        print(f'  缓存命中输入: ${p["input_usd"] or "N/A"}/M tokens  (¥{p["input_cny"] or "N/A"}/M)')
        print(f'  缓存未命中输入: ${p.get("input_usd") or "N/A"}/M tokens')
        print(f'  输出: ${p["output_usd"] or "N/A"}/M tokens  (¥{p["output_cny"] or "N/A"}/M)')
        print(f'  更新时间: {p["updated_at"]}')

def show_electricity_prices(province=None):
    """展示电价数据"""
    all_prices = get_all_electricity_prices()
    last_run = get_config('electricity_last_run', '从未运行')

    if province:
        prices = [p for p in all_prices if province in p['province']]
        title = f'{province} 分时电价'
    else:
        prices = all_prices
        title = f'全国分时电价 (共{len(prices)}条记录)'

    print(f'\n{"="*60}')
    print(f'{title}  (最后更新: {last_run})')
    print(f'{"="*60}')

    if not prices:
        print('暂无数据，等待首次爬取（每12天自动更新）')
        return

    for p in prices:
        print(f'\n{p["province"]} - {p["user_type"]}')
        print(f'  峰时: ¥{p["peak_price"] or "N/A"}/kWh  {p["peak_hours"] or ""}')
        print(f'  平时: ¥{p["normal_price"] or "N/A"}/kWh  {p["normal_hours"] or ""}')
        print(f'  谷时: ¥{p["valley_price"] or "N/A"}/kWh  {p["valley_hours"] or ""}')
        if p.get('deep_valley_price'):
            print(f'  深谷: ¥{p["deep_valley_price"]}/kWh')
        print(f'  生效日期: {p["effective_date"] or "未知"}  来源: {p["source"] or "未知"}')
        print(f'  更新时间: {p["updated_at"]}')

def show_status():
    """展示系统状态"""
    print(f'\n{"="*60}')
    print(f'算电通 - 系统状态')
    print(f'{"="*60}')
    print(f'当前时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'DeepSeek价格 最后更新: {get_config("deepseek_last_run", "从未运行")}')
    print(f'电价数据 最后更新: {get_config("electricity_last_run", "从未运行")}')

    all_ep = get_all_electricity_prices()
    ds_prices = get_deepseek_prices()
    print(f'电价数据: {len(all_ep)} 条省份记录')
    print(f'DeepSeek价格: {len(ds_prices)} 个模型')
    print(f'\n定时任务:')
    print(f'  - DeepSeek价格爬虫: 每3天自动运行')
    print(f'  - 全国电价爬虫: 每12天自动运行')
    print(f'\n数据库位置: {os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "suandiandong.db"))}')

if __name__ == '__main__':
    args = sys.argv[1:]

    if not args or args[0] == 'status':
        show_status()
    elif args[0] == 'deepseek':
        show_deepseek_prices()
    elif args[0] == 'electricity':
        province = args[1] if len(args) > 1 else None
        show_electricity_prices(province)
    elif args[0] == 'all':
        show_status()
        show_deepseek_prices()
        show_electricity_prices()
    else:
        print('用法:')
        print('  python query.py status          # 系统状态')
        print('  python query.py deepseek        # DeepSeek价格')
        print('  python query.py electricity     # 全国电价')
        print('  python query.py electricity 广东 # 指定省份')
        print('  python query.py all             # 全部数据')
