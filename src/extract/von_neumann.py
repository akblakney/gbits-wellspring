"""Von Neumann randomness extractor for debiasing a bitstream."""

from bitarray import bitarray


class VonNeumannExtractor:
    def __init__(self):
        self.reset_state()

    def reset_state(self):
        self.pairs_processed = 0
        self.pairs_discarded = 0
        self.pairs_output = 0

    def extract(self, bits: bitarray) -> bytearray:

        self.reset_state()
        output_bits = bitarray()

        # Process bits in pairs; ignore a trailing odd bit if present.
        num_pairs = len(bits) // 2
        self.pairs_processed += num_pairs
        for i in range(num_pairs):
            first = bits[2 * i]
            second = bits[2 * i + 1]

            if first == second:
                self.pairs_discarded += 1
                continue  # discard 00 or 11
            elif first == 0 and second == 1:
                self.pairs_output += 1
                output_bits.append(0)
            elif first == 1 and second == 0:
                self.pairs_output += 1
                output_bits.append(1)
            else:
                raise ValueError('invalid bit value {} {}'.format(first, second))

        return self._pack_to_bytearray(output_bits)

    def _pack_to_bytearray(self, bits: bitarray) -> bytearray:
        remainder = len(bits) % 8
        bits = bits[: len(bits) - remainder] if remainder else bits
        return bytearray(bits.tobytes())