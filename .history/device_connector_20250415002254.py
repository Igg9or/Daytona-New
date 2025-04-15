import random
import time
from datetime import datetime
from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
import re
from datetime import datetime
import logging


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('device_connector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Тестовые учетные данные (для имитации успешной аутентификации)
TEST_CREDENTIALS = {
    "admin": "cisco123",
    "user": "password123",
    "test": "test123"
}

# В функции connect_and_collect_data изменим определение netmiko_device_type:
def connect_and_collect_data(device_data):
    """Реальное подключение к устройству через SSH с улучшенной обработкой ошибок"""
    connection = None
    try:
        device_type = device_data.get('device_type', 'Cisco').lower()
        # Добавляем поддержку Eltex
        netmiko_device_type = {
            'cisco': 'cisco_ios',
            'huawei': 'huawei',
            'eltex': 'eltex'  # Netmiko поддерживает Eltex
        }.get(device_type, 'cisco_ios')
        
        device_params = {
            'device_type': netmiko_device_type,
            'host': device_data['ip_address'],
            'username': device_data['username'],
            'password': device_data['password'],
            'secret': device_data.get('secret', ''),
            'timeout': 15,
            'session_timeout': 30,
            'banner_timeout': 15,
        }
        
        print(f"Попытка подключения к {device_data['ip_address']}...")
        connection = ConnectHandler(**device_params)
        
        if device_data.get('secret'):
            try:
                connection.enable()
            except Exception as e:
                return {
                    'status': 'error',
                    'message': f'Ошибка enable режима: {str(e)}'
                }
        
        print("Собираем данные с устройства...")
        collected_data = collect_real_device_data(connection, device_data)
        
        return {
            'status': 'success',
            'data': collected_data
        }
            
    except NetmikoAuthenticationException as auth_error:
        error_msg = 'Ошибка аутентификации: неверный логин/пароль'
        if 'enable' in str(auth_error):
            error_msg += ' (или неверный enable пароль)'
        return {
            'status': 'error',
            'message': error_msg
        }
    except NetmikoTimeoutException as timeout_error:
        return {
            'status': 'error',
            'message': 'Таймаут подключения: устройство недоступно'
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Ошибка подключения: {str(e)}'
        }
    finally:
        if connection:
            try:
                connection.disconnect()
            except:
                pass
    
def parse_uptime(uptime_str):
    """Парсим время работы устройства"""
    # Пример: "router uptime is 1 week, 2 days, 3 hours, 4 minutes"
    return uptime_str.split('is')[-1].strip() if uptime_str else "N/A"

def parse_cpu(cpu_str):
    """Парсим загрузку CPU"""
    # Пример: "CPU utilization for five seconds: 10%/0%"
    match = re.search(r'(\d+)%', cpu_str)
    return f"{match.group(1)}%" if match else "0%"

def parse_memory(memory_str):
    """Парсим использование памяти"""
    try:
        # Пример для Cisco: "Processor memory: 1000000K total, 300000K used, 700000K free"
        total_match = re.search(r'total\s*:\s*(\d+)', memory_str)
        used_match = re.search(r'used\s*:\s*(\d+)', memory_str)
        
        if total_match and used_match:
            total = int(total_match.group(1))
            used = int(used_match.group(1))
            percent = (used / total) * 100
            return f"{used}K/{total}K ({int(percent)}%)"
        
        return "N/A"
    except Exception:
        return "N/A"
    
def get_temperature(connection, device_type):
    """Получение температуры устройства с обработкой ошибок"""
    try:
        if device_type and device_type.lower() == 'cisco':
            temp_output = send_command_safe(connection, 'show environment temperature')
            if 'invalid' in temp_output.lower():
                return "N/A"
            
            match = re.search(r'Temperature:\s*(\d+)\s*C', temp_output, re.IGNORECASE)
            return f"{match.group(1)}°C" if match else "N/A"
        
        elif device_type and device_type.lower() == 'huawei':
            temp_output = send_command_safe(connection, 'display temperature all')
            match = re.search(r'Temperature\s*:\s*(\d+)', temp_output)
            return f"{match.group(1)}°C" if match else "N/A"
        
        return "N/A"
    except Exception:
        return "N/A"
    
def send_command_safe(connection, command, delay=1):
    """Безопасная отправка команд с задержкой"""
    time.sleep(delay)
    return connection.send_command(command, delay_factor=2)

def get_gateway(connection):
    """Получение шлюза по умолчанию"""
    try:
        route_output = connection.send_command('show ip route')
        match = re.search(r'via\s+([\d.]+)', route_output)
        return match.group(1) if match else "N/A"
    except Exception:
        return "N/A"   
    
def collect_real_device_data(connection, device_data):
    """Сбор реальных данных с устройства"""
    start_time = datetime.now()
    
    device_type = device_data.get('device_type', 'Cisco').lower()
    
    # Для Eltex устройств
    if device_type == 'eltex':
        try:
            hostname = connection.find_prompt().replace('#', '').strip()
            
            # Получаем информацию о системе
            system_output = connection.send_command('show system', delay_factor=2)
            system_data = parse_eltex_system(system_output)
            
            # Получаем информацию о CPU и памяти
            cpu_output = connection.send_command('show cpu utilization', delay_factor=2)
            cpu_memory_data = parse_eltex_cpu_memory(cpu_output)
            
            # Получаем температуру
            temp_output = connection.send_command('show system sensors', delay_factor=2)
            temp_data = parse_eltex_temperature(temp_output)
            
            # Получаем версию ПО
            version_output = connection.send_command('show version', delay_factor=2)
            version_data = parse_eltex_version(version_output)
            
            # Получаем информацию об интерфейсах
            interfaces_output = connection.send_command('show interfaces status', delay_factor=2)
            interfaces = parse_eltex_interfaces(interfaces_output)
            
            exec_time = (datetime.now() - start_time).total_seconds()
            
            return {
                'monitoring': {
                    'cpu_load': cpu_memory_data.get('cpu_load', 'N/A'),
                    'memory_usage': cpu_memory_data.get('memory_usage', 'N/A'),
                    'temperature': temp_data.get('temperature', 'N/A')
                },
                'configuration': {
                    'hostname': system_data.get('hostname', hostname),
                    'gateway': get_eltex_gateway(connection),
                    'software_version': version_data.get('version', 'N/A'),
                    'uptime': system_data.get('uptime', 'N/A')
                },
                'interfaces': [],  # Пока не парсим интерфейсы для Eltex
                'connection_time': f"{exec_time:.2f} сек"
            }
        except Exception as e:
            logger.error(f"Ошибка при сборе данных с Eltex устройства: {str(e)}")
            raise
    
    # Для Cisco и Huawei (оригинальный функционал)
    hostname = connection.find_prompt().replace('#', '').replace('>', '')
    
    uptime_output = connection.send_command('show version | include uptime') if device_type == 'cisco' else connection.send_command('display version | include uptime')
    uptime = parse_uptime(uptime_output)
    
    version_output = connection.send_command('show version | include Software') if device_type == 'cisco' else connection.send_command('display version | include Software')
    software_version = version_output.split(',')[0].strip() if version_output else "N/A"
    
    cpu_output = connection.send_command('show processes cpu | include CPU') if device_type == 'cisco' else connection.send_command('display cpu-usage')
    cpu_load = parse_cpu(cpu_output)
    
    memory_output = connection.send_command('show memory statistics') if device_type == 'cisco' else connection.send_command('display memory-usage')
    memory_usage = parse_memory(memory_output)
    
    interfaces_output = connection.send_command('show ip interface brief') if device_type == 'cisco' else connection.send_command('display ip interface brief')
    interfaces = parse_interfaces(connection, interfaces_output)
    
    for intf in interfaces:
        try:
            # Получаем детальную информацию об интерфейсе
            details = connection.send_command(f'show interface {intf["name"]}' if device_type == 'cisco' else f'display interface {intf["name"]}', delay_factor=2)
            
            # Парсим дополнительные параметры
            intf.update({
                'type': re.search(r'Hardware is (.+?),', details).group(1) if 'Hardware is' in details else 'N/A',
                'mtu': re.search(r'MTU (\d+)', details).group(1) if 'MTU' in details else '1500',
                'mac_address': re.search(r'address is (.+?) ', details).group(1) if 'address is' in details else 
                              (re.search(r'HWaddr (.+)', details).group(1) if 'HWaddr' in details else 'N/A'),
                'last_input': re.search(r'Last input (.+?),', details).group(1) if 'Last input' in details else 'N/A',
                'last_output': re.search(r'Last output (.+?),', details).group(1) if 'Last output' in details else 'N/A',
                'input_rate': re.search(r'input rate (\d+)', details).group(1) + ' bps' if 'input rate' in details else 'N/A',
                'output_rate': re.search(r'output rate (\d+)', details).group(1) + ' bps' if 'output rate' in details else 'N/A',
                'input_errors': re.search(r'input errors (\d+)', details).group(1) if 'input errors' in details else '0',
                'output_errors': re.search(r'output errors (\d+)', details).group(1) if 'output errors' in details else '0'
            })
            
            # Для Huawei устройств парсим по-другому
            if device_type == 'huawei':
                huawei_details = connection.send_command(f'display interface {intf["name"]}', delay_factor=2)
                if 'Last 300 seconds input rate' in huawei_details:
                    intf.update({
                        'input_rate': re.search(r'Last 300 seconds input rate: (.+?) ', huawei_details).group(1),
                        'output_rate': re.search(r'Last 300 seconds output rate: (.+?) ', huawei_details).group(1)
                    })
                    
        except Exception as e:
            print(f"Ошибка при получении деталей интерфейса {intf['name']}: {str(e)}")
            continue

    # Рассчитываем время выполнения
    exec_time = (datetime.now() - start_time).total_seconds()
    
    return {
        'monitoring': {
            'cpu_load': cpu_load,
            'memory_usage': memory_usage,
            'temperature': get_temperature(connection, device_data.get('device_type'))
        },
        'configuration': {
            'hostname': hostname,
            'gateway': get_gateway(connection),
            'software_version': software_version,
            'uptime': uptime
        },
        'interfaces': interfaces,
        'connection_time': f"{exec_time:.2f} сек"
    }

def get_eltex_gateway(connection):
    """Получение шлюза по умолчанию для Eltex"""
    try:
        route_output = connection.send_command('show ip route', delay_factor=2)
        for line in route_output.splitlines():
            if '0.0.0.0/0' in line:
                parts = line.split()
                if len(parts) > 2:
                    return parts[2]  # Адрес шлюза
        return "N/A"
    except Exception:
        return "N/A"

def parse_eltex_system(output):
    """Парсим вывод команды show system для Eltex"""
    data = {}
    try:
        for line in output.splitlines():
            if 'System Name:' in line:
                parts = line.split(':')
                if len(parts) > 1:
                    data['hostname'] = parts[-1].strip()
            elif 'System Up Time' in line:
                parts = line.split(':')
                if len(parts) > 1:
                    uptime = parts[-1].strip()
                    data['uptime'] = uptime.split(')')[0] if ')' in uptime else uptime
    except Exception as e:
        logger.error(f"Ошибка парсинга system info: {str(e)}")
    return data

def parse_eltex_cpu_memory(output):
    """Парсим вывод команды show cpu utilization для Eltex"""
    data = {'cpu_load': 'N/A', 'memory_usage': 'N/A'}
    
    try:
        # Парсим память
        memory_section = re.search(r'Memory usage\s+-+\s+Total/Free:\s+(\d+)\s+B/(\d+)\s+B\s+\((\d+)%\)', output)
        if memory_section:
            total = memory_section.group(1) + ' B'
            free = memory_section.group(2) + ' B'
            percent = memory_section.group(3) + '%'
            data['memory_usage'] = f"{free}/{total} ({percent})"
        
        # Парсим CPU - более надежный способ
        cpu_section = re.search(
            r'CPU utilization\s+-+\s+five seconds:\s+(\d+)%;\s+one minute:\s+(\d+)%;\s+five minutes:\s+(\d+)%', 
            output
        )
        
        if cpu_section:
            # Берем значение за 5 секунд (первая группа)
            cpu_load = cpu_section.group(1)
            data['cpu_load'] = f"{cpu_load}%"
        else:
            # Альтернативный вариант парсинга, если регулярка не сработала
            for line in output.splitlines():
                if 'five seconds:' in line:
                    parts = line.split(':')
                    if len(parts) > 1:
                        cpu_load = parts[1].split('%')[0].strip()
                        data['cpu_load'] = f"{cpu_load}%"
                        break
    
    except Exception as e:
        logger.error(f"Ошибка парсинга CPU/memory: {str(e)}")
        # Устанавливаем значения по умолчанию в случае ошибки
        data['cpu_load'] = '0%'
        data['memory_usage'] = '0B/0B (0%)'
    
    return data

def parse_eltex_temperature(output):
    """Парсим вывод команды show system sensors для Eltex"""
    data = {'temperature': 'N/A'}
    try:
        for line in output.splitlines():
            if 'Unit/Sensor' in line:
                continue
            parts = line.split()
            if len(parts) > 2 and parts[1].isdigit():
                data['temperature'] = f"{parts[1]}°C"
                break
    except Exception as e:
        logger.error(f"Ошибка парсинга температуры: {str(e)}")
    return data

def parse_eltex_version(output):
    """Парсим вывод команды show version для Eltex"""
    data = {'version': 'N/A'}
    try:
        for line in output.splitlines():
            if 'Version:' in line:
                parts = line.split(':')
                if len(parts) > 1:
                    data['version'] = parts[-1].strip()
                    break
    except Exception as e:
        logger.error(f"Ошибка парсинга версии: {str(e)}")
    return data

def parse_interfaces(connection, interfaces_str):
    """Парсим список интерфейсов с дополнительной информацией"""
    interfaces = []
    for line in interfaces_str.splitlines()[1:]:  # Пропускаем заголовок
        if line.strip():
            parts = line.split()
            if len(parts) >= 6:
                interface_name = parts[0]
                interface = {
                    'name': interface_name,
                    'ip': parts[1] if parts[1] != 'unassigned' else 'N/A',
                    'status': parts[4].lower(),
                    'protocol': parts[5].lower(),
                    'description': '',
                    'vlan': '1',
                    'duplex': 'auto',
                    'speed': 'auto'
                }
                
                try:
                    # Получаем подробную информацию об интерфейсе
                    details = connection.send_command(f'show interface {interface_name}', delay_factor=2)
                    
                    # Парсим описание
                    desc_match = re.search(r'Description:\s*(.+?)\n', details)
                    if desc_match:
                        interface['description'] = desc_match.group(1).strip()
                    
                    # Парсим VLAN (для Cisco)
                    vlan_match = re.search(r'access vlan\s+(\d+)', details)
                    if vlan_match:
                        interface['vlan'] = vlan_match.group(1)
                    
                    # Парсим дуплекс и скорость
                    duplex_match = re.search(r'Duplex:\s*(\w+)', details)
                    if duplex_match:
                        interface['duplex'] = duplex_match.group(1).lower()
                    
                    speed_match = re.search(r'BW\s*(\d+)\s*\w+', details)
                    if speed_match:
                        speed = int(speed_match.group(1))
                        interface['speed'] = f"{speed} Mbps" if speed < 1000 else "1 Gbps"
                    
                except Exception as e:
                    print(f"Ошибка при получении деталей интерфейса {interface_name}: {str(e)}")
                
                interfaces.append(interface)
    return interfaces



def generate_cisco_response(device_data):
    """Генерация тестовых данных для Cisco"""
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
            'interfaces': generate_cisco_interfaces(ip),
            'connection_time': f"{random.uniform(0.8, 2.5):.2f} сек"
        }
    }

