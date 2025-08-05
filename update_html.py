import os, time
import subprocess
from datetime import datetime
from collections import defaultdict
import re

def extract_person_count(filename):
    """从文件名中提取人数信息"""
    # 支持多种命名模式
    patterns = [
        r'gdance_sample_[^_]+_p(\d+)_',  # gdance_sample_{split}_p{num_person}_{name}
        r'_person(\d+)',                  # {prefix}_person{num_person}
        r'_p(\d+)_',                     # {prefix}_p{num_person}_{suffix}
        r'person(\d+)',                  # {prefix}person{num_person}
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            return int(match.group(1))
    
    # 如果没有匹配到，返回 None 表示未知人数
    return None

def parse_existing_index(index_file="index.html"):
    """解析现有的index.html文件，提取文件名和对应的Time added信息"""
    existing_times = {}
    
    if not os.path.exists(index_file):
        print(f"⚠️  现有的 {index_file} 不存在，将使用文件系统时间")
        return existing_times
    
    print(f"📖 解析现有的 {index_file} 文件...")
    
    try:
        with open(index_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 多种解析模式，确保能够正确提取时间信息
        
        # 模式1: 匹配新版本的格式 (折叠式布局) - 包含 Added: 和 Updated:
        # <div class="exp-name">filename</div> ... <span class="exp-time">Added: date</span>
        # <div class="exp-name">filename</div> ... <span class="exp-time">🔄 Updated: date</span>
        pattern1 = r'<div class="exp-name">([^<]+)</div>.*?<span class="exp-time[^"]*">(?:🔄 Updated:|Added:)\s*([^<]+)</span>'
        matches1 = re.findall(pattern1, content, re.DOTALL | re.IGNORECASE)
        
        # 模式2: 更宽松的匹配，处理可能的emoji和特殊字符
        # 匹配任何形式的时间前缀
        pattern2 = r'<div class="exp-name">([^<]+)</div>.*?<span[^>]*class="exp-time[^"]*"[^>]*>(?:[^:]*:)?\s*([A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4})</span>'
        matches2 = re.findall(pattern2, content, re.DOTALL | re.IGNORECASE)
        
        # 模式3: 匹配旧版本的格式
        # <h3>filename</h3> ... <p><strong>Time added:</strong> date</p>
        pattern3 = r'<h3>([^<]+)</h3>.*?<p><strong>Time added:</strong>\s*([^<]+)</p>'
        matches3 = re.findall(pattern3, content, re.DOTALL | re.IGNORECASE)
        
        # 模式4: 更通用的时间匹配，直接查找标准时间格式
        # 在exp-name附近查找标准时间格式
        pattern4 = r'<div class="exp-name">([^<]+)</div>.*?([A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4})'
        matches4 = re.findall(pattern4, content, re.DOTALL | re.IGNORECASE)
        
        all_matches = matches1 + matches2 + matches3 + matches4
        
        print(f"  🔍 找到 {len(matches1)} 个新格式匹配 (Added/Updated)")
        print(f"  🔍 找到 {len(matches2)} 个宽松格式匹配")
        print(f"  🔍 找到 {len(matches3)} 个旧格式匹配") 
        print(f"  🔍 找到 {len(matches4)} 个通用时间匹配")
        
        processed_count = 0
        for filename, time_str in all_matches:
            # 清理文件名和时间字符串
            filename = filename.strip()
            time_str = time_str.strip()
            
            # 跳过已经处理过的文件（避免重复）
            if filename in existing_times:
                continue
                
            try:
                # 解析时间字符串，例如: "Fri Mar 21 12:59:18 2025"
                time_obj = time.strptime(time_str, "%a %b %d %H:%M:%S %Y")
                datetime_obj = datetime(*time_obj[:6])
                existing_times[filename] = datetime_obj
                processed_count += 1
                print(f"  ✅ {filename}: {time_str}")
            except ValueError as e:
                print(f"  ⚠️  无法解析时间 '{time_str}' for {filename}: {e}")
                # 尝试其他时间格式
                try:
                    # 尝试解析 ISO 格式或其他格式
                    datetime_obj = datetime.fromisoformat(time_str.replace('T', ' ').replace('Z', ''))
                    existing_times[filename] = datetime_obj
                    processed_count += 1
                    print(f"  ✅ {filename}: {time_str} (备用格式)")
                except:
                    print(f"  ❌ 完全无法解析时间 '{time_str}' for {filename}")
        
        print(f"📊 成功解析 {processed_count} 个文件的时间信息")
        
        # 如果解析结果很少，提供调试信息
        if processed_count < 10:
            print(f"⚠️  解析结果较少，请检查HTML格式")
            # 查找所有exp-name和exp-time的样例
            exp_name_samples = re.findall(r'<div class="exp-name">([^<]+)</div>', content)[:5]
            exp_time_samples = re.findall(r'<span[^>]*class="exp-time[^"]*"[^>]*>([^<]+)</span>', content)[:5]
            
            print(f"实验名称样例: {exp_name_samples}")
            print(f"时间信息样例: {exp_time_samples}")
        
    except Exception as e:
        print(f"❌ 解析现有索引文件时出错: {e}")
    
    return existing_times

def create_visualization_index(experiment_list, output_file="index.html"):
    """创建包含多个可视化链接的索引页面，按人数分组并支持折叠"""
    
    # 首先解析现有的index.html文件获取准确的时间信息
    existing_times = parse_existing_index(output_file)
    
    # 获取今天的日期
    today = datetime.now().date()
    
    # 按人数分组实验
    experiments_by_person = defaultdict(list)
    unknown_person_experiments = []  # 无法确定人数的实验
    
    print(f"🔍 处理文件人数信息...")
    existing_count = 0
    new_count = 0
    updated_today_count = 0
    
    for exp in experiment_list:
        filename = exp['name']  # 不带扩展名的文件名
        
        # 提取人数信息
        person_count = extract_person_count(filename)
        if person_count is None:
            print(f"  ⚠️  无法从文件名提取人数: {filename}")
            unknown_person_experiments.append(exp)
            person_count = 'unknown'
        else:
            print(f"  👥 {filename}: {person_count} 人")
        
        # 获取文件的系统时间信息
        try:
            mtime = os.path.getmtime(exp['file'])  # 文件修改时间
            system_datetime = datetime.fromtimestamp(mtime)
            system_date = system_datetime.date()
            
            # 调试信息：显示文件的最新修改时间
            print(f"    📁 {filename}: 最新修改时间 = {system_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            
        except Exception as e:
            print(f"  ❌ 无法获取 {filename} 的系统时间: {e}")
            system_datetime = datetime.now()
            system_date = today
        
        # 决定使用哪个时间
        if filename in existing_times:
            original_datetime = existing_times[filename]
            
            print(f"    📅 {filename}: 原始记录时间 = {original_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    🕒 今天日期 = {today}")
            print(f"    🔍 文件修改日期 = {system_date}")
            
            # 计算时间差（秒）
            time_diff_seconds = (system_datetime - original_datetime).total_seconds()
            print(f"    ⏰ 时间差 = {time_diff_seconds:.1f} 秒")
            
            # 设置最小更新阈值（1秒），避免微小时间差的误判
            MIN_UPDATE_THRESHOLD_SECONDS = 1.0
            
            # 检查文件是否在今天被修改过，且修改时间明显大于原始记录时间
            if system_date == today and time_diff_seconds > MIN_UPDATE_THRESHOLD_SECONDS:
                # 文件在今天被修改过，且时间明显更新：使用今天的修改时间
                date_obj = system_datetime
                time_diff = system_datetime - original_datetime
                source = f"今天修改 (修改时间: {system_datetime.strftime('%H:%M:%S')}, 比原始时间晚 {time_diff})"
                updated_today_count += 1
                print(f"  🔄 {filename[:45]:<45} -> {date_obj.strftime('%Y-%m-%d %H:%M:%S')} ({source})")
            elif system_date == today and 0 < time_diff_seconds <= MIN_UPDATE_THRESHOLD_SECONDS:
                # 文件是今天修改的，但时间差太小，认为是微小差异，不更新
                date_obj = original_datetime
                source = f"今天修改但时间差太小 ({time_diff_seconds:.1f}秒 ≤ {MIN_UPDATE_THRESHOLD_SECONDS}秒阈值)"
                existing_count += 1
                print(f"  ⏭️  {filename[:45]:<45} -> {date_obj.strftime('%Y-%m-%d %H:%M:%S')} ({source})")
            elif system_date == today and time_diff_seconds <= 0:
                # 文件虽然是今天修改的，但时间没有比原始记录更新
                date_obj = original_datetime
                source = f"今天修改但时间未更新 (修改:{system_datetime.strftime('%H:%M:%S')} <= 原始:{original_datetime.strftime('%H:%M:%S')})"
                existing_count += 1
                print(f"  ⏭️  {filename[:45]:<45} -> {date_obj.strftime('%Y-%m-%d %H:%M:%S')} ({source})")
            else:
                # 文件不是今天修改的：保持原有记录时间
                date_obj = original_datetime
                source = "保持原始记录时间"
                existing_count += 1
                print(f"  📅 {filename[:45]:<45} -> {date_obj.strftime('%Y-%m-%d %H:%M:%S')} ({source})")
        else:
            # 新文件：使用文件的修改时间
            date_obj = system_datetime
            source = "新文件 (文件修改时间)"
            new_count += 1
            print(f"  🆕 {filename[:45]:<45} -> {date_obj.strftime('%Y-%m-%d %H:%M:%S')} ({source})")
        
        # 添加详细时间信息到实验数据
        exp['datetime'] = date_obj
        exp['time_display'] = date_obj.strftime('%H:%M:%S')
        exp['date_display'] = date_obj.strftime('%Y-%m-%d %H:%M:%S')
        exp['original_date_str'] = date_obj.strftime('%a %b %d %H:%M:%S %Y')  # 保持原格式
        exp['is_updated_today'] = (filename in existing_times and system_date == today and time_diff_seconds > MIN_UPDATE_THRESHOLD_SECONDS if 'time_diff_seconds' in locals() else False)
        exp['person_count'] = person_count
        
        experiments_by_person[person_count].append(exp)
    
    print(f"\n📊 文件处理统计:")
    print(f"  ✅ 现有文件 (保持原始时间): {existing_count}")
    print(f"  🔄 今天更新的文件 (刷新时间): {updated_today_count}")
    print(f"  🆕 新增文件 (使用系统时间): {new_count}")
    print(f"  📋 总计: {len(experiment_list)} 个文件")
    
    if updated_today_count > 0:
        print(f"\n🎉 本次更新了 {updated_today_count} 个文件的时间戳！")
    
    # 对每个人数分组下的实验按时间排序（最新的在前）
    for person_count in experiments_by_person:
        experiments_by_person[person_count].sort(key=lambda x: x['datetime'], reverse=True)
    
    # 获取排序后的人数列表（按人数升序，unknown放在最后）
    sorted_person_counts = []
    numeric_counts = [k for k in experiments_by_person.keys() if isinstance(k, int)]
    numeric_counts.sort()
    sorted_person_counts.extend(numeric_counts)
    if 'unknown' in experiments_by_person:
        sorted_person_counts.append('unknown')
    
    print(f"📊 人数分布统计:")
    for person_count in sorted_person_counts:
        count = len(experiments_by_person[person_count])
        if person_count == 'unknown':
            print(f"  ❓ 未知人数: {count} 个实验")
        else:
            print(f"  👥 {person_count} 人: {count} 个实验")
    
    print(f"📈 总计: {len(experiment_list)} 个实验分布在 {len(sorted_person_counts)} 个人数组")
    
    # 创建HTML内容
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Group Dance 3D Plot - Experiment Records (Organized by Group Size)</title>
        <meta charset="UTF-8">
        <style>
            body {{ 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 20px; 
                background-color: #f5f5f5;
                line-height: 1.6;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h1 {{ 
                color: #2c3e50; 
                text-align: center;
                margin-bottom: 10px;
                font-size: 2.5em;
            }}
            .subtitle {{
                text-align: center;
                color: #7f8c8d;
                font-size: 1.2em;
                margin-bottom: 30px;
            }}
            .person-toggle {{
                margin: 15px 0;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }}
            .person-header {{
                background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
                color: white;
                padding: 15px 20px;
                cursor: pointer;
                font-weight: 600;
                font-size: 1.1em;
                transition: all 0.3s ease;
                user-select: none;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .person-header:hover {{
                background: linear-gradient(135deg, #0984e3 0%, #74b9ff 100%);
            }}
            .person-header.unknown {{
                background: linear-gradient(135deg, #a29bfe 0%, #6c5ce7 100%);
            }}
            .person-header.unknown:hover {{
                background: linear-gradient(135deg, #6c5ce7 0%, #a29bfe 100%);
            }}
            .toggle-icon {{
                transition: transform 0.3s ease;
                font-size: 1.2em;
            }}
            .person-content {{
                display: none;
                background: #fafafa;
                border-top: 1px solid #e0e0e0;
            }}
            .person-content.active {{
                display: block;
            }}
            .exp-item {{ 
                margin: 0;
                padding: 15px 20px; 
                border-bottom: 1px solid #eeeeee;
                background: white;
                transition: background-color 0.2s ease;
            }}
            .exp-item:last-child {{
                border-bottom: none;
            }}
            .exp-item:hover {{
                background-color: #f8f9ff;
            }}
            .exp-name {{ 
                font-weight: 600;
                color: #2c3e50;
                margin-bottom: 8px;
                font-size: 1.05em;
            }}
            .exp-details {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 10px;
            }}
            .exp-time {{
                color: #7f8c8d;
                font-size: 0.9em;
            }}
            .exp-link {{
                display: inline-block;
                padding: 8px 16px;
                background: linear-gradient(135deg, #00b894 0%, #00a085 100%);
                color: white;
                text-decoration: none;
                border-radius: 5px;
                font-size: 0.9em;
                transition: all 0.3s ease;
                font-weight: 500;
            }}
            .exp-link:hover {{
                background: linear-gradient(135deg, #00a085 0%, #00b894 100%);
                transform: translateY(-1px);
                box-shadow: 0 4px 8px rgba(0, 184, 148, 0.3);
            }}
            .stats {{
                background: #ecf0f1;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                text-align: center;
                color: #2c3e50;
            }}
            .stats strong {{
                color: #e74c3c;
                font-size: 1.2em;
            }}
            .person-icon {{
                margin-right: 8px;
                font-size: 1.1em;
            }}
            @media (max-width: 768px) {{
                .container {{ margin: 10px; padding: 15px; }}
                h1 {{ font-size: 2em; }}
                .exp-details {{ flex-direction: column; align-items: flex-start; }}
                .person-header {{ padding: 12px 15px; }}
                .exp-item {{ padding: 12px 15px; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Group Dance 3D Plot</h1>
            <p class="subtitle">Experiment Records - Organized by Group Size</p>
            
            <div class="stats">
                <strong>{total_experiments}</strong> experiments across <strong>{total_groups}</strong> group sizes
            </div>
    """
    
    html_content = html_template.format(
        total_experiments=len(experiment_list),
        total_groups=len(sorted_person_counts)
    )
    
    # 为每个人数分组创建一个折叠区域
    for i, person_count in enumerate(sorted_person_counts):
        experiments = experiments_by_person[person_count]
        
        # 设置标题和样式
        if person_count == 'unknown':
            header_text = f"❓ Unknown Group Size ({len(experiments)} experiments)"
            header_class = "person-header unknown"
            icon = "❓"
        else:
            header_text = f"👥 {person_count} People ({len(experiments)} experiments)"
            header_class = "person-header"
            icon = "👥"
        
        # 第一个分组默认展开
        is_first = i == 0
        content_class = "person-content active" if is_first else "person-content"
        icon_rotation = "rotate(90deg)" if is_first else "rotate(0deg)"
        
        html_content += f"""
            <div class="person-toggle">
                <div class="{header_class}" onclick="togglePerson(this)">
                    <span><span class="person-icon">{icon}</span>{header_text}</span>
                    <span class="toggle-icon" style="transform: {icon_rotation};">▶</span>
                </div>
                <div class="{content_class}">
        """
        
        # 添加该人数分组下的所有实验
        for exp in experiments:
            html_content += f"""
                    <div class="exp-item">
                        <div class="exp-name">{exp['name']}</div>
                        <div class="exp-details">
                            <span class="exp-time">Added: {exp['original_date_str']}</span>
                            <a href="{exp['file']}" target="_blank" class="exp-link">
                                🎮 Interact with 3D plot
                            </a>
                        </div>
                    </div>
            """
        
        html_content += """
                </div>
            </div>
        """
    
    html_content += """
        </div>

        <script>
            function togglePerson(header) {
                const content = header.nextElementSibling;
                const icon = header.querySelector('.toggle-icon');
                
                if (content.classList.contains('active')) {
                    content.classList.remove('active');
                    icon.style.transform = 'rotate(0deg)';
                } else {
                    content.classList.add('active');
                    icon.style.transform = 'rotate(90deg)';
                }
            }

            // Add keyboard support
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') {
                    // Close all toggles
                    document.querySelectorAll('.person-content.active').forEach(content => {
                        content.classList.remove('active');
                        const icon = content.previousElementSibling.querySelector('.toggle-icon');
                        icon.style.transform = 'rotate(0deg)';
                    });
                }
                
                // Press 'a' to expand all sections
                if (e.key === 'a' || e.key === 'A') {
                    document.querySelectorAll('.person-content').forEach(content => {
                        content.classList.add('active');
                        const icon = content.previousElementSibling.querySelector('.toggle-icon');
                        icon.style.transform = 'rotate(90deg)';
                    });
                }
            });

            // Auto-scroll to top on page load
            window.addEventListener('load', function() {
                window.scrollTo(0, 0);
            });
        </script>
    </body>
    </html>
    """
    
    with open(output_file, "w", encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ Updated the index.html: {output_file}")
    print(f"📊 Total: {len(experiment_list)} experiments across {len(sorted_person_counts)} group sizes")
    return output_file

def push_to_github(repo_dir, message="更新可视化索引页面"):
    """将更改推送到GitHub仓库"""
    try:
        # 切换到仓库目录
        os.chdir(repo_dir)
        
        # 添加所有更改
        subprocess.run(["git", "add", "."], check=True)
        
        # 提交更改
        subprocess.run(["git", "commit", "-m", message], check=True)
        
        # 推送到GitHub
        subprocess.run(["git", "push"], check=True)
        
        print("✅ 已成功推送更改到GitHub")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 推送到GitHub时出错: {e}")
        return False

def main():
    root = 'results'
    experiments = []

    if not os.path.exists(root):
        print(f"❌ 目录 '{root}' 不存在")
        return

    print(f"🔍 扫描目录: {root}")
    
    for file in os.listdir(root):
        if file.endswith('.html'):
            meta = {}
            meta['name'] = file.split('.')[0]  # 文件名（不含扩展名）
            meta['file'] = os.path.join(root, file)
            
            if os.path.exists(meta['file']):
                experiments.append(meta)
                print(f"  📄 发现: {file}")
    
    if not experiments:
        print("❌ 在results目录中没有找到HTML文件")
        return
    
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"\n📝 生成按人数分组的索引页面 (今天: {today})...")
    create_visualization_index(experiments, "index.html")
    
    print(f"\n🚀 推送到GitHub...")
    push_to_github('./', message=f"更新可视化索引页面 - 改为按人数分组 ({today})")

if __name__ == "__main__":
    main()