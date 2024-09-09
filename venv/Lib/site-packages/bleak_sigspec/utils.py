"""
Utils to decode binary data from SIG Characteristics
"""

import struct
import xml.etree.ElementTree as ET
import traceback
import os
from typing import Union
from bleak.uuids import uuidstr_to_str
from bleak_sigspec.formatter import SuperStruct
from bleak.backends.characteristic import BleakGATTCharacteristic
import bleak_sigspec
import textwrap


CHARS_XML_DIR = os.path.join(bleak_sigspec.__path__[0],
                             "characteristics_xml")


# Struct IEEE-11073 compliant
sup_struct = SuperStruct()

# UNITS
CHARS_UNITS = {
    "meter": "m",
    "kilogram": "kg",
    "second": "s",
    "ampere": "A",
    "kelvin": "K",
    "mole": "mol",
    "candela": "cd",
    "square meter": "m2",
    "cubic meter": "m3",
    "meter per second": "m/s",
    "metres per second": "m/s",
    "meter per second squared  ": "m/s2",
    "reciprocal meter": "m-1",
    "kilogram per cubic meter": "kg/m3",
    "cubic meter per kilogram": "m3/kg",
    "ampere per square meter": "A/m2",
    "ampere per meter": "A/m",
    "mole per cubic meter": "mol/m3",
    "candela per square meter": "cd/m2",
    "kilogram per kilogram": "kg/kg",
    "radian": "rad",
    "steradian": "sr",
    "hertz": "Hz",
    "newton": "N",
    "pascal": "Pa",
    "joule": "J",
    "watt": "W",
    "coulomb": "C",
    "volt": "V",
    "farad": "F",
    "ohm": "Ω",
    "siemens": "S",
    "weber": "Wb",
    "tesla": "T",
    "henry": "H",
    "degree celsius": "°C",
    "lumen": "lm",
    "lux": "lx",
    "becquerel": "Bq",
    "gray": "Gy",
    "sievert": "Sv",
    "katal": "kat",
    "pascal second": "Pa·s",
    "newton meter": "N·m",
    "newton per meter": "N/m",
    "radian per second": "rad/s",
    "radian per second squared": "rad/s2",
    "watt per square meter": "W/m2",
    "joule per kelvin": "J/K",
    "joule per kilogram kelvin": "J/(kg·K)",
    "joule per kilogram": "J/kg",
    "watt per meter kelvin": "W/(m·K)",
    "joule per cubic meter": "J/m3",
    "volt per meter": "V/m",
    "coulomb per cubic meter": "C/m3",
    "coulomb per square meter": "C/m2",
    "farad per meter": "F/m",
    "henry per meter": "H/m",
    "joule per mole": "J/mol",
    "joule per mole kelvin": "J/(mol·K)",
    "coulomb per kilogram": "C/kg",
    "gray per second": "Gy/s",
    "watt per steradian": "W/sr",
    "watt per square meter steradian": "W/(m2·sr)",
    "katal per cubic meter": "kat/m3",
    "percentage": "%",
    "beats per minute": "bpm",
    "year": "Y",
    "month": "M",
    "day": "D",
    "watt per square metre": "W/m^2",
    "degree": "º",
    "degree fahrenheit": "ºF",
    "decibel": "dBm",
    "kilometre per hour": "km/h",
    "count per cubic metre": "1/m^3",
    "minute": "min",
    "kilogram per litre": "kg/L",
    "mole per litre": "mol/L",
    "inch": "in",
    "pound": "lb",
    "revolution per minute": "RPM",
    "kilogram calorie": "kcal",
    "kilometre per minute": "km/min",
    "metre": "m",
    "step per minute": "stp/min",
    "stroke per minute": "str/min",
    "hour": "h",
    "newton metre": "Nm",
    "millimetre of mercury": "mmHg",
    "metabolic equivalent": "MET",
    "liter per second": "L/s",
    "kilowatt hour": "kWh",
    "lumen per watt": "lm/W",
    "lumen per hour": "lm/h",
    "lux hour": "lx/h",
    "gram per second": "g/s"
}


# DATA UNPACK FORMATS

DATA_FMT = {
    "sint8": "b",
    "uint8": "B",
    "sint16": "h",
    "uint16": "H",
    "uint24": "k",
    "sint32": "i",
    "uint32": "I",
    "uint40": "j",
    "uint48": "J",
    "utf8s": "utf8",
    "8bit": "B",
    "16bit": "h",
    "float64": "d",
    "variable": "X",
    "gatt_uuid": "X",
    "boolean": "?",
    "32bit": "I",
    "FLOAT": "F",
    "24bit": "k",
    "SFLOAT": "S",
    "sint24": "K",
    "nibble": "Y",
    "2bit": "B",
    "uint128": "z",
    "uint12": "o",
    "4bit": "Y",
    "float32": "f",
    "characteristic": "X",
}


