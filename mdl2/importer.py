import struct
import time
import bpy
import bmesh
import json

from io import BufferedReader
# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator
from mathutils import Vector
from pathlib import Path
from os import path

ModelScaleRatio = 100
FilePath = ''
TextureAlias = {}

def ImportTextureAlias():
    global TextureAlias

    pluginFile = path.realpath(__file__)
    #Read in the json
    with open(path.join(path.dirname(pluginFile), "alias_list.json")) as file:
        #and convert it to the dictionary
        TextureAlias = json.loads(file.read())


class ImportMDL2(Operator, ImportHelper):
    """Import MDL2 file from Ty1"""
    bl_idname = "mdl.importer"  # important since its how bpy.ops.mdl.importer is constructed
    bl_label = "Import MDL2"

    # ImportHelper mixin class uses this
    filename_ext = ".mdl"

    filter_glob: StringProperty(
        default="*.mdl",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    SmoothShading: BoolProperty(
        name="Shade Smooth",
        description="Apply smooth shading to the imported mesh",
        default=True,
    )
    ImportBoundingBox: BoolProperty(
        name="Import Bounding Box",
        description="Import the bounding box from the MDL data, some models use the bounding box for collision (mainly just the tilting platforms)",
        default=False,
    )

    OriginEnum: EnumProperty(
        name='Origin Position',
        description='Which origin to use',
        items=[('ORIGIN_GEOMETRY', 'Model Center', 'Use the center of the model as the origin (Usually gives nicer origin points, but may have some issues exporting certain models with a different origin point)'),
               ('ORIGIN_CURSOR', 'MDL Origin', 'Use the origin from the MDL file (May be important for some models)')
        ]
    )

    def execute(self, context):
        return CreateModel(self, context, self.filepath, self.SmoothShading, self.ImportBoundingBox, self.OriginEnum)

    
def CreateModel(self, context, filepath, smoothShading, importBoundingBox, originEnum):

    self.report({'INFO'}, 'Start Reading MDL')
    file = open(filepath, "rb")
    global FilePath
    FilePath = filepath

    ImportTextureAlias()
    MDLHeader.GatherValues(file)
    ComponentDescriptor.GatherValues(file)

    if (MDLHeader.RefPointCount != 0):
        RefPoints.GatherValues(file)

    MeshDescriptor.GatherValues(file)
    Strips.GatherValues(file)

    file.close()
    
    CreateBlenderMesh.Create(smoothShading, importBoundingBox, originEnum)

    #Add a undo/redo restore point
    #Makes it so undo doesn't act weirdly sometimes, and fixes the crash when trying to undo the import right after importing it
    bpy.ops.ed.undo_push(message=('Import ' + Path(filepath).stem))
    return {'FINISHED'}


class MDLHeader:
    MDLName = ''

    ComponentCount = 0
    RefPointCount = 0
    AnimNodeCount = 0
    ComponentDescOffset = 0
    RefPointOffset = 0
    AnimNodeOffset = 0

    BoundingBoxStart = Vector((0, 0, 0))
    BoundingBoxLength = Vector((0, 0, 0))
    DictEntriesCount = 0
    DictOffset = 0

    #Read the mdl header from the mdl file skipping over unneed data
    def GatherValues(file: BufferedReader):
        #MDL header
        #Skip unneeded data for import
        file.seek(6)

        MDLHeader.ComponentCount = int.from_bytes(file.read(2), byteorder='little', signed=False)
        MDLHeader.RefPointCount = int.from_bytes(file.read(2), byteorder='little', signed=False)
        MDLHeader.AnimNodeCount = int.from_bytes(file.read(2), byteorder='little', signed=False)
        MDLHeader.ComponentDescOffset = int.from_bytes(file.read(4), byteorder='little', signed=False)
        MDLHeader.RefPointOffset = int.from_bytes(file.read(4), byteorder='little', signed=False)
        MDLHeader.AnimNodeOffset = int.from_bytes(file.read(4), byteorder='little', signed=False)

        #Seek past 2 unused ints (usually both 0)
        file.seek(8, 1)
        MDLHeader.BoundingBoxStart = (Vector(struct.unpack('fff', file.read(12)))/ModelScaleRatio).xzy
        #Skip the unused W value
        file.seek(4, 1)
        MDLHeader.BoundingBoxLength = (Vector(struct.unpack('fff', file.read(12)))/ModelScaleRatio).xzy
        #Skip the unused W value
        file.seek(4, 1)

        MDLHeader.DictEntriesCount = int.from_bytes(file.read(4), byteorder='little', signed=False)
        MDLHeader.DictOffset = int.from_bytes(file.read(4), byteorder='little', signed=False)

class ComponentDescriptor:
    Descriptors = list()

    def GatherValues(file: BufferedReader):
        
        ComponentDescriptor.Descriptors = list()
        file.seek(MDLHeader.ComponentDescOffset)
        for x in range(MDLHeader.ComponentCount):
            DescriptorInstance = ComponentData()
            ComponentDescriptor.Descriptors.append(DescriptorInstance)

            #Seek past the seemingly unused bounding box values
            file.seek(32, 1)
            DescriptorInstance.Origin = Vector(struct.unpack('ffff', file.read(16)))/ModelScaleRatio
            DescriptorInstance.ComponentNameOffset = int.from_bytes(file.read(4), byteorder='little', signed=False)
            DescriptorInstance.AnimIDOffset = int.from_bytes(file.read(4), byteorder='little', signed=False)

            #Unknown uint
            file.seek(4, 1)
            DescriptorInstance.VboneCount = int.from_bytes(file.read(4), byteorder='little', signed=False)

            #Renderer ID thing, not needed for importing
            file.seek(2, 1)
            DescriptorInstance.MeshCount = int.from_bytes(file.read(2), byteorder='little', signed=False)
            DescriptorInstance.MeshDescOffset = int.from_bytes(file.read(4), byteorder='little', signed=False)

            #Unknown uint
            file.seek(4, 1)
            DescriptorInstance.MiscPtr = int.from_bytes(file.read(4), byteorder='little', signed=False)
            
            previousLocation = file.tell()
            #Get the component name
            file.seek(DescriptorInstance.ComponentNameOffset)
            DescriptorInstance.ComponentName = Strings.Read0EndedString(file)

            #Get the animation name
            file.seek(DescriptorInstance.AnimIDOffset)
            DescriptorInstance.AnimIDName = Strings.Read0EndedString(file)

            #Jump back to previous location
            file.seek(previousLocation)


class RefPoints:
    Points = list()

    def GatherValues(file: BufferedReader):
        RefPoints.Points = list()
        file.seek(MDLHeader.RefPointOffset)

        for x in range(MDLHeader.RefPointCount):
            RefPointInstance = RefPointData()
            RefPoints.Points.append(RefPointInstance)
    
            #Divide by 100 to scale down
            RefPointInstance.Position = Vector(struct.unpack('ffff', file.read(16)))/ModelScaleRatio

            RefPointInstance.NameOffset = int.from_bytes(file.read(4), byteorder='little', signed=False)
            #Seek past the unknown number that is usually 0
            file.seek(4, 1)

            RefPointInstance.Weight1 = struct.unpack('f', file.read(4))[0]
            RefPointInstance.Weight2 = struct.unpack('f', file.read(4))[0]
            
            previousLocation = file.tell()
            #Get the ref point name
            file.seek(RefPointInstance.NameOffset)
            RefPointInstance.Name = Strings.Read0EndedString(file)

            #Jump back to previous location
            file.seek(previousLocation)
        
class MeshDescriptor:
    Descriptors = list()

    def GatherValues(file: BufferedReader):
        MeshDescriptor.Descriptors = list()

        #Loop through every component
        for x in range(MDLHeader.ComponentCount):
            meshes = list()
            #Seek to the mesh descriptor offset just for the odd cases like the pontoon
            #where the mesh descriptors aren't one after another
            file.seek(ComponentDescriptor.Descriptors[x].MeshDescOffset)

            #Loop through all the meshes in that component
            for i in range(ComponentDescriptor.Descriptors[x].MeshCount):
                meshInstance = MeshData()
                meshes.append(meshInstance)
                meshInstance.TextureNameOffset = int.from_bytes(file.read(4), byteorder='little', signed=False)
                meshInstance.StripListOffset = int.from_bytes(file.read(4), byteorder='little', signed=False)
                #Skip past the seemingly unused max offset? value
                file.seek(4, 1)
                meshInstance.StripListCount = int.from_bytes(file.read(4), byteorder='little', signed=False)
                
                previousLocation = file.tell()
                #Get the texture name
                file.seek(meshInstance.TextureNameOffset)
                meshInstance.TextureName = Strings.Read0EndedString(file)

                #Jump back to previous location
                file.seek(previousLocation)
            
            MeshDescriptor.Descriptors.append(meshes)
                
class Strips:
    Objects = list()

    def GatherValues(file: BufferedReader):
        Strips.Objects = list()
        startTime = time.time()
        vertexTime = 0.0
        normalTime = 0.0
        UVTime = 0.0
        colourTime = 0.0
        faceTime = 0.0

        #Loop through every component
        for c in range(MDLHeader.ComponentCount):
            meshes = list()
            #Loop through all the meshes in that component
            for m in range(ComponentDescriptor.Descriptors[c].MeshCount):
                #Jump to the start of the strip
                file.seek(MeshDescriptor.Descriptors[c][m].StripListOffset)

                stripsData = VertexData()
                vertexID = 0
                #Loop through all the strips
                for s in range(MeshDescriptor.Descriptors[c][m].StripListCount):
                    faceIDs = [0, 0, 0]

                    #Skip past the 3 unknown ints (ID?, 00 00 00 00 (00 00 00 14 for every one after the first strip), 00 80 02 6C)
                    #First int for a strip is unique then every one after is (FF FF 00 01)
                    file.seek(12, 1)
                    VertexCount = int.from_bytes(file.read(4), byteorder='little', signed=False)
                    #Skip past 8 unknown ints (00 00 00 00, 00 00 00 00, 00 00 00 00 (sometimes 01 00 00 00), Unique, 00 40 3E 30, 12 04 00 00, 00 00 00 00, 04 01 00 01)
                    file.seek(32, 1)

                    #Skip past the vertex identifier
                    file.seek(4, 1)
                    #Add all the verticies to the list
                    for v in range(VertexCount):
                        #Divide to scale the mesh down to a better size with blenders units
                        vertex = Vector(struct.unpack('fff', file.read(12)))/ModelScaleRatio
                        vertex.xyz = vertex.xzy
                        stripsData.VertexPositions.append(vertex)
                    vertexTime += time.time() - startTime
                    #reset the start time for the next part
                    startTime = time.time()

                    #Skip past the normal identifier
                    file.seek(4, 1)
                    #Add all the normals and bone 2
                    for n in range(VertexCount):
                        normal = Vector(struct.unpack('bbb', file.read(3)))/127
                        normal.xyz = normal.xzy
                        normal.normalize()
                        stripsData.Normals.append(normal)
                        stripsData.Bone2.append((list(file.read(1))[0] >> 1) - 1)
                    normalTime += time.time() - startTime
                    #reset the start time for the next part
                    startTime = time.time()

                    #Skip past the UV identifier
                    file.seek(4, 1)
                    for u in range(VertexCount):
                        uv = (Vector(struct.unpack('hh', file.read(4)))/4096)
                        #Vertically flip it with this method if not in the 0-1 range
                        if (uv.y > 1 or uv.y < 0):
                            uv.y = (uv.y * -1) + 1
                        #Else Vertically flip with this
                        else:
                            #UVs are inverted vertically so 1 - the vector to invert the 0-1 range, eg. 0 becomes 1, 1 become 0, 0.25 becomes 0.75
                            uv.y = 1 - uv.y
                        stripsData.UVs.append(uv)
                        stripsData.BoneWeight.append(struct.unpack('H', file.read(2))[0]/4096)
                        stripsData.Bone1.append((struct.unpack('H', file.read(2))[0] >> 2) - 1)
                    UVTime += time.time() - startTime
                    #reset the start time for the next part
                    startTime = time.time()
                        
                    #Skip past the Colour identifier
                    file.seek(4, 1)
                    for vc in range(VertexCount):
                        colour = Vector(struct.unpack('BBBB', file.read(4)))
                        colour = Strips.VectorToColour(colour)
                        if (colour[3] < 1):
                            stripsData.TransparentVertexColour = True
                        stripsData.VertexColours.append(colour)
                    colourTime += time.time() - startTime
                    #reset the start time for the next part
                    startTime = time.time()

                    #Populate the face list
                    for vertexNum in range(VertexCount):
                        faceIDs[vertexNum % 3] = vertexID
                        if (1 < vertexNum):
                            computedNormal = Strips.ComputedNormal(stripsData.VertexPositions[faceIDs[0]], stripsData.VertexPositions[faceIDs[1]],stripsData.VertexPositions[faceIDs[2]])

                            actualNormal = (stripsData.Normals[faceIDs[0]] + stripsData.Normals[faceIDs[1]] + stripsData.Normals[faceIDs[2]]).normalized()

                            normalDirection = computedNormal.dot(actualNormal)
                            if (normalDirection >= 0.0):
                                stripsData.Faces.append([faceIDs[0], faceIDs[1], faceIDs[2]])
                            else:
                                stripsData.Faces.append([faceIDs[2], faceIDs[1], faceIDs[0]])
                        
                        vertexID += 1

                    faceTime += time.time() - startTime
                    #reset the start time for the next part
                    startTime = time.time()

                meshes.append(stripsData)

            Strips.Objects.append(meshes)

        print('Vertex Time (Sec): ' + str(vertexTime))
        print('Normal Time (Sec): ' + str(normalTime))
        print('Colour Time (Sec): ' + str(colourTime))
        print('UV Time (Sec): ' + str(UVTime))
        print('Face Time (Sec): ' + str(faceTime))
        print('Total Time (Sec): ' + str(vertexTime + normalTime + colourTime + UVTime + faceTime))

    def ComputedNormal(vertexPos1: Vector, vertexPos2: Vector, vertexPos3: Vector):
        return ((vertexPos3 - vertexPos1).cross(vertexPos2 - vertexPos1)).normalized()



    def VectorToColour(ColourVector: Vector):
        #Loop through each colour channel and convert them to a 0-255 range
        for b in range(4):
            if (ColourVector[b] == 0):
                continue
            #expression_if_true *if* condition *else* expression_if_false
            ColourVector[b] = (2*ColourVector[b]-1) if (ColourVector[b] <= 0x80) else (ColourVector[b]-1)*2
            ColourVector[b] = ColourVector[b]/255
        return ColourVector


class CreateBlenderMesh:

    def Create(shadeSmooth: bool, importBoundingBox: bool, originEnum: EnumProperty):
        startTime = time.time()
        #Make sure something is a active object otherwise will get a error
        if (bpy.context.active_object != None):
            bpy.ops.object.mode_set(mode='OBJECT')
        #Start with everything deselected so all the origins get set
        bpy.ops.object.select_all(action='DESELECT')

        objectsToSelect = []
        for components in range(MDLHeader.ComponentCount):
            modelCollection = bpy.data.collections.new(ComponentDescriptor.Descriptors[components].ComponentName)
            bpy.context.scene.collection.children.link(modelCollection)
            for meshes in range(ComponentDescriptor.Descriptors[components].MeshCount):
                #Mesh
                mesh = bpy.data.meshes.new(ComponentDescriptor.Descriptors[components].ComponentName)

                mesh.from_pydata(Strips.Objects[components][meshes].VertexPositions, [], Strips.Objects[components][meshes].Faces)

                #UVs and vertex colours
                uv = mesh.uv_layers.new(name=(ComponentDescriptor.Descriptors[components].ComponentName + ' UV'))
                mesh.vertex_colors.new(name=ComponentDescriptor.Descriptors[components].ComponentName + ' Colour')
                for vertexLoop in mesh.loops:
                    uv.data[vertexLoop.index].uv = Strips.Objects[components][meshes].UVs[vertexLoop.vertex_index]
                    mesh.vertex_colors.active.data[vertexLoop.index].color = Strips.Objects[components][meshes].VertexColours[vertexLoop.vertex_index]

                #use bmesh for the remove doubles function for much faster import
                bm = bmesh.new()

                bm.from_mesh(mesh)
                bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.005)

                bm.to_mesh(mesh)
                mesh.update()
                bm.clear()
                bm.free()

                #Create the object
                object = bpy.data.objects.new(ComponentDescriptor.Descriptors[components].ComponentName, mesh)
                
                #Check if the texture if for a collision type
                collisionMat = False
                if (MeshDescriptor.Descriptors[components][meshes].TextureName in enum_members_from_type(type(object.MDLCollisions), 'CollisionTypes')):
                    object.MDLCollisions.CollisionTypes = MeshDescriptor.Descriptors[components][meshes].TextureName
                    collisionMat = True
                #elif (any(substring in MeshDescriptor.Descriptors[components][meshes].TextureName.lower() for substring in ['ty_', 'ice', 'room'])):
                    #object.MDLCollisions.CollisionTypes = 'Custom'
                    #object.MDLCollisions.CustomCollision = MeshDescriptor.Descriptors[components][meshes].TextureName
                    #collisionMat = True
                
                #Only make the material if its not a collision material
                if (not collisionMat):
                    #Create and add the material
                    material = GetMaterial(path.join(path.dirname(FilePath), "DDS"), MeshDescriptor.Descriptors[components][meshes].TextureName, Strips.Objects[components][meshes].TransparentVertexColour)
                    if material:
                        if object.data.materials:
                            object.data.materials[0] = material
                        else:
                            object.data.materials.append(material)
                        
                
                modelCollection.objects.link(object)

                #Select the object to set its origin
                object.select_set(True)
                
                #Set the origin points
                #Store the location of current 3d cursor
                saved_location = bpy.context.scene.cursor.location
                #Give 3dcursor new coordinates
                bpy.context.scene.cursor.location = ComponentDescriptor.Descriptors[components].Origin.xzy
                #Set the origin on the current object to the either the 3dcursor location or the object center based on the enum
                bpy.ops.object.origin_set(type=originEnum)
                #Set 3dcursor location back to the stored location
                bpy.context.scene.cursor.location = saved_location

                #Shade smooth if the option is checked
                if (shadeSmooth):
                    bpy.ops.object.shade_smooth()
                    
                #Deselect all the objects when done
                bpy.ops.object.select_all(action='DESELECT')

                objectsToSelect.append(object)
            
        for obj in objectsToSelect:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = objectsToSelect[0]
            


        #Bounding box, used for frustrum and oclusion culling (probably something different for levels) and collision for tilting platforms
        if (importBoundingBox):
            BoundingBox = bpy.data.objects.new('Bounding Box', None)
            #Get the center of the bounding box
            BoundingBox.location = (MDLHeader.BoundingBoxStart + (MDLHeader.BoundingBoxStart + MDLHeader.BoundingBoxLength))/2
            #Halve it as the scale is twice its length
            BoundingBox.scale = MDLHeader.BoundingBoxLength/2

            bpy.context.scene.collection.objects.link(BoundingBox)

            BoundingBox.empty_display_type = 'CUBE'


        if (MDLHeader.RefPointCount > 0):
            #Create the collection for the ref points, check if the collection already exists for easier exporting
            if ('Ref Points' not in bpy.data.collections):
                refCollection = bpy.data.collections.new('Ref Points')
                bpy.context.scene.collection.children.link(refCollection)
            else:
                refCollection = bpy.data.collections['Ref Points']

            #Create the empties for the ref points
            for refPoint in RefPoints.Points:
                empty = bpy.data.objects.new(refPoint.Name, None)
                empty.location = refPoint.Position.xzy

                refCollection.objects.link(empty)

                #Some have the w value set to 0 (w is radius maybe?)
                empty.empty_display_size = refPoint.Position.w if refPoint.Position.w > 0.05 else 0.05
                empty.empty_display_type = 'SPHERE'

        print('Create Mesh Time (Sec): ' + str(time.time() - startTime))
        print('')#Padding Line to separate different imports or exports

