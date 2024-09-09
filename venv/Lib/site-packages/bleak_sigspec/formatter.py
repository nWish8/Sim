"""
Utils to work with binary data or bytes
 """

import struct
from binascii import hexlify


class FormatIncompleteError(Exception):
    def __init__(self, *args):
        if args:
            self.message = args[0]
        else:
            self.message = None

    def __str__(self):
        if self.message:
            return 'FormatIncompleteError, {0} '.format(self.message)
        else:
            return 'FormatIncompleteError has been raised'


def encode_FLOAT_ieee11073(value, precision=1, debug=False):
    """
    Binary representation of float value as IEEE-11073:20601 32-bit FLOAT

    FLOAT-Type is defined as a 32-bit value with a 24-bit mantissa and an 8-bit exponent.

    - https://community.hiveeyes.org/t/implementing-ble-gatt-ess-characteristics-with-micropython/2413/3
    """
    assert abs(value * (10 ** precision)) <= 2**23, 'Mantissa too big'
    encoded = int(value * (10 ** precision)).to_bytes(3, 'little',
                                                      signed=True) + struct.pack('<b', -precision)
    if debug:
        hxval = hexlify(encoded)
        stbytes = hxval.decode()[::-1]
        print('0x'+''.join([stbytes[i-2:i][::-1]
                            for i in range(2, len(stbytes)+2, 2)]))
    return encoded


def decode_FLOAT_ieee11073(value):
    """Defined in ISO/IEEE Std. 11073-20601TM-2008:

    FLOAT-Type is defined as a 32-bit value with a 24-bit mantissa and an 8-bit exponent.

    Special Values:
        * +INFINITY : [exponent 0, mantissa +(2^23 –2) → 0x007FFFFE]

        * NaN *(Not a Number)*: [exponent 0, mantissa +(2^23 –1) → 0x007FFFFF]

        * NRes *(Not at this Resolution)*: [exponent 0, mantissa –(2^23) → 0x00800000]

        * Reserved for future use : [exponent 0, mantissa –(2^23–1) → 0x00800001]

        * – INFINITY : [exponent 0, mantissa –(2^23 –2) → 0x00800002]
    """
    special_values = {2**23-2: '+INFINITY', 2**23-1: 'NaN',  -2**23: 'NRes',
                      -(2**23-1): 'Reserved for future use',
                      -(2**23-2): '–INFINITY'}
    # UNPACK SIGN, EXPONENT
    sign, exponent = struct.unpack('4b', value)[-2:]
    # SEPARATE EXPONENT AND MANTISSA
    if sign >= 0:
        # PAD MANTISSA TO BE 32 bit Int
        _mantissa_bytes = bytes(value[:-1]) + b'\x00'
    else:
        # PAD MANTISSA TO BE 32 bit Int
        _mantissa_bytes = bytes(value[:-1]) + b'\xff'

    # UNPACK MANTISSA
    mantissa, = struct.unpack('i', _mantissa_bytes)

    # COMPUTE
    # CHECK IF SPECIAL VALUE
    if exponent == 0:
        if mantissa in special_values:
            return special_values[mantissa]

    float_val = mantissa / (1 / (10**exponent))
    return float_val


def twos_comp(val, bits):
    """returns the 2's complement of int value val with n bits

    - https://stackoverflow.com/questions/1604464/twos-complement-in-python"""

    if (val & (1 << (bits - 1))) != 0:  # if sign bit is set e.g., 8bit: 128-255
        val = val - (1 << bits)        # compute negative value
    return val & ((2 ** bits) - 1)     # return positive value as is


def encode_SFLOAT_ieee11073(value, precision=1, debug=False):
    """
    Binary representation of float value as  ISO/IEEE Std. 11073-20601TM-2008: 16-Bit FLOAT

    The SFLOAT-Type is defined as a 16-bit value with 12-bit mantissa and 4-bit exponent
    """
    val = int(value * (10 ** precision))
    assert abs(val) <= 2**11, 'Mantissa too big'
    encoded = ((-precision << 12) + twos_comp(val, 12)
               ).to_bytes(2, 'little', signed=True)
    if debug:
        hxval = hexlify(encoded)
        stbytes = hxval.decode()[::-1]
        print('0x'+''.join([stbytes[i-2:i][::-1]
                            for i in range(2, len(stbytes)+2, 2)]))
    return encoded


