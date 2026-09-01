#!/usr/bin/env python3
"""
统一测试数据生成器 v2 - 增强版
重点：增加第8-10组的数据强度，确保暴力/次优解会TLE
"""
import os
import sys
import random
import subprocess
from pathlib import Path

BASE = Path(__file__).parent

def run_std(problem_dir, in_file, out_file):
    """调用标准程序生成输出"""
    std_script = problem_dir / "std.py"
    if not std_script.exists():
        print(f"  [警告] {std_script} 不存在，跳过")
        return False
    with open(in_file, "r") as fin:
        result = subprocess.run(
            [sys.executable, str(std_script)],
            stdin=fin,
            capture_output=True,
            text=True,
            timeout=120
        )
    with open(out_file, "w") as fout:
        fout.write(result.stdout)
    if result.returncode != 0:
        print(f"  [错误] {problem_dir.name} 运行失败: {result.stderr[:200]}")
        return False
    return True

# ===================== 2024年题目 ====================

def gen_2024_01():
    """判断格子 - O(n)算法，n越大越好"""
    d = BASE / "suzhou_2024" / "01_check_color"
    random.seed(202401)
    for i in range(1, 11):
        if i <= 3:
            # 基础样例
            t = [3, 10, 100][i-1]
        elif i <= 7:
            t = random.randint(100, 1000)
        else:
            # 高强度：5000~10000，确保O(n)算法轻松通过
            t = random.randint(5000, 10000)
        
        with open(f"{d}/{i:02d}.in", "w") as f:
            f.write(f"{t}\n")
            for _ in range(t):
                col = random.randint(1, 8)
                row = random.randint(1, 8)
                f.write(f"{chr(ord('a')+col-1)}{row}\n")
        run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")

def gen_2024_02():
    """相差几天 - 需要O(1)或O(月份)计算，暴力逐天遍历会TLE"""
    d = BASE / "suzhou_2024" / "02_days_diff"
    random.seed(202402)
    is_leap = lambda y: (y%4==0 and y%100!=0) or (y%400==0)
    dim = [0,31,28,31,30,31,30,31,31,30,31,30,31]
    
    for i in range(1, 11):
        if i == 1:
            raw = "3\n2000 1 1 2000 3 1\n1999 2 29 1999 3 1\n2000 1 1 2024 1 1\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("60\n-1\n8766\n")
            continue
        elif i == 2:
            raw = "5\n2024 1 1 2024 1 1\n2024 1 1 2024 1 2\n2024 2 28 2024 3 1\n2023 12 31 2024 1 1\n2000 2 28 2000 3 1\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("0\n1\n1\n1\n1\n")
            continue
        elif i == 3:
            t = 100  # 非法日期测试
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{t}\n")
                for _ in range(t):
                    y = random.randint(0, 3500)
                    m = random.randint(-5, 20)
                    day = random.randint(-5, 40)
                    f.write(f"{y} {m} {day} {y} {m} {day}\n")
            run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")
            continue
        
        # 高强度测试：跨越数千年的日期差，暴力逐天必TLE
        t = random.randint(100, 500) if i < 8 else 2000
        with open(f"{d}/{i:02d}.in", "w") as f:
            f.write(f"{t}\n")
            for _ in range(t):
                if i >= 8:
                    # 超高强度：年份跨度随机到最大
                    y1 = random.randint(1, 3000)
                    m1 = random.randint(1, 12)
                    leap = is_leap(y1)
                    mx = 29 if (leap and m1 == 2) else dim[m1]
                    d1 = random.randint(1, mx)
                    y2 = random.randint(y1, min(y1 + 50000, 3000)) if y1 < 3000 else 3000
                    m2 = random.randint(1, 12)
                    leap2 = is_leap(y2)
                    mx2 = 29 if (leap2 and m2 == 2) else dim[m2]
                    d2 = random.randint(1, mx2)
                else:
                    y1 = random.randint(1, 3000)
                    m1 = random.randint(1, 12)
                    leap = is_leap(y1)
                    mx = 29 if (leap and m1 == 2) else dim[m1]
                    d1 = random.randint(1, mx)
                    y2 = random.randint(y1, min(y1+2000, 3000))
                    m2 = random.randint(1, 12)
                    leap2 = is_leap(y2)
                    mx2 = 29 if (leap2 and m2 == 2) else dim[m2]
                    d2 = random.randint(1, mx2)
                f.write(f"{y1} {m1} {d1} {y2} {m2} {d2}\n")
        run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")

