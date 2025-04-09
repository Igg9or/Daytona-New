import random
import time
from datetime import datetime
from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
import re
from datetime import datetime

# Тестовые учетные данные (для имитации успешной аутентификации)
TEST_CREDENTIALS = {
    "admin": "cisco123",
    "user": "password123",
    "test": "test123"
}

def connect_and_collect_data(device_data):
    """Реальное подключение к устройству через SSH с улучшенной обработкой ошибок"""
    connection = None
    try:
        device_type = device_data.get('device_type', 'Cisco').lower()
        netmiko_device_type = 'cisco_ios' if device_type == 'cisco' else 'huawei'
        
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

def parse_memory(connection, device_type):
    """Универсальное получение информации о памяти"""
    try:
        # Пробуем разные команды для разных устройств
        commands_to_try = [
            'show memory statistics',
            'show memory summary',
            'show memory',
            'show processes memory'
        ]
        
        for cmd in commands_to_try:
            try:
                output = connection.send_command(cmd, delay_factor=2)
                
                # Паттерны для разных форматов вывода
                if '100v' in connection.send_command('show version', delay_factor=2):
            pattern = r'Memory:\s*(\d+)K\s*total,\s*(\d+)K\s*used,\s*(\d+)K\s*free'
            match = re.search(pattern, output)
            if match:
                total = int(match.group(1))/1024
                used = int(match.group(2))/1024
                return f"{used:.1f}M/{total:.1f}M ({(used/total)*100:.0f}%)"
                patterns = [
                    # Для Catalyst и IOS
                    (r'Processor\s+pool\s*:\s*(\d+)\D+(\d+)\D+(\d+)', 
                     lambda m: f"{int(m.group(2))/1024}M/{int(m.group(1))/1024}M ({int((int(m.group(2))/int(m.group(1)))*100)}%)"),
                    
                    # Для ISR серии
                    (r'Total\s*:\s*(\d+)\D+Used\s*:\s*(\d+)\D+Free\s*:\s*(\d+)',
                     lambda m: f"{int(m.group(2))/1024}M/{int(m.group(1))/1024}M ({int((int(m.group(2))/int(m.group(1)))*100)}%)"),
                    
                    # Для 100v серии
                    (r'Memory\s+usage\s*:\s*(\d+)\D+total\D+(\d+)\D+used\D+(\d+)',
                     lambda m: f"{int(m.group(2))/1024}M/{int(m.group(1))/1024}M ({int((int(m.group(2))/int(m.group(1)))*100)}%)")
                ]
                
                for pattern, formatter in patterns:
                    match = re.search(pattern, output, re.IGNORECASE)
                    if match:
                        return formatter(match)
                        
            except:
                continue
                
        return "N/A"
    except Exception:
        return "N/A"
    
def get_temperature(connection, device_type):
    """Универсальное получение температуры для разных Cisco устройств"""
    try:
        # Пробуем разные команды для разных устройств
        commands_to_try = [
            'show environment temperature',
            'show environment all',
            'show temperature',
            'show env all'
        ]
        
        for cmd in commands_to_try:
            try:
                output = connection.send_command(cmd, delay_factor=2)
                if not ('invalid' in output.lower() or 'error' in output.lower()):
                    # Парсим для разных форматов вывода
                    patterns = [
                        r'Temperature:\s*(\d+)\s*C',  # Для Catalyst
                        r'Sensor\s+\d+\s*:\s*(\d+)',   # Для ISR
                        r'Temp:\s*(\d+)°C',           # Для некоторых моделей
                        r'CPU\s*Temperature\s*:\s*(\d+)'  # Для 100v серии
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, output, re.IGNORECASE)
                        if match:
                            return f"{match.group(1)}°C"
            except:
                continue
                
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

def get_cpu_usage(connection):
    """Универсальное получение загрузки CPU"""
    try:
        commands = [
            'show processes cpu | include CPU',
            'show cpu usage',
            'show cpu statistics'
        ]
        
        for cmd in commands:
            try:
                output = connection.send_command(cmd, delay_factor=2)
                if output:
                    # Разные форматы вывода
                    patterns = [
                        r'CPU utilization for five seconds:\s*(\d+)%',
                        r'CPU\s*usage\s*:\s*(\d+)%',
                        r'CPU\s*load\s*:\s*(\d+)%'
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, output)
                        if match:
                            return f"{match.group(1)}%"
            except:
                continue
                
        return "N/A"
    except Exception:
        return "N/A"