# XML PARSER --> get char tag and return char_xml class
class CHAR_XML:
    """
    Parse characteristic xml file
    """

    def __init__(self, xml_file, path=CHARS_XML_DIR):
        self._tree = ET.parse(os.path.join(path, xml_file))
        self._root = self._tree.getroot()
        self.char_metadata = None
        self.name = None
        self.char_type = None
        self.uuid = None
        self.abstract = None
        self.summary = None
        self.description = None
        self.info_text = None
        self.note = None
        self.xml_tags = {}
        self.fields = {}
        self._actual_field = None
        self.bitfields = {}
        self._actual_bitfield = None
        self._actual_bit = None
        self._nr = 0
        self._metadata_string = ''
        self._wrapper = textwrap.TextWrapper(initial_indent=" "*4,)
        self._get_data()
        self._get_fields()

    def __repr__(self):
        self._metadata_string = ''
        self._metadata_string += 'Characteristic Metadata:\n'
        self._metadata_string += '━'*50 + '\n'
        self._pretty_print_metadata()
        self._metadata_string += '━'*50 + '\n'
        return self._metadata_string

    def _get_metadata_string(self):
        self._metadata_string = ''
        self._metadata_string += 'Characteristic Metadata:\n'
        self._metadata_string += '━'*50 + '\n'
        self._pretty_print_metadata()
        self._metadata_string += '━'*50 + '\n'
        return self._metadata_string

    def _pretty_print_metadata(self):
        self._print_wrp('- NAME: {}'.format(self.name))
        self._print_wrp('- UUID: {}'.format(self.uuid))
        self._print_wrp('- ABSTRACT: {}'.format(self.abstract),
                        indent=4 + len('- ABSTRACT: '))
        self._print_wrp('- SUMMARY: {}'.format(self.summary),
                        indent=4 + len('- SUMMARY: '))
        self._print_wrp('- FIELDS:')
        for field in self.fields:
            self._print_wrp('- {}: '.format(field), f_indent=8)
            for key in self.fields[field]:
                if key == 'BitField':
                    self._print_wrp('- {}:'.format(key), f_indent=12)
                    for bit in self.fields[field][key]:
                        self._print_wrp('- {}: '.format(bit), f_indent=16)
                        for keybit in self.fields[field][key][bit].keys():
                            if keybit == 'Enumerations':
                                self._print_wrp(
                                    '- {}:'.format(keybit), f_indent=20)
                                for k, v in self.fields[field][key][bit][keybit].items():

                                    self._print_wrp(
                                        '- {}: {}'.format(k, v), f_indent=24)
                            else:
                                self._print_wrp(
                                    '- {}: {}'.format(keybit, self.fields[field][key][bit][keybit]), f_indent=20)
                else:
                    if key == 'Enumerations':
                        if 'BitField' not in self.fields[field].keys():
                            self._print_wrp('- {}:'.format(key), f_indent=12)
                            for k, v in self.fields[field][key].items():

                                self._print_wrp(
                                    '- {}: {}'.format(k, v), f_indent=16)
                    else:
                        self._print_wrp(
                            '- {}: {}'.format(key, self.fields[field][key]), f_indent=12, indent=12)

        self._print_wrp('- TYPE: {}'.format(self.char_type))
        self._print_wrp('- INFO TEXT: {}'.format(self.info_text),
                        indent=4 + len('- INFO TEXT: '))
        self._print_wrp('- DESCRIPTION: {}'.format(self.description),
                        indent=4 + len('- DESCRIPTION: '))
        self._print_wrp('- NOTE: {}'.format(self.note),
                        indent=4 + len('- NOTE: '))

    def _print_wrp(self, text, mg=3, f_indent=4, indent=0,
                   f_indent_char='', r_indent_char=' ', s_indent=' '):
        try:
            columns, rows = os.get_terminal_size(0)
        except Exception as e:
            columns = 143
        if f_indent_char != '':
            f_indent += -1
        self._wrapper.initial_indent = f_indent_char + r_indent_char * f_indent
        self._wrapper.subsequent_indent = s_indent + ' ' * indent
        self._wrapper.width = columns-mg
        # print('\n'.join(self._wrapper.wrap(text)))
        self._metadata_string += '\n'.join(self._wrapper.wrap(text)) + '\n'

    def _get_data(self):
        for val in self._root.iter():
            try:
                if hasattr(val.text, "strip"):
                    self.xml_tags[val.tag] = [val.text.strip(), val.attrib]
                else:
                    self.xml_tags[val.tag] = [val.text, val.attrib]
                if val.tag == "Characteristic":
                    self.char_metadata = val.attrib
                    self.name = self.char_metadata["name"]
                    self.char_type = self.char_metadata["type"]
                    self.uuid = self.char_metadata["uuid"]
                if val.tag == 'Summary':
                    if hasattr(val.text, 'strip'):
                        self.summary = val.text.strip()
                    else:
                        self.summary = val.text
                if val.tag == 'Description':
                    if hasattr(val.text, 'strip'):
                        self.description = val.text.strip()
                    else:
                        self.description = val.text
                if val.tag == 'InformativeText':
                    if hasattr(val.text, 'strip'):
                        self.info_text = val.text.strip()
                    else:
                        self.info_text = val.text
                if val.tag == 'Note':
                    if hasattr(val.text, 'strip'):
                        self.note = val.text.strip()
                    else:
                        self.note = val.text
                if val.tag == 'p':
                    if hasattr(val.text, 'strip'):
                        if self.note is None:
                            self.note = ''
                        self.note += val.text.strip() + '\n'
            except Exception as e:
                print(traceback.format_exc())

    def _get_fields(self):
        for val in self._root.iter():
            try:
                if val.tag == "Field":
                    self.fields[val.attrib["name"]] = {}
                    self._actual_field = val.attrib["name"]

                if val.tag == "Maximum":
                    if hasattr(val.text, "strip"):
                        if self.fields.keys():
                            self.fields[self._actual_field][val.tag] = val.text.strip()
                    else:
                        if self.fields.keys():
                            self.fields[self._actual_field][val.tag] = val.text
                if val.tag == "Minimum":
                    if hasattr(val.text, "strip"):
                        if self.fields.keys():
                            self.fields[self._actual_field][val.tag] = val.text.strip()
                    else:
                        if self.fields.keys():
                            self.fields[self._actual_field][val.tag] = val.text
                if val.tag == "Requirement":
                    try:
                        if self.fields.keys():
                            if val.tag in self.fields[self._actual_field].keys():
                                self._nr += 1
                                self.fields[self._actual_field][
                                    "{}-{}".format(val.tag, self._nr)
                                ] = val.text
                            else:
                                self.fields[self._actual_field][val.tag] = val.text
                    except Exception as e:
                        print(e)
                if val.tag == "Format":
                    if self.fields.keys():
                        self.fields[self._actual_field][val.tag] = val.text
                        self.fields[self._actual_field]["Ctype"] = DATA_FMT[val.text]

                if val.tag == "Enumeration":
                    if self.fields.keys():
                        if "Enumerations" in self.fields[self._actual_field].keys():
                            self.fields[self._actual_field]["Enumerations"][
                                val.attrib["key"]
                            ] = val.attrib["value"]
                            if "requires" in val.attrib:
                                if (
                                    "Requires"
                                    not in self.fields[self._actual_field][
                                        "Enumerations"
                                    ]
                                ):
                                    self.fields[self._actual_field]["Enumerations"][
                                        "Requires"
                                    ] = {}
                                self.fields[self._actual_field]["Enumerations"][
                                    "Requires"
                                ][val.attrib["key"]] = val.attrib["requires"]

                        else:
                            self.fields[self._actual_field]["Enumerations"] = {}
                            self.fields[self._actual_field]["Enumerations"][
                                val.attrib["key"]
                            ] = val.attrib["value"]
                            if "requires" in val.attrib:
                                if (
                                    "Requires"
                                    not in self.fields[self._actual_field][
                                        "Enumerations"
                                    ]
                                ):
                                    self.fields[self._actual_field]["Enumerations"][
                                        "Requires"
                                    ] = {}
                                self.fields[self._actual_field]["Enumerations"][
                                    "Requires"
                                ][val.attrib["key"]] = val.attrib["requires"]

                if val.tag == "Enumerations":
                    if self.fields.keys():
                        self.fields[self._actual_field][val.tag] = {}

                if val.tag == "BitField":
                    if self.fields.keys():
                        self.fields[self._actual_field][val.tag] = {}
                    self._actual_bitfield = val.tag
                if val.tag == "Bit":
                    if self.fields[self._actual_field].keys():
                        if "name" in val.attrib.keys():
                            bitname = val.attrib["name"]
                        else:
                            bitname = "BitGroup {}".format(val.attrib["index"])
                        self.fields[self._actual_field][self._actual_bitfield][
                            bitname
                        ] = {}
                        self.fields[self._actual_field][self._actual_bitfield][bitname][
                            "index"
                        ] = val.attrib["index"]
                        self.fields[self._actual_field][self._actual_bitfield][bitname][
                            "size"
                        ] = val.attrib["size"]
                        self._actual_bit = bitname

                if val.tag == "Enumeration":
                    if self._actual_bitfield is not None:
                        if (
                            self._actual_bitfield
                            in self.fields[self._actual_field].keys()
                        ):
                            if self.fields[self._actual_field][
                                self._actual_bitfield
                            ].keys():
                                self.fields[self._actual_field][self._actual_bitfield][
                                    self._actual_bit
                                ]["Enumerations"][val.attrib["key"]] = val.attrib[
                                    "value"
                                ]
                                if "requires" in val.attrib:
                                    if (
                                        "Requires"
                                        not in self.fields[self._actual_field][
                                            self._actual_bitfield
                                        ][self._actual_bit]["Enumerations"]
                                    ):
                                        self.fields[self._actual_field][
                                            self._actual_bitfield
                                        ][self._actual_bit]["Enumerations"][
                                            "Requires"
                                        ] = {}
                                    self.fields[self._actual_field][
                                        self._actual_bitfield
                                    ][self._actual_bit]["Enumerations"]["Requires"][
                                        val.attrib["key"]
                                    ] = val.attrib[
                                        "requires"
                                    ]

                if val.tag == "Enumerations":
                    if self._actual_bitfield is not None:
                        if (
                            self._actual_bitfield
                            in self.fields[self._actual_field].keys()
                        ):
                            if self.fields[self._actual_field][
                                self._actual_bitfield
                            ].keys():
                                self.fields[self._actual_field][self._actual_bitfield][
                                    self._actual_bit
                                ][val.tag] = {}
                if val.tag == "DecimalExponent":
                    if self.fields.keys():
                        self.fields[self._actual_field][val.tag] = int(val.text)

                if val.tag == "Unit":
                    self.fields[self._actual_field]["Unit_id"] = val.text
                    # get unit from unit stringcode
                    unit_stringcode_filt = val.text.replace("org.bluetooth.unit.", "")
                    quantity = " ".join(unit_stringcode_filt.split(".")[0].split("_"))
                    self.fields[self._actual_field]["Quantity"] = quantity
                    try:
                        unit = " ".join(
                            unit_stringcode_filt.split(".")[1].split("_")
                        ).strip()
                        self.fields[self._actual_field][val.tag] = unit
                        self.fields[self._actual_field]["Symbol"] = CHARS_UNITS[unit]
                    except Exception as e:
                        try:
                            self.fields[self._actual_field][val.tag] = quantity
                            self.fields[self._actual_field]["Symbol"] = CHARS_UNITS[
                                quantity
                            ]
                        except Exception as e:
                            self.fields[self._actual_field][val.tag] = ""
                            self.fields[self._actual_field]["Symbol"] = ""
                if val.tag == "InformativeText":
                    if self.fields.keys():
                        if hasattr(val.text, "strip"):
                            self.fields[self._actual_field][val.tag] = val.text.strip()
                        else:
                            self.fields[self._actual_field][val.tag] = val.text
                if val.tag == "Reference":
                    if self.fields.keys():
                        if hasattr(val.text, "strip"):
                            self.fields[self._actual_field][val.tag] = val.text.strip()
                        else:
                            self.fields[self._actual_field][val.tag] = val.text
                if val.tag == "BinaryExponent":
                    if self.fields.keys():
                        if hasattr(val.text, "strip"):
                            self.fields[self._actual_field][val.tag] = int(
                                val.text.strip()
                            )
                        else:
                            self.fields[self._actual_field][val.tag] = int(val.text)
                if val.tag == "Multiplier":
                    if self.fields.keys():
                        if hasattr(val.text, "strip"):
                            self.fields[self._actual_field][val.tag] = int(
                                val.text.strip()
                            )
                        else:
                            self.fields[self._actual_field][val.tag] = int(val.text)

                if val.tag == "Reference":
                    if self.fields.keys():
                        if hasattr(val.text, "strip"):
                            self.fields[self._actual_field][val.tag] = " ".join(
                                ch.capitalize()
                                for ch in val.text.strip().split(".")[-1].split("_")
                            )
                        else:
                            self.fields[self._actual_field][val.tag] = val.text
            except Exception as e:
                print(traceback.format_exc())