def generate_cisco_interfaces(base_ip):
    """Генерация тестовых интерфейсов Cisco"""
    ip_parts = base_ip.split('.')
    return [
        {
            'name': 'GigabitEthernet0/1',
            'description': 'Сервер',
            'status': 'up',
            'vlan': 10,
            'duplex': 'full',
            'speed': '1000'
        },
        {
            'name': 'GigabitEthernet0/2',
            'description': 'Резерв',
            'status': 'down',
            'vlan': 20,
            'duplex': 'auto',
            'speed': '100'
        }
    ]

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
    """Обновление интерфейса на сетевом устройстве с улучшенной обработкой ошибок
    
    Args:
        device_data (dict): Данные для подключения к устройству
        interface_data (dict): Параметры интерфейса для обновления
    
    Returns:
        bool: True если обновление прошло успешно, False в случае ошибки
    """
    connection = None
    try:
        # Определяем тип устройства
        device_type = device_data.get('device_type', 'Cisco').lower()
        netmiko_device_type = 'cisco_ios' if device_type == 'cisco' else 'huawei'
        
        # Параметры подключения
        device_params = {
            'device_type': netmiko_device_type,
            'host': device_data['ip_address'],
            'username': device_data['username'],
            'password': device_data['password'],
            'secret': device_data.get('secret', ''),
            'timeout': 20,  # Увеличенный таймаут
            'session_timeout': 30,
            'banner_timeout': 15,
            'global_delay_factor': 2,  # Увеличенные задержки
        }
        
        print(f"Подключение для обновления интерфейса {interface_data['interface_name']}...")
        
        # Подключаемся к устройству
        connection = ConnectHandler(**device_params)
        
        # Включаем режим enable если требуется
        if device_data.get('secret'):
            try:
                connection.enable()
            except Exception as enable_error:
                print(f"Ошибка входа в enable режим: {str(enable_error)}")
                return False
        
        # Формируем команды в зависимости от типа устройства
        if device_type == 'huawei':
            commands = [
                f"interface {interface_data['interface_name']}",
                f"description {interface_data['description']}",
                f"port default vlan {interface_data['vlan']}",
                "undo shutdown" if interface_data['status'] == 'up' else "shutdown"
            ]
        else:  # Cisco и другие
            commands = [
                f"interface {interface_data['interface_name']}",
                f"description {interface_data['description']}",
                f"switchport access vlan {interface_data['vlan']}",
                "no shutdown" if interface_data['status'] == 'up' else "shutdown"
            ]
        
        print(f"Отправка команд: {commands}")
        
        # Отправляем команды с увеличенными задержками
        try:
            # Входим в режим конфигурации
            connection.config_mode()
            
            # Отправляем команды по одной с проверкой
            for cmd in commands:
                output = connection.send_command(
                    cmd,
                    delay_factor=2,
                    expect_string=r'#|\]|>',  # Ожидаемые промпты
                    strip_prompt=False,
                    strip_command=False
                )
                print(f"Команда: {cmd}\nРезультат: {output[:200]}...")  # Логируем первые 200 символов
            
            # Выходим из режима конфигурации
            connection.exit_config_mode()
            
            # Для Cisco сохраняем конфигурацию
            if device_type == 'cisco':
                save_output = connection.send_command(
                    'write memory',
                    delay_factor=2,
                    expect_string=r'#|\]|>'
                )
                print(f"Сохранение конфигурации: {save_output[:200]}...")
            
            return True
            
        except Exception as cmd_error:
            print(f"Ошибка выполнения команд: {str(cmd_error)}")
            return False
            
    except NetmikoAuthenticationException as auth_error:
        print(f"Ошибка аутентификации: {str(auth_error)}")
        return False
    except NetmikoTimeoutException as timeout_error:
        print(f"Таймаут подключения: {str(timeout_error)}")
        return False
    except Exception as e:
        print(f"Общая ошибка: {str(e)}")
        return False
    finally:
        # Всегда закрываем соединение
        if connection:
            try:
                connection.disconnect()
                print("Соединение закрыто")
            except Exception as disconnect_error:
                print(f"Ошибка при закрытии соединения: {str(disconnect_error)}")