def gen_2024_03():
    """存钱 - n=10^9，必须用O(1)或O(√n)公式，O(n)会TLE"""
    d = BASE / "suzhou_2024" / "03_save_money"
    random.seed(202403)
    for i in range(1, 11):
        if i == 1:
            raw = "3\n4\n6\n365\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("8\n14\n6579\n")
        elif i == 2:
            raw = "5\n1\n2\n3\n7\n10\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("1\n3\n6\n28\n30\n")
        elif i <= 5:
            # 中等规模
            ns = [10**k for k in range(4, 10)] + [random.randint(10**6, 10**8) for _ in range(5)]
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{len(ns)}\n")
                for n in ns: f.write(f"{n}\n")
            run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")
        elif i <= 7:
            # 大规模
            ns = [random.randint(10**8, 10**9) for _ in range(20)]
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{len(ns)}\n")
                for n in ns: f.write(f"{n}\n")
            run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")
        else:
            # 极限：全部是10^9级别
            ns = [10**9] * 50 + [10**9 - 1] * 10 + [random.randint(10**9 - 10**6, 10**9) for _ in range(20)]
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{len(ns)}\n")
                for n in ns: f.write(f"{n}\n")
            run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")

def gen_2024_05():
    """旋转图像 - 矩阵大时O(n*m)操作"""
    d = BASE / "suzhou_2024" / "05_rotate_image"
    random.seed(202405)
    flags_list = [-1, 1, 2, 3]
    
    for i in range(1, 11):
        t = 1 if i < 6 else 5
        with open(f"{d}/{i:02d}.in", "w") as f:
            f.write(f"{t}\n")
        for j in range(t):
            if i == 1 and j == 0:
                data = "-1\n3 3\n1 2 3\n4 5 6\n7 8 9\n"
            elif i == 2 and j == 0:
                data = "1\n3 3\n1 2 3\n4 5 6\n7 8 9\n"
            elif i == 3 and j == 0:
                data = "2\n3 3\n1 2 3\n4 5 6\n7 8 9\n"
            elif i == 4 and j == 0:
                data = "-1\n2 3\n1 2 3\n4 5 6\n"
            elif i == 5 and j == 0:
                data = "1\n3 2\n1 2\n3 4\n5 6\n"
            else:
                flag = flags_list[(i * 3 + j) % 4]
                # 高强度：400x400 矩阵
                if i >= 8:
                    rows = random.randint(300, 500)
                    cols = random.randint(300, 500)
                else:
                    rows = random.randint(50, 200)
                    cols = random.randint(50, 200)
                data = f"{flag}\n{rows} {cols}\n"
                for _ in range(rows):
                    row = " ".join(str(random.randint(-10**9, 10**9)) for _ in range(cols))
                    data += row + "\n"
            with open(f"{d}/{i:02d}.in", "a") as f:
                f.write(data)
        run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")

def gen_2024_06():
    """判断2的幂 - O(1)位运算，数据量要大"""
    d = BASE / "suzhou_2024" / "06_is_power_of_two"
    random.seed(202406)
    
    for i in range(1, 11):
        if i == 1:
            raw = "5\n1\n2\n3\n1024\n0\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("True\nTrue\nFalse\nTrue\nFalse\n")
        elif i == 2:
            raw = "32\n" + "\n".join(str(2**i) for i in range(32)) + "\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("True\n"*32)
        elif i == 3:
            raw = "31\n" + "\n".join(str(2**i - 1) for i in range(1, 32)) + "\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("False\n"*31)
        elif i == 4:
            raw = "4\n0\n1\n4294967295\n2147483648\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("False\nTrue\nFalse\nTrue\n")
        elif i <= 7:
            nums = [random.randint(0, 2**32-1) for _ in range(1000)]
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{len(nums)}\n")
                for n in nums: f.write(f"{n}\n")
            run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")
        else:
            # 高强度：10000个随机大数
            nums = [random.randint(0, 2**32-1) for _ in range(10000)]
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{len(nums)}\n")
                for n in nums: f.write(f"{n}\n")
            run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")

