from flask import Flask, render_template, request

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Получаем данные из формы
        username = request.form['username']
        password = request.form['password']
        ip_address = request.form['ip_address']
        device_type = request.form['device_type']
        
        # Выводим информацию в консоль
        print("\n" + "="*50)
        print("Полученные данные авторизации:")
        print(f"Логин: {username}")
        print(f"Пароль: {password}")
        print(f"IP-адрес: {ip_address}")
        print(f"Тип устройства: {device_type}")
        print("="*50 + "\n")
        
        # Здесь можно добавить логику проверки авторизации
        # return redirect('/dashboard')  # Перенаправление после авторизации
    
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)