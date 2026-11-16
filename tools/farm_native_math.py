"""Offline emulation of the inspected DST 762172 float32 query arithmetic."""
import struct


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def distance_squared(ax, ay, az, bx, by, bz):
    dx, dy, dz = (f32(f32(a)-f32(b)) for a, b in ((ax,bx),(ay,by),(az,bz)))
    return f32(f32(dz*dz) + f32(f32(dx*dx) + f32(dy*dy)))


def radius_squared(radius):
    radius=f32(radius)
    return f32(radius*radius)