def get_xml_char(characteristic: Union[str, BleakGATTCharacteristic])-> CHAR_XML:
    """
    Get characteristic metadata from its xml file

    Args:
        * **characteristic** *(str, BleakGATTCharacteristic)*:

            The name of the characteristic or bleak characteristic class

    Returns:
        * **characteristic metatada class** *(CHAR_XML)*:

            The characteristic metadata parsed from its xml file
        """
    if isinstance(characteristic, BleakGATTCharacteristic):
        characteristic = uuidstr_to_str(characteristic.uuid)
    if "Magnetic Flux" in characteristic:
        char_string = "_".join(
            [
                ch.lower().replace("magnetic", "Magnetic")
                for ch in characteristic.replace("-", " ", 10).replace("–", " ").split()
            ]
        )
        char_string = char_string.replace("3d", "3D").replace("2d", "2D")
    else:
        char_string = "_".join(
            [ch.lower() for ch in characteristic.replace("-", " ", 10).replace("–", " ").split()]
        )
    char_string += ".xml"
    char_string = char_string.replace("_characteristic", "")
    return CHAR_XML(char_string)


def _unpack_data(ctype, data):
    """
    Unpack 'data' bytes with 'ctype' equivalent format
    """
    if ctype == "utf8":
        if hasattr(data, 'decode'):
            return data.decode("utf8")
        else:
            data = bytes(data).decode("utf8")
            return data
    else:
        (data,) = sup_struct.unpack(ctype, data)
        return data


# BITMASKS

def _complete_bytes(bb):
    """
    Make bytes number even
    """
    len_bytes = len(bb)
    if (len_bytes % 2) == 0:
        pass
    else:
        bb = b'\x00' + bb
    return bb


