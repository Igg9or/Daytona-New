from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
import random
import re
from datetime import datetime

# Режим работы (True - реальное подключение, False - тестовый режим)
REAL_MODE = True  # Можно вынести в конфиг или переменные окружения

# Тестовые учетные данные (оставляем для тестового режима)
TEST_CREDENTIALS = {
    "admin": "cisco123",
    "user": "password123",
    "test": "test123"
}

def connect_and_collect_data(device_data):
    """Основная функция подключения с поддержкой двух режимов"""
    if not REAL_MODE:
        return test_connect_and_collect_data(device_data)
    else:
        return real_connect_and_collect_data(device_data)

def test_connect_and_collect_data(device_data):
    """Тестовая функция подключения (оставляем как было)"""
    try:
        device_type = device_data.get('device_type', 'Cisco').lower()
        
        if TEST_CREDENTIALS.get(device_data['username']) != device_data['password']:
            return {
                'status': 'error',
                'message': 'Ошибка аутентификации: неверный логин/пароль'
            }
        
        if device_type == 'huawei':
            return generate_huawei_response(device_data)
        else:
            return generate_cisco_response(device_data)
            
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Ошибка подключения: {str(e)}'
        }

def real_connect_and_collect_data(device_data):
    """Реальное подключение к устройству через SSH"""
    try:
        device_type = device_data.get('device_type', 'Cisco').lower()
        netmiko_device_type = 'cisco_ios' if device_type == 'cisco' else 'huawei'
        
        device_params = {
            'device_type': netmiko_device_type,
            'host': device_data['ip_address'],
            'username': device_data['username'],
            'password': device_data['password'],
            'secret': device_data.get('secret', ''),
            'timeout': 10,
        }
        
        with ConnectHandler(**device_params) as connection:
            if device_data.get('secret'):
                connection.enable()
            
            return {
                'status': 'success',
                'data': collect_real_device_data(connection, device_data)
            }
            
    except NetmikoAuthenticationException:
        # В случае ошибки аутентификации можно попробовать тестовый режим
        if device_data.get('fallback_to_test'):
            return test_connect_and_collect_data(device_data)
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

# Оставляем все существующие тестовые функции (generate_cisco_response, generate_huawei_response и т.д.)

def update_interface_on_device(device_data, interface_data):
    """Функция обновления интерфейса с поддержкой двух режимов"""
    if not REAL_MODE:
        print("\nТестовый режим - команды не отправляются на устройство")
        print(f"Имитация обновления интерфейса {interface_data['interface_name']}")
        return True
    
    try:
        device_type = device_data.get('device_type', 'Cisco').lower()
        netmiko_device_type = 'cisco_ios' if device_type == 'cisco' else 'huawei'
        
        device_params = {
            'device_type': netmiko_device_type,
            'host': device_data['ip_address'],
            'username': device_data['username'],
            'password': device_data['password'],
            'secret': device_data.get('secret', ''),
            'timeout': 10,
        }
        
        with ConnectHandler(**device_params) as connection:
            if device_data.get('secret'):
                connection.enable()
            
            commands = [
                f"interface {interface_data['interface_name']}",
                f"description {interface_data['description']}",
                f"switchport access vlan {interface_data['vlan']}" if device_type == 'cisco' else f"port default vlan {interface_data['vlan']}",
                "no shutdown" if interface_data['status'] == 'up' else "shutdown"
            ]
            
            output = connection.send_config_set(commands)
            print(f"Результат выполнения команд:\n{output}")
            
            return True
            
    except Exception as e:
        print(f"Ошибка при обновлении интерфейса: {str(e)}")
        return False