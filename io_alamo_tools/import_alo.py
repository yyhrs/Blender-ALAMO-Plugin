import bpy
from . import settings, utils, import_ala

from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       EnumProperty,
                       PointerProperty,
                       )
from bpy.types import (Panel,
                       Operator,
                       PropertyGroup,
                       )
import struct
import mathutils
import math
from math import pi
from mathutils import Vector
from bpy.props import *
from bpy_extras.io_utils import ExportHelper, ImportHelper
import sys
import os
from os import listdir
import bmesh


def boneEnumCallback(scene, context):
    bones = [('None', 'None', '', '', 0)]
    counter = 1
    armature = utils.findArmature()
    if(armature != None):
        for bone in armature.data.bones:
            bones.append((bone.name, bone.name, '', '', counter))
            counter += 1
    bones.sort(key=lambda tup: tup[0])
    return bones


class ALO_Importer(bpy.types.Operator):
    """ALO Importer"""      # blender will use this as a tooltip for menu items and buttons.
    bl_idname = "import_mesh.alo"        # unique identifier for buttons and menu items to reference.
    bl_label = "Import ALO File"         # display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}  # enable undo for the operator.
    filename_ext = ".alo"
    filter_glob: StringProperty(default="*.alo", options={'HIDDEN'})
    bl_info = {
        "name": "ALO Importer",
        "category": "Import",
    }

    parentName: EnumProperty(
        name='Attachment Bone',
        description="Bone that imported models are attached to",
        items=boneEnumCallback
    )

    importAnimations: BoolProperty(
        name="Import Animations",
        description="Import the model's animations from the same path",
        default=True,
    )

    textureOverride: EnumProperty(
        name = "Submod Texture Override",
        description = "Try to import textures from a different submod",
        items=(
            ("NONE", "None", ""),
            ('CoreSaga', "Core Saga", ""),
            ('FotR', "Fall of the Republic", ""),
            ('GCW', "Imperial Reign", ""),
            ('Rev', "Revan's Revenge", ""),
            ('TR', "Thrawn's Revenge", ""),
        ),
        default="NONE",
    )

    def draw(self, context):
        layout = self.layout

        layout.prop(self, "importAnimations")
        layout.prop(self, "parentName")
        layout.prop(self, "textureOverride")

    filepath: StringProperty(
        name="File Path", description="Filepath used for importing the ALO file", maxlen=1024, default="")

    # execute() is called by blender when running the operator.
    def execute(self, context):
        # main structure

        def process_active_junk():
            meshNameList = []
            # loop over file until end is reached
            while(file.tell() < os.path.getsize(self.properties.filepath)):
                active_chunk = file.read(4)
                # print(active_chunk)
                if active_chunk == b"\x00\x02\x00\00":
                    armatureData = createArmature()
                elif active_chunk == b"\x00\x04\x00\00":
                    file.seek(4, 1)  # skip size
                    meshName = processMeshChunk()
                    meshNameList.append(meshName)
                elif active_chunk == b"\x00\x13\x00\00":  # light chunk is irrelevant
                    self.report({"WARNING"}, "ALAMO - File contains light objects, these are not supported and might cause minor issues")
                    size = read_chunk_length()
                    file.seek(size, 1)  # skip to next chunk
                elif active_chunk == b"\x00\x06\x00\00":
                    file.seek(8, 1)  # skip size and next header
                    n_objects_proxies = get_n_objects_n_proxies()
                    n_objects = n_objects_proxies['n_objects']
                    n_proxies = n_objects_proxies['n_proxies']
                    print('Found Connection Chunk')
                elif active_chunk == b"\x02\x06\x00\00":
                    file.seek(4, 1)  # skip size
                    read_conncetion(armatureData, meshNameList)
                elif active_chunk == b"\x03\x06\x00\00":
                    read_proxy()

        #armature and bones

        class Armature():
            def __init__(self):
                self.bones = []
                self.boneCount = 0

        class Bone():
            def __init__(self):
                self.name = ''
                self.parentIndex = 0
                self.visible = 0
                self.billboard = 0
                self.matrix = None

        def removeShadowDoubles():
            for object in bpy.data.objects:
                if(object.type == 'MESH'):
                    if(len(object.material_slots) <= 0):
                        continue  # already existing objects might not have a material
                    shader = object.material_slots[0].material.shaderList.shaderList
                    if (shader == 'MeshCollision.fx' or shader == 'RSkinShadowVolume.fx' or shader == 'MeshShadowVolume.fx'):
                        bpy.ops.object.select_all(action='DESELECT')

                        bpy.context.view_layer.objects.active = object
                        object.select_set(True)
                        bpy.ops.object.mode_set(mode='EDIT')
                        bpy.ops.mesh.select_all(action='SELECT')
                        bpy.ops.mesh.remove_doubles()
                        bpy.ops.object.mode_set(mode='OBJECT')

        def createArmature():

            global fileName

            # create armature
            armatureBlender = bpy.data.armatures.new(fileName + "Armature")

            # create object
            armatureObj = bpy.data.objects.new(
                fileName + "Rig", object_data=armatureBlender)

            # Link object to collection
            importCollection.objects.link(armatureObj)
            bpy.context.view_layer.objects.active = armatureObj
            bpy.context.view_layer.update()

            # adjust settings and enter edit-mode
            armatureObj = bpy.context.object
            armatureObj.show_in_front = True
            utils.setModeToEdit()

            armatureBlender.display_type = 'STICK'
            armatureData = Armature()

            file.seek(4, 1)  # skip size
            get_bone_count(armatureData)

            counter = 0
            while (counter < armatureData.boneCount):
                process_bone(armatureData)
                counter += 1

            for bone in armatureData.bones:
                createBone(bone, armatureBlender, armatureData)

            bpy.ops.object.mode_set(mode='OBJECT')

            bpy.context.scene.ActiveSkeleton.skeletonEnum = armatureObj.name

            return armatureData

        def get_bone_count(armatureData):
            file.seek(8, 1)  # skip header and size
            bone_count = struct.unpack("<I", file.read(4))[0]
            armatureData.boneCount = bone_count
            file.seek(124, 1)  # skip padding

        def process_bone(armatureData):
            bone = Bone()
            armatureData.bones.append(bone)

            file.seek(12, 1)  # skip header and size and next header
            bone.name = cut_string(read_string())
            file.seek(8, 1)  # skip header and size
            bone.parentIndex = struct.unpack('<I', file.read(4))[0]
            if bone.name == 'Root':
                bone.parentIndex = 0
            bone.visible = struct.unpack('<I', file.read(4))[0]
            bone.billboard = struct.unpack('<I', file.read(4))[0]
            matrix1_1 = struct.unpack('<f', file.read(4))[0]
            matrix1_2 = struct.unpack('<f', file.read(4))[0]
            matrix1_3 = struct.unpack('<f', file.read(4))[0]
            matrix1_4 = struct.unpack('<f', file.read(4))[0]
            matrix2_1 = struct.unpack('<f', file.read(4))[0]
            matrix2_2 = struct.unpack('<f', file.read(4))[0]
            matrix2_3 = struct.unpack('<f', file.read(4))[0]
            matrix2_4 = struct.unpack('<f', file.read(4))[0]
            matrix3_1 = struct.unpack('<f', file.read(4))[0]
            matrix3_2 = struct.unpack('<f', file.read(4))[0]
            matrix3_3 = struct.unpack('<f', file.read(4))[0]
            matrix3_4 = struct.unpack('<f', file.read(4))[0]
            bone_row_1 = ((matrix1_1, matrix1_2, matrix1_3, matrix1_4))
            bone_row_2 = ((matrix2_1, matrix2_2, matrix2_3, matrix2_4))
            bone_row_3 = ((matrix3_1, matrix3_2, matrix3_3, matrix3_4))
            bone_row_4 = (0, 0, 0, 1)
            bone.matrix = ((bone_row_1), (bone_row_2),
                           (bone_row_3), (bone_row_4))

        def createBone(boneData, armatureBlender, armatureData):
            billboardModeArray = ["Disable", "Parallel", "Face", "ZAxis View",
                                  "ZAxis Light", "ZAxis Wind", "Sunlight Glow", "Sun"]

            bone_matrix = []  # initialize for use
            bone = armatureBlender.edit_bones.new(boneData.name)
            bone.tail = mathutils.Vector([0, 1, 0])

            if boneData.visible == 1:
                bone.Visible = True
            else:
                bone.Visible = False

            parent = armatureData.bones[boneData.parentIndex].name
            if(parent != 'Root'):
                bone.parent = armatureBlender.edit_bones[parent]
                bone.matrix = bone.parent.matrix @ mathutils.Matrix(
                    boneData.matrix)
            else:
                bone.matrix = mathutils.Matrix(boneData.matrix)

            bone.billboardMode.billboardMode = billboardModeArray[boneData.billboard]

            bpy.ops.object.mode_set(mode='EDIT')

        #mesh and material

        class meshClass():
            def __init__(self):
                self.name = ''
                self.isHidden = False
                self.collision = False
                self.nMaterials = 0
                self.subMeshList = []

            def getNVerts(self):
                nVerts = 0
                for subMesh in self.subMeshList:
                    nVerts += subMesh.nVertices
                return nVerts

        class subMeshClass():
            def __init__(self):
                self.nVertices = 0
                self.nFaces = 0
                self.shader = None
                self.vertices = []
                self.faces = []
                self.faceOffset = 0
                self.UVs = []
                self.material = None
                self.animationMapping = []
                self.boneIndex = []

        def construct_mesh(currentMesh):

            vertices = []
            faces = []
            UVs = []
            animationMapping = []
            for subMesh in currentMesh.subMeshList:
                vertices += subMesh.vertices
                faces += subMesh.faces
                UVs += subMesh.UVs
                animationMapping += subMesh.animationMapping

            mesh.from_pydata(vertices, [], faces)

            # Update mesh with new data
            mesh.update(calc_edges=True)

            polys = mesh.polygons
            for p in polys:
                p.use_smooth = True

            # assign materials correctly
            if currentMesh.nMaterials > 1:
                currentSubMeshMaxFaceIndex = currentMesh.subMeshList[0].nFaces
                subMeshCounter = 0
                for face in mesh.polygons:
                    if face.index >= currentSubMeshMaxFaceIndex:
                        subMeshCounter += 1
                        currentSubMeshMaxFaceIndex += currentMesh.subMeshList[subMeshCounter].nFaces
                    face.material_index = subMeshCounter

            # create UVs
            createUVLayer("UVMap", UVs)
            assign_vertex_groups(animationMapping, currentMesh)

            return mesh

        def readMeshInfo(currentMesh):
            file.seek(8, 1)  # skip size and header

            nMaterials = struct.unpack("I", file.read(4))[0]
            currentMesh.nMaterials = nMaterials

            file.seek(24 + 4, 1)  # skip bounding box size and unused
            isHidden = struct.unpack("<I", file.read(4))[0]

            if isHidden == 1:
                currentMesh.isHidden = True

            collision = struct.unpack("<I", file.read(4))[0]
            if collision == 1:
                currentMesh.collision = True

            file.seek(88, 1)
            create_object(currentMesh)

        def get_mesh_name():
            file.seek(4, 1)  # skip header
            length = read_chunk_length()
            counter = 0
            mesh_name = ""
            while counter < length - 1:
                letter = str(file.read(1))
                letter = letter[2:len(letter) - 1]
                mesh_name += letter
                counter += 1
            file.seek(1, 1)  # skip end byte of name

            return cut_string(mesh_name)

        def get_n_vertices_n_primitives(currentSubMesh):
            currentSubMesh.nVertices = struct.unpack("<I", file.read(4))[0]
            currentSubMesh.nFaces = struct.unpack("<I", file.read(4))[0]
            file.seek(120, 1)

        def processMeshChunk():
            # name chunk
            currentMesh = meshClass()
            meshList.append(currentMesh)
            currentMesh.name = get_mesh_name()

            readMeshInfo(currentMesh)

            counter = 0
            faceOffset = 0
            while (counter < currentMesh.nMaterials):
                currentSubMesh = subMeshClass()
                currentMesh.subMeshList.append(currentSubMesh)

                currentSubMesh.faceOffset = faceOffset
                read_material_info_chunk(currentSubMesh)
                read_mesh_data(currentSubMesh)
                faceOffset += currentSubMesh.nVertices
                counter += 1

            contructed_mesh = construct_mesh(currentMesh)
            name = contructed_mesh.name
            return name

        def read_mesh_data(currentSubMesh):
            file.seek(4, 1)  # skip header
            meshDataChunkSize = read_chunk_length()
            currentPosition = file.tell()
            while (file.tell() < currentPosition + meshDataChunkSize):
                active_chunk = file.read(4)
                if active_chunk == b"\x01\x00\x01\00":
                    file.seek(4, 1)  # skip size, chunk is always 128 byte
                    get_n_vertices_n_primitives(currentSubMesh)
                elif active_chunk == b"\x02\x00\x01\00":
                    size = read_chunk_length()
                    file.seek(size, 1)  # skip to next chunk
                elif active_chunk == b"\x04\x00\x01\00":
                    file.seek(4, 1)  # skip size
                    faces = process_index_buffer(currentSubMesh)
                elif active_chunk == b"\x06\x00\x01\00":
                    read_animation_mapping(currentSubMesh)
                elif active_chunk == b"\x07\x00\x01\00":
                    file.seek(4, 1)  # skip size
                    vertex_data = process_vertex_buffer_2(
                        False, currentSubMesh)
                elif active_chunk == b"\x05\x00\x01\00":
                    file.seek(4, 1)  # skip size
                    # old version of the chunk
                    vertex_data = process_vertex_buffer_2(True, currentSubMesh)
                elif active_chunk == b"\x00\x12\x00\00":
                    size = read_chunk_length()
                    file.seek(size, 1)  # skip to next chunk

        def read_material_info_chunk(currentSubMesh):
            file.seek(4, 1)  # skip header
            materialChunkSize = read_chunk_length()
            currentPosition = file.tell()
            while (file.tell() < currentPosition + materialChunkSize):
                active_chunk = file.read(4)
                if active_chunk == b"\x01\x01\x01\00":
                    set_alamo_shader(currentSubMesh)
                elif active_chunk == b"\x02\x01\x01\00":
                    read_int(currentSubMesh.material)
                elif active_chunk == b"\x03\x01\x01\00":
                    read_float(currentSubMesh.material)
                elif active_chunk == b"\x04\x01\x01\00":
                    read_float3(currentSubMesh.material)
                elif active_chunk == b"\x05\x01\x01\00":
                    process_texture_chunk(currentSubMesh.material)
                elif active_chunk == b"\x06\x01\x01\00":
                    read_float4(currentSubMesh.material)
            create_material(currentSubMesh)
            set_up_textures(currentSubMesh.material)

        def read_animation_mapping(currentSubMesh):
            chunk_size = read_chunk_length()  # read chunk size
            read_counter = chunk_size / 4
            counter = 0
            animation_mapping = []
            while counter < read_counter:
                currentSubMesh.animationMapping.append(
                    struct.unpack("I", file.read(4))[0])
                counter += 1
            return animation_mapping

        def material_group_additive(context, operator, group_name, material, is_emissive):
            node_group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

            node = node_group.nodes.new
            link = node_group.links.new

            group_out = node('NodeGroupOutput')
            group_out.location.x += 200.0
            node_group.interface.new_socket(socket_type='NodeSocketShader', name='Surface', in_out='OUTPUT')

            mix_shader = node("ShaderNodeMixShader")

            transparent = node("ShaderNodeBsdfTransparent")
            transparent.location.x -= 200
            transparent.location.y -= 50

            base_image_node = node("ShaderNodeTexImage")
            base_image_node.location.x -= 500

            if is_emissive:
                group_in = node('NodeGroupInput')
                group_in.location.x -= 700
                emissive = node_group.interface.new_socket(socket_type='NodeSocketFloat',
                                                           name='Emissive Strength',
                                                           in_out='INPUT')
                emissive.default_value = 100.0
                color = node("ShaderNodeEmission")
                link(group_in.outputs[0], color.inputs[1])
                eevee_alpha_fix = node("ShaderNodeInvert")
                eevee_alpha_fix.location.x -= 500
                eevee_alpha_fix.location.y += 300
                # Fix for obnoxious transparency bug in Eevee
                link(base_image_node.outputs[1], eevee_alpha_fix.inputs[1])
                link(base_image_node.outputs['Color'],
                     mix_shader.inputs['Fac'])

            else:
                color = node("ShaderNodeBsdfDiffuse")
                link(base_image_node.outputs['Alpha'],
                     mix_shader.inputs['Fac'])

            color.location.x -= 200
            color.location.y -= 150

            link(base_image_node.outputs['Color'], color.inputs[0])
            link(transparent.outputs[0], mix_shader.inputs[1])
            link(color.outputs[0], mix_shader.inputs[2])

            if material.BaseTexture != 'None' and material.BaseTexture in bpy.data.images:
                diffuse_texture = bpy.data.images[material.BaseTexture]
                diffuse_texture.alpha_mode = 'CHANNEL_PACKED'
                base_image_node.image = diffuse_texture

            link(mix_shader.outputs[0], group_out.inputs[0])

            return node_group

        def material_group_basic(context, operator, group_name, material):
            node_group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

            node = node_group.nodes.new
            link = node_group.links.new

            group_in = node('NodeGroupInput')
            group_in.location.x -= 700
            node_group.interface.new_socket(socket_type='NodeSocketColor',
                                            name='Team Color',
                                            in_out='INPUT')
            spec = node_group.interface.new_socket(socket_type='NodeSocketFloat',
                                                   name='Specular Intensity',
                                                   in_out='INPUT')
            spec.default_value = 0.1

            group_out = node('NodeGroupOutput')
            node_group.interface.new_socket(socket_type='NodeSocketColor',
                                            name='Base Color',
                                            in_out='OUTPUT')
            node_group.interface.new_socket(socket_type='NodeSocketFloat',
                                            name='Specular',
                                            in_out='OUTPUT')
            node_group.interface.new_socket(socket_type='NodeSocketVector',
                                            name='Normal',
                                            in_out='OUTPUT')

            base_image_node = node("ShaderNodeTexImage")
            base_image_node.location.x -= 500

            mix_node = node("ShaderNodeMixRGB")
            mix_node.blend_type = 'COLOR'
            mix_node.location.x -= 200

            link(base_image_node.outputs['Color'], mix_node.inputs['Color1'])
            link(base_image_node.outputs['Alpha'], mix_node.inputs['Fac'])
            link(mix_node.outputs['Color'], group_out.inputs['Base Color'])

            normal_image_node = node("ShaderNodeTexImage")
            normal_image_node.location.x -= 1100.0
            normal_image_node.location.y -= 300.0

            normal_split = node("ShaderNodeSeparateRGB")
            normal_split.location.x -= 800
            normal_split.location.y -= 300
            normal_invert = node("ShaderNodeMath")
            normal_invert.operation = 'SUBTRACT'
            normal_invert.inputs[0].default_value = 1
            normal_invert.location.x -= 600
            normal_invert.location.y -= 300
            normal_combine = node("ShaderNodeCombineRGB")
            normal_combine.location.x -= 400
            normal_combine.location.y -= 300

            normal_map_node = node("ShaderNodeNormalMap")
            normal_map_node.space = 'TANGENT'
            normal_map_node.location.x -= 200.0
            normal_map_node.location.y -= 300.0

            specular_multiply = node("ShaderNodeMath")
            specular_multiply.operation = 'MULTIPLY'
            specular_multiply.location.x -= 800
            specular_multiply.location.y -= 100

            link(normal_image_node.outputs['Color'],
                 normal_split.inputs['Image'])
            link(normal_split.outputs['R'], normal_combine.inputs['R'])
            link(normal_split.outputs['G'], normal_invert.inputs[1])
            link(normal_invert.outputs[0], normal_combine.inputs['G'])
            link(normal_split.outputs['B'], normal_combine.inputs['B'])
            link(normal_combine.outputs[0], normal_map_node.inputs[1])
            link(normal_map_node.outputs[0], group_out.inputs[2])

            link(normal_image_node.outputs['Alpha'],
                 specular_multiply.inputs[0])

            link(group_in.outputs['Team Color'], mix_node.inputs['Color2'])
            link(group_in.outputs['Specular Intensity'],
                 specular_multiply.inputs[1])
            link(specular_multiply.outputs[0], group_out.inputs[1])

            if material.BaseTexture != 'None' and material.BaseTexture in bpy.data.images:
                diffuse_texture = bpy.data.images[material.BaseTexture]
                diffuse_texture.alpha_mode = 'CHANNEL_PACKED'
                base_image_node.image = diffuse_texture

            if material.NormalTexture != 'None' and material.NormalTexture in bpy.data.images:
                normal_texture = bpy.data.images[material.NormalTexture]
                normal_texture.alpha_mode = 'CHANNEL_PACKED'
                normal_image_node.image = normal_texture
                normal_image_node.image.colorspace_settings.name = 'Non-Color'

            return node_group

        def set_up_textures(material):
            material.use_nodes = True
            nt = material.node_tree
            nodes = nt.nodes
            links = nt.links
            
            # clean up
            while(nodes):
                nodes.remove(nodes[0])

            output = nodes.new("ShaderNodeOutputMaterial")
            custom_node_name = material.name + "Group"
            my_group = 'null'

            if ("Additive" in material.shaderList.shaderList):
                material.blend_method = "BLEND"
                my_group = material_group_additive(
                    self, context, custom_node_name, material, True)
                mat_group = nt.nodes.new("ShaderNodeGroup")
                mat_group.node_tree = bpy.data.node_groups[my_group.name]
                mat_group.location.x -= 200.0
                links.new(mat_group.outputs[0], output.inputs['Surface'])
            elif ("Alpha" in material.shaderList.shaderList):
                material.blend_method = "BLEND"
                my_group = material_group_additive(
                    self, context, custom_node_name, material, False)
                mat_group = nt.nodes.new("ShaderNodeGroup")
                mat_group.node_tree = bpy.data.node_groups[my_group.name]
                mat_group.location.x -= 200.0
                links.new(mat_group.outputs[0], output.inputs['Surface'])
            else:
                bsdf = nodes.new("ShaderNodeBsdfPrincipled")
                bsdf.inputs['Metallic'].default_value = 0.1
                bsdf.inputs['Roughness'].default_value = 0.2
                bsdf.location.x -= 300.0
                links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
                my_group = material_group_basic(
                    self, context, custom_node_name, material)
                mat_group = nt.nodes.new("ShaderNodeGroup")
                mat_group.node_tree = bpy.data.node_groups[my_group.name]
                mat_group.location.x -= 500.0
                links.new(mat_group.outputs[0], bsdf.inputs['Base Color'])
                links.new(mat_group.outputs[1], bsdf.inputs[5])
                links.new(mat_group.outputs[2], bsdf.inputs['Normal'])

        def create_material(currentSubMesh):
            if currentSubMesh.material.name != "DUMMYMATERIAL":
                return

            oldMat = currentSubMesh.material

            texName = currentSubMesh.material.BaseTexture
            texName = texName[0:len(texName) - 4] + " Material"
            if texName in bpy.data.materials and oldMat.shaderList.shaderList != bpy.data.materials.get(texName).shaderList.shaderList:
                texName += "1"
            mat = assign_material(texName)

            mat.shaderList.shaderList = oldMat.shaderList.shaderList

            # TODO: Extract set_alamo_shader's shader finder to new function, use that here.
            material_props = ["BaseTexture", "NormalTexture", "GlossTexture", "WaveTexture", "DistortionTexture", "CloudTexture", "CloudNormalTexture", "Emissive", "Diffuse", "Specular", "Shininess", "Colorization", "DebugColor", "UVOffset", "Color", "UVScrollRate", "DiffuseColor",
                              "EdgeBrightness", "BaseUVScale", "WaveUVScale", "DistortUVScale", "BaseUVScrollRate", "WaveUVScrollRate", "DistortUVScrollRate", "BendScale", "Diffuse1", "CloudScrollRate", "CloudScale", "SFreq",  "TFreq", "DistortionScale", "Atmosphere", "CityColor", "AtmospherePower", "SpecularTexture", "UVOffsetX", "UVOffsetY", "UVScaleFactor", "MaskTexture"]

            for texture in material_props:
                if texture in oldMat:
                    mat[texture] = oldMat[texture]

            obj = bpy.context.object
            materials = []
            for material in obj.data.materials:
                if material.name != "DUMMYMATERIAL":
                    materials.append(material)
            obj.data.materials.clear()
            for material in materials:
                obj.data.materials.append(material)
            obj.data.materials.append(mat)
            currentSubMesh.material = mat

        def assign_material(name):
            if name in bpy.data.materials:
                return bpy.data.materials.get(name)
            else:
                return bpy.data.materials.new(name)


        def create_object(currentMesh):
            global mesh
            mesh = bpy.data.meshes.new(currentMesh.name)
            object = bpy.data.objects.new(mesh.name, mesh)
            global MeshNameList
            MeshNameList.append(object.name)

            # Link object to collection
            importCollection.objects.link(object)
            bpy.context.view_layer.objects.active = object
            bpy.context.view_layer.update()

            context.view_layer.objects.active = object  # make created object active
            object.show_transparent = True

            if (currentMesh.isHidden == 1):
                object.Hidden = True

            if (currentMesh.collision == 1):
                object.HasCollision = True

            # create vertex groups
            armature = utils.findArmature()
            for bone in armature.data.bones:
                vertgroup = object.vertex_groups.new(name=bone.name)

        def process_vertex_buffer_2(legacy, currentSubMesh):
            f = struct.Struct('f')  # unpack as float
            i = struct.Struct('I')
            counter = 0
            while counter < currentSubMesh.nVertices:
                coX = f.unpack(file.read(4))[0]
                coY = f.unpack(file.read(4))[0]
                coZ = f.unpack(file.read(4))[0]
                currentSubMesh.vertices.append(
                    mathutils.Vector((coX, coY, coZ)))
                file.seek(12, 1)
                UV = []
                UV.append(f.unpack(file.read(4))[0])
                UV.append(f.unpack(file.read(4))[0] * (-1))
                currentSubMesh.UVs.append(UV)
                file.seek(64, 1)
                if not legacy:
                    file.seek(16, 1)
                currentSubMesh.boneIndex.append(i.unpack(file.read(4))[0])
                file.seek(28, 1)
                counter += 1

        def process_index_buffer(currentSubMesh):
            h = struct.Struct('H')  # unpack as unsigned Short
            counter = 0
            while counter < currentSubMesh.nFaces:
                face = []
                face.append(h.unpack(file.read(2))[
                            0] + currentSubMesh.faceOffset)
                face.append(h.unpack(file.read(2))[
                            0] + currentSubMesh.faceOffset)
                face.append(h.unpack(file.read(2))[
                            0] + currentSubMesh.faceOffset)
                currentSubMesh.faces.append(face)
                counter += 1

        def process_texture_chunk(material):
            file.seek(5, 1)  # skip chunk size and child header
            length = struct.unpack("H", file.read(
                1) + b'\x00')  # get string length
            global texture_function_name
            texture_function_name = ""
            counter = 0
            while counter < length[0] - 1:
                letter = str(file.read(1))
                letter = letter[2:len(letter) - 1]
                texture_function_name = texture_function_name + letter
                counter += 1
            file.seek(1, 1)  # skip string end byte
            file.seek(1, 1)  # skip child header
            length = struct.unpack("H", file.read(1) + b'\x00')  # get string length
            texture_name = ""
            counter = 0
            while counter < length[0] - 1:
                letter = str(file.read(1))
                letter = letter[2:len(letter) - 1]
                texture_name = texture_name + letter
                counter += 1
            # replace texture format with .dds
            if texture_name != "None":
                texture_name = texture_name[0:len(texture_name) - 4] + ".dds"
            file.seek(1, 1)  # skip string end byte
            
            load_image(texture_name)
            exec('material.' + texture_function_name + '= texture_name')

        def createUVLayer(layerName, uv_coordinates):
            vert_uvs = uv_coordinates
            mesh.uv_layers.new(name=layerName)
            mesh.uv_layers[-1].data.foreach_set(
                "uv", [uv for pair in [vert_uvs[l.vertex_index] for l in mesh.loops] for uv in pair])

        def set_alamo_shader(currentSubMesh):  # create material and assign
            shaderName = read_string()
            obj = bpy.context.object

            if shaderName == 'MeshCollision.fx':
                mat = assign_material("COLLISION")
            elif shaderName in ['RSkinShadowVolume.fx', 'MeshShadowVolume.fx']:
                mat = assign_material("SHADOW")
            else:
                mat = assign_material("DUMMYMATERIAL")
                # DUMMYMATERIAL is a temporary material to allow Alamo shader properties to be assigned.
                # Can't assign final material because material names are now based on BaseTexture, and textures aren't known yet. Probably a better way to do this.

            # find shader, ignoring case
            currentKey = None
            for key in settings.material_parameter_dict:
                if(key.lower() == shaderName.lower()):
                    currentKey = key
                    break

            if currentKey is None:
                self.report({"WARNING"}, "ALAMO - Unknown shader: " + shaderName +
                      " setting shader to alDefault.fx")
                currentKey = "alDefault.fx"

            mat.shaderList.shaderList = currentKey

            obj.data.materials.append(mat)
            currentSubMesh.material = mat

        def assign_vertex_groups(animation_mapping, currentMesh):
            # assign vertex groups
            object = bpy.context.view_layer.objects.active
            counter = 0
            armatureObject = utils.findArmature()
            n_vertices = currentMesh.getNVerts()

            bone_indices = []
            for subMesh in currentMesh.subMeshList:
                bone_indices += subMesh.boneIndex

            if(len(animation_mapping) != 0):
                # add armature modifier
                mod = object.modifiers.new('MyRigModif', 'ARMATURE')
                mod.object = armatureObject
                mod.use_bone_envelopes = False
                mod.use_vertex_groups = True

                while counter < n_vertices:
                    object.vertex_groups[animation_mapping[bone_indices[counter]]].add([
                                                                                       counter], 1, 'ADD')
                    counter += 1

        # proxy and connection functions

        def get_n_objects_n_proxies():
            size = read_chunk_length()
            file.seek(2, 1)
            n_objects = struct.unpack("i", file.read(4))
            file.seek(2, 1)
            n_proxies = struct.unpack("i", file.read(4))
            n_objects_proxies = {
                "n_objects": n_objects[0], "n_proxies": n_proxies[0]}

            # some .alo formats have an additional unspecified value at this position
            # to read the rest correctly this code checks if this is the case here and skips appropriately
            size -= 12
            file.seek(size, 1)

            return n_objects_proxies

        def read_conncetion(armatureData, meshNameList):
            file.seek(2, 1)  # skip head and size
            mesh_index = struct.unpack("I", file.read(4))[0]
            file.seek(2, 1)  # skip head and size
            bone_index = struct.unpack("I", file.read(4))[0]
            armatureBlender = utils.findArmature()

            # set connection of object to bone and move object to bone
            obj = None
            if mesh_index < len(meshNameList):  # light objects can mess this up
                obj = bpy.data.objects[meshNameList[mesh_index]]
            bone = armatureBlender.data.bones[bone_index]
            if obj != None:
                if bone.name != 'Root':
                    constraint = obj.constraints.new('CHILD_OF')
                    constraint.target = armatureBlender
                    constraint.subtarget = bone.name

        def read_proxy():
            chunk_length = struct.unpack("I", file.read(4))[0]
            file.seek(1, 1)  # skip header
            name_length = struct.unpack("B", file.read(1))[0]
            proxy_name = ""
            counter = 0
            while counter < name_length - 1:
                letter = str(file.read(1))
                letter = letter[2:len(letter) - 1]
                proxy_name = proxy_name + letter
                counter += 1
            file.seek(3, 1)  # skip endbyte of name, chunk mini header and size
            proxy_bone_index = struct.unpack("<I", file.read(4))[0]

            proxyIsHidden = False
            altDecreaseStayHidden = False
            counter = 0
            while (name_length + 9 + counter < chunk_length):
                mini_chunk = file.read(1)
                file.seek(1, 1)
                if mini_chunk == b"\x07":
                    if struct.unpack("<I", file.read(4))[0] == 1:
                        proxyIsHidden = True
                elif mini_chunk == b"\x08":
                    if struct.unpack("<I", file.read(4))[0] == 1:
                        altDecreaseStayHidden = True
                counter += 6

            armatureBlender = utils.findArmature()

            bpy.context.view_layer.objects.active = armatureBlender
            bpy.ops.object.mode_set(mode='EDIT')  # go to Edit mode
            bone = armatureBlender.data.edit_bones[armatureBlender.data.bones[proxy_bone_index].name]
            bone.EnableProxy = True
            bone.ProxyName = proxy_name
            bone.proxyIsHidden = proxyIsHidden
            bone.altDecreaseStayHidden = altDecreaseStayHidden
            bpy.ops.object.mode_set(mode='OBJECT')  # go to Edit mode

        # Utility functions

        def read_chunk_length():
            # the hight bit is used to tell if chunk holds data or chunks, so if it is set it has to be ignored when calculating length
            length = struct.unpack("<I", file.read(4))[0]
            if length >= 2147483648:
                length -= 2147483648
            return length

        def cut_string(string):
            # bones have a 63 character limit, this function cuts longer strings with space for .xyz end used by blender to distinguish double name
            if(len(string) > 63):
                return string[0:59]
            else:
                return string

        def read_string():
            # reads string out of chunk containing only a string
            length = struct.unpack("I", file.read(4))  # get string length
            string = ""
            counter = 0
            while counter < length[0] - 1:
                letter = str(file.read(1))
                letter = letter[2:len(letter) - 1]
                string = string + letter
                counter += 1
            file.seek(1, 1)  # skip end byte of name
            return string

        def read_string_mini_chunk():
            file.seek(1, 1)  # skip chunk header
            size = length = struct.unpack("<b", file.read(1))[0]
            string = ""
            counter = 0
            while counter < length - 1:
                letter = str(file.read(1))
                letter = letter[2:len(letter) - 1]
                string = string + letter
                counter += 1
            file.seek(1, 1)  # skip end byte of name
            return string
        
        def hideObject(object):

            # set correct area type via context overwrite
            area = None
            for window in bpy.context.window_manager.windows:
                screen = window.screen
                for a in screen.areas:
                    if a.type == 'VIEW_3D':
                        area = a
                        break
            with context.temp_override(area=area):
                bpy.ops.object.select_all(action='DESELECT')
                object.select_set(True)
                bpy.ops.object.hide_view_set()
                object.hide_render = True

        def hideLODs():
            # hides all but the most detailed LOD in Blender
            for object in bpy.data.objects:
                if(object.type == 'MESH'):
                    # check if name ends with LOD
                    if object.name[len(object.name)-4:len(object.name)-1] == 'LOD':
                        # check for hightest LOD
                        lodCounter = 0
                        while (object.name[:-1]+str(lodCounter) in bpy.data.objects):
                            lodCounter += 1
                        # hide smaller LODS
                        counter = 0
                        while(counter < lodCounter-1):
                            hideObject(
                                bpy.data.objects[object.name[:-1] + str(counter)])
                            counter += 1

            # hide object if its a shadow or a collision
            for object in bpy.data.objects:
                if object.type == 'MESH':
                    if len(object.material_slots) != 0:
                        shader = object.material_slots[0].material.shaderList.shaderList
                        if(shader == 'MeshCollision.fx' or shader == 'RSkinShadowVolume.fx' or shader == 'MeshShadowVolume.fx'):
                            hideObject(object)

            # hide objects that are set to not visible
            for object in bpy.data.objects:
                if (object.type == 'MESH'):
                    if object.Hidden == True:
                        hideObject(object)

        def deleteRoot():
            armature = utils.findArmature()
            armature.select_set(True)  # select the skeleton
            context.view_layer.objects.active = armature

            if bpy.ops.object.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
            if 'Root' in armature.data.edit_bones:
                armature.data.edit_bones.remove(
                    armature.data.edit_bones['Root'])
            bpy.ops.object.mode_set(mode='OBJECT')

        # material utility functions

        def textureOverride(path, submod, texture_name):
            submodEnd = path.find("\\Data")
            submodStart = -1
            if path.find(submod):
                submodStart = path.find(submod)
            if submodStart == -1:
                submodStart = submodEnd + 1
            newPath = path[:submodStart] + submod + path[submodEnd:]

            if os.path.isfile(newPath):
                return newPath
            else:
                self.report({"WARNING"}, f'ALAMO - {texture_name} not found in {submod}, falling back to default')
                return path

        def load_image(texture_name):
            if texture_name == 'None':
                return
            elif (texture_name in bpy.data.images):
                img = bpy.data.images[texture_name]
            else:
                path = file.name
                path = os.path.split(path)[0]
                path = os.path.split(path)[0]
                for directory in os.listdir(path):
                    if directory.upper() == 'TEXTURES':
                        path = f'{path}/{directory}/{texture_name}'
                        if self.properties.textureOverride != "NONE":
                            path = textureOverride(path, self.properties.textureOverride, texture_name)
                        if os.path.exists(path):
                            img = bpy.data.images.load(path)
                        else:
                            with open(path, "a") as placeholder:
                                placeholder.write('placeholder')
                            img = bpy.data.images.load(path)
                            os.remove(path)
                            self.report({"WARNING"}, "ALAMO - Couldn't find texture: " + texture_name)
                        return
                self.report({"WARNING"}, "ALAMO - Couldn't find: " + path)

        def validate_material_prop(name):
            material_props = ["BaseTexture", "NormalTexture", "GlossTexture", "WaveTexture", "DistortionTexture", "CloudTexture", "CloudNormalTexture", "Emissive", "Diffuse", "Specular", "Shininess", "Colorization" \
                , "DebugColor", "UVOffset", "Color", "UVScrollRate", "DiffuseColor", "EdgeBrightness", "BaseUVScale", "WaveUVScale", "DistortUVScale", "BaseUVScrollRate", "WaveUVScrollRate", "DistortUVScrollRate", "BendScale" \
                , "Diffuse1", "CloudScrollRate", "CloudScale", "SFreq", "TFreq", "DistortionScale", "Atmosphere", "CityColor", "AtmospherePower", "SpecularTexture", "UVOffsetX", "UVOffsetY", "UVScaleFactor", "MaskTexture"]

            if(name in material_props):
                return True
            self.report({"WARNING"}, "ALAMO - Unknown material porperty: " + name)
            return False

        def read_int(material):
            file.seek(4, 1)  # skip size
            name = read_string_mini_chunk()
            file.seek(2, 1)  # skip mini header and size
            value = struct.unpack('<I', file.read(4))[0]

            if validate_material_prop(name):
                exec('material.' + name + '= value')

        def read_float(material):
            file.seek(4, 1)  # skip size
            name = read_string_mini_chunk()
            file.seek(2, 1)  # skip mini header and size
            value = struct.unpack('<f', file.read(4))[0]

            if validate_material_prop(name):
                exec('material.' + name + '= value')

        def read_float3(material):
            file.seek(4, 1)  # skip size
            name = read_string_mini_chunk()
            file.seek(2, 1)  # skip mini header and size
            value1 = struct.unpack('<f', file.read(4))[0]
            value2 = struct.unpack('<f', file.read(4))[0]
            value3 = struct.unpack('<f', file.read(4))[0]

            value = (value1, value2, value3)

            if validate_material_prop(name):
                exec('material.' + name + '= value')

        def read_float4(material):
            file.seek(4, 1)  # skip size
            name = read_string_mini_chunk()
            file.seek(2, 1)  # skip mini header and size
            value1 = struct.unpack('<f', file.read(4))[0]
            value2 = struct.unpack('<f', file.read(4))[0]
            value3 = struct.unpack('<f', file.read(4))[0]
            value4 = struct.unpack('<f', file.read(4))[0]

            value = (value1, value2, value3, value4)

            if validate_material_prop(name):
                exec('material.' + name + '= value')

        def loadAnimations(filePath):
            # remove ending
            path = os.path.dirname(filePath)
            fileName = os.path.basename(filePath)[0:-4]
            bpy.context.scene.modelFileName = fileName

            animationFiles = []

            for file in listdir(path):
                fileExt = file[-4:]
                if(fileExt.lower() == ".ala" and file[0:len(fileName)] == fileName):
                    animationFiles.append(file)

            importer = import_ala.AnimationImporter()
            arm = utils.findArmature()
            arm.animation_data_create()

            for animFile in animationFiles:
                importer.loadAnimation(os.path.join(path, animFile))

        global assignedVertexGroups
        assignedVertexGroups = []
        global MeshNameList
        MeshNameList = []
        global doubleMeshes
        doubleMeshes = []
        global boneNameListALO
        boneNameListALO = []
        global boneConnectedDict
        boneConnectedDict = {}

        global meshList
        meshList = []

        global fileName
        fileName = os.path.basename(self.properties.filepath)[0:-4]

        global importCollection
        importCollection = bpy.data.collections.new(fileName)
        bpy.context.scene.collection.children.link(importCollection)

        # is changed due to implementation details in the enum callback
        activeArmatureBackup = 'None'
        originalArmature = utils.findArmature()
        if(originalArmature != None):
            activeArmatureBackup = originalArmature.name

        global file
        filepath = self.properties.filepath
        file = open(filepath, 'rb') #open file in read binary mode
        process_active_junk()
        removeShadowDoubles()
        hideLODs()
        deleteRoot()
        if(self.importAnimations):
            loadAnimations(filepath)

        # restore previous active armature
        if(activeArmatureBackup != 'None'):
            createdArmature = utils.findArmature()  # get new armature
            bpy.context.scene.ActiveSkeleton.skeletonEnum = activeArmatureBackup  # restore
            armature = utils.findArmature()
            # set parent
            if(self.parentName != 'None' and armature != None):
                parentBone = armature.data.bones[self.parentName]
                if(parentBone != None):
                    createdArmature.parent = armature
                    createdArmature.parent_bone = self.parentName
                    createdArmature.parent_type = 'BONE'
        for object in bpy.data.objects:
            for constraint in object.constraints:
                constraint.inverse_matrix = mathutils.Matrix.Identity(4)
        return {'FINISHED'}            # this lets blender know the operator finished successfully.

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
