import asyncio
import logging
import random
import re
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from services.deepseek_service import DeepSeekService

# Загрузка переменных окружения ДО всего остального
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Импортируем конфиг
from config import config

# Проверка токена из конфига
BOT_TOKEN = config.BOT_TOKEN
if not BOT_TOKEN:
    logger.error("BOT_TOKEN не найден в конфигурации!")
    exit(1)

logger.info(f"Бот запускается с токеном: {BOT_TOKEN[:10]}...")

# Класс для управления ответами на номера заказов
class OrderResponseManager:
    def __init__(self):
        self.order_patterns = {
            # Особые номера
            'premium': {'suffix': ['00', '25', '50', '75'], 'type': 'Премиум сервис'},
            'special_numbers': {'numbers': [111111, 222222, 333333, 444444, 555555, 666666, 777777, 888888, 999999, 123456, 654321], 'type': 'Особый номер'}
        }
        
        # 5 заказов, которые будут "не найдены"
        self.not_found_orders = {
            '999999', '888888', '777777', '666666', '555555'
        }
        
        # Остальные заказы будут найдены
        self.existing_orders = {
            # Основные диапазоны
            '123456', '123457', '123458', '123459', '123460', '123461', '123462', '123463', '123464', '123465',
            '123466', '123467', '123468', '123469', '123470', '123471', '123472', '123473', '123474', '123475',
            '234567', '234568', '234569', '234570', '234571', '234572', '234573', '234574', '234575', '234576',
            '234577', '234578', '234579', '234580', '234581', '234582', '234583', '234584', '234585', '234586',
            '345678', '345679', '345680', '345681', '345682', '345683', '345684', '345685', '345686', '345687',
            '345688', '345689', '345690', '345691', '345692', '345693', '345694', '345695', '345696', '345697',
            '456789', '456790', '456791', '456792', '456793', '456794', '456795', '456796', '456797', '456798',
            '456799', '456800', '456801', '456802', '456803', '456804', '456805', '456806', '456807', '456808',
            '567890', '567891', '567892', '567893', '567894', '567895', '567896', '567897', '567898', '567899',
            '567900', '567901', '567902', '567903', '567904', '567905', '567906', '567907', '567908', '567909',
            
            # Дополнительные диапазоны
            '678901', '678902', '678903', '678904', '678905', '678906', '678907', '678908', '678909', '678910',
            '789012', '789013', '789014', '789015', '789016', '789017', '789018', '789019', '789020', '789021',
            '890123', '890124', '890125', '890126', '890127', '890128', '890129', '890130', '890131', '890132',
            '901234', '901235', '901236', '901237', '901238', '901239', '901240', '901241', '901242', '901243',
            
            # Повторяющиеся и особые номера (кроме 5 не найденных)
            '111111', '222222', '333333', '444444',
            '112233', '223344', '334455', '445566', '556677', '667788', '778899', '889900', '990011',
            '121212', '232323', '343434', '454545', '565656', '676767', '787878', '898989',
            '131313', '242424', '353535', '464646', '575757', '686868', '797979',
            '141414', '252525', '363636', '474747', '585858', '696969',
            '151515', '262626', '373737', '484848',
            '161616', '272727', '383838', '494949',
            '171717', '282828', '393939',
            '181818', '292929',
            '191919',
            
            # Номера с префиксами
            '100001', '100002', '100003', '100004', '100005', '100006', '100007', '100008', '100009', '100010',
            '200001', '200002', '200003', '200004', '200005', '200006', '200007', '200008', '200009', '200010',
            '300001', '300002', '300003', '300004', '300005', '300006', '300007', '300008', '300009', '300010',
            '400001', '400002', '400003', '400004', '400005', '400006', '400007', '400008', '400009', '400010',
            '500001', '500002', '500003', '500004', '500006', '500007', '500008', '500009', '500010',
            
            # Симметричные номера
            '123321', '123432', '123543', '123654', '123765', '123876', '123987',
            '321123', '432234', '543345', '654456', '765567', '876678', '987789',
            '102030', '203040', '304050', '405060', '506070', '607080', '708090', '809010',
            '110011', '220022', '330033', '440044',
            '120012', '230023', '340034', '450045', '560056', '670067', '780078', '890089',
            '130013', '240024', '350035', '460046', '570057', '680068', '790079',
            '140014', '250025', '360036', '470047', '580058', '690069',
            '150015', '260026', '370037', '480048',
            
            # Популярные комбинации
            '123123', '321321', '456456', '654654', '789789', '987987',
            '111222', '222333', '333444', '444555',
            '100100', '200200', '300300', '400400',
            '101010', '202020', '303030', '404040',
            
            # Дополнительные номера для покрытия большинства комбинаций
            '102938', '112233', '122333', '133344', '144455', '155566', '166677', '177788', '188899', '199900',
            '201234', '211235', '221236', '231237', '241238', '251239', '261240', '271241', '281242', '291243',
            '301234', '311235', '321236', '331237', '341238', '351239', '361240', '371241', '381242', '391243',
            '401234', '411235', '421236', '431237', '441238', '451239', '461240', '471241', '481242', '491243',
            '501234', '511235', '521236', '531237', '541238', '551239', '561240', '571241', '581242', '591243',
            
            # Еще больше номеров для максимального покрытия
            '601234', '611235', '621236', '631237', '641238', '651239', '661240', '671241', '681242', '691243',
            '701234', '711235', '721236', '731237', '741238', '751239', '761240', '771241', '781242', '791243',
            '801234', '811235', '821236', '831237', '841238', '851239', '861240', '871241', '881242', '891243',
            '901234', '911235', '921236', '931237', '941238', '951239', '961240', '971241', '981242', '991243',
            
            # Финальный набор для почти 100% покрытия
            '102345', '112346', '122347', '132348', '142349', '152350', '162351', '172352', '182353', '192354',
            '202345', '212346', '222347', '232348', '242349', '252350', '262351', '272352', '282353', '292354',
            '302345', '312346', '322347', '332348', '342349', '352350', '362351', '372352', '382353', '392354',
            '402345', '412346', '422347', '432348', '442349', '452350', '462351', '472352', '482353', '492354',
            '502345', '512346', '522347', '532348', '542349', '552350', '562351', '572352', '582353', '592354'
        }
    
    def get_order_status_response(self, order_number: str) -> str:
        """Генерирует ответ о статусе заказа на основе его номера"""
        
        # Проверяем, является ли заказ одним из 5 "не найденных"
        if order_number in self.not_found_orders:
            return (
                "❌ Заказ не найден\n\n"
                "Убедитесь, что:\n"
                "• Вы покупали билеты у нас на сайте Intickets\n"
                "• Номер заказа указан правильно (6 цифр)\n"
                "• Заказ был оформлен в течение последних 6 месяцев\n\n"
                "Если уверены в номере заказа - обратитесь к оператору для детальной проверки."
            )
        
        # Проверяем существование заказа
        if order_number not in self.existing_orders:
            # Для всех остальных заказов, которых нет в списке, считаем найденными
            pass
        
        num = int(order_number)
        
        # Проверяем специальные паттерны
        order_type = self._detect_order_type(order_number)
        return self._generate_detailed_response(order_number, order_type)
    
    def _detect_order_type(self, order_number: str) -> str:
        """Определяет тип заказа по номеру"""
        num = int(order_number)
        
        # Проверяем диапазоны
        for key, pattern in self.order_patterns.items():
            if 'suffix' in pattern:
                if any(order_number.endswith(suffix) for suffix in pattern['suffix']):
                    return pattern['type']
            
            if 'numbers' in pattern:
                if num in pattern['numbers']:
                    return pattern['type']
        
        return "Стандартная обработка"
    
    def _generate_detailed_response(self, order_number: str, order_type: str) -> str:
        """Генерирует детализированный ответ на основе типа заказа"""
        
        responses = {
            'Премиум сервис': [
                f"✅ Заказ №{order_number} успешно обработан!\n\nБилеты отправлены на email. Проверьте папку «Спам» если не нашли.",
                f"📧 Заказ №{order_number} - письмо с билетами доставлено!\n\nВсе билеты активны и готовы к использованию.",
            ],
            
            'Особый номер': [
                f"✅ Заказ №{order_number} успешно обработан!\n\nБилеты отправлены на email. Проверьте папку «Спам» если не нашли.",
                f"📧 Заказ №{order_number} - письмо с билетами доставлено!\n\nВсе билеты активны и готовы к использованию.",
            ]
        }
        
        # Если тип не найден, используем стандартные ответы
        if order_type not in responses:
            standard_responses = [
                f"✅ Заказ №{order_number} успешно обработан!\n\nБилеты отправлены на email. Проверьте папку «Спам» если не нашли.",
                f"📧 Заказ №{order_number} - письмо с билетами доставлено!\n\nВсе билеты активны и готовы к использованию.",
            ]
            return random.choice(standard_responses)
        
        return random.choice(responses[order_type])

# Функция для определения недовольства (вынесена отдельно)
def detect_dissatisfaction_improved(message_text: str) -> bool:
    """Определяет недовольство клиента (улучшенная версия)"""
    dissatisfaction_phrases = [
        'недоволен', 'плохой', 'ужасный', 'кошмар', 'безобразие', 'возмущен',
        'хреново', 'отстой', 'бесит', 'раздражает', 'достало', 'надоело',
        'человека', 'оператора', 'менеджера', 'живого',
        'это не помогает', 'бесполезно', 'зря', 'напрасно',
        'верните деньги', 'жалоба', 'претензия', 'верните',
        'свяжите с человеком', 'позовите оператора', 'до человека',
        'не помогает', 'без толку', 'напрасн', 'бесполезно',
        'проблема не решена', 'ничего не меняется', 'не решается',
        'уже пробовал', 'уже пытался', 'всё равно не работает',
        'надоело ждать', 'достало ждать', 'устал ждать',
        'это не решает проблему', 'беспонтово', 'фигня', 'ерунда',
        'зря только', 'напрасная трата', 'разочарован', 'разочаровал'
    ]
    
    message_lower = message_text.lower()
    return any(phrase in message_lower for phrase in dissatisfaction_phrases)

# Функция для определения, что пользователь не может разобраться сам
def detect_need_help(message_text: str) -> bool:
    """Определяет, что пользователь не может разобраться сам и нуждается в помощи оператора"""
    help_phrases = [
        'не могу разобраться', 'не понимаю', 'не ясно', 'не понятно', 
        'не получается', 'не выходит', 'не знаю как', 'не знаю что делать',
        'запутался', 'не разберусь', 'не соображу', 'не могу понять',
        'помогите разобраться', 'объясните', 'подскажите как быть',
        'что делать не знаю', 'не могу понять в чем проблема',
        'не могу понять что случилось', 'не могу понять почему',
        'не могу понять как решить', 'не могу решить проблему',
        'не получается решить', 'не выходит решить', 'не могу справиться',
        'не могу сам разобраться', 'сам не справлюсь', 'сам не могу',
        'нужна помощь', 'требуется помощь', 'помогите пожалуйста',
        'не могу понять в чем дело', 'не могу понять что не так'
    ]
    
    message_lower = message_text.lower()
    return any(phrase in message_lower for phrase in help_phrases)

# Функция для определения благодарностей и положительных отзывов
def detect_thanks_and_praise(message_text: str) -> bool:
    """Определяет благодарности и положительные отзывы"""
    thanks_phrases = [
        'спасибо', 'благодарю', 'thanks', 'thank you', 'мерси', 'пасиб', 'сяб', 
        'благодарочка', 'признателен', 'признательна', 'благодарствую',
        'выручил', 'помог', 'спас', 'супер', 'отлично', 'прекрасно', 'замечательно',
        'великолепно', 'потрясающе', 'офигенно', 'офигенный', 'круто', 'крутой',
        'здорово', 'молодец', 'умница', 'красавчик', 'лучший', 'лучшая', 
        'работает', 'все работает', 'всё работает', 'все ок', 'всё ок', 'все хорошо',
        'всё хорошо', 'отличная работа', 'хорошая работа', 'вау', 'ого', 'здорово',
        'суперски', 'класс', 'классно', 'заебись', 'ахуенно', 'шикарно', 'превосходно',
        'идеально', 'безупречно', 'восхитительно', 'потрясающе', 'невероятно',
        'обалденно', 'чудесно', 'изумительно', 'фантастически', 'блестяще'
    ]
    
    message_lower = message_text.lower()
    return any(phrase in message_lower for phrase in thanks_phrases)

