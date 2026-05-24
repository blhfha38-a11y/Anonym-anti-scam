# server.py — Enonym Scam Base Backend
# ====================================================
# Хранит базу скамеров, общается с OpenRouter API,
# отправляет уведомления в Telegram.

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import os
import re
from datetime import datetime

app = Flask(__name__)
CORS(app)

# =====================================================================
# КОНФИГУРАЦИЯ
# =====================================================================

API_KEY = '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'  # ← ЗАМЕНИТЕ
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Telegram
TG_TOKEN = '8630662680:AAGin-Yddy2FonBPTUyf7V4piGE82SlVGXc'
TG_CHAT_ID = '8580157399'

# Файлы
DB_FILE = 'scammers_db.json'
STATS_FILE = 'stats.json'

# Порог для Telegram-уведомлений
ALERT_RISK_THRESHOLD = 90

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
# РАБОТА С БАЗОЙ ДАННЫХ
# =====================================================================

def load_db():
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            default_db = [
                {"id": "SCM-001", "name": "CryptoDevil", "tg": "crypto_devil_invest", "type": "Инвестиционный", "risk": 94, "reports": 47, "added": "2024-01-15"},
                {"id": "SCM-002", "name": "SupportFake", "tg": "telegram_support", "type": "Техподдержка", "risk": 88, "reports": 32, "added": "2024-02-03"},
                {"id": "SCM-003", "name": "LoveScam", "tg": "anna_love", "type": "Романтический", "risk": 76, "reports": 19, "added": "2024-02-18"},
                {"id": "SCM-004", "name": "PrizeHunter", "tg": "prize_bot", "type": "Призы", "risk": 82, "reports": 28, "added": "2024-03-01"},
                {"id": "SCM-005", "name": "BankCaller", "tg": "sber_call", "type": "Фишинг", "risk": 91, "reports": 55, "added": "2024-03-10"}
            ]
            save_db(default_db)
            return default_db
    except Exception as e:
        print(f"Ошибка загрузки БД: {e}")
        return []

def save_db(db):
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения БД: {e}")

# =====================================================================
# СТАТИСТИКА
# =====================================================================

def load_stats():
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {'total_checks': 0, 'scams_found': 0, 'last_check': None}

def save_stats(stats):
    try:
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения статистики: {e}")

# =====================================================================
# TELEGRAM УВЕДОМЛЕНИЯ
# =====================================================================

def send_telegram_alert(tg_username, risk, scam_type, verdict):
    """Отправляет уведомление при нахождении скамера с высоким риском"""
    if risk < ALERT_RISK_THRESHOLD:
        return

    text = f"""🚨 *Enonym AI: Обнаружен скамер!*

👤 *Аккаунт:* @{tg_username}
⚠️ *Вердикт:* {verdict}
📊 *Риск:* {risk}%
🏷️ *Тип:* {scam_type}
🕐 *Время:* {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

🔗 _Проверено через Enonym Scam Base_"""

    try:
        url = f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage'
        payload = {
            'chat_id': TG_CHAT_ID,
            'text': text,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True
        }
        response = requests.post(url, json=payload, timeout=10)
        print(f"[TG] Уведомление отправлено: {response.status_code}")
    except Exception as e:
        print(f"[TG] Ошибка отправки: {e}")

# =====================================================================
# МАРШРУТЫ API
# =====================================================================

