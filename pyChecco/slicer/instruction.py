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


import dis

from typing import Optional
from bytecode import Instr

from pyChecco.execution.codeobjectmetadata import CodeObjectMetaData
from pyChecco.utils.exceptions import InstructionNotFoundException
from pyChecco.utils.opcodes import *

MEMORY_USE_INSTRUCTIONS = [LOAD_FAST, LOAD_NAME, LOAD_GLOBAL, LOAD_ATTR, LOAD_DEREF, BINARY_SUBSCR,
                           LOAD_METHOD, IMPORT_FROM, LOAD_CLOSURE, LOAD_CLASSDEREF]
MEMORY_DEF_INSTRUCTIONS = [STORE_FAST, STORE_NAME, STORE_GLOBAL, STORE_DEREF, STORE_ATTR, STORE_SUBSCR,
                           BINARY_SUBSCR,
                           DELETE_FAST, DELETE_NAME, DELETE_GLOBAL, DELETE_ATTR, DELETE_SUBSCR, DELETE_DEREF,
                           IMPORT_NAME]  # compensate incorrect stack effect for IMPORT_NAME
COND_BRANCH_INSTRUCTIONS = [POP_JUMP_IF_TRUE, POP_JUMP_IF_FALSE, JUMP_IF_TRUE_OR_POP, JUMP_IF_FALSE_OR_POP,
                            FOR_ITER]

UNSET = object()


class UniqueInstruction(Instr):
    """
    The UniqueInstruction is a representation for concrete occurrences of instructions.
    It combines multiple information sources, including the corresponding instruction in the disassembly.
    """

    def __init__(self, file: str, name: str, arg=UNSET, lineno: int = None, code_object_id: int = -1,
                 node_id: int = -1, code_meta: CodeObjectMetaData = None, offset: int = -1,
                 in_slice: Optional[bool] = False):
        self.file = file
        if arg is not UNSET:
            super().__init__(name, arg, lineno=lineno)
        else:
            super().__init__(name, lineno=lineno)
        self.code_object_id = code_object_id
        self.node_id = node_id
        self.offset = offset

        # Additional information from disassembly
        dis_instr = self.locate_in_disassembly(code_meta.disassembly)
        self.dis_arg = dis_instr.arg
        self.is_jump_target = dis_instr.is_jump_target

        self._in_slice = in_slice

    def set_in_slice(self) -> None:
        self._in_slice = True

    def in_slice(self) -> bool:
        return self._in_slice

    def is_def(self) -> bool:
        return self.opcode in MEMORY_DEF_INSTRUCTIONS

    def is_use(self) -> bool:
        return self.opcode in MEMORY_USE_INSTRUCTIONS

    def is_cond_branch(self) -> bool:
        return self.opcode in COND_BRANCH_INSTRUCTIONS

    def locate_in_disassembly(self, disassembly) -> dis.Instruction:
        # EXTENDED_ARG instructions are not counted for instrumented offsets, which has to be
        # compensated here
        offset_offset = 0

        for dis_instr in disassembly:
            if dis_instr.opcode == EXTENDED_ARG:
                offset_offset += 2

            if dis_instr.opcode == self.opcode and dis_instr.offset == (self.offset + offset_offset):
                return dis_instr

        raise InstructionNotFoundException

    def __hash__(self):
        return hash((self.name, self.code_object_id, self.node_id, self.offset))
