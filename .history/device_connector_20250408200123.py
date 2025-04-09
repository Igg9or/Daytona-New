import random
import time
from datetime import datetime

# Тестовые учетные данные (для имитации успешной аутентификации)
TEST_CREDENTIALS = {
    "admin": "cisco123",
    "user": "password123",
    "test": "test123"
}

if device_type == 'huawei':
            return generate_huawei_response(device_data)
        else:  # По умолчанию Cisco
            return generate_cisco_response(device_data)

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
    """
    Функция для реального обновления интерфейса на устройстве
    Пока только заглушка для тестирования
    """
    print(f"Обновление интерфейса {interface_data['interface_name']} на устройстве {device_data['ip_address']}")
    print(f"Параметры: {interface_data}")
    
    # Здесь должен быть реальный код для:
    # 1. Подключения к устройству (SSH/Telnet/API)
    # 2. Отправки команд конфигурации
    # 3. Проверки изменений
    
    # Пример для Cisco (тестовый):
    # commands = [
    #     f"interface {interface_data['interface_name']}",
    #     f"description {interface_data['description']}",
    #     f"switchport access vlan {interface_data['vlan']}",
    #     "no shutdown" if interface_data['status'] == 'up' else "shutdown"
    # ]
    
    return True


def get_device_type(device_type):
    """Фиктивная функция для тестов"""
    return "cisco_ios"