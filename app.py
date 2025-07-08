from flask import Flask, render_template, request
import json
import os
from datetime import datetime
from import_table import CourseManager

app = Flask(__name__)

# 读取楼名与地址数据
with open(os.path.join(os.path.dirname(__file__), 'location.json'), encoding='utf-8') as f:
    locations = json.load(f)

def get_next_course():
    try:
        with open('data/data.json', encoding='utf-8') as f:
            data = json.load(f)
        schedule = data.get('schedule', [])
        now = datetime.now()
        weekday_map = {0: '一', 1: '二', 2: '三', 3: '四', 4: '五', 5: '六', 6: '日'}
        today = '周' + weekday_map[now.weekday()]
        for course in schedule:
            if course['time'].startswith(today):
                # 解析时间段
                time_range = course['time'].split(' ')[1]
                start_time = time_range.split('-')[0]
                course_dt = datetime.strptime(now.strftime('%Y-%m-%d') + ' ' + start_time, '%Y-%m-%d %H:%M')
                if course_dt > now:
                    delta = int((course_dt - now).total_seconds() // 60)
                    return {
                        'course': course['course'],
                        'time': course['time'],
                        'location': course['location'],
                        'minutes_left': delta
                    }
        return None
    except Exception as e:
        return None

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

@app.route('/map')
def map_page():
    next_course = get_next_course()
    return render_template('map.html', next_course=next_course)

@app.route('/import_course', methods=['POST'])
def import_course():
    course_text = request.form.get('course_text')
    if course_text:
        manager = CourseManager()
        try:
            json_data = manager.process_user_text(course_text)
            return json.dumps(json_data, ensure_ascii=False, indent=4)
        except Exception as e:
            return f"导入失败：{str(e)}"
    return "未提供课表文本。"

if __name__ == '__main__':
    app.run(debug=True)
