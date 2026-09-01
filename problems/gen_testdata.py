#!/usr/bin/env python3
"""
苏州大学机试真题 - 测试数据生成器
每道题生成 10 组测试数据 (01.in/01.out ~ 10.in/10.out)
"""
import os
import sys
import math
import random
import subprocess
from pathlib import Path

BASE = Path(__file__).parent

# ============================================================
# 2024年 - 01 判断格子
# ============================================================
def gen_01_check_color(d: Path):
    random.seed(42)
    std = d.parent / "01_check_color" / "std.py"
    for idx in range(1, 11):
        t = random.randint(1, 1000) if idx < 10 else 5000
        with open(f"{d}/01_check_color/{idx:02d}.in", "w") as f:
            f.write(f"{t}\n")
            for _ in range(t):
                col = random.randint(1, 8)
                row = random.randint(1, 8)
                f.write(f"{chr(ord('a')+col-1)}{row}\n")
        run_std(std, f"{d}/01_check_color/{idx:02d}.in", f"{d}/01_check_color/{idx:02d}.out")

# ============================================================
# 2024年 - 02 相差几天
# ============================================================
def gen_02_days_diff(d: Path):
    random.seed(123)
    std = d.parent / "02_days_diff" / "std.py"
    is_leap = lambda y: (y%4==0 and y%100!=0) or (y%400==0)
    dim = [0,31,28,31,30,31,30,31,31,30,31,30,31]
    
    for idx in range(1, 11):
        cases = []
        if idx == 1:
            # 样例
            cases = [(2000,1,1,2000,3,1,60), (1999,2,29,1999,3,1,-1), (2000,1,1,2024,1,1,8766)]
        elif idx == 2:
            # 边界
            cases = [(1,1,1,1,12,31,364), (2024,1,1,2024,1,1,0), (2024,1,1,2024,1,2,1),
                     (2024,2,28,2024,3,1,1), (2000,2,28,2000,3,1,1)]
        elif idx == 3:
            # 非法日期
            cases = [(2024,13,1,2024,1,1,-1), (2024,0,1,2024,2,1,-1),
                     (2024,2,30,2024,3,1,-1), (2024,4,31,2024,5,1,-1)]
        elif idx == 4:
            # 大跨度
            cases = [(1,1,1,3000,12,31,1096129), (2024,1,1,2024,12,31,365),
                     (1900,3,1,1900,3,2,1)]
        elif idx == 5:
            cases = [(2020,1,1,2024,1,1,1461), (2100,2,28,2100,3,1,1)]
        else:
            # 随机数据
            t = 50
            # 混合合法和非法
            for _ in range(t):
                y1 = random.randint(1, 3000)
                m1 = random.randint(1, 12)
                maxd1 = dim[12] if is_leap(y1) and m1==2 else dim[m1]
                if is_leap(y1) and m1==2: maxd1 = 29
                else: maxd1 = dim[m1]
                d1 = random.randint(1, maxd1+2)
                y2 = random.randint(y1, 3000)
                m2 = random.randint(1, 12)
                if is_leap(y2) and m2==2: maxd2 = 29
                else: maxd2 = dim[m2]
                d2 = random.randint(1, maxd2+2)
                cases.append((y1,m1,d1,y2,m2,d2,0)) # placeholder
        
        with open(f"{d}/02_days_diff/{idx:02d}.in", "w") as f:
            f.write(f"{len(cases)}\n")
            for c in cases:
                f.write(f"{c[0]} {c[1]} {c[2]} {c[3]} {c[4]} {c[5]}\n")
        run_std(std, f"{d}/02_days_diff/{idx:02d}.in", f"{d}/02_days_diff/{idx:02d}.out")
        
        # 前5个是手工设定的，需要手动修正out
        if idx <= 5:
            outs = [str(c[6]) for c in cases]
            with open(f"{d}/02_days_diff/{idx:02d}.out", "w") as f:
                f.write("\n".join(outs) + "\n")

# ============================================================
# 2024年 - 03 存钱
# ============================================================
def gen_03_save_money(d: Path):
    random.seed(456)
    std = d.parent / "03_save_money" / "std.py"
    for idx in range(1, 11):
        if idx == 1:
            ns = [4, 6, 365]
        elif idx == 2:
            ns = [1, 2, 3, 7, 10]
        elif idx == 3:
            ns = [100, 1000, 10000, 100000]
        elif idx == 4:
            ns = [10000000, 100000000, 1000000000]
        elif idx == 5:
            ns = [14, 55]
        else:
            ns = [random.randint(1, 10**9) for _ in range(20)]
        with open(f"{d}/03_save_money/{idx:02d}.in", "w") as f:
            f.write(f"{len(ns)}\n")
            for n in ns:
                f.write(f"{n}\n")
        run_std(std, f"{d}/03_save_money/{idx:02d}.in", f"{d}/03_save_money/{idx:02d}.out")

