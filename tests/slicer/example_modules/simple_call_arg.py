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


def callee(a: int, b: int):
    c = a + b  # this line must not be included, since it has no effect on the result
    return a


foo = 1  # must be included, is used by callee() and influences the result
bar = 2  # currently included (I.D.D.); but a bit imprecise: used as parameter, but not in actual function
result = callee(foo, bar)
