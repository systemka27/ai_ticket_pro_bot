<h1 align="center">🤖 Smart Support Assistant</h1>
<p align="center">
  <b>AI-ассистент службы поддержки на базе модели DeepSeek</b><br>
  Автоматизирует ответы клиентам и помогает поддержке работать быстрее.
</p>

---

## ⚙️ Основные возможности

✅ Автоматические ответы на частые вопросы клиентов  
✅ Интеграция с AI-моделью DeepSeek  
✅ Логирование диалогов и ошибок  
✅ Поддержка `.env` и конфигурации через `config.py`  
✅ Готов к деплою на **Amvera / Heroku**

---


## 🚀 Установка и запуск

### 1️⃣ Клонировать репозиторий
```bash
git clone https://github.com/yourusername/smart-support-assistant.git
cd smart-support-assistant
2️⃣ Установить зависимости
bash
Копировать код
pip install -r requirements.txt
3️⃣ Создать файл .env
Пример содержимого:

ini
Копировать код
BOT_TOKEN=your_bot_token_here
DEEPSEEK_API_KEY=your_api_key_here
4️⃣ Запустить бота
bash
Копировать код
python main.py
☁️ Деплой
Проект поддерживает быстрое развёртывание на Amvera или Heroku.
Файлы, необходимые для деплоя:

Procfile

.amvera.yml

runtime.txt

🧠 Используемые технологии
Компонент	Описание
Python	Основной язык проекта
DeepSeek API	Генерация ответов AI
SQLite	Простая встроенная база данных
Amvera	Хостинг и деплой приложения

🪪 Лицензия
Проект распространяется под лицензией MIT.
Вы можете свободно использовать, изменять и распространять код при сохранении авторского уведомления.
