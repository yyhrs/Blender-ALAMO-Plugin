from .import_alo import ALO_Importer
from .export_ala import ALA_Exporter
from .export_alo import ALO_Exporter
from .import_ala import ALA_Importer
from . import validation
from bpy.types import (
    Panel,
    Operator,
    PropertyGroup,
)
from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    FloatProperty,
    EnumProperty,
    PointerProperty,
)
from bpy.props import *
import mathutils
import bpy
import os

if "bpy" in locals():
    import importlib

    importlib.reload(import_alo)
    importlib.reload(import_ala)
    importlib.reload(export_alo)
    importlib.reload(export_ala)
    importlib.reload(settings)
    importlib.reload(utils)
else:
    from . import import_alo
    from . import import_ala
    from . import export_alo
    from . import export_ala
    from . import settings
    from . import utils

bl_info = {
    "name": "ALAMO Tools",
    "author": "Gaukler, evilbobthebob, inertial",
    "version": (0, 0, 3, 4),
    "blender": (2, 93, 0),
    "category": "Import-Export",
}


classes = ()


# UI Utilities ####################################################################################
def CheckObjectType(objects, type):
    for object in objects:
        if object.type != type:
            return False
    return True


def ShouldEnable(objects):
    if objects is None or len(objects) <= 0:
        return False
    if bpy.context.mode == "OBJECT":
        objects_same = CheckObjectType(objects, "MESH")
        if not objects_same:
            return False
    return True


def CheckPropAllSame(objects, prop):
    # True: All same, have value of True
    # False: All same, have value of False
    # None: Not all same
    if objects is None or len(objects) <= 0:
        return None
    first_value = None
    for object in objects:
        if first_value is None:
            first_value = getattr(object, prop)
        elif getattr(object, prop) != first_value:
            return None
    return first_value


def check_anim_prop_all_same(bones, prop):
    """Like check_prop_all_same(), but for animation"""

    all_same = []

    if bones is not None and len(bones) > 0:
        all_same = list(set(getattr(bone, prop) for bone in bones))

    if len(all_same) == 1:
        return all_same[0]

    return None


def threebox(layout, all_same, operator, label):
    icon = "ERROR"
    if all_same is None:
        icon = "LAYER_ACTIVE"
    if all_same is True:
        icon = "CHECKMARK"
    if all_same is False:
        icon = "BLANK1"

    row = layout.row()
    row.operator(operator, text="", icon=icon)
    row.label(text=label)


def setProp(all_same, objects, prop):
    set_to = False
    if all_same in (None, False):
        set_to = True

    for object in objects:
        setattr(object, prop, set_to)


def proxy_name_update(self, context):
    if self.ProxyName != self.ProxyName.upper():  # prevents endless recursion
        self.ProxyName = self.ProxyName.upper()


def skeletonEnumCallback(scene, context):
    armatures = [("None", "None", "", "", 0)]
    counter = 1
    for arm in bpy.data.objects:  # test if armature exists
        if arm.type == "ARMATURE":
            armatures.append((arm.name, arm.name, "", "", counter))
            counter += 1

    return armatures


# Operators #######################################################################################
def propop_builder(prop, object_type):
    """Property Operator Builder"""

    class PropOp(bpy.types.Operator):
        bl_idname = "alamo.set_" + prop.lower()
        bl_label = "Set " + prop + " for all selected objects"
        bl_description = ""

        @classmethod
        def poll(cls, context):
            return ShouldEnable(eval("bpy.context.selected_" + object_type))

        def execute(self, context):
            setProp(
                CheckPropAllSame(eval("bpy.context.selected_" + object_type), prop),
                eval("bpy.context.selected_" + object_type),
                prop,
            )
            return {"FINISHED"}

    return PropOp


SetCollision = propop_builder("HasCollision", "objects")
SetHidden = propop_builder("Hidden", "objects")
SetBoneHidden = propop_builder("Visible", "bones")
SetAltDecreaseStayHidden = propop_builder("altDecreaseStayHidden", "bones")
SetProxy = propop_builder("EnableProxy", "bones")
SetProxyHidden = propop_builder("proxyIsHidden", "bones")

classes = (
    *classes,
    SetCollision,
    SetHidden,
    SetBoneHidden,
    SetAltDecreaseStayHidden,
    SetProxy,
    SetProxyHidden,
)


