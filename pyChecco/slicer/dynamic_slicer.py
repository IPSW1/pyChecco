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


import time
import operator

from bytecode import Instr
from typing import List, Optional, Union, Dict, Tuple, Set

from pyChecco.configuration import Configuration
from pyChecco.analyses.controlflow.controldependencegraph import ControlDependenceGraph
from pyChecco.analyses.controlflow.cfg import CFG
from pyChecco.slicer.execution_flow_builder import ExecutionFlowBuilder
from pyChecco.execution.codeobjectmetadata import CodeObjectMetaData
from pyChecco.execution.executiontrace import ExecutionTrace
from pyChecco.execution.executed_instruction import *
from pyChecco.slicer.instruction import UniqueInstruction
from pyChecco.slicer.stack.stack_effect import StackEffect
from pyChecco.slicer.stack.stack_simulation import TraceStack
from pyChecco.instrumentation.instruction_instrumentation import is_traced_instruction
from pyChecco.utils.exceptions import InstructionNotFoundException, UncertainStackEffectException, \
    SlicingTimeoutException
from pyChecco.utils.opcodes import *


class DynamicSlice:
    def __init__(self, origin_name: str, instructions: List[UniqueInstruction]):
        self.origin_name = origin_name
        self.sliced_instructions: List[UniqueInstruction] = instructions


class SlicingCriterion:
    def __init__(self, unique_instr: UniqueInstruction, occurrence: Optional[int] = 1,
                 local_variables: Optional[Set] = None, global_variables: Optional[Set] = None) -> None:
        self.unique_instr = unique_instr
        self.occurrence = occurrence

        self.local_variables = local_variables
        self.global_variables = global_variables


class SlicingContext:
    def __init__(self):
        # Instructions included in the slice
        self.DS = list()

        # Instructions for which to compute control dependencies
        self.S_C = set()

        # Variable uses for which a definition is needed
        self.D_local = set()
        self.D_global = set()
        self.D_nonlocal = set()
        self.D_addresses = set()
        # Attribute uses for which a definition is needed
        self.D_attributes = set()

        # Variable uses, which normally are attribute uses (used when encompassing object is created)
        self.attribute_variables = set()