# Класс для обработки вызова оператора
class OperatorHandler:
    def __init__(self):
        self.user_sessions: Dict[int, Dict] = {}
        
    def start_operator_session(self, user_id: int):
        """Начинает сессию вызова оператора"""
        self.user_sessions[user_id] = {
            'step': 'waiting_problem_description',
            'data': {},
            'created_at': datetime.now()
        }
        logger.info(f"Начата сессию вызова оператора для пользователя {user_id}")
        
    def process_operator_message(self, user_id: int, message: str) -> Optional[str]:
        """Обрабатывает сообщение в контексте вызова оператора"""
        if user_id not in self.user_sessions:
            return None
            
        session = self.user_sessions[user_id]
        current_step = session['step']
        
        if current_step == 'waiting_problem_description':
            return self._process_problem_description_step(user_id, message)
            
        return None
        
    def _process_problem_description_step(self, user_id: int, message: str) -> str:
        """Обрабатывает шаг описания проблемы"""
        # Проверяем, является ли сообщение корректным текстом (не набором символов)
        if self._is_gibberish(message):
            return (
                "Не совсем понял ваш запрос. Пожалуйста, опишите вашу проблему более подробно и понятно.\n\n"
                "Пример: 'У меня проблема с оплатой заказа 123456' или 'Не пришли билеты на email'"
            )
        
        self.user_sessions[user_id]['data']['problem_description'] = message
        
        # Завершаем сессию
        del self.user_sessions[user_id]
        
        # Формируем финальный ответ
        response = "Оператор уведомлен. Ожидайте подключения в течение 2-5 минут. ⏰"
        
        logger.info(f"Оператор вызван для пользователя {user_id} с проблемой: {message}")
        return response
    
    def _is_gibberish(self, text: str) -> bool:
        """Проверяет, является ли текст бессмысленным набором символов"""
        # Удаляем пробелы для проверки
        clean_text = re.sub(r'\s+', '', text)
        
        # Если текст слишком короткий после очистки
        if len(clean_text) < 3:
            return True
            
        # Проверяем на повторяющиеся символы (например, "аааа", "1111")
        if len(set(clean_text)) <= 2 and len(clean_text) > 5:
            return True
            
        # Проверяем на отсутствие русских/английских букв
        if not re.search(r'[а-яА-Яa-zA-Z]', text):
            return True
            
        return False
        
    def has_active_session(self, user_id: int) -> bool:
        """Проверяет, есть ли активная сессия вызова оператора"""
        return user_id in self.user_sessions
        
    def clear_session(self, user_id: int):
        """Очищает сессию пользователя"""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]

# Класс для обработки восстановления билетов
class TicketRecoveryHandler:
    def __init__(self):
        self.user_sessions: Dict[int, Dict] = {}
        
    def start_recovery_session(self, user_id: int):
        """Начинает сессию восстановления билетов"""
        self.user_sessions[user_id] = {
            'step': 'waiting_contact_info',
            'data': {},
            'created_at': datetime.now()
        }
        logger.info(f"Начата сессия восстановления билетов для пользователя {user_id}")
        
    def process_recovery_message(self, user_id: int, message: str) -> Optional[str]:
        """Обрабатывает сообщение в контексте восстановления билетов"""
        if user_id not in self.user_sessions:
            return None
            
        session = self.user_sessions[user_id]
        current_step = session['step']
        
        if current_step == 'waiting_contact_info':
            return self._process_contact_info_step(user_id, message)
            
        return None
        
    def _validate_phone_number(self, phone: str) -> bool:
        """Проверяет валидность российского номера телефона"""
        clean_phone = re.sub(r'[\s\(\)\-+]', '', phone)
        
        if not clean_phone.startswith(('7', '8')):
            return False
        
        if len(clean_phone) not in [10, 11]:
            return False
        
        if not clean_phone.isdigit():
            return False
        
        patterns = [
            r'^7\d{10}$',
            r'^8\d{10}$',
            r'^7\d{9}$',
            r'^8\d{9}$',
        ]
        
        for pattern in patterns:
            if re.match(pattern, clean_phone):
                return True
        
        return False

    def _validate_email(self, email: str) -> bool:
        """Проверяет валидность email"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
        return re.match(pattern, email) is not None

    def _extract_contact_info(self, text: str) -> Dict[str, str]:
        """Извлекает контактные данные из текста"""
        contacts = {}
        
        # Ищем email
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        if email_match:
            contacts['email'] = email_match.group(0)
        
        # Ищем телефон (улучшенные паттерны)
        phone_patterns = [
            r'\b\+?7\s?\(?\d{3}\)?\s?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b',
            r'\b8\s?\(?\d{3}\)?\s?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b',
            r'\b7\s?\(?\d{3}\)?\s?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b',  # Добавлен паттерн для 7 с пробелами
            r'\b7\d{9,10}\b',
            r'\b8\d{9,10}\b',
        ]
        
        found_phones = []
        for pattern in phone_patterns:
            phone_matches = re.finditer(pattern, text)
            for phone_match in phone_matches:
                phone = phone_match.group(0)
                if self._validate_phone_number(phone):
                    found_phones.append(phone)
        
        if found_phones:
            contacts['phone'] = found_phones[0]
        
        # Ищем номер заказа (6 цифр)
        order_match = re.search(r'\b(\d{6})\b', text)
        if order_match:
            contacts['order_number'] = order_match.group(1)
        
        return contacts

    def _process_contact_info_step(self, user_id: int, message: str) -> str:
        """Обрабатывает шаг ввода контактной информации"""
        contact_info = self._extract_contact_info(message)
        
        if not contact_info:
            # Если не удалось распознать контактные данные, просим уточнить
            return (
                "Не удалось распознать контактные данные. Пожалуйста, укажите:\n\n"
                "• Номер заказа (6 цифр) ИЛИ\n"
                "• Номер телефона ИЛИ\n"
                "• Email\n\n"
                "Пример: 123456, +79123456789 или example@mail.ru"
            )
        
        # Сохраняем данные
        self.user_sessions[user_id]['data'] = contact_info
        
        # Форматируем найденные данные для отображения с правильными падежами
        found_data = []
        if 'order_number' in contact_info:
            found_data.append(f"номеру заказа: {contact_info['order_number']}")
        if 'phone' in contact_info:
            phone = contact_info['phone']
            clean_phone = re.sub(r'[\s\(\)\-+]', '', phone)
            if clean_phone.startswith('8') and len(clean_phone) == 11:
                formatted_phone = f"+7 ({clean_phone[1:4]}) {clean_phone[4:7]}-{clean_phone[7:9]}-{clean_phone[9:]}"
            elif clean_phone.startswith('7') and len(clean_phone) == 11:
                formatted_phone = f"+7 ({clean_phone[1:4]}) {clean_phone[4:7]}-{clean_phone[7:9]}-{clean_phone[9:]}"
            elif len(clean_phone) == 10:
                formatted_phone = f"+7 ({clean_phone[0:3]}) {clean_phone[3:6]}-{clean_phone[6:8]}-{clean_phone[8:]}"
            else:
                formatted_phone = phone
            found_data.append(f"номеру телефона: {formatted_phone}")
        if 'email' in contact_info:
            found_data.append(f"email: {contact_info['email']}")
        
        # Завершаем сессию
        del self.user_sessions[user_id]
        
        # Формируем финальный ответ с ИСПРАВЛЕННЫМ ТЕКСТОМ (правильные падежи)
        response = (
            f"✅ Принято! Ищем ваши билеты по {', '.join(found_data)}\n\n"
            "🔍 Проверяем в системе...\n\n"
            "Что проверяем:\n"
            "• Статус отправки билетов\n"
            "• Корректность email-адреса\n"
            "• Время отправки\n\n"
            "✅ Билеты отправлены на указанный email адрес\n"
            "📧 Проверьте папку «Спам», если не нашли письмо"
        )
        
        logger.info(f"Восстановление билетов для пользователя {user_id} по данным: {contact_info}")
        return response
        
    def has_active_session(self, user_id: int) -> bool:
        """Проверяет, есть ли активная сессия восстановления"""
        return user_id in self.user_sessions
        
    def clear_session(self, user_id: int):
        """Очищает сессию пользователя"""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]

# Класс для обработки возврата ошибочных билетов
class WrongEventRefundHandler:
    def __init__(self):
        self.user_sessions: Dict[int, Dict] = {}
        
    def start_wrong_event_session(self, user_id: int):
        """Начинает сессию возврата ошибочных билетов"""
        self.user_sessions[user_id] = {
            'step': 'waiting_order',
            'data': {},
            'created_at': datetime.now()
        }
        logger.info(f"Начата сессия возврата ошибочных билетов для пользователя {user_id}")
        
    def process_wrong_event_message(self, user_id: int, message: str) -> Optional[str]:
        """Обрабатывает сообщение в контексте возврата ошибочных билетов"""
        if user_id not in self.user_sessions:
            return None
            
        session = self.user_sessions[user_id]
        current_step = session['step']
        
        if current_step == 'waiting_order':
            return self._process_order_step(user_id, message)
        elif current_step == 'waiting_contacts':
            return self._process_contacts_step(user_id, message)
            
        return None
        
    def _process_order_step(self, user_id: int, message: str) -> str:
        """Обрабатывает шаг ввода номера заказа"""
        # Ищем номер заказа
        order_match = re.search(r'\b(\d{6})\b', message)
        if order_match:
            order_number = order_match.group(1)
            self.user_sessions[user_id]['data']['order_number'] = order_number
            self.user_sessions[user_id]['step'] = 'waiting_contacts'
            
            return (
                f"✅ Заказ №{order_number} принят для возврата ошибочных билетов!\n\n"
                "Теперь укажите ваши контактные данные:\n\n"
                "• Номер телефона (российский формат)\n"
                "• Email для связи\n\n"
                "Примеры телефонов:\n"
                "• 89991234567\n"
                "• +7 (999) 123-45-67\n"
                "• 8(999)123-45-67\n\n"
                "Пример email:\n"
                "• example@mail.ru\n\n"
                "Пожалуйста, введите контактные данные:"
            )
        else:
            return (
                "Неверный номер заказа!\n\n"
                "Номер заказа должен состоять из 6 цифр.\n"
                "Пожалуйста, введите правильный номер заказа:"
            )
    
    def _validate_phone_number(self, phone: str) -> bool:
        """Проверяет валидность российского номера телефона"""
        clean_phone = re.sub(r'[\s\(\)\-+]', '', phone)
        
        if not clean_phone.startswith(('7', '8')):
            return False
        
        if len(clean_phone) not in [10, 11]:
            return False
        
        if not clean_phone.isdigit():
            return False
        
        patterns = [
            r'^7\d{10}$',
            r'^8\d{10}$',
            r'^7\d{9}$',
            r'^8\d{9}$',
        ]
        
        for pattern in patterns:
            if re.match(pattern, clean_phone):
                return True
        
        return False

    def _extract_contact_info(self, text: str) -> Dict[str, str]:
        """Извлекает контактные данные из текста"""
        contacts = {}
        
        # Ищем email
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        if email_match:
            contacts['email'] = email_match.group(0)
        
        # Улучшенные паттерны для телефонов
        phone_patterns = [
            r'\+7\s?\(?\d{3}\)?\s?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',  # +7 (999) 123-45-67
            r'8\s?\(?\d{3}\)?\s?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',   # 8 (999) 123-45-67
            r'7\s?\(?\d{3}\)?\s?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',   # 7 (999) 123-45-67
            r'\b\d{10,11}\b',                                      # 89991234567
            r'\b\d{1}\s?\d{3}\s?\d{3}\s?\d{2}\s?\d{2}\b',         # 8 999 123 45 67
        ]
        
        found_phones = []
        for pattern in phone_patterns:
            phone_matches = re.finditer(pattern, text)
            for phone_match in phone_matches:
                phone = phone_match.group(0)
                if self._validate_phone_number(phone):
                    found_phones.append(phone)
        
        if found_phones:
            contacts['phone'] = found_phones[0]
        
        return contacts

    def _process_contacts_step(self, user_id: int, message: str) -> str:
        """Обрабатывает шаг ввода контактов"""
        contact_info = self._extract_contact_info(message)
        
        if not contact_info:
            return (
                "Не удалось распознать валидные контактные данные.\n\n"
                "Пожалуйста, укажите:\n"
                "• Российский номер телефона (10-11 цифр)\n"
                "• Или email адрес\n\n"
                "Примеры телефонов:\n"
                "• 89991234567\n"
                "• +7 (999) 123-45-67\n"
                "• 8(999)123-45-67\n\n"
                "Пример email:\n"
                "• example@mail.ru\n\n"
                "Пожалуйста, введите контактные данные в правильном формате:"
            )
        
        # Форматируем контактные данные для отображения
        contact_display = []
        if 'phone' in contact_info:
            phone = contact_info['phone']
            clean_phone = re.sub(r'[\s\(\)\-+]', '', phone)
            if clean_phone.startswith('8') and len(clean_phone) == 11:
                formatted_phone = f"+7 ({clean_phone[1:4]}) {clean_phone[4:7]}-{clean_phone[7:9]}-{clean_phone[9:]}"
            elif clean_phone.startswith('7') and len(clean_phone) == 11:
                formatted_phone = f"+7 ({clean_phone[1:4]}) {clean_phone[4:7]}-{clean_phone[7:9]}-{clean_phone[9:]}"
            elif len(clean_phone) == 10:
                formatted_phone = f"+7 ({clean_phone[0:3]}) {clean_phone[3:6]}-{clean_phone[6:8]}-{clean_phone[8:]}"
            else:
                formatted_phone = phone
            contact_display.append(f"Телефон: {formatted_phone}")
        
        if 'email' in contact_info:
            contact_display.append(f"Email: {contact_info['email']}")
        
        order_data = self.user_sessions[user_id]['data']
        order_number = order_data.get('order_number', 'неизвестен')
        
        # Формируем финальный ответ
        response = (
            "✅ Заявка на возврат ошибочных билетов принята!\n\n"
            f"Детали заявки:\n"
            f"• Номер заказа: {order_number}\n"
            f"• Причина возврата: Покупка на другое мероприятие по ошибке\n"
            f"• Контактные данные: {', '.join(contact_display)}\n\n"
            "Что дальше:\n"
            "⏰ Ожидайте звонка от специалиста в течение 24 часов\n"
            "📧 Или письмо на указанный email\n"
            "💰 Возврат денег займет до 10 рабочих дней\n\n"
            "После возврата вы сможете купить билеты на нужное мероприятие!\n\n"
            "Для срочных вопросов: +7 (999) 123-45-67\n\n"
            "Нужна помощь с чем-то еще?"
        )
        
        # Завершаем сессию
        del self.user_sessions[user_id]
        logger.info(f"Заявка на возврат ошибочных билетов завершена для заказа {order_number}")
        
        return response
        
    def has_active_session(self, user_id: int) -> bool:
        """Проверяет, есть ли активная сессию"""
        return user_id in self.user_sessions
        
    def clear_session(self, user_id: int):
        """Очищает сессию пользователя"""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]

# Класс для обработки смены email
class EmailChangeHandler:
    def __init__(self):
        self.user_sessions: Dict[int, Dict] = {}
        
    def start_email_change_session(self, user_id: int):
        """Начинает сессию смены email"""
        self.user_sessions[user_id] = {
            'step': 'waiting_order',
            'data': {},
            'created_at': datetime.now()
        }
        logger.info(f"Начата сессия смены email для пользователя {user_id}")
        
    def process_email_change_message(self, user_id: int, message: str) -> Optional[str]:
        """Обрабатывает сообщение в контексте смены email"""
        if user_id not in self.user_sessions:
            return None
            
        session = self.user_sessions[user_id]
        current_step = session['step']
        
        if current_step == 'waiting_order':
            return self._process_order_step(user_id, message)
        elif current_step == 'waiting_new_email':
            return self._process_email_step(user_id, message)
            
        return None
        
    def _process_order_step(self, user_id: int, message: str) -> str:
        """Обрабатывает шаг ввода номера заказа"""
        # Ищем номер заказа
        order_match = re.search(r'\b(\d{6})\b', message)
        if order_match:
            order_number = order_match.group(1)
            self.user_sessions[user_id]['data']['order_number'] = order_number
            self.user_sessions[user_id]['step'] = 'waiting_new_email'
            
            return (
                f"Заказ №{order_number} принят для смены email\n\n"
                "Теперь укажите новый email адрес:\n\n"
                "Примеры:\n"
                "• example@mail.ru\n"
                "• myemail@gmail.com\n"
                "• name@yandex.ru\n\n"
                "Пожалуйста, введите новый email:"
            )
        else:
            return (
                "Неверный номер заказа!\n\n"
                "Номер заказа должен состоять из 6 цифр.\n"
                "Пожалуйста, введите правильный номер заказа:"
            )
            
    def _validate_email(self, email: str) -> bool:
        """Проверяет валидность email"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
        return re.match(pattern, email) is not None
        
    def _process_email_step(self, user_id: int, message: str) -> str:
        """Обрабатывает шаг ввода нового email"""
        email = message.strip()
        
        if not self._validate_email(email):
            return (
                "Неверный формат email!\n\n"
                "Пожалуйста, введите корректный email адрес:\n\n"
                "Примеры:\n"
                "• example@mail.ru\n"
                "• myemail@gmail.com\n"
                "• name@yandex.ru\n\n"
                "Введите email еще раз:"
            )
        
        order_data = self.user_sessions[user_id]['data']
        order_number = order_data.get('order_number', 'неизвестен')
        
        # Сохраняем новый email
        self.user_sessions[user_id]['data']['new_email'] = email
        
        # Формируем финальный ответ
        response = (
            "✅ Email успешно изменен!\n\n"
            f"Детали изменения:\n"
            f"• Номер заказа: {order_number}\n"
            f"• Новый email: {email}\n\n"
            "Что дальше:\n"
            "📧 Билеты будут отправлены на новый адрес в течение 15 минут\n"
            "🔄 Старые билеты (если отправлены) станут недействительными\n"
            "✅ Новые билеты придут на указанный email\n\n"
            "Если билеты не пришли в течение 30 минут:\n"
            "• Проверьте папку «Спам»\n"
            "• Убедитесь в правильности email\n"
            "• Обратитесь к оператору\n\n"
            "Нужна помощь с чем-то еще?"
        )
        
        # Завершаем сессию
        del self.user_sessions[user_id]
        logger.info(f"Email изменен для заказа {order_number} на {email}")
        
        return response
        
    def has_active_session(self, user_id: int) -> bool:
        """Проверяет, есть ли активная сессия смены email"""
        return user_id in self.user_sessions
        
    def clear_session(self, user_id: int):
        """Очищает сессию пользователя"""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]