class keyframeProxySet(bpy.types.Operator):
    bl_idname = "alamo.set_keyframe_proxy"
    bl_label = ""
    bl_description = (
        "Create a keyframe and set proxyIsHiddenAnimation for all selected bones"
    )

    @classmethod
    def poll(cls, context):
        bones = bpy.context.selected_pose_bones
        return bones is not None and len(bones) > 0

    def execute(self, context):
        bones = bpy.context.selected_pose_bones

        all_same = check_anim_prop_all_same(bones, "proxyIsHiddenAnimation")
        operation = "SHOW" if all_same is True else "HIDE"

        for bone in list(bones):
            if operation == "SHOW":
                bone.proxyIsHiddenAnimation = False
            if operation == "HIDE":
                bone.proxyIsHiddenAnimation = True

            bone.keyframe_insert(data_path="proxyIsHiddenAnimation", group=bone.name)

        for area in bpy.context.screen.areas:
            if area.type == "DOPESHEET_EDITOR":
                area.tag_redraw()

        return {"FINISHED"}


class keyframeProxyDelete(bpy.types.Operator):
    bl_idname = "alamo.delete_keyframe_proxy"
    bl_label = ""
    bl_description = (
        "Create a keyframe and set proxyIsHiddenAnimation for all selected bones"
    )

    @classmethod
    def poll(cls, context):
        bones = bpy.context.selected_pose_bones
        action = bpy.context.object.animation_data.action
        frame = bpy.context.scene.frame_current

        if bones is None or len(bones) <= 0:
            return False

        for bone in list(bones):
            keyframes = action.fcurves.find(
                bone.path_from_id() + ".proxyIsHiddenAnimation"
            )
            if keyframes is not None:
                for keyframe in keyframes.keyframe_points:
                    if int(keyframe.co[0]) == frame:
                        return True

        return False

    def execute(self, context):
        bones = list(bpy.context.selected_pose_bones)
        for bone in bones:
            bone.keyframe_delete(data_path="proxyIsHiddenAnimation")

        for area in bpy.context.screen.areas:
            if area.type in ("DOPESHEET_EDITOR", "VIEW_3D"):
                area.tag_redraw()

        return {"FINISHED"}


class ValidateFileButton(bpy.types.Operator):
    bl_idname = "alamo.validate_file"
    bl_label = "Validate"

    def execute(self, context):
        mesh_list = validation.create_export_list(
            bpy.context.scene.collection, True, "DATA"
        )

        # check if export objects satisfy requirements (has material, UVs, ...)
        messages = validation.validate(mesh_list)

        if messages is not None and len(messages) > 0:
            for message in messages:
                self.report(*message)
        else:
            self.report({"INFO"}, "ALAMO - Validation complete. No errors detected!")
        return {"FINISHED"}


# Legacy version, included for the debug panel
class createConstraintBoneButton(bpy.types.Operator):
    bl_idname = "create.constraint_bone"
    bl_label = "Create constraint bone"

    def execute(self, context):
        object = bpy.context.view_layer.objects.active
        armature = utils.findArmature()

        bpy.context.view_layer.objects.active = armature
        utils.setModeToEdit()

        bone = armature.data.edit_bones.new(object.name)
        bone.tail = bone.head + mathutils.Vector((0.0, 0.0, 1.0))
        bone.matrix = object.matrix_world
        object.location = mathutils.Vector((0.0, 0.0, 0.0))
        object.rotation_euler = mathutils.Euler((0.0, 0.0, 0.0), "XYZ")
        constraint = object.constraints.new("CHILD_OF")
        constraint.target = armature
        constraint.subtarget = bone.name

        utils.setModeToObject()
        bpy.context.view_layer.objects.active = object
        return {"FINISHED"}


