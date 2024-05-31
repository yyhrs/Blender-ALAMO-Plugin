import bpy
from . import settings


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
        obj = context.object
        layout = self.layout
        col = layout.column()

        if obj is not None and obj.type == "MESH":
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


# Registration ####################################################################################
classes = (
    shaderListProperties,
    ALAMO_PT_materialPropertyPanel,
    ALAMO_PT_materialPropertySubPanel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Material.BaseTexture = bpy.props.StringProperty(default="None")
    bpy.types.Material.DetailTexture = bpy.props.StringProperty(default="None")
    bpy.types.Material.NormalDetailTexture = bpy.props.StringProperty(default="None")
    bpy.types.Material.NormalTexture = bpy.props.StringProperty(default="None")
    bpy.types.Material.GlossTexture = bpy.props.StringProperty(default="None")
    bpy.types.Material.SpecularTexture = bpy.props.StringProperty(default="None")
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
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    bpy.types.Material.BaseTexture
    bpy.types.Material.DetailTexture
    bpy.types.Material.NormalTexture
    bpy.types.Material.NormalDetailTexture
    bpy.types.Material.GlossTexture
    bpy.types.Material.WaveTexture
    bpy.types.Material.DistortionTexture
    bpy.types.Material.SpecularTexture
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
