import random
import time
from datetime import datetime
from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
import re
from datetime import datetime

# Тестовые учетные данные (для имитации успешной аутентификации)
TEST_CREDENTIALS = {
    "admin": "cisco123",
    "user": "password123",
    "test": "test123"
}

def connect_and_collect_data(device_data):
    """Реальное подключение к устройству через SSH с улучшенной обработкой ошибок"""
    try:
        device_type = device_data.get('device_type', 'Cisco').lower()
        netmiko_device_type = 'cisco_ios' if device_type == 'cisco' else 'huawei'
        
        device_params = {
            'device_type': netmiko_device_type,
            'host': device_data['ip_address'],
            'username': device_data['username'],
            'password': device_data['password'],
            'secret': device_data.get('secret', ''),
            'timeout': 15,  # Увеличиваем таймаут
        }
        
        print(f"Попытка подключения к {device_data['ip_address']}...")
        connection = ConnectHandler(**device_params)
        
        try:
            if device_data.get('secret'):
                connection.enable()
            
            print("Собираем данные с устройства...")
            result = {
                'status': 'success',
                'data': collect_real_device_data(connection, device_data)
            }
            
            return result
            
        except Exception as inner_error:
            print(f"Ошибка при сборе данных: {str(inner_error)}")
            return {
                'status': 'error',
                'message': f'Ошибка при сборе данных: {str(inner_error)}'
            }
        finally:
            connection.disconnect()
            
    except NetmikoAuthenticationException as auth_error:
        error_msg = 'Ошибка аутентификации: неверный логин/пароль'
        if 'enable' in str(auth_error):
            error_msg += ' (или неверный enable пароль)'
        return {
            'status': 'error',
            'message': error_msg
        }
    except NetmikoTimeoutException:
        return {
            'status': 'error',
            'message': 'Таймаут подключения: устройство недоступно'
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Ошибка подключения: {str(e)}'
        }
    
def parse_uptime(uptime_str):
    """Парсим время работы устройства"""
    # Пример: "router uptime is 1 week, 2 days, 3 hours, 4 minutes"
    return uptime_str.split('is')[-1].strip() if uptime_str else "N/A"

def parse_cpu(cpu_str):
    """Парсим загрузку CPU"""
    # Пример: "CPU utilization for five seconds: 10%/0%"
    match = re.search(r'(\d+)%', cpu_str)
    return f"{match.group(1)}%" if match else "0%"

def parse_memory(memory_str):
    """Парсим использование памяти"""
    try:
        # Пример для Cisco: "Processor memory: 1000000K total, 300000K used, 700000K free"
        total_match = re.search(r'total\s*:\s*(\d+)', memory_str)
        used_match = re.search(r'used\s*:\s*(\d+)', memory_str)
        
        if total_match and used_match:
            total = int(total_match.group(1))
            used = int(used_match.group(1))
            percent = (used / total) * 100
            return f"{used}K/{total}K ({int(percent)}%)"
        
        return "N/A"
    except Exception:
        return "N/A"
    
def get_temperature(connection, device_type):
    """Получение температуры устройства"""
    try:
        if device_type.lower() == 'cisco':
            # Для Cisco
            temp_output = connection.send_command('show environment temperature')
            if 'invalid' in temp_output.lower():
                return "N/A"
            
            # Парсим температуру (пример для Cisco)
            match = re.search(r'Temperature:\s*(\d+)\s*C', temp_output)
            if match:
                return f"{match.group(1)}°C"
            
        elif device_type.lower() == 'huawei':
            # Для Huawei
            temp_output = connection.send_command('display temperature all')
            if 'invalid' in temp_output.lower():
                return "N/A"
            
            # Парсим температуру (пример для Huawei)
            match = re.search(r'Temperature\s*:\s*(\d+)', temp_output)
            if match:
                return f"{match.group(1)}°C"
        
        return "N/A"
    except Exception:
        return "N/A"
    
def get_gateway(connection):
    """Получение шлюза по умолчанию"""
    try:
        route_output = connection.send_command('show ip route')
        match = re.search(r'via\s+([\d.]+)', route_output)
        return match.group(1) if match else "N/A"
    except Exception:
        return "N/A"   
    