def twos_comp_dec(val, bits):
    """returns the signed int value from the 2's complement val with n bits

    - https://stackoverflow.com/questions/1604464/twos-complement-in-python"""

    if (val & (1 << (bits - 1))) != 0:  # if sign bit is set e.g., 8bit: 128-255
        val = val - (1 << bits)        # compute negative value
    return val


def decode_SFLOAT_ieee11073(value):
    """Defined in ISO/IEEE Std. 11073-20601TM-2008:

    SFLOAT-Type is defined as a 16-bit value with 12-bit mantissa and 4-bit exponent.
    The 16–bit value contains a 4-bit exponent to base 10, followed by a 12-bit mantissa.
    Each is in twos- complement form.

    Special Values:
        * +INFINITY : [exponent 0, mantissa +(2^11 –2) → 0x07FE]

        * NaN *(Not a Number)*: [exponent 0, mantissa +(2^11 –1) → 0x07FF]

        * NRes *(Not at this Resolution)*: [exponent 0, mantissa –(2^11) → 0x0800]

        * Reserved for future use: [exponent 0, mantissa –(2^11 –1) → 0x0801]

        * – INFINITY : [exponent 0, mantissa –(2^11 –2) → 0x0802]
    """
    special_values = {2**11-2: '+INFINITY', 2**11-1: 'NaN',  -2**11: 'NRes', -
                      (2**11-1): 'Reserved for future use', -(2**11-2): '–INFINITY'}
    # UNPACK SIGN, EXPONENT
    _bitmask_mant = eval(
        "0b{}".format("0" * (16 - (0 + 12)) + (12 * "1") + "0" * 0)
    )
    dec = (value[1] << 8) + value[0]
    _exponent = dec >> 12
    exponent = twos_comp_dec(_exponent, 4)
    _mantissa_uint = (dec & _bitmask_mant) >> 0
    mantissa = twos_comp_dec(_mantissa_uint, 12)

    # COMPUTE
    # CHECK IF SPECIAL VALUE
    if exponent == 0:
        if mantissa in special_values:
            return special_values[mantissa]

    float_val = mantissa / (1 / (10**exponent))
    return float_val


def encode_nibbles(val, val2):
    """Encode two values as two nibbles in a byte

    Specs:
        * **Nibble**:   MSN  LSN

        * **Byte**:   0b0000 0000

        * **Indexes**:  7654 3210

        * **Values**:   val2 val

    Requirement:
        * Only values (0-15) allowed
    """
    assert any([v > 2**4 - 1 for v in [val, val2]]) is False, 'Nibble value too big, only values (0-15) allowed'

    # shift 4 bits to the left
    fullbyte = (val2 << 4) + val
    return struct.pack('B', fullbyte)


def decode_nibbles(bb):
    """Decode 1 byte as two nibbles (ints)

    Specs:
        **bb_len** : 1

        **returns**: (int, int)
    """
    fullbyte, = struct.unpack('B', bb)
    # shift 4 bits to the right
    val2 = fullbyte >> 4
    # Mask 4 bits on the left
    val = fullbyte & 0b1111
    return(val, val2)


def encode_2_uint12(val, val2):
    """
    Format two values as two unsigned 12 bit integers

    Specs:
        **2_uint12 len**: 3 bytes

        **Format string**: 'o'
    """
    full3bytes = (val << 12) + val2
    return full3bytes.to_bytes(3, 'little', signed=False)


def decode_2_uint12(bb):
    """
    Decode 3 bytes as two unsigned 12 bit integers

    Specs:
        **2_uint12 len**: 3 bytes

        **Format string**: 'o'

    """
    _bb_int = int.from_bytes(bb, byteorder='little', signed=False)
    val = _bb_int >> 12
    val2 = _bb_int & 0b111111111111  # 2**12-1
    return (val, val2)


