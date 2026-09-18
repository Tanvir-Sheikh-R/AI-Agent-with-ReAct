# summation.py
"""
A simple Python script that demonstrates summation.
It provides:
- sum_numbers(iterable): returns the sum of the elements.
- A command‑line interface that reads space‑separated numbers and prints their sum.
"""

def sum_numbers(iterable):
    """Return the sum of the numbers in *iterable*.
    Works with any iterable of numeric types.
    """
    total = 0
    for num in iterable:
        total += num
    return total

if __name__ == "__main__":
    import sys
    # If numbers are passed as command‑line arguments, use them.
    # Otherwise, read a line from stdin.
    if len(sys.argv) > 1:
        # Convert arguments to floats (or ints if possible)
        try:
            numbers = [int(arg) for arg in sys.argv[1:]]
        except ValueError:
            numbers = [float(arg) for arg in sys.argv[1:]]
    else:
        line = sys.stdin.read().strip()
        if not line:
            print("Usage: python summation.py 1 2 3   or   echo '1 2 3' | python summation.py")
            sys.exit(0)
        parts = line.split()
        try:
            numbers = [int(p) for p in parts]
        except ValueError:
            numbers = [float(p) for p in parts]
    print(sum_numbers(numbers))
