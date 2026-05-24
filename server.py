# server.py — Enonym Scam Base Backend
# ====================================================
# База данных: Supabase (PostgreSQL)

from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
import requests
import re
from datetime import datetime

app = Flask(__name__)
CORS(app)

# =====================================================================
# КОНФИГУРАЦИЯ
# =====================================================================

# OpenRouter (ЗАМЕНИТЕ НА СВОЙ НОВЫЙ КЛЮЧ)
API_KEY = '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'
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Supabase
SUPABASE_URL = 'https://tjpjphgyylkkxi.supabase.co'
SUPABASE_KEY = 'sb_secret_2JUBdWMa8rMeF5Sv288rkg_DNDnaI0p'

# Инициализация Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Telegram
TG_TOKEN = '8630662680:AAGin-Yddy2FonBPTUyf7V4piGE82SlVGXc'
TG_CHAT_ID = '8580157399'

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
# TELEGRAM УВЕДОМЛЕНИЯ
# =====================================================================

def send_telegram_alert(tg_username, risk, scam_type, verdict):
    if risk < ALERT_RISK_THRESHOLD:
        return

    text = f"""🚨 *Enonym AI: Обнаружен скамер!*

👤 *Аккаунт:* @{tg_username}
⚠️ *Вердикт:* {verdict}
📊 *Риск:* {risk}%
🏷️ *Тип:* {scam_type}
🕐 *Время:* {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"""

    try:
        url = f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage'
        requests.post(url, json={
            'chat_id': TG_CHAT_ID,
            'text': text,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True
        }, timeout=10)
    except Exception as e:
        print(f"[TG] Ошибка: {e}")

# =====================================================================
# МАРШРУТЫ API
# =====================================================================

@app.route('/')
def index():
    return jsonify({'status': 'ok', 'service': 'Enonym Scam Base API', 'version': '3.0.0', 'database': 'Supabase'})

@app.route('/api/database', methods=['GET'])
def get_database():
    try:
        response = supabase.table('scammers').select('*').order('id', desc=False).execute()
        return jsonify({'success': True, 'data': response.data, 'total': len(response.data)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/database/search', methods=['GET'])
def search_database():
    query = request.args.get('q', '').lower()
    try:
        response = supabase.table('scammers').select('*').execute()
        if not query:
            return jsonify({'success': True, 'data': response.data, 'total': len(response.data)})
        results = [s for s in response.data if query in s.get('name', '').lower() or query in s.get('tg', '').lower() or query in s.get('type', '').lower()]
        return jsonify({'success': True, 'data': results, 'total': len(results)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/database/add', methods=['POST'])
def add_to_database():
    data = request.json
    tg = data.get('tg', '').replace('@', '').strip()
    if not tg:
        return jsonify({'success': False, 'error': 'Telegram username обязателен'}), 400

    try:
        existing = supabase.table('scammers').select('*').eq('tg', tg).execute()
        if existing.data:
            supabase.table('scammers').update({
                'reports': existing.data[0]['reports'] + 1,
                'risk': min(100, existing.data[0]['risk'] + 1)
            }).eq('tg', tg).execute()
        else:
            supabase.table('scammers').insert({
                'name': data.get('name', tg),
                'tg': tg,
                'type': data.get('type', 'Не указан'),
                'risk': data.get('risk', 70),
                'reports': 1,
                'added': datetime.now().strftime('%Y-%m-%d')
            }).execute()

        count = supabase.table('scammers').select('*', count='exact').execute()
        return jsonify({'success': True, 'message': 'Добавлен в базу', 'total': count.count if count.count else 0})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/database/stats', methods=['GET'])
def get_db_stats():
    try:
        response = supabase.table('scammers').select('*').execute()
        data = response.data
        total = len(data)
        total_reports = sum(s.get('reports', 0) for s in data)
        avg_risk = round(sum(s.get('risk', 0) for s in data) / total) if total > 0 else 0
        return jsonify({'success': True, 'totalScammers': total, 'totalReports': total_reports, 'avgRisk': avg_risk})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/database/export/<format>', methods=['GET'])
def export_database(format):
    try:
        response = supabase.table('scammers').select('*').execute()
        data = response.data
        if format == 'json':
            return jsonify({'success': True, 'data': data})
        elif format == 'csv':
            csv_lines = ['ID,Имя,Telegram,Тип,Риск,Жалобы,Дата']
            for s in data:
                csv_lines.append(f'{s["id"]},"{s["name"]}",@{s["tg"]},"{s["type"]}",{s["risk"]}%,{s["reports"]},{s["added"]}')
            return '\n'.join(csv_lines), 200, {'Content-Type': 'text/csv; charset=utf-8'}
        return jsonify({'success': False, 'error': 'Формат не поддерживается'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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

        text = response.json()['choices'][0]['message']['content']

        risk_match = re.search(r'уверенность:\s*(\d+)', text)
        type_match = re.search(r'тип:\s*(.+)', text)
        verdict_match = re.search(r'вердикт:\s*(.+)', text)

        risk = int(risk_match.group(1)) if risk_match else 0
        scam_type = type_match.group(1).strip() if type_match else 'Неизвестен'
        verdict = verdict_match.group(1).strip() if verdict_match else 'Не определён'

        add_match = re.search(r'добавить в базу:\s*(да|нет)', text, re.IGNORECASE)
        if add_match and add_match.group(1).lower() == 'да':
            try:
                existing = supabase.table('scammers').select('*').eq('tg', tg_username).execute()
                if existing.data:
                    supabase.table('scammers').update({
                        'reports': existing.data[0]['reports'] + 1,
                        'risk': min(100, max(existing.data[0]['risk'], risk))
                    }).eq('tg', tg_username).execute()
                else:
                    supabase.table('scammers').insert({
                        'name': tg_username,
                        'tg': tg_username,
                        'type': scam_type,
                        'risk': risk,
                        'reports': 1,
                        'added': datetime.now().strftime('%Y-%m-%d')
                    }).execute()
            except Exception as e:
                print(f"[DB] Ошибка: {e}")

        if risk >= ALERT_RISK_THRESHOLD:
            send_telegram_alert(tg_username, risk, scam_type, verdict)

        return jsonify({'success': True, 'result': text})

    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'Нейросеть не ответила за 30 секунд'}), 504
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print('=' * 50)
    print('Enonym Scam Base API Server v3.0')
    print('=' * 50)
    app.run(host='0.0.0.0', port=5000)
