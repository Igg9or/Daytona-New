from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = 'super-secret-key'  # Обязательно для работы сессий!

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Получаем данные из формы
        device_data = {
            'username': request.form['username'],
            'password': request.form['password'],
            'ip_address': request.form['ip_address'],
            'device_type': request.form['device_type']
        }

        # Выводим данные в консоль (для отладки)
        print("\n=== ПОЛУЧЕНЫ ДАННЫЕ ===")
        print(f"Логин: {device_data['username']}")
        print(f"Пароль: {device_data['password']}")  # ⚠️ В реальном проекте так делать нельзя!
        print(f"IP: {device_data['ip_address']}")
        print(f"Тип устройства: {device_data['device_type']}\n")

        # Сохраняем данные в сессии
        session['device_data'] = device_data

        # Перенаправляем на страницу результата
        return redirect(url_for('result'))  # Исправлено: url_for('result'), а не 'show_result'

    return render_template('login.html')

@app.route('/result')  # Обратите внимание на URL
def result():
    # Получаем данные из сессии
    device_data = session.get('device_data')
    
    if not device_data:
        return "Данные не найдены. Вернитесь на главную страницу."

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Результат</title>
        <style>
            body {{ font-family: Arial; padding: 20px; }}
            pre {{ background: #f0f0f0; padding: 10px; }}
            a {{ color: blue; }}
        </style>
    </head>
    <body>
        <h1>Данные подключения:</h1>
        <pre>
Логин: {device_data['username']}
IP: {device_data['ip_address']}
Тип устройства: {device_data['device_type']}
        </pre>
        <a href="/">Назад</a>
    </body>
    </html>
    """

if __name__ == '__main__':
    app.run(debug=True)