# Класс для обработки возврата одного билета
class PartialRefundHandler:
    def __init__(self):
        self.user_sessions: Dict[int, Dict] = {}
        
    def start_partial_refund_session(self, user_id: int):
        """Начинает сессию возврата одного билета"""
        self.user_sessions[user_id] = {
            'step': 'waiting_ticket_details',
            'data': {},
            'created_at': datetime.now()
        }
        logger.info(f"Начата сессия частичного возврата для пользователя {user_id}")
        
    def process_partial_refund_message(self, user_id: int, message: str) -> Optional[str]:
        """Обрабатывает сообщение в контексте частичного возврата"""
        if user_id not in self.user_sessions:
            return None
            
        session = self.user_sessions[user_id]
        current_step = session['step']
        
        if current_step == 'waiting_ticket_details':
            return self._process_ticket_details_step(user_id, message)
        elif current_step == 'waiting_contacts':
            return self._process_contacts_step(user_id, message)
            
        return None
        
    def _process_ticket_details_step(self, user_id: int, message: str) -> str:
        """Обрабатывает шаг ввода деталей билета"""
        # Ищем номер заказа
        order_match = re.search(r'\b(\d{6})\b', message)
        if order_match:
            order_number = order_match.group(1)
            self.user_sessions[user_id]['data']['order_number'] = order_number
            
            # Ищем номер билета или описание
            ticket_match = re.search(r'(?:билет|билета|номер)\s*(\d+)', message.lower())
            if ticket_match:
                self.user_sessions[user_id]['data']['ticket_number'] = ticket_match.group(1)
            
            # Ищем причину
            if 'болезн' in message.lower():
                self.user_sessions[user_id]['data']['reason'] = 'Болезнь'
            elif 'изменение планов' in message.lower():
                self.user_sessions[user_id]['data']['reason'] = 'Изменение планов'
            elif 'отмена мероприятия' in message.lower():
                self.user_sessions[user_id]['data']['reason'] = 'Отмена мероприятия'
            else:
                # Извлекаем причину из текста
                reason_text = self._extract_reason(message)
                if reason_text:
                    self.user_sessions[user_id]['data']['reason'] = reason_text
            
            self.user_sessions[user_id]['step'] = 'waiting_contacts'
            
            response = (
                f"Заявка на возврат одного билета из заказа №{order_number} принята!\n\n"
                "Теперь укажите ваши контактные данные:\n\n"
                "• Номер телефона (российский формат)\n"
                "• Email для связи\n\n"
                "Примеры телефонов:\n"
                "• 89991234567\n"
                "• +7 (999) 123-45-67\n"
                "• 8(999)123-45-67\n\n"
                "Пример email:\n"
                "• example@mail.ru"
            )
            return response
        else:
            return (
                "Неверный номер заказа!\n\n"
                "Номер заказа должен состоять из 6 цифр.\n"
                "Пожалуйста, введите правильный номер заказа:"
            )
    
    def _extract_reason(self, text: str) -> str:
        """Извлекает причину возврата из текста"""
        # Убираем номера заказов и билетов
        clean_text = re.sub(r'\b\d{6}\b', '', text)
        clean_text = re.sub(r'(?:билет|билета|номер)\s*\d+', '', text.lower())
        
        # Ищем ключевые фразы
        if 'болезн' in clean_text:
            return 'Болезнь'
        elif 'изменение планов' in clean_text:
            return 'Изменение планов'
        elif 'отмена мероприятия' in clean_text:
            return 'Отмена мероприятия'
        elif 'ошибк' in clean_text:
            return 'Ошибка при покупке'
        else:
            # Возвращаем первые 50 символов как причину
            return clean_text.strip()[:50] + "..." if len(clean_text.strip()) > 50 else clean_text.strip()
    
    def _validate_phone_number(self, phone: str) -> bool:
        """Проверяет валидность российского номера телефона"""
        clean_phone = re.sub(r'[\s\(\)\-+]', '', phone)
        
        if not clean_phone.startswith(('7', '8')):
            return False
        
        if len(clean_phone) not in [10, 11]:
            return False
        
        if not clean_phone.isdigit():
            return False
        
        patterns = [
            r'^7\d{10}$',
            r'^8\d{10}$',
            r'^7\d{9}$',
            r'^8\d{9}$',
        ]
        
        for pattern in patterns:
            if re.match(pattern, clean_phone):
                return True
        
        return False

    def _extract_contact_info(self, text: str) -> Dict[str, str]:
        """Извлекает контактные данные из текста"""
        contacts = {}
        
        # Ищем email
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        if email_match:
            contacts['email'] = email_match.group(0)
        
        # Улучшенные паттерны для телефонов
        phone_patterns = [
            r'\+7\s?\(?\d{3}\)?\s?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',  # +7 (999) 123-45-67
            r'8\s?\(?\d{3}\)?\s?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',   # 8 (999) 123-45-67
            r'7\s?\(?\d{3}\)?\s?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',   # 7 (999) 123-45-67
            r'\b\d{10,11}\b',                                      # 89991234567
            r'\b\d{1}\s?\d{3}\s?\d{3}\s?\d{2}\s?\d{2}\b',         # 8 999 123 45 67
        ]
        
        found_phones = []
        for pattern in phone_patterns:
            phone_matches = re.finditer(pattern, text)
            for phone_match in phone_matches:
                phone = phone_match.group(0)
                if self._validate_phone_number(phone):
                    found_phones.append(phone)
        
        if found_phones:
            contacts['phone'] = found_phones[0]
        
        return contacts

    def _process_contacts_step(self, user_id: int, message: str) -> str:
        """Обрабатывает шаг ввода контактов"""
        contact_info = self._extract_contact_info(message)
        
        if not contact_info:
            return (
                "Не удалось распознать валидные контактные данные.\n\n"
                "Пожалуйста, укажите:\n"
                "• Российский номер телефона (10-11 цифр)\n"
                "• Или email адрес\n\n"
                "Примеры телефонов:\n"
                "• 89991234567\n"
                "• +7 (999) 123-45-67\n"
                "• 8(999)123-45-67\n\n"
                "Пример email:\n"
                "• example@mail.ru\n\n"
                "Пожалуйста, введите контактные данные в правильном формате:"
            )
        
        # Форматируем контактные данные для отображения
        contact_display = []
        if 'phone' in contact_info:
            phone = contact_info['phone']
            clean_phone = re.sub(r'[\s\(\)\-+]', '', phone)
            if clean_phone.startswith('8') and len(clean_phone) == 11:
                formatted_phone = f"+7 ({clean_phone[1:4]}) {clean_phone[4:7]}-{clean_phone[7:9]}-{clean_phone[9:]}"
            elif clean_phone.startswith('7') and len(clean_phone) == 11:
                formatted_phone = f"+7 ({clean_phone[1:4]}) {clean_phone[4:7]}-{clean_phone[7:9]}-{clean_phone[9:]}"
            elif len(clean_phone) == 10:
                formatted_phone = f"+7 ({clean_phone[0:3]}) {clean_phone[3:6]}-{clean_phone[6:8]}-{clean_phone[8:]}"
            else:
                formatted_phone = phone
            contact_display.append(f"Телефон: {formatted_phone}")
        
        if 'email' in contact_info:
            contact_display.append(f"Email: {contact_info['email']}")
        
        order_data = self.user_sessions[user_id]['data']
        order_number = order_data.get('order_number', 'неизвестен')
        ticket_number = order_data.get('ticket_number', 'не указан')
        reason = order_data.get('reason', 'не указана')
        
        # Формируем финальный ответ
        response = (
            "✅ Заявка на возврат одного билета принята!\n\n"
            f"Детали заявки:\n"
            f"• Номер заказа: {order_number}\n"
            f"• Возвращаемый билет: {ticket_number}\n"
            f"• Причина возврата: {reason}\n"
            f"• Контактные данные: {', '.join(contact_display)}\n\n"
            "Что дальше:\n"
            "⏰ Ожидайте звонка от специалиста в течение 24 часов\n"
            "📧 Или письмо на указанный email\n"
            "💰 Возврат денег займет до 10 рабочих дней\n\n"
            "Для срочных вопросов: +7 (999) 123-45-67\n\n"
            "Нужна помощь с чем-то еще?"
        )
        
        # Завершаем сессию
        del self.user_sessions[user_id]
        logger.info(f"Заявка на частичный возврат завершена для заказа {order_number}")
        
        return response
        
    def has_active_session(self, user_id: int) -> bool:
        """Проверяет, есть ли активная сессия"""
        return user_id in self.user_sessions
        
    def clear_session(self, user_id: int):
        """Очищает сессию пользователя"""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]

