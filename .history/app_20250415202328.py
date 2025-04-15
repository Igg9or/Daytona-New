from flask import Flask, render_template, request, session, redirect, url_for, jsonify, flash
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
from device_connector import create_interface_on_device,parse_eltex_routing_table, connect_and_collect_data, parse_cisco_arp_table, parse_huawei_arp_table, parse_eltex_interface_details


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
        interfaces_data = device_status.get('interfaces', [])
        return render_template('interfaces.html', interfaces=interfaces_data)
    
    # Для Eltex устройств возвращаем пустой список, так как данные должны быть в сессии
    if device_type.lower() == 'eltex':
        return render_template('interfaces.html', interfaces=[])
    
    # Иначе генерируем тестовые данные для Cisco/Huawei
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
        netmiko_device_type = 'cisco_ios' if device_type == 'cisco' else 'huawei' if device_type == 'huawei' else 'eltex'
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
            if device_type == 'eltex':
                details_cmd = f'show interfaces {interface_name}'
                details = connection.send_command(details_cmd, delay_factor=2)
                app.logger.debug(f"Полученные данные:\n{details[:500]}...")
                interface_data = parse_eltex_interface_details(details)
            elif device_type == 'huawei':
                details_cmd = f'display interface {interface_name}'
                details = connection.send_command(details_cmd, delay_factor=2)
                interface_data = parse_huawei_interface_details(details)
            else:
                details_cmd = f'show interface {interface_name}'
                details = connection.send_command(details_cmd, delay_factor=2)
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
    """Получение реальной информации о VLAN с устройства"""
    connection = None
    try:
        device_type = device_data.get('device_type', 'Cisco').lower()
        netmiko_device_type = 'cisco_ios' if device_type == 'cisco' else 'huawei' if device_type == 'huawei' else 'eltex'
        
        device_params = {
            'device_type': netmiko_device_type,
            'host': device_data['ip_address'],
            'username': device_data['username'],
            'password': device_data['password'],
            'secret': device_data.get('secret', ''),
            'timeout': 20,
            'session_timeout': 30,
            'global_delay_factor': 2,
            'session_log': 'netmiko_vlan_session.log'
        }
        
        app.logger.info(f"Подключение к {device_data['ip_address']} для получения VLAN информации")
        connection = ConnectHandler(**device_params)
        
        try:
            if device_data.get('secret'):
                connection.enable()
            
            # Получаем информацию о VLAN
            if device_type == 'huawei':
                vlan_output = connection.send_command('display vlan', delay_factor=2)
                svi_output = connection.send_command('display ip interface brief | include Vlanif', delay_factor=2)
                vlans = parse_huawei_vlan_info(vlan_output, svi_output)
            elif device_type == 'eltex':
                vlan_output = connection.send_command('show vlan', delay_factor=2)
                vlans = parse_eltex_vlan_info(vlan_output)
            else:
                vlan_output = connection.send_command('show vlan brief', delay_factor=2)
                svi_output = connection.send_command('show ip interface brief | include Vlan', delay_factor=2)
                vlans = parse_cisco_vlan_info(vlan_output, svi_output)
            
            app.logger.info(f"Успешно получены данные о VLAN")
            return vlans
            
        except Exception as e:
            app.logger.error(f"Ошибка при получении VLAN информации: {str(e)}", exc_info=True)
            return []
            
        finally:
            connection.disconnect()
            
    except NetmikoAuthenticationException as auth_error:
        app.logger.error(f"Ошибка аутентификации: {str(auth_error)}")
        return []
    except NetmikoTimeoutException as timeout_error:
        app.logger.error(f"Таймаут подключения: {str(timeout_error)}")
        return []
    except Exception as e:
        app.logger.error(f"Ошибка подключения: {str(e)}", exc_info=True)
        return []
    
    
    
def parse_cisco_vlan_info(vlan_output, svi_output):
    """Парсинг информации о VLAN для Cisco устройств с портами"""
    vlans = []
    port_info = {}  # Для хранения информации о портах
    
    # Парсим основной вывод VLAN
    for line in vlan_output.splitlines():
        if re.match(r'^\d+\s+\w+', line):
            parts = re.split(r'\s+', line.strip())
            vlan_id = parts[0]
            ports = ' '.join(parts[3:]) if len(parts) > 3 else ''
            
            vlans.append({
                'id': vlan_id,
                'name': parts[1],
                'status': 'active' if parts[2].lower() == 'active' else 'inactive',
                'port_mode': 'access',  # Будет уточнено ниже
                'ports': ports,  # Добавляем порты
                'access_vlan': vlan_id,
                'allowed_vlans': None,
                'mac_addresses': None,
                'svi_ip': None
            })
            
            # Сохраняем порты для этого VLAN
            port_info[vlan_id] = ports
    
    # Получаем дополнительную информацию о портах из show interfaces switchport
    try:
        switchport_output = connection.send_command('show interfaces switchport', delay_factor=2)
        # Здесь можно добавить парсинг для определения режима порта (access/trunk)
    except Exception as e:
        app.logger.error(f"Ошибка получения информации о switchport: {str(e)}")
    
    # Парсим SVI интерфейсы
    svi_ips = {}
    for line in svi_output.splitlines():
        if 'Vlan' in line:
            parts = re.split(r'\s+', line.strip())
            vlan_id = parts[0].replace('Vlan', '')
            svi_ips[vlan_id] = parts[1] if parts[1] != 'unassigned' else None
    
    # Обновляем SVI IP в VLAN информации
    for vlan in vlans:
        if vlan['id'] in svi_ips:
            vlan['svi_ip'] = svi_ips[vlan['id']]
    
    return vlans