def gen_2024_09():
    """完全平方数 - DP O(n√n)，n=10000足够卡掉暴力"""
    d = BASE / "suzhou_2024" / "09_perfect_square"
    random.seed(202409)
    
    for i in range(1, 11):
        if i == 1:
            raw = "5\n12\n13\n1\n4\n9999\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("3\n2\n1\n1\n4\n")
        elif i == 2:
            raw = "8\n2\n3\n5\n6\n7\n8\n10\n11\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("2\n3\n2\n3\n2\n2\n2\n3\n")
        elif i == 3:
            ns = [i*i for i in range(1, 101)]
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{len(ns)}\n")
                for n in ns: f.write(f"{n}\n")
        elif i == 4:
            ns = [10000, 50000, 99999, 75000, 33333]
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{len(ns)}\n")
                for n in ns: f.write(f"{n}\n")
        elif i <= 7:
            nums = [random.randint(1, 10000) for _ in range(100)]
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{len(nums)}\n")
                for n in nums: f.write(f"{n}\n")
        else:
            # 高强度：全部是最大值 10000，测试多次
            nums = [10000] * 200
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{len(nums)}\n")
                for n in nums: f.write(f"{n}\n")
        if i >= 3:
            run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")

def gen_2024_10():
    """错位排列 - O(n) DP，n=10^5会卡掉暴力递归"""
    d = BASE / "suzhou_2024" / "10_derangement"
    random.seed(202410)
    
    for i in range(1, 11):
        if i == 1:
            raw = "5\n1\n2\n3\n4\n5\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("0\n1\n2\n9\n44\n")
        elif i == 2:
            raw = "10\n" + "\n".join(str(x) for x in range(6, 16)) + "\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
        elif i == 3:
            raw = "10\n" + "\n".join(str(x) for x in range(11, 21)) + "\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
        elif i == 4:
            raw = "5\n50\n100\n200\n500\n1000\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
        elif i <= 7:
            ns = [random.randint(100, 5000) for _ in range(20)]
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{len(ns)}\n")
                for n in ns: f.write(f"{n}\n")
        else:
            # 高强度：10^5级别
            ns = [100000] * 10 + [99999] * 10 + [100000] * 10
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{len(ns)}\n")
                for n in ns: f.write(f"{n}\n")
        if i >= 2:
            run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")

# ===================== 2025年题目 ====================

def gen_2025_01():
    """判断日期是否合法 - O(1)判断，需要大数据量"""
    d = BASE / "suzhou_2025" / "01_date_valid"
    random.seed(202501)
    for i in range(1, 11):
        if i == 1:
            raw = "5\n2024 2 29\n2023 2 29\n2000 13 1\n1000 1 1\n2025 12 31\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("True\nFalse\nFalse\nTrue\nTrue\n")
        elif i <= 5:
            t = random.randint(1000, 5000)
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{t}\n")
                for _ in range(t):
                    y = random.randint(995, 2030)
                    m = random.randint(-5, 20)
                    day = random.randint(-5, 40)
                    f.write(f"{y} {m} {day}\n")
        else:
            # 高强度：20000个
            t = 20000
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{t}\n")
                for _ in range(t):
                    y = random.randint(995, 2030)
                    m = random.randint(-5, 20)
                    day = random.randint(-5, 40)
                    f.write(f"{y} {m} {day}\n")
            run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")

def gen_2025_02():
    """中位数匹配 - O(n)扫描，需要大数组"""
    d = BASE / "suzhou_2025" / "02_median_match"
    random.seed(202502)
    for i in range(1, 11):
        if i == 1:
            raw = "5 2\n123 456 234 789 12\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("123\n")
        elif i <= 5:
            n = random.randint(1000, 10000)
            target = random.randint(0, 9)
            arr = [random.randint(1, 10**9) for _ in range(n)]
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{n} {target}\n")
                f.write(" ".join(map(str, arr)) + "\n")
        else:
            # 高强度：500000规模
            n = 500000 if i == 10 else random.randint(100000, 300000)
            target = random.randint(0, 9)
            arr = [random.randint(1, 10**9) for _ in range(n)]
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{n} {target}\n")
                f.write(" ".join(map(str, arr)) + "\n")
        run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")

