import re
import json
from typing import Dict, List, Any
import os
import requests
from dotenv import load_dotenv
from analytics import (
    get_lots_with_enstru, calculate_fair_price, detect_anomalies,
    get_quantity_anomalies, format_fair_price_response
)

load_dotenv()

def validate_env_vars():
    """Валидация обязательных переменных окружения"""
    required_vars = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'AI_URL', 'AI_TOKEN', 'AI_MODEL']

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        raise ValueError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")

validate_env_vars()

def call_llm_api(prompt: str, context: str = "", sources: str = "") -> str:
    """Вызов внешнего LLM API для обработки запроса"""
    ai_url = os.getenv('AI_URL').rstrip('/')
    ai_token = os.getenv('AI_TOKEN')
    ai_model = os.getenv('AI_MODEL')
    
    system_prompt = """Ты AI-помощник для анализа государственных закупок Казахстана. 
Отвечай структурировано и на основе предоставленных данных.
Используй следующий формат ответа:

1. Краткий вывод: [основной результат]
2. Использованные данные: [какие данные использованы]
3. Аналитика: [детальный анализ]
4. Метрика оценки: [метод оценки]
5. Ограничения и уверенность: [риски и уверенность]
6. Примеры: [конкретные примеры]
7. Источники данных: [перечисли конкретные ID лотов, контрактов, объявлений и таблицы БД которые были использованы]"""
    
    user_message = f"{prompt}"
    if context:
        user_message += f"\n\nДанные для анализа:\n{context}"
    if sources:
        user_message += f"\n\nДоступные источники данных:\n{sources}"
    
    try:
        headers = {
            'Authorization': f'Bearer {ai_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': ai_model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_message}
            ],
            'temperature': 0.7,
            'max_tokens': 2000
        }
        
        response = requests.post(
            f'{ai_url}/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']
        else:
            return "Ошибка: Неожиданный формат ответа от LLM API"
            
    except requests.exceptions.RequestException as e:
        return f"Ошибка при обращении к LLM API: {str(e)}"
    except Exception as e:
        return f"Ошибка обработки ответа LLM: {str(e)}"