def parse_huawei_vlan_info(vlan_output, svi_output):
    """Парсинг информации о VLAN для Huawei устройств с портами"""
    vlans = []
    current_vlan = None
    port_info = {}
    
    # Парсим основной вывод VLAN
    for line in vlan_output.splitlines():
        if line.startswith('VLAN ID:'):
            if current_vlan:
                vlans.append(current_vlan)
            vlan_id = line.split(':')[1].strip()
            current_vlan = {
                'id': vlan_id,
                'name': '',
                'status': 'active',
                'port_mode': 'hybrid',
                'ports': '',  # Будет заполнено ниже
                'access_vlan': None,
                'allowed_vlans': None,
                'mac_addresses': None,
                'svi_ip': None
            }
        elif line.startswith('VLAN Name:'):
            current_vlan['name'] = line.split(':')[1].strip()
        elif 'Untagged' in line or 'Tagged' in line:
            # Это строка с информацией о портах
            port_type = 'Untagged' if 'Untagged' in line else 'Tagged'
            ports = line.split(':')[1].strip()
            current_vlan['ports'] += f"{port_type}: {ports} "
    
    if current_vlan:
        vlans.append(current_vlan)
    
    # Парсим SVI интерфейсы
    svi_ips = {}
    for line in svi_output.splitlines():
        if 'Vlanif' in line:
            parts = re.split(r'\s+', line.strip())
            vlan_id = parts[0].replace('Vlanif', '')
            svi_ips[vlan_id] = parts[1] if parts[1] != 'unassigned' else None
    
    # Обновляем SVI IP в VLAN информации
    for vlan in vlans:
        if vlan['id'] in svi_ips:
            vlan['svi_ip'] = svi_ips[vlan['id']]
    
    return vlans


@app.route('/create-interface', methods=['POST'])
def create_interface():
    if 'device_data' not in session:
        return jsonify({'success': False, 'message': 'Требуется авторизация'}), 401
    
    try:
        data = request.get_json()
        device_data = session['device_data']
        
        # Реальное создание интерфейса на устройстве
        success, result = create_interface_on_device(device_data, data)
        
        if success:
            # Обновляем данные устройства после изменения
            result = connect_and_collect_data(device_data)
            if result['status'] == 'success':
                session['device_status'] = json.dumps(result['data'])
                session['last_update'] = datetime.now().isoformat()
            
            return jsonify({
                'success': True,
                'message': 'Интерфейс успешно создан',
                'details': result
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Ошибка при создании интерфейса: {result}'
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"Ошибка в create_interface: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Ошибка: {str(e)}'
        }), 500

@app.route('/vlan-details')
def vlan_details():
    if 'device_data' not in session:
        return redirect(url_for('login'))
    
    device_info = {
        'model': session['device_data'].get('device_type', 'Unknown'),
        'software_version': 'N/A',
        'ip_address': session['device_data'].get('ip_address', 'Unknown')
    }
    
    if 'device_status' in session:
        device_status = json.loads(session['device_status'])
        device_info['software_version'] = device_status.get('configuration', {}).get('software_version', 'N/A')
    
    vlans = get_vlan_list(session['device_data'])
    
    return render_template('vlan_details.html',
                         device_info=device_info,
                         vlans=vlans)

@app.route('/get-vlan-details')
def get_vlan_details():
    if 'device_data' not in session:
        return jsonify({'error': 'Требуется авторизация'}), 401
    
    vlan_id = request.args.get('id')
    if not vlan_id:
        return jsonify({'error': 'Не указан ID VLAN'}), 400
    
    try:
        vlan_details = get_real_vlan_details(session['device_data'], vlan_id)
        return jsonify(vlan_details)
    except Exception as e:
        app.logger.error(f"Ошибка получения деталей VLAN: {str(e)}")
        return jsonify({'error': str(e)}), 500

def get_vlan_list(device_data):
    """Получаем список VLAN с устройства"""
    connection = None
    try:
        device_type = device_data.get('device_type', 'Cisco').lower()
        netmiko_device_type = 'cisco_ios' if device_type == 'cisco' else 'huawei'
        
        connection = ConnectHandler(
            device_type=netmiko_device_type,
            host=device_data['ip_address'],
            username=device_data['username'],
            password=device_data['password'],
            secret=device_data.get('secret', ''),
            timeout=20
        )
        
        if device_data.get('secret'):
            connection.enable()
        
        if device_type == 'cisco':
            output = connection.send_command('show vlan brief')
            return parse_cisco_vlan_list(output)
        else:
            output = connection.send_command('display vlan')
            return parse_huawei_vlan_list(output)
            
    except Exception as e:
        app.logger.error(f"Ошибка получения списка VLAN: {str(e)}")
        return []
    finally:
        if connection:
            connection.disconnect()

