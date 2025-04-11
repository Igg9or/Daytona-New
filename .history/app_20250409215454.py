from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from device_connector import connect_and_collect_data
import json
from datetime import datetime
from device_connector import update_interface_on_device
from flask import Flask, render_template, session, redirect, url_for
from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
import re
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler


app = Flask(__name__, static_url_path='/static')
app.secret_key = 'your-secret-key'  # Ваш секретный ключ
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 час

handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.logger.setLevel(logging.DEBUG)

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
            'secret': request.form.get('secret', ''),  # Добавляем поле для enable password
            'ip_address': request.form['ip_address'],
            'device_type': request.form['device_type'],
            'timestamp': datetime.now().isoformat()
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
    
    device_type = session['device_data'].get('device_type', 'Cisco')
    
    # Используем данные из сессии, если они есть
    if 'device_status' in session:
        device_status = json.loads(session['device_status'])
        if 'interfaces' in device_status:
            return render_template('interfaces.html', interfaces=device_status['interfaces'])
    
    # Иначе генерируем тестовые данные
    if device_type.lower() == 'huawei':
        interfaces_data = [
            {
                'name': 'GigabitEthernet0/0/1',
                'description': 'Uplink to core',
                'status': 'up',
                'vlan': 100,
                'duplex': 'full',
                'speed': '1000 Mbps'
            },
            {
                'name': 'GigabitEthernet0/0/2',
                'description': 'Access port',
                'status': 'down',
                'vlan': 200,
                'duplex': 'auto',
                'speed': '100 Mbps'
            }
        ]
    else:
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

@app.route('/interface-details')
def interface_details():
    if 'device_data' not in session:
        return redirect(url_for('login'))
    
    # Получаем список интерфейсов из сессии или генерируем тестовые
    if 'device_status' in session:
        device_status = json.loads(session['device_status'])
        interfaces = device_status.get('interfaces', [])
    else:
        device_type = session['device_data'].get('device_type', 'Cisco')
        interfaces = generate_test_interfaces(device_type)
    
    return render_template('interface_details.html', interfaces=interfaces)

@app.route('/get-interface-details')
def get_interface_details():
    if 'device_data' not in session:
        return jsonify({'error': 'Требуется авторизация'}), 401
    
    interface_name = request.args.get('name')
    if not interface_name:
        return jsonify({'error': 'Не указано имя интерфейса'}), 400
    
    device_data = session['device_data']
    device_type = device_data.get('device_type', 'Cisco').lower()
    
    try:
        netmiko_device_type = 'cisco_ios' if device_type == 'cisco' else 'huawei'
        device_params = {
            'device_type': netmiko_device_type,
            'host': device_data['ip_address'],
            'username': device_data['username'],
            'password': device_data['password'],
            'secret': device_data.get('secret', ''),
            'timeout': 20,
            'session_timeout': 30,
            'global_delay_factor': 2,
            'session_log': 'netmiko_session.log'
        }
        
        app.logger.info(f"Подключение к {device_data['ip_address']} для получения интерфейса {interface_name}")
        connection = ConnectHandler(**device_params)
        
        try:
            if device_data.get('secret'):
                connection.enable()
            
            # Получаем детальную информацию об интерфейсе
            if device_type == 'huawei':
                details_cmd = f'display interface {interface_name}'
            else:
                details_cmd = f'show interface {interface_name}'
            
            app.logger.debug(f"Отправка команды: {details_cmd}")
            details = connection.send_command(details_cmd, delay_factor=2)
            app.logger.debug(f"Полученные данные:\n{details[:500]}...")  # Логируем первые 500 символов
            
            if not details:
                raise ValueError("Пустой ответ от устройства")
            
            if device_type == 'huawei':
                interface_data = parse_huawei_interface_details(details)
            else:
                interface_data = parse_cisco_interface_details(details)
            
            interface_data['name'] = interface_name
            interface_data['raw_data'] = details[:1000]  # Для отладки
            
            app.logger.info(f"Успешно получены данные интерфейса {interface_name}")
            return jsonify(interface_data)
            
        except Exception as e:
            app.logger.error(f"Ошибка при получении данных интерфейса {interface_name}: {str(e)}", exc_info=True)
            return jsonify({
                'error': f'Не удалось получить данные интерфейса: {str(e)}',
                'name': interface_name,
                'device_type': device_type,
                'suggestions': [
                    'Проверьте правильность имени интерфейса',
                    'Убедитесь, что устройство поддерживает команду',
                    'Проверьте права доступа'
                ]
            }), 500
            
        finally:
            connection.disconnect()
            
    except NetmikoAuthenticationException as auth_error:
        app.logger.error(f"Ошибка аутентификации: {str(auth_error)}")
        return jsonify({'error': 'Ошибка аутентификации'}), 401
    except NetmikoTimeoutException as timeout_error:
        app.logger.error(f"Таймаут подключения: {str(timeout_error)}")
        return jsonify({'error': 'Таймаут подключения'}), 408
    except Exception as e:
        app.logger.error(f"Ошибка подключения: {str(e)}", exc_info=True)
        return jsonify({'error': f'Ошибка подключения: {str(e)}'}), 500

