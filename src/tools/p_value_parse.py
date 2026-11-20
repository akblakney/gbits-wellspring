
#!/usr/bin/env python3

import sys
import numpy as np
from scipy.stats import kstest


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <filename>")
        sys.exit(1)

    filename = sys.argv[1]

    # Read p-values, one per line
    try:
        with open(filename, "r") as f:
            pvalues = np.array([
                float(line.strip())
                for line in f
                if line.strip()
            ])
    except (OSError, ValueError) as e:
        print(f"Error reading p-values: {e}")
        sys.exit(1)

    # Validate p-values
    if len(pvalues) == 0:
        print("Error: No p-values found.")
        sys.exit(1)

    if np.any((pvalues < 0) | (pvalues > 1)):
        print("Error: All p-values must be between 0 and 1.")
        sys.exit(1)

    # Perform one-sample KS test against Uniform(0, 1)
    statistic, pvalue = kstest(pvalues, "uniform")

    print(f"Number of p-values: {len(pvalues)}")
    print(f"KS statistic:       {statistic:.6g}")
    print(f"Uniformity p-value: {pvalue:.6g}")

    alpha = 0.05
    if pvalue < alpha:
        print("Result: Reject uniformity (alpha = 0.05)")
    else:
        print("Result: Cannot reject uniformity (alpha = 0.05)")


if __name__ == "__main__":
    main()
