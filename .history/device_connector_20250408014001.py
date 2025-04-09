import random
import time
from datetime import datetime

def connect_and_collect_data(device_data):
    """Безопасная тестовая функция с обработкой всех крайних случаев"""
    try:
        # Имитация задержки подключения
        time.sleep(random.uniform(0.5, 2.0))
        
        # Вероятность ошибки (можно регулировать)
        if random.random() < 0.3:  # 30% вероятность ошибки
            error_types = [
                "Ошибка: Устройство недоступно (таймаут)",
                "Ошибка аутентификации",
                "Ошибка: Неверный тип устройства"
            ]
            return {
                'status': 'error',
                'message': random.choice(error_types)
            }
        
        # Генерация безопасных тестовых данных
        ip_parts = device_data.get('ip_address', '192.168.1.1').split('.')
        gateway = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.1" if len(ip_parts) >= 3 else "192.168.1.1"
        
        # Всегда возвращаем корректную структуру данных
        return {
            'status': 'success',
            'data': {
                'monitoring': {
                    'cpu_load': f"{random.randint(1, 95)}%",
                    'memory_usage': f"{random.randint(200, 800)}/{random.randint(800, 1000)} MB ({random.randint(20, 90)}%)",
                    'temperature': f"{random.randint(30, 75)}°C"
                },
                'configuration': {
                    'hostname': f"TEST-{random.randint(100, 999)}",
                    'gateway': gateway,
                    'software_version': f"15.{random.randint(1, 4)}({random.choice(['A', 'B', 'C'])})",
                    'uptime': f"{random.randint(1, 30)} дней, {random.randint(1, 23)} часов"
                },
                'interfaces': [
                    {
                        'name': 'GigabitEthernet0/0',
                        'ip': device_data.get('ip_address', '192.168.1.1'),
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
    
    except Exception as e:
        return {
            'status': 'error',
            'message': f"Тестовая ошибка: {str(e)}"
        }

def get_device_type(device_type):
    """Всегда возвращает тестовый тип"""
    return "cisco_ios"