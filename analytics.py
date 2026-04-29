import psycopg2
import json
import os
from dotenv import load_dotenv
from typing import List, Dict, Any
import numpy as np
from scipy import stats

load_dotenv()

def validate_env_vars():
    """Валидация обязательных переменных окружения"""
    required_vars = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        raise ValueError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")

validate_env_vars()

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def get_lots_with_enstru(enstru_codes: List[int] = None, region: str = None, year: int = None) -> List[Dict]:
    """Получить лоты с фильтрами по ЕНСТРУ, региону, году"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = """
    SELECT l.id, l.amount, l.nameRu, l.descriptionRu, l.customerBin, l.trdBuyId,
           l.enstruList, l.plnPointKatoList, l.lastUpdateDate,
           a.nameRu as announcement_name, a.publishDate
    FROM lots l
    LEFT JOIN announcements a ON l.trdBuyId = a.id
    WHERE 1=1
    """
    
    params = []
    if enstru_codes:
        query += " AND l.enstruList && %s"
        params.append([int(code) for code in enstru_codes])
        
    if region:
        query += " AND l.plnPointKatoList @> %s"
        params.append([region])
        
    if year:
        query += " AND EXTRACT(YEAR FROM a.publishDate) = %s"
        params.append(year)
        
    query += " ORDER BY l.amount DESC"
    
    cur.execute(query, params)
    rows = cur.fetchall()
    
    lots = []
    for row in rows:
        lots.append({
            'id': row[0],
            'amount': row[1],
            'name': row[2],
            'description': row[3],
            'customer_bin': row[4],
            'announcement_id': row[5],
            'enstru_codes': row[6],
            'kato_codes': row[7],
            'last_update': row[8],
            'announcement_name': row[9],
            'publish_date': row[10]
        })
    
    conn.close()
    return lots

def calculate_fair_price(lots: List[Dict], target_enstru: int, region: str = None, target_year: int = None) -> Dict:
    """Рассчитать Fair Price для ЕНСТРУ с учетом региона и времени"""
    target_enstru = int(target_enstru)
    relevant_lots = [lot for lot in lots if target_enstru in (lot.get('enstru_codes') or [])]
    
    if not relevant_lots:
        return {'error': 'Нет данных для данного ЕНСТРУ'}
    
    if region:
        relevant_lots = [lot for lot in relevant_lots if region in (lot.get('kato_codes') or [])]
        if not relevant_lots:
            return {'error': f'Нет данных для ЕНСТРУ {target_enstru} в регионе {region}'}
    
    if target_year:
        relevant_lots = [lot for lot in relevant_lots if lot.get('publish_date') and lot['publish_date'].year == target_year]
        if not relevant_lots:
            return {'error': f'Нет данных для ЕНСТРУ {target_enstru} за {target_year} год'}
    
    amounts = [float(lot['amount']) for lot in relevant_lots if lot['amount'] and lot['amount'] >= 1000]
    
    if len(amounts) < 3:
        return {'error': f'Недостаточно данных для статистики ({len(amounts)} лотов)'}
    
    median_price = float(np.median(amounts))
    mean_price = float(np.mean(amounts))
    q25, q75 = float(np.percentile(amounts, 25)), float(np.percentile(amounts, 75))
    iqr = q75 - q25
    
    lower_bound = q25 - 1.5 * iqr
    upper_bound = q75 + 1.5 * iqr
    
    normal_amounts = [a for a in amounts if lower_bound <= a <= upper_bound]
    outlier_amounts = [a for a in amounts if a < lower_bound or a > upper_bound]
    
    regional_multiplier = 1.0
    if region:
        if region.startswith('19'):
            regional_multiplier = 1.15
        elif region.startswith('75'):
            regional_multiplier = 1.10
        else:
            regional_multiplier = 0.95
    
    time_multiplier = 1.0
    if target_year:
        current_year = 2024
        years_diff = current_year - target_year
        if years_diff > 0:
            inflation_rate = 0.08
            time_multiplier = (1 + inflation_rate) ** years_diff
    
    seasonal_multiplier = 1.0
    if target_year and region:
        summer_months = [6, 7, 8]
        winter_months = [12, 1, 2]
        
        lot_dates = [lot['publish_date'] for lot in relevant_lots if lot.get('publish_date')]
        if lot_dates:
            avg_month = np.mean([d.month for d in lot_dates])
            if avg_month in summer_months:
                seasonal_multiplier = 1.10
            elif avg_month in winter_months:
                seasonal_multiplier = 0.95
    
    base_median = median_price
    adjusted_median = base_median * regional_multiplier * time_multiplier * seasonal_multiplier
    
    lot_distances = [(lot, abs(float(lot['amount']) - base_median)) for lot in relevant_lots]
    lot_distances.sort(key=lambda x: x[1])
    top_k_lots = [{'id': lot['id'], 'amount': float(lot['amount']), 'distance_from_median': dist} 
                  for lot, dist in lot_distances[:5]]
    
    return {
        'enstru_code': target_enstru,
        'region': region,
        'year': target_year,
        'total_lots': len(amounts),
        'normal_lots': len(normal_amounts),
        'outlier_lots': len(outlier_amounts),
        'base_median_price': base_median,
        'adjusted_median_price': adjusted_median,
        'mean_price': mean_price,
        'q25': q25,
        'q75': q75,
        'iqr': iqr,
        'regional_multiplier': regional_multiplier,
        'time_multiplier': time_multiplier,
        'seasonal_multiplier': seasonal_multiplier,
        'price_range': [min(amounts), max(amounts)],
        'outliers': outlier_amounts,
        'confidence': len(normal_amounts) / len(amounts) if amounts else 0,
        'top_k_lots': top_k_lots
    }

def detect_anomalies(lots: List[Dict], threshold_percent: float = 30.0) -> List[Dict]:
    """Найти аномалии цен с использованием статистических методов (IQR и Z-score)"""
    if not lots:
        return []
    
    amounts = [float(lot['amount']) for lot in lots if lot['amount'] and lot['amount'] >= 1000]
    if len(amounts) < 3:
        return []
    
    median_price = np.median(amounts)
    mean_price = np.mean(amounts)
    std_price = np.std(amounts)
    
    q25, q75 = np.percentile(amounts, [25, 75])
    iqr = q75 - q25
    lower_bound = q25 - 1.5 * iqr
    upper_bound = q75 + 1.5 * iqr
    
    anomalies = []
    for lot in lots:
        if not lot['amount']:
            continue
        
        price = float(lot['amount'])
        
        percent_deviation = abs(price - median_price) / median_price * 100
        
        z_score = abs((price - mean_price) / std_price) if std_price > 0 else 0
        
        iqr_anomaly = price < lower_bound or price > upper_bound
        
        # Аномалия = выходит за пределы Tukey fences ИЛИ очень высокий Z-score (>3)
        is_anomaly = iqr_anomaly or (z_score > 3)
        
        if is_anomaly:
            anomalies.append({
                'lot_id': lot['id'],
                'amount': price,
                'median_price': median_price,
                'mean_price': mean_price,
                'deviation_percent': percent_deviation,
                'z_score': z_score,
                'anomaly_type': 'outlier' if iqr_anomaly else ('high_deviation' if percent_deviation > threshold_percent else 'statistical'),
                'name': lot['name'],
                'customer_bin': lot['customer_bin'],
                'announcement_id': lot.get('announcement_id')
            })
    
    return sorted(anomalies, key=lambda x: abs(x['z_score']), reverse=True)

def get_quantity_anomalies(year: int) -> List[Dict]:
    """Найти аномалии по количеству ТРУ по сравнению с предыдущими годами"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = """
    WITH yearly_stats AS (
        SELECT
            EXTRACT(YEAR FROM a.publishDate) as year,
            COUNT(l.id) as total_lots,
            AVG(l.amount) as avg_amount,
            SUM(l.amount) as total_amount
        FROM lots l
        JOIN announcements a ON l.trdBuyId = a.id
        WHERE EXTRACT(YEAR FROM a.publishDate) BETWEEN %s - 3 AND %s
        GROUP BY EXTRACT(YEAR FROM a.publishDate)
        ORDER BY year
    )
    SELECT * FROM yearly_stats
    """
    
    cur.execute(query, (year, year))
    rows = cur.fetchall()
    
    if len(rows) < 2:
        conn.close()
        return []
    
    years = [float(row[0]) for row in rows]
    counts = [int(row[1]) for row in rows]
    
    if len(counts) >= 3:
        slope, intercept = np.polyfit(years, counts, 1)
        predicted = slope * year + intercept
        actual = counts[-1] if years[-1] == year else 0
        
        deviation = abs(actual - predicted) / predicted * 100 if predicted > 0 else 0
        
        if deviation > 50:
            result = {
                'year': year,
                'actual_count': actual,
                'predicted_count': predicted,
                'deviation_percent': deviation,
                'trend': 'увеличение' if slope > 0 else 'уменьшение',
                'historical_data': [{'year': int(y), 'count': int(c)} for y, c in zip(years, counts)]
            }
        else:
            result = None
    else:
        result = None
    
    conn.close()
    return [result] if result else []

def format_fair_price_response(query_amount: float, fair_price_data: Dict, sample_size: int) -> str:
    """Форматировать ответ по Fair Price в требуемой структуре"""
    if 'error' in fair_price_data:
        return f"Недостаточно данных для оценки справедливой цены. {fair_price_data['error']}"
    
    fp = fair_price_data
    
    adjusted_median = fp.get('adjusted_median_price', fp.get('base_median_price', 0))
    base_median = fp.get('base_median_price', 0)
    
    if abs(query_amount - adjusted_median) / adjusted_median < 0.1:
        verdict = f"Цена {query_amount:,.0f} тенге соответствует рыночным значениям для данного типа работ."
    elif query_amount > adjusted_median:
        deviation = (query_amount - adjusted_median) / adjusted_median * 100
        verdict = f"Цена {query_amount:,.0f} тенге на {deviation:.1f}% выше скорректированной медианной цены."
    else:
        deviation = (adjusted_median - query_amount) / adjusted_median * 100
        verdict = f"Цена {query_amount:,.0f} тенге на {deviation:.1f}% ниже скорректированной медианной цены."
    
    region_info = f", Регион: {fp.get('region', 'все регионы')}" if fp.get('region') else ""
    year_info = f", Год: {fp.get('year', 'все года')}" if fp.get('year') else ""
    search_params = f"ЕНСТРУ код: {fp['enstru_code']}{region_info}{year_info}, Выборка: {sample_size} лотов"
    
    analytics = f"""Базовая медианная цена: {base_median:,.0f} тенге
