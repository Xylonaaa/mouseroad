from flask import Flask, render_template, request, redirect, url_for
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
        with open('data.json', encoding='utf-8') as f:
            data = json.load(f)
        schedule = data
        now = datetime.now()
        weekday_map = {0: '一', 1: '二', 2: '三', 3: '四', 4: '五', 5: '六', 6: '日'}
        today = '星期' + weekday_map[now.weekday()]
        for courses in schedule.get(today, []):
           for course in courses:
                # 假设 time 字段的格式为 "X-X节"
                time_range = courses['time'].split('节')[0]
                start_section = int(course['time'].split('-')[0])
                # 这里简单假设每节课开始时间为 8 点，每节课 45 分钟，课间休息 10 分钟
                start_time = f"{8 + (start_section - 1) * 0.75:02.0f}:{((start_section - 1) * 0.75 % 1) * 60:02.0f}"
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
    # 读取课表数据
    schedule = None
    try:
        with open('data.json', encoding='utf-8') as f:
            schedule = json.load(f)
    except Exception:
        schedule = None
    return render_template('index.html', building_name=building_name, address=address, schedule=schedule)

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
            manager.process_user_text(course_text)
            # 成功后重定向到首页并带上success参数
            return redirect(url_for('index', success=1))
        except Exception as e:
            return f"导入失败：{str(e)}"
    return "未提供课表文本。"

if __name__ == '__main__':
    app.run(debug=True)