def get_real_vlan_details(device_data, vlan_id):
    """Получаем детальную информацию о VLAN"""
    connection = None
    try:
        device_type = device_data.get('device_type', 'Cisco').lower()
        netmiko_device_type = 'cisco_ios' if device_type == 'cisco' else 'huawei'
        
        connection = ConnectHandler(
            device_type=netmiko_device_type,
            host=device_data['ip_address'],
            username=device_data['username'],
            password=device_data['password'],
            secret=device_data.get('secret', ''),
            timeout=20
        )
        
        if device_data.get('secret'):
            connection.enable()
        
        if device_type == 'cisco':
            vlan_output = connection.send_command(f'show vlan id {vlan_id}')
            svi_output = connection.send_command(f'show interface Vlan{vlan_id}')
            ports_output = connection.send_command(f'show interface status | include {vlan_id}')
            return parse_cisco_vlan_details(vlan_id, vlan_output, svi_output, ports_output)
        else:
            vlan_output = connection.send_command(f'display vlan {vlan_id}')
            svi_output = connection.send_command(f'display interface Vlanif{vlan_id}')
            ports_output = connection.send_command(f'display interface brief | include {vlan_id}')
            return parse_huawei_vlan_details(vlan_id, vlan_output, svi_output, ports_output)
            
    except Exception as e:
        app.logger.error(f"Ошибка получения деталей VLAN {vlan_id}: {str(e)}")
        raise Exception(f"Не удалось получить данные VLAN: {str(e)}")
    finally:
        if connection:
            connection.disconnect()

def parse_cisco_vlan_list(output):
    """Парсим список VLAN для Cisco"""
    vlans = []
    for line in output.splitlines():
        if re.match(r'^\d+\s+\w+', line):
            parts = re.split(r'\s+', line.strip())
            vlans.append({
                'id': parts[0],
                'name': parts[1],
                'status': parts[2]
            })
    return vlans

def parse_huawei_vlan_list(output):
    """Парсим список VLAN для Huawei"""
    vlans = []
    current_vlan = None
    
    for line in output.splitlines():
        if line.startswith('VLAN ID:'):
            if current_vlan:
                vlans.append(current_vlan)
            current_vlan = {
                'id': line.split(':')[1].strip(),
                'name': '',
                'status': 'active'
            }
        elif line.startswith('VLAN Name:'):
            current_vlan['name'] = line.split(':')[1].strip()
    
    if current_vlan:
        vlans.append(current_vlan)
    
    return vlans

def parse_cisco_vlan_details(vlan_id, vlan_output, svi_output, ports_output):
    """Парсим детали VLAN для Cisco"""
    details = {
        'id': vlan_id,
        'name': '',
        'status': 'active',
        'description': '',
        'ports': [],
        'ip': '',
        'netmask': '',
        'mtu': '1500',
        'dhcp': 'Disabled',
        'mac': '',
        'traffic_in': '0 bps',
        'traffic_out': '0 bps'
    }
    
    # Парсим основную информацию VLAN
    for line in vlan_output.splitlines():
        if 'Name' in line and not details['name']:
            details['name'] = line.split('Name')[1].strip()
    
    # Парсим SVI интерфейс
    for line in svi_output.splitlines():
        if 'Internet address is' in line:
            ip_parts = line.split('Internet address is')[1].strip().split('/')
            details['ip'] = ip_parts[0]
            if len(ip_parts) > 1:
                details['netmask'] = f"/{ip_parts[1]}"
        elif 'MTU' in line:
            details['mtu'] = line.split('MTU')[1].split()[0]
        elif 'Hardware is' in line:
            details['mac'] = line.split('address is')[1].split()[0]
    
    # Парсим порты
    for line in ports_output.splitlines():
        if 'connected' in line.lower():
            port = line.split()[0]
            details['ports'].append(port)
    
    return details

def parse_huawei_vlan_details(vlan_id, vlan_output, svi_output, ports_output):
    """Парсим детали VLAN для Huawei"""
    details = {
        'id': vlan_id,
        'name': '',
        'status': 'active',
        'description': '',
        'ports': [],
        'ip': '',
        'netmask': '',
        'mtu': '1500',
        'dhcp': 'Disabled',
        'mac': '',
        'traffic_in': '0 bps',
        'traffic_out': '0 bps'
    }
    
    # Парсим основную информацию VLAN
    for line in vlan_output.splitlines():
        if 'VLAN Name:' in line:
            details['name'] = line.split(':')[1].strip()
        elif 'Description:' in line:
            details['description'] = line.split(':')[1].strip()
    
    # Парсим SVI интерфейс
    for line in svi_output.splitlines():
        if 'Internet Address is' in line:
            ip_parts = line.split('Internet Address is')[1].strip().split('/')
            details['ip'] = ip_parts[0]
            if len(ip_parts) > 1:
                details['netmask'] = f"/{ip_parts[1]}"
        elif 'The Maximum Transmit Unit is' in line:
            details['mtu'] = line.split('is')[1].strip()
        elif 'Hardware address is' in line:
            details['mac'] = line.split('is')[1].strip()
    
    # Парсим порты
    for line in ports_output.splitlines():
        if 'up' in line.lower() or 'down' in line.lower():
            port = line.split()[0]
            details['ports'].append(port)
    
    return details


