"""Lightweight websocket payload validation utilities.

Avoids external dependencies; provides minimal schema-like checking with
clear, consistent error responses. Intended for pre-1.0 internal use.

Design goals:
- Zero third-party deps (keep footprint small in early stage).
- Fast, small, explicit; not a general JSON Schema implementation.
- Return (ok, value_or_error) tuples; caller decides whether to emit an error event.

Schema Mini-Language (Python dict):
{
  'field_name': ('type', required: bool, extras: dict)
}
Supported types: 'str', 'int', 'list', 'dict'
Extras examples:
  max_len (for str), min_len (str), allow_empty (str)
  item_type (list element primitive type)

Example:
 schema = {
   'message': ('str', True, {'max_len': 500, 'min_len': 1})
 }
 ok, data_or_err = validate(data, schema)

If invalid: (False, {'field': 'message', 'error': 'too long', 'code': 'max_len'})
If valid: (True, normalized_data)
"""
from __future__ import annotations
from typing import Any, Dict, Tuple

PRIMITIVES = {
    'str': str,
    'int': int,
    'list': list,
    'dict': dict,
}

class ValidationError(Exception):
    def __init__(self, field: str, message: str, code: str):
        super().__init__(message)
        self.field = field
        self.message = message
        self.code = code


def _fail(field: str, message: str, code: str) -> Tuple[bool, Dict[str, Any]]:
    return False, {'field': field, 'error': message, 'code': code}


def validate(payload: Any, schema: Dict[str, tuple]) -> Tuple[bool, Dict[str, Any]]:
    if not isinstance(payload, dict):
        return _fail('__root__', 'payload must be an object', 'type')
    out = {}
    for name, spec in schema.items():
        if not isinstance(spec, tuple) or len(spec) < 2:
            return _fail('__schema__', f'invalid spec for {name}', 'schema')
        type_name, required = spec[0], spec[1]
        extras = spec[2] if len(spec) > 2 else {}
        if type_name not in PRIMITIVES:
            return _fail('__schema__', f'unsupported type {type_name}', 'schema')
        if name not in payload:
            if required:
                return _fail(name, 'missing required field', 'required')
            else:
                continue
        value = payload[name]
        py_type = PRIMITIVES[type_name]
        if not isinstance(value, py_type):
            return _fail(name, f'expected {type_name}', 'type')
        if type_name == 'str':
            s = value.strip() if not extras.get('allow_empty') else value
            if not extras.get('allow_empty') and len(s) == 0:
                return _fail(name, 'must not be empty', 'empty')
            if 'max_len' in extras and len(value) > extras['max_len']:
                return _fail(name, 'too long', 'max_len')
            if 'min_len' in extras and len(value) < extras['min_len']:
                return _fail(name, 'too short', 'min_len')
            out[name] = value if extras.get('preserve_whitespace') else s
        elif type_name == 'int':
            out[name] = value
        elif type_name == 'list':
            item_type = extras.get('item_type')
            if item_type:
                it = PRIMITIVES.get(item_type)
                if not it:
                    return _fail('__schema__', f'unsupported item_type {item_type}', 'schema')
                for idx, elem in enumerate(value):
                    if not isinstance(elem, it):
                        return _fail(name, f'element {idx} not {item_type}', 'item_type')
            out[name] = value
        elif type_name == 'dict':
            out[name] = value
    return True, out

# Predefined schemas used by handlers
LOBBY_CHAT_MESSAGE = {
    'message': ('str', True, {'min_len': 1, 'max_len': 500})
}
ADMIN_BROADCAST = {
    'target': ('str', False, {'min_len': 1, 'max_len': 32}),
    'message': ('str', True, {'min_len': 1, 'max_len': 500})
}
JOIN_GAME = {
    'room': ('str', True, {'min_len': 1, 'max_len': 64})
}
LEAVE_GAME = JOIN_GAME
GAME_ACTION = {
    'room': ('str', True, {'min_len': 1, 'max_len': 64}),
    'action': ('str', True, {'min_len': 1, 'max_len': 64})
}