class CreateConstraintBone(bpy.types.Operator):
    bl_idname = "alamo.create_constraint_bone"
    bl_label = "Create Constraint Bone"

    @classmethod
    def poll(cls, context):
        object = bpy.context.object
        if (
            type(object) != type(None)
            and object.type == "MESH"
            and bpy.context.mode == "OBJECT"
        ):
            armature = utils.findArmature()
            if armature is not None:
                hasChildConstraint = False
                for constraint in object.constraints:
                    if constraint.type == "CHILD_OF":
                        hasChildConstraint = True
                if not hasChildConstraint:
                    return True
        return False

    def execute(self, context):
        object = bpy.context.view_layer.objects.active
        armature = utils.findArmature()

        bpy.context.view_layer.objects.active = armature
        utils.setModeToEdit()

        bone = armature.data.edit_bones.new(object.name)
        bone.tail = bone.head + mathutils.Vector((0.0, 0.0, 1.0))
        bone.matrix = object.matrix_world
        object.location = mathutils.Vector((0.0, 0.0, 0.0))
        object.rotation_euler = mathutils.Euler((0.0, 0.0, 0.0), "XYZ")
        constraint = object.constraints.new("CHILD_OF")
        constraint.target = armature
        constraint.subtarget = bone.name

        utils.setModeToObject()
        bpy.context.view_layer.objects.active = object
        return {"FINISHED"}


class CopyProxyNameToSelected(bpy.types.Operator):
    bl_idname = "alamo.copy_proxy_name"
    bl_label = ""
    bl_description = "Copy Proxy Name to Selected Bones"

    @classmethod
    def poll(cls, context):
        return (
            bpy.context.selected_bones is not None
            and len(bpy.context.selected_bones) > 1
        )

    def execute(self, context):
        bones = list(bpy.context.selected_bones)
        name = bones[0].ProxyName
        for bone in bones:
            bone.ProxyName = name
        return {"FINISHED"}


class skeletonEnumClass(PropertyGroup):
    skeletonEnum: EnumProperty(
        name="Active Skeleton",
        description="skeleton that is exported",
        items=skeletonEnumCallback,
    )


# Panels ##########################################################################################
class ALAMO_PT_ValidationPanel(bpy.types.Panel):

    bl_label = "Validation"
    bl_idname = "ALAMO_PT_ValidationPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ALAMO"

    def draw(self, context):
        row = self.layout.row()
        row.operator("alamo.validate_file")
        row.scale_y = 3.0


class ALAMO_PT_ObjectPanel(bpy.types.Panel):
    bl_label = "Object"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ALAMO"

    def draw(self, context):
        layout = self.layout
        layout.active = False
        if bpy.context.mode == "OBJECT":
            layout.active = True

        threebox(
            layout,
            CheckPropAllSame(bpy.context.selected_objects, "HasCollision"),
            "alamo.set_hascollision",
            "Collision",
        )
        threebox(
            layout,
            CheckPropAllSame(bpy.context.selected_objects, "Hidden"),
            "alamo.set_hidden",
            "Hidden",
        )


class ALAMO_PT_ArmatureSettingsPanel(bpy.types.Panel):

    bl_label = "Armature"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ALAMO"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        col = layout.column(align=True)
        col.label(text="Active Skeleton")
        col.prop(scene.ActiveSkeleton, "skeletonEnum", text="")

        layout.separator()

        layout.operator("alamo.create_constraint_bone")


class ALAMO_PT_EditBonePanel(bpy.types.Panel):

    bl_label = "Bone"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ALAMO"

    def draw(self, context):
        bones = bpy.context.selected_bones
        layout = self.layout

        layout.active = False
        if bpy.context.mode == "EDIT_ARMATURE":
            layout.active = True

        col = layout.column(align=True)
        col.label(text="Billboard Mode")
        row = col.row()
        row.enabled = False
        if bones is not None:
            if len(bones) == 1:
                row.prop(list(bones)[0].billboardMode, "billboardMode", text="")
                row.enabled = True
            else:
                row.label(text="Billboard")
        else:
            row.label(text="Billboard")

        layout.separator()

        threebox(
            layout,
            CheckPropAllSame(bpy.context.selected_bones, "Visible"),
            "alamo.set_visible",
            "Visible",
        )
        threebox(
            layout,
            CheckPropAllSame(bpy.context.selected_bones, "EnableProxy"),
            "alamo.set_enableproxy",
            "Enable Proxy",
        )