def collect_real_device_data(connection, device_data):
    """Сбор реальных данных с устройства"""
    hostname = connection.find_prompt().replace('#', '').replace('>', '')
    
    uptime_output = connection.send_command('show version | include uptime')
    uptime = parse_uptime(uptime_output)
    
    version_output = connection.send_command('show version | include Software')
    software_version = version_output.split(',')[0].strip() if version_output else "N/A"
    
    cpu_output = connection.send_command('show processes cpu | include CPU')
    cpu_load = parse_cpu(cpu_output)
    
    memory_output = connection.send_command('show memory statistics')
    memory_usage = parse_memory(memory_output)
    
    interfaces_output = connection.send_command('show ip interface brief')
    interfaces = parse_interfaces(interfaces_output)
    
    return {
        'monitoring': {
            'cpu_load': cpu_load,
            'memory_usage': memory_usage,
            'temperature': get_temperature(connection, device_data.get('device_type'))
        },
        'configuration': {
            'hostname': hostname,
            'gateway': get_gateway(connection),
            'software_version': software_version,
            'uptime': uptime
        },
        'interfaces': interfaces,
        'connection_time': f"{datetime.now().timestamp() - connection.start_time:.2f} сек"
    }

def parse_interfaces(interfaces_str):
    """Парсим список интерфейсов с дополнительной информацией"""
    interfaces = []
    for line in interfaces_str.splitlines()[1:]:  # Пропускаем заголовок
        if line.strip():
            parts = line.split()
            if len(parts) >= 6:
                interface = {
                    'name': parts[0],
                    'ip': parts[1] if parts[1] != 'unassigned' else 'N/A',
                    'status': parts[4].lower(),
                    'protocol': parts[5].lower(),
                    'description': '',
                    'vlan': '1',
                    'duplex': 'auto',
                    'speed': 'auto'
                }
                
                # Получаем дополнительную информацию об интерфейсе
                try:
                    details = connection.send_command(f'show interface {parts[0]}')
                    
                    # Парсим описание
                    desc_match = re.search(r'Description:\s*(.+?)\n', details)
                    if desc_match:
                        interface['description'] = desc_match.group(1).strip()
                    
                    # Парсим дуплекс и скорость
                    duplex_match = re.search(r'Duplex:\s*(\w+)', details)
                    if duplex_match:
                        interface['duplex'] = duplex_match.group(1).lower()
                    
                    speed_match = re.search(r'BW\s*(\d+)\s*\w+', details)
                    if speed_match:
                        speed = int(speed_match.group(1))
                        interface['speed'] = f"{speed} Mbps" if speed < 1000 else "1 Gbps"
                    
                except Exception:
                    pass
                
                interfaces.append(interface)
    return interfaces



def generate_cisco_response(device_data):
    """Генерация тестовых данных для Cisco"""
    ip = device_data.get('ip_address', '192.168.1.1')
    return {
        'status': 'success',
        'data': {
            'monitoring': {
                'cpu_load': f"{random.randint(5, 45)}%",
                'memory_usage': f"{random.randint(200, 500)}/1024 MB ({random.randint(20, 50)}%)",
                'temperature': f"{random.randint(35, 55)}°C"
            },
            'configuration': {
                'hostname': f"SW-{random.randint(100, 999)}",
                'gateway': f"{'.'.join(ip.split('.')[:3])}.1",
                'software_version': "15.2(4)M7",
                'uptime': f"{random.randint(1, 30)} дней"
            },
            'interfaces': generate_cisco_interfaces(ip),
            'connection_time': f"{random.uniform(0.8, 2.5):.2f} сек"
        }
    }

def generate_cisco_interfaces(base_ip):
    """Генерация тестовых интерфейсов Cisco"""
    ip_parts = base_ip.split('.')
    return [
        {
            'name': 'GigabitEthernet0/1',
            'description': 'Сервер',
            'status': 'up',
            'vlan': 10,
            'duplex': 'full',
            'speed': '1000'
        },
        {
            'name': 'GigabitEthernet0/2',
            'description': 'Резерв',
            'status': 'down',
            'vlan': 20,
            'duplex': 'auto',
            'speed': '100'
        }
    ]

