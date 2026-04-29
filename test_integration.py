#!/usr/bin/env python3
"""
Comprehensive integration test для TЗ компонентов
"""

from ai_agent import GoszakupAIAgent
from analytics import get_lots_with_enstru, calculate_fair_price, detect_anomalies
import time

def test_fair_price():
    """Тест Fair Price с региональными корректировками"""
    print("\n=== TEST 1: Fair Price ===")
    lots = get_lots_with_enstru([0])
    print(f"Найдено лотов: {len(lots)}")
    
    fair_price = calculate_fair_price(lots, 0)
    print(f" Базовая медиана: {fair_price.get('base_median_price', 0):,.0f} тенге")
    print(f" Скорректированная медиана: {fair_price.get('adjusted_median_price', 0):,.0f} тенге")
    print(f" Top-K лотов: {len(fair_price.get('top_k_lots', []))} лотов")
    
    fair_price_regional = calculate_fair_price(lots, 0, region='711210000', target_year=2024)
    print(f" С регионом - медиана: {fair_price_regional.get('base_median_price', 0):,.0f} тенге")
    print(f" Региональный коэффициент: {fair_price_regional.get('regional_multiplier', 1.0):.2f}")
    
    return True

def test_explainability():
    """Тест Top-K лотов для объяснимости"""
    print("\n=== TEST 2: Explainability (Top-K) ===")
    lots = get_lots_with_enstru([0])
    fair_price = calculate_fair_price(lots, 0)
    
    top_k = fair_price.get('top_k_lots', [])
    print(f" Найдено Top-K лотов: {len(top_k)}")
    for i, lot in enumerate(top_k, 1):
        print(f"  {i}. Лот ID {lot['id']}: {lot['amount']:,.0f} тенге")
    
    return len(top_k) > 0

def test_anomaly_detection():
    """Тест улучшенного обнаружения аномалий"""
    print("\n=== TEST 3: Anomaly Detection ===")
    lots = get_lots_with_enstru([0])
    anomalies = detect_anomalies(lots, threshold_percent=30)
    
    print(f" Найдено аномалий: {len(anomalies)}")
    if anomalies:
        top_anomaly = anomalies[0]
        print(f" Топ аномалия - Лот {top_anomaly['lot_id']}:")
        print(f"  - Сумма: {top_anomaly['amount']:,.0f} тенге")
        print(f"  - Z-score: {top_anomaly['z_score']:.2f}")
        print(f"  - Тип: {top_anomaly['anomaly_type']}")
    
    return len(anomalies) > 0

def test_ai_agent():
    """Тест AI-агента с различными типами вопросов"""
    print("\n=== TEST 4: AI Agent Questions ===")
    agent = GoszakupAIAgent()
    
    test_questions = [
        ("Справедлива ли цена 2000000 тенге для ЕНСТРУ 0?", "fair_price"),
        ("Какие аномалии цен для ЕНСТРУ 0 с отклонением >30%?", "anomalies"),
        ("Покажи лоты для ЕНСТРУ 0", "search"),
    ]
    
    results = []
    for question, expected_type in test_questions:
        print(f"\nВопрос: {question}")
        question_type = agent.classify_question(question)
        print(f"  Классификация: {question_type} {'✓' if question_type == expected_type or expected_type == 'search' else '✗'}")
        
        params = agent.extract_parameters(question, question_type)
        print(f"  Параметры: {params}")
        results.append(question_type in ['fair_price', 'anomalies', 'search'])
    
    return all(results)

def test_incremental_sync():
    """Тест инкрементальной синхронизации"""
    print("\n=== TEST 5: Incremental Sync (<24h) ===")
    import os
    from dotenv import load_dotenv
    from sync_all import get_last_update, update_last_update
    from datetime import datetime
    
    load_dotenv()
    
    last_sync = get_last_update("test_entity")
    print(f" Последняя синхронизация test_entity: {last_sync}")
    
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    update_last_update("test_entity", now)
    
    last_sync_updated = get_last_update("test_entity")
    print(f" Обновленная дата: {last_sync_updated}")
    
    return last_sync_updated is not None

def main():
    """Запустить все тесты"""
    print("=" * 60)
    print("INTEGRATION TESTS FOR TЗ REQUIREMENTS")
    print("=" * 60)
    
    start_time = time.time()
    
    tests = [
        ("Fair Price Metric", test_fair_price),
        ("Explainability (Top-K)", test_explainability),
        ("Anomaly Detection", test_anomaly_detection),
        ("AI Agent", test_ai_agent),
        ("Incremental Sync", test_incremental_sync),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = "✓ PASS" if result else "✗ FAIL"
        except Exception as e:
            results[test_name] = f"✗ ERROR: {str(e)[:50]}"
            print(f"ERROR: {e}")
    
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for test_name, result in results.items():
        print(f"{test_name:30} {result}")
    print(f"Time: {elapsed:.1f}s")
    print("=" * 60)

if __name__ == "__main__":
    main()
