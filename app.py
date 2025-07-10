from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import json
import os
from datetime import datetime, timedelta
from import_table import CourseManager
import logging
import re
import sys
from werkzeug.utils import secure_filename

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


def calculate_walking_time(location):
    """
    根据教室位置计算预计步行时间（分钟）
    
    Args:
        location: 教室位置字符串
        
    Returns:
        预计步行时间（分钟）
    """
    # 基础步行时间（分钟）
    base_walking_time = 5
    
    # 根据楼层调整时间
    floor_adjustment = 0
    if '楼' in location:
        # 提取楼层数字
        import re
        floor_match = re.search(r'(\d+)楼', location)
        if floor_match:
            floor_num = int(floor_match.group(1))
            # 每层楼增加1分钟
            floor_adjustment = floor_num - 1
    
    # 根据建筑距离调整时间
    distance_adjustment = 0
    if '教学楼' in location:
        distance_adjustment = 3
    elif '实验楼' in location:
        distance_adjustment = 5
    elif '图书馆' in location:
        distance_adjustment = 8
    elif '体育馆' in location:
        distance_adjustment = 10
    
    total_time = base_walking_time + floor_adjustment + distance_adjustment
    
    # 确保时间在合理范围内（5-20分钟）
    return max(5, min(20, total_time))

def calculate_suggested_departure_time(course_time, walking_time):
    """
    根据课程时间和步行时间计算建议出门时间
    
    Args:
        course_time: 课程时间字符串，格式如 "3-4节"
        walking_time: 步行时间（分钟）
        
    Returns:
        建议出门时间字符串，格式如 "07:45"
    """
    try:
        # 解析课程节次
        section_range = course_time.split('节')[0]
        start_section = int(section_range.split('-')[0])
        
        # 节次时间表（与index.html一致）
        section_times = [
            '08:00', '08:55', '09:50', '10:45', '11:40',
            '13:30', '14:25', '15:20', '16:15'
        ]
        
        if 1 <= start_section <= len(section_times):
            start_time_str = section_times[start_section - 1]
            start_time = datetime.strptime(start_time_str, '%H:%M')
            
            # 建议提前10分钟到达教室，加上步行时间
            total_advance_time = walking_time + 10
            
            # 计算建议出门时间
            departure_time = start_time - timedelta(minutes=total_advance_time)
            
            return departure_time.strftime('%H:%M')
        else:
            return "08:00"  # 默认时间
    except Exception as e:
        logging.error(f'计算建议出门时间失败: {e}')
        return "08:00"  # 默认时间

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

PROFILE_FIELDS = ['realname', 'nickname', 'grade', 'major', 'gender', 'signature', 'avatar']
PROFILE_DEFAULTS = {
    'realname': '',
    'nickname': '',
    'grade': '',
    'major': '',
    'gender': '',
    'signature': '',
    'avatar': ''
}
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_user_profile(username):
    profile_file = f"user_{username}_profile.json"
    if os.path.exists(profile_file):
        with open(profile_file, encoding='utf-8') as f:
            profile = json.load(f)
        # 补全缺失字段
        for k, v in PROFILE_DEFAULTS.items():
            if k not in profile:
                profile[k] = v
        return profile
    else:
        return PROFILE_DEFAULTS.copy()

def save_user_profile(username, profile):
    profile_file = f"user_{username}_profile.json"
    with open(profile_file, 'w', encoding='utf-8') as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

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
    # 读取课表数据，优先用户课表
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
            logging.info('成功读取 data.json 文件')
        except Exception as e:
            logging.error(f'读取 data.json 文件时出错: {e}')
            schedule = None
    return render_template('index.html', building_name=building_name, address=address, schedule=schedule)

@app.route('/map')
def map_page():
    # 检查是否有从首页传递的课程参数
    course_name = request.args.get('course')
    course_time = request.args.get('time')
    course_location = request.args.get('location')
    course_weeks = request.args.get('weeks')
    
    # 如果从首页传递了课程信息，直接使用
    if course_name and course_location:
        selected_course = {
            'course': course_name,
            'time': course_time or '',
            'location': course_location,
            'weeks': course_weeks or '',
            'minutes_left': 0  # 从首页点击时不需要计算剩余时间
        }
        # 查找对应的地址
        location_name = re.sub(r'\d+', '', course_location).strip()
        next_location_address = None
        for loc in locations:
            if loc['楼名'] == location_name:
                next_location_address = loc['具体地址']
                break
        
        # 计算预计路程时间和建议出门时间
        estimated_walking_time = calculate_walking_time(course_location)
        suggested_departure_time = calculate_suggested_departure_time(course_time, estimated_walking_time)
        
        selected_course['estimated_walking_time'] = estimated_walking_time
        selected_course['suggested_departure_time'] = suggested_departure_time
        
        logging.info('从首页接收到课程信息：%s，地点：%s，地址：%s，预计步行时间：%d分钟', 
                    course_name, course_location, next_location_address, estimated_walking_time)
        return render_template('map.html', next_course=selected_course, next_location_address=next_location_address)
    
    # 如果没有从首页传递参数，则按原来的逻辑查找下一门课程
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
                        
                        # 计算预计路程时间和建议出门时间
                        estimated_walking_time = calculate_walking_time(course['location'])
                        suggested_departure_time = calculate_suggested_departure_time(course['time'], estimated_walking_time)
                        
                        next_course['estimated_walking_time'] = estimated_walking_time
                        next_course['suggested_departure_time'] = suggested_departure_time
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
    profile_info = get_user_profile(username)
    if next_course:
        logging.info('为用户 %s 显示个人资料页面，下一门课程为：%s，将于 %s 开始，剩余 %d 分钟', username, next_course['course'], next_course['time'], next_course['minutes_left'])
    else:
        logging.info('为用户 %s 显示个人资料页面，今日无后续课程', username)
    return render_template('profile.html', username=username, next_course=next_course, profile=profile_info)

