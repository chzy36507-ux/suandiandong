import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
from db import init_db, upsert_electricity_price
from electricity_crawler import crawl_province_electricity

init_db()

test_provinces = ['广东', '北京', '浙江']
results = []

for province in test_provinces:
    print('\n[测试] ' + province + '...')
    r = crawl_province_electricity(province)
    results.append((province, r))
    time.sleep(3)

print('\n\n=== 测试结果汇总 ===')
for province, r in results:
    if r:
        peak = str(r.get('peak_price', 'N/A'))
        normal = str(r.get('normal_price', 'N/A'))
        valley = str(r.get('valley_price', 'N/A'))
        peak_h = r.get('peak_hours', '')
        source = r.get('source', '')
        print('[OK] ' + province + ': 峰=' + peak + ' 平=' + normal + ' 谷=' + valley + ' 元/kWh')
        print('     峰时段: ' + peak_h)
        print('     来源: ' + source)
        # 写入数据库
        upsert_electricity_price(
            province=r.get('province', province),
            user_type=r.get('user_type', '工商业'),
            peak=r.get('peak_price'),
            normal=r.get('normal_price'),
            valley=r.get('valley_price'),
            deep_valley=r.get('deep_valley_price'),
            peak_hours=r.get('peak_hours', ''),
            normal_hours=r.get('normal_hours', ''),
            valley_hours=r.get('valley_hours', ''),
            source=r.get('source', ''),
            effective_date=r.get('effective_date', ''),
            raw_data=str(r)
        )
        print('     [已写入数据库]')
    else:
        print('[FAIL] ' + province + ': 未获取到数据')
