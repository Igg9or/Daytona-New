from flask import Flask, render_template, request, redirect, url_for, session, flash
from device_connector import connect_to_device

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Необходимо для работы сессий

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        device_data = {
            'username': request.form['username'],
            'password': request.form['password'],
            'ip_address': request.form['ip_address'],
            'device_type': request.form['device_type']
        }
        
        # Подключаемся к устройству
        result = connect_to_device(device_data)
        
        # Сохраняем результат в сессии
        session['connection_result'] = result
        return redirect(url_for('show_result'))
    
    return render_template('login.html')

@app.route('/result')
def show_result():
    result = session.get('connection_result', 'Нет данных о подключении')
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Результат подключения</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            pre {{ background: #f4f4f4; padding: 10px; border-radius: 5px; }}
            a {{ color: #0066cc; text-decoration: none; }}
        </style>
    </head>
    <body>
        <h1>Результат подключения</h1>
        <pre>{result}</pre>
        <a href="/">Вернуться</a>
    </body>
    </html>
    """

if __name__ == '__main__':
    app.run(debug=True)