def parse_cisco_interface_details(details):
    """Парсинг деталей интерфейса для Cisco устройств с защитой от ошибок"""
    def safe_regex(pattern, text, default='N/A'):
        match = re.search(pattern, text)
        return match.group(1).strip() if match else default

    status = 'up' if 'line protocol is up' in details.lower() else 'down'
    
    return {
        'description': safe_regex(r'Description: (.+)', details),
        'status': status,
        'type': safe_regex(r'Hardware is (.+?),', details),
        'speed': safe_regex(r'BW (\d+)', details) + ' Kbps' if safe_regex(r'BW (\d+)', details) != 'N/A' else 'N/A',
        'duplex': safe_regex(r'Duplex:(.+?),', details).lower(),
        'mtu': safe_regex(r'MTU (\d+)', details, '1500'),
        'mac_address': safe_regex(r'address is (.+?) ', details) or 
                      safe_regex(r'Hardware(?: is|:)\s*(.+?)\s', details),
        'ip_address': safe_regex(r'Internet address is (.+?)[,\s]', details),
        'netmask': safe_regex(r'Internet address is .+?/(\d+)', details),
        'last_input': safe_regex(r'Last input (.+?),', details),
        'last_output': safe_regex(r'Last output (.+?),', details),
        'input_rate': safe_regex(r'input rate (\d+)', details) + ' bps' if safe_regex(r'input rate (\d+)', details) != 'N/A' else 'N/A',
        'output_rate': safe_regex(r'output rate (\d+)', details) + ' bps' if safe_regex(r'output rate (\d+)', details) != 'N/A' else 'N/A',
        'input_errors': safe_regex(r'input errors (\d+)', details, '0'),
        'output_errors': safe_regex(r'output errors (\d+)', details, '0')
    }


def parse_huawei_interface_details(details):
    """Парсинг деталей интерфейса для Huawei устройств с защитой от ошибок"""
    def safe_regex(pattern, text, default='N/A'):
        match = re.search(pattern, text)
        return match.group(1).strip() if match else default

    status = 'up' if 'current state : up' in details.lower() else 'down'
    
    ip_info = safe_regex(r'Internet Address is (.+?)\s', details)
    ip_parts = ip_info.split('/') if ip_info != 'N/A' else ['N/A', 'N/A']
    
    return {
        'description': safe_regex(r'Description:(.+?)\n', details),
        'status': status,
        'type': safe_regex(r'Port Type:(.+?)\n', details),
        'speed': safe_regex(r'Speed :(.+?),', details),
        'duplex': safe_regex(r'Duplex :(.+?)\n', details).lower(),
        'mtu': safe_regex(r'The Maximum Transmit Unit is (\d+)', details, '1500'),
        'mac_address': safe_regex(r'Hardware address is (.+?)\s', details) or 
                      safe_regex(r'Hardware addr is (.+?)\s', details),
        'ip_address': ip_parts[0],
        'netmask': ip_parts[1] if len(ip_parts) > 1 else 'N/A',
        'last_input': safe_regex(r'Last 300 seconds input rate: (.+?) ', details) + ' bps' if safe_regex(r'Last 300 seconds input rate: (.+?) ', details) != 'N/A' else 'N/A',
        'last_output': safe_regex(r'Last 300 seconds output rate: (.+?) ', details) + ' bps' if safe_regex(r'Last 300 seconds output rate: (.+?) ', details) != 'N/A' else 'N/A',
        'input_rate': safe_regex(r'Input bandwidth utilization : (.+?)%', details) + '%' if safe_regex(r'Input bandwidth utilization : (.+?)%', details) != 'N/A' else 'N/A',
        'output_rate': safe_regex(r'Output bandwidth utilization : (.+?)%', details) + '%' if safe_regex(r'Output bandwidth utilization : (.+?)%', details) != 'N/A' else 'N/A',
        'input_errors': safe_regex(r'Input error: (\d+)', details, '0'),
        'output_errors': safe_regex(r'Output error: (\d+)', details, '0')
    }

