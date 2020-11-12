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


# byteplay - Python bytecode assembler/disassembler.
# Copyright (C) 2006-2010 Noam Yorav-Raphael
# Homepage: http://code.google.com/p/byteplay
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA


from opcode import opname, opmap
from typing import Tuple

from pyChecco.utils.opcodes import *
from pyChecco.utils.exceptions import UncertainStackEffectException


class _SE:
    # Definition of stack effects is taken from byteplay (see license header) and modified for Python 3.8.
    # Stack effects are should match the combined effects in the CPython interpreter:
    # https://github.com/python/cpython/blob/3.8/Python/compile.c#L999
    NOP = 0, 0
    EXTENDED_ARG = 0, 0

    # Stack manipulation
    POP_TOP = 1, 0
    ROT_TWO = 2, 2
    ROT_THREE = 3, 3
    ROT_FOUR = 4, 4
    DUP_TOP = 1, 2
    DUP_TOP_TWO = 2, 4

    UNARY_POSITIVE = UNARY_NEGATIVE = UNARY_NOT = UNARY_INVERT = 1, 1

    SET_ADD = 2, 1
    LIST_APPEND = 1, 0
    MAP_ADD = 2, 0

    BINARY_POWER = BINARY_MULTIPLY = BINARY_MATRIX_MULTIPLY = BINARY_MODULO = BINARY_ADD = BINARY_SUBTRACT = \
        BINARY_SUBSCR = BINARY_FLOOR_DIVIDE = BINARY_TRUE_DIVIDE = 2, 1

    INPLACE_FLOOR_DIVIDE = INPLACE_TRUE_DIVIDE = 2, 1

    INPLACE_ADD = INPLACE_SUBTRACT = INPLACE_MULTIPLY = INPLACE_MATRIX_MULTIPLY = INPLACE_MODULO = 2, 1
    STORE_SUBSCR = 3, 0
    DELETE_SUBSCR = 2, 0

    BINARY_LSHIFT = BINARY_RSHIFT = BINARY_AND = BINARY_XOR = BINARY_OR = 2, 1
    INPLACE_POWER = 2, 1
    GET_ITER = 1, 1

    PRINT_EXPR = 1, 0
    LOAD_BUILD_CLASS = 0, 1
    INPLACE_LSHIFT = INPLACE_RSHIFT = INPLACE_AND = INPLACE_XOR = INPLACE_OR = 2, 1

    RETURN_VALUE = 1, 0
    IMPORT_STAR = 1, 0
    SETUP_ANNOTATIONS = 0, 0
    YIELD_VALUE = 1, 1
    YIELD_FROM = 2, 1
    POP_BLOCK = 0, 0
    POP_EXCEPT = 3, 0
    POP_FINALLY = END_FINALLY = 6, 0

    STORE_NAME = 1, 0
    DELETE_NAME = 0, 0

    STORE_ATTR = 2, 0
    DELETE_ATTR = 1, 0
    STORE_GLOBAL = 1, 0
    DELETE_GLOBAL = 0, 0
    LOAD_CONST = 0, 1
    LOAD_NAME = 0, 1
    LOAD_ATTR = 1, 1
    COMPARE_OP = 2, 1
    IMPORT_NAME = 2, 1
    IMPORT_FROM = 0, 1
    # 1, 2 would be more accurate, but this would cause a wider scope;
    # we compensate this by treating IMPORT_NAME as a definition -> connection is made via module memory address

    JUMP_FORWARD = 0, 0
    JUMP_ABSOLUTE = 0, 0

    POP_JUMP_IF_FALSE = 1, 0
    POP_JUMP_IF_TRUE = 1, 0

    LOAD_GLOBAL = 0, 1

    BEGIN_FINALLY = 0, 6

    LOAD_FAST = 0, 1
    STORE_FAST = 1, 0
    DELETE_FAST = 0, 0

    LOAD_CLOSURE = 0, 1
    LOAD_DEREF = LOAD_CLASSDEREF = 0, 1
    STORE_DEREF = 1, 0
    DELETE_DEREF = 0, 0

    GET_AWAITABLE = 1, 1
    BEFORE_ASYNC_WITH = 1, 2
    GET_AITER = 1, 1
    GET_ANEXT = 1, 2
    GET_YIELD_FROM_ITER = 1, 1

    LOAD_METHOD = 1, 2


class StackEffect:
    UNCERTAIN = [WITH_CLEANUP_START, WITH_CLEANUP_FINISH, SETUP_ASYNC_WITH, END_ASYNC_FOR, FORMAT_VALUE]
    STACK_MANIPULATION = [ROT_TWO, ROT_THREE, ROT_FOUR, DUP_TOP, DUP_TOP_TWO]

    # Lookup method is taken from byteplay (see license header) and modified for Python 3.8.
    _se = dict((opmap.get(op), getattr(_SE, op)) for op in opname if hasattr(_SE, op))

    @staticmethod
    def stack_effect(opcode: int, arg, jump: bool) -> Tuple[int, int]:
        if opcode in StackEffect.UNCERTAIN:
            raise UncertainStackEffectException("The opname " + str(opcode) + " has a special flow control")

        # Static stack effect
        if opcode in StackEffect._se:
            return StackEffect._se.get(opcode)

        # Instructions depending on jump
        if opcode == SETUP_WITH:
            if not jump:
                return 0, 1
            return 0, 6
        elif opcode == FOR_ITER:
            if not jump:
                return 1, 2
            return 1, 0
        elif opcode == JUMP_IF_TRUE_OR_POP or opcode == JUMP_IF_FALSE_OR_POP:
            if not jump:
                return 1, 0
            return 0, 0
        elif opcode == SETUP_FINALLY:
            if not jump:
                return 0, 0
            return 0, 6
        elif opcode == CALL_FINALLY:
            if not jump:
                return 0, 1
            return 0, 0

        # Instructions depending on argument
        if opcode == UNPACK_SEQUENCE:
            return 1, arg
        elif opcode == UNPACK_EX:
            return 1, (arg & 0xFF) + (arg >> 8) + 1
        elif opcode in [BUILD_TUPLE, BUILD_LIST, BUILD_SET, BUILD_STRING]:
            return arg, 1
        elif opcode in [BUILD_LIST_UNPACK, BUILD_TUPLE_UNPACK, BUILD_TUPLE_UNPACK_WITH_CALL, BUILD_SET_UNPACK,
                        BUILD_MAP_UNPACK, BUILD_MAP_UNPACK_WITH_CALL]:
            return arg, 1
        elif opcode == BUILD_MAP:
            return (2 * arg), 1
        elif opcode == BUILD_CONST_KEY_MAP:
            return (1 + arg), 1
        elif opcode == RAISE_VARARGS:
            return arg, 0
        elif opcode == CALL_FUNCTION:
            return (1 + arg), 1
        elif opcode == CALL_METHOD:
            return (2 + arg), 1
        elif opcode == CALL_FUNCTION_KW:
            return (2 + arg), 1
        elif opcode == CALL_FUNCTION_EX:
            # argument contains flags
            pops = 2
            if arg & 0x01 != 0:
                pops += 1
            return pops, 1
        elif opcode == MAKE_FUNCTION:
            # argument contains flags
            pops = 2
            if arg & 0x01 != 0:
                pops += 1
            if arg & 0x02 != 0:
                pops += 1
            if arg & 0x04 != 0:
                pops += 1
            if arg & 0x08 != 0:
                pops += 1
            return pops, 1
        elif opcode == BUILD_SLICE:
            if arg == 3:
                return 3, 1
            else:
                return 2, 1

        raise ValueError("The opcode " + str(opcode) + " isn't recognized.")