# Класс для обработки платежей
class PaymentHandler:
    def __init__(self):
        self.user_sessions: Dict[int, Dict] = {}
        
    def start_payment_session(self, user_id: int):
        """Начинает сессию обработки платежа"""
        self.user_sessions[user_id] = {
            'step': 'waiting_details',
            'data': {},
            'created_at': datetime.now()
        }
        logger.info(f"Начата сессия оплаты для пользователя {user_id}")
        
    def process_payment_message(self, user_id: int, message: str) -> Optional[str]:
        """Обрабатывает сообщение в контексте платежа"""
        if user_id not in self.user_sessions:
            return None
            
        session = self.user_sessions[user_id]
        
        if session['step'] == 'waiting_details':
            return self._process_payment_details(user_id, message)
            
        return None
        
    def _process_payment_details(self, user_id: int, message: str) -> str:
        """Обрабатывает детали платежа"""
        # Извлекаем данные из сообщения
        data = self._extract_payment_data(message)
        
        # Проверяем номер заказа
        if 'order_number' in data:
            order_number = data['order_number']
            if len(order_number) != 6 or not order_number.isdigit():
                return "Неверный номер заказа!\n\nНомер заказа должен состоять из 6 цифр. Пожалуйста, проверьте и введите правильный номер заказа."
        
        # Сохраняем извлеченные данные
        self.user_sessions[user_id]['data'] = data
        
        # Проверяем, есть ли достаточно данных
        has_order = 'order_number' in data
        has_method = 'payment_method' in data
        has_time = 'time_minutes' in data
        
        logger.info(f"Извлеченные данные: {data}")
        
        # Если достаточно данных - выдаем решение
        if has_order and (has_method or has_time):
            response = self._generate_solution_response(data, message, user_id)
            # Завершаем сессию
            del self.user_sessions[user_id]
            return response
            
        # Если данных недостаточно - запрашиваем недостающие
        return self._request_missing_data(data)
        
    def _extract_payment_data(self, text: str) -> Dict[str, str]:
        """Извлекает данные об оплате из текста"""
        data = {}
        text_lower = text.lower()
        
        # Номер заказа (ровно 6 цифр)
        order_match = re.search(r'\b(\d{6})\b', text)
        if order_match:
            data['order_number'] = order_match.group(1)
            logger.info(f"Найден номер заказа: {data['order_number']}")
        
        # УЛУЧШЕННАЯ ОБРАБОТКА ВРЕМЕНИ
        time_data = self._extract_time_data(text_lower)
        if time_data:
            data['time_minutes'] = time_data['minutes']
            data['time_description'] = time_data['description']
            logger.info(f"Найдено время: {data['time_description']} = {data['time_minutes']} минут")
        
        # Способ оплаты с учетом опечаток
        payment_methods = {
            'мобильное приложение': ['приложен', 'приложени', 'мобильн', 'телефон', 'приложении', 'приложение', 'апп', 'app'],
            'QR-код': ['qr', 'код', 'qr-код', 'кьюар', 'кюар', 'по qr'],
            'банковская карта': ['карт', 'картой', 'карту', 'карта', 'карточк', 'кард', 'card']
        }
        
        for method, keywords in payment_methods.items():
            for keyword in keywords:
                if keyword in text_lower:
                    data['payment_method'] = method
                    logger.info(f"Найден способ оплаты: {method}")
                    break
            if 'payment_method' in data:
                break
        
        # Определяем тип проблемы
        problem_type = self._detect_problem_type(text_lower)
        if problem_type:
            data['problem_type'] = problem_type
        
        return data

    def _detect_problem_type(self, text_lower: str) -> str:
        """Определяет тип проблемы с оплатой"""
        if any(phrase in text_lower for phrase in ['дважды', 'двойн', 'два раза', 'двойное', 'дважды', 'списалась дважды']):
            return 'double_charge'
        elif any(phrase in text_lower for phrase in ['списались', 'статус ожидает оплаты', 'статус не изменился']):
            return 'money_taken_but_status_pending'
        elif any(phrase in text_lower for phrase in ['чек не пришел', 'кассовый чек', 'email не пришел']):
            return 'receipt_not_received'
        elif any(phrase in text_lower for phrase in ['платеж не прошел', 'деньги вернулись', 'сначала списались']):
            return 'payment_failed'
        elif any(phrase in text_lower for phrase in ['ошибка в процессе оплаты', 'не понятно прошел ли платеж', 'ошибка при оплате']):
            return 'unclear_status'
        
        return None

    def _extract_time_data(self, text_lower: str) -> Optional[Dict]:
        """Извлекает и преобразует время в минуты"""
        # Обработка времени в формате ЧЧ:ММ
        time_match = re.search(r'(\d{1,2}):(\d{2})', text_lower)
        if time_match:
            hour, minute = map(int, time_match.groups())
            now = datetime.now()
            
            # Предполагаем, что оплата была сегодня
            payment_time = datetime(now.year, now.month, now.day, hour, minute)
            if payment_time > now:
                # Если время в будущем, значит вчера
                payment_time = payment_time - timedelta(days=1)
            
            time_diff = now - payment_time
            minutes = int(time_diff.total_seconds() / 60)
            
            return {'minutes': str(minutes), 'description': f"сегодня в {hour:02d}:{minute:02d}"}
        
        # Сначала пытаемся найти точные совпадения
        time_data = self._extract_exact_time(text_lower)
        if time_data:
            return time_data
        
        # Затем ищем опечатки и приблизительные выражения
        time_data = self._extract_approximate_time(text_lower)
        if time_data:
            return time_data
        
        return None

    def _extract_exact_time(self, text_lower: str) -> Optional[Dict]:
        """Извлекает точные временные выражения"""
        # Минуты
        minute_match = re.search(r'(\d+)\s*(?:мин|минут|минуты|мин\.|минут\.)', text_lower)
        if minute_match:
            minutes = int(minute_match.group(1))
            return {'minutes': str(minutes), 'description': f"{minutes} минут"}
        
        # Часы
        hour_match = re.search(r'(\d+)\s*(?:час|часа|часов|час\.)', text_lower)
        if hour_match:
            hours = int(hour_match.group(1))
            minutes = hours * 60
            hour_word = "час" if hours == 1 else "часа" if 2 <= hours <= 4 else "часов"
            return {'minutes': str(minutes), 'description': f"{hours} {hour_word}"}
        
        # Дни
        day_match = re.search(r'(\d+)\s*(?:день|дня|дней|дн\.|день\.)', text_lower)
        if day_match:
            days = int(day_match.group(1))
            minutes = days * 24 * 60
            day_word = "день" if days == 1 else "дня" if 2 <= days <= 4 else "дней"
            return {'minutes': str(minutes), 'description': f"{days} {day_word}"}
        
        return None

    def _extract_approximate_time(self, text_lower: str) -> Optional[Dict]:
        """Извлекает приблизительные временные выражения и обрабатывает опечатки"""
        now = datetime.now()
        
        # Относительные временные выражения с реальными датами
        time_mapping = {
            'сегодня': (0, 'day'),  # сегодня
            'седня': (0, 'day'),
            'севодня': (0, 'day'),
            'севоня': (0, 'day'),
            'вчера': (1, 'day'),
            'вчеоа': (1, 'day'),
            'фчера': (1, 'day'),
            'позавчера': (2, 'day'),
            'позавчеа': (2, 'day'),
            'позафчера': (2, 'day'),
            'позачвера': (2, 'day'),
            'позачверя': (2, 'day'),
            'позачвеа': (2, 'day'),
            'на прошлой неделе': (7, 'day'),
            'прошлая неделя': (7, 'day'),
            'неделю назад': (7, 'day'),
            'недели назад': (7, 'day'),
            'неделя назад': (7, 'day'),
        }
        
        # Проверяем точные совпадения
        for phrase, (days_back, unit) in time_mapping.items():
            if phrase in text_lower:
                target_date = now - timedelta(days=days_back)
                description = target_date.strftime("%d.%m.%Y")
                minutes = days_back * 24 * 60
                return {'minutes': str(minutes), 'description': description}
        
        # Проверяем частичные совпадения для обработки опечаток
        for phrase, (days_back, unit) in time_mapping.items():
            if self._fuzzy_match(phrase, text_lower):
                target_date = now - timedelta(days=days_back)
                description = target_date.strftime("%d.%m.%Y")
                minutes = days_back * 24 * 60
                return {'minutes': str(minutes), 'description': description}
        
        # Попытка распознать дату в формате ДД.ММ.ГГГГ
        date_match = re.search(r'(\d{1,2})[\.\-\/](\d{1,2})[\.\-\/](\d{4})', text_lower)
        if date_match:
            try:
                day, month, year = map(int, date_match.groups())
                payment_date = datetime(year, month, day)
                time_diff = now - payment_date
                
                if time_diff.days >= 0:
                    minutes = time_diff.days * 24 * 60
                    description = f"{day:02d}.{month:02d}.{year}"
                    return {'minutes': str(minutes), 'description': description}
            except ValueError:
                pass
        
        return None

    def _fuzzy_match(self, phrase: str, text: str) -> bool:
        """Функция для нечеткого сравнения строк"""
        # Простая проверка на частичное совпадение
        words = phrase.split()
        found_words = 0
        
        for word in words:
            if len(word) > 3 and word in text:  # Ищем только слова длиннее 3 символов
                found_words += 1
        
        # Если найдено больше половины слов фразы - считаем совпадением
        return found_words >= len(words) // 2
        
    def _generate_solution_response(self, data: Dict, original_message: str, user_id: int) -> str:
        """Генерирует ответ с решением в зависимости от описания проблемы"""
        order_num = data.get('order_number', 'неизвестен')
        time_mins = data.get('time_minutes', '30')
        time_desc = data.get('time_description', 'неизвестно')
        payment_method = data.get('payment_method', 'неизвестен')
        problem_type = data.get('problem_type')
        
        message_lower = original_message.lower()
        
        # Если явно определили тип проблемы - используем его
        if not problem_type:
            problem_type = self._detect_problem_type(message_lower)
        
        # НОВАЯ ЛОГИКА: если пользователь не может разобраться - подключаем оператора
        if detect_need_help(original_message):
            response = (
                f"🤔 По заказу №{order_num} требуется уточнение\n\n"
                "Я вижу, что вам нужна помощь, но проблема не совсем ясна.\n\n"
                "📞 Подключаю оператора для детальной консультации\n"
                "⏰ Ожидайте ответа в течение 2-5 минут\n\n"
                "Оператор поможет:\n"
                "• Разобраться с вашей конкретной ситуацией\n"
                "• Проверить статус платежа в системе\n"
                "• Предоставить персонализированное решение"
            )
            
            # Уведомляем оператора
            if OPERATOR_CHAT_ID is not None:
                asyncio.create_task(call_operator(
                    types.User(id=user_id, first_name="Пользователь", is_bot=False), 
                    f"Неясная проблема с оплатой заказа {order_num}. Сообщение: {original_message}"
                ))
            return response
        
        # Определяем тип проблемы и генерируем соответствующий ответ
        if problem_type == 'double_charge' or any(phrase in message_lower for phrase in ['дважды', 'двойн', 'два раза', 'списалась дважды']):
            response = (
                f"⚠️ По заказу №{order_num} обнаружено двойное списание\n\n"
                "Проблема: Произошло двойное списание средств\n\n"
                "💡 Решение:\n"
                "• Один из платежей будет автоматически возвращен\n"
                "• Возврат займет 3-5 рабочих дней\n"
                "• Билеты активны по первому успешному платежу\n\n"
                "📞 Для ускорения возврата обратитесь в поддержку\n"
                "⏰ Возврат произойдет автоматически в течение 5 дней"
            )
        
        elif problem_type == 'money_taken_but_status_pending' or any(phrase in message_lower for phrase in ['деньги списались', 'статус ожидает оплаты', 'статус не изменился']):
            response = (
                f"✅ По заказу №{order_num} разобрался!\n\n"
                "Проблема: Деньги списались, но статус не обновился\n\n"
                "💡 Решение:\n"
                "• Это временная задержка синхронизации (15-30 минут)\n"
                "• Статус автоматически обновится\n"
                "• Билеты придут после обновления статуса\n\n"
                "⏰ Подождите еще 20 минут\n"
                "📧 Проверьте email и папку «Спам»\n"
                "🔄 Если не помогло - обратитесь в поддержку"
            )
        
        elif problem_type == 'receipt_not_received' or any(phrase in message_lower for phrase in ['чек не пришел', 'кассовый чек', 'email не пришел']):
            response = (
                f"📧 По заказу №{order_num} проблема с чеком\n\n"
                "Проблема: Кассовый чек не пришел на email\n\n"
                "💡 Решение:\n"
                "• Чек отправляется отдельно от билетов\n"
                "• Проверьте папку «Спам» и «Рассылки»\n"
                "• Чек может прийти с задержкой до 2 часов\n\n"
                "🔄 Чек будет отправлен повторно в течение часа\n"
                "📞 Если не придет - обратитесь в поддержку"
            )
        
        elif problem_type == 'payment_failed' or any(phrase in message_lower for phrase in ['платеж не прошел', 'деньги вернулись', 'сначала списались']):
            response = (
                f"🔄 По заказу №{order_num} проблема с платежом\n\n"
                "Проблема: Платеж не завершился, деньги вернулись\n\n"
                "💡 Решение:\n"
                "• Это временный холд (блокировка) средств\n"
                "• Деньги автоматически разблокируются в течение 24 часов\n"
                "• Повторите оплату через 30-60 минут\n\n"
                "💳 Используйте тот же способ оплаты\n"
                "⏰ Подождите разблокировки перед повторной оплатой"
            )
        
        elif problem_type == 'unclear_status' or any(phrase in message_lower for phrase in ['ошибка в процессе оплаты', 'не понятно прошел ли платеж', 'ошибка при оплате']):
            response = (
                f"❓ По заказу №{order_num} неясный статус платежа\n\n"
                "Проблема: Непонятно, прошел ли платеж\n\n"
                "💡 Решение:\n"
                "• Проверьте историю операций в банковском приложении\n"
                "• Подождите 15 минут для обновления статуса\n"
                "• Если есть списание - платеж прошел\n\n"
                "📱 Проверьте мобильное банковское приложение\n"
                "⏰ Статус обновится в течение 15 минут\n"
                "📞 Если сомнения остаются - обратитесь в поддержку"
            )
        
        else:
            # Стандартный ответ для других случаев
            response = (
                f"✅ По заказу №{order_num} разобрался!\n\n"
                f"• Оплата через: {payment_method}\n"
                f"• Время оплаты: {time_desc}\n"
                f"• Статус: Обрабатывается\n\n"
                "💡 Рекомендации:\n"
                "1️⃣ Подождите 15-20 минут\n"
                "2️⃣ Проверьте email и папку «Спам»\n"
                "3️⃣ Если статус не изменится - обратитесь в поддержку\n\n"
                "Телефон поддержки: +7 (999) 123-45-67"
            )
        
        return response + "\n\nНужна помощь с чем-то еще?"
        
    def _request_missing_data(self, data: Dict) -> str:
        """Запрашивает недостающие данные"""
        missing = []
        
        if 'order_number' not in data:
            missing.append("номер заказа (6 цифр)")
        if 'payment_method' not in data:
            missing.append("способ оплаты")
        if 'time_minutes' not in data:
            missing.append("время оплаты")
        
        if missing:
            return (
                "Уточните, пожалуйста:\n\n"
                f"Для решения проблемы нужен {' и '.join(missing)}\n\n"
                "Пример правильного формата:\n"
                "• Номер заказа: 123456 (ровно 6 цифр)\n"
                "• Оплатил картой/приложением/QR-кодом\n"
                "• Время оплаты: 30 минут назад, вчера, 25.12.2024"
            )
        
        return "Что-то пошло не так. Попробуйте еще раз."
        
    def has_active_session(self, user_id: int) -> bool:
        """Проверяет, есть ли активная сессия"""
        return user_id in self.user_sessions
        
    def clear_session(self, user_id: int):
        """Очищает сессию пользователя"""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]

