from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    EnumProperty,
    PointerProperty,
)
from . import validation
from . import utils
import mathutils
import bpy


# UI Utilities ####################################################################################
def CheckObjectType(objects, target_type):
    for obj in objects:
        if obj.type != target_type:
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
    for obj in objects:
        if first_value is None:
            first_value = getattr(obj, prop)
        elif getattr(obj, prop) != first_value:
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
        icon = "BLANK1"
    if all_same is False:
        icon = "CHECKMARK"

    row = layout.row()
    row.operator(operator, text="", icon=icon)
    row.label(text=label)

def setProp(all_same, objects, prop):
    set_to = False
    if all_same in (None, False):
        set_to = True

    for obj in objects:
        setattr(obj, prop, set_to)


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
class keyframeProxySet(bpy.types.Operator):
    bl_idname = "alamo.set_keyframe_proxy"
    bl_label = ""
    bl_description = "Create a keyframe and set proxyIsHiddenAnimation for all selected bones"

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
    bl_description = "Delete proxyIsHiddenAnimation keyframes for all selected bones"

    @classmethod
    def poll(cls, context):
        bones = bpy.context.selected_pose_bones
        action = utils.getCurrentAction()
        frame = bpy.context.scene.frame_current

        if bones is None or len(bones) <= 0 or action is None:
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
        obj = bpy.context.view_layer.objects.active
        armature = utils.findArmature()

        bpy.context.view_layer.objects.active = armature
        utils.setModeToEdit()

        bone = armature.data.edit_bones.new(obj.name)
        bone.tail = bone.head + mathutils.Vector((0.0, 0.0, 1.0))
        bone.matrix = obj.matrix_world
        obj.location = mathutils.Vector((0.0, 0.0, 0.0))
        obj.rotation_euler = mathutils.Euler((0.0, 0.0, 0.0), "XYZ")
        constraint = obj.constraints.new("CHILD_OF")
        constraint.target = armature
        constraint.subtarget = bone.name

        utils.setModeToObject()
        bpy.context.view_layer.objects.active = obj
        return {"FINISHED"}


class CreateConstraintBone(bpy.types.Operator):
    bl_idname = "alamo.create_constraint_bone"
    bl_label = "Create Constraint Bone"
    bl_description = "Adds a bone and parents the active object to it"

    @classmethod
    def poll(cls, context):
        obj = bpy.context.object
        if (
            obj is not None
            and obj.type == "MESH"
            and bpy.context.mode == "OBJECT"
        ):
            armature = utils.findArmature()
            if armature is not None:
                has_child_constraint = False
                for constraint in obj.constraints:
                    if constraint.type == "CHILD_OF":
                        has_child_constraint = True
                if not has_child_constraint:
                    return True
        return False

    def execute(self, context):
        obj = bpy.context.view_layer.objects.active
        armature = utils.findArmature()

        bpy.context.view_layer.objects.active = armature
        utils.setModeToEdit()

        bone = armature.data.edit_bones.new(obj.name)
        bone.tail = bone.head + mathutils.Vector((0.0, 0.0, 1.0))
        bone.matrix = obj.matrix_world
        obj.location = mathutils.Vector((0.0, 0.0, 0.0))
        obj.rotation_euler = mathutils.Euler((0.0, 0.0, 0.0), "XYZ")
        constraint = obj.constraints.new("CHILD_OF")
        constraint.target = armature
        constraint.subtarget = bone.name

        utils.setModeToObject()
        bpy.context.view_layer.objects.active = obj
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


class skeletonEnumClass(bpy.types.PropertyGroup):
    skeletonEnum: EnumProperty(
        name="Active Skeleton",
        description="skeleton that is exported",
        items=skeletonEnumCallback,
    )


# Panels ##########################################################################################
class ALAMO_PT_SettingsPanel(bpy.types.Panel):

    bl_label = "Settings"
    bl_idname = "ALAMO_PT_SettingsPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ALAMO"

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.operator("alamo.validate_file")
        row.scale_y = 3.0

        layout.separator()

        col = layout.column(align=True)
        col.label(text="Active Skeleton")
        row = col.row()
        row.scale_y = 1.25
        row.prop(context.scene.ActiveSkeleton, "skeletonEnum", text="")


class ALAMO_PT_InfoPanel(bpy.types.Panel):

    bl_label = "Info"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ALAMO"

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text="Hold ALT when clicking a checkbox")
        col.label(text="to apply it to all selected objects/bones.")

        col = self.layout.column(align=True)
        col.label(text="Buttons in Animation are NOT checkboxes.")


