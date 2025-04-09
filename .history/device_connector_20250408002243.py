import json
from netmiko import ConnectHandler

def connect_to_device(device_data):
    """Подключение к сетевому устройству"""
    try:
        if device_data['device_type'] == 'Cisco':
            device_type = 'cisco_ios'
        elif device_data['device_type'] == 'Huawei':
            device_type = 'huawei'
        elif device_data['device_type'] == 'Eltex':
            device_type = 'eltex'
        else:
            return "Неизвестный тип устройства"
        
        connection = ConnectHandler(
            device_type=device_type,
            host=device_data['ip_address'],
            username=device_data['username'],
            password=device_data['password'],
        )
        
        # Пример выполнения команды
        output = connection.send_command('show version')
        connection.disconnect()
        return output
    except Exception as e:
        return f"Ошибка подключения: {str(e)}"

if __name__ == '__main__':
    # Пример использования
    test_device = {
        'username': 'admin',
        'password': 'password',
        'ip_address': '192.168.1.1',
        'device_type': 'Cisco'
    }
    print(connect_to_device(test_device))