class ALAMO_PT_EditBoneSubPanel(bpy.types.Panel):

    bl_label = ""
    bl_parent_id = "ALAMO_PT_EditBonePanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ALAMO"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        bones = bpy.context.selected_bones
        layout = self.layout

        all_same = CheckPropAllSame(bones, "EnableProxy")

        layout.active = False
        if bpy.context.mode == "EDIT_ARMATURE" and all_same is not None:
            layout.active = all_same

        if bpy.context.mode == "EDIT_ARMATURE" and all_same is None and len(bones) > 0:
            layout.label(icon="ERROR", text="Inconsistent EnableProxy states")

        threebox(
            layout,
            all_same,
            "alamo.set_proxyishidden",
            "Proxy Visible",
        )
        threebox(
            layout,
            all_same,
            "alamo.set_altdecreasestayhidden",
            "altDecreaseStayHidden",
        )

        col = layout.column(align=True)
        col.label(text="Proxy Name")
        row = col.row(align=True)
        row.enabled = False
        if bpy.context.mode == "EDIT_ARMATURE" and bones is not None and len(bones) > 0 and all_same:
            row.prop(list(bones)[0], "ProxyName", text="")
            row.operator("alamo.copy_proxy_name", text="", icon="DUPLICATE")
            row.enabled = True
        else:
            row.label(text="ProxyName")


class ALAMO_PT_AnimationPanel(bpy.types.Panel):

    bl_label = "Animation"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ALAMO"

    def draw(self, context):
        layout = self.layout
        layout.active = False
        if bpy.context.mode == "POSE":
            layout.active = True

        threebox(
            layout,
            check_anim_prop_all_same(
                bpy.context.selected_pose_bones, "proxyIsHiddenAnimation"
            ),
            "alamo.set_keyframe_proxy",
            "Keyframe Proxy Visible",
        )

        row = layout.row()
        row.operator("alamo.delete_keyframe_proxy", text="", icon="X")
        row.label(text="Delete Proxy Keyframes")


class ALAMO_PT_AnimationActionSubPanel(bpy.types.Panel):

    bl_label = "Action End Frames"
    bl_parent_id = "ALAMO_PT_AnimationPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ALAMO"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        layout = self.layout.column(align=True)
        layout.label(text="Action End Frames")
        for action in bpy.data.actions:
            layout.prop(action, "AnimationEndFrame", text=action.name)


class ALAMO_PT_DebugPanel(bpy.types.Panel):

    bl_label = "Debug"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ALAMO"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        object = context.object
        layout = self.layout
        scene = context.scene
        c = layout.column()

        c.prop(scene.ActiveSkeleton, "skeletonEnum")

        if type(object) != type(None):
            if object.type == "MESH":
                if bpy.context.mode == "OBJECT":
                    c.prop(object, "HasCollision")
                    c.prop(object, "Hidden")

                    armature = utils.findArmature()
                    if armature != None:
                        hasChildConstraint = False
                        for constraint in object.constraints:
                            if constraint.type == "CHILD_OF":
                                hasChildConstraint = True
                        if not hasChildConstraint:
                            self.layout.operator(
                                "create.constraint_bone", text="Create Constraint Bone"
                            )

            action = utils.getCurrentAction()
            if action != None:
                c.prop(action, "AnimationEndFrame")

        bone = bpy.context.active_bone
        if type(bone) != type(None):
            if type(bpy.context.active_bone) is bpy.types.EditBone:
                c.prop(bone.billboardMode, "billboardMode")
                c.prop(bone, "Visible")
                c.prop(bone, "EnableProxy")
                if bone.EnableProxy:
                    c.prop(bone, "proxyIsHidden")
                    c.prop(bone, "altDecreaseStayHidden")
                    c.prop(bone, "ProxyName")

            elif (
                type(bpy.context.active_bone) is bpy.types.Bone
                and bpy.context.mode == "POSE"
            ):
                poseBone = object.pose.bones[bone.name]
                c.prop(poseBone, "proxyIsHiddenAnimation")


class ALAMO_PT_materialPropertyPanel(bpy.types.Panel):
    bl_label = "Alamo Shader Properties"
    bl_id = "ALAMO_PT_materialPropertyPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"

    def draw(self, context):
        object = context.object
        layout = self.layout
        col = layout.column()

        # if type(object) != type(None) and object.type == "MESH":
        if type(object) != type(None) and object.type == "MESH":
            material = bpy.context.active_object.active_material
            if material is not None:
                # a None image is needed to represent not using a texture
                if "None" not in bpy.data.images:
                    bpy.data.images.new(name="None", width=1, height=1)
                col.prop(material.shaderList, "shaderList")
                if material.shaderList.shaderList != "alDefault.fx":
                    shader_props = settings.material_parameter_dict[
                        material.shaderList.shaderList
                    ]
                    for shader_prop in shader_props:
                        # because contains() doesn't exist, apparently
                        if shader_prop.find("Texture") > -1:
                            layout.prop_search(
                                material, shader_prop, bpy.data, "images"
                            )
                            # layout.template_ID(material, shader_prop, new="image.new", open="image.open")


