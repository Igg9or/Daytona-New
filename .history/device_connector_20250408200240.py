import random
import time
from datetime import datetime

# Тестовые учетные данные (для имитации успешной аутентификации)
TEST_CREDENTIALS = {
    "admin": "cisco123",
    "user": "password123",
    "test": "test123"
}

def connect_and_collect_data(device_data):
    """Улучшенная функция с поддержкой Huawei"""
    try:
        device_type = device_data.get('device_type', 'Cisco').lower()
        ip = device_data.get('ip_address', '192.168.1.1')
        
        # Имитация задержки подключения
        time.sleep(random.uniform(0.3, 1.5))
        
        # Проверка учетных данных
        username = device_data.get('username', '')
        password = device_data.get('password', '')
        
        # Всегда разрешаем аутентификацию для тестовых IP
        whitelist_ips = ['127.0.0.1', '192.168.1.1', '10.0.0.1']
        
        if ip not in whitelist_ips and TEST_CREDENTIALS.get(username) != password:
            return {
                'status': 'error',
                'message': 'Ошибка аутентификации: неверный логин/пароль'
            }
            
        # Генерация ответа в зависимости от типа устройства
        if device_type == 'huawei':
            return generate_huawei_response(device_data)
        else:  # Cisco и другие по умолчанию
            return generate_cisco_response(device_data)
            
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Ошибка подключения: {str(e)}'
        }

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
    """Обновленная функция для работы с Huawei"""
    device_type = device_data.get('device_type', 'Cisco').lower()
    print(f"Обновление интерфейса {interface_data['interface_name']} на {device_type.upper()} устройстве {device_data['ip_address']}")
    
    # Здесь будет разная логика для разных производителей
    if device_type == 'huawei':
        print("Имитация команд Huawei:")
        print(f"interface {interface_data['interface_name']}")
        print(f"description {interface_data['description']}")
        print(f"port default vlan {interface_data['vlan']}")
        print("undo shutdown" if interface_data['status'] == 'up' else "shutdown")
    else:  # Cisco и другие
        print("Имитация команд Cisco:")
        print(f"interface {interface_data['interface_name']}")
        print(f"description {interface_data['description']}")
        print(f"switchport access vlan {interface_data['vlan']}")
        print("no shutdown" if interface_data['status'] == 'up' else "shutdown")
    
    return True


def get_device_type(device_type):
    """Фиктивная функция для тестов"""
    return "cisco_ios"