def enum_members_from_type(rna_type, prop_str):
    prop = rna_type.bl_rna.properties[prop_str]
    return [e.identifier for e in prop.enum_items]

def GetMaterial(texturePath, textureName, transparentVertexColour):
    if (textureName == ""):
        print('Empty String')
        return None
    textureFound = True
    #Use the original name instead of the name in the alias (if it has one), just because some are variants in global.mad, like no_grass ones
    originalName = textureName

    #Check if the image doesn't exist
    if (not Path(path.join("./", texturePath, textureName + '.dds')).is_file()):
        #Check if it has a alias
        if ((textureName.lower() in TextureAlias) and (Path(path.join("./", texturePath, TextureAlias[textureName.lower()] + '.dds')).is_file())):
            textureName = TextureAlias[textureName.lower()]
        #Check lowercase name
        elif (Path(path.join("./", texturePath, textureName.lower() + '.dds')).is_file()):
            textureName = textureName.lower()
        else:
            textureFound = False

    #Check if the material already exists
    if (originalName in bpy.data.materials):
        material = bpy.data.materials[originalName]
        return material
    
    material = bpy.data.materials.new(name=originalName)
    material.use_nodes = True
    bsdf = material.node_tree.nodes['Principled BSDF']
    texureImage = material.node_tree.nodes.new('ShaderNodeTexImage') if textureFound else material.node_tree.nodes.new('ShaderNodeRGB')
    #Just to have the material the same
    if (not textureFound and transparentVertexColour):
        placeholderAlpha = material.node_tree.nodes.new('ShaderNodeValue')
        placeholderAlpha.outputs[0].default_value = 1.0
    colourMultiply = material.node_tree.nodes.new('ShaderNodeMixRGB')
    colourMultiply.blend_type = 'MULTIPLY'
    colourMultiply.inputs['Fac'].default_value = 1.0
    vertexColour = material.node_tree.nodes.new('ShaderNodeVertexColor')

    if (textureFound):
        texureImage.image = bpy.data.images.load(path.join("./", texturePath, textureName + '.dds'))
    else:
        texureImage.outputs[0].default_value = (1, 1, 1, 1)
    material.node_tree.links.new(colourMultiply.inputs['Color1'], texureImage.outputs['Color'])
    material.node_tree.links.new(colourMultiply.inputs['Color2'], vertexColour.outputs['Color'])
    material.node_tree.links.new(bsdf.inputs['Base Color'], colourMultiply.outputs['Color'])

    #Check if the image has a alpha channel
    if (((texureImage.image.depth == 32) if textureFound else False) or transparentVertexColour):
        #Set up the alpha
        mathNode = material.node_tree.nodes.new('ShaderNodeMath')
        mathNode.operation = 'MULTIPLY'
        material.node_tree.links.new(mathNode.inputs[0], texureImage.outputs['Alpha'] if textureFound else placeholderAlpha.outputs[0])
        material.node_tree.links.new(mathNode.inputs[1], vertexColour.outputs['Alpha'])
        material.node_tree.links.new(bsdf.inputs['Alpha'], mathNode.outputs[0])
        #Just safer to assume its alpha blended
        material.blend_method = 'BLEND'
        material.shadow_method = 'HASHED'
        
    return material