@app.route('/update-vlan', methods=['POST'])
def update_vlan():
    if 'device_data' not in session:
        return jsonify({'success': False, 'message': 'Требуется авторизация'}), 401
    
    try:
        data = request.get_json()
        device_data = session['device_data']
        device_type = device_data.get('device_type', 'Cisco').lower()
        
        # Подключаемся к устройству
        netmiko_device_type = 'cisco_ios' if device_type == 'cisco' else 'huawei'
        connection = ConnectHandler(
            device_type=netmiko_device_type,
            host=device_data['ip_address'],
            username=device_data['username'],
            password=device_data['password'],
            secret=device_data.get('secret', ''),
            timeout=20
        )
        
        try:
            connection.enable()
            
            if device_type == 'cisco':
                commands = [
                    f"vlan {data['id']}",
                    f"name {data['name']}",
                    f"description {data['description']}" if data.get('description') else "no description",
                ]
            else:  # Huawei
                commands = [
                    f"vlan {data['id']}",
                    f"description {data['description']}" if data.get('description') else "undo description",
                    f"name {data['name']}",
                ]
            
            # Применяем команды
            output = connection.send_config_set(commands)
            
            # Для режима порта обновляем все интерфейсы этого VLAN
            if data.get('port_mode'):
                interfaces = get_interfaces_for_vlan(connection, data['id'], device_type)
                for intf in interfaces:
                    if device_type == 'cisco':
                        cmd = [
                            f"interface {intf}",
                            f"switchport mode {data['port_mode']}",
                            f"switchport access vlan {data['id']}" if data['port_mode'] == 'access' else "",
                        ]
                    else:  # Huawei
                        cmd = [
                            f"interface {intf}",
                            f"port link-type {data['port_mode']}",
                            f"port default vlan {data['id']}" if data['port_mode'] == 'access' else "",
                        ]
                    connection.send_config_set(cmd)
            
            # Сохраняем конфигурацию
            if device_type == 'cisco':
                connection.send_command('write memory')
            else:  # Huawei
                connection.send_command('save force')
            
            return jsonify({
                'success': True,
                'message': 'VLAN успешно обновлен',
                'output': output
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Ошибка на устройстве: {str(e)}',
                'suggestions': [
                    'Проверьте правильность параметров VLAN',
                    'Убедитесь, что VLAN существует',
                    'Проверьте права доступа'
                ]
            })
        finally:
            connection.disconnect()
            
    except NetmikoAuthenticationException:
        return jsonify({'success': False, 'message': 'Ошибка аутентификации'}), 401
    except NetmikoTimeoutException:
        return jsonify({'success': False, 'message': 'Таймаут подключения'}), 408
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }), 500
    
def get_interfaces_for_vlan(connection, vlan_id, device_type):
    """Получаем список интерфейсов для указанного VLAN"""
    try:
        if device_type == 'cisco':
            output = connection.send_command(f"show vlan id {vlan_id}")
            interfaces = []
            for line in output.splitlines():
                if re.match(r'^\s*[A-Za-z]+\d+/\d+', line):
                    interfaces.append(line.split()[0])
            return interfaces
        else:  # Huawei
            output = connection.send_command(f"display vlan {vlan_id}")
            interfaces = []
            for line in output.splitlines():
                if 'Untagged' in line or 'Tagged' in line:
                    ports = line.split(':')[1].strip().split()
                    interfaces.extend(ports)
            return interfaces
    except Exception:
        return []

@app.route('/routing-table')
def routing_table():
    if 'device_data' not in session:
        return redirect(url_for('login'))
    
    device_info = {
        'model': session['device_data'].get('device_type', 'Unknown'),
        'software_version': 'N/A',
        'ip_address': session['device_data'].get('ip_address', 'Unknown'),
        'uptime': 'N/A'
    }
    
    if 'device_status' in session:
        device_status = json.loads(session['device_status'])
        device_info['software_version'] = device_status.get('configuration', {}).get('software_version', 'N/A')
        device_info['uptime'] = device_status.get('configuration', {}).get('uptime', 'N/A')
    
    # Получаем таблицу маршрутизации
    routing_table = get_routing_table(session['device_data'])
    
    return render_template('routing_table.html',
                         device_info=device_info,
                         routing_table=routing_table)

@app.route('/refresh-routing-table')
def refresh_routing_table():
    if 'device_data' not in session:
        return redirect(url_for('login'))
    
    # Обновляем данные устройства
    result = connect_and_collect_data(session['device_data'])
    if result['status'] == 'success':
        session['device_status'] = json.dumps(result['data'])
        session['last_update'] = datetime.now().isoformat()
    
    return redirect(url_for('routing_table'))

def get_routing_table(device_data):
    """Получение таблицы маршрутизации с устройства"""
    connection = None
    try:
        device_type = device_data.get('device_type', 'Cisco').lower()
        netmiko_device_type = {
            'cisco': 'cisco_ios',
            'huawei': 'huawei',
            'eltex': 'eltex'
        }.get(device_type, 'cisco_ios')
        
        connection = ConnectHandler(
            device_type=netmiko_device_type,
            host=device_data['ip_address'],
            username=device_data['username'],
            password=device_data['password'],
            secret=device_data.get('secret', ''),
            timeout=20
        )
        
        if device_data.get('secret'):
            connection.enable()
        
        if device_type == 'cisco':
            output = connection.send_command('show ip route', delay_factor=2)
            return parse_cisco_routing_table(output)
        elif device_type == 'huawei':
            output = connection.send_command('display ip routing-table', delay_factor=2)
            return parse_huawei_routing_table(output)
        elif device_type == 'eltex':
            output = connection.send_command('show ip route', delay_factor=2)
            return parse_eltex_routing_table(output)
        else:
            return []
            
    except Exception as e:
        app.logger.error(f"Ошибка получения таблицы маршрутизации: {str(e)}")
        return []
    finally:
        if connection:
            connection.disconnect()