def gen_2025_03():
    """连续数字提取 - O(L)正则，需要长字符串"""
    d = BASE / "suzhou_2025" / "03_number_extract"
    random.seed(202503)
    for i in range(1, 11):
        if i == 1:
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write("abc123def45gh6i789\n10 200\n")
            with open(f"{d}/{i:02d}.out", "w") as f:
                f.write("123 45\n")
        elif i <= 5:
            s = "".join(chr(ord('a')+random.randint(0,25)) + str(random.randint(0, 9999)) for _ in range(random.randint(100, 500)))
            L = random.randint(1, 10000)
            R = L + random.randint(1, 100000)
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{s}\n{L} {R}\n")
        else:
            # 高强度：200000字符的字符串
            length = 200000 if i == 10 else random.randint(50000, 100000)
            s = ""
            while len(s) < length:
                if random.random() < 0.5:
                    s += "".join(chr(ord('a')+random.randint(0,25)) for _ in range(random.randint(1, 10)))
                else:
                    s += str(random.randint(0, 10**9))
            s = s[:length]
            L = random.randint(0, 10**15)
            R = L + random.randint(1, 10**18)
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{s}\n{L} {R}\n")
        run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")

def gen_2025_04():
    """判断质数不含重复数字 - O(√n)判断质数，需要大量大数"""
    d = BASE / "suzhou_2025" / "04_prime_no_repeat"
    random.seed(202504)
    for i in range(1, 11):
        if i == 1:
            raw = "5\n13\n11\n23\n113\n1231\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("True\nFalse\nTrue\nFalse\nFalse\n")
        elif i <= 5:
            t = random.randint(500, 2000)
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{t}\n")
                for _ in range(t):
                    f.write(f"{random.randint(1, 10**9)}\n")
        else:
            # 高强度：10000个接近10^9的大数
            t = 10000
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{t}\n")
                for _ in range(t):
                    # 生成大质数附近的数
                    base = random.randint(10**8, 10**9)
                    f.write(f"{base}\n")
            run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")

def gen_2025_05():
    """回文文件名 - 字符串匹配，需要大量文件名"""
    d = BASE / "suzhou_2025" / "05_palindrome_file"
    random.seed(202505)
    exts = [".txt", ".py", ".doc", ".cpp", ".java", ".html", ".css", ".js", ".pdf", ".png"]
    
    for i in range(1, 11):
        if i == 1:
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write("level.txt hello.py noon.doc noon.txt noon.sys\n.txt\n")
            with open(f"{d}/{i:02d}.out", "w") as f:
                f.write("noon.txt\n")
        elif i <= 5:
            parts = []
            for _ in range(random.randint(50, 200)):
                if random.random() < 0.4:
                    name = "".join(chr(ord('a')+random.randint(0,25)) for _ in range(random.randint(1, 10)))
                else:
                    base = "".join(chr(ord('a')+random.randint(0,25)) for _ in range(random.randint(1, 4)))
                    name = base + base[::-1] if random.random() < 0.5 else base + base[-2::-1] if len(base) > 1 else base
                parts.append(name + random.choice(exts))
            suffix = random.choice(exts)
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(" ".join(parts) + f"\n{suffix}\n")
        else:
            # 高强度：10000个文件名
            parts = []
            for _ in range(10000):
                if random.random() < 0.05:  # 5%概率是回文
                    half = "".join(chr(ord('a')+random.randint(0,25)) for _ in range(random.randint(1, 5)))
                    name = half + half[::-1]
                else:
                    name = "".join(chr(ord('a')+random.randint(0,25)) for _ in range(random.randint(5, 15)))
                parts.append(name + random.choice(exts))
            suffix = random.choice(exts)
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(" ".join(parts) + f"\n{suffix}\n")
        run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")