def get_device_type(device_type):
    """Фиктивная функция для тестов"""
    return "cisco_ios"

def get_real_vlan_info(connection, device_type):
    """Получение реальной информации о VLAN с устройства"""
    vlans = []
    
    try:
        if device_type.lower() == 'cisco':
            # Для Cisco устройств
            vlan_output = connection.send_command('show vlan brief')
            svi_output = connection.send_command('show ip interface brief | include Vlan')
            
            # Парсинг вывода (упрощенный пример)
            # Здесь должен быть ваш парсинг реального вывода команд
            
        elif device_type.lower() == 'huawei':
            # Для Huawei устройств
            vlan_output = connection.send_command('display vlan')
            svi_output = connection.send_command('display ip interface brief | include Vlanif')
            
            # Парсинг вывода (упрощенный пример)
            
        # Формирование списка VLAN на основе распарсенных данных
        
    except Exception as e:
        print(f"Ошибка получения VLAN информации: {str(e)}")
    
    return vlans

import logging

# Создаем логгер для этого модуля
logger = logging.getLogger(__name__)

def create_interface_on_device(device_data, interface_data):
    """Создание интерфейса на Cisco устройстве с правильным форматом имен"""
    connection = None
    try:
        device_params = {
            'device_type': 'cisco_ios',
            'host': device_data['ip_address'],
            'username': device_data['username'],
            'password': device_data['password'],
            'secret': device_data.get('secret', ''),
            'timeout': 20,
            'session_timeout': 30,
            'global_delay_factor': 2,
            'session_log': 'netmiko_create_interface.log'
        }
        
        logger.info(f"Подключение для создания интерфейса {interface_data['name']}")
        connection = ConnectHandler(**device_params)
        
        try:
            if device_data.get('secret'):
                connection.enable()
            
            commands = []
            # Форматируем имя интерфейса с пробелом
            interface_name = format_interface_name(interface_data['name'])
            commands.append(f"interface {interface_name}")
            
            # Настройка IP-адреса
            if interface_data.get('ip_address'):
                commands.append(f"ip address {interface_data['ip_address']} {interface_data['netmask']}")
            
            # Описание интерфейса
            if interface_data.get('description'):
                commands.append(f"description {interface_data['description']}")
            
            # MTU
            if interface_data.get('mtu'):
                commands.append(f"mtu {interface_data['mtu']}")
            
            # Полоса пропускания
            if interface_data.get('bandwidth'):
                commands.append(f"bandwidth {interface_data['bandwidth']}")
            
            # Режим дуплекса
            if interface_data.get('duplex'):
                commands.append(f"duplex {interface_data['duplex']}")
            
            # Настройка VLAN для access-портов
            if interface_data.get('vlan'):
                commands.append(f"switchport access vlan {interface_data['vlan']}")
                commands.append("switchport mode access")
            
            # Статус интерфейса
            if interface_data.get('status') == 'up':
                commands.append("no shutdown")
            else:
                commands.append("shutdown")
            
            logger.debug(f"Отправка команд для создания интерфейса: {commands}")
            output = connection.send_config_set(commands)
            logger.debug(f"Результат выполнения команд:\n{output}")
            
            # Проверка ошибок в выводе
            if 'Invalid input' in output or 'Error' in output:
                raise Exception(f"Ошибка выполнения команд: {output}")
            
            # Сохранение конфигурации
            save_output = connection.send_command('write memory')
            logger.debug(f"Результат сохранения конфигурации:\n{save_output}")
            
            return True, output
            
        except Exception as e:
            logger.error(f"Ошибка при создании интерфейса: {str(e)}")
            return False, str(e)
        finally:
            if connection:
                connection.disconnect()
                
    except Exception as e:
        logger.error(f"Ошибка подключения для создания интерфейса: {str(e)}")
        return False, str(e)

