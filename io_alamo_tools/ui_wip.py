import bpy

def CheckObjectType(objects, type):
    for object in objects:
        if object.type != type:
            return False
    return True
    
def CheckPropAllSame(objects, prop):
    # True: All same, have value of True
    # False: All same, have value of False
    # None: Not all same
    first_value = None
    for object in objects:
        if first_value is None:
            first_value = getattr(object, prop)
        elif getattr(object, prop) != first_value:
            return None
    return first_value

def ShouldEnable(objects):
    if objects is None or len(objects) <= 0:
        return False
    if bpy.context.mode == "OBJECT":
        objects_same = CheckObjectType(objects, "MESH")
        if not objects_same:
            return False
    return True

def threebox(layout, all_same, operator, label):
    icon="ERROR"
    if all_same is None:
        icon="LAYER_ACTIVE"
    if all_same == True:
        icon="CHECKMARK"
    if all_same == False:
        icon="BLANK1"
        
    row=layout.row()
    row.operator(operator, text="", icon=icon)
    row.label(text=label)
    
def setProp(all_same, objects, prop):
    set_to = False
    if all_same in (None, False) :
        set_to = True
        
    for object in objects:
        setattr(object, prop, set_to)

def propop_builder(prop, object_type):
    
    class PropOp(bpy.types.Operator):
        bl_idname = "alamo.set_" + prop.lower()
        bl_label = "Set " + prop + " for all selected objects"
        bl_description = ""
        
        @classmethod
        def poll(cls, context):
            return ShouldEnable(eval("bpy.context.selected_" + object_type))

        def execute(self, context):
            setProp(CheckPropAllSame(eval("bpy.context.selected_" + object_type), prop), eval("bpy.context.selected_" + object_type), prop)
            return {'FINISHED'}

    return PropOp
        
SetCollision = propop_builder("HasCollision", "objects")
SetHidden = propop_builder("Hidden", "objects")

class ALAMO_PT_ObjectPanel(bpy.types.Panel):
    bl_label = "Object"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "ALAMO"

    def draw(self, context):
        layout = self.layout
        layout.active = False
        if bpy.context.mode == "OBJECT":
            layout.active = True
        
        threebox(layout, CheckPropAllSame(bpy.context.selected_objects, "HasCollision"), "alamo.set_hascollision", "Collision")
        threebox(layout, CheckPropAllSame(bpy.context.selected_objects, "Hidden"), "alamo.set_hidden", "Hidden")


def register():
    bpy.utils.register_class(SetCollision)
    bpy.utils.register_class(SetHidden)
    bpy.utils.register_class(ALAMO_PT_ObjectPanel)


def unregister():
    bpy.utils.unregister_class(SetCollision)
    bpy.utils.unregister_class(SetHidden)
    bpy.utils.unregister_class(ALAMO_PT_ObjectPanel)


if __name__ == "__main__":
    register()
