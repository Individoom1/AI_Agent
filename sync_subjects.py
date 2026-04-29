import json
import os
import time
import requests
from requests.exceptions import RequestException
from dotenv import load_dotenv
from db import get_db_connection
from constants import BINS

load_dotenv()


def get_api_headers():
    token = os.getenv("GOSZAKUP_TOKEN")
    return {
        "Authorization": token,
        "Content-Type": "application/json"
    }


def graphql_post(query, variables, max_retries=4, timeout=60):
    url = os.getenv("GOSZAKUP_URL")
    delay = 2
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, json={"query": query, "variables": variables}, headers=get_api_headers(), timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            if "errors" in payload:
                raise RuntimeError(payload["errors"])
            return payload
        except (RequestException, RuntimeError) as exc:
            last_error = exc
            if attempt == max_retries:
                raise
            print(f"[SUBJECT] Ошибка запроса ({attempt}/{max_retries}): {exc}. Повтор через {delay}s...")
            time.sleep(delay)
            delay = min(delay * 2, 20)
    raise last_error


def fetch_subject_by_bin(bin_code):
    query = """
    query($bin: String) {
      Subjects(filter: {bin: $bin}, limit: 1) {
        pid
        bin
        iin
        inn
        unp
        regdate
        crdate
        indexDate
        numberReg
        series
        name
        nameRu
        nameKz
        fullName
        fullNameRu
        fullNameKz
        email
        phone
        website
        lastUpdateDate
        countryCode
        katoList
        customer
        organizer
        supplier
        typeSupplier
        Address {
          address
          katoCode
        }
      }
    }
    """

    payload = graphql_post(query, {"bin": bin_code})
    subjects = payload.get("data", {}).get("Subjects")
    return subjects[0] if subjects else None


def save_subject(subject):
    conn = get_db_connection()
    cur = conn.cursor()
    bin_code = subject.get("bin")
    address = None
    kato_code = None

    if subject.get("Address"):
        address = subject["Address"][0].get("address") if subject["Address"] else None
        kato_code = subject["Address"][0].get("katoCode") if subject["Address"] else None

    cur.execute(
        """
        INSERT INTO subjects (
            bin,
            pid,
            iin,
            inn,
            unp,
            name,
            name_ru,
            name_kz,
            full_name,
            full_name_ru,
            full_name_kz,
            email,
            phone,
            website,
            customer,
            organizer,
            supplier,
            type_supplier,
            country_code,
            kato_list,
            last_update_date,
            address,
            kato_code,
            raw_payload
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (bin) DO UPDATE
          SET pid = EXCLUDED.pid,
              iin = EXCLUDED.iin,
              inn = EXCLUDED.inn,
              unp = EXCLUDED.unp,
              name = EXCLUDED.name,
              name_ru = EXCLUDED.name_ru,
              name_kz = EXCLUDED.name_kz,
              full_name = EXCLUDED.full_name,
              full_name_ru = EXCLUDED.full_name_ru,
              full_name_kz = EXCLUDED.full_name_kz,
              email = EXCLUDED.email,
              phone = EXCLUDED.phone,
              website = EXCLUDED.website,
              customer = EXCLUDED.customer,
              organizer = EXCLUDED.organizer,
              supplier = EXCLUDED.supplier,
              type_supplier = EXCLUDED.type_supplier,
              country_code = EXCLUDED.country_code,
              kato_list = EXCLUDED.kato_list,
              last_update_date = EXCLUDED.last_update_date,
              address = EXCLUDED.address,
              kato_code = EXCLUDED.kato_code,
              raw_payload = EXCLUDED.raw_payload;
        """,
        (
            bin_code,
            subject.get("pid"),
            subject.get("iin"),
            subject.get("inn"),
            subject.get("unp"),
            subject.get("name"),
            subject.get("nameRu"),
            subject.get("nameKz"),
            subject.get("fullName"),
            subject.get("fullNameRu"),
            subject.get("fullNameKz"),
            subject.get("email"),
            subject.get("phone"),
            subject.get("website"),
            bool(subject.get("customer")),
            bool(subject.get("organizer")),
            bool(subject.get("supplier")),
            subject.get("typeSupplier"),
            subject.get("countryCode"),
            ",".join(subject.get("katoList") or []),
            subject.get("lastUpdateDate"),
            address,
            kato_code,
            json.dumps(subject, ensure_ascii=False)
        )
    )

    cur.execute(
        """
        INSERT INTO organizations (bin, is_customer, is_supplier, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (bin) DO UPDATE
          SET is_customer = EXCLUDED.is_customer,
              is_supplier = EXCLUDED.is_supplier,
              updated_at = EXCLUDED.updated_at
        """,
        (bin_code, bool(subject.get("customer")), bool(subject.get("supplier")))
    )

    conn.commit()
    cur.close()
    conn.close()
    return 1


def sync_subjects():
    total_saved = 0
    for bin_code in BINS:
        print(f"[SUBJECT] Обработка BIN={bin_code}")
        try:
            subject = fetch_subject_by_bin(bin_code)
            if subject is None:
                print(f"[SUBJECT] BIN={bin_code}: субъект не найден")
                continue
            save_subject(subject)
            total_saved += 1
            print(f"[SUBJECT] BIN={bin_code}: сохранён субъект")
        except Exception as exc:
            print(f"[SUBJECT] Ошибка BIN={bin_code}: {exc}")
            print("[SUBJECT] Пропускаем BIN и продолжаем.")
    print(f"[SUBJECT] Всего субъектов сохранено: {total_saved}")
    return total_saved


if __name__ == "__main__":
    sync_subjects()
