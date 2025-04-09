from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
import re
from datetime import datetime

def connect_and_collect_data(device_data):
    """
    Подключается к устройству и собирает все необходимые данные за одно соединение
    Возвращает:
    {
        'status': 'success'|'error',
        'message': 'Сообщение об ошибке',
        'data': {
            'monitoring': {...},
            'configuration': {...},
            'interfaces': [...]
        }
    }
    """
    try:
        start_time = datetime.now()
        
        # Определяем тип устройства
        device_type = get_device_type(device_data['device_type'])
        if not device_type:
            return {
                'status': 'error',
                'message': 'Неподдерживаемый тип устройства'
            }

        # Подключаемся к устройству
        with ConnectHandler(
            device_type=device_type,
            host=device_data['ip_address'],
            username=device_data['username'],
            password=device_data['password'],
            timeout=10,
            banner_timeout=20
        ) as conn:
            
            # Собираем все данные
            monitoring_data = get_monitoring_data(conn)
            config_data = get_configuration_data(conn)
            interfaces = get_interface_data(conn)
            
            connection_duration = (datetime.now() - start_time).total_seconds()
            
            return {
                'status': 'success',
                'data': {
                    'monitoring': monitoring_data,
                    'configuration': config_data,
                    'interfaces': interfaces,
                    'connection_time': f"{connection_duration:.2f} сек"
                }
            }

    except NetmikoTimeoutException:
        return {
            'status': 'error',
            'message': 'Ошибка: Устройство недоступно (таймаут)'
        }
    except NetmikoAuthenticationException:
        return {
            'status': 'error',
            'message': 'Ошибка: Неверные учетные данные'
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Ошибка подключения: {str(e)}'
        }

def get_device_type(device_type):
    """Определяем тип устройства для Netmiko"""
    types = {
        'Cisco': 'cisco_ios',
        'Huawei': 'huawei',
        'Eltex': 'eltex'
    }
    return types.get(device_type)

def get_monitoring_data(conn):
    """Собираем данные мониторинга"""
    cpu_output = conn.send_command('show processes cpu')
    mem_output = conn.send_command('show memory')
    temp_output = conn.send_command('show environment')
    
    return {
        'cpu_load': parse_cpu(cpu_output),
        'memory_usage': parse_memory(mem_output),
        'temperature': parse_temp(temp_output)
    }

def get_configuration_data(conn):
    """Собираем конфигурационные данные"""
    hostname = parse_hostname(conn.send_command('show running-config | include hostname'))
    gateway = parse_gateway(conn.send_command('show running-config | include ip route'))
    version = parse_version(conn.send_command('show version'))
    
    return {
        'hostname': hostname,
        'gateway': gateway,
        'software_version': version,
        'uptime': parse_uptime(conn.send_command('show uptime'))
    }

def get_interface_data(conn):
    """Получаем статус интерфейсов"""
    brief_output = conn.send_command('show ip interface brief')
    return parse_interfaces(brief_output)

# --- Парсеры для Cisco ---
def parse_cpu(output):
    """Парсим загрузку CPU"""
    match = re.search(r'CPU utilization for five seconds: (\d+)%', output)
    return f"{match.group(1)}%" if match else "N/A"

def parse_memory(output):
    """Парсим использование памяти"""
    match = re.search(r'Total:\s*(\d+)\s*Used:\s*(\d+)', output)
    if match:
        used = int(match.group(2))
        total = int(match.group(1))
        percent = (used / total) * 100
        return f"{used}/{total} MB ({percent:.1f}%)"
    return "N/A"

def parse_temp(output):
    """Парсим температуру"""
    match = re.search(r'System Temperature\s*:\s*(\d+) C', output)
    return f"{match.group(1)}°C" if match else "N/A"

def parse_hostname(output):
    """Парсим hostname"""
    return output.replace('hostname', '').strip()

def parse_gateway(output):
    """Парсим шлюз по умолчанию"""
    match = re.search(r'ip route 0\.0\.0\.0 0\.0\.0\.0 (\S+)', output)
    return match.group(1) if match else "N/A"

def parse_version(output):
    """Парсим версию ПО"""
    match = re.search(r'Version (\S+)', output)
    return match.group(1) if match else "N/A"

def parse_uptime(output):
    """Парсим время работы"""
    match = re.search(r'uptime is (.+)', output)
    return match.group(1) if match else "N/A"

def parse_interfaces(output):
    """Парсим список интерфейсов"""
    interfaces = []
    for line in output.split('\n'):
        if any(x in line for x in ['up', 'down']) and not line.startswith('Interface'):
            parts = line.split()
            if len(parts) >= 4:
                interfaces.append({
                    'name': parts[0],
                    'ip': parts[1] if parts[1] != 'unassigned' else '-',
                    'status': parts[-2],
                    'protocol': parts[-1]
                })
    return interfaces