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


# Idea and structure are taken from the Pynguin project, see:
# https://github.com/se2p/pynguin
# Modifications were made in various parts.


#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#


"""Provides capabilities to perform bytecode instruction instrumentation."""
import builtins
import logging
from types import CodeType
from typing import Dict, List, Optional, Union

import networkx as nx
from bytecode import Bytecode, ConcreteBytecode, Instr

from pyChecco.analyses.controlflow.cfg import CFG
from pyChecco.analyses.controlflow.controldependencegraph import ControlDependenceGraph
from pyChecco.analyses.controlflow.programgraph import ProgramGraphNode
from pyChecco.execution.executiontracer import CodeObjectMetaData, ExecutionTracer
from pyChecco.slicer.instruction import UniqueInstruction
from pyChecco.utils.opcodes import *

IMPORT_OFFSET = 12

OP_UNARY = [UNARY_POSITIVE, UNARY_NEGATIVE, UNARY_NOT, UNARY_INVERT, GET_ITER, GET_YIELD_FROM_ITER]
OP_BINARY = [BINARY_POWER, BINARY_MULTIPLY, BINARY_MATRIX_MULTIPLY, BINARY_FLOOR_DIVIDE, BINARY_TRUE_DIVIDE,
             BINARY_MODULO, BINARY_ADD, BINARY_SUBTRACT, BINARY_LSHIFT, BINARY_RSHIFT,
             BINARY_AND, BINARY_XOR, BINARY_OR]
OP_INPLACE = [INPLACE_POWER, INPLACE_MULTIPLY, INPLACE_MATRIX_MULTIPLY, INPLACE_FLOOR_DIVIDE,
              INPLACE_TRUE_DIVIDE, INPLACE_MODULO, INPLACE_ADD, INPLACE_SUBTRACT, INPLACE_LSHIFT,
              INPLACE_RSHIFT, INPLACE_AND, INPLACE_XOR, INPLACE_OR]
OP_COMPARE = [COMPARE_OP]
OP_LOCAL_ACCESS = [STORE_FAST, LOAD_FAST, DELETE_FAST]
OP_NAME_ACCESS = [STORE_NAME, LOAD_NAME, DELETE_NAME]
OP_GLOBAL_ACCESS = [STORE_GLOBAL, LOAD_GLOBAL, DELETE_GLOBAL]
OP_DEREF_ACCESS = [STORE_DEREF, LOAD_DEREF, DELETE_DEREF, LOAD_CLASSDEREF]
OP_ATTR_ACCESS = [STORE_ATTR, LOAD_ATTR, DELETE_ATTR, IMPORT_FROM, LOAD_METHOD]
OP_SUBSCR_ACCESS = [STORE_SUBSCR, DELETE_SUBSCR, BINARY_SUBSCR]
OP_IMPORT_NAME = [IMPORT_NAME]
OP_ABSOLUTE_JUMP = [JUMP_IF_FALSE_OR_POP, JUMP_IF_TRUE_OR_POP, JUMP_ABSOLUTE, POP_JUMP_IF_FALSE, POP_JUMP_IF_TRUE]
OP_RELATIVE_JUMP = [FOR_ITER, JUMP_FORWARD, SETUP_FINALLY, SETUP_WITH, SETUP_ASYNC_WITH, CALL_FINALLY]
OP_CALL = [CALL_FUNCTION, CALL_FUNCTION_KW, CALL_FUNCTION_EX, CALL_METHOD, YIELD_FROM]
OP_RETURN = [RETURN_VALUE, YIELD_VALUE]

TRACED_INSTRUCTIONS = OP_UNARY + OP_BINARY + OP_INPLACE + OP_COMPARE + OP_LOCAL_ACCESS + OP_NAME_ACCESS + \
                      OP_GLOBAL_ACCESS + OP_DEREF_ACCESS + OP_ATTR_ACCESS + OP_SUBSCR_ACCESS + OP_IMPORT_NAME + \
                      OP_ABSOLUTE_JUMP + OP_RELATIVE_JUMP + OP_CALL + OP_RETURN


