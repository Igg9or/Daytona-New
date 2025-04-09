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
        
        # Здесь можно добавить логику проверки авторизации
        print(f"Логин: {username}, Пароль: {password}, IP: {ip_address}, Устройство: {device_type}")
        
        # После авторизации можно перенаправить на другую страницу
        # return redirect('/dashboard')
    
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)