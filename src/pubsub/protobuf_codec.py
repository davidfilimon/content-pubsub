from __future__ import annotations

"""
Small Protocol Buffers wire-format codec for Publication messages.

Binary schema used for publisher -> broker:
  1 uint64 publication_id
  2 uint64 created_ns
  3 string company
  4 double value
  5 double drop
  6 double variation
  7 string date
  8 string source
"""

import struct
from typing import Dict, Tuple

from .models import Publication

WIRE_VARINT = 0
WIRE_FIXED64 = 1
WIRE_LEN = 2


def _encode_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("varint value must be non-negative")
    out = bytearray()
    while True:
        to_write = value & 0x7F
        value >>= 7
        if value:
            out.append(to_write | 0x80)
        else:
            out.append(to_write)
            break
    return bytes(out)


def _decode_varint(data: bytes, pos: int) -> Tuple[int, int]:
    shift = 0
    result = 0
    while True:
        if pos >= len(data):
            raise ValueError("truncated varint")
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, pos
        shift += 7
        if shift > 70:
            raise ValueError("varint too long")


def _tag(field_number: int, wire_type: int) -> bytes:
    return _encode_varint((field_number << 3) | wire_type)


def _string_field(field_number: int, value: str) -> bytes:
    raw = value.encode("utf-8")
    return _tag(field_number, WIRE_LEN) + _encode_varint(len(raw)) + raw


def _uint64_field(field_number: int, value: int) -> bytes:
    return _tag(field_number, WIRE_VARINT) + _encode_varint(value)


def _double_field(field_number: int, value: float) -> bytes:
    return _tag(field_number, WIRE_FIXED64) + struct.pack("<d", value)


def serialize_publication(publication: Publication) -> bytes:
    return b"".join(
        [
            _uint64_field(1, publication.publication_id),
            _uint64_field(2, publication.created_ns),
            _string_field(3, publication.company),
            _double_field(4, publication.value),
            _double_field(5, publication.drop),
            _double_field(6, publication.variation),
            _string_field(7, publication.date),
            _string_field(8, publication.source),
        ]
    )


def deserialize_publication(data: bytes) -> Publication:
    pos = 0
    fields: Dict[int, object] = {}

    while pos < len(data):
        raw_tag, pos = _decode_varint(data, pos)
        field_number = raw_tag >> 3
        wire_type = raw_tag & 0x07

        if wire_type == WIRE_VARINT:
            value, pos = _decode_varint(data, pos)
            fields[field_number] = value
        elif wire_type == WIRE_FIXED64:
            if pos + 8 > len(data):
                raise ValueError("truncated fixed64 field")
            fields[field_number] = struct.unpack("<d", data[pos : pos + 8])[0]
            pos += 8
        elif wire_type == WIRE_LEN:
            length, pos = _decode_varint(data, pos)
            if pos + length > len(data):
                raise ValueError("truncated length-delimited field")
            fields[field_number] = data[pos : pos + length].decode("utf-8")
            pos += length
        else:
            raise ValueError(f"unsupported wire type: {wire_type}")

    required = [1, 2, 3, 4, 5, 6, 7, 8]
    missing = [field for field in required if field not in fields]
    if missing:
        raise ValueError(f"missing required Publication fields: {missing}")

    return Publication(
        publication_id=int(fields[1]),
        created_ns=int(fields[2]),
        company=str(fields[3]),
        value=float(fields[4]),
        drop=float(fields[5]),
        variation=float(fields[6]),
        date=str(fields[7]),
        source=str(fields[8]),
    )
