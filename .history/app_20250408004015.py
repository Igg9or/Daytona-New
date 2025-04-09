from flask import Flask, render_template, request, redirect, url_for, session, flash
from device_connector import connect_to_device  # Импорт функции подключения

app = Flask(__name__)
app.secret_key = 'super-secret-key-123'

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        device_data = {
            'username': request.form['username'],
            'password': request.form['password'],
            'ip_address': request.form['ip_address'],
            'device_type': request.form['device_type']
        }

        # Пытаемся подключиться к устройству
        connection_result = connect_to_device(device_data)
        
        # Проверяем, была ли ошибка
        if "Ошибка" in connection_result or "Error" in connection_result:
            session['connection_error'] = connection_result
            return redirect(url_for('connection_error'))
        else:
            session['connection_success'] = connection_result
            return redirect(url_for('connection_success'))

    return render_template('login.html')

@app.route('/connection-error')
def connection_error():
    error_message = session.get('connection_error', 'Неизвестная ошибка подключения')
    return render_template('error.html', error_message=error_message)

@app.route('/connection-success')
def connection_success():
    success_message = session.get('connection_success', 'Успешное подключение')
    return render_template('success.html', success_message=success_message)

if __name__ == '__main__':
    app.run(debug=True)