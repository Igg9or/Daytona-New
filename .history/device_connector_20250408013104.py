from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
import re

def connect_and_collect_data(device_data):
    try:
        # Подключение (сохраняем предыдущую логику)
        with ConnectHandler(
            device_type=get_device_type(device_data['device_type']),
            host=device_data['ip_address'],
            username=device_data['username'],
            password=device_data['password'],
            timeout=10
        ) as conn:
            
            # Собираем ВСЕ данные за одно подключение
            data = {
                'monitoring': get_monitoring_data(conn),
                'configuration': get_configuration_data(conn),
                'interfaces': get_interface_data(conn)
            }
            
            return {'status': 'success', 'data': data}
    
    except NetmikoTimeoutException as e:
        return {'status': 'error', 'message': f'Ошибка подключения: {str(e)}'}
    except Exception as e:
        return {'status': 'error', 'message': f'Неизвестная ошибка: {str(e)}'}

# --- Вспомогательные функции (сохраняем предыдущие парсеры) ---
def get_device_type(device_type):
    types = {'Cisco': 'cisco_ios', 'Huawei': 'huawei', 'Eltex': 'eltex'}
    return types.get(device_type, 'cisco_ios')

def get_monitoring_data(conn):
    cpu_output = conn.send_command('show processes cpu')
    mem_output = conn.send_command('show memory')
    temp_output = conn.send_command('show environment')
    
    return {
        'cpu_load': parse_cpu(cpu_output),
        'memory_usage': parse_memory(mem_output),
        'temperature': parse_temp(temp_output)
    }

def get_configuration_data(conn):
    hostname = conn.send_command('show running-config | include hostname')
    gateway = conn.send_command('show running-config | include ip route')
    version = conn.send_command('show version')
    
    return {
        'hostname': parse_hostname(hostname),
        'gateway': parse_gateway(gateway),
        'software_version': parse_version(version)
    }

def get_interface_data(conn):
    output = conn.send_command('show ip interface brief')
    return parse_interfaces(output)

# ... (все предыдущие функции parse_*) остаются без изменений ...