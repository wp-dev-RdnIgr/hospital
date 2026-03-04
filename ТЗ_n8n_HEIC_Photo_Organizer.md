# ТЗ: n8n Workflow — Автоматическая сортировка HEIC-фото пациентов по ID клиента

## Контекст задачи

На Google Drive в папке хранятся HEIC-фотографии экранов больничного монитора. На каждом фото — медицинский отчёт пациента. В левом верхнем углу каждого документа виден **ID клиента** (числовой, 6 цифр, например `441882`).

Один клиент может иметь несколько фотографий.

**Целевая папка на Google Drive:**
`https://drive.google.com/drive/u/0/folders/1iEbSMlsHPX6Sg3y0J0znlT47ri78hk9_`

---

## Задача

Создать n8n workflow, который:

1. Принимает ID папки Google Drive с HEIC-фотографиями
2. Обходит каждый файл
3. Конвертирует HEIC в JPEG (для отправки в Vision API)
4. Отправляет изображение в OpenAI Vision API (GPT-4o) для распознавания ID клиента
5. Создаёт в **той же** папке Google Drive подпапку с именем = ID клиента (если не существует)
6. Перемещает фото в подпапку соответствующего клиента
7. Файлы, где не удалось распознать ID, остаются в исходной папке без изменений

Итог: каждый клиент имеет свою подпапку вида `441882/`, в которой лежат все его фотографии. Нераспознанные файлы остаются в корневой папке.

---

## Входные данные

| Параметр | Значение |
|---|---|
| Папка Google Drive | `1iEbSMlsHPX6Sg3y0J0znlT47ri78hk9_` |
| Формат файлов | `.HEIC` |
| Примерное кол-во файлов | ~100 штук |
| Структура данных на фото | Медицинский отчёт на немецком языке |
| Положение ID | Верхний левый угол (числовой код, 5–7 цифр) |

---

## Архитектура Workflow

### Нода 1 — Manual Trigger / Webhook
- Запуск вручную или через webhook
- Параметр: `folder_id` (Google Drive folder ID)
- Можно захардкодить `1iEbSMlsHPX6Sg3y0J0znlT47ri78hk9_` как дефолтное значение

### Нода 2 — Google Drive: List Files
- Получить список всех файлов в папке
- Фильтр: только файлы с расширением `.HEIC` или `image/heic`
- Выход: массив объектов `{id, name, mimeType}`

### Нода 3 — Split in Batches
- Разбить массив файлов на отдельные элементы для поочерёдной обработки
- Размер батча: 1 (обрабатывать по одному файлу)
- Причина: ограничения Vision API и квоты Google Drive

### Нода 4 — Google Drive: Download File
- Скачать бинарное содержимое HEIC-файла
- Входные данные: `fileId` из предыдущей ноды
- Выход: бинарные данные файла

### Нода 5 — Execute Command (HEIC → JPEG конвертация)
- Конвертировать HEIC в JPEG для совместимости с OpenAI Vision API
- Использовать системную утилиту `ImageMagick` или `heif-convert`
- Команда: `convert input.heic output.jpg` (через Code node или Execute Command node)
- **Альтернатива**: использовать Code node (JavaScript) с sharp/heic-decode если ImageMagick недоступен

> **Примечание для разработчика**: Проверить доступность ImageMagick на n8n-сервере. Если недоступен — реализовать конвертацию через npm-пакет `sharp` в Code node.

### Нода 6 — HTTP Request (OpenAI Vision API)
- **URL**: `https://api.openai.com/v1/chat/completions`
- **Метод**: POST
- **Headers**:
  ```
  Authorization: Bearer {{$credentials.openai.apiKey}}
  Content-Type: application/json
  ```
- **Body** (JSON):
  ```json
  {
    "model": "gpt-4o",
    "max_tokens": 100,
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "image_url",
            "image_url": {
              "url": "data:image/jpeg;base64,{{base64EncodedImage}}"
            }
          },
          {
            "type": "text",
            "text": "This is a photo of a hospital monitor screen showing a patient medical report. Look at the top-left corner of the document visible on screen. There should be a patient ID number (5-7 digits). Extract ONLY the patient ID number. Return ONLY the number, nothing else. If you cannot find it, return 'UNKNOWN'."
          }
        ]
      }
    ]
  }
  ```
- **Выход**: строка с ID клиента (например: `441882`)

### Нода 7 — Code Node (Парсинг ответа OpenAI)
```javascript
const response = $input.first().json;
const text = response.choices[0].message.content.trim();

// Валидация: должно быть число (5-7 цифр)
const clientId = /^\d{5,7}$/.test(text) ? text : 'UNKNOWN';

return [{ json: { clientId, fileName: $('Split in Batches').first().json.name, fileId: $('Split in Batches').first().json.id } }];
```

