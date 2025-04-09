import random
import time
from datetime import datetime
from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
import re
# Тестовые учетные данные (для имитации успешной аутентификации)
TEST_CREDENTIALS = {
    "admin": "cisco123",
    "user": "password123",
    "test": "test123"
}

def connect_and_collect_data(device_data):
    """Реальное подключение к Cisco устройству через SSH"""
    try:
        device_type = device_data.get('device_type', 'Cisco').lower()
        
        # Определяем тип устройства для Netmiko
        netmiko_device_type = 'cisco_ios'
        
        # Параметры подключения
        device_params = {
            'device_type': netmiko_device_type,
            'host': device_data['ip_address'],
            'username': device_data['username'],
            'password': device_data['password'],
            'secret': device_data.get('secret', ''),  # Enable password, если нужен
            'timeout': 10,  # Таймаут подключения
        }
        
        # Подключаемся к устройству
        with ConnectHandler(**device_params) as connection:
            # Переходим в режим enable если нужно
            if device_data.get('secret'):
                connection.enable()
            
            # Собираем данные
            return {
                'status': 'success',
                'data': collect_real_device_data(connection, device_data)
            }
            
    except NetmikoAuthenticationException:
        return {
            'status': 'error',
            'message': 'Ошибка аутентификации: неверный логин/пароль'
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
    
def collect_real_device_data(connection, device_data):
    """Сбор реальных данных с устройства"""
    # Получаем hostname
    hostname = connection.find_prompt().replace('#', '').replace('>', '')
    
    # Получаем uptime
    uptime_output = connection.send_command('show version | include uptime')
    uptime = parse_uptime(uptime_output)
    
    # Получаем версию ПО
    version_output = connection.send_command('show version | include Software')
    software_version = version_output.split(',')[0].strip() if version_output else "N/A"
    
    # Получаем CPU
    cpu_output = connection.send_command('show processes cpu | include CPU')
    cpu_load = parse_cpu(cpu_output)
    
    # Получаем память
    memory_output = connection.send_command('show memory statistics')
    memory_usage = parse_memory(memory_output)
    
    # Получаем интерфейсы
    interfaces_output = connection.send_command('show ip interface brief')
    interfaces = parse_interfaces(interfaces_output)
    
    return {
        'monitoring': {
            'cpu_load': cpu_load,
            'memory_usage': memory_usage,
            'temperature': get_temperature(connection)  # Если поддерживается устройством
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
    """Функция обновления интерфейса"""
    device_type = device_data.get('device_type', 'Cisco').lower()
    print(f"\nКоманды для {device_type.upper()}:")
    
    if device_type == 'huawei':
        print(f"interface {interface_data['interface_name']}")
        print(f"description {interface_data['description']}")
        print(f"port default vlan {interface_data['vlan']}")
        print("undo shutdown" if interface_data['status'] == 'up' else "shutdown")
    else:  # Cisco
        print(f"interface {interface_data['interface_name']}")
        print(f"description {interface_data['description']}")
        print(f"switchport access vlan {interface_data['vlan']}")
        print("no shutdown" if interface_data['status'] == 'up' else "shutdown")
    
    return True


def get_device_type(device_type):
    """Фиктивная функция для тестов"""
    return "cisco_ios"