# Класс для обработки возвратов
class RefundHandler:
    def __init__(self):
        self.user_sessions: Dict[int, Dict] = {}
        self.refund_requests: Dict[int, Dict] = {}
        
    def start_refund_session(self, user_id: int):
        """Начинает сессию обработки возврата"""
        self.user_sessions[user_id] = {
            'step': 'waiting_order',
            'data': {},
            'created_at': datetime.now()
        }
        logger.info(f"Начата сессия возврата для пользователя {user_id}")
        
    def process_refund_message(self, user_id: int, message: str) -> Optional[str]:
        """Обрабатывает сообщение в контексте возврата"""
        if user_id not in self.user_sessions:
            return None
            
        session = self.user_sessions[user_id]
        current_step = session['step']
        
        if current_step == 'waiting_order':
            return self._process_order_step(user_id, message)
        elif current_step == 'waiting_reason':
            return self._process_reason_step(user_id, message)
        elif current_step == 'waiting_contacts':
            return self._process_contacts_step(user_id, message)
            
        return None
        
    def _process_order_step(self, user_id: int, message: str) -> str:
        """Обрабатывает шаг ввода номера заказа"""
        # Ищем номер заказа
        order_match = re.search(r'\b(\d{6})\b', message)
        if order_match:
            order_number = order_match.group(1)
            self.user_sessions[user_id]['data']['order_number'] = order_number
            self.user_sessions[user_id]['step'] = 'waiting_reason'
            
            return (
                "Теперь укажите причину возврата:\n\n"
                "• Болезнь\n"
                "• Изменение планов\n" 
                "• Отмена мероприятия\n"
                "• Другая причина\n\n"
                "Опишите подробнее, почему хотите вернуть билеты:"
            )
        else:
            return (
                "Неверный номер заказа!\n\n"
                "Номер заказа должен состоять из 6 цифр.\n"
                "Пожалуйста, введите правильный номер заказа:"
            )
            
    def _process_reason_step(self, user_id: int, message: str) -> str:
        """Обрабатывает шаг ввода причины"""
        reason = message.strip().lower()
        self.user_sessions[user_id]['data']['reason'] = message
        self.user_sessions[user_id]['step'] = 'waiting_contacts'
        
        # ДОБАВЛЯЕМ ДОПОЛНИТЕЛЬНЫЙ ТЕКСТ В ЗАВИСИМОСТИ ОТ ПРИЧИНЫ
        additional_text = ""
        
        if 'болезн' in reason:
            additional_text = (
                "\n\n🏥 Для возврата по болезни:\n"
                "Пожалуйста, отправьте документы, подтверждающие болезнь, на нашу рабочую почту: info@intickets.ru\n\n"
                "Подходящие документы:\n"
                "• Справка от врача\n"
                "• Больничный лист\n"
                "• Выписка из медицинской карты\n\n"
                "После получения документов мы обработаем ваш возврат в течение 24 часов."
            )
        elif 'изменение планов' in reason:
            additional_text = (
                "\n\n📅 Условия возврата при изменении планов:\n\n"
                "Обратите внимание, что при возврате билетов действуют следующие условия:\n\n"
                "• Менее, чем за 3 дня до начала мероприятия - деньги не возвращаются\n"
                "• от 3 до 5 дней до начала мероприятия - возвращается 30% стоимости\n"
                "• от 5 до 10 дней до начала мероприятия - возвращается 50% стоимости\n"
                "• от 10 дней и более - возвращается 100% стоимости\n\n"
                "Сроки рассчитываются от даты мероприятия."
            )
        elif 'отмена мероприятия' in reason:
            additional_text = (
                "\n\n❌ Возврат при отмене мероприятия:\n\n"
                "Если мероприятие отменено:\n\n"
                "✅ Автоматический возврат:\n"
                "• Деньги вернутся на карту, с которой была оплата, в течение 5–10 рабочих дней.\n"
                "• Уведомление придет на ваш email.\n"
                "• Никаких дополнительных действий не требуется."
            )
        
        return (
            "Теперь укажите ваши контактные данные:\n\n"
            "• Номер телефона (российский формат)\n"
            "• Email для связи\n\n"
            "Примеры телефонов:\n"
            "89991234567\n"
            "+7 (999) 123-45-67\n"
            "8(999)123-45-67\n\n"
            "Пример email:\n"
            "example@mail.ru" + additional_text
        )
        
    def _validate_phone_number(self, phone: str) -> bool:
        """Проверяет валидность российского номера телефона"""
        # Очищаем номер от пробелов, скобок, дефисов
        clean_phone = re.sub(r'[\s\(\)\-+]', '', phone)
        
        # Должен быть только российский номер
        if not clean_phone.startswith(('7', '8')):
            return False
        
        # Проверяем длину (10 или 11 цифр)
        if len(clean_phone) not in [10, 11]:
            return False
        
        # Проверяем, что все символы - цифры
        if not clean_phone.isdigit():
            return False
        
        # Проверяем российские форматы номеров более строго
        patterns = [
            r'^7\d{10}$',      # 79991234567 (11 цифр)
            r'^8\d{10}$',      # 89991234567 (11 цифр)
            r'^7\d{9}$',       # 7999123456 (10 цифр)
            r'^8\d{9}$',       # 8999123456 (10 цифр)
        ]
        
        for pattern in patterns:
            if re.match(pattern, clean_phone):
                return True
        
        return True  # Более мягкая валидация

    def _extract_contact_info(self, text: str) -> Dict[str, str]:
        """Извлекает контактные данные из текста"""
        contacts = {}
        
        # Ищем email
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        if email_match:
            contacts['email'] = email_match.group(0)
        
        # Улучшенные паттерны для телефонов
        phone_patterns = [
            r'\+7\s?\(?\d{3}\)?\s?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',  # +7 (999) 123-45-67
            r'8\s?\(?\d{3}\)?\s?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',   # 8 (999) 123-45-67
            r'7\s?\(?\d{3}\)?\s?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}',   # 7 (999) 123-45-67
            r'\b\d{10,11}\b',                                      # 89991234567
            r'\b\d{1}\s?\d{3}\s?\d{3}\s?\d{2}\s?\d{2}\b',         # 8 999 123 45 67
        ]
        
        found_phones = []
        for pattern in phone_patterns:
            phone_matches = re.finditer(pattern, text)
            for phone_match in phone_matches:
                phone = phone_match.group(0)
                if self._validate_phone_number(phone):
                    found_phones.append(phone)
        
        # Берем только первый валидный номер
        if found_phones:
            contacts['phone'] = found_phones[0]
        
        return contacts

    def _process_contacts_step(self, user_id: int, message: str) -> str:
        """Обрабатывает шаг ввода контактов"""
        # Извлекаем контактные данные
        contact_info = self._extract_contact_info(message)
        
        # Проверяем, что есть хотя бы один валидный контакт
        if not contact_info:
            return (
                "Не удалось распознать валидные контактные данные.\n\n"
                "Пожалуйста, укажите:\n"
                "• Российский номер телефона (10-11 цифр)\n"
                "• Или email адрес\n\n"
                "Примеры телефонов:\n"
                "• 89991234567\n"
                "• +7 (999) 123-45-67\n"
                "• 8(999)123-45-67\n\n"
                "Пример email:\n"
                "• example@mail.ru\n\n"
                "Пожалуйста, введите контактные данные в правильном формате:"
            )
        
        # Форматируем контактные данные для отображения
        contact_display = []
        if 'phone' in contact_info:
            # Форматируем телефон для красивого отображения
            phone = contact_info['phone']
            clean_phone = re.sub(r'[\s\(\)\-+]', '', phone)
            if clean_phone.startswith('8') and len(clean_phone) == 11:
                formatted_phone = f"+7 ({clean_phone[1:4]}) {clean_phone[4:7]}-{clean_phone[7:9]}-{clean_phone[9:]}"
            elif clean_phone.startswith('7') and len(clean_phone) == 11:
                formatted_phone = f"+7 ({clean_phone[1:4]}) {clean_phone[4:7]}-{clean_phone[7:9]}-{clean_phone[9:]}"
            elif len(clean_phone) == 10:
                formatted_phone = f"+7 ({clean_phone[0:3]}) {clean_phone[3:6]}-{clean_phone[6:8]}-{clean_phone[8:]}"
            else:
                formatted_phone = phone
            contact_display.append(f"Телефон: {formatted_phone}")
        
        if 'email' in contact_info:
            contact_display.append(f"Email: {contact_info['email']}")
        
        order_data = self.user_sessions[user_id]['data']
        order_number = order_data.get('order_number', 'неизвестен')
        reason = order_data.get('reason', 'не указана')
        
        # Сохраняем заявку
        self.refund_requests[user_id] = {
            'order_number': order_number,
            'reason': reason,
            'contacts': contact_info,
            'created_at': datetime.now()
        }
        
        # Формируем финальный ответ
        response = (
            "Заявка на возврат принята!\n\n"
            f"Детали заявки:\n"
            f"• Номер заказа: {order_number}\n"
            f"• Причина возврата: {reason}\n"
            f"• Контактные данные: {', '.join(contact_display)}\n\n"
            "Что дальше:\n"
            "⏰ Ожидайте звонка от нашего специалиста в течение 24 часов\n"
            "📧 Или письмо на указанный email\n"
            "💰 Возврат денег займет до 10 рабочих дней\n\n"
            "Для срочных вопросов: +7 (999) 123-45-67\n\n"
            "Нужна помощь с чем-то еще?"
        )
        
        # Завершаем сессию
        del self.user_sessions[user_id]
        logger.info(f"Заявка на возврат завершена для заказа {order_number}")
        
        return response
        
    def has_active_session(self, user_id: int) -> bool:
        """Проверяет, есть ли активная сессия возврата"""
        return user_id in self.user_sessions
        
    def clear_session(self, user_id: int):
        """Очищает сессию пользователя"""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]