def parse_eltex_routing_table(output):
    """Парсинг вывода Eltex 'show ip route'"""
    routes = []
    
    for line in output.splitlines():
        if not line.strip() or line.startswith('Maximum Parallel Paths') or line.startswith('Load balancing') or line.startswith('IP Forwarding') or line.startswith('Codes:') or line.startswith('[d/m]:'):
            continue
            
        # Обработка маршрутов
        if line.strip() and line[0].isalpha() and len(line.split()) >= 3:
            parts = line.split()
            route_type = parts[0][0]  # Первый символ - тип маршрута
            
            # Для маршрутов типа "O IA" (OSPF inter-area)
            if len(parts[0]) > 1 and parts[0][1] == '*':
                route_type = parts[0][0]
                
            network = parts[1]
            mask_or_prefix = None
            admin_distance = None
            metric = None
            next_hop = None
            interface = None
            time_info = None
            
            # Обработка разных форматов вывода
            if 'is directly connected' in line:
                # Пример: C    192.168.1.0/24 is directly connected, te1/0/1
                interface = line.split(',')[-1].strip()
                next_hop = '0.0.0.0'
                if '/' in network:
                    network, mask_or_prefix = network.split('/')
            elif 'via' in line:
                # Пример: S    0.0.0.0/0 [1/2] via 172.23.88.1, 150:27:04, oob
                via_index = parts.index('via')
                if '/' in network:
                    network, mask_or_prefix = network.split('/')
                
                # Извлекаем административное расстояние и метрику
                if '[' in parts[2]:
                    adm_metric = parts[2].strip('[]')
                    admin_distance, metric = adm_metric.split('/')
                
                next_hop = parts[via_index + 1].rstrip(',')
                
                # Интерфейс и время могут быть не у всех маршрутов
                if len(parts) > via_index + 2:
                    if ',' in parts[via_index + 2]:
                        time_info = parts[via_index + 2].rstrip(',')
                        interface = parts[via_index + 3] if len(parts) > via_index + 3 else None
                    else:
                        interface = parts[via_index + 2]
            
            routes.append({
                'type': route_type,
                'network': network,
                'mask': None,
                'prefix': mask_or_prefix,
                'admin_distance': admin_distance,
                'metric': metric,
                'next_hop': next_hop,
                'interface': interface,
                'time': time_info
            })
    
    return routes

def parse_cisco_routing_table(output):
    """Парсинг таблицы маршрутизации Cisco"""
    routes = []
    for line in output.splitlines():
        if line.startswith(('C', 'D', 'S', 'O', 'R', 'i')):
            parts = line.split()
            route = {
                'type': parts[0],
                'network': parts[1],
                'mask': parts[2] if len(parts) > 2 else '255.255.255.255',
                'admin_distance': parts[3].strip('[]') if '[' in parts[3] else '',
                'metric': parts[4].strip('/') if '/' in parts[4] else '',
                'next_hop': parts[5] if len(parts) > 5 else '',
                'interface': parts[6] if len(parts) > 6 else '',
                'time': parts[7] if len(parts) > 7 else ''
            }
            routes.append(route)
    return routes

def parse_huawei_routing_table(output):
    """Парсинг таблицы маршрутизации Huawei"""
    routes = []
    for line in output.splitlines():
        if line.startswith(('D', 'C', 'S', 'O', 'R', 'i')):
            parts = line.split()
            route = {
                'type': parts[0],
                'network': parts[1].split('/')[0],
                'mask': parts[1].split('/')[1] if '/' in parts[1] else '32',
                'admin_distance': parts[2],
                'metric': parts[3],
                'next_hop': parts[4] if len(parts) > 4 else '',
                'interface': parts[5] if len(parts) > 5 else '',
                'time': parts[6] if len(parts) > 6 else ''
            }
            routes.append(route)
    return routes

@app.route('/mac-table')
def mac_table():
    if 'device_data' not in session:
        return redirect(url_for('login'))
    
    device_info = {
        'model': session['device_data'].get('device_type', 'Unknown'),
        'software_version': 'N/A',
        'ip_address': session['device_data'].get('ip_address', 'Unknown'),
        'uptime': 'N/A'
    }
    
    if 'device_status' in session:
        device_status = json.loads(session['device_status'])
        device_info['software_version'] = device_status.get('configuration', {}).get('software_version', 'N/A')
        device_info['uptime'] = device_status.get('configuration', {}).get('uptime', 'N/A')
    
    # Получаем таблицу коммутации
    mac_table = get_mac_table(session['device_data'])
    
    return render_template('mac_table.html',
                         device_info=device_info,
                         mac_table=mac_table,
                         last_update=session.get('last_update', 'N/A'))