def encode_uint24(val):
    """
    Format a value as a unsigned 24 bit integer

    Specs:
        * **uint24 len**: 3 bytes

        * **Format string**: 'k'
    """
    return val.to_bytes(3, 'little', signed=False)


def decode_uint24(bb):
    """
    Decode 3 bytes as a unsigned 24 bit integer

    Specs:
        * **uint24 len**: 3 bytes

        * **Format string**: 'k'
    """
    return int.from_bytes(bb, byteorder='little', signed=False)


def encode_sint24(val):
    """
    Format a value as a signed 24 bit integer

    Specs:
        * **sint24 len**: 3 bytes

        * **Format string**: 'K'
    """
    return val.to_bytes(3, 'little', signed=True)


def decode_sint24(bb):
    """
    Decode 3 bytes as a signed 24 bit integer

    Specs:
        * **sint24 len**: 3 bytes

        * **Format string**: 'K'
    """
    return int.from_bytes(bb, byteorder='little', signed=True)


def encode_uint40(val):
    """
    Format a value as an unsigned 40 bit integer

    Specs:
        * **uint40 len**: 5 bytes

        * **Format string**: 'j'
    """
    return val.to_bytes(5, 'little', signed=False)


def decode_uint40(bb):
    """
    Decode 5 bytes as an unsigned 40 bit integer

    Specs:
        * **uint40 len**: 5 bytes

        * **Format string**: 'j'
    """
    return int.from_bytes(bb, byteorder='little')


def encode_uint48(val):
    """
    Format a value as an unsigned 48 bit integer

    Specs:
        * **uint48 len**: 6 bytes

        * **Format string**: 'J'
    """
    return val.to_bytes(6, 'little', signed=False)


def decode_uint48(bb):
    """
    Decode 6 bytes as an unsigned 48 bit integer

    Specs:
        * **uint48 len**: 6 bytes

        * **Format string**: 'J'
    """
    return int.from_bytes(bb, byteorder='little', signed=False)


def encode_uint128(val):
    """
    Format a value as a unsigned 128 bit integer

    Specs:
        * **uint128 len**: 16 bytes

        * **Format string**: 'z'
    """
    return val.to_bytes(16, 'little', signed=False)


def decode_uint128(bb):
    """
    Decode 16 bytes as a unsigned 128 bit integer

    Specs:
        * **uint128 len**: 16 bytes

        * **Format string**: 'z'
    """
    return int.from_bytes(bb, byteorder='little', signed=False)


