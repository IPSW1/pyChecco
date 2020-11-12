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


from typing import List, Set, Tuple, Optional

from pyChecco.slicer.instruction import UniqueInstruction
from pyChecco.utils.opcodes import *


DEFAULT_STACK_HEIGHT = 40
DEFAULT_FRAME_HEIGHT = 40


class BlockStack(list):
    """Represents the stack for a block in a frame."""

    def push(self, instr: UniqueInstruction) -> None:
        self.append(instr)

    def peek(self) -> Optional[UniqueInstruction]:
        try:
            return self[-1]
        except IndexError:
            return None


class FrameStack:
    """Represents the stack for a frame in the frame stack of frames."""

    def __init__(self, code_object_id: int, block_stacks: List[BlockStack]):
        self.code_object_id = code_object_id
        self.block_stacks: List[BlockStack] = block_stacks
        self.attribute_uses = set()
        self.import_name_instr: Optional[UniqueInstruction] = None
        super().__init__()


class TraceStack:
    def __init__(self):
        self.frame_stacks: List[FrameStack] = list()
        self._reset()
        self._prepare_stack()

    def _reset(self) -> None:
        self.frame_stacks.clear()

    def _prepare_stack(self) -> None:
        # Since we do not exactly know what the stack state at the slicing criterion is
        # and because the behavior is reversed, we fill the stack with some frames (having some
        # block stacks inside them.
        for _ in range(0, DEFAULT_STACK_HEIGHT):
            frame_stack = FrameStack(-1, [])
            for _ in range(0, DEFAULT_FRAME_HEIGHT):
                block_stack = BlockStack([])
                frame_stack.block_stacks.append(block_stack)
            self.frame_stacks.append(frame_stack)

    def push_stack(self, code_object_id: int) -> None:
        self.frame_stacks.append(FrameStack(code_object_id, [BlockStack([])]))

    def push_artificial_stack(self) -> None:
        self.push_stack(code_object_id=-1)

    def pop_stack(self) -> None:
        # TOS from the frame stack is popped
        frame = self.frame_stacks.pop()
        if frame.code_object_id != -1:
            # A non-dummy frame can only have one block_stack at the end of execution
            assert len(frame.block_stacks) == 1, "More than one block on a popped stack"

            # # Last block stack in the non-dummy frame must be empty
            # block = frame.block_stacks.pop()
            # assert len(block) == 0, "Remaining instructions in a popped block"

    def update_push_operations(self, num_pushes: int, returned: bool) -> Tuple[bool, bool]:
        curr_frame_stack = self.frame_stacks[-1]
        curr_block_stack = curr_frame_stack.block_stacks[-1]

        imp_dependency = False
        include_use = True

        if returned:
            prev_frame_stack = self.frame_stacks[-2]
            prev_block_stack = prev_frame_stack.block_stacks[-1]
            if prev_block_stack.peek() and prev_block_stack.peek().in_slice():
                imp_dependency = True

        # Handle push operations
        for _ in range(0, num_pushes):
            try:
                tos_instr = curr_block_stack.pop()
            except IndexError:
                # Started backward tracing not at the end of execution. In forward direction this
                # corresponds to popping from an empty stack when starting the execution at an arbitrary point.
                # For slicing this can of course happen all the time, so this is not a problem
                tos_instr = None

            if tos_instr and tos_instr.in_slice():
                imp_dependency = True

                # For attribute accesses, instructions preparing TOS to access the attribute should be included.
                # However, the use data for these will not be searched for, since this would widen the scope of
                # the search for complete objects rather than only for the attribute thereof.
                if tos_instr.opcode in [STORE_ATTR, STORE_SUBSCR]:
                    if len(curr_block_stack) > 0:
                        tos1_instr = curr_block_stack.peek()
                        if tos1_instr.opcode == tos_instr.opcode:
                            include_use = False
                if tos_instr.opcode in [LOAD_ATTR, DELETE_ATTR, IMPORT_FROM]:
                    include_use = False

        return imp_dependency, include_use

    def update_pop_operations(self, num_pops: int, unique_instr: UniqueInstruction, in_slice: bool) -> None:
        curr_frame_stack = self.frame_stacks[-1]
        curr_block_stack = curr_frame_stack.block_stacks[-1]

        if in_slice:
            unique_instr.set_in_slice()

        # Handle pop operations
        for _ in range(0, num_pops):
            curr_block_stack.push(unique_instr)

    def set_attribute_uses(self, attribute_uses: Set[str]):
        self.frame_stacks[-1].attribute_uses = set()
        for attr in attribute_uses:
            self.frame_stacks[-1].attribute_uses.add(attr)

    def get_attribute_uses(self):
        return self.frame_stacks[-1].attribute_uses

    def get_import_frame(self) -> UniqueInstruction:
        return self.frame_stacks[-1].import_name_instr

    def set_import_frame(self, import_name_instr: UniqueInstruction):
        self.frame_stacks[-1].import_name_instr = import_name_instr