def gen_2025_09():
    """乘积最大的子数组 - O(n) DP，需要长数组含边界"""
    d = BASE / "suzhou_2025" / "09_max_product"
    random.seed(202509)
    for i in range(1, 11):
        if i == 1:
            raw = "4\n2 3 -2 4\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("6\n")
        elif i == 2:
            raw = "3\n-2 0 -1\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("0\n")
        elif i == 3:
            raw = "1\n-2\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("-2\n")
        elif i <= 7:
            n = random.randint(1000, 10000)
            nums = [random.randint(-10, 10) for _ in range(n)]
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{n}\n")
                f.write(" ".join(map(str, nums)) + "\n")
        else:
            # 高强度：200000长度，全为-10或10交替，卡边界
            n = 200000
            if i == 8:
                nums = [-10] * n
            elif i == 9:
                nums = [10 if j % 2 == 0 else -10 for j in range(n)]
            else:
                nums = [random.choice([-10, 10]) for _ in range(n)]
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{n}\n")
                f.write(" ".join(map(str, nums)) + "\n")
        run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")

def gen_2025_10():
    """募集捐款（打家劫舍）- O(n) DP，需要长数组"""
    d = BASE / "suzhou_2025" / "10_house_robber"
    random.seed(202510)
    for i in range(1, 11):
        if i == 1:
            raw = "4\n1 2 3 1\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("4\n")
        elif i == 2:
            raw = "5\n2 7 9 3 1\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("12\n")
        elif i == 3:
            raw = "1\n5\n"
            with open(f"{d}/{i:02d}.in", "w") as f: f.write(raw)
            with open(f"{d}/{i:02d}.out", "w") as f: f.write("5\n")
        elif i <= 7:
            n = random.randint(1000, 10000)
            nums = [random.randint(0, 10000) for _ in range(n)]
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{n}\n")
                f.write(" ".join(map(str, nums)) + "\n")
        else:
            # 高强度：200000规模
            n = 200000
            if i == 8:
                nums = [10000] * n  # 全最大值
            elif i == 9:
                nums = [10000 if j % 2 == 0 else 0 for j in range(n)]
            else:
                nums = [random.randint(0, 10000) for _ in range(n)]
            with open(f"{d}/{i:02d}.in", "w") as f:
                f.write(f"{n}\n")
                f.write(" ".join(map(str, nums)) + "\n")
        run_std(d, f"{d}/{i:02d}.in", f"{d}/{i:02d}.out")

# ===================== 主函数 ====================

def main():
    print("=" * 60)
    print("苏州大学机试真题 - 测试数据批量生成 v2（增强版）")
    print("=" * 60)
    print("\n生成策略：第8-10组为极限数据，确保暴力解法TLE\n")
    
    # 2024年题目
    print("[2024年题目]")
    print("  01_check_color...    ", end=" "); gen_2024_01(); print("✓ (max n=10000)")
    print("  02_days_diff...      ", end=" "); gen_2024_02(); print("✓ (max span=3000年, 2000cases)")
    print("  03_save_money...     ", end=" "); gen_2024_03(); print("✓ (max n=10^9)")
    print("  05_rotate_image...   ", end=" "); gen_2024_05(); print("✓ (max 500x500)")
    print("  06_is_power_of_two...", end=" "); gen_2024_06(); print("✓ (max 10000 cases)")
    print("  09_perfect_square... ", end=" "); gen_2024_09(); print("✓ (max n=10000, 200cases)")
    print("  10_derangement...    ", end=" "); gen_2024_10(); print("✓ (max n=100000)")
    
    # 2025年题目
    print("\n[2025年题目]")
    print("  01_date_valid...     ", end=" "); gen_2025_01(); print("✓ (max n=20000)")
    print("  02_median_match...   ", end=" "); gen_2025_02(); print("✓ (max n=500000)")
    print("  03_number_extract... ", end=" "); gen_2025_03(); print("✓ (max len=200000)")
    print("  04_prime_no_repeat...", end=" "); gen_2025_04(); print("✓ (max 10000 cases)")
    print("  05_palindrome_file...", end=" "); gen_2025_05(); print("✓ (max 10000 files)")
    print("  09_max_product...    ", end=" "); gen_2025_09(); print("✓ (max n=200000)")
    print("  10_house_robber...   ", end=" "); gen_2025_10(); print("✓ (max n=200000)")
    
    print("\n" + "=" * 60)
    print("全部生成完成！极限测试点汇总：")
    print("  - 日期类：3000年跨度，2000+测试用例")
    print("  - 数值类：n=10^9 级别")
    print("  - 数组类：n=200000~500000")
    print("  - 字符串：长度200000+")
    print("  - 矩阵类：500x500")
    print("=" * 60)

if __name__ == "__main__":
    main()