@app.route('/vlan-info')
def vlan_info():
    if 'device_data' not in session:
        return redirect(url_for('login'))
    
    # Получаем базовую информацию об устройстве
    device_info = {
        'model': session.get('device_data', {}).get('device_type', 'Unknown'),
        'software_version': 'N/A',
        'ip_address': session.get('device_data', {}).get('ip_address', 'Unknown'),
        'uptime': 'N/A'
    }
    
    # Если есть данные устройства в сессии, используем их
    if 'device_status' in session:
        device_status = json.loads(session['device_status'])
        device_info.update({
            'software_version': device_status.get('configuration', {}).get('software_version', 'N/A'),
            'uptime': device_status.get('configuration', {}).get('uptime', 'N/A')
        })
    
    # Получаем информацию о VLAN (реальную или тестовую)
    vlans = get_vlan_info(session['device_data'])
    
    return render_template('vlan_info.html', 
                         device_info=device_info,
                         vlans=vlans)

def get_vlan_info(device_data):
    """Получение информации о VLAN с устройства или тестовых данных"""
    try:
        # Здесь должна быть логика реального подключения к устройству
        # Временно используем тестовые данные
        device_type = device_data.get('device_type', 'Cisco').lower()
        
        if device_type == 'huawei':
            return generate_huawei_vlan_test_data()
        else:
            return generate_cisco_vlan_test_data()
            
    except Exception as e:
        app.logger.error(f"Ошибка получения VLAN информации: {str(e)}")
        return []

def generate_cisco_vlan_test_data():
    """Генерация тестовых данных VLAN для Cisco"""
    return [
        {
            'id': '1',
            'name': 'default',
            'description': 'Default VLAN',
            'status': 'active',
            'port_mode': 'access',
            'access_vlan': '1',
            'allowed_vlans': None,
            'mac_addresses': '00:1A:2B:3C:4D:5E',
            'svi_ip': None
        },
        {
            'id': '10',
            'name': 'Management',
            'description': 'Management VLAN',
            'status': 'active',
            'port_mode': 'access',
            'access_vlan': '10',
            'allowed_vlans': None,
            'mac_addresses': '00:1A:2B:3C:4D:5F',
            'svi_ip': '192.168.10.1'
        },
        {
            'id': '20',
            'name': 'Users',
            'description': 'VLAN for users',
            'status': 'active',
            'port_mode': 'trunk',
            'access_vlan': None,
            'allowed_vlans': '10,20,30',
            'mac_addresses': '00:1A:2B:3C:4D:60,00:1A:2B:3C:4D:61',
            'svi_ip': '192.168.20.1'
        }
    ]

def generate_huawei_vlan_test_data():
    """Генерация тестовых данных VLAN для Huawei"""
    return [
        {
            'id': '1',
            'name': 'default',
            'description': 'Default VLAN',
            'status': 'active',
            'port_mode': 'access',
            'access_vlan': '1',
            'allowed_vlans': None,
            'mac_addresses': '00-1A-2B-3C-4D-5E',
            'svi_ip': None
        },
        {
            'id': '10',
            'name': 'Management',
            'description': 'Management VLAN',
            'status': 'active',
            'port_mode': 'hybrid',
            'access_vlan': '10',
            'allowed_vlans': '10,20',
            'mac_addresses': '00-1A-2B-3C-4D-5F',
            'svi_ip': '192.168.10.1'
        }
    ]



if __name__ == '__main__':
    app.run(debug=True)