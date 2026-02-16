import os
from collections import defaultdict

# 要排除的文件夹
EXCLUDE_DIRS = {'.venv', '__pycache__', '.git', '.idea', 'node_modules', 'venv', 'env'}
# 只统计这些扩展名（按语言分组）
LANG_EXT = {
    'Python': {'.py'},
    'HTML': {'.html', '.htm'},
    'JavaScript': {'.js', '.jsx'},
    'CSS': {'.css', '.scss', '.less'},
    'CSV': {'.csv'},
    'JSON': {'.json'},
    'Markdown': {'.md'},
    'Text': {'.txt'},
    'Shell': {'.sh', '.bash'},
    'Batch': {'.bat', '.cmd'},
    'YAML': {'.yml', '.yaml'},
    '其他': set()
}

def count_lines_in_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return len(f.readlines())
    except:
        return 0

def main():
    stats = defaultdict(int)
    total_files = 0
    
    for root, dirs, files in os.walk('.'):
        # 排除文件夹
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            filepath = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()
            
            # 找语言
            lang = '其他'
            for l, exts in LANG_EXT.items():
                if ext in exts:
                    lang = l
                    break
            
            lines = count_lines_in_file(filepath)
            stats[lang] += lines
            total_files += 1
    
    # 显示结果
    print("\n" + "=" * 50)
    print("📊 项目语言统计（按行数）")
    print("=" * 50)
    
    total_lines = sum(stats.values())
    for lang, lines in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        if lines > 0:
            percent = (lines / total_lines) * 100
            print(f"{lang:12} : {lines:8,} 行 ({percent:.1f}%)")
    
    print("-" * 50)
    print(f"总计文件数   : {total_files:,} 个")
    print(f"总计行数     : {total_lines:,} 行")
    print("=" * 50)

if __name__ == '__main__':
    main()