def format_interface_name(name):
    """Форматирует имя интерфейса для Cisco IOS (добавляет пробелы)"""
    # Для физических интерфейсов: GigabitEthernet0/1 -> GigabitEthernet 0/1
    if name.startswith(('GigabitEthernet', 'FastEthernet', 'TenGigabitEthernet')):
        return name[:len('GigabitEthernet')] + ' ' + name[len('GigabitEthernet'):]
    # Для SVI интерфейсов: Vlan10 -> Vlan 10
    elif name.startswith('Vlan'):
        return name[:4] + ' ' + name[4:]
    # Для loopback интерфейсов: Loopback0 -> Loopback 0
    elif name.startswith('Loopback'):
        return name[:8] + ' ' + name[8:]
    return name


def get_routing_table(connection, device_type):
    """Получение таблицы маршрутизации с устройства"""
    try:
        if device_type.lower() == 'cisco':
            output = connection.send_command('show ip route', delay_factor=2)
            return parse_cisco_routing_table(output)
        else:
            output = connection.send_command('display ip routing-table', delay_factor=2)
            return parse_huawei_routing_table(output)
    except Exception as e:
        logger.error(f"Ошибка получения таблицы маршрутизации: {str(e)}")
        return []

def parse_cisco_routing_table(output):
    """Парсинг вывода Cisco 'show ip route' для реального оборудования"""
    routes = []
    current_protocol = None
    
    for line in output.splitlines():
        # Определяем протокол маршрутизации
        if line.strip().startswith('Gateway of last resort is'):
            continue
            
        if 'Routing entry for' in line:
            continue
            
        if line.startswith('Codes:'):
            continue
            
        # Обработка маршрутов
        if line.strip() and line[0].isalpha() and 'via' in line:
            parts = line.split()
            route_type = parts[0][0]  # Первый символ - тип маршрута
            
            # Для маршрутов типа "O IA" (OSPF inter-area)
            if len(parts[0]) > 1 and parts[0][1] == '*':
                route_type = parts[0][0]
                
            network = parts[1]
            mask_or_prefix = None
            admin_distance = None
            metric = None
            next_hop = None
            interface = None
            time_info = None
            
            # Обработка разных форматов вывода
            if 'is directly connected' in line:
                # Пример: C        192.168.1.0/24 is directly connected, GigabitEthernet0/1
                interface = line.split(',')[-1].strip()
                next_hop = '0.0.0.0'
                mask_or_prefix = network.split('/')[1] if '/' in network else '24'
                network = network.split('/')[0]
            elif 'via' in line:
                # Пример: D EX     10.1.2.0/24 [170/30720] via 192.168.1.1, 00:00:15, GigabitEthernet0/1
                via_index = parts.index('via')
                network = parts[1]
                if '/' in network:
                    network, mask_or_prefix = network.split('/')
                
                # Извлекаем административное расстояние и метрику
                if '[' in parts[2]:
                    adm_metric = parts[2].strip('[]')
                    admin_distance, metric = adm_metric.split('/')
                
                next_hop = parts[via_index + 1].rstrip(',')
                
                # Интерфейс и время могут быть не у всех маршрутов
                if len(parts) > via_index + 2:
                    if ',' in parts[via_index + 2]:
                        interface = parts[via_index + 3].rstrip(',') if len(parts) > via_index + 3 else None
                        time_info = ' '.join(parts[via_index + 4:]) if len(parts) > via_index + 4 else None
                    else:
                        interface = parts[via_index + 2].rstrip(',')
                        time_info = ' '.join(parts[via_index + 3:]) if len(parts) > via_index + 3 else None
            
            routes.append({
                'type': route_type,
                'network': network,
                'mask': None,
                'prefix': mask_or_prefix,
                'admin_distance': admin_distance,
                'metric': metric,
                'next_hop': next_hop,
                'interface': interface,
                'time': time_info
            })
    
    return routes

