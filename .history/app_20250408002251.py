from flask import Flask, render_template, request, redirect, url_for
from device_connector import connect_to_device

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        device_data = {
            'username': request.form['username'],
            'password': request.form['password'],
            'ip_address': request.form['ip_address'],
            'device_type': request.form['device_type']
        }
        
        # Подключаемся к устройству
        result = connect_to_device(device_data)
        
        # Перенаправляем на страницу с результатом
        return redirect(url_for('show_result', result=result))
    
    return render_template('login.html')

@app.route('/result/<path:result>')
def show_result(result):
    return f"""
    <h1>Результат подключения</h1>
    <pre>{result}</pre>
    <a href="/">Вернуться</a>
    """

if __name__ == '__main__':
    app.run(debug=True)