def _autobitmask(val, total_size, index, size, keymap):
    """
    Generate a bitmask and apply it to 'val' bits given the 'total_size',
        'index', and 'size' of the BitField
    """
    _bitmask = eval(
        "0b{}".format("0" * (total_size - (index + size)) + (size * "1") + "0" * index)
    )

    key = (val & _bitmask) >> index
    key_str = str(key)
    mapped_val = keymap[key_str]
    return mapped_val


def _autobitmask_req(val, total_size, index, size, keymap):
    """
    Generate a bitmask and apply it to 'val' bits given the 'total_size',
        'index', and 'size' of the BitField
    """
    _bitmask = eval(
        "0b{}".format("0" * (total_size - (index + size)) + (size * "1") + "0" * index)
    )
    key = (val & _bitmask) >> index
    key_str = str(key)
    if key_str in keymap:
        mapped_val = keymap[key_str]
        return mapped_val
    else:
        return False


# AUTOFORMAT BITFIELDS

# FLAG VALUES


def _autoformat(char, val, field_to_unpack=None):
    """
    Given a characteristic and 'val' bytes, obtain the BitField values
    """
    fields = {}
    if not field_to_unpack:
        for field in char.fields:
            if "Ctype" in char.fields[field]:
                # ctype = char.fields[field]['Ctype']
                total_size = 0
                if "BitField" in char.fields[field]:
                    fields[field] = {}
                    bitfield = char.fields[field]["BitField"]
                    for bitf in bitfield:
                        total_size += int(bitfield[bitf]["size"])
                    for bitf in bitfield:
                        size = int(bitfield[bitf]["size"])
                        index = int(bitfield[bitf]["index"])
                        key_map = bitfield[bitf]["Enumerations"]
                        fields[field][bitf] = _autobitmask(
                            val,
                            total_size=total_size,
                            index=index,
                            size=size,
                            keymap=key_map,
                        )
                    break

        return fields
    else:
        field = field_to_unpack
        if hasattr(char, 'fields'):
            if "Ctype" in char.fields[field]:
                # ctype = char.fields[field]['Ctype']
                total_size = 0
                if "BitField" in char.fields[field]:
                    fields[field] = {}
                    bitfield = char.fields[field]["BitField"]
                    for bitf in bitfield:
                        total_size += int(bitfield[bitf]["size"])
                    for bitf in bitfield:
                        size = int(bitfield[bitf]["size"])
                        index = int(bitfield[bitf]["index"])
                        key_map = bitfield[bitf]["Enumerations"]
                        fields[field][bitf] = _autobitmask(
                            val,
                            total_size=total_size,
                            index=index,
                            size=size,
                            keymap=key_map,
                        )
        else:
            if "Ctype" in char[field]:
                # ctype = char.fields[field]['Ctype']
                total_size = 0
                if "BitField" in char[field]:
                    fields[field] = {}
                    bitfield = char[field]["BitField"]
                    for bitf in bitfield:
                        total_size += int(bitfield[bitf]["size"])
                    for bitf in bitfield:
                        size = int(bitfield[bitf]["size"])
                        index = int(bitfield[bitf]["index"])
                        key_map = bitfield[bitf]["Enumerations"]
                        fields[field][bitf] = _autobitmask(
                            val,
                            total_size=total_size,
                            index=index,
                            size=size,
                            keymap=key_map,
                        )

        return fields


# FIELDS REQUIREMENTS


def _autoformat_reqs(char, val):
    """
    Given a 'char' characteristic and 'val' bytes, obtain the BitField values
    requirements
    """
    fields = {}
    for field in char.fields:
        if "Ctype" in char.fields[field]:
            # ctype = char.fields[field]['Ctype']
            total_size = 0
            if "BitField" in char.fields[field]:
                fields[field] = {}
                bitfield = char.fields[field]["BitField"]
                for bitf in bitfield:
                    total_size += int(bitfield[bitf]["size"])
                for bitf in bitfield:
                    size = int(bitfield[bitf]["size"])
                    index = int(bitfield[bitf]["index"])
                    key_map = bitfield[bitf]["Enumerations"]
                    if "Requires" in key_map:
                        fields[field][bitf] = _autobitmask_req(
                            val,
                            total_size=total_size,
                            index=index,
                            size=size,
                            keymap=key_map["Requires"],
                        )

    return fields


# GET FIELD REQUIREMENTS
def _get_req(char_field):
    """
    Get characteristics field requirements
    """
    reqs = []
    for key in char_field:
        if "Requirement" in key:
            reqs.append(char_field[key])
    return reqs


# GET FIELD REFERENCES RECURSIVELY
def get_ref_char_field(_field, name_field):
    """
    Get characteristics field references recursively
    """
    _REFERENCE_TAGS_FIELDS = {}
    _FIELDS_OF_REFERENCED_CHAR = {}
    _REFERENCE_FIELDS = {}
    ctype_global = ''
    if "Reference" in _field:
        reference = _field["Reference"]
        _REFERENCE_TAGS_FIELDS[name_field] = reference
        reference_char = get_xml_char(reference)
        _FIELDS_OF_REFERENCED_CHAR[reference] = []
        for ref_field in reference_char.fields:
            if "Reference" not in reference_char.fields[ref_field]:

                _REFERENCE_FIELDS[ref_field] = reference_char.fields[ref_field]
            _FIELDS_OF_REFERENCED_CHAR[reference].append(ref_field)
            if "Ctype" in reference_char.fields[ref_field]:
                ctype = reference_char.fields[ref_field]["Ctype"]
                ctype_global += ctype
            elif "Reference" in reference_char.fields[ref_field]:
                _ref_tag_fields, _fields_of_ref_char, _ref_fields, _ctype_global = get_ref_char_field(
                    reference_char.fields[ref_field], ref_field)
                _REFERENCE_TAGS_FIELDS.update(_ref_tag_fields)
                _FIELDS_OF_REFERENCED_CHAR.update(_fields_of_ref_char)
                _REFERENCE_FIELDS.update(_ref_fields)
                ctype_global += _ctype_global
        return (_REFERENCE_TAGS_FIELDS, _FIELDS_OF_REFERENCED_CHAR, _REFERENCE_FIELDS, ctype_global)


# GET REFERENCE FIELD IN ONE LEVEL DEEP
def _get_plain_ref_fields(fof_refchar):
    it_dict = fof_refchar.copy()
    for ref in it_dict:
        if any([sf in it_dict for sf in it_dict[ref]]):
            for sf in it_dict[ref]:
                if sf in it_dict:
                    index = fof_refchar[ref].index(sf)
                    fof_refchar[ref].pop(index)
                    for rf in it_dict[sf]:
                        fof_refchar[ref].insert(index, rf)
                        index += 1
            fof_refchar = _get_plain_ref_fields(fof_refchar)
        else:
            break
        break

    return fof_refchar


# GET FORMATTED VALUE