def parse_huawei_routing_table(output):
    """Парсинг вывода Huawei 'display ip routing-table' для реального оборудования"""
    routes = []
    
    for line in output.splitlines():
        if not line.strip() or line.startswith('Route Flags:'):
            continue
            
        parts = line.split()
        if len(parts) < 6:
            continue
            
        # Пример строки:
        # Destination/Mask    Proto   Pre  Cost      Flags NextHop         Interface
        # 10.1.1.0/24         OSPF    10   2           D   192.168.1.1    GigabitEthernet0/0/1
        route_type = parts[1][0]  # Первый символ протокола
        
        # Обработка сети/маски
        dest_mask = parts[0]
        if '/' in dest_mask:
            network, prefix = dest_mask.split('/')
            mask = None
        else:
            network = dest_mask
            prefix = None
            mask = '255.255.255.255'  # Для хост-маршрутов
            
        admin_distance = parts[2]
        metric = parts[3]
        next_hop = parts[5] if len(parts) > 5 else None
        interface = parts[6] if len(parts) > 6 else None
        
        routes.append({
            'type': route_type,
            'network': network,
            'mask': mask,
            'prefix': prefix,
            'admin_distance': admin_distance,
            'metric': metric,
            'next_hop': next_hop,
            'interface': interface,
            'time': None  # Huawei обычно не показывает время
        })
    
    return routes