class ALAMO_PT_materialPropertySubPanel(bpy.types.Panel):
    bl_label = "Additional Properties"
    bl_parent_id = "ALAMO_PT_materialPropertyPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        object = context.object
        layout = self.layout
        col = layout.column()

        if type(object) != type(None) and object.type == "MESH":
            material = bpy.context.active_object.active_material
            if (
                material is not None
                and material.shaderList.shaderList != "alDefault.fx"
            ):
                shader_props = settings.material_parameter_dict[
                    material.shaderList.shaderList
                ]
                for shader_prop in shader_props:
                    # because contains() doesn't exist, apparently
                    if shader_prop.find("Texture") == -1:
                        col.prop(material, shader_prop)


class shaderListProperties(bpy.types.PropertyGroup):
    mode_options = [
        (shader_name, shader_name, "", "", index)
        for index, shader_name in enumerate(settings.material_parameter_dict)
    ]

    shaderList: bpy.props.EnumProperty(
        items=mode_options,
        description="Choose ingame Shader",
        default="alDefault.fx",
    )


class billboardListProperties(bpy.types.PropertyGroup):
    mode_options = [
        ("Disable", "Disable", "Description WIP", "", 0),
        ("Parallel", "Parallel", "Description WIP", "", 1),
        ("Face", "Face", "Description WIP", "", 2),
        ("ZAxis View", "ZAxis View", "Description WIP", "", 3),
        ("ZAxis Light", "ZAxis Light", "Description WIP", "", 4),
        ("ZAxis Wind", "ZAxis Wind", "Description WIP", "", 5),
        ("Sunlight Glow", "Sunlight Glow", "Description WIP", "", 6),
        ("Sun", "Sun", "Description WIP", "", 7),
    ]

    billboardMode: bpy.props.EnumProperty(
        items=mode_options,
        description="billboardMode",
        default="Disable",
    )


# Registration ####################################################################################
def menu_func_import(self, context):
    self.layout.operator(import_alo.ALO_Importer.bl_idname, text=".ALO Importer")
    self.layout.operator(import_ala.ALA_Importer.bl_idname, text=".ALA Importer")


def menu_func_export(self, context):
    self.layout.operator(export_alo.ALO_Exporter.bl_idname, text=".ALO Exporter")
    self.layout.operator(export_ala.ALA_Exporter.bl_idname, text=".ALA Exporter")


classes = (
    *classes,
    skeletonEnumClass,
    billboardListProperties,
    shaderListProperties,
    ALO_Importer,
    ALA_Importer,
    ALO_Exporter,
    ALA_Exporter,
    ALAMO_PT_materialPropertyPanel,
    ALAMO_PT_materialPropertySubPanel,
    ValidateFileButton,
    CreateConstraintBone,
    createConstraintBoneButton,
    CopyProxyNameToSelected,
    keyframeProxySet,
    keyframeProxyDelete,
    ALAMO_PT_ValidationPanel,
    ALAMO_PT_ObjectPanel,
    ALAMO_PT_ArmatureSettingsPanel,
    ALAMO_PT_EditBonePanel,
    ALAMO_PT_EditBoneSubPanel,
    ALAMO_PT_AnimationPanel,
    ALAMO_PT_AnimationActionSubPanel,
    ALAMO_PT_DebugPanel,
)


