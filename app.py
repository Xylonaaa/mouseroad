from flask import Flask, render_template, request
import json
import os

app = Flask(__name__)

# 读取楼名与地址数据
with open(os.path.join(os.path.dirname(__file__), 'location.json'), encoding='utf-8') as f:
    locations = json.load(f)

@app.route('/', methods=['GET', 'POST'])
def index():
    building_name = ''
    address = ''
    if request.method == 'POST':
        building_name = request.form.get('building_name', '').strip()
        for loc in locations:
            if loc['楼名'] == building_name:
                address = loc['具体地址']
                break
        if not address and building_name:
            address = '未找到对应的楼名。'
    return render_template('index.html', building_name=building_name, address=address)

if __name__ == '__main__':
    app.run(debug=True)