def parse_interfaces(connection):
    """Универсальный парсинг интерфейсов"""
    try:
        # Получаем краткую информацию
        brief_output = connection.send_command('show ip interface brief', delay_factor=2)
        interfaces = []
        
        for line in brief_output.splitlines()[1:]:
            if line.strip():
                parts = line.split()
                if len(parts) >= 6:
                    interface = {
                        'name': parts[0],
                        'ip': parts[1] if parts[1] != 'unassigned' else 'N/A',
                        'status': parts[4].lower(),
                        'protocol': parts[5].lower(),
                        'description': '',
                        'vlan': '1',
                        'duplex': 'auto',
                        'speed': 'auto'
                    }
                    interfaces.append(interface)
        
        # Дополняем детальной информацией
        for intf in interfaces:
            try:
                details = connection.send_command(f'show interface {intf["name"]}', delay_factor=2)
                
                # Парсим описание
                desc_match = re.search(r'Description:\s*(.+?)\n', details)
                if desc_match:
                    intf['description'] = desc_match.group(1).strip()
                
                # Парсим VLAN
                vlan_match = re.search(r'access vlan\s+(\d+)', details)
                if vlan_match:
                    intf['vlan'] = vlan_match.group(1)
                
                # Парсим дуплекс и скорость
                duplex_match = re.search(r'Duplex:\s*(\w+)', details)
                if duplex_match:
                    intf['duplex'] = duplex_match.group(1).lower()
                
                speed_match = re.search(r'BW\s*(\d+)\s*\w+', details)
                if speed_match:
                    speed = int(speed_match.group(1))
                    intf['speed'] = f"{speed} Mbps" if speed < 1000 else "1 Gbps"
                
            except Exception as e:
                print(f"Ошибка получения деталей интерфейса {intf['name']}: {str(e)}")
        
        return interfaces
    except Exception:
        return []
        
def collect_real_device_data(connection, device_data):
    """Сбор данных с улучшенной обработкой разных устройств"""
    start_time = datetime.now()
    
    try:
        hostname = connection.find_prompt().replace('#', '').replace('>', '')
        
        # Получаем uptime с учетом разных форматов
        uptime = "N/A"
        for cmd in ['show version | include uptime', 'show system uptime']:
            try:
                output = connection.send_command(cmd, delay_factor=2)
                if output and 'invalid' not in output.lower():
                    uptime = parse_uptime(output)
                    break
            except:
                continue
        
        # Получаем версию ПО
        software_version = "N/A"
        for cmd in ['show version | include Software', 'show version | include IOS']:
            try:
                output = connection.send_command(cmd, delay_factor=2)
                if output:
                    software_version = output.split(',')[0].strip()
                    break
            except:
                continue
        
        # Получаем данные
        cpu_load = get_cpu_usage(connection)
        memory_usage = parse_memory(connection, device_data.get('device_type'))
        temperature = get_temperature(connection, device_data.get('device_type'))
        interfaces = parse_interfaces(connection)
        gateway = get_gateway(connection)
        
        exec_time = (datetime.now() - start_time).total_seconds()
        
        return {
            'monitoring': {
                'cpu_load': cpu_load,
                'memory_usage': memory_usage,
                'temperature': temperature
            },
            'configuration': {
                'hostname': hostname,
                'gateway': gateway,
                'software_version': software_version,
                'uptime': uptime
            },
            'interfaces': interfaces,
            'connection_time': f"{exec_time:.2f} сек"
        }
    except Exception as e:
        print(f"Ошибка при сборе данных: {str(e)}")
        raise


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
    """Обновление интерфейса с улучшенной обработкой ошибок"""
    try:
        device_type = device_data.get('device_type', 'Cisco').lower()
        netmiko_device_type = 'cisco_ios' if device_type == 'cisco' else 'huawei'
        
        device_params = {
            'device_type': netmiko_device_type,
            'host': device_data['ip_address'],
            'username': device_data['username'],
            'password': device_data['password'],
            'secret': device_data.get('secret', ''),
            'timeout': 15,
        }
        
        print(f"Подключение для обновления интерфейса {interface_data['interface_name']}...")
        connection = ConnectHandler(**device_params)
        
        try:
            if device_data.get('secret'):
                connection.enable()
            
            commands = [
                f"interface {interface_data['interface_name']}",
                f"description {interface_data['description']}",
            ]
            
            # Добавляем команды в зависимости от типа устройства
            if device_type == 'cisco':
                commands.append(f"switchport access vlan {interface_data['vlan']}")
            else:
                commands.append(f"port default vlan {interface_data['vlan']}")
            
            commands.append("no shutdown" if interface_data['status'] == 'up' else "shutdown")
            
            print(f"Отправка команд: {commands}")
            output = connection.send_config_set(commands)
            print(f"Результат выполнения команд:\n{output}")
            
            # Проверяем успешность выполнения
            if 'Invalid input' in output or 'Error' in output:
                raise Exception(f"Ошибка выполнения команд: {output}")
            
            return True
            
        except Exception as inner_error:
            print(f"Ошибка при обновлении интерфейса: {str(inner_error)}")
            return False
        finally:
            connection.disconnect()
            
    except Exception as e:
        print(f"Ошибка подключения для обновления интерфейса: {str(e)}")
        return False


def get_device_type(device_type):
    """Фиктивная функция для тестов"""
    return "cisco_ios"