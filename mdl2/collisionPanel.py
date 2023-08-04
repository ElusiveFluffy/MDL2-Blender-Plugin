import bpy
from bpy.props import EnumProperty, StringProperty
from bpy.types import PropertyGroup

class MDLCollisionPanel(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "MDL Collision Property"
    bl_idname = "DATA_PT_MDLCollisionPanel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and (obj.type == 'MESH')   

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        propertyClass = obj.MDLCollisions
        
        layout.prop(propertyClass, 'CollisionTypes')
        if (obj.MDLCollisions.CollisionTypes == 'Custom'):
            split = layout.split(factor=0.3)
            col = split.column(align=True)
            col.label(text='Custom Collision ID:')
            col = split.column(align=True)
            col.prop(propertyClass, 'CustomCollision', text='', expand=True)


def register():
    bpy.utils.register_class(MDLCollisionPanel)
    bpy.utils.register_class(MDLPropertiesClass)

    bpy.types.Object.MDLCollisions = bpy.props.PointerProperty(type= MDLPropertiesClass)


def unregister():
    bpy.utils.unregister_class(MDLCollisionPanel)
    bpy.utils.unregister_class(MDLPropertiesClass)
    del bpy.types.Object.MDLCollisions
    

class MDLPropertiesClass(PropertyGroup):
    CollisionTypes : EnumProperty(
        name='Collision Type',
        description='Collision type for this mesh (disables any material and rendering in game, names taken from the comments in global.mad)',
        items=[('None', 'None', ''),
               ('T0103_01_R', 'Standard', ''),
               ('T0103_01', 'Wood', ''),
               ('T0103_01_b', 'Rock', ''),
               ('T0103_01_e', 'Sand', ''),
               ('T0103_01_d', 'Sandy Sound in a Tunnel', ''),
               ('T0103_01_o', 'Mud', ''),
               ('T0103_01_j', 'Ice', ''),
               ('T0103_01_T', 'Snow', ''),
               ('T0103_01_Z', 'Snowtop', ''),
               ('T0103_01_ac', 'Metal', ''),
               ('T0103_01_f', 'Water Sound', ''),
               ('T0103_01_i', 'Wall', ''),
               ('T0103_01_v', 'Metal Wall', ''),
               ('T0103_01_p', 'Mud Wall', ''),
               ('T0103_01_Y', 'Soft', ''),
               ('T0103_01_u', 'Lava', ''),
               ('T0103_01_c', 'Wood', 'Seems to be the same as the first Wood value'),
               ('T0103_01_g', 'Green Water?', 'Same as water sound but has two invisible flags'),
               ('T0103_01_ab', 'Slippery Wood', ''),
               ('T0103_01_a', 'Slippery Rock', ''),
               ('T0103_01_K', 'Slippery Sand', ''),
               ('T0103_01_aj', 'Slippery Metal', ''),
               ('T0103_01_ah', 'Slippery Metal, Cam Ignore', ''),
               ('T0103_01_ai', 'Slippery Wood, Cam Ignore', ''),
               ('T0103_01_L', 'Water Slide', ''),
               ('T0103_01_x', 'Ice Slide', ''),
               ('T0103_01_h', 'Rock with Normal Camera?', ''),
               ('T0103_01_q', 'Turn Around?', ''),
               ('T0103_01_m', 'Only Collide With Ty', ''),
               ('T0103_01_S', 'Standard Cam go Through', ''),
               ('T0103_01_n', 'Camera Can go Through', ''),
               ('T0103_01_w', 'Enemy Collision Test', ''),
               ('T0103_01_z', 'Thin Grass Pattern?', ''),
               ('T0103_01_aa', 'Thick Grass Pattern?', ''),
               ('T0103_01_ad', 'Rang Pass', ''),
               ('T0103_01_ae', 'Cam Ignore, Wood', ''),
               ('T0103_01_af', 'Cam Ignore Wall ID for the Blockers', ''),
               ('T0103_01_ag', 'Cam and Boomerang go Through', ''),
               ('T0103_01_ak', 'Cam and Boomerang go Through, Wall ID', ''),
               ('T0103_01_al', 'T0103_01_al', 'Not sure what this one is for'),
               ('crate_01', 'crate_01', 'Not sure what this one is for'),
               ('boomerangnocollide', 'boomerangnocollide', ''),
               ('RangpassNocam', 'RangpassNocam', ''),
               ('Custom', 'Custom', 'Manually enter a custom collision type from global.mad')
               ]
    )
    CustomCollision: StringProperty(
        name='Custom Collision ID',
        description='Manually enter a custom collision type from global.mad'
    )