@app.route('/update_profile_field', methods=['POST'])
def update_profile_field():
    if 'username' not in session:
        return jsonify({'success': False, 'msg': '未登录'}), 401
    username = session['username']
    field = request.form.get('field')
    if field not in PROFILE_FIELDS:
        return jsonify({'success': False, 'msg': '字段非法'}), 400
    profile = get_user_profile(username)
    if field == 'avatar':
        if 'avatar' not in request.files:
            return jsonify({'success': False, 'msg': '未上传头像文件'}), 400
        file = request.files['avatar']
        if file.filename == '':
            return jsonify({'success': False, 'msg': '未选择文件'}), 400
        filename = secure_filename(f"{username}_avatar_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        profile['avatar'] = filename
    else:
        value = request.form.get('value', '')
        profile[field] = value
    save_user_profile(username, profile)
    return jsonify({'success': True, 'msg': '更新成功', 'field': field, 'value': profile[field]})

@app.route('/remove_avatar', methods=['POST'])
def remove_avatar():
    if 'username' not in session:
        return jsonify({'success': False, 'msg': '未登录'}), 401
    username = session['username']
    profile = get_user_profile(username)
    avatar_filename = profile.get('avatar', '')
    if avatar_filename:
        avatar_path = os.path.join(app.config['UPLOAD_FOLDER'], avatar_filename)
        if os.path.exists(avatar_path):
            try:
                os.remove(avatar_path)
            except Exception as e:
                logging.error(f'删除头像文件失败: {e}')
    profile['avatar'] = ''
    save_user_profile(username, profile)
    return jsonify({'success': True, 'msg': '头像已移除'})

@app.route('/import_course', methods=['POST'])
def import_course():
    course_text = request.form.get('course_text')
    if course_text:
        # 获取当前用户名，如果已登录则使用用户特定文件
        username = session.get('username') if 'username' in session else None
        manager = CourseManager(username=username)
        try:
            manager.process_user_text(course_text)
            # 成功后重定向到首页并带上success参数
            logging.info('课表导入成功，处理了 %d 条课程信息，用户: %s', len(course_text.splitlines()), username or '未登录')
            return redirect(url_for('index', success=1))
        except Exception as e:
            logging.error(f'课表导入失败: {e}')
            return f"导入失败：{str(e)}"
    logging.warning('未提供课表文本，无法进行导入操作')
    return "未提供课表文本。"

@app.route('/import_course_excel', methods=['POST'])
def import_course_excel():
    if 'excel_file' not in request.files:
        return '未上传Excel文件', 400
    file = request.files['excel_file']
    if file.filename == '':
        return '未选择文件', 400
    filename = secure_filename(file.filename)
    temp_path = os.path.join('static', 'uploads', filename)
    file.save(temp_path)
    # 获取当前用户名，如果已登录则使用用户特定文件
    username = session.get('username') if 'username' in session else None
    manager = CourseManager(username=username)
    try:
        manager.process_user_excel(temp_path)
        os.remove(temp_path)
        logging.info('Excel课表导入成功，用户: %s', username or '未登录')
        return redirect(url_for('index', success=1))
    except Exception as e:
        logging.error(f'Excel课表导入失败: {e}')
        return f"导入失败：{str(e)}"

@app.route('/clear_schedule', methods=['POST'])
def clear_schedule():
    try:
        if 'username' in session:
            user_file = f"user_{session['username']}_schedule.json"
            abs_user_file = os.path.abspath(user_file)
            logging.info(f'尝试删除用户课表文件: {abs_user_file}')
            if os.path.exists(user_file):
                os.remove(user_file)
                logging.info(f'用户课表文件 {abs_user_file} 已删除')
            else:
                logging.info(f'用户课表文件 {abs_user_file} 不存在')
        else:
            abs_data_file = os.path.abspath('data.json')
            logging.info(f'尝试清空全局课表文件: {abs_data_file}')
            with open('data.json', 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
            logging.info(f'已将 {abs_data_file} 内容清空')
        return redirect(url_for('index', cleared=1, cleared_success=1))
    except Exception as e:
        logging.error(f'清除课表失败: {e}')
        return f"清除失败：{str(e)}"


if __name__ == '__main__':
    logging.info('应用启动')
    app.run(debug=True)