class GoszakupAIAgent:
    """AI-агент для анализа государственных закупок Казахстана"""

    def __init__(self):
        self.question_patterns = {
            'anomalies': [
                r'аномали',
                r'отклонение.*>?\s*\d+%?',
                r'выброс.*цена',
                r'подозрительн.*закупк',
                r'сравнени.*цена.*средн'
            ],
            'fair_price': [
                r'справедлив.*цен',
                r'адекватн.*цен',
                r'оцен.*цен.*лот',
                r'рыночн.*цен',
                r'сравн.*цен.*аналогичн'
            ],
            'quantity_anomalies': [
                r'завышен.*количеств',
                r'нетипичн.*количеств',
                r'аномали.*количеств',
                r'сравнени.*количеств.*год'
            ],
            'search': [
                r'найди',
                r'покажи',
                r'список',
                r'поиск'
            ],
            'analytics': [
                r'статистик',
                r'анализ',
                r'тренд',
                r'динамик'
            ]
        }

    def classify_question(self, question: str) -> str:
        """Классифицировать тип вопроса"""
        question_lower = question.lower()
        
        priority_order = ['anomalies', 'fair_price', 'quantity_anomalies', 'analytics', 'search']
        
        for question_type in priority_order:
            patterns = self.question_patterns.get(question_type, [])
            for pattern in patterns:
                if re.search(pattern, question_lower):
                    return question_type

        return 'search'

    def extract_parameters(self, question: str, question_type: str) -> Dict[str, Any]:
        """Извлечь параметры из вопроса"""
        params = {}

        enstru_match = re.search(r'енстру\s*(\d+)', question.lower())
        if enstru_match:
            params['enstru_code'] = int(enstru_match.group(1))

        bin_match = re.search(r'бин\s*(\d{12})', question.lower())
        if bin_match:
            params['bin'] = bin_match.group(1)

        amount_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:тенге|тг|тыс\.?|млн\.?)', question.lower())
        if amount_match:
            amount_str = amount_match.group(1).replace(',', '.')
            if 'млн' in question.lower():
                params['amount'] = float(amount_str) * 1000000
            elif 'тыс' in question.lower():
                params['amount'] = float(amount_str) * 1000
            else:
                params['amount'] = float(amount_str)

        percent_match = re.search(r'(\d+)%', question)
        if percent_match:
            params['threshold_percent'] = float(percent_match.group(1))

        year_match = re.search(r'(\d{4})\s*год', question.lower())
        if year_match:
            params['year'] = int(year_match.group(1))

        region_match = re.search(r'(?:регион|город|область)\s*(\d+)', question.lower())
        if region_match:
            params['region'] = region_match.group(1)

        return params

    def process_anomalies_question(self, question: str, params: Dict) -> str:
        """Обработать вопрос об аномалиях цен"""
        enstru_code = params.get('enstru_code', 12345)
        threshold = params.get('threshold_percent', 30.0)
        
        lots = get_lots_with_enstru([enstru_code])
        anomalies = detect_anomalies(lots, threshold)
        
        context = f"""ЕНСТРУ: {enstru_code}
Порог отклонения: {threshold}%
Лотов в выборке: {len(lots)}
Найдено аномалий: {len(anomalies) if anomalies else 0}

Примеры аномалий:"""
        
        sources = f"Таблица: lots (ЕНСТРУ {enstru_code})\n"
        if anomalies:
            sources += f"Использованные лоты (ID):\n"
            for i, a in enumerate(anomalies[:10]):
                sources += f"  - Лот {a['lot_id']}: {a['amount']:,.0f} тг (+{a['deviation_percent']:.1f}%)\n"
                context += f"\n{i+1}. Лот {a['lot_id']}: {a['amount']:,.0f} тг (+{a['deviation_percent']:.1f}%)"
        sources += f"\nВсего проанализировано лотов: {len(lots)}"
        
        prompt = f"Проанализируй аномалии цен: {question}"
        return call_llm_api(prompt, context, sources)

    def process_fair_price_question(self, question: str, params: Dict) -> str:
        """Обработать вопрос о справедливой цене"""
        enstru_code = params.get('enstru_code', 12345)
        query_amount = params.get('amount', 1000000)
        region = params.get('region')
        year = params.get('year')
        
        lots = get_lots_with_enstru([enstru_code], region=region, year=year)
        fair_price_data = calculate_fair_price(lots, enstru_code, region=region, target_year=year)
        
        context = f"""ЕНСТРУ: {enstru_code}
Запрашиваемая цена: {query_amount:,.0f} тенге
Лотов для анализа: {len(lots)}"""
        
        if region:
            context += f"\nРегион: {region}"
        if year:
            context += f"\nГод: {year}"
            
        context += f"""

Рыночные данные:
- Базовая медиана: {fair_price_data.get('base_median_price', 0):,.0f} тенге
- Скорректированная медиана: {fair_price_data.get('adjusted_median_price', 0):,.0f} тенге
- Среднее: {fair_price_data.get('mean_price', 0):,.0f} тенге
- IQR: {fair_price_data.get('iqr', 0):,.0f} тенге"""
        
        if fair_price_data.get('regional_multiplier', 1.0) != 1.0:
            context += f"\nРегиональный коэффициент: {fair_price_data['regional_multiplier']:.2f}"
        if fair_price_data.get('time_multiplier', 1.0) != 1.0:
            context += f"\nВременная корректировка: {fair_price_data['time_multiplier']:.2f}"
        if fair_price_data.get('seasonal_multiplier', 1.0) != 1.0:
            context += f"\nСезонная корректировка: {fair_price_data['seasonal_multiplier']:.2f}"
        
        if fair_price_data.get('top_k_lots'):
            context += "\n\nTop-5 лотов ближайших к медиане:"
            for i, lot in enumerate(fair_price_data['top_k_lots'], 1):
                context += f"\n{i}. Лот ID {lot['id']}: {lot['amount']:,.0f} тенге (отклонение: {lot['distance_from_median']:,.0f})"
        
        sources = f"Таблица: lots (ЕНСТРУ {enstru_code})\n"
        sources += f"Использованные лоты (Top-5 ближайшие к медиане):\n"
        if fair_price_data.get('top_k_lots'):
            for i, lot in enumerate(fair_price_data['top_k_lots'], 1):
                sources += f"  - Лот ID {lot['id']}: {lot['amount']:,.0f} тг\n"
        sources += f"\nОбщее количество проанализированных лотов: {len(lots)}"
        
        prompt = f"Оцени справедливость цены: {question}"
        return call_llm_api(prompt, context, sources)

    def process_quantity_anomalies_question(self, question: str, params: Dict) -> str:
        """Обработать вопрос об аномалиях количества"""
        year = params.get('year', 2023)
        
        anomalies = get_quantity_anomalies(year)
        
        context = f"Анализ аномалий количества ТРУ за {year} год.\n"
        
        sources = f"Таблица: lots (год: {year})\n"
        
        if anomalies:
            anomaly = anomalies[0]
            context += f"""Фактическое: {anomaly['actual_count']}
Прогноз: {anomaly['predicted_count']:.0f}
Отклонение: {anomaly['deviation_percent']:.1f}%
Тренд: {anomaly['trend']}

История по годам:"""
            sources += f"Основано на торговых УНита (ТРУ):\n"
            for h in anomaly['historical_data'][-3:]:
                context += f"\n- {h['year']}: {h['count']} лотов"
                sources += f"  - {h['year']}: {h['count']} лотов\n"
        else:
            context += "Аномалий количества не выявлено."
            sources += "Нет данных об аномалиях"
        
        prompt = f"Выяви аномалии количества: {question}"
        return call_llm_api(prompt, context, sources)

    def process_search_question(self, question: str, params: Dict) -> str:
        """Обработать поисковый вопрос"""
        enstru_code = params.get('enstru_code')
        
        context = ""
        sources = ""
        if enstru_code and enstru_code > 0:
            lots = get_lots_with_enstru([enstru_code])
            context = f"ЕНСТРУ {enstru_code}: найдено {len(lots)} лотов\n"
            sources = f"Таблица: lots (ЕНСТРУ {enstru_code})\n"
            if lots:
                sources += f"Показано первых 5 лотов из {len(lots)}:\n"
                for i, lot in enumerate(lots[:5]):
                    context += f"{i+1}. Лот ID {lot.get('id', '?')}: {lot['amount']:,.0f} тг - {lot['name'][:80]}\n"
                    sources += f"  - Лот ID {lot.get('id', '?')}: {lot['amount']:,.0f} тг\n"
        else:
            lots = get_lots_with_enstru()
            context = f"Всего лотов в системе: {len(lots)}\n"
            sources = f"Таблица: lots (all records)\n"
            if lots:
                sources += f"Показано первых 5 лотов:\n"
                for i, lot in enumerate(lots[:5]):
                    context += f"{i+1}. Лот ID {lot.get('id', '?')}: {lot['amount']:,.0f} тг - {lot['name'][:80]}\n"
                    sources += f"  - Лот ID {lot.get('id', '?')}: {lot['amount']:,.0f} тг\n"
        
        prompt = f"На основе данных по закупкам ответь: {question}"
        return call_llm_api(prompt, context, sources)

    def answer_question(self, question: str) -> str:
        """Основной метод для ответа на вопрос"""
        question_type = self.classify_question(question)
        params = self.extract_parameters(question, question_type)
        
        print(f"[AI Agent] Вопрос: {question}")
        print(f"[AI Agent] Тип: {question_type}")
        print(f"[AI Agent] Параметры: {params}")
        
        if question_type == 'anomalies':
            return self.process_anomalies_question(question, params)
        elif question_type == 'fair_price':
            return self.process_fair_price_question(question, params)
        elif question_type == 'quantity_anomalies':
            return self.process_quantity_anomalies_question(question, params)
        elif question_type == 'search':
            return self.process_search_question(question, params)
        else:
            return "Тип вопроса не распознан."

