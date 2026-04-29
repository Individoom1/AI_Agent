import os
import json
import time
import requests
from requests.exceptions import RequestException
from db import get_db_connection
from dotenv import load_dotenv
from constants import BINS

load_dotenv()


def get_api_headers():
    token = os.getenv("GOSZAKUP_TOKEN")
    return {
        "Authorization": token,
        "Content-Type": "application/json"
    }


def fetch_contracts_by_bin(bin_code, limit=200, after=None, last_update_after=None, start_date=None, max_retries=5):
    url = os.getenv("GOSZAKUP_URL")

    variables = {
        "bin": bin_code,
        "limit": limit
    }
    args = ["$bin: String", "$limit: Int"]
    filter_args = ["customerBin: $bin"]
    after_arg = ""

    if after is not None:
        args.append("$after: Int")
        after_arg = ", after: $after"
        variables["after"] = after

    if last_update_after:
        args.append("$lastUpdateDate: String")
        filter_args.append("lastUpdateDate: $lastUpdateDate")
        variables["lastUpdateDate"] = last_update_after

    args_string = ', '.join(args)

    query = f"""
    query({args_string}) {{
      Contract(filter: {{{', '.join(filter_args)}}}, limit: $limit{after_arg}) {{
        id
        contractNumber
        contractNumberSys
        customerBin
        supplierBiin
        contractSum
        contractSumWnds
        signDate
        crdate
        lastUpdateDate
        descriptionRu
        faktTradeMethodsId
        refContractStatusId
        finYear
      }}
    }}
    """

    retry_delay = 3
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, json={"query": query, "variables": variables}, headers=get_api_headers(), timeout=60)
            response.raise_for_status()
            data = response.json()
            if "errors" in data:
                raise RuntimeError(data["errors"])
            return data.get("data", {}).get("Contract", [])
        except (RequestException, RuntimeError) as exc:
            last_error = exc
            if attempt == max_retries:
                raise
            print(f"[SYNC] Ошибка запроса ({attempt}/{max_retries}): {exc}. Повтор через {retry_delay}s...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)
    raise last_error


def fetch_all_contracts_for_bin(bin_code, batch_size=200, last_update_after=None, start_date=None):
    all_contracts = []
    after = None

    while True:
        batch = fetch_contracts_by_bin(bin_code, limit=batch_size, after=after, last_update_after=last_update_after, start_date=start_date)

        if not batch:
            break

        all_contracts.extend(batch)

        if len(batch) < batch_size:
            break

        after = batch[-1].get("id")
        if after is None:
            break

    return all_contracts


def save_contracts(contracts):
    conn = get_db_connection()
    cur = conn.cursor()
    saved = 0
    for contract in contracts:
        try:
            cur.execute(
                """
                INSERT INTO contracts (
                    contract_id_sys,
                    customer_bin,
                    supplier_bin,
                    contract_sum,
                    sign_date,
                    description,
                    trade_method_id,
                    status_id,
                    fin_year,
                    raw_payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (contract_id_sys) DO UPDATE
                  SET customer_bin = EXCLUDED.customer_bin,
                      supplier_bin = EXCLUDED.supplier_bin,
                      contract_sum = EXCLUDED.contract_sum,
                      sign_date = EXCLUDED.sign_date,
                      description = EXCLUDED.description,
                      trade_method_id = EXCLUDED.trade_method_id,
                      status_id = EXCLUDED.status_id,
                      fin_year = EXCLUDED.fin_year,
                      raw_payload = EXCLUDED.raw_payload;
                """,
                (
                    contract.get("contractNumberSys"),
                    contract.get("customerBin"),
                    contract.get("supplierBiin"),
                    contract.get("contractSumWnds"),
                    contract.get("signDate"),
                    contract.get("descriptionRu"),
                    contract.get("faktTradeMethodsId"),
                    contract.get("refContractStatusId"),
                    contract.get("finYear"),
                    json.dumps(contract, ensure_ascii=False)
                )
            )
            saved += 1
        except Exception:
            continue
    conn.commit()
    cur.close()
    conn.close()
    return saved


def sync_contracts(last_update_after=None, start_date=None):
    total_saved = 0
    for bin_code in BINS:
        print(f"[SYNC] Получение договоров для BIN={bin_code}")
        try:
            contracts = fetch_all_contracts_for_bin(bin_code, last_update_after=last_update_after, start_date=start_date)
            count_saved = save_contracts(contracts)
            total_saved += count_saved
            print(f"[SYNC] BIN={bin_code}: найдено {len(contracts)}, сохранено {count_saved}")
        except Exception as exc:
            print(f"[SYNC] Ошибка при синхронизации BIN={bin_code}: {exc}")
            print("[SYNC] Пропускаем этот BIN и продолжаем дальше.")
    print(f"[SYNC] Общее количество сохраненных контрактов: {total_saved}")
    return total_saved


if __name__ == "__main__":
    sync_contracts()
