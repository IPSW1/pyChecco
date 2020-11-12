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


from typing import Tuple, List, Dict
from bytecode import Instr

from pyChecco.execution.codeobjectmetadata import CodeObjectMetaData
from pyChecco.execution.executiontrace import ExecutionTrace
from pyChecco.instrumentation.instruction_instrumentation import OP_CALL, OP_RETURN, is_traced_instruction
from pyChecco.slicer.instruction import UniqueInstruction
from pyChecco.execution.executed_instruction import ExecutedInstruction
from pyChecco.utils.exceptions import InstructionNotFoundException
from pyChecco.utils.opcodes import *


class LastInstrState:
    """
    When the execution flow is reconstructed with traced instructions there are some events which can
    happen between instructions, e.g. a switch to a different code object with a function call.

    All relevant information required to keep track of the exact location of the flow is represented here.
    """

    def __init__(self, file: str, last_instr: Instr, code_object_id: int, basic_block_id: int, offset: int,
                 jump: bool = False, call: bool = False, returned: bool = False, exception: bool = False,
                 import_start: bool = False, import_back_call: UniqueInstruction = None) -> None:
        self.file = file
        self.last_instr = last_instr
        self.code_object_id = code_object_id
        self.basic_block_id = basic_block_id
        self.offset = offset
        self.jump = jump
        self.call = call
        self.returned = returned
        self.exception = exception
        self.import_start = import_start
        self.import_back_call = import_back_call


