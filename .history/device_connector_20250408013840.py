import random
from datetime import datetime
import time

def connect_and_collect_data(device_data):
    """Тестовая функция, имитирующая подключение к устройству"""
    # Имитация задержки подключения
    time.sleep(random.uniform(0.5, 2))
    
    # 20% вероятность "ошибки подключения"
    if random.random() < 0.2:
        return {
            'status': 'error',
            'message': 'Ошибка: Устройство недоступно (таймаут)'
        }
    
    # Генерация тестовых данных
    hostname = f"TEST-{random.randint(100, 999)}"
    ip_parts = device_data['ip_address'].split('.')
    
    return {
        'status': 'success',
        'data': {
            'monitoring': {
                'cpu_load': f"{random.randint(1, 95)}%",
                'memory_usage': f"{random.randint(200, 800)}/{random.randint(800, 1000)} MB ({random.randint(20, 90)}%)",
                'temperature': f"{random.randint(30, 75)}°C"
            },
            'configuration': {
                'hostname': hostname,
                'gateway': f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.1",
                'software_version': f"15.{random.randint(1, 4)}({random.choice(['A', 'B', 'C'])})",
                'uptime': f"{random.randint(1, 30)} дней, {random.randint(1, 23)} часов"
            },
            'interfaces': [
                {
                    'name': 'GigabitEthernet0/0',
                    'ip': device_data['ip_address'],
                    'status': 'up',
                    'protocol': 'up'
                },
                {
                    'name': 'GigabitEthernet0/1',
                    'ip': 'unassigned',
                    'status': random.choice(['up', 'down']),
                    'protocol': random.choice(['up', 'down'])
                }
            ],
            'connection_time': f"{random.uniform(0.5, 3.2):.2f} сек"
        }
    }

# Остальные функции можно оставить пустыми или удалить
def get_device_type(device_type):
    return "cisco_ios"  # Всегда возвращаем тестовый тип