@app.route('/refresh-mac-table')
def refresh_mac_table():
    if 'device_data' not in session:
        return redirect(url_for('login'))
    
    # Обновляем данные устройства
    result = connect_and_collect_data(session['device_data'])
    if result['status'] == 'success':
        session['device_status'] = json.dumps(result['data'])
        session['last_update'] = datetime.now().isoformat()
    
    return redirect(url_for('mac_table'))

def get_mac_table(device_data):
    """Получение MAC-таблицы с устройства"""
    connection = None
    try:
        device_type = device_data.get('device_type', 'Cisco').lower()
        netmiko_device_type = 'cisco_ios' if device_type == 'cisco' else 'huawei'
        
        connection = ConnectHandler(
            device_type=netmiko_device_type,
            host=device_data['ip_address'],
            username=device_data['username'],
            password=device_data['password'],
            secret=device_data.get('secret', ''),
            timeout=20
        )
        
        if device_data.get('secret'):
            connection.enable()
        
        if device_type == 'cisco':
            output = connection.send_command('show mac address-table', delay_factor=2)
            return parse_cisco_mac_table(output)
        else:
            output = connection.send_command('display mac-address', delay_factor=2)
            return parse_huawei_mac_table(output)
            
    except Exception as e:
        app.logger.error(f"Ошибка получения MAC-таблицы: {str(e)}")
        return None
    finally:
        if connection:
            connection.disconnect()

@app.route('/arp-table')
def arp_table():
    if 'device_data' not in session:
        return redirect(url_for('login'))
    
    device_info = {
        'model': session['device_data'].get('device_type', 'Unknown'),
        'software_version': 'N/A',
        'ip_address': session['device_data'].get('ip_address', 'Unknown'),
        'uptime': 'N/A'
    }
    
    if 'device_status' in session:
        device_status = json.loads(session['device_status'])
        device_info['software_version'] = device_status.get('configuration', {}).get('software_version', 'N/A')
        device_info['uptime'] = device_status.get('configuration', {}).get('uptime', 'N/A')
    
    # Получаем ARP таблицу
    arp_table = get_arp_table(session['device_data'])
    
    return render_template('arp_table.html',
                         device_info=device_info,
                         arp_table=arp_table,
                         last_update=session.get('last_update', 'N/A'))

@app.route('/refresh-arp-table')
def refresh_arp_table():
    if 'device_data' not in session:
        return redirect(url_for('login'))
    
    # Обновляем данные устройства
    result = connect_and_collect_data(session['device_data'])
    if result['status'] == 'success':
        session['device_status'] = json.dumps(result['data'])
        session['last_update'] = datetime.now().isoformat()
    
    return redirect(url_for('arp_table'))

def get_arp_table(device_data):
    """Получение ARP таблицы с устройства"""
    connection = None
    try:
        device_type = device_data.get('device_type', 'Cisco').lower()
        netmiko_device_type = 'cisco_ios' if device_type == 'cisco' else 'huawei'
        
        connection = ConnectHandler(
            device_type=netmiko_device_type,
            host=device_data['ip_address'],
            username=device_data['username'],
            password=device_data['password'],
            secret=device_data.get('secret', ''),
            timeout=20
        )
        
        if device_data.get('secret'):
            connection.enable()
        
        if device_type == 'cisco':
            output = connection.send_command('show arp', delay_factor=2)
            return parse_cisco_arp_table(output)
        else:
            output = connection.send_command('display arp', delay_factor=2)
            return parse_huawei_arp_table(output)
            
    except Exception as e:
        app.logger.error(f"Ошибка получения ARP таблицы: {str(e)}")
        return None
    finally:
        if connection:
            connection.disconnect()

@app.route('/device-config')
def device_config():
    if 'device_data' not in session:
        return redirect(url_for('login'))
    
    # Базовые данные устройства
    device_info = {
        'model': session['device_data'].get('device_type', 'Unknown'),
        'ip_address': session['device_data'].get('ip_address', 'Unknown'),
        'software_version': 'N/A',
        'uptime': 'N/A'
    }
    
    # Дополняем данными из сессии, если они есть
    if 'device_status' in session:
        device_status = json.loads(session['device_status'])
        device_info.update({
            'software_version': device_status.get('configuration', {}).get('software_version', 'N/A'),
            'uptime': device_status.get('configuration', {}).get('uptime', 'N/A')
        })
    
    # Получаем конфигурацию устройства
    try:
        full_config = get_device_configuration(session['device_data'])
        if not full_config:
            raise Exception("Не удалось получить конфигурацию")
    except Exception as e:
        app.logger.error(f"Ошибка при получении конфигурации: {str(e)}")
        # Создаем пустую конфигурацию для шаблона
        full_config = {
            'raw_config': 'Не удалось загрузить конфигурацию устройства',
            'parsed_config': {
                'hostname': 'N/A',
                'domain_name': 'N/A',
                'vlans': [],
                'interfaces': [],
                'snmp': {'enabled': False, 'community': 'N/A'},
                'ntp': {'enabled': False, 'servers': []},
                'aaa': {'new_model': False, 'authentication': []},
                'logging': {'enabled': False, 'servers': []},
                'tacacs': {'enabled': False, 'servers': []}
            }
        }
        flash(f"Ошибка: {str(e)}", 'error')
    
    return render_template('device_config.html',
                         device_info=device_info,
                         full_config=full_config)