Скорректированная медианная цена: {adjusted_median:,.0f} тенге
Средняя цена: {fp['mean_price']:,.0f} тенге
25-й перцентиль: {fp['q25']:,.0f} тенге
75-й перцентиль: {fp['q75']:,.0f} тенге
IQR: {fp['iqr']:,.0f} тенге
Диапазон цен: {fp['price_range'][0]:,.0f} - {fp['price_range'][1]:,.0f} тенге"""
    
    corrections = ""
    if fp.get('regional_multiplier', 1.0) != 1.0:
        corrections += f"Региональный коэффициент: {fp['regional_multiplier']:.2f}\n"
    if fp.get('time_multiplier', 1.0) != 1.0:
        corrections += f"Временная корректировка: {fp['time_multiplier']:.2f}\n"
    if fp.get('seasonal_multiplier', 1.0) != 1.0:
        corrections += f"Сезонная корректировка: {fp['seasonal_multiplier']:.2f}\n"
    
    if corrections:
        analytics += f"\nКорректировки:\n{corrections.strip()}"
    
    top_k_info = ""
    if fp.get('top_k_lots'):
        top_k_info = "\n\nТоп-5 лотов ближайших к медиане (для объяснимости):"
        for i, lot in enumerate(fp['top_k_lots'], 1):
            top_k_info += f"\n{i}. Лот ID {lot['id']}: {lot['amount']:,.0f} тенге (отклонение: {lot['distance_from_median']:,.0f})"
    
    metric = f"Метод: статистический анализ с корректировками (медиана, IQR, регион, время, сезонность), Выбросы: {fp['outlier_lots']} из {fp['total_lots']} лотов"
    
    confidence = f"Уверенность: {fp['confidence']:.1%} (на основе нормальных значений), Риски: малый размер выборки, упрощённые модели корректировок"
    
    return f"""1. Краткий вывод: {verdict}

2. Использованные данные: {search_params}

3. Сравнение: {analytics}

4. Метрика оценки: {metric}

5. Ограничения и уверенность: {confidence}{top_k_info}"""

if __name__ == "__main__":
    lots = get_lots_with_enstru([12345], year=2023)
    if lots:
        fair_price = calculate_fair_price(lots, 12345)
        print("Fair Price Analysis:")
        print(json.dumps(fair_price, indent=2, ensure_ascii=False))
        
        anomalies = detect_anomalies(lots, 30.0)
        print(f"\nНайдено аномалий: {len(anomalies)}")
        for anomaly in anomalies[:5]:
            print(f"Лот {anomaly['lot_id']}: {anomaly['amount']:,.0f} тенге (+{anomaly['deviation_percent']:.1f}%)")
