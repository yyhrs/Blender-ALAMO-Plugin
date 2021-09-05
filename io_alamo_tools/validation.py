import mathutils
import bpy
import bmesh
from . import utils

def create_export_list(collection, exportHiddenObjects, useNamesFrom):
    export_list = []

    if(collection.hide_viewport):
        return export_list

    for object in collection.objects:
        if(object.type == 'MESH' and (object.hide_viewport == False or exportHiddenObjects)):
            if useNamesFrom == 'OBJECT':
                object.data.name = object.name

            export_list.append(object)

    for child in collection.children:
        export_list.extend(create_export_list(child, exportHiddenObjects, useNamesFrom))

    return export_list

def selectNonManifoldVertices(object):
    if(bpy.context.mode != 'OBJECT'):
        bpy.ops.object.mode_set(mode='OBJECT')
    object.hide_set(False)
    bpy.context.view_layer.objects.active = object
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_non_manifold()

# checks if shadow meshes are correct and checks if material is missing
def checkShadowMesh(mesh_list):
    error = []
    for object in mesh_list:
        if len(object.data.materials) > 0:
            shader = object.data.materials[0].shaderList.shaderList
            if shader in ['MeshShadowVolume.fx', 'RSkinShadowVolume.fx']:
                bm = bmesh.new()  # create an empty BMesh
                bm.from_mesh(object.data)  # fill it in from a Mesh
                bm.verts.ensure_lookup_table()

                for vertex in bm.verts:
                    if not vertex.is_manifold:
                        bm.free()
                        selectNonManifoldVertices(object)
                        error += [f'ALAMO - Non manifold geometry shadow mesh: {object.name}']
                        break

                for edge in bm.edges:
                    if len(edge.link_faces) < 2:
                        bm.free()
                        selectNonManifoldVertices(object)
                        error += [f'ALAMO - Non manifold geometry shadow mesh: {object.name}']
                        break

                bm.free()
        else:
            error += [f'ALAMO - Missing material on object: {object.name}']

    return error

def checkUV(mesh_list):  # throws error if object lacks UVs
    error = []
    for object in mesh_list:
        for material in object.data.materials:
            if material.shaderList.shaderList == 'MeshShadowVolume.fx' or material.shaderList.shaderList == 'RSkinShadowVolume.fx':
                if len(object.data.materials) > 1:
                    error += [f'ALAMO - Multiple materials on shadow volume: {object.name}; remove additional materials']
            if object.HasCollision:
                if len(object.data.materials) > 1:
                    error += [f'ALAMO - Multiple submeshes/materials on collision mesh: {object.name}; remove additional materials']
        if object.data.uv_layers:  # or material.shaderList.shaderList in settings.no_UV_Shaders:  #currently UVs are needed for everything but shadows
            continue
        else:
            error += [f'ALAMO - Missing UV: {object.name}']

    return error

# throws error if armature modifier lacks rig, this would crash the exporter later and checks if skeleton in modifier doesn't match active skeleton
def checkInvalidArmatureModifier(mesh_list):
    activeSkeleton = bpy.context.scene.ActiveSkeleton.skeletonEnum
    error = []
    for object in mesh_list:
        for modifier in object.modifiers:
            if modifier.type == "ARMATURE":
                if modifier.object == None:
                    error += [f'ALAMO - Armature modifier without selected skeleton on: {object.name}']
                    break
                elif modifier.object.type != 'NoneType':
                    if modifier.object.name != activeSkeleton:
                        error += [f"ALAMO - Armature modifier skeleton doesn't match active skeleton on: {object.name}"]
                        break
        for constraint in object.constraints:
            if constraint.type == 'CHILD_OF':
                if constraint.target is not None:
                    # print(type(constraint.target))
                    if constraint.target.name != activeSkeleton:
                        error += [f"ALAMO - Constraint doesn't match active skeleton on: {object.name}"]
                        break

    return error

# checks if the number of faces exceeds max ushort, which is used to save the indices
def checkFaceNumber(mesh_list):
    for object in mesh_list:
        if len(object.data.polygons) > 65535:
            return [f'ALAMO - Face number exceeds uShort max on object: {object.name}; split mesh into multiple objects']
    return []

def checkAutosmooth(mesh_list):  # prints a warning if Autosmooth is used
    for object in mesh_list:
        if object.data.use_auto_smooth:
            return [f'ALAMO -  {object.name} uses autosmooth, ingame shading might not match blender; use edgesplit instead']
    return []

def checkTranslation(mesh_list):  # prints warning when translation is not default
    for object in mesh_list:
        if object.location != mathutils.Vector((0.0, 0.0, 0.0)) or object.rotation_euler != mathutils.Euler((0.0, 0.0, 0.0), 'XYZ') or object.scale != mathutils.Vector((1.0, 1.0, 1.0)):
            return [f'ALAMO - {object.name} is not aligned with the world origin; apply translation or bind to bone']
    return []

def checkTranslationArmature(mesh_list):  # prints warning when translation is not default
    armature = utils.findArmature()
    if armature != None:
        if armature.location != mathutils.Vector((0.0, 0.0, 0.0)) or armature.rotation_euler != mathutils.Euler((0.0, 0.0, 0.0), 'XYZ') or armature.scale != mathutils.Vector((1.0, 1.0, 1.0)):
            return ['ALAMO - active Armature is not aligned with the world origin']
    return []

def validate(mesh_list):
    errors = []
    checklist = [
        checkShadowMesh,
        checkUV,
        checkFaceNumber,
        checkAutosmooth,
        checkTranslation,
        checkTranslationArmature,
        checkInvalidArmatureModifier,
    ]

    for check in checklist:
        test = check(mesh_list)
        print(f'{test = }')
        if test is not None:
            errors += test

    print(f'{errors = }')

    return errors