def get_device_configuration(device_data):
    """Получение и парсинг конфигурации устройства"""
    connection = None
    try:
        device_type = device_data.get('device_type', 'cisco').lower()
        netmiko_device_type = 'cisco_ios' if device_type == 'cisco' else 'huawei'
        
        connection = ConnectHandler(
            device_type=netmiko_device_type,
            host=device_data['ip_address'],
            username=device_data['username'],
            password=device_data['password'],
            secret=device_data.get('secret', ''),
            timeout=30,
            global_delay_factor=2
        )
        
        if device_data.get('secret'):
            connection.enable()
        
        # Получаем полную конфигурацию
        cmd = 'show running-config' if device_type == 'cisco' else 'display current-configuration'
        output = connection.send_command(cmd, delay_factor=2)
        
        # Парсим конфигурацию
        parsed_config = parse_device_configuration(output, device_type)
        
        return {
            'raw_config': output,
            'parsed_config': parsed_config
        }
        
    except Exception as e:
        app.logger.error(f"Ошибка получения конфигурации: {str(e)}")
        return None
    finally:
        if connection:
            connection.disconnect()

def parse_device_configuration(config, device_type):
    """Парсинг конфигурации устройства"""
    result = {
        'hostname': 'N/A',
        'domain_name': 'N/A',
        'vlans': [],
        'interfaces': [],
        'snmp': {'enabled': False, 'community': 'N/A'},
        'ntp': {'enabled': False, 'servers': []},
        'aaa': {'new_model': False, 'authentication': []},
        'logging': {'enabled': False, 'servers': []},
        'tacacs': {'enabled': False, 'servers': []}
    }
    
    try:
        # Hostname
        hostname_match = re.search(r'hostname\s+(\S+)', config)
        if hostname_match:
            result['hostname'] = hostname_match.group(1)
        
        # Domain name
        domain_match = re.search(r'ip\s+domain-name\s+(\S+)', config)
        if domain_match:
            result['domain_name'] = domain_match.group(1)
        
        # VLANs
        if device_type == 'cisco':
            vlan_matches = re.finditer(r'vlan\s+(\d+)\s*\n\s*name\s+(\S+)', config)
            result['vlans'] = [{'id': m.group(1), 'name': m.group(2)} for m in vlan_matches]
        else:
            vlan_matches = re.finditer(r'vlan\s+(\d+)\s*\n\s*description\s+(.+?)\n', config)
            result['vlans'] = [{'id': m.group(1), 'name': m.group(2).strip()} for m in vlan_matches]
        
        # Interfaces
        if device_type == 'cisco':
            intf_matches = re.finditer(r'interface\s+(\S+)\s*\n(.*?)(?=\ninterface|\Z)', config, re.DOTALL)
        else:
            intf_matches = re.finditer(r'interface\s+(\S+)\s*\n(.*?)(?=\ninterface|\Z)', config, re.DOTALL)
        
        for match in intf_matches:
            intf_config = match.group(2)
            intf_data = {
                'name': match.group(1),
                'description': re.search(r'description\s+(.+?)\n', intf_config).group(1).strip() 
                             if 'description' in intf_config else 'N/A',
                'ip': re.search(r'ip\s+address\s+(\S+\s+\S+)', intf_config).group(1) 
                     if 'ip address' in intf_config else 'N/A',
                'status': 'down' if 'shutdown' in intf_config else 'up'
            }
            result['interfaces'].append(intf_data)
        
        # SNMP
        snmp_match = re.search(r'snmp-server\s+community\s+(\S+)', config)
        if snmp_match:
            result['snmp'] = {
                'enabled': True,
                'community': snmp_match.group(1)
            }
        
        # NTP
        ntp_servers = re.findall(r'ntp\s+server\s+(\S+)', config)
        if ntp_servers:
            result['ntp'] = {
                'enabled': True,
                'servers': ntp_servers
            }
        
        # AAA
        if 'aaa new-model' in config:
            result['aaa']['new_model'] = True
            result['aaa']['authentication'] = re.findall(r'aaa\s+authentication\s+(\S+.+?)\n', config)
        
        # Logging
        logging_servers = re.findall(r'logging\s+host\s+(\S+)', config)
        if logging_servers:
            result['logging'] = {
                'enabled': True,
                'servers': logging_servers
            }
        
        # TACACS
        tacacs_servers = re.findall(r'tacacs-server\s+host\s+(\S+)', config)
        if tacacs_servers:
            result['tacacs'] = {
                'enabled': True,
                'servers': tacacs_servers
            }
    
    except Exception as e:
        app.logger.error(f"Ошибка парсинга конфигурации: {str(e)}")
    
    return result

@app.route('/refresh-config')
def refresh_config():
    if 'device_data' not in session:
        return redirect(url_for('login'))
    
    try:
        # Обновляем данные устройства
        result = connect_and_collect_data(session['device_data'])
        if result['status'] == 'success':
            session['device_status'] = json.dumps(result['data'])
            session['last_update'] = datetime.now().isoformat()
            flash('Конфигурация успешно обновлена', 'success')
        else:
            flash('Не удалось обновить конфигурацию', 'error')
    
    except Exception as e:
        flash(f'Ошибка при обновлении конфигурации: {str(e)}', 'error')
    
    return redirect(url_for('device_config'))

