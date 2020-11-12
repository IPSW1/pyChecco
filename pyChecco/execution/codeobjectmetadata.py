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

import dis

from types import CodeType
from typing import Optional

from pyChecco.analyses.controlflow.cfg import CFG
from pyChecco.analyses.controlflow.controldependencegraph import ControlDependenceGraph


class CodeObjectMetaData:
    """Stores meta data of a code object."""

    def __init__(self, filename: str, code_object: CodeType, parent_code_object_id: Optional[int],
                 original_cfg: CFG, cfg: CFG, original_cdg: ControlDependenceGraph) -> None:
        self.filename = filename
        self.code_object = code_object
        self.parent_code_object_id = parent_code_object_id
        self.original_cfg = original_cfg
        self.original_cdg = original_cdg
        self.cfg = cfg
        self.disassembly = list(dis.get_instructions(code_object))