def register():
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

    bpy.types.Scene.ActiveSkeleton = PointerProperty(type=skeletonEnumClass)
    bpy.types.Scene.modelFileName = StringProperty(name="")

    bpy.types.Action.AnimationEndFrame = IntProperty(default=24)

    bpy.types.EditBone.Visible = BoolProperty(default=True)
    bpy.types.EditBone.EnableProxy = BoolProperty()
    bpy.types.EditBone.proxyIsHidden = BoolProperty()
    bpy.types.PoseBone.proxyIsHiddenAnimation = BoolProperty()
    bpy.types.EditBone.altDecreaseStayHidden = BoolProperty()
    bpy.types.EditBone.ProxyName = StringProperty(update=proxy_name_update)
    bpy.types.EditBone.billboardMode = bpy.props.PointerProperty(
        type=billboardListProperties
    )

    bpy.types.Object.HasCollision = BoolProperty()
    bpy.types.Object.Hidden = BoolProperty()

    bpy.types.Material.BaseTexture = bpy.props.StringProperty(default="None")
    bpy.types.Material.DetailTexture = bpy.props.StringProperty(default="None")
    bpy.types.Material.NormalDetailTexture = bpy.props.StringProperty(default="None")
    bpy.types.Material.NormalTexture = bpy.props.StringProperty(default="None")
    bpy.types.Material.GlossTexture = bpy.props.StringProperty(default="None")
    bpy.types.Material.WaveTexture = bpy.props.StringProperty(default="None")
    bpy.types.Material.DistortionTexture = bpy.props.StringProperty(default="None")
    bpy.types.Material.CloudTexture = bpy.props.StringProperty(default="None")
    bpy.types.Material.CloudNormalTexture = bpy.props.StringProperty(default="None")

    bpy.types.Material.shaderList = bpy.props.PointerProperty(type=shaderListProperties)
    bpy.types.Material.Emissive = bpy.props.FloatVectorProperty(
        min=0.0, max=1.0, size=4, default=(0.0, 0.0, 0.0, 0.0)
    )
    bpy.types.Material.Diffuse = bpy.props.FloatVectorProperty(
        min=0.0, max=1.0, size=4, default=(1.0, 1.0, 1.0, 0.0)
    )
    bpy.types.Material.Specular = bpy.props.FloatVectorProperty(
        min=0.0, max=1.0, size=4, default=(1.0, 1.0, 1.0, 0.0)
    )
    bpy.types.Material.Shininess = bpy.props.FloatProperty(
        min=0.0, max=255.0, default=32.0
    )
    bpy.types.Material.Colorization = bpy.props.FloatVectorProperty(
        min=0.0, max=1.0, size=4, default=(1.0, 1.0, 1.0, 0.0)
    )
    bpy.types.Material.DebugColor = bpy.props.FloatVectorProperty(
        min=0.0, max=1.0, size=4, default=(0.0, 1.0, 0.0, 0.0)
    )
    bpy.types.Material.UVOffset = bpy.props.FloatVectorProperty(
        min=0.0, max=1.0, size=4, default=(0.0, 0.0, 0.0, 0.0)
    )
    bpy.types.Material.Color = bpy.props.FloatVectorProperty(
        min=0.0, max=1.0, size=4, default=(1.0, 1.0, 1.0, 1.0)
    )
    bpy.types.Material.UVScrollRate = bpy.props.FloatVectorProperty(
        min=0.0, max=1.0, size=4, default=(0.0, 0.0, 0.0, 0.0)
    )
    bpy.types.Material.DiffuseColor = bpy.props.FloatVectorProperty(
        min=0.0, max=1.0, size=3, default=(0.5, 0.5, 0.5)
    )
    # shield shader properties
    bpy.types.Material.EdgeBrightness = bpy.props.FloatProperty(
        min=0.0, max=255.0, default=0.5
    )
    bpy.types.Material.BaseUVScale = bpy.props.FloatProperty(
        min=-255.0, max=255.0, default=1.0
    )
    bpy.types.Material.WaveUVScale = bpy.props.FloatProperty(
        min=-255.0, max=255.0, default=1.0
    )
    bpy.types.Material.DistortUVScale = bpy.props.FloatProperty(
        min=-255.0, max=255.0, default=1.0
    )
    bpy.types.Material.BaseUVScrollRate = bpy.props.FloatProperty(
        min=-255.0, max=255.0, default=-0.15
    )
    bpy.types.Material.WaveUVScrollRate = bpy.props.FloatProperty(
        min=-255.0, max=255.0, default=-0.15
    )
    bpy.types.Material.DistortUVScrollRate = bpy.props.FloatProperty(
        min=-255.0, max=255.0, default=-0.25
    )
    # tree properties
    bpy.types.Material.BendScale = bpy.props.FloatProperty(
        min=-255.0, max=255.0, default=0.4
    )
    # grass properties
    bpy.types.Material.Diffuse1 = bpy.props.FloatVectorProperty(
        min=0.0, max=1.0, size=4, default=(1.0, 1.0, 1.0, 1.0)
    )
    # skydome.fx properties
    bpy.types.Material.CloudScrollRate = bpy.props.FloatProperty(
        min=-255.0, max=255.0, default=0.001
    )
    bpy.types.Material.CloudScale = bpy.props.FloatProperty(
        min=-255.0, max=255.0, default=1.0
    )
    # nebula.fx properties
    bpy.types.Material.SFreq = bpy.props.FloatProperty(
        min=-255.0, max=255.0, default=0.002
    )
    bpy.types.Material.TFreq = bpy.props.FloatProperty(
        min=-255.0, max=255.0, default=0.005
    )
    bpy.types.Material.DistortionScale = bpy.props.FloatProperty(
        min=-255.0, max=255.0, default=1.0
    )
    # planet.fx properties
    bpy.types.Material.Atmosphere = bpy.props.FloatVectorProperty(
        min=0.0, max=1.0, size=4, default=(0.5, 0.5, 0.5, 0.5)
    )
    bpy.types.Material.CityColor = bpy.props.FloatVectorProperty(
        min=0.0, max=1.0, size=4, default=(0.5, 0.5, 0.5, 0.5)
    )
    bpy.types.Material.AtmospherePower = bpy.props.FloatProperty(
        min=-255.0, max=255.0, default=1.0
    )
    # tryplanar mapping properties
    bpy.types.Material.MappingScale = bpy.props.FloatProperty(
        min=0.0, max=255.0, default=0.1
    )
    bpy.types.Material.BlendSharpness = bpy.props.FloatProperty(
        min=0.0, max=255.0, default=0.1
    )


