# This file is part of pyChecco.
# Copyright (C) 2020 Marco Reichenberger
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


POP_TOP = 1
ROT_TWO = 2
ROT_THREE = 3
DUP_TOP = 4
DUP_TOP_TWO = 5
ROT_FOUR = 6

NOP = 9
UNARY_POSITIVE = 10
UNARY_NEGATIVE = 11
UNARY_NOT = 12

UNARY_INVERT = 15

BINARY_MATRIX_MULTIPLY = 16
INPLACE_MATRIX_MULTIPLY = 17

BINARY_POWER = 19
BINARY_MULTIPLY = 20

BINARY_MODULO = 22
BINARY_ADD = 23
BINARY_SUBTRACT = 24
BINARY_SUBSCR = 25
BINARY_FLOOR_DIVIDE = 26
BINARY_TRUE_DIVIDE = 27
INPLACE_FLOOR_DIVIDE = 28
INPLACE_TRUE_DIVIDE = 29

GET_AITER = 50
GET_ANEXT = 51
BEFORE_ASYNC_WITH = 52
BEGIN_FINALLY = 53
END_ASYNC_FOR = 54
INPLACE_ADD = 55
INPLACE_SUBTRACT = 56
INPLACE_MULTIPLY = 57

INPLACE_MODULO = 59
STORE_SUBSCR = 60
DELETE_SUBSCR = 61
BINARY_LSHIFT = 62
BINARY_RSHIFT = 63
BINARY_AND = 64
BINARY_XOR = 65
BINARY_OR = 66
INPLACE_POWER = 67
GET_ITER = 68
GET_YIELD_FROM_ITER = 69

PRINT_EXPR = 70
LOAD_BUILD_CLASS = 71
YIELD_FROM = 72
GET_AWAITABLE = 73

INPLACE_LSHIFT = 75
INPLACE_RSHIFT = 76
INPLACE_AND = 77
INPLACE_XOR = 78
INPLACE_OR = 79
WITH_CLEANUP_START = 81
WITH_CLEANUP_FINISH = 82
RETURN_VALUE = 83
IMPORT_STAR = 84
SETUP_ANNOTATIONS = 85
YIELD_VALUE = 86
POP_BLOCK = 87
END_FINALLY = 88
POP_EXCEPT = 89

HAVE_ARGUMENT = 90

STORE_NAME = 90
DELETE_NAME = 91
UNPACK_SEQUENCE = 92
FOR_ITER = 93
UNPACK_EX = 94
STORE_ATTR = 95
DELETE_ATTR = 96
STORE_GLOBAL = 97
DELETE_GLOBAL = 98
LOAD_CONST = 100

LOAD_NAME = 101
BUILD_TUPLE = 102
BUILD_LIST = 103
BUILD_SET = 104
BUILD_MAP = 105
LOAD_ATTR = 106
COMPARE_OP = 107
IMPORT_NAME = 108
IMPORT_FROM = 109

JUMP_FORWARD = 110
JUMP_IF_FALSE_OR_POP = 111
JUMP_IF_TRUE_OR_POP = 112
JUMP_ABSOLUTE = 113
POP_JUMP_IF_FALSE = 114
POP_JUMP_IF_TRUE = 115

LOAD_GLOBAL = 116

SETUP_FINALLY = 122

LOAD_FAST = 124
STORE_FAST = 125
DELETE_FAST = 126

RAISE_VARARGS = 130
CALL_FUNCTION = 131
MAKE_FUNCTION = 132
BUILD_SLICE = 133
LOAD_CLOSURE = 135
LOAD_DEREF = 136
STORE_DEREF = 137
DELETE_DEREF = 138

CALL_FUNCTION_KW = 141
CALL_FUNCTION_EX = 142

SETUP_WITH = 143

LIST_APPEND = 145
SET_ADD = 146
MAP_ADD = 147

LOAD_CLASSDEREF = 148

EXTENDED_ARG = 144

BUILD_LIST_UNPACK = 149
BUILD_MAP_UNPACK = 150
BUILD_MAP_UNPACK_WITH_CALL = 151
BUILD_TUPLE_UNPACK = 152
BUILD_SET_UNPACK = 153

SETUP_ASYNC_WITH = 154

FORMAT_VALUE = 155
BUILD_CONST_KEY_MAP = 156
BUILD_STRING = 157
BUILD_TUPLE_UNPACK_WITH_CALL = 158

LOAD_METHOD = 160
CALL_METHOD = 161
CALL_FINALLY = 162
POP_FINALLY = 163
