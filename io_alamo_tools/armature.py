centers = []

for object in bpy.context.selected_objects:
    center = object.matrix_world @ (1 / 8 * sum((Vector(vector) for vector in object.bound_box), Vector())) 
    object.location -= center
    centers += [center]

print(centers)

import random

index = 0

for vector in centers:
    print(str(index))
    bone = bpy.data.armatures['Armature'].edit_bones.new(str(index))
    bone.head = vector
    bone.tail = vector + Vector((random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1))).normalized()
    index += 1



import random

index = 0
objects = []

for object in bpy.context.selected_objects:
    objects += [object]

random.shuffle(objects)

for object in objects:
    constraint = object.constraints.new('CHILD_OF')
    constraint.target = bpy.data.objects['Armature']
    constraint.subtarget = str(index)
    constraint.inverse_matrix = Matrix.Identity(4)
    index += 1














for object in bpy.context.selected_objects:
    for constraint in object.constraints:
        constraint.inverse_matrix = Matrix.Identity(4)


import random

index = 0
objects = []
for object in bpy.context.selected_objects:
    objects += [object]
random.shuffle(objects)
for object in objects:
    for constraint in object.constraints[:]:
        constraint.subtarget = str(index)
    index += 1