class InstructionInstrumentation:
    """Instruments code objects to enable dynamic slicing.

    General notes:

    When calling a method on an object, the arguments have to be on top of the stack.
    In most cases, we need to rotate the items on the stack with ROT_TWO, ROT_THREE or
    ROT_FOUR to reorder the elements accordingly.

    A POP_TOP instruction is required after calling a method, because each method
    implicitly returns None."""

    _logger = logging.getLogger(__name__)

    def __init__(self, tracer: ExecutionTracer) -> None:
        self._tracer = tracer
        self._filename = None

    def _instrument_inner_code_objects(self, code: CodeType, parent_code_object_id: int) -> CodeType:
        """Apply the instrumentation to all constants of the given code object.
        :param code: The code object to be instrumented.
        :param parent_code_object_id: Internal id of the code object to which this code object belongs
        (can be None if `code` is the highest node, i.e. the module node).
        :return: The code object whose constants were instrumented.
        """
        new_consts = []
        for const in code.co_consts:
            if isinstance(const, CodeType):
                # The const is an inner code object
                new_consts.append(self.instrument_code_recursive(const, parent_code_object_id=parent_code_object_id))
            else:
                new_consts.append(const)

        return code.replace(co_consts=tuple(new_consts))

    def instrument_code_recursive(self, code: CodeType, parent_code_object_id: Optional[int] = None) -> CodeType:
        """Instrument the given Code Object recursively.

        :param code: The code object to be instrumented.
        :param parent_code_object_id: Internal id of the code object to which this code object belongs
        (can be None if `code` is the highest node, i.e. the module node).
        :return The instrumented code object.
        """
        # The original bytecode should match the disassembly, so EXTENDED_ARG is included
        # original_cfg = CFG.from_bytecode(ConcreteBytecode.from_code(code, extended_arg=False).to_bytecode())
        original_cfg = CFG.from_bytecode(ConcreteBytecode.from_code(code, extended_arg=False).to_bytecode())
        original_cdg = ControlDependenceGraph.compute(original_cfg)
        cfg = CFG.from_bytecode(Bytecode.from_code(code))
        code_object_id = self._tracer.register_code_object(
            CodeObjectMetaData(code.co_filename, code, parent_code_object_id, original_cfg, cfg, original_cdg)
        )
        assert cfg.entry_node is not None, "Entry node cannot be None."

        module_entry = False
        if not parent_code_object_id:
            # This is the module entry, in which we want to import the ExecutionTracer
            self._instrument_import(cfg)
            module_entry = True

        self._instrument_cfg(cfg, original_cfg, code_object_id, module_entry)
        return self._instrument_inner_code_objects(cfg.bytecode_cfg().to_code(), code_object_id)

    def _instrument_cfg(self, cfg: CFG, original_cfg: CFG, code_object_id: int, module_entry: bool) -> None:
        """Instrument the bytecode cfg associated with the given CFG.

        :param cfg: The CFG that overlays the bytecode cfg.
        :param original_cfg: The unmodified cfg.
        :param code_object_id: Internal id for the code object of `cfg`.
        :param module_entry: True if `cfg` is the highest cfg in the module.
        """
        # Attributes which store the predicate ids assigned to instrumented nodes.
        node_attributes: Dict[ProgramGraphNode, Dict[str, int]] = dict()

        # We need to sort nodes in order to keep track of the correct offset
        cfg_nodes = list(cfg.nodes)
        cfg_nodes.sort(key=lambda n: n.index)
        original_cfg_nodes = list(original_cfg.nodes)
        original_cfg_nodes.sort(key=lambda n: n.index)

        if not module_entry:
            offset = 0
        else:
            offset = -IMPORT_OFFSET

        # Each node in the cfg is instrumented, but we want to save offset information in the original cfg
        for node, original_node in zip(cfg_nodes, original_cfg_nodes):
            if offset < 0:
                original_node.set_offset(0)
            else:
                original_node.set_offset(offset)
            offset = self._instrument_node(node, cfg, code_object_id, offset)

        nx.set_node_attributes(cfg.graph, node_attributes)

    def _instrument_node(self, node: ProgramGraphNode, cfg: CFG, code_object_id: int, offset: int) -> int:
        """
        Instrument a single node in the CFG.
        We instrument memory accesses, control flow instructions and attribute access instructions.

        The instruction number in combination with the line number and the filename can uniquely identify the traced
        instruction in the original bytecode. Since instructions have a fixed length of two bytes since version 3.6,
        this is rather trivial to keep track of.

        :param node: The node that should be instrumented.
        :param cfg: The control flow graph where `node` belongs to.
        :param code_object_id: Internal id for the code object of `cfg`.
        :param offset: Instruction offset of the basic block in `node`.
        :return: The offset of the next instruction after the basic block of this node.
        """
        # Not every block has an associated basic block, e.g. the artificial exit node.
        if node.is_artificial:
            return offset

        assert (node.basic_block is not None), "Non artificial node does not have a basic block."
        assert len(node.basic_block) > 0, "Empty basic block in CFG."

        new_block_instructions = []

        for instr in node.basic_block:
            # Perform the actual instrumentation
            if offset >= 0:  # Skip import of ExecutionTracer
                if (instr.opcode in OP_UNARY) or (instr.opcode in OP_BINARY) or (instr.opcode in OP_INPLACE) or \
                        (instr.opcode in OP_COMPARE):
                    self._instrument_generic(new_block_instructions, code_object_id, node.index, instr, offset)
                elif instr.opcode in OP_LOCAL_ACCESS:
                    self._instrument_local_access(code_object_id, node.index, new_block_instructions, instr, offset)
                elif instr.opcode in OP_NAME_ACCESS:
                    self._instrument_name_access(code_object_id, node.index, new_block_instructions, instr, offset)
                elif instr.opcode in OP_GLOBAL_ACCESS:
                    self._instrument_global_access(code_object_id, node.index, new_block_instructions, instr, offset)
                elif instr.opcode in OP_DEREF_ACCESS:
                    self._instrument_deref_access(code_object_id, node.index, new_block_instructions, instr, offset)
                elif instr.opcode in OP_ATTR_ACCESS:
                    self._instrument_attr_access(code_object_id, node.index, new_block_instructions, instr, offset)
                elif instr.opcode in OP_SUBSCR_ACCESS:
                    self._instrument_subscr_access(code_object_id, node.index, new_block_instructions, instr, offset)
                elif instr.opcode in OP_ABSOLUTE_JUMP or instr.opcode in OP_RELATIVE_JUMP:
                    self._instrument_jump(code_object_id, node.index, new_block_instructions, instr, offset, cfg)
                elif instr.opcode in OP_CALL:
                    self._instrument_call(code_object_id, node.index, new_block_instructions, instr, offset)
                elif instr.opcode in OP_RETURN:
                    self._instrument_return(code_object_id, node.index, new_block_instructions, instr, offset)
                elif instr.opcode in OP_IMPORT_NAME:
                    self._instrument_import_name_access(code_object_id, node.index, new_block_instructions, instr,
                                                        offset)
                else:
                    # Un-traced instruction retrieved during analysis
                    new_block_instructions.append(instr)
            else:
                new_block_instructions.append(instr)

            offset += 2

        node.basic_block.clear()
        node.basic_block.extend(new_block_instructions)

        return offset

    def _instrument_generic(self, new_block_instructions: List[Instr], code_object_id: int, node_id: int,
                            instr: Instr, offset: int) -> None:
        # Call tracing method
        new_block_instructions.extend([
            # Load tracing method
            Instr("LOAD_GLOBAL", self._tracer.__class__.__name__, lineno=instr.lineno),
            Instr("LOAD_METHOD", "track_generic", lineno=instr.lineno),

            # Load arguments
            # Current module
            Instr("LOAD_GLOBAL", "__file__", lineno=instr.lineno),
            # Code object id
            Instr("LOAD_CONST", code_object_id, lineno=instr.lineno),
            # Basic block id
            Instr("LOAD_CONST", node_id, lineno=instr.lineno),
            # Instruction opcode
            Instr("LOAD_CONST", instr.opcode, lineno=instr.lineno),
            # Line number of access
            Instr("LOAD_CONST", instr.lineno, lineno=instr.lineno),
            # Instruction number of access
            Instr("LOAD_CONST", offset, lineno=instr.lineno),

            # Call tracing method
            Instr("CALL_METHOD", 6, lineno=instr.lineno),
            Instr("POP_TOP", lineno=instr.lineno),

            # Original instruction
            instr,
        ])

    def _instrument_local_access(self, code_object_id: int, node_id: int, new_block_instructions: List[Instr],
                                 instr: Instr, offset: int) -> None:
        if instr.opcode in [LOAD_FAST, STORE_FAST]:
            # Original instruction before instrumentation
            new_block_instructions.append(instr)

        new_block_instructions.extend([
            # Load tracing method
            Instr("LOAD_GLOBAL", self._tracer.__class__.__name__, lineno=instr.lineno),
            Instr("LOAD_METHOD", "track_memory_access", lineno=instr.lineno),
        ])

        # Load static arguments
        new_block_instructions.extend(self._load_args(code_object_id, node_id, offset, instr.arg, instr))

        new_block_instructions.extend([
            # Argument address
            Instr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            Instr("LOAD_FAST", instr.arg, lineno=instr.lineno),
            Instr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Argument type
            Instr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            Instr("LOAD_FAST", instr.arg, lineno=instr.lineno),
            Instr("CALL_FUNCTION", 1, lineno=instr.lineno),

            # Call tracing method
            Instr("CALL_METHOD", 9, lineno=instr.lineno),
            Instr("POP_TOP", lineno=instr.lineno),
        ])

        if instr.opcode == DELETE_FAST:
            # Original instruction after instrumentation (otherwise we can not read it anymore)
            new_block_instructions.append(instr)

    def _instrument_attr_access(self, code_object_id: int, node_id: int, new_block_instructions: List[Instr],
                                instr: Instr, offset: int) -> None:
        if instr.opcode in [LOAD_ATTR, DELETE_ATTR, IMPORT_FROM, LOAD_METHOD]:
            # Duplicate top of stack to access attribute
            new_block_instructions.append(Instr("DUP_TOP", lineno=instr.lineno))
        elif instr.opcode == STORE_ATTR:
            new_block_instructions.extend([
                # Execute actual store instruction
                Instr("DUP_TOP", lineno=instr.lineno),
                Instr("ROT_THREE", lineno=instr.lineno),
                instr,
            ])

        new_block_instructions.extend([
            # Load tracing method
            Instr("LOAD_GLOBAL", self._tracer.__class__.__name__, lineno=instr.lineno),
            Instr("LOAD_METHOD", "track_attribute_access", lineno=instr.lineno),
            # A method occupies two slots on top of the stack -> move third up and keep order of upper two
            Instr("ROT_THREE", lineno=instr.lineno),
            Instr("ROT_THREE", lineno=instr.lineno),
        ])

        # Load static arguments
        new_block_instructions.extend(self._load_args_with_prop(code_object_id, node_id, offset, instr.arg, instr))

        new_block_instructions.extend([
            # TOS is object ref -> duplicate for determination of source address, argument address and argument_type
            Instr("DUP_TOP", lineno=instr.lineno),
            Instr("DUP_TOP", lineno=instr.lineno),
            # Determine source address
            #   Load lookup method
            Instr("LOAD_GLOBAL", self._tracer.__class__.__name__, lineno=instr.lineno),
            Instr("LOAD_METHOD", "attribute_lookup", lineno=instr.lineno),
            Instr("ROT_THREE", lineno=instr.lineno),
            Instr("ROT_THREE", lineno=instr.lineno),
            #   Load attribute name (second argument)
            Instr("LOAD_CONST", instr.arg, lineno=instr.lineno),
            #   Call lookup method
            Instr("CALL_METHOD", 2, lineno=instr.lineno),

            # Determine argument address
            Instr("ROT_TWO", lineno=instr.lineno),
            Instr("LOAD_ATTR", arg=instr.arg, lineno=instr.lineno),
            Instr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            Instr("ROT_TWO", lineno=instr.lineno),
            Instr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Determine argument type
            Instr("ROT_THREE", lineno=instr.lineno),
            Instr("ROT_THREE", lineno=instr.lineno),
            Instr("LOAD_ATTR", arg=instr.arg, lineno=instr.lineno),
            Instr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            Instr("ROT_TWO", lineno=instr.lineno),
            Instr("CALL_FUNCTION", 1, lineno=instr.lineno),

            # Call tracing method
            Instr("CALL_METHOD", 10, lineno=instr.lineno),
            Instr("POP_TOP", lineno=instr.lineno),
        ])

        if instr.opcode in [LOAD_ATTR, DELETE_ATTR, IMPORT_FROM, LOAD_METHOD]:
            # Original instruction: we need to load the attribute afterwards
            new_block_instructions.append(instr)

    def _instrument_subscr_access(self, code_object_id: int, node_id: int, new_block_instructions: List[Instr],
                                  instr: Instr, offset: int) -> None:
        if instr.opcode == STORE_SUBSCR:
            new_block_instructions.extend([
                # Execute actual store instruction
                Instr("ROT_TWO", lineno=instr.lineno),
                Instr("DUP_TOP", lineno=instr.lineno),
                Instr("ROT_FOUR", lineno=instr.lineno),
                Instr("ROT_TWO", lineno=instr.lineno),
                instr,
            ])
        elif instr.opcode == DELETE_SUBSCR:
            new_block_instructions.extend([
                # Execute delete instruction
                Instr("ROT_TWO", lineno=instr.lineno),
                Instr("DUP_TOP", lineno=instr.lineno),
                Instr("ROT_THREE", lineno=instr.lineno),
                Instr("ROT_THREE", lineno=instr.lineno),
                instr,
            ])
        elif instr.opcode == BINARY_SUBSCR:
            new_block_instructions.extend([
                # Execute access afterwards, prepare stack
                Instr("DUP_TOP_TWO", lineno=instr.lineno),
                Instr("POP_TOP", lineno=instr.lineno),
            ])

        new_block_instructions.extend([
            # Load tracing method
            Instr("LOAD_GLOBAL", self._tracer.__class__.__name__, lineno=instr.lineno),
            Instr("LOAD_METHOD", "track_attribute_access", lineno=instr.lineno),
            # A method occupies two slots on top of the stack -> move third up and keep order of upper two
            Instr("ROT_THREE", lineno=instr.lineno),
            Instr("ROT_THREE", lineno=instr.lineno),
        ])

        # Load static arguments
        new_block_instructions.extend(self._load_args_with_prop(code_object_id, node_id, offset, "None", instr))

        new_block_instructions.extend([
            # Source object address
            Instr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            Instr("ROT_TWO", lineno=instr.lineno),
            Instr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # No arg address
            Instr("LOAD_CONST", None, lineno=instr.lineno),
            # No arg type
            Instr("LOAD_CONST", None, lineno=instr.lineno),

            # Call tracing method
            Instr("CALL_METHOD", 10, lineno=instr.lineno),
            Instr("POP_TOP", lineno=instr.lineno),
        ])

        if instr.opcode == BINARY_SUBSCR:
            new_block_instructions.append(instr)

    def _instrument_name_access(self, code_object_id: int, node_id: int, new_block_instructions: List[Instr],
                                instr: Instr, offset: int) -> None:
        if instr.opcode in [STORE_NAME, LOAD_NAME, IMPORT_NAME]:
            # Original instruction at before instrumentation
            new_block_instructions.append(instr)

        new_block_instructions.extend([
            # Load tracing method
            Instr("LOAD_GLOBAL", self._tracer.__class__.__name__, lineno=instr.lineno),
            Instr("LOAD_METHOD", "track_memory_access", lineno=instr.lineno),
        ])

        # Load static arguments
        new_block_instructions.extend(self._load_args(code_object_id, node_id, offset, instr.arg, instr))

        new_block_instructions.extend([
            # Argument address
            Instr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            Instr("LOAD_NAME", instr.arg, lineno=instr.lineno),
            Instr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Argument type
            Instr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            Instr("LOAD_NAME", instr.arg, lineno=instr.lineno),
            Instr("CALL_FUNCTION", 1, lineno=instr.lineno),

            # Call tracing method
            Instr("CALL_METHOD", 9, lineno=instr.lineno),
            Instr("POP_TOP", lineno=instr.lineno),
        ])
        if instr.opcode == DELETE_NAME:
            # Original instruction after instrumentation (otherwise we can not read it anymore)
            new_block_instructions.append(instr)

    def _instrument_import_name_access(self, code_object_id: int, node_id: int, new_block_instructions: List[Instr],
                                       instr: Instr, offset: int) -> None:
        new_block_instructions.extend([
            # Execute actual instruction and duplicate module reference on TOS
            instr,
            Instr("DUP_TOP"),

            # Load tracing method
            Instr("LOAD_GLOBAL", self._tracer.__class__.__name__, lineno=instr.lineno),
            Instr("LOAD_METHOD", "track_memory_access", lineno=instr.lineno),
            Instr("ROT_THREE", lineno=instr.lineno),
            Instr("ROT_THREE", lineno=instr.lineno),
        ])

        # Load static arguments
        new_block_instructions.extend(self._load_args_with_prop(code_object_id, node_id, offset, instr.arg, instr))

        new_block_instructions.extend([
            Instr("DUP_TOP", lineno=instr.lineno),
            # Argument address
            Instr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            Instr("ROT_TWO", lineno=instr.lineno),
            Instr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Argument type
            Instr("ROT_TWO", lineno=instr.lineno),
            Instr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            Instr("ROT_TWO", lineno=instr.lineno),
            Instr("CALL_FUNCTION", 1, lineno=instr.lineno),

            # Call tracing method
            Instr("CALL_METHOD", 9, lineno=instr.lineno),
            Instr("POP_TOP", lineno=instr.lineno),
        ])

    def _instrument_global_access(self, code_object_id: int, node_id: int, new_block_instructions: List[Instr],
                                  instr: Instr, offset: int) -> None:
        if instr.opcode in [STORE_GLOBAL, LOAD_GLOBAL]:
            # Original instruction before instrumentation
            new_block_instructions.append(instr)

        new_block_instructions.extend([
            # Load tracing method
            Instr("LOAD_GLOBAL", self._tracer.__class__.__name__, lineno=instr.lineno),
            Instr("LOAD_METHOD", "track_memory_access", lineno=instr.lineno),
        ])

        # Load static arguments
        new_block_instructions.extend(self._load_args(code_object_id, node_id, offset, instr.arg, instr))

        new_block_instructions.extend([
            # Argument address
            Instr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            Instr("LOAD_GLOBAL", instr.arg, lineno=instr.lineno),
            Instr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Argument type
            Instr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            Instr("LOAD_GLOBAL", instr.arg, lineno=instr.lineno),
            Instr("CALL_FUNCTION", 1, lineno=instr.lineno),

            # Call tracing method
            Instr("CALL_METHOD", 9, lineno=instr.lineno),
            Instr("POP_TOP", lineno=instr.lineno),
        ])

        if instr.opcode == DELETE_GLOBAL:
            # Original instruction after instrumentation (otherwise we can not read it anymore)
            new_block_instructions.append(instr)

    def _instrument_deref_access(self, code_object_id: int, node_id: int, new_block_instructions: List[Instr],
                                 instr: Instr, offset: int) -> None:
        # Load instruction
        if instr.opcode == LOAD_CLASSDEREF:
            load_instr = Instr("LOAD_CLASSDEREF", instr.arg, lineno=instr.lineno)
        else:
            load_instr = Instr("LOAD_DEREF", instr.arg, lineno=instr.lineno)

        if instr.opcode in [STORE_DEREF, LOAD_DEREF, LOAD_CLASSDEREF]:
            # Original instruction before instrumentation
            new_block_instructions.append(instr)

        new_block_instructions.extend([
            # Load tracing method
            Instr("LOAD_GLOBAL", self._tracer.__class__.__name__, lineno=instr.lineno),
            Instr("LOAD_METHOD", "track_memory_access", lineno=instr.lineno),
        ])

        # Load static arguments
        new_block_instructions.extend(self._load_args(code_object_id, node_id, offset, instr.arg.name, instr))

        new_block_instructions.extend([
            # Argument address
            Instr("LOAD_GLOBAL", builtins.id.__name__, lineno=instr.lineno),
            load_instr,
            Instr("CALL_FUNCTION", 1, lineno=instr.lineno),
            # Argument type
            Instr("LOAD_GLOBAL", builtins.type.__name__, lineno=instr.lineno),
            load_instr,
            Instr("CALL_FUNCTION", 1, lineno=instr.lineno),

            # Call tracing method
            Instr("CALL_METHOD", 9, lineno=instr.lineno),
            Instr("POP_TOP", lineno=instr.lineno),
        ])

        if instr.opcode == DELETE_DEREF:
            # Original instruction after instrumentation (otherwise we can not read it anymore)
            new_block_instructions.append(instr)

    def _instrument_jump(self, code_object_id: int, node_id: int, new_block_instructions: List[Instr], instr: Instr,
                         offset: int, cfg: CFG) -> None:
        new_block_instructions.extend([
            # Load tracing method
            Instr("LOAD_GLOBAL", self._tracer.__class__.__name__, lineno=instr.lineno),
            Instr("LOAD_METHOD", "track_jump", lineno=instr.lineno),
        ])

        # Load static arguments
        new_block_instructions.extend(self._load_args(code_object_id, node_id, offset,
                                                      cfg.bytecode_cfg().get_block_index(instr.arg), instr))

        new_block_instructions.extend([
            # Call tracing method
            Instr("CALL_METHOD", 7, lineno=instr.lineno),
            Instr("POP_TOP", lineno=instr.lineno),
        ])

        new_block_instructions.append(instr)

    def _instrument_call(self, code_object_id: int, node_id: int, new_block_instructions: List[Instr], instr: Instr,
                         offset: int) -> None:
        # Trace argument only for calls with integer arguments
        if type(instr.arg) is int:
            argument = instr.arg
        else:
            argument = None

        # Call tracing method
        new_block_instructions.extend([
            # Load tracing method
            Instr("LOAD_GLOBAL", self._tracer.__class__.__name__, lineno=instr.lineno),
            Instr("LOAD_METHOD", "track_call", lineno=instr.lineno),
        ])

        # Load static arguments
        new_block_instructions.extend(self._load_args(code_object_id, node_id, offset, argument, instr))

        new_block_instructions.extend([
            # Call tracing method
            Instr("CALL_METHOD", 7, lineno=instr.lineno),
            Instr("POP_TOP", lineno=instr.lineno),
        ])

        new_block_instructions.append(instr)

    def _instrument_return(self, code_object_id: int, node_id: int, new_block_instructions: List[Instr], instr: Instr,
                           offset: int) -> None:
        new_block_instructions.extend([
            # Load tracing method
            Instr("LOAD_GLOBAL", self._tracer.__class__.__name__, lineno=instr.lineno),
            Instr("LOAD_METHOD", "track_return", lineno=instr.lineno),

            # Load arguments
            # Current module
            Instr("LOAD_GLOBAL", "__file__", lineno=instr.lineno),
            # Code object id
            Instr("LOAD_CONST", code_object_id, lineno=instr.lineno),
            # Basic block id
            Instr("LOAD_CONST", node_id, lineno=instr.lineno),
            # Instruction opcode
            Instr("LOAD_CONST", instr.opcode, lineno=instr.lineno),
            # Line number of access
            Instr("LOAD_CONST", instr.lineno, lineno=instr.lineno),
            # Instruction number of access
            Instr("LOAD_CONST", offset, lineno=instr.lineno),

            # Call tracing method
            Instr("CALL_METHOD", 6, lineno=instr.lineno),
            Instr("POP_TOP", lineno=instr.lineno),
        ])

        # Original instruction after instrumentation (otherwise we do not reach instrumented code)
        new_block_instructions.append(instr)

    def _instrument_assertion(self, code_object_id: int, node_id: int, new_block_instructions: List[Instr],
                              instr: Instr) -> None:
        # Call tracing method
        new_block_instructions.extend([
            # Load tracing method
            Instr("LOAD_GLOBAL", self._tracer.__class__.__name__, lineno=instr.lineno),
            Instr("LOAD_METHOD", "track_assertion", lineno=instr.lineno),

            # Load arguments
            #   Current module
            Instr("LOAD_GLOBAL", "__file__", lineno=instr.lineno),
            #   Code object id
            Instr("LOAD_CONST", code_object_id, lineno=instr.lineno),
            #   Basic block id
            Instr("LOAD_CONST", node_id, lineno=instr.lineno),
            #   Line number of access
            Instr("LOAD_CONST", instr.lineno, lineno=instr.lineno),

            # Call tracing method
            Instr("CALL_METHOD", 4, lineno=instr.lineno),
            Instr("POP_TOP", lineno=instr.lineno),

            # Original instruction
            instr,
        ])

    def _instrument_import(self, cfg: CFG) -> None:
        """Import the tracer at the beginning of a module.

        :param cfg: The cfg of the module code object.
        """

        assert cfg.entry_node is not None, "Entry node cannot be None."
        real_entry_node = cfg.get_successors(cfg.entry_node).pop()  # Only one exists!
        assert real_entry_node.basic_block is not None, "Basic block cannot be None."

        # Add import right at the beginning
        lineno = 1

        real_entry_node.basic_block[0:0] = [
            Instr("LOAD_CONST", 0, lineno=lineno),
            Instr("LOAD_CONST", self._tracer.__class__.__name__, lineno=lineno),
            Instr("IMPORT_NAME", self._tracer.__module__, lineno=lineno),
            Instr("IMPORT_FROM", self._tracer.__class__.__name__, lineno=lineno),
            Instr("STORE_GLOBAL", self._tracer.__class__.__name__, lineno=lineno),
            Instr("POP_TOP", lineno=lineno),
        ]

    def instrument_module(self, module_code: CodeType) -> CodeType:
        """
        Instrument the given code object of a module and recursively all its child code objects.

        :param module_code: Code object of the module
        :return Recursively instrumented code object.
        """
        self._filename = module_code.co_filename

        for const in module_code.co_consts:
            if isinstance(const, str):
                if const == "ExecutionTracer":
                    # Abort instrumentation, since we have already instrumented this code object.
                    assert False, "Tried to instrument already instrumented module."

        return self.instrument_code_recursive(module_code)

    @staticmethod
    def _load_args(code_object_id: int, node_id: int, offset: int, arg, instr: Instr) -> List[Instr]:
        instructions = [
            # Current module
            Instr("LOAD_GLOBAL", "__file__", lineno=instr.lineno),
            # Code object id
            Instr("LOAD_CONST", code_object_id, lineno=instr.lineno),
            # Basic block id
            Instr("LOAD_CONST", node_id, lineno=instr.lineno),
            # Instruction opcode
            Instr("LOAD_CONST", instr.opcode, lineno=instr.lineno),
            # Line number of access
            Instr("LOAD_CONST", instr.lineno, lineno=instr.lineno),
            # Instruction number of access
            Instr("LOAD_CONST", offset, lineno=instr.lineno),
            # Argument name
            Instr("LOAD_CONST", arg, lineno=instr.lineno),
        ]

        return instructions

    @staticmethod
    def _load_args_with_prop(code_object_id: int, node_id: int, offset: int, arg, instr: Instr) -> List[Instr]:
        instructions = [
            # Load arguments
            #   Current module
            Instr("LOAD_GLOBAL", "__file__", lineno=instr.lineno),
            Instr("ROT_TWO", lineno=instr.lineno),
            #   Code object id
            Instr("LOAD_CONST", code_object_id, lineno=instr.lineno),
            Instr("ROT_TWO", lineno=instr.lineno),
            #   Basic block id
            Instr("LOAD_CONST", node_id, lineno=instr.lineno),
            Instr("ROT_TWO", lineno=instr.lineno),
            #   Instruction opcode
            Instr("LOAD_CONST", instr.opcode, lineno=instr.lineno),
            Instr("ROT_TWO", lineno=instr.lineno),
            #   Line number of access
            Instr("LOAD_CONST", instr.lineno, lineno=instr.lineno),
            Instr("ROT_TWO", lineno=instr.lineno),
            #   Instruction number of access
            Instr("LOAD_CONST", offset, lineno=instr.lineno),
            Instr("ROT_TWO", lineno=instr.lineno),
            #   Argument name
            Instr("LOAD_CONST", arg, lineno=instr.lineno),
            Instr("ROT_TWO", lineno=instr.lineno),
        ]

        return instructions


def is_traced_instruction(instr: Union[Instr, UniqueInstruction]) -> bool:
    """
    Determine if the given instruction is traced.

    :param instr: Instruction to be checked if it is traced.
    :return: True if `instr` is traced, False otherwise.
    """
    return instr.opcode in TRACED_INSTRUCTIONS