def _get_single_field(char, val, debug=False):
    """
    Get characteristic single field data
    """
    if debug:
        print("CASE 1: ONE FIELD")
    for field in char.fields:
        # FIXME: CASE 1C REFERENCE ANOTHER CHAR (WITH ONE OR MULTIPLE FIELDS) ?
        if "Ctype" in char.fields[field]:
            ctype = char.fields[field]["Ctype"]
            if "BitField" in char.fields[field]:
                if debug:
                    print("CASE 1A: BITFIELD")
                (raw_data,) = struct.unpack(ctype, val)
                data = list(_autoformat(char, raw_data).values())[0]
                return {field: {"Value": data}}
            else:
                if debug:
                    print("CASE 1B: VALUE")
                if "Enumerations" in char.fields[field]:
                    if debug:
                        print("CASE 1B.1: MAPPED VALUE")
                    keymap = char.fields[field]["Enumerations"]
                    if keymap:
                        (data,) = struct.unpack(ctype, val)  # here read char
                        try:
                            mapped_val = keymap[str(data)]
                            return {field: {"Value": mapped_val}}
                        except Exception as e:
                            if debug:
                                print("Value not in keymap")
                    else:
                        (data,) = struct.unpack(ctype, val)
                else:
                    if debug:
                        print("CASE 1B.2: SINGLE VALUE")
                    data = _unpack_data(ctype, val)
                # Format fields values according to field metadata: (DecimalExponent/Multiplier):
                _FIELDS_VALS = {}
                _FIELDS_VALS[field] = {}
                if "Quantity" in char.fields[field]:
                    _FIELDS_VALS[field]["Quantity"] = char.fields[field]["Quantity"]
                if "Unit" in char.fields[field]:
                    _FIELDS_VALS[field]["Unit"] = char.fields[field]["Unit"]
                if "Symbol" in char.fields[field]:
                    _FIELDS_VALS[field]["Symbol"] = char.fields[field]["Symbol"]

                formatted_value = data
                if "Multiplier" in char.fields[field]:
                    formatted_value *= char.fields[field]["Multiplier"]
                if "DecimalExponent" in char.fields[field]:
                    formatted_value /= 1 / (10 ** (char.fields[field]["DecimalExponent"]))
                if "BinaryExponent" in char.fields[field]:
                    formatted_value *= 2 ** (char.fields[field]["BinaryExponent"])

                _FIELDS_VALS[field]["Value"] = formatted_value
                return _FIELDS_VALS