# ============================================================
# 2024年 - 05 旋转图像
# ============================================================
def gen_05_rotate_image(d: Path):
    random.seed(789)
    std = d.parent / "05_rotate_image" / "std.py"
    flags = [-1, 2, 1, 5]
    for idx in range(1, 11):
        cases = []
        if idx == 1:
            cases = [(-1, 3, 3, [[1,2,3],[4,5,6],[7,8,9]]),
                     (1, 3, 3, [[1,2,3],[4,5,6],[7,8,9]]),
                     (2, 3, 3, [[1,2,3],[4,5,6],[7,8,9]]),
                     (5, 3, 3, [[1,2,3],[4,5,6],[7,8,9]])]
        elif idx == 2:
            cases = [(-1, 1, 1, [[7]]),
                     (2, 1, 1, [[7]]),
                     (1, 2, 2, [[1,2],[3,4]]),
                     (-1, 2, 2, [[1,2],[3,4]])]
        elif idx == 3:
            # 非方阵
            cases = [(-1, 2, 3, [[1,2,3],[4,5,6]]),
                     (1, 2, 3, [[1,2,3],[4,5,6]]),
                     (2, 2, 3, [[1,2,3],[4,5,6]])]
        elif idx == 4:
            cases = [(-1, 3, 2, [[1,2],[3,4],[5,6]]),
                     (1, 3, 2, [[1,2],[3,4],[5,6]])]
        else:
            flag = flags[idx % 4]
            rows = random.randint(1, 50)
            cols = random.randint(1, 50)
            mat = [[random.randint(-100, 100) for _ in range(cols)] for _ in range(rows)]
            cases = [(flag, rows, cols, mat)]
        
        with open(f"{d}/05_rotate_image/{idx:02d}.in", "w") as f:
            f.write(f"{len(cases)}\n")
            for flag, rows, cols, mat in cases:
                f.write(f"{flag}\n")
                f.write(f"{rows} {cols}\n")
                for row in mat:
                    f.write(" ".join(map(str, row)) + "\n")
        run_std(std, f"{d}/05_rotate_image/{idx:02d}.in", f"{d}/05_rotate_image/{idx:02d}.out")

# ============================================================
# 2024年 - 06 判断2的幂
# ============================================================
def gen_06_is_power_of_two(d: Path):
    random.seed(101)
    std = d.parent / "06_is_power_of_two" / "std.py"
    for idx in range(1, 11):
        if idx == 1:
            ns = [1, 2, 3, 4, 16, 1024, 1073741824, 0]
        elif idx == 2:
            ns = [2**i for i in range(0, 32)]
        elif idx == 3:
            ns = [2**i - 1 for i in range(1, 32)]
        elif idx == 4:
            ns = [2**i + 1 for i in range(1, 31)]
        elif idx == 5:
            ns = [0, 1, 2**32-1, 2**31]
        else:
            ns = [random.randint(0, 2**32-1) for _ in range(100)]
        
        with open(f"{d}/06_is_power_of_two/{idx:02d}.in", "w") as f:
            f.write(f"{len(ns)}\n")
            for n in ns:
                f.write(f"{n}\n")
        run_std(std, f"{d}/06_is_power_of_two/{idx:02d}.in", f"{d}/06_is_power_of_two/{idx:02d}.out")

# ============================================================
# 2024年 - 09 完全平方数 (力扣279)
# ============================================================
def gen_09_perfect_square(d: Path):
    random.seed(202)
    std = d.parent / "09_perfect_square" / "std.py"
    for idx in range(1, 11):
        if idx == 1:
            ns = [12, 13, 1, 4, 9999]
        elif idx == 2:
            ns = [2, 3, 5, 6, 7, 8, 10, 11]
        elif idx == 3:
            ns = [i*i for i in range(1, 101)]
        elif idx == 4:
            ns = [i*i - 1 for i in range(2, 51)]
        elif idx == 5:
            ns = [10000, 99999, 50000]
        else:
            ns = [random.randint(1, 10000) for _ in range(50)]
        
        with open(f"{d}/09_perfect_square/{idx:02d}.in", "w") as f:
            f.write(f"{len(ns)}\n")
            for n in ns:
                f.write(f"{n}\n")
        run_std(std, f"{d}/09_perfect_square/{idx:02d}.in", f"{d}/09_perfect_square/{idx:02d}.out")

# ============================================================
# 2024年 - 10 错位排列
# ============================================================
def gen_10_derangement(d: Path):
    random.seed(303)
    std = d.parent / "10_derangement" / "std.py"
    for idx in range(1, 11):
        if idx == 1:
            ns = [1, 2, 3, 4, 5]
        elif idx == 2:
            ns = [6, 7, 8, 9, 10]
        elif idx == 3:
            ns = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
        elif idx == 4:
            ns = [50, 100, 200, 500, 1000]
        elif idx == 5:
            ns = [10000, 50000, 100000]
        else:
            ns = [random.randint(1, 100000) for _ in range(20)]
        
        with open(f"{d}/10_derangement/{idx:02d}.in", "w") as f:
            f.write(f"{len(ns)}\n")
            for n in ns:
                f.write(f"{n}\n")
        run_std(std, f"{d}/10_derangement/{idx:02d}.in", f"{d}/10_derangement/{idx:02d}.out")

# ============================================================
# 工具函数
# ============================================================
def run_std(std_script, in_file, out_file):
    """运行标准程序生成输出"""
    result = subprocess.run(
        [sys.executable, str(std_script)],
        stdin=open(in_file, "r"),
        capture_output=True,
        text=True,
        timeout=60
    )
    with open(out_file, "w") as f:
        f.write(result.stdout)

def main():
    d = BASE / "suzhou_2024" / "testdata_backup"
    # 实际测试数据在各自目录下
    d = BASE
    
    print("Generating test data for 2024 problems...")
    gen_01_check_color(d)
    gen_02_days_diff(d)
    gen_03_save_money(d)
    gen_05_rotate_image(d)
    gen_06_is_power_of_two(d)
    gen_09_perfect_square(d)
    gen_10_derangement(d)
    print("Done!")

if __name__ == "__main__":
    main()
