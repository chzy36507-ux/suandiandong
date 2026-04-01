"""
算电通 - 本地数据库管理
存储电价数据、DeepSeek价格、爬取日志
"""
import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'suandiandong.db')

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表结构"""
    conn = get_conn()
    c = conn.cursor()

    # 全国分时电价表
    c.execute('''
        CREATE TABLE IF NOT EXISTS electricity_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            province TEXT NOT NULL,
            user_type TEXT NOT NULL DEFAULT '工商业',
            peak_price REAL,
            normal_price REAL,
            valley_price REAL,
            deep_valley_price REAL,
            peak_hours TEXT,
            normal_hours TEXT,
            valley_hours TEXT,
            source TEXT,
            effective_date TEXT,
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            raw_data TEXT
        )
    ''')

    # 全国居民分时电价表（新增）
    c.execute('''
        CREATE TABLE IF NOT EXISTS residential_electricity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            province TEXT NOT NULL UNIQUE,
            peak_price REAL,
            flat_price REAL,
            valley_price REAL,
            deep_valley_price REAL,
            peak_hours TEXT,
            flat_hours TEXT,
            valley_hours TEXT,
            note TEXT,
            source TEXT,
            effective_date TEXT,
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            raw_data TEXT
        )
    ''')

    # 绿电知识库（新增，待填充）
    c.execute('''
        CREATE TABLE IF NOT EXISTS green_energy_knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            province TEXT NOT NULL UNIQUE,
            energy_type TEXT,
            peak_hours_start TEXT,
            peak_hours_end TEXT,
            peak_hours_note TEXT,
            best_months TEXT,
            season_note TEXT,
            confidence TEXT,
            update_date TEXT
        )
    ''')

    # 提醒记录表（新增）
    c.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            province TEXT NOT NULL,
            reminder_time TEXT,
            user_id TEXT,
            channel TEXT,
            status TEXT DEFAULT 'active',
            last_triggered TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            note TEXT
        )
    ''')

    # DeepSeek API 价格表
    c.execute('''
        CREATE TABLE IF NOT EXISTS deepseek_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model TEXT NOT NULL,
            input_usd REAL,
            output_usd REAL,
            cached_input_usd REAL,
            input_cny REAL,
            output_cny REAL,
            cached_input_cny REAL,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')

    # 爬取日志表
    c.execute('''
        CREATE TABLE IF NOT EXISTS crawler_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL,
            provinces_updated TEXT,
            changes_detected TEXT,
            error_msg TEXT,
            duration_sec REAL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')

    # 系统配置表
    c.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')

    conn.commit()
    conn.close()
    print(f"[DB] 数据库初始化完成: {os.path.abspath(DB_PATH)}")

def upsert_electricity_price(province, user_type, peak, normal, valley, deep_valley,
                              peak_hours, normal_hours, valley_hours, source, effective_date, raw_data):
    """插入或更新电价数据（工商业）"""
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT id FROM electricity_prices WHERE province=? AND user_type=?', (province, user_type))
    row = c.fetchone()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if row:
        c.execute('''
            UPDATE electricity_prices SET
                peak_price=?, normal_price=?, valley_price=?, deep_valley_price=?,
                peak_hours=?, normal_hours=?, valley_hours=?,
                source=?, effective_date=?, updated_at=?, raw_data=?
            WHERE province=? AND user_type=?
        ''', (peak, normal, valley, deep_valley, peak_hours, normal_hours, valley_hours,
              source, effective_date, now, raw_data, province, user_type))
    else:
        c.execute('''
            INSERT INTO electricity_prices
                (province, user_type, peak_price, normal_price, valley_price, deep_valley_price,
                 peak_hours, normal_hours, valley_hours, source, effective_date, updated_at, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (province, user_type, peak, normal, valley, deep_valley,
              peak_hours, normal_hours, valley_hours, source, effective_date, now, raw_data))
    conn.commit()
    conn.close()


def upsert_residential_electricity(province, peak, flat, valley, deep_valley,
                                    peak_hours, flat_hours, valley_hours,
                                    note, source, effective_date, raw_data):
    """插入或更新居民电价数据"""
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('SELECT id FROM residential_electricity WHERE province=?', (province,))
    row = c.fetchone()
    if row:
        c.execute('''
            UPDATE residential_electricity SET
                peak_price=?, flat_price=?, valley_price=?, deep_valley_price=?,
                peak_hours=?, flat_hours=?, valley_hours=?,
                note=?, source=?, effective_date=?, updated_at=?, raw_data=?
            WHERE province=?
        ''', (peak, flat, valley, deep_valley,
              peak_hours, flat_hours, valley_hours,
              note, source, effective_date, now, raw_data, province))
    else:
        c.execute('''
            INSERT INTO residential_electricity
                (province, peak_price, flat_price, valley_price, deep_valley_price,
                 peak_hours, flat_hours, valley_hours,
                 note, source, effective_date, updated_at, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (province, peak, flat, valley, deep_valley,
              peak_hours, flat_hours, valley_hours,
              note, source, effective_date, now, raw_data))
    conn.commit()
    conn.close()
    print(f"    [DB] {province} 居民电价已写入")


def get_residential_electricity(province=None):
    """获取居民电价数据，可指定省份"""
    conn = get_conn()
    c = conn.cursor()
    if province:
        c.execute('SELECT * FROM residential_electricity WHERE province=?', (province,))
    else:
        c.execute('SELECT * FROM residential_electricity ORDER BY province')
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def upsert_green_energy_knowledge(province, energy_type, peak_start, peak_end,
                                   peak_note, best_months, season_note, confidence):
    """插入或更新绿电知识库"""
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('SELECT id FROM green_energy_knowledge WHERE province=?', (province,))
    row = c.fetchone()
    if row:
        c.execute('''
            UPDATE green_energy_knowledge SET
                energy_type=?, peak_hours_start=?, peak_hours_end=?, peak_hours_note=?,
                best_months=?, season_note=?, confidence=?, update_date=?
            WHERE province=?
        ''', (energy_type, peak_start, peak_end, peak_note,
              best_months, season_note, confidence, now, province))
    else:
        c.execute('''
            INSERT INTO green_energy_knowledge
                (province, energy_type, peak_hours_start, peak_hours_end, peak_hours_note,
                 best_months, season_note, confidence, update_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (province, energy_type, peak_start, peak_end, peak_note,
              best_months, season_note, confidence, now))
    conn.commit()
    conn.close()


def get_green_energy_knowledge(province=None):
    """获取绿电知识库"""
    conn = get_conn()
    c = conn.cursor()
    if province:
        c.execute('SELECT * FROM green_energy_knowledge WHERE province=?', (province,))
    else:
        c.execute('SELECT * FROM green_energy_knowledge ORDER BY province')
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def upsert_deepseek_price(model, input_usd, output_usd, cached_input_usd, usd_to_cny=7.25):
    """更新DeepSeek价格"""
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('SELECT id FROM deepseek_prices WHERE model=?', (model,))
    row = c.fetchone()
    if row:
        c.execute('''
            UPDATE deepseek_prices SET
                input_usd=?, output_usd=?, cached_input_usd=?,
                input_cny=?, output_cny=?, cached_input_cny=?, updated_at=?
            WHERE model=?
        ''', (input_usd, output_usd, cached_input_usd,
              round(input_usd * usd_to_cny, 4) if input_usd else None,
              round(output_usd * usd_to_cny, 4) if output_usd else None,
              round(cached_input_usd * usd_to_cny, 4) if cached_input_usd else None,
              now, model))
    else:
        c.execute('''
            INSERT INTO deepseek_prices
                (model, input_usd, output_usd, cached_input_usd, input_cny, output_cny, cached_input_cny, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (model, input_usd, output_usd, cached_input_usd,
              round(input_usd * usd_to_cny, 4) if input_usd else None,
              round(output_usd * usd_to_cny, 4) if output_usd else None,
              round(cached_input_usd * usd_to_cny, 4) if cached_input_usd else None,
              now))
    conn.commit()
    conn.close()

def log_crawler(task_type, status, provinces_updated=None, changes=None, error=None, duration=None):
    """记录爬虫日志"""
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        INSERT INTO crawler_logs (task_type, status, provinces_updated, changes_detected, error_msg, duration_sec)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (task_type, status,
          json.dumps(provinces_updated, ensure_ascii=False) if provinces_updated else None,
          json.dumps(changes, ensure_ascii=False) if changes else None,
          error, duration))
    conn.commit()
    conn.close()

def get_all_electricity_prices():
    """获取所有电价数据"""
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM electricity_prices ORDER BY province, user_type')
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_deepseek_prices():
    """获取DeepSeek价格"""
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM deepseek_prices ORDER BY model')
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def set_config(key, value):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('INSERT OR REPLACE INTO system_config (key, value, updated_at) VALUES (?, ?, ?)',
              (key, str(value), now))
    conn.commit()
    conn.close()

def get_config(key, default=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT value FROM system_config WHERE key=?', (key,))
    row = c.fetchone()
    conn.close()
    return row['value'] if row else default

if __name__ == '__main__':
    init_db()
    print("[DB] 测试完成")
