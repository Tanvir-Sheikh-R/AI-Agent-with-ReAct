# summation.py
"""
A simple Python script that demonstrates summation.
It provides:
- sum_list(nums): returns the sum of a list of numbers.
- sum_range(n): returns the sum of integers from 1 to n inclusive.
- A command-line interface to sum numbers entered by the user.
"""

def sum_list(nums):
    """Return the sum of the numbers in the iterable `nums`."""
    total = 0
    for n in nums:
        total += n
    return total


def sum_range(n):
    """Return the sum of integers from 1 to n (inclusive)."""
    # Using the arithmetic series formula for efficiency.
    return n * (n + 1) // 2


if __name__ == "__main__":
    import sys
    # If arguments are provided, treat them as numbers to sum.
    if len(sys.argv) > 1:
        try:
            numbers = [float(arg) for arg in sys.argv[1:]]
        except ValueError:
            print("All arguments must be numbers.")
            sys.exit(1)
        print("Sum of arguments:", sum_list(numbers))
    else:
        # Interactive mode: ask user for numbers separated by spaces.
        try:
            line = input("Enter numbers separated by spaces: ")
            numbers = [float(x) for x in line.strip().split()]
            print("Sum:", sum_list(numbers))
        except EOFError:
            pass
        except Exception as e:
            print("Error:", e)