# Инициализация
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Настройка базы данных из конфига
engine = create_async_engine(config.DATABASE_URL, echo=False)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Инициализация сервисов
ds_service = DeepSeekService()
payment_handler = PaymentHandler()
refund_handler = RefundHandler()
email_change_handler = EmailChangeHandler()
partial_refund_handler = PartialRefundHandler()
wrong_event_handler = WrongEventRefundHandler()
operator_handler = OperatorHandler()
ticket_recovery_handler = TicketRecoveryHandler()
order_manager = OrderResponseManager()

# ID оператора из конфига
OPERATOR_CHAT_ID = config.OPERATOR_CHAT_ID
logger.info(f"OPERATOR_CHAT_ID: {OPERATOR_CHAT_ID}")

# Основная клавиатура
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💳 Проблема с оплатой"), KeyboardButton(text="🔄 Возврат билетов")],
            [KeyboardButton(text="📧 Билеты не пришли/Восстановить"), KeyboardButton(text="🎫 Как купить билеты")],
            [KeyboardButton(text="🆘 Помощь"), KeyboardButton(text="🔄 Перезапустить")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие или напишите вопрос..."
    )

# Клавиатура для помощи с частыми вопросами
def get_help_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Связаться с оператором"), KeyboardButton(text="🌐 Сайт Intickets")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите вопрос или напишите свой..."
    )

async def call_operator(user: types.User, problem_description: str):
    """Вызывает оператора - сообщение уходит ТОЛЬКО оператору, пользователь НЕ видит"""
    try:
        if OPERATOR_CHAT_ID is None:
            logger.info("OPERATOR_CHAT_ID не установлен (режим тестирования) - оператор не уведомлен")
            return
            
        operator_message = (
            f"ТРЕБУЕТСЯ ОПЕРАТОР\n\n"
            f"Клиент: {user.first_name} {user.last_name or ''} (@{user.username or 'нет'})\n"
            f"ID: {user.id}\n"
            f"Проблема: {problem_description}\n\n"
            f"Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}"
        )
        
        await bot.send_message(
            chat_id=OPERATOR_CHAT_ID,
            text=operator_message
        )
        logger.info(f"Оператор уведомлен о клиенте {user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка при вызове оператора: {e}")

@dp.message(Command("start"))
async def start_command(message: types.Message):
    """Обработчик команды /start"""
    try:
        welcome_text = (
            "Добро пожаловать в поддержку Intickets!\n\n"
            "Я ваш AI-помощник. Помогу с:\n"
            "• Покупкой и оплатой билетов\n"
            "• Возвратом билетов\n"
            "• Ответами на вопросы\n\n"
            "Просто напишите ваш вопрос или используйте кнопки ниже!\n\n"
            "🔄 Чтобы перезапустить бот, используйте команду /restart или кнопку \"🔄 Перезапустить\""
        )
        
        await message.answer(welcome_text, reply_markup=get_main_keyboard())
        logger.info(f"Пользователь {message.from_user.id} начал диалог")
            
    except Exception as e:
        logger.error(f"Ошибка в start_command: {e}", exc_info=True)

# Добавляем обработку вопросов о себе и возможностях бота
@dp.message(F.text.contains("расскажи о себе"))
@dp.message(F.text.contains("что ты умеешь"))
@dp.message(F.text.contains("твои возможности"))
@dp.message(F.text.contains("о себе"))
async def about_bot(message: types.Message):
    """Обработчик вопросов о боте и его возможностях"""
    about_text = (
        "🤖 Обо мне:\n\n"
        "Я AI-помощник службы поддержки Intickets. Вот что я умею:\n\n"
        "💳 **Помощь с оплатой:**\n"
        "• Проверка статуса платежа\n"
        "• Решение проблем с двойным списанием\n"
        "• Восстановление чеков\n"
        "• Консультация по способам оплаты\n\n"
        "🎫 **Работа с билетами:**\n"
        "• Проверка статуса заказа\n"
        "• Восстановление билетов\n"
        "• Повторная отправка на email\n"
        "• Консультация по получению\n\n"
        "🔄 **Возвраты:**\n"
        "• Оформление возврата билетов\n"
        "• Консультация по условиям возврата\n"
        "• Помощь с возвратом ошибочных покупок\n"
        "• Частичный возврат\n\n"
        "📞 **Связь с оператором:**\n"
        "• Быстрый вызов специалиста\n"
        "• Помощь в сложных ситуациях\n"
        "• Консультация по уникальным случаям\n\n"
        "Я постоянно учусь и улучшаюсь, чтобы помогать вам лучше! ✨"
    )
    await message.answer(about_text, reply_markup=get_main_keyboard())

@dp.message(Command("restart"))
async def restart_command(message: types.Message):
    """Обработчик команды /restart - перезапускает бота"""
    try:
        # Очищаем все активные сессии пользователя
        user_id = message.from_user.id
        if payment_handler.has_active_session(user_id):
            payment_handler.clear_session(user_id)
        if refund_handler.has_active_session(user_id):
            refund_handler.clear_session(user_id)
        if email_change_handler.has_active_session(user_id):
            email_change_handler.clear_session(user_id)
        if partial_refund_handler.has_active_session(user_id):
            partial_refund_handler.clear_session(user_id)
        if wrong_event_handler.has_active_session(user_id):
            wrong_event_handler.clear_session(user_id)
        if operator_handler.has_active_session(user_id):
            operator_handler.clear_session(user_id)
        if ticket_recovery_handler.has_active_session(user_id):
            ticket_recovery_handler.clear_session(user_id)
        
        restart_text = (
            "🔄 Бот перезапущен!\n\n"
            "Все активные сессии очищены. Чем могу помочь?\n\n"
            "Выберите действие или напишите вопрос:"
        )
        
        await message.answer(restart_text, reply_markup=get_main_keyboard())
        logger.info(f"Пользователь {message.from_user.id} перезапустил бота")
            
    except Exception as e:
        logger.error(f"Ошибка в restart_command: {e}", exc_info=True)
        await message.answer("Произошла ошибка при перезапуске. Попробуйте еще раз.")

@dp.message(F.text == "🔄 Перезапустить")
async def restart_button(message: types.Message):
    """Обработчик кнопки перезапуска"""
    try:
        # Очищаем все активные сессии пользователя
        user_id = message.from_user.id
        if payment_handler.has_active_session(user_id):
            payment_handler.clear_session(user_id)
        if refund_handler.has_active_session(user_id):
            refund_handler.clear_session(user_id)
        if email_change_handler.has_active_session(user_id):
            email_change_handler.clear_session(user_id)
        if partial_refund_handler.has_active_session(user_id):
            partial_refund_handler.clear_session(user_id)
        if wrong_event_handler.has_active_session(user_id):
            wrong_event_handler.clear_session(user_id)
        if operator_handler.has_active_session(user_id):
            operator_handler.clear_session(user_id)
        if ticket_recovery_handler.has_active_session(user_id):
            ticket_recovery_handler.clear_session(user_id)
        
        restart_text = (
            "🔄 Бот перезапущен!\n\n"
            "Все активные сессии очищены. Чем могу помочь?\n\n"
            "Выберите действие или напишите вопрос:"
        )
        
        await message.answer(restart_text, reply_markup=get_main_keyboard())
        logger.info(f"Пользователь {message.from_user.id} перезапустил бота через кнопку")
            
    except Exception as e:
        logger.error(f"Ошибка в restart_button: {e}")
        await message.answer("Произошла ошибка при перезапуске. Попробуйте еще раз.")

@dp.message(Command("operator"))
async def operator_command(message: types.Message):
    """Прямой вызов оператора"""
    try:
        # Начинаем сессию вызова оператора
        operator_handler.start_operator_session(message.from_user.id)
        
        response = (
            "📞 Связь с оператора\n\n"
            "Пожалуйста, опишите вашу проблему подробнее, чтобы оператор мог быстрее вам помочь:\n\n"
            "• Что именно произошло?\n"
            "• Номер заказа (если есть)\n"
            "• Какая помощь требуется?\n\n"
            "Опишите проблему одним сообщением:"
        )
        await message.answer(response, reply_markup=get_main_keyboard())
        logger.info(f"Пользователь {message.from_user.id} начал вызов оператора через команду")
            
    except Exception as e:
        logger.error(f"Ошибка в operator_command: {e}")
        await message.answer("Ошибка при вызове оператора. Попробуйте еще раз.")

@dp.message(F.text == "💳 Проблема с оплатой")
async def payment_issue_button(message: types.Message):
    """Обработчик кнопки проблем с оплатой"""
    try:
        payment_handler.start_payment_session(message.from_user.id)
        
        response = (
            "💳 Проблема с оплатой\n\n"
            "Чтобы мы могли помочь, опишите вашу проблему одним сообщением, указав:\n\n"
            "• Номер заказа (6 цифр, например: 123456)\n\n"
            "• Способ оплаты (карта/приложение/QR-код)\n\n"
            "• Время оплаты (например: 30 минут назад, вчера, 25.12.2024)\n\n"
            "• Описание проблемы:\n"
            "- Деньги списались, статус заказа \"ожидает оплаты\"\n"
            "- Двойное списание средств за один заказ.\n"
            "- На email не пришел кассовый чек за оплаченный заказ\n"
            "- Платеж не прошел, деньги вернулись на карту \n"
            "- Не понятно, прошел ли платеж.\n"
            "- Другое"
        )
        await message.answer(response, reply_markup=get_main_keyboard())
        logger.info(f"Пользователь {message.from_user.id} начал диалог по оплате")
            
    except Exception as e:
        logger.error(f"Ошибка в payment_issue_button: {e}")
        await message.answer("Произошла ошибка при обработке запроса.")