class SuperStruct:
    """
    Struct class Bluetooth SIG compliant
    """

    def __init__(self):
        self._version = 'Struct class Bluetooth SIG compliant'
        self.spec_formats = ['F', 'S', 'Y', 'j', 'J', 'k', 'K', 'z', 'o']
        self.len_F = 4  # bytes # 8 bit * 4 --> (32 bit)
        self.len_SF = 2  # bytes # 8 bit * 2 --> (16 bit)
        self.len_nibble = 1/2  # bytes 8 bit * 1/2 --> (4 bit)
        self.len_uint12 = 1 + (1/2)  # bytes 8 bit * 3/2 --> (12 bit)
        self.len_uint24 = 3  # bytes # 8 bit * 3 --> (24 bit)
        self.len_sint24 = 3  # bytes # 8 bit * 3 --> (24 bit)
        self.len_uint40 = 5  # bytes # 8 bit * 5 --> (40 bit)
        self.len_uint48 = 6  # bytes # 8 bit * 6 --> (48 bit)
        self.len_uint128 = 16  # bytes # 8 bit * 16 --> (128 bit)

    def __repr__(self):
        return(self._version)

    def unpack(self, fmt, bb):
        """
        Unpack values from bytes(bb) following the specified format (fmt)
        """
        if any([f in self.spec_formats for f in fmt]):
            values, index = self._get_all_index_bytes(fmt, bb)
            return tuple(values)

        else:
            return struct.unpack(fmt, bb)

    def pack(self, fmt, *args):
        """
        Pack values (*args*) into bytes following the specified format (fmt)
        """
        if fmt != 'utf8':
            assert len(fmt) == len([*args]), 'pack expected {} items for packing (got {})'.format(len(fmt), len([*args]))
            if any([f in self.spec_formats for f in fmt]):
                # values, index = self._get_all_index_bytes(fmt, *args)
                # return tuple(values)
                return self._put_all_index_bytes(fmt, *args)

            else:
                return struct.pack(fmt, *args)
        else:
            data = [*args][0]
            return data.encode('utf8')

    def _get_all_index_bytes(self, fmt_string, bb):
        indexes = []
        intermediate_fmt_string = ""
        intermediate_nibble_fmt_string = ""
        intermediate_uint12_fmt_string = ""
        values = []
        index = 0
        expected_size = self._get_overall_size(fmt_string)
        assert len(bb) == expected_size, 'unpack requires a buffer of {} bytes'.format(
            expected_size)
        for s in fmt_string:
            if s in self.spec_formats:
                if intermediate_fmt_string:
                    val = struct.unpack(
                        intermediate_fmt_string, bb[index:index+struct.calcsize(intermediate_fmt_string)])
                    for v in val:
                        values.append(v)
                    index += struct.calcsize(intermediate_fmt_string)
                indexes.append(index)
                if s == 'F':
                    val_F = decode_FLOAT_ieee11073(bb[index:index+self.len_F])
                    values.append(val_F)
                    index += self.len_F

                elif s == 'S':
                    val_S = decode_SFLOAT_ieee11073(
                        bb[index:index+self.len_SF])
                    values.append(val_S)
                    index += self.len_SF

                elif s == 'Y':
                    if intermediate_nibble_fmt_string == "":
                        intermediate_nibble_fmt_string += s
                    elif intermediate_nibble_fmt_string == 'Y':
                        val, val2 = decode_nibbles(
                            bb[index:index+int(self.len_nibble*2)])
                        values.append(val)
                        values.append(val2)
                        index += int(self.len_nibble*2)
                        intermediate_nibble_fmt_string = ""

                elif s == 'o':
                    if intermediate_uint12_fmt_string == "":
                        intermediate_uint12_fmt_string += s
                    elif intermediate_uint12_fmt_string == 'o':
                        val, val2 = decode_2_uint12(
                            bb[index:index+int(self.len_uint12*2)])
                        values.append(val)
                        values.append(val2)
                        index += int(self.len_uint12*2)
                        intermediate_uint12_fmt_string = ""

                elif s == 'k':
                    val_uint24 = decode_uint24(bb[index:index+self.len_uint24])
                    values.append(val_uint24)
                    index += self.len_uint24

                elif s == 'K':
                    val_sint24 = decode_sint24(bb[index:index+self.len_sint24])
                    values.append(val_sint24)
                    index += self.len_sint24

                elif s == 'j':
                    val_uint40 = decode_uint40(bb[index:index+self.len_uint40])
                    values.append(val_uint40)
                    index += self.len_uint40

                elif s == 'J':
                    val_uint48 = decode_uint48(bb[index:index+self.len_uint48])
                    values.append(val_uint48)
                    index += self.len_uint48
                elif s == 'z':
                    val_uint128 = decode_uint128(
                        bb[index:index+self.len_uint128])
                    values.append(val_uint128)
                    index += self.len_uint128

                intermediate_fmt_string = ""
            else:
                intermediate_fmt_string += s

        if intermediate_fmt_string:
            val = struct.unpack(
                intermediate_fmt_string, bb[index:index+struct.calcsize(intermediate_fmt_string)])
            for v in val:
                values.append(v)

        return (values, indexes)

    def _put_all_index_bytes(self, fmt_string, *args):
        expected_size = self.calcsize(fmt_string)
        indexes = []
        intermediate_fmt_string = ""
        intermediate_values = []
        intermediate_nibble_fmt_string = ""
        intermediate_nibble_values = []
        intermediate_uint12_fmt_string = ""
        intermediate_uint12_values = []
        values = [*args]
        bb = b''
        index = 0
        for s in fmt_string:
            if s in self.spec_formats:
                if intermediate_fmt_string:
                    val = struct.pack(
                        intermediate_fmt_string, *intermediate_values)
                    bb += val
                    intermediate_fmt_string = ""
                    intermediate_values = []
                if s == 'F':
                    _precision = 0
                    if '.' in str(values[index]):
                        _precision = len(str(values[index]).split('.')[-1])
                    val_F = encode_FLOAT_ieee11073(values[index],
                                                   precision=_precision)
                    bb += val_F

                elif s == 'S':
                    _precision = 0
                    if '.' in str(values[index]):
                        _precision = len(str(values[index]).split('.')[-1])
                    val_S = encode_SFLOAT_ieee11073(values[index],
                                                   precision=_precision)
                    bb += val_S

                elif s == 'Y':
                    if intermediate_nibble_fmt_string == "":
                        intermediate_nibble_fmt_string += s
                        intermediate_nibble_values.append(values[index])
                    elif intermediate_nibble_fmt_string == 'Y':
                        intermediate_nibble_values.append(values[index])
                        val_nibbles = encode_nibbles(*intermediate_nibble_values)
                        bb += val_nibbles
                        intermediate_nibble_fmt_string = ""
                        intermediate_nibble_values = []

                elif s == 'o':
                    if intermediate_uint12_fmt_string == "":
                        intermediate_uint12_fmt_string += s
                        intermediate_uint12_values.append(values[index])
                    elif intermediate_uint12_fmt_string == 'o':
                        intermediate_uint12_values.append(values[index])
                        val_2_uint12 = encode_2_uint12(*intermediate_uint12_values)
                        bb += val_2_uint12
                        intermediate_uint12_fmt_string = ""
                        intermediate_uint12_values = []

                elif s == 'k':
                    val_uint24 = encode_uint24(values[index])
                    bb += val_uint24

                elif s == 'K':
                    val_sint24 = encode_sint24(values[index])
                    bb += val_sint24

                elif s == 'j':
                    val_uint40 = encode_uint40(values[index])
                    bb += val_uint40

                elif s == 'J':
                    val_uint48 = encode_uint48(values[index])
                    bb += val_uint48
                elif s == 'z':
                    val_uint128 = encode_uint128(values[index])
                    bb += val_uint128

                index += 1
            else:
                intermediate_fmt_string += s
                intermediate_values.append(values[index])
                index += 1

        if intermediate_fmt_string:
            val = struct.pack(
                intermediate_fmt_string, *intermediate_values)
            bb += val

        return bb

    def _get_overall_size(self, fmt_string):
        intermediate_fmt_string = ""
        size_value = 0
        is_nibble_now = False
        is_uint12_now = False
        index = 0
        for s in fmt_string:
            if is_nibble_now and s != 'Y':
                raise FormatIncompleteError("'Y' format (nibble) must come in pairs")
            if is_uint12_now and s != 'o':
                raise FormatIncompleteError("'o' format (uint12) must come in pairs")

            if s in self.spec_formats:
                if intermediate_fmt_string:
                    size_value += struct.calcsize(intermediate_fmt_string)
                    index += struct.calcsize(intermediate_fmt_string)
                if s == 'F':
                    size_value += self.len_F
                elif s == 'S':
                    size_value += self.len_SF
                elif s == 'Y':
                    is_nibble_now = not is_nibble_now
                    size_value += self.len_nibble
                elif s == 'o':
                    is_uint12_now = not is_uint12_now
                    size_value += self.len_uint12
                elif s == 'k':
                    size_value += self.len_uint24
                elif s == 'K':
                    size_value += self.len_sint24
                elif s == 'j':
                    size_value += self.len_uint40
                elif s == 'J':
                    size_value += self.len_uint48
                elif s == 'z':
                    size_value += self.len_uint128
                intermediate_fmt_string = ""
            else:
                intermediate_fmt_string += s

        if intermediate_fmt_string:
            size_value += struct.calcsize(intermediate_fmt_string)

        return int(size_value)

    def calcsize(self, fmt):
        """
        Return the size in bytes of a string format, same as ``struct.calcsize``
        """
        return self._get_overall_size(fmt)
