from flask import Flask, render_template, request, redirect, url_for, session, flash
import json
import os
from datetime import datetime
from import_table import CourseManager
import logging
import re
import logging
import sys

# 設定 logging 輸出支援 UTF-8
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout,  # 輸出到 stdout
    encoding='utf-8'    # 指定使用 UTF-8
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
app.secret_key = 'mouseroadgogogoyeah250709'
# 读取楼名与地址数据
try:
    with open(os.path.join(os.path.dirname(__file__), 'location.json'), encoding='utf-8') as f:
        locations = json.load(f)
    logging.info('成功读取 location.json 文件')
except Exception as e:
    logging.error(f'读取 location.json 文件时出错: {e}')


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
        logging.error(f'获取下一门课程时出错: {e}')
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
        logging.info('成功读取 data.json 文件')
    except Exception as e:
        logging.error(f'读取 data.json 文件时出错: {e}')
        schedule = None
    return render_template('index.html', building_name=building_name, address=address, schedule=schedule)

@app.route('/map')
def map_page():
    # 1. 获取当前用户课表（如有），否则用data.json
    schedule = None
    if 'username' in session:
        user_file = f"user_{session['username']}_schedule.json"
        if os.path.exists(user_file):
            with open(user_file, encoding='utf-8') as f:
                schedule = json.load(f)
    if not schedule:
        try:
            with open('data.json', encoding='utf-8') as f:
                schedule = json.load(f)
        except Exception as e:
            schedule = None
    # 2. 获取当前时间和星期
    now = datetime.now()
    weekday_map = {0: '一', 1: '二', 2: '三', 3: '四', 4: '五', 5: '六', 6: '日'}
    today = '星期' + weekday_map[now.weekday()]
    next_course = None
    next_location_address = None
    if schedule and today in schedule:
        # 3. 找到下一节课
        for course in schedule[today]:
            # 假设 time 字段格式为 "X-X节"
            section_range = course['time'].split('节')[0]
            start_section = int(section_range.split('-')[0])
            # 计算课程开始时间
            start_hour = 8 + (start_section - 1) * 0.75
            start_minute = int(((start_section - 1) * 0.75 % 1) * 60)
            start_time = now.replace(hour=int(start_hour), minute=start_minute, second=0, microsecond=0)
            if start_time > now:
                next_course = course
                # 4. 用正则去掉location中的数字
                location_name = re.sub(r'\d+', '', course['location'])
                location_name = location_name.strip()
                # 5. 去location.json查找具体地址
                for loc in locations:
                    if loc['楼名'] == location_name:
                        next_location_address = loc['具体地址']
                        break
                break
    return render_template('map.html', next_course=next_course, next_location_address=next_location_address)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        # 简单用户名密码校验，实际可查数据库
        if username == 'test' and password == '123456':
            session['username'] = username
            logging.info(f'用户 {username} 登录成功')
            return redirect(url_for('profile'))
        else:
            flash('用户名或密码错误')
            logging.warning(f'用户 {username} 登录失败，密码错误')
    return render_template('login.html')

@app.route('/logout')
def logout():
    username=session.pop('username', None)
    if username:
        logging.info(f'用户 {username} 注销登录')
    return redirect(url_for('login'))

@app.route('/reminder')
def reminder():
    next_course = get_next_course()
    return render_template('reminder.html', next_course=next_course)

@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    next_course = get_next_course()
    return render_template('profile.html', username=username, next_course=next_course)

@app.route('/import_course', methods=['POST'])
def import_course():
    course_text = request.form.get('course_text')
    if course_text:
        manager = CourseManager()
        try:
            manager.process_user_text(course_text)
            # 成功后重定向到首页并带上success参数
            logging.info('课表导入成功')
            return redirect(url_for('index', success=1))
        except Exception as e:
            logging.error(f'课表导入失败: {e}')
            return f"导入失败：{str(e)}"
    logging.warning('未提供课表文本')
    return "未提供课表文本。"

@app.route('/clear_schedule', methods=['POST'])
def clear_schedule():
    """清除课表数据"""
    try:
        if 'username' in session:
            # 清除当前用户的课表
            user_file = f"user_{session['username']}_schedule.json"
            if os.path.exists(user_file):
                os.remove(user_file)
                logging.info(f'用户 {session["username"]} 的课表已清除')
            return redirect(url_for('index', cleared=1))
        else:
            # 清除全局课表
            if os.path.exists('data.json'):
                os.remove('data.json')
                logging.info('全局课表已清除')
            return redirect(url_for('index', cleared=1))
    except Exception as e:
        logging.error(f'清除课表失败: {e}')
        return f"清除失败：{str(e)}"

if __name__ == '__main__':
    logging.info('应用启动')
    app.run(debug=True)