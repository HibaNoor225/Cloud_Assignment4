#!/usr/bin/env python3
"""Writes an httperf --wsesslog file with COUNT one-request sessions.

Each session is a POST /api/emi with random valid inputs, so every request
also writes a document to MongoDB.

Usage: python3 scripts/gen_wsesslog.py COUNT OUTPUT_FILE
"""
import random
import sys


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    count, out = int(sys.argv[1]), sys.argv[2]
    with open(out, "w") as f:
        for _ in range(count):
            p = random.randint(50, 5000) * 1000
            r = round(random.uniform(1, 25), 2)
            n = random.randint(6, 360)
            f.write(f'/api/emi method=POST contents="principal={p}&rate={r}&months={n}"\n\n')


if __name__ == "__main__":
    main()