class Strings:

    def Read0EndedString(file: BufferedReader):
        resultString = ''
        #Have to add this because file.peek(1) is being dumb and reading the whole rest of the file instead of one byte like it should
        currentValue = file.read(1)

        #Loop through until find the end of the string
        while (currentValue != b'\x00'):
            #Failsafe to make it so it won't go past the end of the file looking for a 0, python also doesn't throw a error when past the end of the file
            #Also sometimes some models have a sting offset that is past the end of the file
            if (file.tell() > Path(file.name).stat().st_size):
                #Discard the string and just assume its bad
                return ''
            resultString += currentValue.decode('utf-8')
            currentValue = file.read(1)
        return resultString




class ComponentData:
    Origin = Vector((0.0, 0.0, 0.0, 0.0))
    ComponentNameOffset = 0
    ComponentName = ''
    AnimIDOffset = 0
    #Blank if no ID
    AnimIDName = ''
    VboneCount = 0
    MeshCount = 0
    MeshDescOffset = 0
    MiscPtr = 0

class RefPointData:
    Position = Vector((0.0, 0.0, 0.0, 0.0))
    NameOffset = 0
    Name = ''
    Weight1 = 0.0
    Weight2 = 0.0

class MeshData:
    TextureNameOffset = 0
    TextureName = ''
    StripListOffset = 0
    StripListCount = 0

class VertexData:

    def __init__(self):
        self.VertexPositions = []
        self.Faces = []
        self.Normals = []
        self.Bone2 = []
        self.UVs = []
        self.BoneWeight = []
        self.Bone1 = []
        self.VertexColours = []

    VertexPositions = []

    #Vertex index in the vertex position list
    Faces = []

    Normals = []
    Bone2 = []

    UVs = []
    BoneWeight = []
    Bone1 = []

    VertexColours = []
    TransparentVertexColour = False