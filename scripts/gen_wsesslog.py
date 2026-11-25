#!/usr/bin/env python3
"""Writes an httperf --wsesslog file with COUNT sessions of BURSTS requests each.

Every request is a POST /api/emi with random valid inputs, so every request also
writes a document to MongoDB. Requests of one session share one persistent
connection, which keeps the number of new connections per second low.

Usage: python3 scripts/gen_wsesslog.py COUNT OUTPUT_FILE [BURSTS]
"""
import random
import sys


def main():
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    count, out = int(sys.argv[1]), sys.argv[2]
    bursts = int(sys.argv[3]) if len(sys.argv) == 4 else 1
    with open(out, "w") as f:
        for _ in range(count):
            for _ in range(bursts):
                p = random.randint(50, 5000) * 1000
                r = round(random.uniform(1, 25), 2)
                n = random.randint(6, 360)
                f.write(f'/api/emi method=POST contents="principal={p}&rate={r}&months={n}"\n')
            f.write("\n")


if __name__ == "__main__":
    main()
