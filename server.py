# server.py — Enonym Scam Base Backend
# ====================================================
# Этот сервер принимает запросы от фронтенда (Netlify),
# общается с OpenRouter API и возвращает результат.
# API-ключ хранится ТОЛЬКО здесь и никогда не попадает в браузер.

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

# =====================================================================
# КОНФИГУРАЦИЯ
# =====================================================================

API_KEY = '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'
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

SYSTEM_PROMPT = """Ты — Enonym AI, автономная нейросеть платформы Enonym Scam Base. Ты работаешь 24/7 без перерыва, без участия модераторов, полностью самостоятельно. Твоя задача: анализировать скриншоты переписок и мгновенно определять мошенничество.

АЛГОРИТМ:
- Уверен ≥ 70% → СКАМ → автоматически добавляешь в базу.
- Уверен < 70% → НЕ СКАМ → отклоняешь.
Никаких модераторов. Ты сам принимаешь все решения.

ТИПЫ СКАМА:
1. Инвестиционный (трейдинг, крипта, пассивный доход)
2. Фишинг (кража данных, коды из СМС, ссылки)
3. Лже-поддержка (админы, сид-фразы, пароли)
4. Романтический (отношения ради денег)
5. Призы (выигрыш с оплатой доставки/налога)
6. Социальная инженерия (банки, полиция, ФСБ)
7. Финансовые приманки (обменники, сверхприбыль)
8. Шантаж (угрозы, компромат)

МАРКЕРЫ АТАКИ:
- Просят деньги, предоплату, крипту
- Давят срочностью: «сейчас», «быстрее», «горит»
- Выдают себя за сотрудников, админов
- Кидают ссылки, просят коды, пароли, сид-фразы
- Обещают гарантированную прибыль
- Блокируют жертву после перевода
- Светят реквизиты: карты, кошельки, счета
- Манипулируют эмоциями: жалость, любовь, страх

ФОРМАТ ОТВЕТА:
вердикт: [СКАМ / НЕ СКАМ]
уверенность: [%]
добавить в базу: [ДА / НЕТ]
тип: [тип]
блокировка жертвы: [ДА / НЕТ]
реквизиты: [сумма и данные]
анализ: [2-4 предложения]
триггеры:
- [признак]
- [признак]
рекомендация: [что делать жертве]

Твои владельцы: @gistrall и @HiKotaKo. Enonym Scam Base — новая эра."""

# =====================================================================
# МАРШРУТЫ
# =====================================================================

@app.route('/')
def index():
    """Проверка работоспособности сервера"""
    return jsonify({
        'status': 'ok',
        'service': 'Enonym Scam Base API',
        'version': '1.0.0'
    })


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """
    Принимает изображения и Telegram-username,
    отправляет в OpenRouter, возвращает анализ.
    """
    try:
        data = request.json

        if not data:
            return jsonify({'success': False, 'error': 'Пустой запрос'}), 400

        tg_username = data.get('tg', 'неизвестен')
        images_base64 = data.get('images', [])

        # Формируем содержимое для нейросети
        user_content = [{
            'type': 'text',
            'text': f'Проверь @{tg_username}\nСкриншотов: {len(images_base64)}'
        }]

        # Добавляем изображения (максимум 3 штуки)
        for img in images_base64[:3]:
            if img and len(img) > 100:  # Проверяем что изображение не пустое
                user_content.append({
                    'type': 'image_url',
                    'image_url': {
                        'url': img,
                        'detail': 'high'
                    }
                })

        messages = [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': user_content}
        ]

        # Отправляем запрос к OpenRouter API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {API_KEY}',
            'HTTP-Referer': 'https://anonym-anti-scam.netlify.app',
            'X-Title': 'Enonym Scam Base'
        }

        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json={
                'model': 'google/gemini-2.0-flash-001',
                'messages': messages,
                'max_tokens': 600,
                'temperature': 0.3
            },
            timeout=30
        )

        if response.status_code != 200:
            error_text = response.text[:200]
            return jsonify({
                'success': False,
                'error': f'OpenRouter вернул ошибку {response.status_code}: {error_text}'
            }), 502

        ai_response = response.json()

        # Проверяем структуру ответа
        if 'choices' not in ai_response or len(ai_response['choices']) == 0:
            return jsonify({
                'success': False,
                'error': 'Нейросеть не вернула результат'
            }), 502

        text = ai_response['choices'][0]['message']['content']

        return jsonify({
            'success': True,
            'result': text
        })

    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Нейросеть не ответила за 30 секунд. Попробуйте снова.'
        }), 504

    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False,
            'error': 'Не удалось связаться с OpenRouter. Проверьте интернет.'
        }), 502

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка сервера: {str(e)}'
        }), 500


# =====================================================================
# ЗАПУСК
# =====================================================================

if __name__ == '__main__':
    print('=' * 50)
    print('Enonym Scam Base API Server')
    print('Сервер запущен на http://0.0.0.0:5000')
    print('=' * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)