def parse_cisco_mac_table(output):
    """Парсинг вывода Cisco 'show mac address-table'"""
    mac_entries = []
    
    # Пример вывода:
    #           Mac Address Table
    # -------------------------------------------
    # Vlan    Mac Address       Type        Ports
    # ----    -----------       --------    -----
    #  100    0011.2233.4455    DYNAMIC     Gi0/1
    #  200    aabb.ccdd.eeff    STATIC      Gi0/2
    
    for line in output.splitlines():
        if not line.strip() or line.startswith('Mac Address Table') or line.startswith('---'):
            continue
            
        parts = line.split()
        if len(parts) < 4:
            continue
            
        # Проверяем, начинается ли строка с VLAN (число)
        if parts[0].isdigit():
            vlan = parts[0]
            mac = parts[1]
            entry_type = parts[2].capitalize()
            port = ' '.join(parts[3:])  # Объединяем оставшиеся части (на случай пробелов в имени порта)
            
            # Определяем статус порта (упрощенно - для реального устройства нужно проверять статус интерфейса)
            port_status = 'up' if not port.startswith('Po') else 'down'
            
            mac_entries.append({
                'vlan': vlan,
                'mac_address': format_mac_address(mac),
                'type': entry_type,
                'port': port,
                'port_status': port_status,
                'age': '0' if entry_type.lower() == 'static' else str(random.randint(10, 3600))
            })
    
    return mac_entries

