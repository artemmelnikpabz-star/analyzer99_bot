НАВЧАЛЬНИЙ TELEGRAM-БОТ

Файли: bot.py, requirements.txt
Пари: 21 звичайна FX-пара з переліку користувача; OTC немає.
Функції: вибір пари, тривалість 1/3/5 хв, новий навчальний аналіз,
індикатори EMA/RSI/MACD, таймер початку/завершення, перевірка руху,
навчальні бали та історична статистика в межах поточного чату.

ВАЖЛИВО:
- Це не інтеграція з Pocket Option і не інструкція для реальних ставок.
- Відсоток показує узгодженість індикаторів, а не шанс виграшу.
- Дані Yahoo Finance можуть бути затриманими, неповними або недоступними.
- Котирування можуть відрізнятися від Pocket Option.
- Сервіс не гарантує точність або прибуток.

РОЗГОРТАННЯ НА RENDER:
1. Додай bot.py і requirements.txt у GitHub-репозиторій.
2. Render -> New -> Background Worker -> під'єднай репозиторій.
3. Build Command: pip install -r requirements.txt
4. Start Command: python bot.py
5. Environment -> Add Environment Variable:
   Key: TELEGRAM_BOT_TOKEN
   Value: токен від BotFather (нікому не показуй).
6. Натисни Deploy.
