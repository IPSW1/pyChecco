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


def abc_generator():  # included in slice
    a = "a"  # included in slice
    b = "b"
    c = "c"
    yield a  # included in slice
    yield b
    yield c


def abc_xyz_generator():  # included in slice
    x = "x"  # included in slice
    y = "y"
    z = "z"

    yield from abc_generator()  # included in slice
    yield x  # included in slice
    yield y
    yield z


generator = abc_xyz_generator()  # included in slice
result = ""  # included in slice
for letter in generator:  # included in slice
    if letter == "x" or letter == "a":  # included in slice
        result += letter  # included in slice
