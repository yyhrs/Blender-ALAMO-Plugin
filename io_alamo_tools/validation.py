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
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    object.hide_set(False)
    bpy.context.view_layer.objects.active = object
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_non_manifold()

# checks if shadow meshes are correct and checks if material is missing
def checkShadowMesh(object):
    error = []
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

def checkUV(object):  # throws error if object lacks UVs
    error = []
    for material in object.data.materials:
        if material.shaderList.shaderList == 'MeshShadowVolume.fx' or material.shaderList.shaderList == 'RSkinShadowVolume.fx':
            if len(object.data.materials) > 1:
                error += [f'ALAMO - Multiple materials on shadow volume: {object.name}; remove additional materials']
        if object.HasCollision:
            if len(object.data.materials) > 1:
                error += [f'ALAMO - Multiple submeshes/materials on collision mesh: {object.name}; remove additional materials']
    if not object.data.uv_layers:  # or material.shaderList.shaderList in settings.no_UV_Shaders:  #currently UVs are needed for everything but shadows
        error += [f'ALAMO - Missing UV: {object.name}']

    return error

# throws error if armature modifier lacks rig, this would crash the exporter later and checks if skeleton in modifier doesn't match active skeleton
def checkInvalidArmatureModifier(object):
    activeSkeleton = bpy.context.scene.ActiveSkeleton.skeletonEnum
    error = []
    for modifier in object.modifiers:
        if modifier.type == "ARMATURE":
            if modifier.object is None:
                error += [f'ALAMO - Armature modifier without selected skeleton on: {object.name}']
                break
            elif modifier.object.type != 'NoneType':
                if modifier.object.name != activeSkeleton:
                    error += [f"ALAMO - Armature modifier skeleton doesn't match active skeleton on: {object.name}"]
                    break
    for constraint in object.constraints:
        if (
            constraint.type == 'CHILD_OF'
            and constraint.target is not None
            and constraint.target.name != activeSkeleton
        ):
            error += [f"ALAMO - Constraint doesn't match active skeleton on: {object.name}"]
            break

    return error

# checks if the number of faces exceeds max ushort, which is used to save the indices
def checkFaceNumber(object):
    if len(object.data.polygons) > 65535:
        return [f'ALAMO - {object.name} exceeds maximum face limit; split mesh into multiple objects']
    return []

def checkAutosmooth(object):  # prints a warning if Autosmooth is used
    if object.data.use_auto_smooth:
        return [f'ALAMO - {object.name} uses autosmooth, ingame shading might not match blender; use edgesplit instead']
    return []

def checkTranslation(object):  # prints warning when translation is not default
    if object.location != mathutils.Vector((0.0, 0.0, 0.0)) or object.rotation_euler != mathutils.Euler((0.0, 0.0, 0.0), 'XYZ'):
        return [f'ALAMO - {object.name} is not aligned with the world origin; apply translation or bind to bone']
    return []

def checkScale(object):  # prints warning when scale is not default
    if object.scale != mathutils.Vector((1.0, 1.0, 1.0)):
        return [f'ALAMO - {object.name} has non-identity scale. Apply scale.']
    return []

# checks if vertices have 0 or > 1 groups
def checkVertexGroups(object):
    if object.vertex_groups is None or len(object.vertex_groups) == 0:
        return []
    for vertex in object.data.vertices:
        total = 0
        for group in vertex.groups:
            if group.weight not in [0, 1]:
                return [f'ALAMO - Object {object.name} has improper vertex groups']
            total += group.weight
        if total not in [0, 1]:
            return [f'ALAMO - Object {object.name} has improper vertex groups']

    return []

def checkNumBones(object):
    if type(object) != type(None) and object.type == 'MESH':
        material = bpy.context.active_object.active_material
        if material is not None and material.shaderList.shaderList.find("RSkin") > -1:
            used_groups = []
            for vertex in object.data.vertices:
                for group in vertex.groups:
                    if group.weight == 1:
                        used_groups.append(group.group)

            if len(set(used_groups)) > 23:
                return [f'ALAMO - Object {object.name} has more than 23 bones.']
    return []

def checkTranslationArmature():  # prints warning when translation is not default
    armature = utils.findArmature()
    if armature is not None:
        if armature.location != mathutils.Vector((0.0, 0.0, 0.0)) or armature.rotation_euler != mathutils.Euler((0.0, 0.0, 0.0), 'XYZ') or armature.scale != mathutils.Vector((1.0, 1.0, 1.0)):
            return [f'ALAMO - Armature {armature} is not aligned with the world origin; apply translation']
    return []

def checkProxyKeyframes():
    actions = bpy.data.actions
    local_errors = []
    for action in actions:
        for fcurve in action.fcurves:
            if fcurve.data_path.find("proxyIsHiddenAnimation") > -1 and len(fcurve.keyframe_points) > 2:
                local_errors += [f'ALAMO - Action {action.name} has fcurves with more than 2 proxy keyframes.']
                break
    return local_errors


def validate(mesh_list):
    errors = []
    checklist = [
        checkShadowMesh,
        checkUV,
        checkFaceNumber,
        checkAutosmooth,
        checkTranslation,
        checkInvalidArmatureModifier,
        checkScale,
        checkVertexGroups,
        checkNumBones,
    ]
    checklist_no_object = [
        checkTranslationArmature,
        checkProxyKeyframes,
    ]

    for check in checklist:
        for object in mesh_list:
            errors += check(object)
    for check in checklist_no_object:
        errors += check()

    return errors