def _get_multiple_fields(char, val, rtn_flags=False, debug=False):
    """
    Get characteristic multiple fields data
    """
    if debug:
        print("CASE 2: MULTIPLE FIELDS")
    _FLAGS = None
    _REQS = None
    if "Flags" in char.fields:
        if debug:
            print("CASE 2.A: Flags Field Present")
        if "Ctype" in char.fields["Flags"]:
            ctype_flag = char.fields["Flags"]["Ctype"]
            if "BitField" in char.fields["Flags"]:
                (raw_data,) = struct.unpack(
                    ctype_flag, val[: struct.calcsize(ctype_flag)]
                )
                _FLAGS = list(_autoformat(char, raw_data).values())[0]
                _REQS = list(_autoformat_reqs(char, raw_data).values())[0]

    if _FLAGS:
        # Get fields according to flags
        if debug:
            print(_FLAGS)
            print(_REQS)
            print("Fields to read according to Flags:")
        _FIELDS_TO_READ = []
        for field in char.fields:
            if field != "Flags":
                field_req = None
                # get requirements if any:
                field_req = _get_req(char.fields[field])
                if "Mandatory" in field_req:
                    if debug:
                        print("   - {}: {}".format(field, True))
                    _FIELDS_TO_READ.append(field)
                else:
                    _READ_FIELD = all([req in _REQS.values() for req in field_req])
                    if _READ_FIELD:
                        if debug:
                            print("   - {}: {}".format(field, field_req))
                        _FIELDS_TO_READ.append(field)
        if _FIELDS_TO_READ:
            # get global unpack format: ctype_flag += ctype_field_to_read
            ctype_global = ctype_flag
            # REFERENCE FIELDS
            _REFERENCE_FIELDS = {}  # fields with attributes
            _REFERENCE_TAGS_FIELDS = {}  # fields that references another characteristic
            _FIELDS_OF_REFERENCED_CHAR = {}  # fields of the referenced characteristic
            copy_FIELDS_TO_READ = _FIELDS_TO_READ.copy()
            for field in copy_FIELDS_TO_READ:
                if "Ctype" in char.fields[field]:
                    ctype = char.fields[field]["Ctype"]
                    ctype_global += ctype

                # Get Reference if any and ctype/unit/symbol/decexp/multiplier

                if "Reference" in char.fields[field]:
                    reference = char.fields[field]["Reference"]
                    _rtf, _fofrc, _rf, ctype = get_ref_char_field(char.fields[field],
                                                                  field)
                    # clean intermediate references
                    # _ref_tag_fields = { k:v for k,v in _rtf.items() if k == field}
                    _fofrc = _get_plain_ref_fields(_fofrc)
                    # _fields_of_ref_char = { k:v for k,v in _fofrc.items() if k == reference}
                    _REFERENCE_TAGS_FIELDS[field] = reference
                    _FIELDS_OF_REFERENCED_CHAR[reference] = []
                    for ref_field in _rf:
                        _FIELDS_OF_REFERENCED_CHAR[reference].append(ref_field)
                        _REFERENCE_FIELDS[ref_field] = _rf[ref_field]
                    ctype_global += ctype
                    # reference = char.fields[field]["Reference"]
                    # _REFERENCE_TAGS_FIELDS[field] = reference
                    # reference_char = get_xml_char(reference)
                    # _FIELDS_OF_REFERENCED_CHAR[reference] = []
                    # for ref_field in reference_char.fields:
                    #     # Add fields to _REFERENCE_FIELDS
                    #     _FIELDS_OF_REFERENCED_CHAR[reference].append(ref_field)
                    #     _REFERENCE_FIELDS[ref_field] = reference_char.fields[ref_field]
                    #     if "Ctype" in reference_char.fields[ref_field]:
                    #         ctype = reference_char.fields[ref_field]["Ctype"]
                    #         ctype_global += ctype

            # Unpack data
            # First value is the flags value
            # Rest are field values

            # val = _complete_bytes(val)
            # HEART RATE MEASUREMENT FIX
            if char.name == 'Heart Rate Measurement':
                rri = _FLAGS['RR-Interval bit']
                if rri == 'One or more RR-Interval values are present.':
                    interval_index = 0
                    _REFERENCE_TAGS_FIELDS['RR-Interval'] = 'RR-Interval'
                    _FIELDS_OF_REFERENCED_CHAR['RR-Interval'] = []
                    ref_field = 'RR-I{}'.format(interval_index)
                    _FIELDS_OF_REFERENCED_CHAR['RR-Interval'].append(ref_field)
                    _REFERENCE_FIELDS[ref_field] = char.fields['RR-Interval']
                    while len(val) > struct.calcsize(ctype_global):
                        interval_index += 1
                        ctype_global += 'H'
                        ref_field = 'RR-I{}'.format(interval_index)
                        _FIELDS_OF_REFERENCED_CHAR['RR-Interval'].append(ref_field)
                        _REFERENCE_FIELDS[ref_field] = char.fields['RR-Interval']
            if debug:
                print("Global Unpack Format: {}".format(ctype_global))

            flag, *data = sup_struct.unpack(ctype_global, val)
            if debug:
                print(data)
                print(_FIELDS_TO_READ)
                print(_REFERENCE_TAGS_FIELDS)
                print(_FIELDS_OF_REFERENCED_CHAR)
                print(_REFERENCE_FIELDS)
            value_index = 0
            _FIELDS_VALS = {}
            # Format fields values according to field metadata: (DecimalExponent/Multiplier):
            for field in _FIELDS_TO_READ:
                value = data[value_index]
                if field in char.fields:
                    _FIELDS_VALS[field] = {}
                    if field not in _REFERENCE_TAGS_FIELDS:
                        if "Quantity" in char.fields[field]:
                            _FIELDS_VALS[field]["Quantity"] = char.fields[field]["Quantity"]
                        if "Unit" in char.fields[field]:
                            _FIELDS_VALS[field]["Unit"] = char.fields[field]["Unit"]
                        if "Symbol" in char.fields[field]:
                            _FIELDS_VALS[field]["Symbol"] = char.fields[field]["Symbol"]

                        formatted_value = value
                        if "Multiplier" in char.fields[field]:
                            formatted_value *= char.fields[field]["Multiplier"]
                        if "DecimalExponent" in char.fields[field]:
                            formatted_value /= 1 / (10 ** (char.fields[field]["DecimalExponent"]))
                        if "BinaryExponent" in char.fields[field]:
                            formatted_value *= 2 ** (char.fields[field]["BinaryExponent"])
                        if "BitField" in char.fields[field]:
                            formatted_value = list(
                                _autoformat(char, formatted_value, field).values()
                            )[0]
                        if "Enumerations" in char.fields[field] and 'BitField' not in char.fields[field]:
                            if str(value) in char.fields[field]["Enumerations"]:
                                formatted_value = char.fields[field]["Enumerations"][str(value)]

                        _FIELDS_VALS[field]["Value"] = formatted_value
                    else:
                        ref_char = _REFERENCE_TAGS_FIELDS[field]
                        _FIELDS_VALS[field][ref_char] = {}
                        for ref_field in _FIELDS_OF_REFERENCED_CHAR[ref_char]:
                            _FIELDS_VALS[field][ref_char][ref_field] = {}
                            if "Quantity" in _REFERENCE_FIELDS[ref_field]:
                                _FIELDS_VALS[field][ref_char][ref_field]["Quantity"] = _REFERENCE_FIELDS[ref_field][
                                    "Quantity"
                                ]
                            if "Unit" in _REFERENCE_FIELDS[ref_field]:
                                _FIELDS_VALS[field][ref_char][ref_field]["Unit"] = _REFERENCE_FIELDS[ref_field][
                                    "Unit"
                                ]
                            if "Symbol" in _REFERENCE_FIELDS[ref_field]:
                                _FIELDS_VALS[field][ref_char][ref_field]["Symbol"] = _REFERENCE_FIELDS[ref_field][
                                    "Symbol"
                                ]
                            value = data[value_index]
                            formatted_value = value
                            if "Multiplier" in _REFERENCE_FIELDS[ref_field]:
                                formatted_value *= _REFERENCE_FIELDS[ref_field]["Multiplier"]
                            if "DecimalExponent" in _REFERENCE_FIELDS[ref_field]:
                                formatted_value /= 1 / (10 ** (
                                    _REFERENCE_FIELDS[ref_field]["DecimalExponent"]
                                ))
                            if "BinaryExponent" in _REFERENCE_FIELDS[ref_field]:
                                formatted_value *= 2 ** (
                                    _REFERENCE_FIELDS[ref_field]["BinaryExponent"]
                                )
                            if "BitField" in _REFERENCE_FIELDS[ref_field]:

                                formatted_value = list(
                                    _autoformat(_REFERENCE_FIELDS, formatted_value, ref_field).values()
                                )[0]

                            if "Enumerations" in _REFERENCE_FIELDS[ref_field] and 'BitField' not in _REFERENCE_FIELDS[ref_field]:
                                if str(value) in _REFERENCE_FIELDS[ref_field]["Enumerations"]:
                                    formatted_value = _REFERENCE_FIELDS[ref_field]["Enumerations"][str(value)]

                            _FIELDS_VALS[field][ref_char][ref_field]["Value"] = formatted_value
                            value_index += 1
                        value_index -= 1
                value_index += 1

            if not rtn_flags:
                return _FIELDS_VALS
            else:
                return [_FIELDS_VALS, _FLAGS]
    else:
        if debug:
            print("CASE 2.B: Flags Field Not Present")
            print("Fields to read:")
        _FIELDS_TO_READ = []
        for field in char.fields:
            if field != "Flags":
                field_req = None
                # get requirements if any:
                field_req = _get_req(char.fields[field])
                if "Mandatory" in field_req:
                    if debug:
                        print("   - {}: {}".format(field, True))
                    _FIELDS_TO_READ.append(field)
                else:
                    _READ_FIELD = all([req in _REQS.values() for req in field_req])
                    if _READ_FIELD:
                        if debug:
                            print("   - {}: {}".format(field, field_req))
                        _FIELDS_TO_READ.append(field)

        # REFERENCE FIELDS
        _REFERENCE_FIELDS = {}  # fields with attributes
        _REFERENCE_TAGS_FIELDS = {}  # fields that references another characteristic
        _FIELDS_OF_REFERENCED_CHAR = {}  # fields of the referenced characteristic
        copy_FIELDS_TO_READ = _FIELDS_TO_READ.copy()
        if _FIELDS_TO_READ:
            # get global unpack format: ctype_flag += ctype_field_to_read
            ctype_global = ""
            for field in copy_FIELDS_TO_READ:
                if "Ctype" in char.fields[field]:
                    ctype = char.fields[field]["Ctype"]
                    ctype_global += ctype

                # Get Reference if any and ctype/unit/symbol/decexp/multiplier

                if "Reference" in char.fields[field]:
                    reference = char.fields[field]["Reference"]
                    _rtf, _fofrc, _rf, ctype = get_ref_char_field(char.fields[field],
                                                                  field)
                    # clean intermediate references
                    # _ref_tag_fields = { k:v for k,v in _rtf.items() if k == field}
                    _fofrc = _get_plain_ref_fields(_fofrc)
                    # _fields_of_ref_char = { k:v for k,v in _fofrc.items() if k == reference}
                    _REFERENCE_TAGS_FIELDS[field] = reference
                    _FIELDS_OF_REFERENCED_CHAR[reference] = []
                    for ref_field in _rf:
                        _FIELDS_OF_REFERENCED_CHAR[reference].append(ref_field)
                        _REFERENCE_FIELDS[ref_field] = _rf[ref_field]
                    ctype_global += ctype
                    # reference = char.fields[field]["Reference"]
                    # _REFERENCE_TAGS_FIELDS[field] = reference
                    # reference_char = get_xml_char(reference)
                    # _FIELDS_OF_REFERENCED_CHAR[reference] = []
                    # for ref_field in reference_char.fields:
                    #     # Add fields to _REFERENCE_FIELDS
                    #     _FIELDS_OF_REFERENCED_CHAR[reference].append(ref_field)
                    #     _REFERENCE_FIELDS[ref_field] = reference_char.fields[ref_field]
                    #     if "Ctype" in reference_char.fields[ref_field]:
                    #         ctype = reference_char.fields[ref_field]["Ctype"]
                    #         ctype_global += ctype

            # Unpack data
            # There is no flags value
            # All fields are values
            if debug:
                print("Global Unpack Format: {}".format(ctype_global))
            data = sup_struct.unpack(ctype_global, val)
            value_index = 0
            _FIELDS_VALS = {}
            if debug:
                print(data)
                print(_FIELDS_TO_READ)
                print(_REFERENCE_TAGS_FIELDS)
                print(_FIELDS_OF_REFERENCED_CHAR)
                print(_REFERENCE_FIELDS)
            # Format fields values according to field metadata: (DecimalExponent/Multiplier):
            for field in _FIELDS_TO_READ:
                value = data[value_index]
                if field in char.fields:
                    _FIELDS_VALS[field] = {}
                    if field not in _REFERENCE_TAGS_FIELDS:
                        if "Quantity" in char.fields[field]:
                            _FIELDS_VALS[field]["Quantity"] = char.fields[field]["Quantity"]
                        if "Unit" in char.fields[field]:
                            _FIELDS_VALS[field]["Unit"] = char.fields[field]["Unit"]
                        if "Symbol" in char.fields[field]:
                            _FIELDS_VALS[field]["Symbol"] = char.fields[field]["Symbol"]

                        formatted_value = value
                        if "Multiplier" in char.fields[field]:
                            formatted_value *= char.fields[field]["Multiplier"]
                        if "DecimalExponent" in char.fields[field]:
                            formatted_value /= 1 / (10 ** (char.fields[field]["DecimalExponent"]))
                        if "BinaryExponent" in char.fields[field]:
                            formatted_value *= 2 ** (char.fields[field]["BinaryExponent"])
                        if "Enumerations" in char.fields[field] and 'BitField' not in char.fields[field]:
                            if str(value) in char.fields[field]["Enumerations"]:
                                formatted_value = char.fields[field]["Enumerations"][str(value)]

                        if "BitField" in char.fields[field]:
                            print(formatted_value)
                            formatted_value = list(
                                _autoformat(char, formatted_value, field).values()
                            )[0]

                        _FIELDS_VALS[field]["Value"] = formatted_value
                    else:
                        ref_char = _REFERENCE_TAGS_FIELDS[field]
                        _FIELDS_VALS[field][ref_char] = {}
                        for ref_field in _FIELDS_OF_REFERENCED_CHAR[ref_char]:
                            _FIELDS_VALS[field][ref_char][ref_field] = {}
                            if "Quantity" in _REFERENCE_FIELDS[ref_field]:
                                _FIELDS_VALS[field][ref_char][ref_field]["Quantity"] = _REFERENCE_FIELDS[ref_field][
                                    "Quantity"
                                ]
                            if "Unit" in _REFERENCE_FIELDS[ref_field]:
                                _FIELDS_VALS[field][ref_char][ref_field]["Unit"] = _REFERENCE_FIELDS[ref_field][
                                    "Unit"
                                ]
                            if "Symbol" in _REFERENCE_FIELDS[ref_field]:
                                _FIELDS_VALS[field][ref_char][ref_field]["Symbol"] = _REFERENCE_FIELDS[ref_field][
                                    "Symbol"
                                ]
                            value = data[value_index]
                            formatted_value = value
                            if "Multiplier" in _REFERENCE_FIELDS[ref_field]:
                                formatted_value *= _REFERENCE_FIELDS[ref_field]["Multiplier"]
                            if "DecimalExponent" in _REFERENCE_FIELDS[ref_field]:
                                formatted_value /= 1 / (10 ** (
                                    _REFERENCE_FIELDS[ref_field]["DecimalExponent"]
                                ))
                            if "BinaryExponent" in _REFERENCE_FIELDS[ref_field]:
                                formatted_value *= 2 ** (
                                    _REFERENCE_FIELDS[ref_field]["BinaryExponent"]
                                )
                            if "Enumerations" in _REFERENCE_FIELDS[ref_field] and 'BitField' not in _REFERENCE_FIELDS[ref_field]:
                                if str(value) in _REFERENCE_FIELDS[ref_field]["Enumerations"]:
                                    formatted_value = _REFERENCE_FIELDS[ref_field]["Enumerations"][str(value)]

                            if "BitField" in _REFERENCE_FIELDS[ref_field]:

                                formatted_value = list(
                                    _autoformat(_REFERENCE_FIELDS, formatted_value, ref_field).values()
                                )[0]

                            _FIELDS_VALS[field][ref_char][ref_field]["Value"] = formatted_value
                            value_index += 1
                        value_index -= 1
                value_index += 1
            if not rtn_flags:
                return _FIELDS_VALS
            else:
                return [_FIELDS_VALS, _FLAGS]