@app.route('/')
def index():
    return jsonify({
        'status': 'ok',
        'service': 'Enonym Scam Base API',
        'version': '2.1.0'
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    stats = load_stats()
    db = load_db()
    return jsonify({
        'success': True,
        'totalChecks': stats['total_checks'],
        'scamsFound': stats['scams_found'],
        'totalScammers': len(db),
        'lastCheck': stats['last_check']
    })

@app.route('/api/database', methods=['GET'])
def get_database():
    db = load_db()
    return jsonify({'success': True, 'data': db, 'total': len(db)})

@app.route('/api/database/search', methods=['GET'])
def search_database():
    query = request.args.get('q', '').lower()
    db = load_db()
    if not query:
        return jsonify({'success': True, 'data': db, 'total': len(db)})
    results = [s for s in db if query in s.get('name', '').lower() or query in s.get('tg', '').lower() or query in s.get('type', '').lower()]
    return jsonify({'success': True, 'data': results, 'total': len(results)})

@app.route('/api/database/add', methods=['POST'])
def add_to_database():
    data = request.json
    tg = data.get('tg', '').replace('@', '').strip()
    if not tg:
        return jsonify({'success': False, 'error': 'Telegram username обязателен'}), 400

    db = load_db()
    found = next((s for s in db if s['tg'].lower() == tg.lower()), None)

    if found:
        found['reports'] = found.get('reports', 1) + 1
        found['risk'] = min(100, found.get('risk', 70) + 1)
    else:
        new_id = f"SCM-{len(db) + 1:03d}"
        db.append({
            'id': new_id,
            'name': data.get('name', tg),
            'tg': tg,
            'type': data.get('type', 'Не указан'),
            'risk': data.get('risk', 70),
            'reports': 1,
            'added': datetime.now().strftime('%Y-%m-%d')
        })

    save_db(db)
    return jsonify({'success': True, 'message': 'Добавлен в базу', 'total': len(db)})

@app.route('/api/database/stats', methods=['GET'])
def get_db_stats():
    db = load_db()
    total = len(db)
    total_reports = sum(s.get('reports', 0) for s in db)
    avg_risk = round(sum(s.get('risk', 0) for s in db) / total) if total > 0 else 0
    return jsonify({'success': True, 'totalScammers': total, 'totalReports': total_reports, 'avgRisk': avg_risk})

@app.route('/api/database/export/<format>', methods=['GET'])
def export_database(format):
    db = load_db()
    if format == 'json':
        return jsonify({'success': True, 'data': db})
    elif format == 'csv':
        csv_lines = ['ID,Имя,Telegram,Тип,Риск,Жалобы,Дата']
        for s in db:
            csv_lines.append(f'{s["id"]},"{s["name"]}",@{s["tg"]},"{s["type"]}",{s["risk"]}%,{s["reports"]},{s["added"]}')
        csv_text = '\n'.join(csv_lines)
        return csv_text, 200, {'Content-Type': 'text/csv; charset=utf-8'}
    return jsonify({'success': False, 'error': 'Формат не поддерживается'}), 400

@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'Пустой запрос'}), 400

        tg_username = data.get('tg', 'неизвестен')
        images_base64 = data.get('images', [])

        user_content = [{'type': 'text', 'text': f'Проверь @{tg_username}\nСкриншотов: {len(images_base64)}'}]
        for img in images_base64[:3]:
            if img and len(img) > 100:
                user_content.append({'type': 'image_url', 'image_url': {'url': img, 'detail': 'high'}})

        messages = [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': user_content}
        ]

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {API_KEY}',
            'HTTP-Referer': 'https://anonym-anti-scam.netlify.app',
            'X-Title': 'Enonym Scam Base'
        }

        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json={'model': 'google/gemini-2.0-flash-001', 'messages': messages, 'max_tokens': 600, 'temperature': 0.3},
            timeout=30
        )

        if response.status_code != 200:
            return jsonify({'success': False, 'error': f'OpenRouter вернул ошибку {response.status_code}'}), 502

        ai_response = response.json()
        text = ai_response['choices'][0]['message']['content']

        # Парсим ответ
        risk_match = re.search(r'уверенность:\s*(\d+)', text)
        type_match = re.search(r'тип:\s*(.+)', text)
        verdict_match = re.search(r'вердикт:\s*(.+)', text)

        risk = int(risk_match.group(1)) if risk_match else 0
        scam_type = type_match.group(1).strip() if type_match else 'Неизвестен'
        verdict = verdict_match.group(1).strip() if verdict_match else 'Не определён'

        # Обновляем статистику
        stats = load_stats()
        stats['total_checks'] += 1
        if 'СКАМ' in verdict.upper() and 'НЕ СКАМ' not in verdict.upper():
            stats['scams_found'] += 1
        stats['last_check'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        save_stats(stats)

        # Уведомление в Telegram при высоком риске
        if risk >= ALERT_RISK_THRESHOLD:
            send_telegram_alert(tg_username, risk, scam_type, verdict)

        return jsonify({'success': True, 'result': text})

    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'Нейросеть не ответила за 30 секунд'}), 504
    except Exception as e:
        return jsonify({'success': False, 'error': f'Ошибка сервера: {str(e)}'}), 500

# =====================================================================
# ЗАПУСК
# =====================================================================

if __name__ == '__main__':
    print('=' * 50)
    print('Enonym Scam Base API Server v2.1')
    print('Сервер запущен на http://0.0.0.0:5000')
    print('Telegram уведомления:', 'ВКЛ')
    print('=' * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)
