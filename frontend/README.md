# TenderLens frontend

React-клиент для реального TenderLens API. Интерфейс загружает PDF через FastAPI, отслеживает
статус обработки, показывает условия и риски из `/analysis`, отправляет вопросы в `/questions`
и открывает цитаты на соответствующей странице PDF.

## Локальный запуск

Требуются Node.js 20+ и запущенный TenderLens backend на `http://localhost:8000`.

```bash
cp .env.example .env
pnpm install
pnpm run api:types
pnpm dev
```

Откройте `http://localhost:5173`.

При обычном запуске проекта отдельно устанавливать Node.js не требуется: корневая команда
`docker compose up --build` собирает frontend и открывает его на этом же адресе.

Русский язык включён по умолчанию. Переключатель `RU / EN` меняет язык интерфейса и
сохраняет выбор. Текст исходного PDF и точные цитаты не переводятся, поскольку должны
дословно совпадать с документом.

Для запросов из Vite backend должен разрешать origin `http://localhost:5173`. В корневом
`.env` проекта задайте:

```dotenv
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
```

## Проверки

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm test:e2e
```

`pnpm run api:types` обновляет `src/api/schema.d.ts` напрямую из `openapi.json` работающего
backend. Сгенерированный файл хранится в репозитории, поэтому обычная сборка не требует
доступного API.

## Текущие ограничения

- PDF viewer использует локальный object URL сразу после выбора файла, а после перезагрузки
  безопасно получает Blob через `GET /api/v1/documents/{document_id}/file`. Версии PDF.js API
  и worker зафиксированы, а Nginx отдаёт module worker с корректным JavaScript MIME-типом.
- `start_char` и `end_char` описывают позиции текста, а не геометрию PDF. Интерфейс не рисует
  неподтверждённую прямоугольную подсветку.
- Тёмная тема, сравнение тендеров, шаблоны и экспорт намеренно не добавлены: соответствующих
  возможностей пока нет в backend.