class ALAMO_PT_ObjectPanel(bpy.types.Panel):

    bl_label = "Object"
    bl_context = "objectmode"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ALAMO"

    def draw(self, context):
        layout = self.layout

        obj = context.object
        if obj is not None and obj.type == 'MESH':
            col = layout.column()
            col.prop(obj, "HasCollision", text="Collision")
            col.prop(obj, "Hidden")
            col.scale_y = 1.25

        layout.separator()

        col = layout.column()
        col.scale_y = 1.25
        col.operator("alamo.create_constraint_bone")


class ALAMO_PT_EditBonePanel(bpy.types.Panel):

    bl_label = "Bone"
    bl_context = "armature_edit"
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
        row.scale_y = 1.25
        row.enabled = False
        if bones is not None:
            if len(bones) == 1:
                row.prop(list(bones)[0].billboardMode, "billboardMode", text="")
                row.enabled = True
            else:
                row.label(text="Select a single bone")
        else:
            row.label(text="-")

        layout.separator()

        col = layout.column()
        col.scale_y = 1.25
        col.active = False
        if bpy.context.active_bone is not None:
            col.active = True
            col.prop(bpy.context.active_bone, "Visible")
            col.prop(bpy.context.active_bone, "EnableProxy", text="Enable Proxy")


class ALAMO_PT_EditBoneSubPanel(bpy.types.Panel):

    bl_label = ""
    bl_parent_id = "ALAMO_PT_EditBonePanel"
    bl_context = "armature_edit"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ALAMO"
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        bone = bpy.context.active_bone
        bones = bpy.context.selected_bones
        layout = self.layout

        all_same = CheckPropAllSame(bones, "EnableProxy")

        layout.active = False
        if all_same is not None:
            layout.active = all_same

        if all_same is None and len(bones) > 0:
            layout.label(icon="ERROR", text="Inconsistent EnableProxy states")

        col = layout.column()
        col.scale_y = 1.25
        col.active = False
        if bone is not None and bone.EnableProxy:
            col.active = True
            col.prop(bone, "proxyIsHidden", text="Proxy Visible", invert_checkbox=True)
            col.prop(bone, "altDecreaseStayHidden")

        col = layout.column(align=True)
        col.label(text="Proxy Name")
        row = col.row(align=True)
        row.scale_y = 1.25
        row.enabled = False
        if bones is not None and len(bones) > 0 and all_same:
            row.prop(list(bones)[0], "ProxyName", text="")
            row.operator("alamo.copy_proxy_name", text="", icon="DUPLICATE")
            row.enabled = True
        else:
            row.label(text="ProxyName")


class ALAMO_PT_AnimationPanel(bpy.types.Panel):

    bl_label = "Animation"
    bl_context = "posemode"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ALAMO"

    def draw(self, context):
        layout = self.layout

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
        row.label(text="Delete Keyframes")

        # col = layout.column()
        # col.scale_y = 1.25
        # col.prop(bpy.context.active_pose_bone, "proxyIsHiddenAnimation", text="Proxy Visible", invert_checkbox=True)


class ALAMO_PT_AnimationActionSubPanel(bpy.types.Panel):

    bl_label = "Action End Frames"
    bl_parent_id = "ALAMO_PT_AnimationPanel"
    bl_context = "posemode"
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
                        has_child_constraint = False
                        for constraint in object.constraints:
                            if constraint.type == "CHILD_OF":
                                has_child_constraint = True
                        if not has_child_constraint:
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
classes = (
    skeletonEnumClass,
    billboardListProperties,
    ValidateFileButton,
    CreateConstraintBone,
    createConstraintBoneButton,
    CopyProxyNameToSelected,
    keyframeProxySet,
    keyframeProxyDelete,
    ALAMO_PT_SettingsPanel,
    ALAMO_PT_InfoPanel,
    ALAMO_PT_ObjectPanel,
    ALAMO_PT_EditBonePanel,
    ALAMO_PT_EditBoneSubPanel,
    ALAMO_PT_AnimationPanel,
    ALAMO_PT_AnimationActionSubPanel,
    ALAMO_PT_DebugPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.ActiveSkeleton = PointerProperty(type=skeletonEnumClass)
    bpy.types.Scene.modelFileName = StringProperty(name="")

    bpy.types.Action.AnimationEndFrame = IntProperty(default=24)

    bpy.types.EditBone.Visible = BoolProperty(default=True)
    bpy.types.EditBone.EnableProxy = BoolProperty()
    bpy.types.EditBone.proxyIsHidden = BoolProperty()
    bpy.types.PoseBone.proxyIsHiddenAnimation = BoolProperty()
    bpy.types.EditBone.altDecreaseStayHidden = BoolProperty()
    bpy.types.EditBone.ProxyName = StringProperty(update=proxy_name_update)
    bpy.types.EditBone.billboardMode = bpy.props.PointerProperty(type=billboardListProperties)

    bpy.types.Object.HasCollision = BoolProperty()
    bpy.types.Object.Hidden = BoolProperty()


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

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


if __name__ == "__main__":
    register()
