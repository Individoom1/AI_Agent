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
            print(f"[ANN] Ошибка запроса ({attempt}/{max_retries}): {exc}. Повтор через {delay}s...")
            time.sleep(delay)
            delay = min(delay * 2, 20)
    raise last_error


def fetch_announcements_by_bin(bin_code, limit=200, after=None, last_update_after=None, start_date=None, max_retries=5):
    variables = {
        "bin": bin_code,
        "limit": limit
    }
    args = ["$bin: String", "$limit: Int"]
    filter_args = ["orgBin: $bin"]
    
    if last_update_after:
        args.append("$lastUpdateDate: String")
        filter_args.append("lastUpdateDate: $lastUpdateDate")
        variables["lastUpdateDate"] = last_update_after
    after_arg = ""

    if after is not None:
        args.append("$after: Int")
        after_arg = ", after: $after"
        variables["after"] = after

    args_string = ', '.join(args)

    query = f"""
    query({args_string}) {{
      TrdBuy(filter: {{{', '.join(filter_args)}}}, limit: $limit{after_arg}) {{
        id
        numberAnno
        nameRu
        nameKz
        totalSum
        countLots
        refTradeMethodsId
        refSubjectTypeId
        customerBin
        customerPid
        customerNameKz
        customerNameRu
        orgBin
        orgPid
        orgNameKz
        orgNameRu
        refBuyStatusId
        startDate
        repeatStartDate
        repeatEndDate
        endDate
        publishDate
        itogiDatePublic
        refTypeTradeId
        disablePersonId
        discusStartDate
        discusEndDate
        idSupplier
        biinSupplier
        parentId
        singlOrgSign
        isLightIndustry
        isConstructionWork
        refSpecPurchaseTypeId
        lastUpdateDate
        finYear
        kato
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
            return data.get("data", {}).get("TrdBuy", [])
        except (RequestException, RuntimeError) as exc:
            last_error = exc
            if attempt == max_retries:
                raise
            print(f"[ANN] Ошибка запроса ({attempt}/{max_retries}): {exc}. Повтор через {retry_delay}s...")
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)
    raise last_error


def fetch_all_announcements_for_bin(bin_code, batch_size=200, last_update_after=None, start_date=None):
    all_announcements = []
    after = None

    while True:
        batch = fetch_announcements_by_bin(bin_code, limit=batch_size, after=after, last_update_after=last_update_after, start_date=start_date)

        if not batch:
            break

        all_announcements.extend(batch)

        if len(batch) < batch_size:
            break

        after = batch[-1].get("id")
        if after is None:
            break

    return all_announcements


def save_announcements(announcements):
    conn = get_db_connection()
    cur = conn.cursor()
    saved = 0
    for ann in announcements:
        try:
            cur.execute(
                """
                INSERT INTO announcements (
                    id, numberAnno, nameRu, nameKz, totalSum, countLots, refTradeMethodsId, refSubjectTypeId,
                    customerBin, customerPid, customerNameKz, customerNameRu, orgBin, orgPid, orgNameKz, orgNameRu,
                    refBuyStatusId, startDate, repeatStartDate, repeatEndDate, endDate, publishDate, itogiDatePublic,
                    refTypeTradeId, disablePersonId, discusStartDate, discusEndDate, idSupplier, biinSupplier, parentId,
                    singlOrgSign, isLightIndustry, isConstructionWork, refSpecPurchaseTypeId, lastUpdateDate, finYear,
                    kato, systemId, indexDate, raw_payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                  SET numberAnno = EXCLUDED.numberAnno,
                      nameRu = EXCLUDED.nameRu,
                      nameKz = EXCLUDED.nameKz,
                      totalSum = EXCLUDED.totalSum,
                      countLots = EXCLUDED.countLots,
                      refTradeMethodsId = EXCLUDED.refTradeMethodsId,
                      refSubjectTypeId = EXCLUDED.refSubjectTypeId,
                      customerBin = EXCLUDED.customerBin,
                      customerPid = EXCLUDED.customerPid,
                      customerNameKz = EXCLUDED.customerNameKz,
                      customerNameRu = EXCLUDED.customerNameRu,
                      orgBin = EXCLUDED.orgBin,
                      orgPid = EXCLUDED.orgPid,
                      orgNameKz = EXCLUDED.orgNameKz,
                      orgNameRu = EXCLUDED.orgNameRu,
                      refBuyStatusId = EXCLUDED.refBuyStatusId,
                      startDate = EXCLUDED.startDate,
                      repeatStartDate = EXCLUDED.repeatStartDate,
                      repeatEndDate = EXCLUDED.repeatEndDate,
                      endDate = EXCLUDED.endDate,
                      publishDate = EXCLUDED.publishDate,
                      itogiDatePublic = EXCLUDED.itogiDatePublic,
                      refTypeTradeId = EXCLUDED.refTypeTradeId,
                      disablePersonId = EXCLUDED.disablePersonId,
                      discusStartDate = EXCLUDED.discusStartDate,
                      discusEndDate = EXCLUDED.discusEndDate,
                      idSupplier = EXCLUDED.idSupplier,
                      biinSupplier = EXCLUDED.biinSupplier,
                      parentId = EXCLUDED.parentId,
                      singlOrgSign = EXCLUDED.singlOrgSign,
                      isLightIndustry = EXCLUDED.isLightIndustry,
                      isConstructionWork = EXCLUDED.isConstructionWork,
                      refSpecPurchaseTypeId = EXCLUDED.refSpecPurchaseTypeId,
                      lastUpdateDate = EXCLUDED.lastUpdateDate,
                      finYear = EXCLUDED.finYear,
                      kato = EXCLUDED.kato,
                      systemId = EXCLUDED.systemId,
                      indexDate = EXCLUDED.indexDate,
                      raw_payload = EXCLUDED.raw_payload;
                """,
                (
                    ann.get("id"),
                    ann.get("numberAnno"),
                    ann.get("nameRu"),
                    ann.get("nameKz"),
                    ann.get("totalSum"),
                    ann.get("countLots"),
                    ann.get("refTradeMethodsId"),
                    ann.get("refSubjectTypeId"),
                    ann.get("customerBin"),
                    ann.get("customerPid"),
                    ann.get("customerNameKz"),
                    ann.get("customerNameRu"),
                    ann.get("orgBin"),
                    ann.get("orgPid"),
                    ann.get("orgNameKz"),
                    ann.get("orgNameRu"),
                    ann.get("refBuyStatusId"),
                    ann.get("startDate"),
                    ann.get("repeatStartDate"),
                    ann.get("repeatEndDate"),
                    ann.get("endDate"),
                    ann.get("publishDate"),
                    ann.get("itogiDatePublic"),
                    ann.get("refTypeTradeId"),
                    ann.get("disablePersonId"),
                    ann.get("discusStartDate"),
                    ann.get("discusEndDate"),
                    ann.get("idSupplier"),
                    ann.get("biinSupplier"),
                    ann.get("parentId"),
                    ann.get("singlOrgSign"),
                    ann.get("isLightIndustry"),
                    ann.get("isConstructionWork"),
                    ann.get("refSpecPurchaseTypeId"),
                    ann.get("lastUpdateDate"),
                    ann.get("finYear"),
                    ann.get("kato"),
                    ann.get("systemId"),
                    ann.get("indexDate"),
                    json.dumps(ann, ensure_ascii=False)
                )
            )
            saved += 1
        except Exception:
            continue
    conn.commit()
    cur.close()
    conn.close()
    return saved


def sync_announcements(last_update_after=None, start_date=None):
    total_saved = 0
    for bin_code in BINS:
        print(f"[ANN] Получение объявлений для BIN={bin_code}")
        try:
            announcements = fetch_all_announcements_for_bin(bin_code, start_date=start_date)
            count_saved = save_announcements(announcements)
            total_saved += count_saved
            print(f"[ANN] BIN={bin_code}: найдено {len(announcements)}, сохранено {count_saved}")
        except Exception as exc:
            print(f"[ANN] Ошибка при синхронизации BIN={bin_code}: {exc}")
            print("[ANN] Пропускаем этот BIN и продолжаем дальше.")
    print(f"[ANN] Общее количество сохраненных объявлений: {total_saved}")
    return total_saved


if __name__ == "__main__":
    sync_announcements()