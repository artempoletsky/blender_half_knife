# ##### BEGIN GPL LICENSE BLOCK #####
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####


import time

last_time = 0
start_time = 0

enabled = True


def msg(time, message):
    print(("%.2f" % (time* 1000)) + "ms: " + message)

def start():
    global last_time, start_time, enabled
    if not enabled:
        return
    last_time = time.time()
    start_time = last_time
    print("---------------------------------")
    print("--------------START--------------")
    print("---------------------------------")


def lap(message):
    global last_time, enabled
    if not enabled:
        return
    current = time.time()
    msg(current - last_time, message)
    last_time = current

def finish():
    global start_time, enabled
    if not enabled:
        return
    current = time.time()
    msg(current - start_time, "Time total")
