import os

class Config:
    # База данных
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///./bot.db')
    
    # Токены из переменных окружения (ИМЕННО BOT_TOKEN!)
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
    
    # OPERATOR_CHAT_ID с безопасной обработкой
    operator_chat_id = os.getenv('OPERATOR_CHAT_ID', '').strip()
    OPERATOR_CHAT_ID = int(operator_chat_id) if operator_chat_id and operator_chat_id.isdigit() else None
    
    # Настройки DeepSeek
    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
    DEEPSEEK_MODEL = "deepseek-chat"
    
    # Настройки бота
    MAX_MESSAGE_LENGTH = 4000
    TYPING_DELAY = 0.5
    
    # Проверка обязательных переменных
    @classmethod
    def validate(cls):
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не установлен! Проверьте переменные окружения в Amvera")
        if not cls.DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY не установлен! Проверьте переменные окружения в Amvera")

# Создаем экземпляр конфигурации
config = Config()

# Проверяем при импорте
config.validate()