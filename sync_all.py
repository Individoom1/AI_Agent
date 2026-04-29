from sync_contracts import sync_contracts
from sync_subjects import sync_subjects
from sync_announcements import sync_announcements
from sync_lots import sync_lots
from datetime import datetime, timedelta
from db import get_db_connection

def get_last_update(entity):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT last_update_date FROM sync_meta WHERE entity = %s", (entity,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def update_last_update(entity, last_date):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sync_meta (entity, last_update_date) VALUES (%s, %s) ON CONFLICT (entity) DO UPDATE SET last_update_date = EXCLUDED.last_update_date",
        (entity, last_date)
    )
    conn.commit()
    conn.close()

if __name__ == "__main__":
    print("[SYNC_ALL] Запуск полной синхронизации данных")
    
    print("[SYNC_ALL] Запуск синхронизации субъектов")
    try:
        subjects_count = sync_subjects()
        print(f"[SYNC_ALL] Субъектов сохранено: {subjects_count}")
    except Exception as exc:
        print(f"[SYNC_ALL] Ошибка синхронизации субъектов: {exc}")

    print("[SYNC_ALL] Запуск синхронизации объявлений")
    last_update_ann = get_last_update("announcements")
    if last_update_ann:
        last_update_ann = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    else:
        last_update_ann = None
    
    try:
        announcements_count = sync_announcements(last_update_after=last_update_ann)
        print(f"[SYNC_ALL] Объявлений сохранено: {announcements_count}")
        update_last_update("announcements", datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
    except Exception as exc:
        print(f"[SYNC_ALL] Ошибка синхронизации объявлений: {exc}")

    print("[SYNC_ALL] Запуск синхронизации контрактов")
    last_update_contracts = get_last_update("contracts")
    if last_update_contracts:
        last_update_contracts = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    else:
        last_update_contracts = None
    
    try:
        contracts_count = sync_contracts(last_update_after=last_update_contracts)
        print(f"[SYNC_ALL] Контрактов сохранено: {contracts_count}")
        update_last_update("contracts", datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
    except Exception as exc:
        print(f"[SYNC_ALL] Ошибка синхронизации контрактов: {exc}")

    print("[SYNC_ALL] Запуск синхронизации лотов")
    last_update_lots = get_last_update("lots")
    if last_update_lots:
        last_update_lots = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    else:
        last_update_lots = None
    
    try:
        lots_count = sync_lots(last_update_after=last_update_lots)
        print(f"[SYNC_ALL] Лотов сохранено: {lots_count}")
        update_last_update("lots", datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
    except Exception as exc:
        print(f"[SYNC_ALL] Ошибка синхронизации лотов: {exc}")

    print("[SYNC_ALL] Синхронизация завершена")
