# gbits

## Install

`sudo apt install python3-uvicorn python3-numpy python3-scipy python3-pyaudio python3-bitarray python3-fastapi python3-matplotlib`

`sudo apt install alsa-utils`

## audio hardware config stuff

Use `src/tools/audio_devices_test.py` to see pyaudio's list of devices with index.

To see info about current device in use, 

`cat /proc/asound/card1/pcm0c/sub0/hw_params`

To play raw audio files generated, use 

`ffplay -f s16le -ar 48000 audio.raw`

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

improved sts command:

`sts -s -i <bitstreams> -w . -F r data.bin`

### dieharder
Run dieharadser with all tests and verbose output:
`dieharder -D 98302 -a -g 201 -f data.bin > report.txt`

Run dieharder with specific test and param (see all tests with -l):
`dieharder -D 98302 -g 201 -d 203 -n 2 -f`

Then can get brief assessment from this with:
`grep 'PASS\|Assess\|FAIL\|WEAK' report.txt`

test descriptions

`dieharder -a -h`

### practrand

`cat ~/gbits-testing/all.bin | ./RNG_test stdin -tlmax 1000M`

## fun

LC_ALL=C tr -cd '[:print:]' < 01.bin