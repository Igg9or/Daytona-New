from netmiko import ConnectHandler
from netmiko.ssh_exception import NetMikoTimeoutException, NetMikoAuthenticationException
import random

def connect_to_device(device_data):
    # Для демонстрации - случайным образом возвращаем ошибку или успех
    if random.choice([True, False]):
        try:
            # Здесь реальный код подключения
            if device_data['device_type'] == 'Cisco':
                device_type = 'cisco_ios'
            else:
                device_type = 'generic'
            
            connection = ConnectHandler(
                device_type=device_type,
                host=device_data['ip_address'],
                username=device_data['username'],
                password=device_data['password'],
                timeout=5
            )
            
            output = connection.send_command('show version')
            connection.disconnect()
            return output
            
        except NetMikoTimeoutException:
            return "Ошибка: Устройство недоступно\nПроверьте:\n- Правильность IP-адреса\n- Доступность устройства\n- Настройки фаервола"
        except NetMikoAuthenticationException:
            return "Ошибка аутентификации:\n- Неверный логин/пароль\n- Недостаточно прав"
        except Exception as e:
            return f"Критическая ошибка: {str(e)}"
    else:
        return "show version\nCisco IOS Software, 3700 Software (C3725-ADVENTERPRISEK9-M), Version 12.4(25d)"