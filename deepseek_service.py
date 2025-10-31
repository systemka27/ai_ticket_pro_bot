import asyncio
import aiohttp
import random
import logging
import re
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from config import config

logger = logging.getLogger(__name__)

class DeepSeekService:
    def __init__(self):
        self.api_key = config.DEEPSEEK_API_KEY
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.user_contexts: Dict[int, Dict] = {}
        self.session_timeout = timedelta(minutes=30)
        logger.info("DeepSeekService инициализирован")

    def _clean_old_contexts(self):
        """Очищает старые контексты"""
        now = datetime.now()
        expired_users = []
        
        for user_id, context in self.user_contexts.items():
            if 'created_at' in context and now - context['created_at'] > self.session_timeout:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self.user_contexts[user_id]
            logger.debug(f"Удален контекст для пользователя {user_id} по таймауту")

    async def get_ai_response(self, user_message: str, user_id: int = None, chat_history: Optional[List[Dict]] = None) -> Optional[str]:
        """Получает ответ от DeepSeek с учетом контекста"""
        # Очищаем старые контексты
        self._clean_old_contexts()
        
        # Сначала проверяем контекст пользователя
        if user_id and user_id in self.user_contexts:
            context_response = self._handle_user_context(user_id, user_message)
            if context_response:
                return context_response

        # Подготавливаем историю сообщений
        messages = [{"role": "system", "content": self._get_system_prompt()}]
        
        if chat_history:
            messages.extend(chat_history[-6:])
        
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 500,
            "stream": False
        }

        try:
            logger.info(f"Запрос к DeepSeek от пользователя {user_id}: {user_message[:100]}...")
            
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.api_url, json=payload, headers=self.headers) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        response_text = data['choices'][0]['message']['content'].strip()
                        logger.info(f"DeepSeek ответил: {response_text[:100]}...")
                        return response_text
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка DeepSeek API: {response.status} - {error_text}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("Таймаут запроса к DeepSeek")
            return None
        except Exception as e:
            logger.error(f"Ошибка при запросе к DeepSeek: {e}")
            return None

    def _get_system_prompt(self) -> str:
        """Возвращает системный промпт для AI"""
        return """Ты - AI-помощник службы поддержки Intickets. Отвечай вежливо и профессионально.
Если не знаешь ответа - предложи подключить оператора.
При недовольстве клиента сразу извинись и предложи оператора."""

    def _handle_user_context(self, user_id: int, user_message: str) -> Optional[str]:
        """Обрабатывает контекст пользователя"""
        context = self.user_contexts[user_id]
        
        if context.get('type') == 'payment_issue':
            return self._handle_payment_context(user_id, user_message, context)
        
        return None

    def _handle_payment_context(self, user_id: int, user_message: str, context: Dict) -> Optional[str]:
        """Обрабатывает контекст оплаты"""
        # Извлекаем данные из сообщения
        extracted_data = self._extract_payment_data(user_message)
        
        # Обновляем контекст
        context['data'].update(extracted_data)
        
        # Проверяем, собрали ли все данные
        collected_data = context['data']
        has_order = 'order_number' in collected_data
        has_method = 'payment_method' in collected_data
        has_time = 'time_minutes' in collected_data
        
        logger.info(f"Собранные данные: {collected_data}")
        
        # Если есть хотя бы 2 из 3 данных - считаем достаточным
        if (has_order and has_method) or (has_order and has_time) or (has_method and has_time):
            response = self._get_payment_solution_response(collected_data)
            # Очищаем контекст после решения
            if user_id in self.user_contexts:
                del self.user_contexts[user_id]
            return response
        
        # Если данных еще не все, запрашиваем недостающие
        return self._get_missing_data_response(collected_data)

    def _extract_payment_data(self, text: str) -> Dict[str, str]:
        """Извлекает данные об оплате из текста"""
        data = {}
        text_lower = text.lower()
        
        # Ищем номер заказа (6+ цифр подряд)
        order_match = re.search(r'(\d{6,})', text)
        if order_match:
            data['order_number'] = order_match.group(1)
            logger.info(f"Найден номер заказа: {data['order_number']}")
        
        # Ищем время
        time_match = re.search(r'(\d+)\s*(мин|минут|час|часа|часов)', text_lower)
        if time_match:
            data['time_minutes'] = time_match.group(1)
            logger.info(f"Найдено время: {data['time_minutes']} минут")
        
        # Ищем способ оплаты
        if any(word in text_lower for word in ['приложен', 'приложени', 'мобильн', 'телефон', 'приложении']):
            data['payment_method'] = 'мобильное приложение'
            logger.info("Найден способ оплаты: мобильное приложение")
        elif any(word in text_lower for word in ['qr', 'код', 'qr-код']):
            data['payment_method'] = 'QR-код'
            logger.info("Найден способ оплаты: QR-код")
        elif any(word in text_lower for word in ['карт', 'картой', 'карту', 'карта']):
            data['payment_method'] = 'банковская карта'
            logger.info("Найден способ оплаты: банковская карта")
        
        return data

    def _get_payment_solution_response(self, data: Dict) -> str:
        """Формирование решения на основе собранных данных"""
        order_num = data.get('order_number', 'неизвестен')
        time_mins = data.get('time_minutes', '30')
        payment_method = data.get('payment_method', 'неизвестен')
        
        return (
            "✅ **Отлично, разобрался!**\n\n"
            f"**По вашему заказу №{order_num}:**\n"
            f"• Оплата через: {payment_method}\n"
            f"• Время назад: {time_mins} минут\n"
            f"• Деньги списались\n\n"
            "**Рекомендую:**\n"
            "1️⃣ Подождите еще 15-20 минут - иногда бывают задержки\n"
            "2️⃣ Проверьте email - должно прийти подтверждение\n"
            "3️⃣ Если статус не изменится - обратитесь в поддержку\n\n"
            "📞 **Телефон поддержки:** +7 (999) 123-45-67\n"
            "⏰ **Время работы:** 9:00-21:00\n\n"
            "Нужна помощь с чем-то еще?"
        )

    def _get_missing_data_response(self, data: Dict) -> str:
        """Запрос недостающих данных"""
        missing = []
        
        if 'order_number' not in data:
            missing.append("номер заказа")
        if 'payment_method' not in data:
            missing.append("способ оплаты")
        if 'time_minutes' not in data:
            missing.append("время оплаты")
        
        if missing:
            return (
                "🔍 **Уточните, пожалуйста:**\n\n"
                f"Для решения проблемы нужен {' и '.join(missing)}\n\n"
                "Например:\n"
                "• Номер заказа: 123456\n"
                "• Оплатил картой/приложением/QR-кодом\n"
                "• Время оплаты: 30 минут назад"
            )
        
        return "Что-то пошло не так. Попробуйте еще раз."

    def detect_dissatisfaction(self, message_text: str) -> bool:
        """Определяет недовольство клиента"""
        dissatisfaction_phrases = [
            'недоволен', 'плохой', 'ужасный', 'кошмар', 'безобразие', 'возмущен',
            'хреново', 'отстой', 'бесит', 'раздражает', 'достало', 'надоело',
            'человека', 'оператора', 'менеджера', 'живого',
            'это не помогает', 'бесполезно', 'зря', 'напрасно',
            'верните деньги', 'жалоба', 'претензия', 'верните',
            'свяжите с человеком', 'позовите оператора', 'до человека'
        ]
        
        message_lower = message_text.lower()
        return any(phrase in message_lower for phrase in dissatisfaction_phrases)

    def get_greeting_response(self, message_text: str) -> Optional[str]:
        """Обрабатывает приветственные сообщения"""
        greetings = [
            'привет', 'здравствуй', 'добрый', 'hello', 'hi', 'начать',
            'здравствуйте', 'добрый день', 'доброе утро', 'добрый вечер',
            'здрасьте', 'приветствую', 'доброго времени'
        ]
        
        message_lower = message_text.lower().strip()
        
        words = message_lower.split()
        greeting_words = [word for word in words if any(greet in word for greet in greetings)]
        
        if len(greeting_words) >= 1 and len(greeting_words) / len(words) >= 0.5:
            greeting_templates = [
                "🎭 Добро пожаловать в поддержку Intickets! Я ваш AI-помощник. Чем могу помочь?",
                "👋 Здравствуйте! Я помощник по билетам и мероприятиям. Задайте ваш вопрос!",
                "✨ Приветствую! Готов помочь с билетами, мероприятиями и ответить на вопросы."
            ]
            return random.choice(greeting_templates)
        
        return None

    def get_quick_response(self, message_text: str, user_id: int = None) -> Optional[str]:
        """Обрабатывает частые запросы"""
        normalized_text = ' '.join(message_text.lower().split())
        
        # Очищаем старые контексты
        self._clean_old_contexts()
        
        # 1. Проверяем проблемы с оплатой (ВЫСШИЙ ПРИОРИТЕТ)
        if self._is_payment_issue(normalized_text):
            if user_id:
                # Создаем контекст для пользователя
                self.user_contexts[user_id] = {
                    'type': 'payment_issue',
                    'data': {},
                    'created_at': datetime.now()
                }
                logger.info(f"Создан контекст оплаты для пользователя {user_id}")
            return self._get_payment_help_response()
        
        # 2. Проверяем благодарность
        if self._is_thankful(normalized_text):
            return self._get_thankyou_response()
        
        # 3. Стандартные быстрые ответы
        quick_responses = {
            'билеты': "💰 Билеты доступны на сайте. Какое мероприятие вас интересует?",
            'купить билет': "💳 Для покупки билетов выберите мероприятие на сайте и следуйте инструкциям",
            'помощь': "🔧 Расскажите о вашей проблеме, и я постараюсь помочь!",
            'вернуть билет': "🔄 Возврат возможен за 3 дня до мероприятия. Напишите номер заказа.",
            'не пришел билет': "📧 Проверьте папку 'Спам'. Если нет - напишите номер заказа.",
            'оплата': "💳 Принимаем карты, электронные кошельки. Какая проблема с оплатой?",
            'контакты': "📞 Support: support@intickets.ru, +7 (999) 123-45-67",
            'сайт': "🌐 Наш сайт: https://intickets.ru"
        }
        
        for keyword, response in quick_responses.items():
            if keyword in normalized_text:
                return response
        
        return None

    def _is_payment_issue(self, text: str) -> bool:
        """Проверяет проблемы с оплатой"""
        payment_words = ['оплат', 'платеж', 'деньг', 'списал', 'не прошел', 'завис', 'платил', 'оплатил']
        problem_words = ['проблем', 'не работ', 'ошибк', 'сломал', 'не меняется']
        return any(pword in text for pword in payment_words) and any(pword in text for pword in problem_words)

    def _is_thankful(self, text: str) -> bool:
        """Проверяет благодарность"""
        thankful_words = ['спасибо', 'благодарю', 'помог', 'сработало', 'получилось', 'thanks', 'решилось']
        return any(word in text for word in thankful_words)

    def _get_payment_help_response(self) -> str:
        """Ответ на проблемы с оплатой"""
        return (
            "💳 **Помощь с оплатой:**\n\n"
            "Частые проблемы и решения:\n\n"
            "✅ **Платеж не прошел:**\n"
            "• Проверьте баланс карты\n"
            "• Подождите 15 минут - иногда бывают задержки\n"
            "• Проверьте email - должно прийти уведомление\n\n"
            "✅ **Деньги списались, но билетов нет:**\n"
            "• Проверьте папку 'Спам' в почте\n"
            "• Напишите номер заказа для проверки\n\n"
            "✅ **Не принимается карта:**\n"
            "• Попробуйте другую карту\n"
            "• Используйте электронный кошелек\n\n"
            "📞 **Если проблема осталась:**\n"
            "Напишите номер заказа и описание проблемы"
        )

    def _get_thankyou_response(self) -> str:
        """Ответ на благодарность"""
        responses = [
            "🎉 Рад был помочь! Обращайтесь, если нужна помощь!",
            "✅ Отлично! Если что-то ещё понадобится - я здесь!",
            "🤝 Пожалуйста! Хорошего дня и приятного мероприятия!"
        ]
        return random.choice(responses)

    def clear_user_context(self, user_id: int):
        """Очищает контекст пользователя"""
        if user_id in self.user_contexts:
            del self.user_contexts[user_id]
            logger.debug(f"Контекст очищен для пользователя {user_id}")