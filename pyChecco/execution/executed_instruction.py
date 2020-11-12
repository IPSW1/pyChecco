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


from opcode import opname


class ExecutedInstruction:
    """Represents an executed bytecode instruction with additional information."""

    def __init__(self, file: str, code_object_id: int, node_id: int, opcode: int, arg, lineno: int, offset: int):
        self.file = file
        self.code_object_id = code_object_id
        self.node_id = node_id
        self.opcode = opcode
        self.argument = arg
        self.lineno = lineno
        self.offset = offset

    @property
    def name(self):
        return opname[self.opcode]

    def is_jump(self) -> bool:
        return False

    def __str__(self) -> str:
        return "%-7s %-40s %-72s %02d @ line: %d-%d" % ("(-)", self.file, opname[self.opcode], self.code_object_id,
                                                        self.lineno, self.offset)


class ExecutedMemoryInstruction(ExecutedInstruction):
    """Represents an executed instructions which read from or wrote to memory."""

    def __init__(self, file: str, code_object_id: int, node_id: int, opcode: int, lineno: int, offset: int,
                 arg_name: str, arg_address: int, is_mutable_type: bool, object_creation: bool) -> None:
        super().__init__(file, code_object_id, node_id, opcode, arg_name, lineno, offset)
        self.arg_address = arg_address
        self.is_mutable_type = is_mutable_type
        self.object_creation = object_creation

    def __str__(self) -> str:
        if not self.arg_address:
            arg_address = -1
        else:
            arg_address = self.arg_address
        return "%-7s %-40s %-20s %-25s %-25s %02d @ line: %d-%d" % ("(mem)", self.file, opname[self.opcode],
                                                                    self.argument, hex(arg_address),
                                                                    self.code_object_id, self.lineno, self.offset)


class ExecutedAttributeInstruction(ExecutedInstruction):
    """
    Represents an executed instructions which accessed an attribute.

    We prepend each accessed attribute with the address of the object the attribute is taken from. This allows
    to build correct def-use pairs during backward traversal.
    """

    def __init__(self, file: str, code_object_id: int, node_id: int, opcode: int, lineno: int, offset: int,
                 attr_name: str, src_address: int, arg_address: int, is_mutable_type: bool) -> None:
        super().__init__(file, code_object_id, node_id, opcode, attr_name, lineno, offset)
        self.src_address = src_address
        self.combined_attr = hex(self.src_address) + "_" + self.argument
        self.arg_address = arg_address
        self.is_mutable_type = is_mutable_type

    def __str__(self) -> str:
        return "%-7s %-40s %-20s %-51s %02d @ line: %d-%d" % ("(attr)", self.file, opname[self.opcode],
                                                              self.combined_attr, self.code_object_id, self.lineno,
                                                              self.offset)


class ExecutedControlInstruction(ExecutedInstruction):
    """Represents an executed control flow instruction."""

    def __init__(self, file: str, code_object_id: int, node_id: int, opcode: int, lineno: int, offset: int,
                 arg: int) -> None:
        super().__init__(file, code_object_id, node_id, opcode, arg, lineno, offset)

    def is_jump(self) -> bool:
        return True

    def __str__(self) -> str:
        return "%-7s %-40s %-20s %-51s %02d @ line: %d-%d" % ("(crtl)", self.file, opname[self.opcode],
                                                              self.argument, self.code_object_id, self.lineno,
                                                              self.offset)


class ExecutedCallInstruction(ExecutedInstruction):
    def __init__(self, file: str, code_object_id: int, node_id: int, opcode: int, lineno: int, offset: int,
                 arg: int) -> None:
        super().__init__(file, code_object_id, node_id, opcode, arg, lineno, offset)

    def __str__(self) -> str:
        return "%-7s %-40s %-72s %02d @ line: %d-%d" % ("(func)", self.file, opname[self.opcode], self.code_object_id,
                                                        self.lineno, self.offset)


class ExecutedReturnInstruction(ExecutedInstruction):
    def __init__(self, module: str, code_object_id: int, node_id: int, opcode: int, lineno: int, offset: int) -> None:
        super().__init__(module, code_object_id, node_id, opcode, None, lineno, offset)

    def __str__(self) -> str:
        return "%-7s %-40s %-72s %02d @ line: %d-%d" % ("(ret)", self.file, opname[self.opcode], self.code_object_id,
                                                        self.lineno, self.offset)