### Нода 8 — IF Node (Проверка распознавания)
- **Условие**: `clientId !== 'UNKNOWN'`
- **True**: переходим к созданию/проверке папки
- **False**: файл остаётся в исходной папке без изменений (пропускаем, переходим к следующему файлу)

### Нода 9 — Google Drive: Search Folder (Проверка существования папки)
- Поиск папки с именем = `clientId` внутри родительской папки
- Query: `name = '{{clientId}}' and '{{parentFolderId}}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false`
- **Если найдена** → использовать её `id`
- **Если не найдена** → создать новую (следующая нода)

### Нода 10 — Google Drive: Create Folder (условная нода)
- Создать подпапку с именем `clientId` в родительской папке
- Только если папка не существует (по результату ноды 9)
- Выход: `folderId` новой папки

### Нода 11 — Google Drive: Move File
- Переместить файл в папку клиента
- `fileId` = ID текущего файла
- `targetFolderId` = ID папки клиента (из ноды 9 или 10)
- Метод: обновить `parents` файла через Google Drive API

### Нода 12 — Google Sheets / Append (опционально, лог)
- Записать результат обработки в таблицу:
  - Имя файла
  - Распознанный ID клиента
  - Статус (успех / UNKNOWN)
  - Timestamp

---

## Технические детали реализации

### Аутентификация
- **Google Drive**: OAuth2 credential (уже настроен в n8n Webpromo)
- **OpenAI**: API Key credential

### Работа с HEIC
HEIC не поддерживается напрямую OpenAI Vision API. Варианты конвертации:
1. **ImageMagick** (предпочтительно): `convert file.heic file.jpg`
2. **Sharp npm** в Code node: `npm install sharp heic-decode`
3. **Внешний API конвертации** (запасной вариант)

Проверить доступность на сервере:
```bash
which convert && convert --version
```

### Обработка ошибок
- Таймаут OpenAI API: retry 3 раза с паузой 5 сек
- Файл не распознан: оставить в исходной папке + логировать
- Google Drive quota exceeded: throttle — 1 запрос в 2 секунды

### Rate Limiting
- Между обработкой файлов: задержка 1-2 секунды (Wait node)
- OpenAI API: не более 50 запросов в минуту
- Google Drive API: не более 1000 запросов в 100 секунд

---

## Структура результата на Google Drive

**До:**
```
📁 1iEbSMlsHPX6Sg3y0J0znlT47ri78hk9_/
  📷 IMG_001.HEIC
  📷 IMG_002.HEIC
  📷 IMG_003.HEIC
  ... (100 файлов)
```

**После:**
```
📁 1iEbSMlsHPX6Sg3y0J0znlT47ri78hk9_/
  📁 441882/
    📷 IMG_001.HEIC
    📷 IMG_015.HEIC
  📁 387654/
    📷 IMG_002.HEIC
  📁 512090/
    📷 IMG_003.HEIC
    📷 IMG_047.HEIC
    📷 IMG_088.HEIC
  📷 IMG_077.HEIC  ← не распознан, остался в корне
```

---

## Порядок разработки (рекомендуемый)

1. Проверить конвертацию HEIC → JPEG на тестовом файле
2. Настроить и протестировать OpenAI Vision на 3-5 файлах
3. Собрать workflow для одного файла end-to-end
4. Добавить логику создания папок
5. Добавить батч-обработку всех файлов
6. Добавить обработку ошибок и логирование
7. Прогнать на всей папке (~100 файлов)

---

## Критерии приёмки

- [ ] Workflow запускается по нажатию кнопки (или webhook)
- [ ] Каждый HEIC-файл обрабатывается один раз
- [ ] ID клиента извлекается корректно (проверить на 10 случайных файлах)
- [ ] Для каждого уникального ID создаётся ровно 1 папка
- [ ] Файлы перемещены (не скопированы) в соответствующие папки
- [ ] Нераспознанные файлы остаются в исходной папке
- [ ] Workflow не падает при обработке 100 файлов подряд
- [ ] Логи сохранены (Google Sheets или n8n execution log)

---

## Дополнительные замечания

- **Конфиденциальность**: данные пациентов — медицинская тайна. OpenAI API обрабатывает изображения согласно своей политике, но убедитесь в соответствии с GDPR/HIPAA требованиями клиники.
- **Промпт для OpenAI**: можно улучшить, указав конкретный шрифт или контекст ("German medical BMI report"), если точность распознавания будет недостаточной.
- **Альтернатива OpenAI**: если нужно исключить внешние API — можно использовать локальный OCR (Tesseract) через Execute Command node.
