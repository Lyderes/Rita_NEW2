from flask import Flask, render_template, jsonify, request
import os

app = Flask(__name__, 
            template_folder='../templates',
            static_folder='../static')

# Estado compartido para la UI
ui_status = {
    "status": "esperando",
    "user_text": "",
    "rita_text": ""
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/rita-simon.html')
def simon():
    return render_template('rita-simon.html')

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify(ui_status)

@app.route('/api/update', methods=['POST'])
def update_status():
    global ui_status
    data = request.json
    ui_status.update(data)
    return jsonify({"success": True})

@app.route('/api/exit', methods=['POST'])
def exit_system():
    # Comando radical para cerrar Chromium y Rita en la Raspberry
    os.system("pkill chromium")
    os.system("pkill chromium-browser")
    os.system("pkill -9 python3")
    return jsonify({"status": "apagando"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