def generate_huawei_response(device_data):
    """Генерация тестовых данных для Huawei"""
    ip = device_data.get('ip_address', '192.168.1.1')
    return {
        'status': 'success',
        'data': {
            'monitoring': {
                'cpu_load': f"{random.randint(5, 30)}%",
                'memory_usage': f"{random.randint(300, 800)}/2048 MB ({random.randint(15, 40)}%)",
                'temperature': f"{random.randint(30, 45)}°C"
            },
            'configuration': {
                'hostname': f"HW-{random.randint(100, 999)}",
                'gateway': f"{'.'.join(ip.split('.')[:3])}.254",
                'software_version': f"V200R0{random.randint(1, 9)}C00SPC{random.randint(1, 5)}00",
                'uptime': f"{random.randint(1, 60)} дней"
            },
            'interfaces': generate_huawei_interfaces(ip),
            'connection_time': f"{random.uniform(0.5, 1.5):.2f} сек"
        }
    }

def generate_huawei_interfaces(base_ip):
    """Генерация интерфейсов Huawei"""
    return [
        {
            'name': 'GigabitEthernet0/0/1',
            'description': 'Uplink to core',
            'status': 'up',
            'vlan': random.randint(1, 100),
            'duplex': 'full',
            'speed': '1000'
        },
        {
            'name': 'GigabitEthernet0/0/2',
            'description': 'Access port',
            'status': random.choice(['up', 'down']),
            'vlan': random.randint(101, 200),
            'duplex': 'auto',
            'speed': '100'
        }
    ]


def generate_successful_response(device_data):
    """Генерация успешного ответа с тестовыми данными"""
    ip = device_data.get('ip_address', '192.168.1.1')
    return {
        'status': 'success',
        'data': {
            'monitoring': {
                'cpu_load': f"{random.randint(5, 45)}%",
                'memory_usage': f"{random.randint(200, 500)}/1024 MB ({random.randint(20, 50)}%)",
                'temperature': f"{random.randint(35, 55)}°C"
            },
            'configuration': {
                'hostname': f"SW-{random.randint(100, 999)}",
                'gateway': f"{'.'.join(ip.split('.')[:3])}.1",
                'software_version': "15.2(4)M7",
                'uptime': f"{random.randint(1, 30)} дней"
            },
            'interfaces': generate_interfaces(ip),
            'connection_time': f"{random.uniform(0.8, 2.5):.2f} сек"
        }
    }

def generate_interfaces(base_ip):
    """Генерация тестовых интерфейсов"""
    ip_parts = base_ip.split('.')
    return [
        {
            'name': 'GigabitEthernet0/0',
            'ip': base_ip,
            'status': 'up',
            'protocol': 'up'
        },
        {
            'name': 'GigabitEthernet0/1',
            'ip': f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{random.randint(2, 254)}",
            'status': random.choice(['up', 'down']),
            'protocol': random.choice(['up', 'down'])
        }
    ]

# В device_connector.py
def update_interface_on_device(device_data, interface_data):
    """Обновление интерфейса с улучшенной обработкой ошибок"""
    try:
        device_type = device_data.get('device_type', 'Cisco').lower()
        netmiko_device_type = 'cisco_ios' if device_type == 'cisco' else 'huawei'
        
        device_params = {
            'device_type': netmiko_device_type,
            'host': device_data['ip_address'],
            'username': device_data['username'],
            'password': device_data['password'],
            'secret': device_data.get('secret', ''),
            'timeout': 15,
        }
        
        print(f"Подключение для обновления интерфейса {interface_data['interface_name']}...")
        connection = ConnectHandler(**device_params)
        
        try:
            if device_data.get('secret'):
                connection.enable()
            
            commands = [
                f"interface {interface_data['interface_name']}",
                f"description {interface_data['description']}",
            ]
            
            # Добавляем команды в зависимости от типа устройства
            if device_type == 'cisco':
                commands.append(f"switchport access vlan {interface_data['vlan']}")
            else:
                commands.append(f"port default vlan {interface_data['vlan']}")
            
            commands.append("no shutdown" if interface_data['status'] == 'up' else "shutdown")
            
            print(f"Отправка команд: {commands}")
            output = connection.send_config_set(commands)
            print(f"Результат выполнения команд:\n{output}")
            
            # Проверяем успешность выполнения
            if 'Invalid input' in output or 'Error' in output:
                raise Exception(f"Ошибка выполнения команд: {output}")
            
            return True
            
        except Exception as inner_error:
            print(f"Ошибка при обновлении интерфейса: {str(inner_error)}")
            return False
        finally:
            connection.disconnect()
            
    except Exception as e:
        print(f"Ошибка подключения для обновления интерфейса: {str(e)}")
        return False


def get_device_type(device_type):
    """Фиктивная функция для тестов"""
    return "cisco_ios"