def get_char_value(value: bytes, characteristic: Union[BleakGATTCharacteristic,
                                                       str, CHAR_XML],
                   rtn_flags: bool = False,
                   debug: bool = False) -> dict:
    """
    Given a characteristic and its raw value in bytes,\
    obtain the formatted value as a dict instance:

    Args:
        * **value (bytes)**:

            The result of ``read_gatt_char()``

        * **characteristic** *(BleakGATTCharacteristic, str, CHAR_XML)*:

            The characteristic from which get metadata.

        * **rnt_flags**:

            return the bitflags too if present

        * **debug**:

            print debug information about bytes unpacking

    Returns:
        * **dict**:

            `dict` instance with the formatted value and its metadata.
    """

    # Get characteristic metadata from xml file
    if isinstance(characteristic, str) or isinstance(characteristic,
                                                     BleakGATTCharacteristic):
        characteristic = get_xml_char(characteristic)
    # if isinstance(characteristic, BleakGATTCharacteristic):
    #     characteristic = get_xml_char(uuidstr_to_str(characteristic.uuid))

    if len(characteristic.fields) == 1:
        # CASE 1: ONLY ONE FIELD: SINGLE VALUE OR SINGLE BITFIELD
        return _get_single_field(characteristic, value, debug=debug)

    else:
        # CASE 2: MULTIPLE FIELDS: 1º Field flags, Rest of Fields values
        # check if Flags field exists
        # get flags and fields requirements if any
        return _get_multiple_fields(characteristic, value, rtn_flags=rtn_flags,
                                    debug=debug)


