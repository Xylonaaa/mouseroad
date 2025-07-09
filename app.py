from flask import Flask, render_template, request, redirect, url_for, session, flash
import json
import os
from datetime import datetime
from import_table import CourseManager
import logging
import re
import sys

# 設定 logging 輸出支援 UTF-8
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout,  # 輸出到 stdout
    encoding='utf-8'    # 指定使用 UTF-8
)

# 配置日志
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s'))

stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s'))

logging.getLogger().addHandler(file_handler)
logging.getLogger().addHandler(stream_handler)

app = Flask(__name__)
app.secret_key = 'mouseroadgogogoyeah250709'
# 读取楼名与地址数据
try:
    with open(os.path.join(os.path.dirname(__file__), 'location.json'), encoding='utf-8') as f:
        locations = json.load(f)
    logging.info('成功读取 location.json 文件，加载了 %d 条楼名与地址数据', len(locations))
except Exception as e:
    logging.error('读取 location.json 文件时出错: %s', str(e))


def get_next_course():
    try:
        with open('data.json', encoding='utf-8') as f:
            data = json.load(f)
        schedule = data
        now = datetime.now()
        weekday_map = {0: '一', 1: '二', 2: '三', 3: '四', 4: '五', 5: '六', 6: '日'}
        today = '星期' + weekday_map[now.weekday()]
        logging.info('当前日期为 %s，开始查找下一门课程', today)
        for course in schedule.get(today, []):
            # 假设 time 字段的格式为 "X-X节"
            time_range = course['time'].split('节')[0]
            start_section = int(time_range.split('-')[0])
            # 这里简单假设每节课开始时间为 8 点，每节课 45 分钟，课间休息 10 分钟
            start_time = f"{8 + (start_section - 1) * 0.75:02.0f}:{((start_section - 1) * 0.75 % 1) * 60:02.0f}"
            course_dt = datetime.strptime(now.strftime('%Y-%m-%d') + ' ' + start_time, '%Y-%m-%d %H:%M')
            if course_dt > now:
                delta = int((course_dt - now).total_seconds() // 60)
                return {
                    'course': course['course_name'],
                    'time': course['time'],
                    'location': course['location'],
                    'minutes_left': delta
                }
        logging.info('今日无后续课程')
        return None
    except Exception as e:
        logging.error('获取下一门课程时出错: %s', str(e))
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    building_name = ''
    address = ''
    if request.method == 'POST':
        building_name = request.form.get('building_name', '').strip()
        logging.info('用户请求查询楼名：%s', building_name)
        for loc in locations:
            if loc['楼名'] == building_name:
                address = loc['具体地址']
                break
        if not address and building_name:
            address = '未找到对应的楼名。'
            logging.warning('未找到楼名 %s 对应的地址', building_name)
        else:
            logging.info('楼名 %s 对应的地址为：%s', building_name, address)
    # 读取课表数据
    schedule = None
    try:
        with open('data.json', encoding='utf-8') as f:
            schedule = json.load(f)
        logging.info('成功读取 data.json 文件,加载了课表数据')
    except Exception as e:
        logging.error('读取 data.json 文件时出错: %s', str(e))
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
            logging.info('成功加载用户 %s 的课表数据', session['username'])
        else:
            logging.info('用户 %s 的课表文件不存在，尝试加载全局课表', session['username'])
    if not schedule:
        try:
            with open('data.json', encoding='utf-8') as f:
                schedule = json.load(f)
            logging.info('成功加载全局课表数据')
        except Exception as e:
            schedule = None
            logging.error('加载课表数据时出错: %s', str(e))
    # 2. 获取当前时间和星期
    now = datetime.now()
    weekday_map = {0: '一', 1: '二', 2: '三', 3: '四', 4: '五', 5: '六', 6: '日'}
    today = '星期' + weekday_map[now.weekday()]
    next_course = None
    next_location_address = None
    # 节次时间表（与index.html一致）
    section_times = [
        '08:00', '08:55', '09:50', '10:45', '11:40',
        '13:30', '14:25', '15:20', '16:15'
    ]
    if schedule and today in schedule:
        min_time_diff = float('inf')
        logging.info('当前日期为 %s，开始查找下一门课程', today)
        for course in schedule[today]:
            section_range = course['time'].split('节')[0]
            start_section = int(section_range.split('-')[0])
            # 用课表时间表
            if 1 <= start_section <= len(section_times):
                start_time_str = section_times[start_section - 1]
                start_time = datetime.strptime(now.strftime('%Y-%m-%d') + ' ' + start_time_str, '%Y-%m-%d %H:%M')
                if start_time > now:
                    time_diff = (start_time - now).total_seconds() / 60
                    if time_diff < min_time_diff:
                        min_time_diff = time_diff
                        next_course = {
                            'course': course['course_name'],
                            'time': course['time'],
                            'location': course['location'],
                            'weeks': course['weeks'],
                            'minutes_left': int(time_diff)
                        }
                        # 正则和地址查找同前
                        location_name = re.sub(r'\d+', '', course['location']).strip()
                        for loc in locations:
                            if loc['楼名'] == location_name:
                                next_location_address = loc['具体地址']
                                break
        if next_course:
            logging.info('找到下一门课程：%s，将于 %s 开始，剩余 %d 分钟，地址为 %s', next_course['course'], next_course['time'], next_course['minutes_left'], next_location_address)
        else:
            logging.info('今日无后续课程')
    return render_template('map.html', next_course=next_course, next_location_address=next_location_address)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        logging.info('用户 %s 尝试登录', username)
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
    if next_course:
        logging.info('为用户提供下一门课程提醒：%s，将于 %s 开始，剩余 %d 分钟', next_course['course'], next_course['time'], next_course['minutes_left'])
    else:
        logging.info('今日无后续课程，无提醒信息')
    return render_template('reminder.html', next_course=next_course)

@app.route('/profile')
def profile():
    if 'username' not in session:
        logging.warning('未登录用户尝试访问个人资料页面，重定向到登录页面')
        return redirect(url_for('login'))
    username = session['username']
    next_course = get_next_course()
    if next_course:
        logging.info('为用户 %s 显示个人资料页面，下一门课程为：%s，将于 %s 开始，剩余 %d 分钟', username, next_course['course'], next_course['time'], next_course['minutes_left'])
    else:
        logging.info('为用户 %s 显示个人资料页面，今日无后续课程', username)
    return render_template('profile.html', username=username, next_course=next_course)

@app.route('/import_course', methods=['POST'])
def import_course():
    course_text = request.form.get('course_text')
    if course_text:
        manager = CourseManager()
        try:
            manager.process_user_text(course_text)
            # 成功后重定向到首页并带上success参数
            logging.info('课表导入成功，处理了 %d 条课程信息', len(course_text.splitlines()))
            return redirect(url_for('index', success=1))
        except Exception as e:
            logging.error(f'课表导入失败: {e}')
            return f"导入失败：{str(e)}"
    logging.warning('未提供课表文本，无法进行导入操作')
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
                logging.info('用户 %s 的课表已清除', session['username'])
            else:
                logging.info('用户 %s 的课表文件不存在，无需清除', session['username'])
            return redirect(url_for('index', cleared=1))
        else:
            # 清除全局课表
            if os.path.exists('data.json'):
                os.remove('data.json')
                logging.info('全局课表已清除')
            else:
                logging.info('全局课表文件不存在，无需清除')
            return redirect(url_for('index', cleared=1))
    except Exception as e:
        logging.error('清除课表失败: %s', str(e))
        return f"清除失败：{str(e)}"

if __name__ == '__main__':
    logging.info('应用启动')
    app.run(debug=True)