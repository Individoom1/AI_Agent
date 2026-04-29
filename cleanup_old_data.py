#!/usr/bin/env python3
"""
Скрипт очистки данных старше 3 лет и переинициализации синхронизации
за последние 3 года (2024-2026)
"""

import psycopg2
from datetime import datetime, timedelta
from db import get_db_connection

def cleanup_old_data(years=3):
    """
    Удаляет данные из таблиц, которые старше N лет
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    cutoff_date = datetime.now() - timedelta(days=365*years)
    cutoff_date_str = cutoff_date.strftime("%Y-%m-%d")
    
    print(f"  Удаление данных старше: {cutoff_date_str}")
    print(f"  Будут сохранены данные с {datetime.now().strftime('%Y-%m-%d')} до {cutoff_date_str}\n")
    
    tables_with_dates = {
        'lots': 'lastUpdateDate',
        'announcements': 'lastUpdateDate',
        'contracts': 'sign_date'
    }
    
    for table, date_column in tables_with_dates.items():
        cur.execute(f"""
            SELECT COUNT(*) FROM {table} 
            WHERE {date_column} < %s
        """, (cutoff_date,))
        count_to_delete = cur.fetchone()[0]
        
        if count_to_delete > 0:
            print(f"{table:15} | Удаление {count_to_delete:,} старых записей...")
            
            cur.execute(f"""
                DELETE FROM {table} 
                WHERE {date_column} < %s
            """, (cutoff_date,))
            
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            remaining = cur.fetchone()[0]
            print(f"                    | Осталось: {remaining:,} записей \n")
        else:
            print(f"{table:15} | Нет данных для удаления\n")
    
    cur.execute("DELETE FROM sync_meta")
    print(f" sync_meta очищена (синхронизация будет переинициализирована)\n")
    
    conn.commit()
    conn.close()
    
    print("Очистка завершена!")


def show_data_stats():
    """
    Показывает статистику данных до и после
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n📊 Статистика данных:\n")
    
    tables = ['organizations', 'subjects', 'contracts', 'lots', 'announcements']
    total = 0
    
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        total += count
        print(f"   {table:15} | {count:,} записей")
    
    print(f"   {'TOTAL':15} | {total:,} записей\n")
    
    cur.execute("""
    SELECT 
        MIN(lastUpdateDate) as oldest,
        MAX(lastUpdateDate) as newest
    FROM lots
    WHERE lastUpdateDate IS NOT NULL
    """)
    
    result = cur.fetchone()
    if result:
        oldest, newest = result
        print(f"📅 Диапазон дат в лотах:")
        print(f"   Старая запись: {oldest}")
        print(f"   Новая запись: {newest}")
    
    cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM lastUpdateDate) as year,
        COUNT(*) as count
    FROM lots
    WHERE lastUpdateDate IS NOT NULL
    GROUP BY year
    ORDER BY year DESC
    """)
    
    print(f"\nРаспределение лотов по годам:\n")
    for year, count in cur.fetchall():
        print(f"   {int(year)}: {count:,} лотов")
    
    conn.close()


if __name__ == "__main__":
    import sys
    
    print("=" * 70)
    print("Скрипт очистки старых данных и переинициализации (3 года)")
    print("=" * 70)
    
    print("\nДО очистки:\n")
    show_data_stats()
    
    response = input("\nВы уверены? Это удалит все данные старше 3 лет! [y/N]: ").strip().lower()
    
    if response == 'y':
        cleanup_old_data(years=3)
        
        print("\nПОСЛЕ очистки:\n")
        show_data_stats()
        
        print("\n" + "=" * 70)
        print("Готово! Запустите 'python3 sync_all.py' для загрузки свежих данных")
        print("=" * 70)
    else:
        print("\nОтменено.")
        sys.exit(0)