def pformat_field_value(field_data, field='', sep=',', prnt=True,
                        rtn=False):
    """
    Print or return the field value in string format
    """
    try:
        field_string_values = ["{} {}".format(field_data['Value'], field_data['Symbol'])]
    except Exception as e:
        field_string_values = ["{}".format(field_data['Value'])]
    if field:
        if prnt:
            print('{}: {}'.format(field, sep.join(field_string_values)))
        elif rtn:
            return '{}: {}'.format(field, sep.join(field_string_values))
    else:
        if prnt:
            print(sep.join(field_string_values))
        elif rtn:
            return sep.join(field_string_values)


def pformat_char_value(data,
                       char="",
                       only_val=False,
                       one_line=False,
                       sep=",",
                       custom=None,
                       symbols=True,
                       prnt=True,
                       rtn=False):
    """
    Print or return the characteristic value in string format
    """
    if not custom:
        if not one_line:
            if char:
                print("{}:".format(char))
            if not only_val:
                for key in data:
                    try:
                        print(
                            "{}: {} {}".format(
                                key, data[key]["Value"], data[key]["Symbol"]
                            )
                        )
                    except Exception as e:
                        print("{}: {} ".format(key, data[key]["Value"]))
            else:
                for key in data:
                    try:
                        print("{} {}".format(
                            data[key]["Value"], data[key]["Symbol"]))
                    except Exception as e:
                        print("{}".format(data[key]["Value"]))
        else:

            if not only_val:
                try:
                    char_string_values = [
                        "{}: {} {}".format(
                            key, data[key]["Value"], data[key]["Symbol"])
                        for key in data
                    ]
                except Exception as e:
                    char_string_values = [
                        "{}: {}".format(key, data[key]["Value"]) for key in data
                    ]
                if char:
                    if prnt:
                        print("{}: {}".format(char, sep.join(char_string_values)))
                    elif rtn:
                        return "{}: {}".format(char, sep.join(char_string_values))
                else:
                    if prnt:
                        print(sep.join(char_string_values))
                    elif rtn:
                        return sep.join(char_string_values)
            else:
                try:
                    char_string_values = [
                        "{} {}".format(data[key]["Value"], data[key]["Symbol"])
                        for key in data
                    ]
                except Exception as e:
                    char_string_values = [
                        "{}".format(data[key]["Value"]) for key in data
                    ]
                if char:
                    if prnt:
                        print("{}: {}".format(char, sep.join(char_string_values)))
                    elif rtn:
                        return "{}: {}".format(char, sep.join(char_string_values))
                else:
                    if prnt:
                        print(sep.join(char_string_values))
                    elif rtn:
                        return sep.join(char_string_values)
    else:
        if not symbols:
            print(custom.format(*[data[k]["Value"] for k in data]))
        else:
            print(
                custom.format(
                    *["{} {}".format(data[k]["Value"], data[k]["Symbol"]) for k in data]
                )
            )


def get_plain_format(field):
    """
    Iterates until the last level where Value is
    """
    val = ""
    for k in field:
        if 'Value' in field[k]:
            try:
                val += "{}: {} {} ; ".format(k, field[k]['Value'],  field[k]['Symbol'])
            except Exception as e:
                val += "{}: {} ; ".format(k, field[k]['Value'])
        else:
            val += get_plain_format(field[k])
    if val != "":
        return val


def pformat_ref_char_value(char_value):
    """
    Print or return the characteristic value in string format
    """
    for field in char_value:
        if 'Value' in char_value[field]:
            print(field, char_value[field]['Value'])
        else:
            # iterate function
            val = get_plain_format(char_value[field])
            print("{}: {}".format(field, val))


def map_char_value(data, keys=[], string_fmt=False, one_line=True, sep=", "):
    """
    Map characteristic value with the given keys, return dict or string
    format
    """
    if keys:
        if not string_fmt:
            return dict(zip(keys, list(data.values())[0]['Value'].values()))
        else:
            map_values = dict(zip(keys, list(data.values())[0]['Value'].values()))
            if one_line:
                return sep.join(["{}: {}".format(k, v) for k, v in map_values.items()])
            else:
                sep += "\n"
                return sep.join(["{}: {}".format(k, v) for k, v in map_values.items()])


def dict_char_value(data, raw=False):
    """
    Simplify the characteristic value in dict format
    """
    try:
        if raw:
            values = {
                k: {"Value": data[k]["Value"], "Symbol": data[k]["Symbol"]}
                for k in data
            }
        else:
            values = {
                k: "{} {}".format(data[k]["Value"], data[k]["Symbol"]) for k in data
            }
    except Exception as e:
        values = {}
        if raw:
            for k in data:
                if "Symbol" in data[k]:
                    values[k] = {"Value": data[k]["Value"], "Symbol": data[k]["Symbol"]}
                else:
                    values[k] = {"Value": data[k]["Value"]}
        else:
            for k in data:
                if "Symbol" in data[k]:
                    values[k] = "{} {}".format(data[k]["Value"], data[k]["Symbol"])
                else:
                    values[k] = data[k]["Value"]
    return values


def pformat_char_flags(data, sep="\n", prnt=False, rtn=True):
    """
    Print or return the characteristic flag in string format
    """
    try:
        char_string_values = [
            ["{}: {}".format(k, v) for k, v in data[key].items()] for key in data
        ]
        all_values = []
        for values in char_string_values:
            if prnt:
                print(sep.join(values))
            elif rtn:
                all_values.append(sep.join(values))
        if rtn:
            return sep.join(all_values)

    except Exception as e:
        print(e)
