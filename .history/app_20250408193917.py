from flask import Flask, render_template, request, session, redirect, url_for
from device_connector import connect_and_collect_data
import json
from datetime import datetime
from device_connector import update_interface_on_device
from flask import Flask, render_template, session, redirect, url_for

app = Flask(__name__, static_url_path='/static')
app.secret_key = 'your-secret-key'  # Ваш секретный ключ
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 час


interfaces_store = [
    {
        'name': 'GigabitEthernet0/1',
        'description': 'Сервер',
        'status': 'up',
        'vlan': 10,
        'duplex': 'full',
        'speed': '1 Gbps'
    },
    {
        'name': 'GigabitEthernet0/2',
        'description': 'Резерв',
        'status': 'down',
        'vlan': 20,
        'duplex': 'auto',
        'speed': '100 Mbps'
    }
]

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        device_data = {
            'username': request.form['username'],
            'password': request.form['password'],
            'ip_address': request.form['ip_address'],
            'device_type': request.form['device_type'],
            'timestamp': datetime.now().isoformat()  # Метаданные
        }

        # Сохраняем в сессии перед подключением (для индикатора загрузки)
        session['device_data'] = device_data
        session.pop('device_status', None)  # Очищаем предыдущие данные
        
        return redirect(url_for('connect_device'))  # Отдельный маршрут для подключения
    
    return render_template('login.html')

@app.route('/connect-device')
def connect_device():
    if 'device_data' not in session:
        return redirect(url_for('login'))
    
    # Получаем сохраненные данные
    device_data = session['device_data']
    
    # Подключаемся и собираем ВСЕ данные
    result = connect_and_collect_data(device_data)
    
    if result['status'] == 'error':
        return render_template('error.html', 
                             error_message=result['message'],
                             device_data=device_data)
    
    # Сохраняем ВСЕ данные в сессии
    session['device_status'] = json.dumps(result['data'])  # Сериализуем
    session['last_update'] = datetime.now().isoformat()
    
    return redirect(url_for('device_status'))

@app.route('/device-status')
def device_status():
    if 'device_status' not in session or 'device_data' not in session:
        return redirect(url_for('login'))
    
    return render_template(
        'device_status.html',
        device_status=json.loads(session['device_status']),  # Десериализуем
        device_data=session['device_data'],
        last_update=session['last_update']
    )


@app.route('/interfaces')
def interfaces():
    if 'device_data' not in session:
        return redirect(url_for('login'))
    
    # Тестовые данные интерфейсов
    interfaces_data = [
        {
            'name': 'GigabitEthernet0/1',
            'description': 'Сервер',
            'status': 'up',
            'vlan': 10,
            'duplex': 'full',
            'speed': '1 Gbps'
        },
        {
            'name': 'GigabitEthernet0/2',
            'description': 'Резерв',
            'status': 'down',
            'vlan': 20,
            'duplex': 'auto',
            'speed': '100 Mbps'
        }
    ]
    
    return render_template('interfaces.html', interfaces=interfaces_data)

# В app.py
@app.route('/update-interface', methods=['POST'])
def update_interface():
    if 'device_data' not in session:
        return jsonify({'success': False, 'message': 'Требуется авторизация'}), 401
    
    try:
        data = request.get_json()
        
        # Здесь будет код для отправки изменений на реальное устройство
        # Пока просто логируем и возвращаем успех
        
        print(f"Получены данные для обновления интерфейса: {data}")
        
        # В реальной реализации здесь будет:
        # 1. Подключение к устройству (используя данные из session['device_data'])
        # 2. Отправка команд для настройки интерфейса
        # 3. Проверка успешности выполнения
        
        return jsonify({
            'success': True,
            'message': 'Изменения сохранены (тестовый режим)'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500
    
@app.route('/update-interface', methods=['POST'])
def update_interface():
    if 'device_data' not in session:
        return jsonify({'success': False, 'message': 'Требуется авторизация'}), 401
    
    try:
        data = request.get_json()
        device_data = session['device_data']
        
        # Вызываем функцию для обновления интерфейса на устройстве
        success = update_interface_on_device(device_data, data)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Интерфейс успешно обновлен'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Не удалось обновить интерфейс на устройстве'
            })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500
        
if __name__ == '__main__':
    app.run(debug=True)