import re
import os
import json
from typing import List, Dict, Optional

class CourseManager:
    """课程表管理系统，处理文本保存、解析和JSON导出"""
    
    def __init__(self, txt_path="YongHuKeBiao.txt", json_path="data.json"):
        self.txt_path = txt_path
        self.json_path = json_path
        self.weekday_map = {
            '星期一': 1, '星期二': 2, '星期三': 3, '星期四': 4, 
            '星期五': 5, '星期六': 6, '星期日': 7
        }
    
    def save_text_to_file(self, text: str) -> None:
        """将用户文本保存到TXT文件"""
        with open(self.txt_path, 'w', encoding='utf-8') as f:
            f.write(text)
    
    def parse_course_text(self) -> List[Dict]:
        """从TXT文件解析课程数据，支持无空行分隔的课表格式"""
        if not os.path.exists(self.txt_path):
            raise FileNotFoundError(f"找不到文件: {self.txt_path}")
        with open(self.txt_path, 'r', encoding='utf-8') as f:
            text = f.read()
        courses = []
        current_weekday = None
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        i = 0
        while i < len(lines):
            line = lines[i]
            # 检查是否为星期行
            weekday_match = re.match(r'^(星期[一二三四五六日])$', line)
            if weekday_match:
                weekday_text = weekday_match.group(1)
                current_weekday = self.weekday_map.get(weekday_text)
                i += 1
                continue
            # 如果当前没有有效的星期，跳过后续解析
            if current_weekday is None:
                i += 1
                continue
            # 检查是否为节次和周次行
            time_week_match = re.match(r'^(\d+)-(\d+)节 \((\d+)-(\d+)周\)$', line)
            if time_week_match:
                start_section = int(time_week_match.group(1))
                end_section = int(time_week_match.group(2))
                start_week = int(time_week_match.group(3))
                end_week = int(time_week_match.group(4))
                # 下一行应该是课程名称
                if i + 1 < len(lines):
                    course_name = lines[i + 1].strip()
                    # 再下一行应该是教室
                    if i + 2 < len(lines):
                        location = lines[i + 2].strip()
                        # 创建课程数据
                        course = {
                            'course_name': course_name,
                            'location': location,
                            'day_of_week': current_weekday,
                            'start_section': start_section,
                            'end_section': end_section,
                            'weeks': f"{start_week}-{end_week}"
                        }
                        courses.append(course)
                        i += 3
                        continue
            i += 1
        return courses
    
    def convert_to_json(self, courses: List[Dict]) -> Dict:
        """将课程列表转换为结构化JSON数据，保证每天课程按节次排序"""
        # 按星期分组
        grouped_data = {i: [] for i in range(1, 8)}  # 1-7对应周一到周日
        for course in courses:
            day = course['day_of_week']
            grouped_data[day].append(course)
        # 每天按 start_section 排序
        for day in grouped_data:
            grouped_data[day].sort(key=lambda x: x['start_section'])
        # 转换为星期文本
        weekday_text_map = {
        1: '星期一', 2: '星期二', 3: '星期三', 
        4: '星期四', 5: '星期五', 6: '星期六', 7: '星期日'
    }
        result = {weekday_text_map[day]: [
            {
                'course_name': c['course_name'],
                'location': c['location'],
                'time': f"{c['start_section']}-{c['end_section']}节",
                'weeks': c['weeks']
            } for c in grouped_data[day]
        ] for day in grouped_data if grouped_data[day]}
        return result
    
    def save_to_json(self, data: Dict) -> None:
        """将数据保存到JSON文件"""
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    
    def process_user_text(self, text: str) -> Dict:
        """处理用户文本的完整流程"""
        # 保存文本到TXT
        self.save_text_to_file(text)
        
        # 解析课程数据
        courses = self.parse_course_text()
        
        # 转换为JSON格式
        json_data = self.convert_to_json(courses)
        
        # 保存到JSON文件
        self.save_to_json(json_data)
        
        return json_data

