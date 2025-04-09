from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException

def connect_to_device(device_data):
    try:
        # Определяем тип устройства
        if device_data['device_type'] == 'Cisco':
            device_type = 'cisco_ios'
        elif device_data['device_type'] == 'Huawei':
            device_type = 'huawei'
        elif device_data['device_type'] == 'Eltex':
            device_type = 'eltex'
        else:
            return "Ошибка: Неизвестный тип устройства"

        # Параметры подключения
        connection_params = {
            'device_type': device_type,
            'host': device_data['ip_address'],
            'username': device_data['username'],
            'password': device_data['password'],
            'timeout': 10  # Таймаут 10 секунд
        }

        # Подключаемся
        with ConnectHandler(**connection_params) as conn:
            output = conn.send_command('show version')
            return output

    except NetmikoTimeoutException:
        return ("Ошибка: Не удалось подключиться (таймаут)\n"
                "Проверьте:\n"
                "1. Правильность IP-адреса\n"
                "2. Доступность устройства\n"
                "3. Настройки сети и фаервола")
    
    except NetmikoAuthenticationException:
        return ("Ошибка аутентификации:\n"
                "1. Неверный логин/пароль\n"
                "2. Недостаточно прав")
    
    except Exception as e:
        return f"Неизвестная ошибка: {str(e)}"