from flask import Flask, render_template, request, jsonify, session
from device_connector import connect_to_device
import time

app = Flask(__name__)
app.secret_key = 'your-secret-key-123'

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        device_data = {
            'username': request.form['username'],
            'password': request.form['password'],
            'ip_address': request.form['ip_address'],
            'device_type': request.form['device_type']
        }
        
        # Сохраняем данные в сессии
        session['device_data'] = device_data
        
        # Подключаемся к устройству
        result = connect_to_device(device_data)
        
        if "Ошибка" in result:
            return render_template('error.html', error_message=result)
        else:
            return render_template('success.html', success_message=result)
    
    return render_template('login.html')

@app.route('/api/connect', methods=['POST'])
def api_connect():
    device_data = request.json
    result = connect_to_device(device_data)
    
    return jsonify({
        'status': 'error' if "Ошибка" in result else 'success',
        'message': result
    })

if __name__ == '__main__':
    app.run(debug=True)