def parse_huawei_mac_table(output):
    """Парсинг вывода Huawei 'display mac-address'"""
    mac_entries = []
    
    # Пример вывода:
    # MAC Address    VLAN/VSI/BD   Learned-From        Type               Age
    # ---------------------------------------------------------------
    # 00-11-22-33-44-56 100/-/-      GE0/0/1             dynamic          20
    # AA-BB-CC-DD-EE-FF 200/-/-      GE0/0/2             static           -
    
    for line in output.splitlines():
        if not line.strip() or line.startswith('MAC Address') or line.startswith('---'):
            continue
            
        parts = line.split()
        if len(parts) < 5:
            continue
            
        mac = parts[0]
        vlan = parts[1].split('/')[0]  # Берем только VLAN (игнорируем VSI/BD)
        port = parts[2]
        entry_type = parts[3].capitalize()
        age = parts[4] if len(parts) > 4 else '0'
        
        # Определяем статус порта
        port_status = 'up' if not port.startswith('Eth') else 'down'
        
        mac_entries.append({
            'vlan': vlan,
            'mac_address': format_mac_address(mac),
            'type': entry_type,
            'port': port,
            'port_status': port_status,
            'age': age if age != '-' else '0'
        })
    
    return mac_entries

def format_mac_address(mac):
    """Форматирование MAC-адреса к единому виду (00:11:22:33:44:55)"""
    # Удаляем все разделители и приводим к нижнему регистру
    clean_mac = re.sub(r'[^a-fA-F0-9]', '', mac).lower()
    
    # Вставляем двоеточия каждые 2 символа
    formatted_mac = ':'.join(clean_mac[i:i+2] for i in range(0, 12, 2))
    
    return formatted_mac