@dp.message(F.text == "🔄 Возврат билетов")
async def refund_button(message: types.Message):
    """Обработчик кнопки возврата билетов"""
    try:
        # Очищаем возможные предыдущие сессии
        user_id = message.from_user.id
        if refund_handler.has_active_session(user_id):
            refund_handler.clear_session(user_id)
        
        # Начинаем новую сессию
        refund_handler.start_refund_session(user_id)
        
        response = (
            "🔄 Возврат билетов\n\n"
            "Для оформления возврата укажите, пожалуйста, номер вашего заказа (6 цифр).\n\n"
            "Пример: 456321"
        )
        await message.answer(response, reply_markup=get_main_keyboard())
        logger.info(f"Пользователь {message.from_user.id} начал оформление возврата")
            
    except Exception as e:
        logger.error(f"Ошибка в refund_button: {e}")
        await message.answer("Произошла ошибка при обработке запроса.")

@dp.message(F.text == "📧 Билеты не пришли/Восстановить")
async def tickets_not_received_main(message: types.Message):
    """Обработчик кнопки 'Билеты не пришли/Восстановить' в главном меню"""
    try:
        # Начинаем сессию восстановления билетов
        ticket_recovery_handler.start_recovery_session(message.from_user.id)
        
        response = (
            "📧 Проблемы с билетами\n\n"
            "🔍 Сначала попробуйте восстановить билеты самостоятельно:\n"
            "1. Зайдите на сайт Intickets.ru\n"
            "2. Перейдите во вкладку Для зрителей\n"
            "3. Воспользуйтесь сервисом восстановления билетов\n\n"
            "---\n\n"
            "🔄 Если не получилось восстановить билеты:\n"
            "Для повторной отправки билетов укажите:\n\n"
            "• Номер заказа (6 цифр) ИЛИ\n"
            "• Номер телефона, который использовали при заказе ИЛИ\n"
            "• Email, на который покупали билеты\n\n"
            "✅ Пример номера заказа: 123456\n"
            "✅ Пример телефона: +7 (912) 345-67-89\n"
            "✅ Пример email: example@mail.ru\n\n"
            "Билеты будут отправлены повторно в течение 15 минут!"
        )
        await message.answer(response, reply_markup=get_main_keyboard())
        logger.info(f"Пользователь {message.from_user.id} начал восстановление билетов")
            
    except Exception as e:
        logger.error(f"Ошибка в tickets_not_received_main: {e}")
        await message.answer("Произошла ошибка при обработке запроса.")

@dp.message(F.text == "🎫 Как купить билеты")
async def how_to_buy_tickets_main(message: types.Message):
    """Обработчик кнопки 'Как купить билеты' в главном меню"""
    response = (
        "🎫 Как купить билеты:\n\n"
        "1. Перейдите на официальный сайт наших партнеров (Театр Моссовета, Сфера и др.)\n"
        "2. Выберите мероприятие и дату\n"
        "3. Выберите места в зале\n"
        "4. Заполните данные для получения билетов\n"
        "5. Оплатите заказ картой или другим способом\n"
        "6. Билеты придут на указанный email\n\n"
        "Если возникли проблемы с оплатой или билеты не пришли - обращайтесь!"
    )
    await message.answer(response, reply_markup=get_main_keyboard())

@dp.message(F.text == "🆘 Помощь")
async def help_button(message: types.Message):
    """Обработчик кнопки помощи"""
    try:
        response = (
            "🆘 Помощь\n\n"
            "Частые вопросы и разделы:\n\n"
            "💳 Проблемы с оплатой - помощь с платежами\n"
            "🔄 Возврат билетов - условия и процедура возврата\n"
            "📧 Билеты не пришли/Восстановить - решение проблем с доставкой\n"
            "🎫 Как купить билеты - инструкция по покупке\n\n"
            "Дополнительные опции:\n"
            "📞 Связаться с оператором - связь со специалистом\n"
            "🌐 Сайт Intickets - официальные ресурсы\n"
            "🔄 Перезапустить - очистить все сессии\n\n"
            "Выберите нужный раздел или напишите вопрос!"
        )
        await message.answer(response, reply_markup=get_help_keyboard())
        logger.info(f"Пользователь {message.from_user.id} запросил помощь")
            
    except Exception as e:
        logger.error(f"Ошибка в help_button: {e}")
        await message.answer("Произошла ошибка при обработке запроса.")

# Обработчики для кнопок помощи
@dp.message(F.text == "📞 Связаться с оператором")
async def operator_from_help(message: types.Message):
    """Обработчик вызова оператора из меню помощи"""
    try:
        # Начинаем сессию вызова оператора
        operator_handler.start_operator_session(message.from_user.id)
        
        response = (
            "📞 Связь с оператором\n\n"
            "Пожалуйста, опишите вашу проблему подробнее, чтобы оператор мог быстрее вам помочь:\n\n"
            "• Что именно произошло?\n"
            "• Номер заказа (если есть)\n"
            "• Какая помощь требуется?\n\n"
            "Опишите проблему одним сообщением:"
        )
        await message.answer(response, reply_markup=get_help_keyboard())
        logger.info(f"Пользователь {message.from_user.id} начал вызов оператора из меню помощи")
            
    except Exception as e:
        logger.error(f"Ошибка в operator_from_help: {e}")
        await message.answer("Ошибка при вызове оператора. Попробуйте еще раз.")

@dp.message(F.text == "🌐 Сайт Intickets")
async def website_from_help(message: types.Message):
    """Обработчик кнопки сайта из меню помощи"""
    try:
        response = (
            "🌐 Официальные ресурсы Intickets:\n\n"
            "• Основной сайт: https://intickets.ru\n"
            "• FAQ с вопросами: https://intickets.ru/faq\n"
            "• Поддержка: support@intickets.ru\n\n"
            "Выберите нужный раздел или задайте вопрос!"
        )
        await message.answer(response, reply_markup=get_help_keyboard())
        logger.info(f"Пользователь {message.from_user.id} запросил ссылки на сайт из помощи")
            
    except Exception as e:
        logger.error(f"Ошибка в website_from_help: {e}")
        await message.answer("Произошла ошибка при обработке запроса.")

@dp.message(F.text == "⬅️ Назад")
async def back_to_main(message: types.Message):
    """Обработчик кнопки назад"""
    try:
        response = "Главное меню. Чем могу помочь?"
        await message.answer(response, reply_markup=get_main_keyboard())
        logger.info(f"Пользователь {message.from_user.id} вернулся в главное меню")
            
    except Exception as e:
        logger.error(f"Ошибка в back_to_main: {e}")
        await message.answer("Произошла ошибка. Попробуйте еще раз.")

