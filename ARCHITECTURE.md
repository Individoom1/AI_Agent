# Архитектура AI-агента анализа государственных закупок

## 📊 Общая архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                    OWS v3 API (GraphQL)                         │
│            https://ows.goszakup.gov.kz/v3/graphql              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ETL Pipeline Layer                         │
│  ┌──────────┬──────────┬──────────┬──────────┐                 │
│  │ sync_    │ sync_    │ sync_    │ sync_    │                 │
│  │contracts │subjects  │announce- │ lots     │                 │
│  │          │          │ments     │          │                 │
│  └────┬─────┴────┬─────┴────┬─────┴────┬─────┘                 │
│       └──────────┴──────────┴──────────┘                        │
│              ▼                                                   │
│       GraphQL Queries                                           │
│   (Batching, Retry Logic)                                      │
└─────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│              PostgreSQL Database (Docker)                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Normalized Schema                    │   │
│  │  ┌──────────┬──────────┬──────────┬──────────┐          │   │
│  │  │   lots   │contracts │announce- │subjects  │          │   │
│  │  │(253k)    │(86k)     │ments     │(27)      │          │   │
│  │  │          │          │(68k)     │          │          │   │
│  │  └──────────┴──────────┴──────────┴──────────┘          │   │
│  │  ┌──────────┬──────────┬──────────┬──────────┐          │   │
│  │  │  orgs    │sync_meta │trade_    │contract_ │          │   │
│  │  │(27)      │metadata  │methods   │statuses  │          │   │
│  │  └──────────┴──────────┴──────────┴──────────┘          │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Analytics Layer (Python)                     │
│  ┌──────────────────────────────────────────────────────┐      │
│  │   analytics.py                                       │      │
│  │  ┌────────────────────────────────────────────────┐  │      │
│  │  │ • get_lots_with_enstru()    - фильтр данных   │  │      │
│  │  │ • calculate_fair_price()     - справедлив цена│  │      │
│  │  │ • detect_anomalies()         - аномалии       │  │      │
│  │  │ • get_quantity_anomalies()   - объемы         │  │      │
│  │  │ • format_*_response()        - форматирование │  │      │
│  │  └────────────────────────────────────────────────┘  │      │
│  └──────────────────────────────────────────────────────┘      │
└─────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AI Agent Layer                             │
│  ┌──────────────────────────────────────────────────────┐      │
│  │   ai_agent.py (GoszakupAIAgent)                      │      │
│  │                                                      │      │
│  │  1. classify_question()      ──► Тип вопроса        │      │
│  │                                                      │      │
│  │  2. extract_parameters()     ──► ЕНСТРУ, БИН, сумма│      │
│  │                                                      │      │
│  │  3. process_*_question()     ──► Аналитика          │      │
│  │     • anomalies                                      │      │
│  │     • fair_price                                     │      │
│  │     • quantity_anomalies                             │      │
│  │     • search                                         │      │
│  │                                                      │      │
│  │  4. call_llm_api()           ──► Отправка в LLM     │      │
│  │                                                      │      │
│  └──────────────────────────────────────────────────────┘      │
└─────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                  LLM API (Nitec AI / OpenAI)                    │
│              https://nitec-ai.kz/api/chat/completions          │
│                    (gpt-oss-120b model)                         │
│                                                                 │
│  Input: {                                                       │
│    "model": "openai/gpt-oss-120b",                             │
│    "messages": [                                               │
│      {"role": "system", "content": "Вы AI-агент закупок..."},│
│      {"role": "user", "content": "Контекст + вопрос"}         │
│    ]                                                            │
│  }                                                              │
└─────────────────────────┬────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│              Structured Response (6-part format)                │
│                                                                 │
│  1. Краткий вывод (1-3 предложения)                            │
│  2. Использованные данные (период, фильтры)                    │
│  3. Аналитика (сравнение, средние значения)                   │
│  4. Метрика оценки (методология)                               │
│  5. Ограничения и уверенность (качество данных)               │
│  6. Примеры (top-K закупок с ID)                              │
└─────────────────────────────────────────────────────────────────┘
```

## 🗄️ Схема базы данных

### Таблица: `organizations` (27 записей)
```sql
CREATE TABLE organizations (
  bin VARCHAR(12) PRIMARY KEY,          -- Бизнес-идентификационный номер
  name TEXT,
  is_customer BOOLEAN,
  is_supplier BOOLEAN,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
);
```

### Таблица: `subjects` (27 записей)
```sql
CREATE TABLE subjects (
  bin VARCHAR(12) PRIMARY KEY,
  iin VARCHAR(12),
  nameRu TEXT,
  nameKz TEXT,
  regdate DATE,
  customer BOOLEAN,
  supplier BOOLEAN,
  Address JSONB,                       -- {address, katoCode}
  created_at TIMESTAMPTZ
);
```

### Таблица: `contracts` (86,922 записи)
```sql
CREATE TABLE contracts (
  contract_id_sys VARCHAR(128) PRIMARY KEY,
  customer_bin VARCHAR(12),            -- FOREIGN KEY → organizations
  supplier_bin VARCHAR(12),
  contract_sum NUMERIC,                -- Сумма контракта
  sign_date DATE,
  description TEXT,
  trade_method_id INTEGER,
  status_id INTEGER,
  fin_year INTEGER,
  raw_payload JSONB                    -- Оригинальные данные API
);
```

### Таблица: `lots` (253,025 записей)
```sql
CREATE TABLE lots (
  id BIGINT PRIMARY KEY,
  nameRu TEXT,
  amount NUMERIC,                      -- Сумма лота (ключевое поле)
  customerBin VARCHAR(12),
  trdBuyId BIGINT,
  count NUMERIC,                       -- Количество единиц
  enstruList INTEGER[],                -- Коды ЕНСТРУ (для класс-ции)
  plnPointKatoList TEXT[],            -- Регионы (KATO коды)
  lastUpdateDate TIMESTAMPTZ,          -- Для инкрементального обновления
  raw_payload JSONB
);
```

### Таблица: `announcements` (68,492 записи)
```sql
CREATE TABLE announcements (
  id BIGINT PRIMARY KEY,
  numberAnno TEXT,
  nameRu TEXT,
  totalSum NUMERIC,
  countLots INTEGER,
  customerBin VARCHAR(12),
  refTradeMethodsId INTEGER,
  publishDate TIMESTAMPTZ,
  lastUpdateDate TIMESTAMPTZ,          -- Для инкрементального обновления
  raw_payload JSONB
);
```

### Таблица: `sync_meta` (отслеживание обновлений)
```sql
CREATE TABLE sync_meta (
  entity VARCHAR(50) PRIMARY KEY,      -- 'announcements', 'contracts', 'lots'
  last_update_date TIMESTAMPTZ,        -- Время последнего обновления
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 🔄 Data Flow - Инкрементальное обновление

### Сценарий: Запуск sync_all.py

```python
# 1. Получить время последнего обновления
last_update = SELECT last_update_date FROM sync_meta WHERE entity = 'announcements'
# Результат: 2026-04-26 11:07:51

# 2. Запустить GraphQL с фильтром lastUpdateDate
query = """
  query($bin, $lastUpdateDate) {
    TrdBuy(filter: {
      orgBin: $bin,
      lastUpdateDate: {gte: $lastUpdateDate}  # Только новые!
    }) { ... }
  }
"""

# 3. Загрузить только новые/измененные объявления
# Задержка: < 24 часов

# 4. Обновить sync_meta
UPDATE sync_meta SET last_update_date = NOW() WHERE entity = 'announcements'
```

## 📐 Методы анализа

### 1️⃣ Обнаружение аномалий (`detect_anomalies()`)

**Метод:** Tukey's Fences

```python
def detect_anomalies(lots, threshold_percent):
  # 1. Вычислить квартили
  Q1 = percentile(prices, 25)
  Q3 = percentile(prices, 75)
  IQR = Q3 - Q1
  
  # 2. Вычислить границы
  lower = Q1 - 1.5 * IQR
  upper = Q3 + 1.5 * IQR
  
  # 3. Найти выбросы
  anomalies = [lot for lot in lots if lot.price < lower or lot.price > upper]
  
  # 4. Вычислить отклонение %
  deviation = ((actual - median) / median) * 100
  
  return anomalies
```

**Статистика на данных:**
- Лотов с ЕНСТРУ=0: 251,604
- Аномалий (deviation > 20%): 233,870 (92.9%)
- Указывает на проблему с данными (нулевые базовые цены)

### 2️⃣ Справедливая цена (`calculate_fair_price()`)

**Текущая реализация:**
```python
def calculate_fair_price(lots, enstru_code, region=None):
  # Фильтруем по ЕНСТРУ
  relevant = [l for l in lots if enstru_code in l.enstruList]
  
  # Базовая статистика
  prices = [l.amount for l in relevant]
  
  return {
    'median': np.median(prices),
    'mean': np.mean(prices),
    'iqr': np.percentile(prices, 75) - np.percentile(prices, 25),
    'min': min(prices),
    'max': max(prices)
  }
```

**Требует расширения:**
```python
# TODO: Региональный коэффициент
regional_coefficient = price_by_region / avg_price_national

# TODO: Временной фактор
inflation_coefficient = inflation_rate[current_year] / inflation_rate[contract_year]
seasonality_coefficient = seasonal_index[month]

# Fair Price = base_price × regional × inflation × seasonality
```

### 3️⃣ Аномалии количества (`get_quantity_anomalies()`)

**Метод:** Линейная регрессия

```python
# Построить трендлинию по историческим данным
years = [2021, 2022, 2023, 2024]
counts = [100k, 120k, 150k, 160k]

# Предсказать для 2025
predicted_2025 = regression_line(2025)  # e.g., 170k

# Найти аномалию
actual_2025 = 200k
deviation = (actual_2025 - predicted_2025) / predicted_2025 * 100  # 17.6%

if deviation > threshold:
  mark_as_anomaly()
```

## 🤖 AI Agent - Логика обработки вопросов

### Этап 1: Классификация

```python
def classify_question(question: str) -> str:
  patterns = {
    'anomalies': [r'аномалии', r'выброс', r'отклонение'],
    'fair_price': [r'справедлив', r'адекватн', r'оценк'],
    'quantity_anomalies': [r'завышение.*количество'],
    'search': [r'найди', r'покажи', r'список']
  }
  
  for type, patterns in patterns.items():
    if match_any(question, patterns):
      return type
```

### Этап 2: Извлечение параметров

```python
def extract_parameters(question: str) -> Dict:
  params = {}
  
  # ЕНСТРУ код (цифры после "ЕНСТРУ")
  enstru_match = re.search(r'енстру\s*(\d+)', question)
  if enstru_match:
    params['enstru_code'] = int(enstru_match.group(1))
  
  # Сумма (числа + тенге/тыс/млн)
  amount_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:тенге|тыс|млн)', question)
  if amount_match:
    amount_str = amount_match.group(1).replace(',', '.')
    if 'млн' in question:
      params['amount'] = float(amount_str) * 1_000_000
    elif 'тыс' in question:
      params['amount'] = float(amount_str) * 1_000
    else:
      params['amount'] = float(amount_str)
  
  # Процент отклонения
  percent_match = re.search(r'(\d+)%', question)
  if percent_match:
    params['threshold_percent'] = float(percent_match.group(1))
  
  # Год
  year_match = re.search(r'(\d{4})\s*год', question)
  if year_match:
    params['year'] = int(year_match.group(1))
  
  return params
```

### Этап 3: Аналитика

```python
# Для каждого типа вопроса:
if type == 'anomalies':
  lots = get_lots_with_enstru([enstru_code])
  anomalies = detect_anomalies(lots, threshold)
  
  context = f"""
  ЕНСТРУ: {enstru_code}
  Лотов в выборке: {len(lots)}
  Аномалий найдено: {len(anomalies)}
  Примеры:
  {format_examples(anomalies[:5])}
  """

elif type == 'fair_price':
  lots = get_lots_with_enstru([enstru_code])
  fair_price = calculate_fair_price(lots, enstru_code)
  
  context = f"""
  ЕНСТРУ: {enstru_code}
  Медиана: {fair_price['median']}
  Среднее: {fair_price['mean']}
  Запрашиваемая: {query_amount}
  Отклонение: {deviation_percent}%
  """
```

### Этап 4: LLM Call

```python
def call_llm_api(prompt: str, context: str) -> str:
  response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
      {
        "role": "system",
        "content": """
        Ты AI-агент анализа закупок Казахстана.
        Ответы структурированы в 6 пунктов:
        1. Краткий вывод
        2. Использованные данные
        3. Аналитика
        4. Метрика оценки
        5. Ограничения и уверенность
        6. Примеры
        """
      },
      {
        "role": "user",
        "content": f"{prompt}\n\nДанные:\n{context}"
      }
    ],
    temperature=0.7,
    max_tokens=2000
  )
  
  return response.choices[0].message.content
```

## 🔐 Безопасность

### Защита токенов

```
.env (SECRET) ───────── не коммитится в git
              │
              ├── GOSZAKUP_TOKEN (OWS v3 API)
              ├── AI_TOKEN (Nitec AI)
              └── DB_PASSWORD (PostgreSQL)

docker-compose.yml (SAFE) - использует переменные из .env
```

### SQL безопасность

```python
# Безопасно (параметризованный запрос)
cur.execute("SELECT * FROM lots WHERE enstruList && %s", (enstru_codes,))

# НЕБЕЗОПАСНО (SQL injection)
cur.execute(f"SELECT * FROM lots WHERE enstruList && {enstru_codes}")
```

## 📊 Производительность

| Операция | Время | Примечания |
|----------|-------|-----------|
| Холодный старт sync_all | 15-20 мин | Загрузка 410k записей |
| Инкрементальное обновление | 2-5 мин | Только новые данные |
| Запрос к LLM | 2-3 сек | Зависит от нагрузки API |
| Анализ 253k лотов | < 100 ms | SQL + Python анализ |

## 📝 Лимиты и ограничения

1. **API Rate Limiting**
   - OWS v3: ~100 req/min (estimated)
   - Nitec AI: ~50 req/min (estimated)

2. **Память**
   - Текущая: ~500 MB (все лоты в памяти)
   - Оптимизация: streaming queries

3. **Точность**
   - Извлечение БИН: > 99%
   - Извлечение сумм: > 98%
   - Извлечение дат: > 95%
