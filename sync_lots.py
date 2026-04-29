import json
import os
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
            print(f"[LOTS] Ошибка запроса ({attempt}/{max_retries}): {exc}. Повтор через {delay}s...")
            time.sleep(delay)
            delay = min(delay * 2, 20)
    raise last_error


def fetch_lots_by_bin(bin_code, limit=200, after=None, last_update_after=None, start_date=None, max_retries=5):
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
      Lots(filter: {{{', '.join(filter_args)}}}, limit: $limit{after_arg}) {{
        id
        lotNumber
        refLotStatusId
        lastUpdateDate
        unionLots
        count
        amount
        nameRu
        nameKz
        descriptionRu
        descriptionKz
        customerId
        customerBin
        customerNameRu
        customerNameKz
        trdBuyNumberAnno
        trdBuyId
        dumping
        refTradeMethodsId
        refBuyTradeMethodsId
        psdSign
        consultingServices
        pointList
        enstruList
        plnPointKatoList
        singlOrgSign
        isLightIndustry
        isConstructionWork
        disablePersonId
        isDeleted
        systemId
        indexDate
      }}
    }}
    """

    retry_delay = 3
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(os.getenv("GOSZAKUP_URL"), json={"query": query, "variables": variables}, headers=get_api_headers(), timeout=60)
            response.raise_for_status()
            data = response.json()
            if "errors" in data:
                raise RuntimeError(data["errors"])
            return data.get("data", {}).get("Lots", [])
        except (RequestException, RuntimeError) as exc:
            last_error = exc
            if attempt == max_retries:
                raise
            print(f"[LOTS] Ошибка запроса ({attempt}/{max_retries}): {exc}. Повтор через {retry_delay}s...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)
    raise last_error


def fetch_all_lots_for_bin(bin_code, batch_size=200, last_update_after=None, start_date=None):
    all_lots = []
    after = None

    while True:
        batch = fetch_lots_by_bin(bin_code, limit=batch_size, after=after, last_update_after=last_update_after, start_date=start_date)

        if not batch:
            break

        all_lots.extend(batch)

        if len(batch) < batch_size:
            break

        after = batch[-1].get("id")
        if after is None:
            break

    return all_lots


def save_lots(lots):
    conn = get_db_connection()
    cur = conn.cursor()
    saved = 0
    for lot in lots:
        try:
            cur.execute(
                """
                INSERT INTO lots (
                    id, lotNumber, refLotStatusId, lastUpdateDate, unionLots, count, amount,
                    nameRu, nameKz, descriptionRu, descriptionKz, customerId, customerBin,
                    customerNameRu, customerNameKz, trdBuyNumberAnno, trdBuyId, dumping,
                    refTradeMethodsId, refBuyTradeMethodsId, psdSign, consultingServices,
                    pointList, enstruList, plnPointKatoList, singlOrgSign, isLightIndustry,
                    isConstructionWork, disablePersonId, isDeleted, systemId, indexDate, raw_payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                  SET lotNumber = EXCLUDED.lotNumber,
                      refLotStatusId = EXCLUDED.refLotStatusId,
                      lastUpdateDate = EXCLUDED.lastUpdateDate,
                      unionLots = EXCLUDED.unionLots,
                      count = EXCLUDED.count,
                      amount = EXCLUDED.amount,
                      nameRu = EXCLUDED.nameRu,
                      nameKz = EXCLUDED.nameKz,
                      descriptionRu = EXCLUDED.descriptionRu,
                      descriptionKz = EXCLUDED.descriptionKz,
                      customerId = EXCLUDED.customerId,
                      customerBin = EXCLUDED.customerBin,
                      customerNameRu = EXCLUDED.customerNameRu,
                      customerNameKz = EXCLUDED.customerNameKz,
                      trdBuyNumberAnno = EXCLUDED.trdBuyNumberAnno,
                      trdBuyId = EXCLUDED.trdBuyId,
                      dumping = EXCLUDED.dumping,
                      refTradeMethodsId = EXCLUDED.refTradeMethodsId,
                      refBuyTradeMethodsId = EXCLUDED.refBuyTradeMethodsId,
                      psdSign = EXCLUDED.psdSign,
                      consultingServices = EXCLUDED.consultingServices,
                      pointList = EXCLUDED.pointList,
                      enstruList = EXCLUDED.enstruList,
                      plnPointKatoList = EXCLUDED.plnPointKatoList,
                      singlOrgSign = EXCLUDED.singlOrgSign,
                      isLightIndustry = EXCLUDED.isLightIndustry,
                      isConstructionWork = EXCLUDED.isConstructionWork,
                      disablePersonId = EXCLUDED.disablePersonId,
                      isDeleted = EXCLUDED.isDeleted,
                      systemId = EXCLUDED.systemId,
                      indexDate = EXCLUDED.indexDate,
                      raw_payload = EXCLUDED.raw_payload;
                """,
                (
                    lot.get("id"),
                    lot.get("lotNumber"),
                    lot.get("refLotStatusId"),
                    lot.get("lastUpdateDate"),
                    lot.get("unionLots"),
                    lot.get("count"),
                    lot.get("amount"),
                    lot.get("nameRu"),
                    lot.get("nameKz"),
                    lot.get("descriptionRu"),
                    lot.get("descriptionKz"),
                    lot.get("customerId"),
                    lot.get("customerBin"),
                    lot.get("customerNameRu"),
                    lot.get("customerNameKz"),
                    lot.get("trdBuyNumberAnno"),
                    lot.get("trdBuyId"),
                    lot.get("dumping"),
                    lot.get("refTradeMethodsId"),
                    lot.get("refBuyTradeMethodsId"),
                    lot.get("psdSign"),
                    lot.get("consultingServices"),
                    lot.get("pointList"),
                    lot.get("enstruList"),
                    lot.get("plnPointKatoList"),
                    lot.get("singlOrgSign"),
                    lot.get("isLightIndustry"),
                    lot.get("isConstructionWork"),
                    lot.get("disablePersonId"),
                    lot.get("isDeleted"),
                    lot.get("systemId"),
                    lot.get("indexDate"),
                    json.dumps(lot, ensure_ascii=False)
                )
            )
            saved += 1
        except Exception:
            continue
    conn.commit()
    cur.close()
    conn.close()
    return saved


def sync_lots(last_update_after=None, start_date=None):
    total_saved = 0
    for bin_code in BINS:
        try:
            print(f"[LOTS] Получение лотов для BIN={bin_code}")
            lots = fetch_all_lots_for_bin(bin_code, last_update_after=last_update_after, start_date=start_date)
            saved = save_lots(lots)
            print(f"[LOTS] BIN={bin_code}: найдено {len(lots)}, сохранено {saved}")
            total_saved += saved
        except Exception as e:
            print(f"[LOTS] Ошибка при синхронизации BIN={bin_code}: {e}")
            print(f"[LOTS] Пропускаем этот BIN и продолжаем дальше.")
    print(f"[LOTS] Всего сохранено {total_saved} лотов")
    return total_saved


if __name__ == "__main__":
    sync_lots()
