import sys

for line in sys.stdin:
    print(line.rstrip()[::-1])