class DynamicSlicer:
    def __init__(self, configuration: Configuration, trace: ExecutionTrace,
                 known_code_objects: Dict[int, CodeObjectMetaData]):
        self._configuration = configuration

        self.known_code_objects = known_code_objects
        self.trace = trace

    def slice(self, trace: ExecutionTrace, slicing_criterion: SlicingCriterion, trace_position: int = -1,
              debug_output: bool = False) -> DynamicSlice:
        """
        Main routine to perform the dynamic slicing.

        :param trace: Execution trace object containing with collected instructions.
        :param slicing_criterion: Slicing criterion object where slicing is started (must have correct `occurrence`
        attribute if `trace_position` is not given.
        :param trace_position: Optional parameter. The position in the trace where slicing is started
        can be given directly (as in the case of internal traced assertions). In case it is not given
        it has to be determined based on the occurrence of the instruction of the slicing criterion in the trace.
        :param debug_output: Print detailed output about each step if True.
        :return: A `DynamicSlice` object containing the included instructions.
        """

        if trace_position < 0:
            trace_position = self.find_trace_position(trace, slicing_criterion)

        #
        # Initialization
        #
        execution_flow_builder = ExecutionFlowBuilder(trace, self.known_code_objects)

        # Build slicing criterion
        last_ex_instruction = slicing_criterion.unique_instr
        file = last_ex_instruction.file
        code_object_id = last_ex_instruction.code_object_id
        basic_block_id = last_ex_instruction.node_id
        offset = last_ex_instruction.offset
        curr_instr = self._locate_unique_in_bytecode(last_ex_instruction, code_object_id, basic_block_id)

        in_slice = True  # The slicing criterion is in the slice

        # Initialize stack
        stack_simulation = True  # Stack simulation is enabled initially (must be disabled for exceptions)
        trace_stack = TraceStack()
        pops, pushes = StackEffect.stack_effect(last_ex_instruction.opcode, last_ex_instruction.dis_arg, False)
        trace_stack.update_push_operations(pushes, False)
        trace_stack.update_pop_operations(pops, last_ex_instruction, in_slice)

        # Initial context
        context = SlicingContext()
        context.DS.append(last_ex_instruction)
        if slicing_criterion.global_variables:
            for tup in slicing_criterion.global_variables:
                context.D_global.add(tup)
        self.add_control_dependencies(context, last_ex_instruction, code_object_id)

        code_object_dependent = False
        new_attribute_object_uses = set()
        import_back_call = None

        timeout = time.time() + self._configuration.max_slicing_time

        while True:
            in_slice = imp_data_dep = False
            include_use = True

            # Get last instruction
            last_state = execution_flow_builder.get_last_instruction(file, curr_instr, trace_position, offset,
                                                                     code_object_id, basic_block_id, import_back_call)
            file = last_state.file
            offset = last_state.offset
            code_object_id = last_state.code_object_id
            basic_block_id = last_state.basic_block_id

            if last_state.exception:
                # Stack can not be reliably simulated when an exception occurred
                stack_simulation = False
            if not last_state.last_instr:
                # Reached end of executed instructions -> return slice (and keep order)
                instructions = set()
                slice_instructions = \
                    [i for i in reversed(context.DS) if not (i in instructions or instructions.add(i))]
                return DynamicSlice(trace.test_id, slice_instructions)

            last_unique_instr = self.create_unique_instruction(file, last_state.last_instr, code_object_id,
                                                               basic_block_id, offset)
            # Adjust trace position
            last_traced_instr = None
            if is_traced_instruction(last_state.last_instr):
                last_traced_instr = trace.executed_instructions[trace_position]
                trace_position -= 1

            #
            # Stack housekeeping
            #
            prev_import_back_call = trace_stack.get_import_frame()
            trace_stack.set_attribute_uses(context.attribute_variables)
            if last_state.returned:
                # New frame
                trace_stack.push_stack(code_object_id)
                trace_stack.set_attribute_uses(new_attribute_object_uses)
                new_attribute_object_uses.clear()

                trace_stack.set_import_frame(last_state.import_back_call)
            if last_state.call or last_state.import_start:
                # Frame finished
                trace_stack.pop_stack()
                # After leaving the frame where the exception occurred, simulation can be continued
                if not stack_simulation:
                    trace_stack.push_artificial_stack()
                    stack_simulation = True
            context.attribute_variables = trace_stack.get_attribute_uses()
            import_back_call = trace_stack.get_import_frame()

            try:
                pops, pushes = StackEffect.stack_effect(last_unique_instr.opcode, last_unique_instr.dis_arg,
                                                        jump=last_state.jump)
            except UncertainStackEffectException:
                # Stack simulation in not possible with this opcode
                stack_simulation = False

            #
            # Control dependency
            #
            control_dependency = self.check_control_dependency(context, last_unique_instr, code_object_id)

            #
            # Data dependencies
            #
            # Explicit data dependency
            exp_data_dep, new_attribute_object_uses = self.check_explicit_data_dependency(context,
                                                                                          last_unique_instr,
                                                                                          last_traced_instr)

            # Dependency via method call
            if last_state.call and code_object_dependent:
                imp_data_dep = True
                code_object_dependent = False

                if last_state.import_start:
                    # We need to include the import statement after determining if one of the instructions
                    # executed by the import is included (because IMPORT_NAME is traced afterwards).
                    context.DS.append(prev_import_back_call)
                    num_import_pops = StackEffect.stack_effect(prev_import_back_call.opcode, arg=None, jump=False)[0]
                    trace_stack.update_pop_operations(num_import_pops, prev_import_back_call, True)
            # Implicit data dependency (over stack)
            if stack_simulation:
                stack_dep, include_use = trace_stack.update_push_operations(pushes, last_state.returned)
                if stack_dep:
                    imp_data_dep = True
            if last_state.returned:
                code_object_dependent = False

            if control_dependency or exp_data_dep or imp_data_dep:
                in_slice = True

                if not last_state.call:
                    code_object_dependent = True

            #
            # Unconditional jumps
            #
            if last_state.jump and last_state.last_instr.is_uncond_jump():
                in_slice = True

            #
            # Housekeeping for execution trace, stack and next iteration
            #
            # Add instruction to slice
            if in_slice:
                context.DS.append(last_unique_instr)
            # Add uses (for S_D)
            if in_slice and last_unique_instr.is_use() and include_use:
                self.add_uses(context, last_traced_instr)
            # Add control dependencies (for S_C)
            if in_slice:
                self.add_control_dependencies(context, last_unique_instr, code_object_id)
            # Add current instruction to the stack
            if stack_simulation:
                trace_stack.update_pop_operations(pops, last_unique_instr, in_slice)

            curr_instr = last_state.last_instr

            if time.time() > timeout:
                raise SlicingTimeoutException

            if debug_output:
                print(curr_instr)
                print("\tIn slice: ", in_slice, end="")
                if in_slice:
                    print("\t(Reason: ", end="")
                    if exp_data_dep:
                        print("explicit data dependency, ", end="")
                    if imp_data_dep:
                        print("implicit data dependency, ", end="")
                    if control_dependency:
                        print("control dependency", end="")
                    print(")", end="")
                print()
                print("\tlocal_variables:", context.D_local)
                print("\tglobal_variables:", context.D_global)
                print("\tcell_free_variables:", context.D_nonlocal)
                print("\taddresses:", context.D_addresses)
                print("\tattributes:", context.D_attributes)
                print("\tattribute_variables:", context.attribute_variables)
                print("\tS_C:", context.S_C)
                print("\n")

    def _locate_unique_in_bytecode(self, instr: UniqueInstruction, code_object_id: int, basic_block_id: int) -> Instr:
        # Get relevant basic block
        basic_block = None
        bb_offset = -1
        for node in self.known_code_objects.get(code_object_id).original_cfg.nodes:
            if node.index == basic_block_id:
                basic_block = node.basic_block
                bb_offset = node.offset

        if (not basic_block) or (bb_offset < 0):
            raise InstructionNotFoundException

        for instruction in basic_block:
            if instr.opcode == instruction.opcode and instr.lineno == instruction.lineno and \
                    instr.offset == bb_offset:
                return instruction
            bb_offset += 2

        raise InstructionNotFoundException

    def create_unique_instruction(self, file: str, instr: Instr, code_object_id: int, node_id: int,
                                  offset: int) -> UniqueInstruction:
        code_meta = self.known_code_objects.get(code_object_id)
        return UniqueInstruction(file, instr.name, instr.arg, instr.lineno, code_object_id, node_id, code_meta,
                                 offset)

    def check_control_dependency(self, context: SlicingContext, unique_instr: UniqueInstruction,
                                 code_object_id: int) -> bool:
        control_dependency = False

        if not unique_instr.is_cond_branch():
            return False

        cdg: ControlDependenceGraph = self.known_code_objects.get(code_object_id).original_cdg
        curr_node = self.get_node(unique_instr.node_id, cdg)
        successors = cdg.get_successors(curr_node)

        s_c_copy = context.S_C.copy()

        # Check if any instruction on S_C is control dependent on current instruction
        # If so: include current instruction in the slice, remove all instructions control
        # dependent on current instruction
        for instr in context.S_C:
            instr_node = self.get_node(instr.node_id, cdg)
            if instr_node in successors:
                s_c_copy.remove(instr)
                control_dependency = True
        context.S_C = s_c_copy

        return control_dependency

    def add_control_dependencies(self, context: SlicingContext, unique_instr: UniqueInstruction,
                                 code_object_id: int) -> None:
        cdg: ControlDependenceGraph = self.known_code_objects.get(code_object_id).original_cdg
        curr_node = self.get_node(unique_instr.node_id, cdg)
        predecessors = cdg.get_predecessors(curr_node)

        for predecessor in predecessors:
            if not predecessor.is_artificial:
                context.S_C.add(unique_instr)

    @staticmethod
    def organize_by_code_object(instructions: List[UniqueInstruction]) -> Dict[int, List[UniqueInstruction]]:
        code_object_instructions = dict()

        for instruction in instructions:
            if instruction.code_object_id not in code_object_instructions:
                code_object_instructions[instruction.code_object_id] = []
            code_object_instructions[instruction.code_object_id].append(instruction)

        return code_object_instructions

    @staticmethod
    def organize_by_module(dynamic_slice: DynamicSlice):
        module_instructions = dict()

        for instruction in dynamic_slice.sliced_instructions:
            if instruction.file not in module_instructions:
                module_instructions[instruction.file] = []
            module_instructions[instruction.file].append(instruction)

        return module_instructions

    @staticmethod
    def get_node(node_id: int, graph: Union[ControlDependenceGraph, CFG]):
        for node in graph.nodes:
            if node.index == node_id:
                return node

    def check_explicit_data_dependency(self, context: SlicingContext, unique_instr: UniqueInstruction,
                                       traced_instr: ExecutedInstruction) -> Tuple[bool, Set]:
        complete_cover = False
        partial_cover = False

        attribute_creation_uses = set()

        if unique_instr.is_def():
            #
            # Check variable definitions
            #
            if isinstance(traced_instr, ExecutedMemoryInstruction):
                # Check local variables
                if traced_instr.opcode in [STORE_FAST, DELETE_FAST]:
                    complete_cover = self._check_scope_for_def(context.D_local, traced_instr.argument,
                                                               traced_instr.code_object_id, operator.eq)
                # Check global variables (with *_NAME instructions)
                elif traced_instr.opcode in [STORE_NAME, DELETE_NAME]:
                    if self.known_code_objects.get(traced_instr.code_object_id).code_object.co_name == "<module>":
                        complete_cover = self._check_scope_for_def(context.D_global, traced_instr.argument,
                                                                   traced_instr.file, operator.eq)
                    else:
                        # complete_cover = self._check_scope_for_def(context.D_name, traced_instr.argument,
                        #                                            traced_instr.code_object_id, operator.eq)
                        complete_cover = self._check_scope_for_def(context.D_local, traced_instr.argument,
                                                                   traced_instr.code_object_id, operator.eq)
                # Check global variables
                elif traced_instr.opcode in [STORE_GLOBAL, DELETE_GLOBAL]:
                    complete_cover = self._check_scope_for_def(context.D_global, traced_instr.argument,
                                                               traced_instr.file, operator.eq)
                # Check nonlocal variables
                elif traced_instr.opcode in [STORE_DEREF, DELETE_DEREF]:
                    complete_cover = self._check_scope_for_def(context.D_nonlocal, traced_instr.argument,
                                                               traced_instr.code_object_id, operator.contains)
                # Check IMPORT_NAME instructions
                # IMPORT_NAME gets a special treatment: it has an incorrect stack effect,
                # but it is compensated by treating it as a definition
                elif traced_instr.opcode in [IMPORT_NAME]:
                    if traced_instr.arg_address and hex(traced_instr.arg_address) in context.D_addresses and \
                            traced_instr.object_creation:
                        complete_cover = True
                        context.D_addresses.remove(hex(traced_instr.arg_address))
                else:
                    # There should be no other possible instructions
                    raise ValueError("Instruction opcode can not be analyzed for definitions.")

                # When an object, of which certain used attributes are taken from, is created, the slicer
                # has to look for the definition of normal variables instead of these attributes, since
                # they are defined as variables and not as attributes on class/module level.
                if traced_instr.arg_address and traced_instr.object_creation:
                    attribute_uses = set()
                    for use in context.D_attributes:
                        if use.startswith(hex(traced_instr.arg_address)) and \
                                len(use) > len(hex(traced_instr.arg_address)):
                            complete_cover = True
                            attribute_uses.add(use)
                            attribute_creation_uses.add("_".join(use.split("_")[1:]))
                    for use in attribute_uses:
                        context.D_attributes.remove(use)

                # Check for address dependencies
                if traced_instr.is_mutable_type and traced_instr.object_creation:
                    # Note that the definition of an object here means the creation of the object.
                    address_dependency = self._check_scope_for_def(context.D_addresses,
                                                                   hex(traced_instr.arg_address),
                                                                   None, None)
                    if address_dependency:
                        complete_cover = True

                # Check for the attributes which were converted to variables (explained in the previous construct)
                if traced_instr.argument in context.attribute_variables:
                    complete_cover = True
                    context.attribute_variables.remove(traced_instr.argument)

            #
            # Check attribute definitions
            #
            if isinstance(traced_instr, ExecutedAttributeInstruction):
                if traced_instr.combined_attr in context.D_attributes:
                    complete_cover = True
                    context.D_attributes.remove(traced_instr.combined_attr)

                # Partial cover: modification of attribute of object in search for definition
                if hex(traced_instr.src_address) in context.D_addresses:
                    partial_cover = True

        return (complete_cover or partial_cover), attribute_creation_uses

    @staticmethod
    def _check_scope_for_def(context_scope: Set, argument: str, scope_id: Optional[Union[int, str, Tuple]],
                             comp_op) -> bool:
        complete_cover = False
        remove_tuples = set()

        for tup in context_scope:
            if isinstance(tup, Tuple):
                if argument == tup[0] and comp_op(tup[1], scope_id):
                    complete_cover = True
                    remove_tuples.add(tup)
            else:
                if argument == tup:
                    complete_cover = True
                    remove_tuples.add(tup)
        for tup in remove_tuples:
            context_scope.remove(tup)

        return complete_cover

    def add_uses(self, context: SlicingContext, traced_instr: ExecutedInstruction):
        #
        # Add variable uses
        #
        if isinstance(traced_instr, ExecutedMemoryInstruction):
            if traced_instr.arg_address and traced_instr.is_mutable_type:
                context.D_addresses.add(hex(traced_instr.arg_address))

            # Add local variables
            if traced_instr.opcode in [LOAD_FAST]:
                context.D_local.add((traced_instr.argument, traced_instr.code_object_id))
            # Add global variables (with *_NAME instructions)
            elif traced_instr.opcode in [LOAD_NAME]:
                if self.known_code_objects.get(traced_instr.code_object_id).code_object.co_name == "<module>":
                    context.D_global.add((traced_instr.argument, traced_instr.file))
                else:
                    # context.D_name.add((traced_instr.argument, traced_instr.code_object_id))
                    context.D_local.add((traced_instr.argument, traced_instr.code_object_id))
            # Add global variables
            elif traced_instr.opcode in [LOAD_GLOBAL]:
                context.D_global.add((traced_instr.argument, traced_instr.file))
            # Add nonlocal variables
            elif traced_instr.opcode in [LOAD_CLOSURE, LOAD_DEREF, LOAD_CLASSDEREF]:
                variable_scope = set()
                current_code_object_id = traced_instr.code_object_id
                while True:
                    current_code_meta = self.known_code_objects[current_code_object_id]
                    variable_scope.add(current_code_object_id)
                    current_code_object_id = current_code_meta.parent_code_object_id

                    if traced_instr.argument in current_code_meta.code_object.co_cellvars:
                        break
                context.D_nonlocal.add((traced_instr.argument, tuple(variable_scope)))
            else:
                # There should be no other possible instructions
                raise ValueError("Instruction opcode can not be analyzed for definitions.")

        #
        # Add attribute uses
        #
        if isinstance(traced_instr, ExecutedAttributeInstruction):
            # Memory address of loaded attribute
            if traced_instr.arg_address and traced_instr.is_mutable_type:
                context.D_addresses.add(hex(traced_instr.arg_address))

            # Attribute name in combination with source
            if traced_instr.arg_address:
                context.D_attributes.add(traced_instr.combined_attr)

            # Special case for access to composite types and imports:
            # We want the complete definition of composite types and the imported module, respectively
            if not traced_instr.arg_address or traced_instr.opcode == IMPORT_FROM:
                context.D_addresses.add(hex(traced_instr.src_address))

    @staticmethod
    def find_trace_position(trace: ExecutionTrace, slicing_criterion: SlicingCriterion) -> int:
        slice_instr = slicing_criterion.unique_instr
        occurrences = 0

        for ex_instr, position in zip(trace.executed_instructions):
            if ex_instr.file == slice_instr.file and \
                    ex_instr.opcode == slice_instr.opcode and \
                    ex_instr.lineno == ex_instr.lineno and \
                    ex_instr.offset == slice_instr.offset:
                occurrences += 1

                if occurrences == slicing_criterion.occurrence:
                    return position

        raise ValueError("Slicing criterion could not be found in trace")