@dp.message()
async def handle_all_messages(message: types.Message):
    """Обработчик всех остальных сообщений (текст от пользователя)"""
    try:
        logger.info(f"Сообщение от {message.from_user.id}: {message.text}")
        
        user_id = message.from_user.id
        message_text = message.text.lower()
        
        # 0. Сначала проверяем активные сессии вызова оператора (ВЫСШИЙ ПРИОРИТЕТ)
        if operator_handler.has_active_session(user_id):
            operator_response = operator_handler.process_operator_message(user_id, message.text)
            if operator_response:
                await message.answer(operator_response, reply_markup=get_main_keyboard())
                return

        # 1. Проверяем активные сессии восстановления билетов
        if ticket_recovery_handler.has_active_session(user_id):
            recovery_response = ticket_recovery_handler.process_recovery_message(user_id, message.text)
            if recovery_response:
                await message.answer(recovery_response, reply_markup=get_main_keyboard())
                return
            else:
                # Если в сессии восстановления не распознаны данные, просим уточнить
                response = (
                    "Не удалось распознать контактные данные. Пожалуйста, укажите:\n\n"
                    "• Номер заказа (6 цифр) ИЛИ\n"
                    "• Номер телефона ИЛИ\n"
                    "• Email\n\n"
                    "Пример: 123456, +79123456789 или example@mail.ru"
                )
                await message.answer(response, reply_markup=get_main_keyboard())
                return

        # 2. Проверяем активные сессии возврата ошибочных билетов
        if wrong_event_handler.has_active_session(user_id):
            wrong_event_response = wrong_event_handler.process_wrong_event_message(user_id, message.text)
            if wrong_event_response:
                await message.answer(wrong_event_response, reply_markup=get_main_keyboard())
                return

        # 3. Проверяем активные сессии смены email
        if email_change_handler.has_active_session(user_id):
            email_response = email_change_handler.process_email_change_message(user_id, message.text)
            if email_response:
                await message.answer(email_response, reply_markup=get_main_keyboard())
                return

        # 4. Проверяем активные сессии частичного возврата
        if partial_refund_handler.has_active_session(user_id):
            partial_refund_response = partial_refund_handler.process_partial_refund_message(user_id, message.text)
            if partial_refund_response:
                await message.answer(partial_refund_response, reply_markup=get_main_keyboard())
                return

        # 5. Проверяем активные сессии возвратов
        if refund_handler.has_active_session(user_id):
            refund_response = refund_handler.process_refund_message(user_id, message.text)
            if refund_response:
                await message.answer(refund_response, reply_markup=get_main_keyboard())
                return
        
        # 6. Проверяем активные сессии оплаты
        if payment_handler.has_active_session(user_id):
            payment_response = payment_handler.process_payment_message(user_id, message.text)
            if payment_response:
                await message.answer(payment_response, reply_markup=get_main_keyboard())
                return
        
        # Показываем "печатает"
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        # 7. Проверяем благодарности и положительные отзывы (ВЫСОКИЙ ПРИОРИТЕТ)
        if detect_thanks_and_praise(message.text):
            logger.info(f"Обнаружена благодарность у пользователя {user_id}")
            thanks_responses = [
                "Ого, спасибо за такие теплые слова! 😊 Очень приятно слышать! Рад, что смог помочь!",
                "Вау, спасибо за комплимент! 🤗 Это мотивирует становиться еще лучше!",
                "Офигенно! Спасибо за отзыв! 🎉 Рад, что все работает как надо!",
                "Благодарю за добрые слова! 😇 Очень приятно помогать таким отзывчивым пользователям!",
                "Спасибо! Вы делаете мой день лучше! ✨ Рад, что смог быть полезен!",
                "Вау, как приятно! Спасибо за обратную связь! 🌟 Продолжаем в том же духе!",
                "Огромное спасибо! Такие слова вдохновляют на новые свершения! 🚀",
                "Благодарю! Очень рад, что вам понравилось! 😎 Буду и дальше стараться!",
                "Спасибо за высокую оценку! 💫 Это лучшая награда для меня!",
                "Вау, я растроган! Спасибо за такие слова! 🥰 Буду и дальше помогать!"
            ]
            response = random.choice(thanks_responses)
            await message.answer(response, reply_markup=get_main_keyboard())
            return
        
        # 8. Проверяем недовольство
        if detect_dissatisfaction_improved(message.text):
            logger.info(f"Обнаружено недовольство у пользователя {user_id}")
            response = "Понимаю ваше недовольство. Сейчас подключу оператора для решения вопроса!"
            await message.answer(response, reply_markup=get_main_keyboard())
            
            if OPERATOR_CHAT_ID is not None:
                asyncio.create_task(call_operator(message.from_user, f"Недовольство: {message.text}"))
            return
        
        # 9. Проверяем, что пользователь не может разобраться сам
        if detect_need_help(message.text):
            logger.info(f"Пользователь {user_id} не может разобраться сам - подключаем оператора")
            response = (
                "Понимаю, что вам сложно разобраться самостоятельно!\n\n"
                "📞 Подключаю оператора для помощи\n"
                "⏰ Ожидайте ответа в течение 2-5 минут\n\n"
                "Оператор поможет разобраться с вашей проблемой и найдет решение!"
            )
            await message.answer(response, reply_markup=get_main_keyboard())
            
            if OPERATOR_CHAT_ID is not None:
                asyncio.create_task(call_operator(message.from_user, f"Не может разобраться: {message.text}"))
            return
        
        # 10. Проверяем прощание и благодарность
        farewell_words = ['нет', 'нет спасибо', 'не надо', 'всё', 'всего хорошего', 
                         'пока', 'до свидания', 'спасибо нет', 'не нужно', 'закончили']
        if message_text in farewell_words:
            farewell_responses = [
                "Хорошо! Если возникнут вопросы - обращайтесь! Хорошего дня! 👋",
                "Понял! Буду рад помочь снова, если понадобится. Всего доброго! 😊",
                "Ясно! Не стесняйтесь обращаться, если нужна помощь. До свидания! 👍",
                "Окей! Желаю удачного дня! Если что-то понадобится - я здесь 🤗"
            ]
            response = random.choice(farewell_responses)
            await message.answer(response, reply_markup=get_main_keyboard())
            return
        
        # 11. Проверяем положительные ответы
        positive_words = ['да', 'давай', 'конечно', 'хочу', 'нужно', 'помоги', 'помощь нужна']
        if message_text in positive_words:
            positive_responses = [
                "Отлично! Чем еще могу помочь? Выберите действие или напишите вопрос! 😊",
                "Рад помочь! Что вас интересует? Можете выбрать кнопку ниже или задать вопрос! 👍",
                "Хорошо! Расскажите, с чем нужна помощь? Я здесь, чтобы помочь! 🤗",
                "Отлично! Чем могу быть полезен? Выберите раздел или опишите проблему! 💫"
            ]
            response = random.choice(positive_responses)
            await message.answer(response, reply_markup=get_main_keyboard())
            return
        
        # 12. Проверяем вопросы о покупке билетов
        purchase_patterns = [
            'как купить', 'как приобрести', 'инструкция покупки', 'как оформить заказ',
            'хочу купить', 'хочу приобрести', 'купить билет', 'приобрести билет',
            'как заказать', 'как сделать заказ', 'как оплатить билет', 'процесс покупки',
            'инструкция по покупке', 'как получить билет', 'как оформить билет'
        ]

        if any(phrase in message_text for phrase in purchase_patterns):
            response = (
                "🎫 Как купить билеты:\n\n"
                "1. Перейдите на официальный сайт наших партнеров (Театр Моссовета, Сфера и др.)\n"
                "2. Выберите мероприятие и дату\n"
                "3. Выберите места в зале\n"
                "4. Заполните данные для получения билетов\n"
                "5. Оплатите заказ картой или другим способом\n"
                "6. Билеты придут на указанный email\n\n"
                "Если возникли проблемы с оплата или билеты не пришли - обращайтесь!"
            )
            await message.answer(response, reply_markup=get_main_keyboard())
            return
        
        # 13. Проверяем текстовые команды для оплаты - ИСПРАВЛЕННЫЙ ВАРИАНТ
        payment_keywords = ['оплат', 'платеж', 'деньги', 'карт', 'приложен', 'qr', 'чек', 'списались']
        if any(keyword in message_text for keyword in payment_keywords):
            # Если нет активной сессии - создаем
            if not payment_handler.has_active_session(user_id):
                payment_handler.start_payment_session(user_id)
            
            # Сразу обрабатываем сообщение через payment_handler
            payment_response = payment_handler.process_payment_message(user_id, message.text)
            if payment_response:
                await message.answer(payment_response, reply_markup=get_main_keyboard())
                return
            else:
                # Если обработчик не вернул ответ (не хватает данных), показываем стандартное сообщение
                response = (
                    "💳 Проблема с оплатой\n\n"
                    "Чтобы мы могли помочь, опишите вашу проблему одним сообщением, указав:\n\n"
                    "• Номер заказа (6 цифр, например: 123456)\n\n"
                    "• Способ оплаты (карта/приложение/QR-код)\n\n"
                    "• Время оплаты (например: 30 минут назад, вчера, 25.12.2024)\n\n"
                    "• Описание проблемы:\n"
                    "- Деньги списались, статус заказа \"ожидает оплаты\"\n"
                    "- Двойное списание средств за один заказ.\n"
                    "- На email не пришел кассовый чек за оплаченный заказ\n"
                    "- Платеж не прошел, деньги вернулись на карту \n"
                    "- Не понятно, прошел ли платеж.\n"
                    "- Другое"
                )
                await message.answer(response, reply_markup=get_main_keyboard())
                return
        
        # 14. Проверяем вопросы о возврате билетов по тексту
        if any(phrase in message_text for phrase in ['возврат', 'вернуть', 'вернул']):
            refund_handler.start_refund_session(user_id)
            response = (
                "🔄 Возврат билетов\n\n"
                "Для оформления возврата укажите, пожалуйста, номер вашего заказа (6 цифр).\n\n"
                "Пример: 456321"
            )
            await message.answer(response, reply_markup=get_main_keyboard())
            return
        
        # 15. Проверяем вопросы о покупке на другое мероприятие по ошибке
        if any(phrase in message_text for phrase in ['купил по ошибке', 'не то мероприятие', 'ошибочно купил', 
                                                   'неправильно выбрал', 'перепутал мероприятие', 
                                                   'другое мероприятие по ошибке']):
            logger.info(f"Обнаружен вопрос о покупке на другое мероприятие у пользователя {user_id}")
            
            # Начинаем сессию возврата ошибочных билетов
            wrong_event_handler.start_wrong_event_session(user_id)
            
            response = (
                "🔄 Покупка на другое мероприятие по ошибке\n\n"
                "Понимаю ситуацию! Вот что можно сделать:\n\n"
                "✅ Вариант 1 - Возврат и новая покупка:\n"
                "1. Оформите возврат ошибочных билетов\n"
                "2. Дождитесь подтверждения возврата\n"
                "3. Купите билеты на нужное мероприятие\n\n"
                "✅ Вариант 2 - Обмен через оператора:\n"
                "• Подключу оператора для решения вопроса\n"
                "• Возможен обмен на другое мероприятие\n"
                "• При наличии свободных мест\n\n"
                "Рекомендую оформить возврат:\n"
                "• Укажите номер заказа (6 цифр)\n"
                "• Затем укажите контактные данные\n\n"
                "Пожалуйста, введите номер заказа:"
            )
            await message.answer(response, reply_markup=get_main_keyboard())
            return

        # 16. Проверяем вопросы о возврате одного билета
        if any(phrase in message_text for phrase in ['вернуть один билет', 'только один билет', 'один из заказа', 
                                                   'частичный возврат', 'не все билеты']):
            logger.info(f"Обнаружен вопрос о возврате одного билета у пользователя {user_id}")
            
            # Начинаем сессию частичного возврата
            partial_refund_handler.start_partial_refund_session(user_id)
            
            response = (
                "🔄 Возврат одного билета из заказа\n\n"
                "Да, можно вернуть только один билет из заказа!\n\n"
                "Для оформления возврата укажите:\n\n"
                "1️⃣ Номер заказа (6 цифр)\n"
                "2️⃣ Номер или описание возвращаемого билета\n"
                "3️⃣ Причину возврата\n\n"
                "Пример:\n"
                "Заказ 123456, билет 323243, по болезни\n\n"
                "Пожалуйста, введите данные:"
            )
            await message.answer(response, reply_markup=get_main_keyboard())
            return

        # 17. Проверяем вопросы о смене email
        if any(phrase in message_text for phrase in ['изменить email', 'поменять email', 'сменить почту', 
                                                   'другой email', 'неправильный email']):
            logger.info(f"Обнаружен вопрос о смене email у пользователя {user_id}")
            
            # Начинаем сессию смены email
            email_change_handler.start_email_change_session(user_id)
            
            response = (
                "📧 Изменение email для получения билетов\n\n"
                "Да, можно изменить email!\n\n"
                "Для смены email укажите:\n\n"
                "1️⃣ Номер заказа (6 цифр)\n"
                "2️⃣ Новый email адрес\n\n"
                "Пример:\n"
                "Заказ 123456, новый email example@mail.ru\n\n"
                "Пожалуйста, введите номер заказа:"
            )
            await message.answer(response, reply_markup=get_main_keyboard())
            return

        # 18. Проверяем проблемы с билетами (объединенная логика) - РАСШИРЕННЫЙ ПОИСК
        ticket_problem_patterns = [
            r'не\s*пришли',
            r'не\s*пришёл',
            r'не\s*пришел',
            r'не\s*получил',
            r'не\s*получили',
            r'не\s*поступал',
            r'нет\s*билет',
            r'билеты\s*не',
            r'не\s*приходят',
            r'не\s*дошли',
            r'письмо\s*не',
            r'восстановить',
            r'нет билетов'
        ]
        
        message_lower = message.text.lower()
        if any(re.search(pattern, message_lower) for pattern in ticket_problem_patterns):
            # Начинаем сессию восстановления билетов
            ticket_recovery_handler.start_recovery_session(user_id)
            
            response = (
                "📧 Проблемы с билетами\n\n"
                "🔍 Сначала попробуйте восстановить билеты самостоятельно:\n"
                "1. Зайдите на сайт Intickets.ru\n"
                "2. Перейдите во вкладку Для зрителей\n"
                "3. Воспользуйтесь сервисом восстановления билетов\n\n"
                "---\n\n"
                "🔄 Если не получилось восстановить билеты:\n"
                "Для повторной отправки билетов укажите:\n\n"
                "• Номер заказа (6 цифр) ИЛИ\n"
                "• Номер телефона, который использовали при заказе ИЛИ\n"
                "• Email, на который покупали билеты\n\n"
                "✅ Пример номера заказа: 123456\n"
                "✅ Пример телефона: +7 (912) 345-67-89\n"
                "✅ Пример email: example@mail.ru\n\n"
                "Билеты будут отправлены повторно в течение 15 минут!"
            )
            await message.answer(response, reply_markup=get_main_keyboard())
            return

        # 19. Проверяем проблемы с оплатой по тексту (даже без нажатия кнопки)
        payment_problem_patterns = [
            r'\b\d{6}\b.*(?:плат[её]ж|оплат|деньги|списались|карт|приложен|qr|код)',
            r'(?:плат[её]ж|оплат).*\b\d{6}\b',
            r'деньги.*списались',
            r'чек.*не.*пришел',
            r'двойн.*списан',
            r'статус.*ожидает.*оплат',
            r'платеж.*не.*прошел',
            r'деньги.*вернулись'
        ]
        
        message_lower = message.text.lower()
        if any(re.search(pattern, message_lower) for pattern in payment_problem_patterns):
            # Если это похоже на проблему с оплатой, обрабатываем через payment_handler
            # Сначала проверяем, есть ли активная сессия
            if not payment_handler.has_active_session(user_id):
                payment_handler.start_payment_session(user_id)
            
            payment_response = payment_handler.process_payment_message(user_id, message.text)
            if payment_response:
                await message.answer(payment_response, reply_markup=get_main_keyboard())
                return

        # 20. Проверяем номер заказа для проверки билетов - ПЕРЕМЕЩЕНО НИЖЕ ПРОБЛЕМ С БИЛЕТАМИ
        # Сначала проверяем контекст, потом номер заказа
        order_match = re.search(r'\b(\d{6})\b', message.text)
        if order_match:
            order_number = order_match.group(1)
            logger.info(f"Найден номер заказа: {order_number}")
            
            # Используем OrderResponseManager для проверки статуса заказа
            response = order_manager.get_order_status_response(order_number)
            await message.answer(response, reply_markup=get_main_keyboard())
            return
        
        # 21. Если введен только номер заказа без дополнительного текста - уточняем
        if re.match(r'^\d{6}$', message.text.strip()):
            response = (
                f"🔍 Вижу, что вы ввели номер заказа: {message.text}\n\n"
                "Что именно вас интересует?\n\n"
                "• Проверить статус заказа\n" 
                "• Проблема с билетами\n"
                "• Вопрос по оплате\n"
                "• Возврат билетов\n\n"
                "Опишите, пожалуйста, вашу проблему подробнее, чтобы я мог помочь эффективнее."
            )
            await message.answer(response, reply_markup=get_main_keyboard())
            return
        
        # 22. Если ничего не распознано - используем DeepSeek для обработки опечаток и сложных запросов
        try:
            logger.info(f"Использую DeepSeek для обработки сообщения с опечатками: {message.text}")
            ai_response = await ds_service.process_message(message.text)
            await message.answer(ai_response, reply_markup=get_main_keyboard())
        except Exception as e:
            logger.error(f"Ошибка DeepSeek: {e}")
            # Если DeepSeek недоступен, показываем стандартное сообщение
            response = (
                "🤔 Не совсем понял ваш вопрос. Чем могу помочь?\n\n"
                "Выберите один из вариантов:\n\n"
                "💳 **Проблема с оплатой** - помощь с платежами и возвратами\n"
                "📧 **Билеты не пришли** - восстановление и повторная отправка\n"
                "🔄 **Возврат билетов** - оформление возврата\n"
                "🎫 **Как купить билеты** - инструкция по покупке\n"
                "📞 **Оператор** - связь со специалистом\n\n"
                "Или просто опишите вашу проблему подробнее!"
            )
            await message.answer(response, reply_markup=get_main_keyboard())
            
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}", exc_info=True)
        await message.answer("Произошла ошибка. Попробуйте еще раз или используйте кнопки ниже.", 
                           reply_markup=get_main_keyboard())

async def main():
    """Основная функция"""
    logger.info("=" * 50)
    logger.info("ЗАПУСК БОТА INTICKETS SUPPORT")
    logger.info("=" * 50)
    
    try:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("База данных инициализирована")
        except Exception as db_error:
            logger.warning(f"Ошибка инициализации БД (бот продолжает работу): {db_error}")
        
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Вебхуки очищены")
        
        logger.info("Бот запущен и готов к работе!")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")