def unregister():
    from bpy.utils import unregister_class

    for cls in reversed(classes):
        unregister_class(cls)

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    bpy.types.Scene.ActiveSkeleton

    bpy.types.Action.AnimationEndFrame

    bpy.types.EditBone.Visible
    bpy.types.EditBone.EnableProxy
    bpy.types.EditBone.proxyIsHidden
    bpy.types.PoseBone.proxyIsHiddenAnimation
    bpy.types.EditBone.altDecreaseStayHidden
    bpy.types.EditBone.ProxyName
    bpy.types.EditBone.billboardMode

    bpy.types.Object.HasCollision
    bpy.types.Object.Hidden

    bpy.types.Material.BaseTexture
    bpy.types.Material.DetailTexture
    bpy.types.Material.NormalTexture
    bpy.types.Material.NormalDetailTexture
    bpy.types.Material.GlossTexture
    bpy.types.Material.WaveTexture
    bpy.types.Material.DistortionTexture
    bpy.types.Material.CloudTexture
    bpy.types.Material.CloudNormalTexture

    bpy.types.Material.shaderList
    bpy.types.Material.Emissive
    bpy.types.Material.Diffuse
    bpy.types.Material.Specular
    bpy.types.Material.Shininess
    bpy.types.Material.Colorization
    bpy.types.Material.DebugColor
    bpy.types.Material.UVOffset
    bpy.types.Material.Color
    bpy.types.Material.UVScrollRate
    bpy.types.Material.DiffuseColor
    # shield shader properties
    bpy.types.Material.EdgeBrightness
    bpy.types.Material.BaseUVScale
    bpy.types.Material.WaveUVScale
    bpy.types.Material.DistortUVScale
    bpy.types.Material.BaseUVScrollRate
    bpy.types.Material.WaveUVScrollRate
    bpy.types.Material.DistortUVScrollRate
    # tree properties
    bpy.types.Material.BendScale
    # grass properties
    bpy.types.Material.Diffuse1
    # skydome.fx properties
    bpy.types.Material.CloudScrollRate
    bpy.types.Material.CloudScale
    # nebula.fx properties
    bpy.types.Material.SFreq
    bpy.types.Material.TFreq
    bpy.types.Material.DistortionScale
    # planet.fx properties
    bpy.types.Material.Atmosphere
    bpy.types.Material.CityColor
    bpy.types.Material.AtmospherePower
    # tryplanar mapping properties
    bpy.types.Material.MappingScale
    bpy.types.Material.BlendSharpness


if __name__ == "__main__":
    register()