def parse_cisco_arp_table(output):
    """Парсинг вывода Cisco 'show arp'"""
    arp_entries = []
    
    # Пример вывода Cisco:
    # Protocol  Address          Age (min)  Hardware Addr   Type   Interface
    # Internet  192.168.1.1            0   0011.2233.4455  ARPA   GigabitEthernet0/1
    # Internet  192.168.1.2            -   0022.3344.5566  ARPA   GigabitEthernet0/2
    # Internet  192.168.1.3            5   Incomplete      ARPA
    
    for line in output.splitlines():
        if not line.strip() or line.startswith('Protocol') or line.startswith('---'):
            continue
            
        parts = line.split()
        if len(parts) < 4:
            continue
            
        # Проверяем, начинается ли строка с "Internet"
        if parts[0] == 'Internet':
            ip = parts[1]
            age = parts[2] if parts[2] != '-' else '0'
            mac = parts[3] if parts[3].lower() != 'incomplete' else 'Incomplete'
            interface = ' '.join(parts[5:]) if len(parts) > 5 else 'N/A'
            
            # Определяем тип записи
            if mac == 'Incomplete':
                entry_type = 'Incomplete'
            elif age == '0':
                entry_type = 'Static'
            else:
                entry_type = 'Dynamic'
            
            arp_entries.append({
                'ip_address': ip,
                'mac_address': format_mac_address(mac) if mac != 'Incomplete' else 'Incomplete',
                'interface': interface,
                'type': entry_type,
                'age': age,
                'last_update': datetime.now().strftime('%H:%M:%S')
            })
    
    return arp_entries

def parse_huawei_arp_table(output):
    """Парсинг вывода Huawei 'display arp'"""
    arp_entries = []
    
    # Пример вывода Huawei:
    # IP ADDRESS      MAC ADDRESS     EXPIRE(M) TYPE        INTERFACE
    # ------------------------------------------------------------
    # 192.168.1.1     0011-2233-4455  20        D           GE0/0/1
    # 192.168.1.2     0022-3344-5566  -         S           GE0/0/2
    # 192.168.1.3     Incomplete      I         GE0/0/3
    
    for line in output.splitlines():
        if not line.strip() or line.startswith('IP ADDRESS') or line.startswith('---'):
            continue
            
        parts = line.split()
        if len(parts) < 4:
            continue
            
        ip = parts[0]
        mac = parts[1] if parts[1].lower() != 'incomplete' else 'Incomplete'
        expire = parts[2] if parts[2] != '-' else '0'
        entry_type = 'Dynamic' if parts[3] == 'D' else 'Static' if parts[3] == 'S' else 'Incomplete'
        interface = parts[4] if len(parts) > 4 else 'N/A'
        
        arp_entries.append({
            'ip_address': ip,
            'mac_address': format_mac_address(mac) if mac != 'Incomplete' else 'Incomplete',
            'interface': interface,
            'type': entry_type,
            'age': expire,
            'last_update': datetime.now().strftime('%H:%M:%S')
        })
    
    return arp_entries


def parse_eltex_interfaces(output):
    """Парсинг вывода 'show interfaces status' для Eltex устройств"""
    interfaces = []
    for line in output.splitlines():
        # Пропускаем заголовки и пустые строки
        if not line.strip() or line.startswith('Port') or line.startswith('---') or line.startswith('Ch'):
            continue
            
        parts = line.split()
        if len(parts) < 5:
            continue
            
        # Для физических интерфейсов (начинаются с te)
        if line.startswith('te'):
            interface_name = parts[0]
            status = 'up' if parts[6].lower() == 'up' else 'down'
            duplex = parts[2].lower()
            speed = parts[3]
            vlan = parts[-1].strip('()') if '(' in parts[-1] else '1'
            
            interfaces.append({
                'name': interface_name,
                'description': '',  # Eltex не показывает описание в этом выводе
                'status': status,
                'vlan': vlan,
                'duplex': duplex,
                'speed': speed + ' Mbps' if speed != '--' else 'auto',
                'type': parts[1]
            })
            
    return interfaces