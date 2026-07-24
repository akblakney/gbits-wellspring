# gbits

## API requests
- run: `python3 main.py`
- `http://127.0.0.1:8000/bits?num_bytes=10&plot=False`
- `http://127.0.0.1:8000/health`


## Statistical testing
For the NIST test suite, and for 100 bitstreams, the probability of "failure" (95/100 streams pass at the 0.01 level) is about 0.00343. Then for 188 individual tests performed, the probability distribution of failure counts under the assumption of random data is as follows:

`{0: 0.5240227, 1: 0.339039, 2: 0.1093585, 3: 0.0233439, 4: 0.0037083, 5: 0.0004743, 6: 4.91e-05, 7: 3.7e-06, 8: 5e-07}`

(These are not exact values; I quickly ran a monte carlo simulation to get these values to use as a sanity check.)

For 200 bitstreams, the probability distribution of failure counts (minimum 193/200 to pass) is:

`{0: 0.8284568, 1: 0.1559774, 2: 0.0146169, 3: 0.0009051, 4: 4.26e-05, 5: 1.1e-06, 6: 1e-07}`
