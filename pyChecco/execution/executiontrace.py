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


from typing import List, Set, Optional

import pyChecco.execution.executed_instruction as ei

from pyChecco.utils.opcodes import *


class TracedAssertion:
    def __init__(self, code_object_id: int, node_id: int, lineno: int, trace_position_start: int,
                 traced_assertion_call: Optional[ei.ExecutedInstruction] = None) -> None:
        self.code_object_id = code_object_id
        self.node_id = node_id
        self.lineno = lineno
        self.trace_position_start = trace_position_start

        self.trace_position_end = -1
        self.traced_assertion_call = traced_assertion_call


class UniqueAssertion:
    def __init__(self, assertion_call_instruction: ei.ExecutedInstruction):
        self.assertion_call_instruction = assertion_call_instruction

    def __eq__(self, other):
        if not isinstance(other, UniqueAssertion):
            return False

        if self.assertion_call_instruction.code_object_id == other.assertion_call_instruction.code_object_id and \
                self.assertion_call_instruction.node_id == other.assertion_call_instruction.node_id and \
                self.assertion_call_instruction.lineno == other.assertion_call_instruction.lineno and \
                self.assertion_call_instruction.offset == other.assertion_call_instruction.offset:
            return True
        else:
            return False

    def __hash__(self):
        hash_string = str(self.assertion_call_instruction.code_object_id) + "_" + \
               str(self.assertion_call_instruction.node_id) + "_" + \
               str(self.assertion_call_instruction.lineno) + "_" + \
               str(self.assertion_call_instruction.offset) + "_"

        return hash(hash_string)

    def __str__(self):
        return str(self.assertion_call_instruction.lineno)


class ExecutionTrace:
    """Stores trace information about the execution."""

    def __init__(self, module: bool = False):
        self.test_id = None
        self.module_name = None
        self.module = module
        self.executed_instructions: List[ei.ExecutedInstruction] = list()

        self.traced_assertions: List[TracedAssertion] = list()
        self.unique_assertions: Set[UniqueAssertion] = set()
        self._current_assertion: Optional[TracedAssertion] = None

    def add_instruction(self, module: str, code_object_id: int, node_id: int, opcode: int, lineno: int,
                        offset: int) -> None:
        executed_instr = ei.ExecutedInstruction(module, code_object_id, node_id, opcode, None, lineno, offset)
        self.executed_instructions.append(executed_instr)

    def add_memory_instruction(self, module: str, code_object_id: int, node_id: int, opcode: int, lineno: int,
                               offset: int, arg_name: str, arg_address: int, is_mutable_type: bool,
                               object_creation: bool) -> None:
        executed_instr = ei.ExecutedMemoryInstruction(module, code_object_id, node_id, opcode, lineno, offset,
                                                      arg_name, arg_address, is_mutable_type, object_creation)
        self.executed_instructions.append(executed_instr)

    def add_attribute_instruction(self, module: str, code_object_id: int, node_id: int, opcode: int, lineno: int,
                                  offset: int, attr_name: str, src_address: int, arg_address: int,
                                  is_mutable_type: bool) -> None:
        executed_instr = ei.ExecutedAttributeInstruction(module, code_object_id, node_id, opcode, lineno, offset,
                                                         attr_name, src_address, arg_address, is_mutable_type)
        self.executed_instructions.append(executed_instr)

    def add_jump_instruction(self, module: str, code_object_id: int, node_id: int, opcode: int, lineno: int,
                             offset: int, target_id: int) -> None:
        executed_instr = ei.ExecutedControlInstruction(module, code_object_id, node_id, opcode, lineno, offset,
                                                       target_id)
        self.executed_instructions.append(executed_instr)

    def add_call_instruction(self, module: str, code_object_id: int, node_id: int, opcode: int, lineno: int,
                             offset: int, arg: int) -> None:
        executed_instr = ei.ExecutedCallInstruction(module, code_object_id, node_id, opcode, lineno, offset, arg)

        self.executed_instructions.append(executed_instr)

    def add_return_instruction(self, module: str, code_object_id: int, node_id: int, opcode: int, lineno: int,
                               offset: int) -> None:
        executed_instr = ei.ExecutedReturnInstruction(module, code_object_id, node_id, opcode, lineno, offset)

        self.executed_instructions.append(executed_instr)

    def start_assertion(self, code_object_id: int, node_id: int, lineno: int) -> TracedAssertion:
        self._current_assertion = TracedAssertion(code_object_id, node_id, lineno, len(self.executed_instructions) - 1)
        return self._current_assertion

    def end_assertion(self):
        assert self._current_assertion.traced_assertion_call
        assert self._current_assertion.traced_assertion_call.opcode in [CALL_METHOD, CALL_FUNCTION_KW, CALL_FUNCTION_EX]
        assert self._current_assertion.trace_position_end > 0

        self.traced_assertions.append(self._current_assertion)
        self.unique_assertions.add(UniqueAssertion(self._current_assertion.traced_assertion_call))

        self._current_assertion = None

    def set_test_id(self, test_id: str) -> None:
        self.test_id = test_id

    def set_module_name(self, module_name: str) -> None:
        self.module_name = module_name

    def print_trace(self, debug_output: int = 0):
        if debug_output > 0:
            print("\n" + str(len(self.traced_assertions)) + " assertion call(s)")

            if debug_output > 1:
                print("------ Execution Trace ------")
                for instr in self.executed_instructions:
                    print(instr)
            print()