class ExecutionFlowBuilder:
    """
    The ExecutionFlowBuilder reconstructs the execution flow of a program run (backwards!) with the help
    of an execution trace.
    The trace must contain instructions relevant for the control flow of the specific execution.

    Note: The solution here is designed to provide a last instruction whenever possible. That means, whenever
    there is an unexpected mismatch between expected and real last traced instruction, it is assumed that
    an exception occurred and the flow is continued at the last traced instruction.
    """

    def __init__(self, trace: ExecutionTrace, known_code_objects: Dict[int, CodeObjectMetaData]):
        self.trace = trace
        self.known_code_objects = known_code_objects

    def get_last_instruction(self, file: str, instr: Instr, trace_pos: int, offset: int, co_id: int,
                             bb_id: int, import_instr: UniqueInstruction = None) -> LastInstrState:
        """
        Look for the last instruction that must have been executed before ``instr``.

        :param file: File of parameter instr
        :param instr: Instruction for which the instruction executed beforehand is searched.
        :param trace_pos: Position in the execution trace where instr occurs (or, in case it is not a traced one,
            the position of the last instruction traced before instr)
        :param offset: Offset of instr in the basic block
        :param co_id: Code object id of instr
        :param bb_id: Basic block id of instr
        :param import_instr: This instruction is necessary if the execution of ``instr`` is caused
            directly (i.e. no calls in between) by an IMPORT_NAME instruction. The argument is this import instruction.
        :return:
        """

        # Find the basic block and the exact location of the current instruction
        basic_block, bb_offset = self._get_basic_block(co_id, bb_id)
        instr_index = self.locate_in_basic_block(instr, offset, basic_block, bb_offset)

        #
        # Special case: if there are not remaining instructions in the trace, finish this basic block
        #
        if trace_pos < 0:
            # This is the last location where instructions must be reconstructed, so it is either the end or
            # there are remaining instruction in the same code object (and no jump since this would have been traced.)
            if instr_index > 0:
                # Instruction has exactly one possible predecessor
                last_instr = basic_block[instr_index - 1]
                offset -= 2
            else:
                last_instr, offset, bb_id = self._continue_at_last_basic_block(offset, co_id, bb_id)

            # Special case inside the special case. Imports are "special calls": the instructions on the
            # module level of the imported module are executed before the IMPORT_NAME instruction ("import back call").
            # This case is the end of these module instructions and we continue before the IMPORT_NAME.
            if not last_instr and import_instr:
                file, last_instr, co_id, bb_id, offset = self._continue_before_import(import_instr)
                return LastInstrState(file, last_instr, co_id, bb_id, offset, import_start=True)

            return LastInstrState(file, last_instr, co_id, bb_id, offset)

        # Variables to keep track of what happened
        jump = False
        call = False
        returned = False
        exception = False
        import_start = False
        import_back_call = False

        # Get the current instruction in the disassembly for further information
        unique_instr = self._create_unique_instruction(file, instr, co_id, bb_id, offset)

        # Get the instruction last in the trace
        last_traced_instr = self.trace.executed_instructions[trace_pos]

        #
        # Determine last instruction
        #
        if instr_index > 0:
            # Instruction has exactly one possible predecessor
            last_instr = basic_block[instr_index - 1]
            offset -= 2
        else:
            # Instruction is the last instruction in this basic block -> decide what to do with this instruction
            if unique_instr.is_jump_target:
                # The instruction is a jump target, check if it was jumped to
                if last_traced_instr.is_jump() and last_traced_instr.argument == bb_id:
                    # It was jumped to this instruction, continue with target basic block of last traced
                    assert co_id == last_traced_instr.code_object_id, \
                        "Jump to instruction must originate from same code object"
                    file, last_instr, offset, co_id, bb_id = self._continue_at_last_traced(last_traced_instr)
                    jump = True
                else:
                    # If this is not a jump target, proceed with previous block (in case there is one)
                    last_instr, offset, bb_id = self._continue_at_last_basic_block(offset, co_id, bb_id)
            else:
                # If this is not a jump target, proceed with previous block (in case there is one)
                last_instr, offset, bb_id = self._continue_at_last_basic_block(offset, co_id, bb_id)

        # Handle return instruction
        if last_traced_instr.opcode in OP_RETURN:
            if not instr.opcode == IMPORT_NAME:
                # Coming back from a method call. If last_instr is a call, then the method was called explicitly.
                # If last_instr is not a call, but is traced and does not match the last instruction in the trace,
                # there must have been an implicit call to a magic method (such as __get__). Since we collect
                # instructions invoking these methods, we can safely switch to the called method.
                if last_instr:
                    if (last_instr.opcode in OP_CALL) or \
                            (is_traced_instruction(last_instr) and last_instr.opcode != last_traced_instr.opcode):
                        file, last_instr, offset, co_id, bb_id = self._continue_at_last_traced(last_traced_instr)
                        returned = True

                else:
                    # Edge case: reached the end of a method, but there is neither a call nor any previous instruction.
                    # Can happen for example with setUp(), i.e. when no calls but multiple methods are involved.
                    # The only way to resolve this is to continue at the last traced instruction (RETURN).
                    file, last_instr, offset, co_id, bb_id = self._continue_at_last_traced(last_traced_instr)
                    returned = True
            else:
                # Imports are "special calls": The instructions on the module level of the imported module are
                # executed before the IMPORT_NAME instruction. We call this an "import back call" here.
                file, last_instr, offset, co_id, bb_id = self._continue_at_last_traced(last_traced_instr)
                import_back_call = unique_instr
                returned = True

        # Handle method invocation
        if not last_instr:
            # There is not last instruction in code object, so there must have been a call.
            call = True
            if not import_instr:
                # Switch to another function/method.
                # Either an explicit call (when the last traced is a call instruction), or an implicit call
                # to a magic method. In both cases tracing is continued at the caller.
                file, last_instr, offset, co_id, bb_id = self._continue_at_last_traced(last_traced_instr)
            else:
                # Imports are "special calls": the instructions on the module level of the imported
                # module are executed before the IMPORT_NAME instruction ("import back call").
                # This case is the end of these module instructions and we continue before the IMPORT_NAME.
                file, last_instr, co_id, bb_id, offset = self._continue_before_import(import_instr)
                import_start = True

        # Handle generators and exceptions
        if not call and not returned:
            if last_instr.opcode in [YIELD_VALUE, YIELD_FROM]:
                # Generators produce an unusual execution flow: the interpreter handles jumps to the respective
                # yield statement internally and we can not see this in the trace.
                # So we assume that this unusual case (explained in the next branch) is not an exception but
                # The return from a generator.
                file, last_instr, offset, co_id, bb_id = self._continue_at_last_traced(last_traced_instr)

            elif last_instr and (is_traced_instruction(last_instr)) and last_instr.opcode != last_traced_instr.opcode:
                # The last instruction that is determined is not in the trace, despite the fact that it should be.
                # There is only one known remaining reasons for this: during an exception.
                # Tracing continues with the last traced instruction (and probably misses some in between).
                file, last_instr, offset, co_id, bb_id = self._continue_at_last_traced(last_traced_instr)
                exception = True

        return LastInstrState(file, last_instr, co_id, bb_id, offset=offset, jump=jump, call=call, returned=returned,
                              exception=exception, import_start=import_start, import_back_call=import_back_call)

    def _create_unique_instruction(self, module: str, instr: Instr, code_object_id: int, node_id: int, offset: int) \
            -> UniqueInstruction:
        code_meta = self.known_code_objects.get(code_object_id)
        return UniqueInstruction(module, instr.name, instr.arg, instr.lineno, code_object_id, node_id, code_meta,
                                 offset)

    def _continue_at_last_traced(self, last_traced_instr: ExecutedInstruction):
        file = last_traced_instr.file
        curr_code_object_id = last_traced_instr.code_object_id
        curr_basic_block_id = last_traced_instr.node_id
        last_instr = self._locate_traced_in_bytecode(last_traced_instr)
        new_offset = last_traced_instr.offset

        return file, last_instr, new_offset, curr_code_object_id, curr_basic_block_id

    def _continue_at_last_basic_block(self, offset: int, code_object_id: int, basic_block_id: int) -> \
            Tuple[Instr, int, int]:
        last_instr = None

        if basic_block_id > 0:
            basic_block_id = basic_block_id - 1
            last_instr = self._get_last_in_basic_block(code_object_id, basic_block_id)
            offset -= 2

        return last_instr, offset, basic_block_id

    def _continue_before_import(self, import_instr: UniqueInstruction):
        co_id = import_instr.code_object_id
        bb_id = import_instr.node_id
        offset = import_instr.offset
        instr = Instr(import_instr.name, arg=import_instr.arg, lineno=import_instr.lineno)

        # Find the basic block and the exact location of the current instruction
        basic_block, bb_offset = self._get_basic_block(co_id, bb_id)
        instr_index = self.locate_in_basic_block(instr, offset, basic_block, bb_offset)

        if instr_index > 0:
            # Instruction has exactly one possible predecessor
            last_instr = basic_block[instr_index - 1]
            offset -= 2
        else:
            last_instr, offset, bb_id = self._continue_at_last_basic_block(offset, co_id, bb_id)

        return import_instr.file, last_instr, co_id, bb_id, offset

    def _get_last_in_basic_block(self, code_object_id: int, basic_block_id: int) -> Instr:
        # Locate basic block in CFG to which instruction belongs
        for node in self.known_code_objects.get(code_object_id).original_cfg.nodes:
            if node.index == basic_block_id:
                return node.basic_block[-1]

    def _get_basic_block(self, code_object_id: int, basic_block_id: int) -> (List[Instr], int):
        """
        Locates the basic block in CFG to which the current state (i.e. the last instruction) belongs.

        :return: Tuple of the current basic block and the offset of the first instruction in the basic block
        """
        for node in self.known_code_objects.get(code_object_id).original_cfg.nodes:
            if node.index == basic_block_id:
                return node.basic_block, node.offset

        raise InstructionNotFoundException

    def _locate_traced_in_bytecode(self, instr: ExecutedInstruction) -> Instr:
        basic_block, bb_offset = self._get_basic_block(instr.code_object_id, instr.node_id)

        for instruction in basic_block:
            if instr.opcode == instruction.opcode and instr.lineno == instruction.lineno and \
                    instr.offset == bb_offset:
                return instruction
            bb_offset += 2

        raise InstructionNotFoundException

    @staticmethod
    def locate_in_basic_block(instr: Instr, instr_offset: int, basic_block: List[Instr], bb_offset: int) -> int:
        """
        Searches for the location (that is the index) of the instruction in the given basic block.

        :param instr: Instruction to be searched for
        :param instr_offset: Offset of instr
        :param basic_block: Basic block where instr is located
        :param bb_offset: Offset of the first instruction in basic_block
        :return: Index of instr in basic_block
        """
        for index, instruction in enumerate(basic_block):
            if instruction == instr and instr_offset == bb_offset:
                return index
            bb_offset += 2

        raise InstructionNotFoundException