def main():
    agent = GoszakupAIAgent()
    
    print("="*80)
    print("AI АГЕНТ ДЛЯ АНАЛИЗА ГОСУДАРСТВЕННЫХ ЗАКУПОК КАЗАХСТАНА")
    print("="*80)
    print("\nДобро пожаловать! Вы можете задавать вопросы о закупках.")
    print("Примеры вопросов:")
    print("  - Найди закупки с отклонением цены > 30% для ЕНСТРУ 12345")
    print("  - Оцени адекватность цены 5000000 тенге для ЕНСТРУ 12345")
    print("  - Выяви аномалии количества ТРУ в 2023 году")
    print("  - Покажи лоты для ЕНСТРУ 12345")
    print("\nДля выхода введите 'выход' или 'exit'\n")
    
    while True:
        try:
            question = input("Ваш вопрос: ").strip()
            
            if not question:
                print("Пожалуйста, введите вопрос.\n")
                continue
            
            if question.lower() in ['выход', 'exit', 'quit']:
                print("До свидания!")
                break
            
            print(f"\n{'='*80}")
            answer = agent.answer_question(question)
            print(f"[ОТВЕТ]\n{answer}")
            print(f"{'='*80}\n")
            
        except KeyboardInterrupt:
            print("\n\nДо свидания!")
            break
        except Exception as e:
            print(f"Ошибка при обработке вопроса: {e}\n")

if __name__ == "__main__":
    main()