@app.route('/device-logs')
def device_logs():
    if 'device_data' not in session:
        return redirect(url_for('login'))
    
    # Получаем данные устройства
    device_info = {
        'model': session['device_data'].get('device_type', 'Unknown'),
        'ip_address': session['device_data'].get('ip_address', 'Unknown'),
        'software_version': 'N/A',
        'uptime': 'N/A'
    }
    
    # Если есть данные в сессии, используем их
    if 'device_status' in session:
        device_status = json.loads(session['device_status'])
        device_info.update({
            'software_version': device_status.get('configuration', {}).get('software_version', 'N/A'),
            'uptime': device_status.get('configuration', {}).get('uptime', 'N/A')
        })
    
    # Получаем логи устройства
    logs = get_device_logs(session['device_data'])
    
    return render_template('device_logs.html',
                         device_info=device_info,
                         logs=logs)

def get_device_logs(device_data):
    """Получение логов с устройства"""
    connection = None
    try:
        device_type = device_data.get('device_type', 'cisco').lower()
        netmiko_device_type = 'cisco_ios' if device_type == 'cisco' else 'huawei'
        
        connection = ConnectHandler(
            device_type=netmiko_device_type,
            host=device_data['ip_address'],
            username=device_data['username'],
            password=device_data['password'],
            secret=device_data.get('secret', ''),
            timeout=30,
            global_delay_factor=2
        )
        
        if device_data.get('secret'):
            connection.enable()
        
        # Для Cisco
        if device_type == 'cisco':
            output = connection.send_command('show logging', delay_factor=2)
            logs = parse_cisco_logs(output)
        # Для Huawei
        else:
            output = connection.send_command('display logbuffer', delay_factor=2)
            logs = parse_huawei_logs(output)
        
        return logs
        
    except Exception as e:
        app.logger.error(f"Ошибка получения логов: {str(e)}")
        return []
    finally:
        if connection:
            connection.disconnect()

def parse_cisco_logs(log_output):
    """Парсинг логов Cisco"""
    logs = []
    for line in log_output.splitlines():
        if not line.strip():
            continue
        
        # Пример формата: *Apr 11 15:22:01.123: %LINK-3-UPDOWN: Interface GigabitEthernet0/1, changed state to up
        log_entry = {
            'raw': line,
            'timestamp': ' '.join(line.split()[:2]) if len(line.split()) > 1 else 'N/A',
            'severity': 'info',
            'message': line
        }
        
        # Определяем уровень важности
        if '%LINEPROTO-5' in line:
            log_entry['severity'] = 'info'
            log_entry['message'] = line.split('%LINEPROTO-5:')[-1].strip()
        elif '%LINK-3' in line:
            log_entry['severity'] = 'warning'
            log_entry['message'] = line.split('%LINK-3:')[-1].strip()
        elif '%SYS-5' in line:
            log_entry['severity'] = 'info'
            log_entry['message'] = line.split('%SYS-5:')[-1].strip()
        elif '%LINEPROTO-5' in line:
            log_entry['severity'] = 'info'
            log_entry['message'] = line.split('%LINEPROTO-5:')[-1].strip()
        
        logs.append(log_entry)
    
    return logs[-100:]  # Возвращаем последние 100 записей

def parse_huawei_logs(log_output):
    """Парсинг логов Huawei"""
    logs = []
    for line in log_output.splitlines():
        if not line.strip():
            continue
        
        # Пример формата: Apr 11 2025 15:22:01 HUAWEI %%01IFNET/4/LINK_STATE(l)[42]:Interface GigabitEthernet0/0/1 has turned into UP state.
        log_entry = {
            'raw': line,
            'timestamp': ' '.join(line.split()[:4]) if len(line.split()) > 3 else 'N/A',
            'severity': 'info',
            'message': line
        }
        
        # Определяем уровень важности
        if '%%01' in line:
            parts = line.split('%%01')
            if len(parts) > 1:
                severity_part = parts[1].split('/')[2] if '/' in parts[1] else ''
                if severity_part.startswith('1'):
                    log_entry['severity'] = 'critical'
                elif severity_part.startswith('2'):
                    log_entry['severity'] = 'error'
                elif severity_part.startswith('3'):
                    log_entry['severity'] = 'warning'
                elif severity_part.startswith('4'):
                    log_entry['severity'] = 'notice'
                else:
                    log_entry['severity'] = 'info'
                
                log_entry['message'] = parts[1].split(']:')[-1].strip()
        
        logs.append(log_entry)
    
    return logs[-100:]  # Возвращаем последние 100 записей

@app.route('/refresh-logs')
def refresh_logs():
    if 'device_data' not in session:
        return redirect(url_for('login'))
    
    try:
        # Обновляем данные устройства
        result = connect_and_collect_data(session['device_data'])
        if result['status'] == 'success':
            session['device_status'] = json.dumps(result['data'])
            session['last_update'] = datetime.now().isoformat()
            flash('Логи успешно обновлены', 'success')
        else:
            flash('Не удалось обновить логи', 'error')
    
    except Exception as e:
        flash(f'Ошибка при обновлении логов: {str(e)}', 'error')
    
    return redirect(url_for('device_logs'))


if __name__ == '__main__':
    app.run(debug=True)