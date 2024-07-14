import time
import bpy
import bmesh
import ctypes
import struct
import numpy as np

# ExportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty
from bpy.types import Object, Operator
from mathutils import Vector
from pathlib import Path

ModelScaleRatio = 100

class ExportMDL2(Operator, ExportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "mdl.exporter"  # important since its how bpy.ops.mdl.exporter is constructed
    bl_label = "Export MDL2"

    # ExportHelper mixin class uses this
    filename_ext = ".mdl"

    filter_glob: StringProperty(
        default="*.mdl",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        return ExportModel(self, context, self.filepath)
    

def ExportModel(self, context, filepath):

    #Check if there is any meshes in the scene otherwise will get a error if there is none
    meshes = list(o for o in bpy.data.objects if o.type == 'MESH')
    if (len(meshes) == 0):
        self.report({'ERROR'}, 'No Meshes in the Scene')
        return {'CANCELLED'}

    file = open(filepath, 'wb')

    startTime = time.time()
    headerTime = 0.0
    componentTime = 0.0
    refPointsTime = 0.0
    meshDescriptorTime = 0.0
    stripTime = 0.0
    stringListTime = 0.0

    #MDL Header
    file.write(bytearray("MDL2", 'utf-8'))
    file.write(ctypes.c_short(1)) #Matrix count (Hard code for now to 1 until animation stuff is done)
    #Check that the collection has a mesh in it
    validCollectionCount = 0
    for collection in bpy.data.collections:
        meshes = list(o for o in collection.all_objects if o.type == 'MESH')
        if (len(meshes) > 0):
            validCollectionCount += 1
    file.write(ctypes.c_short(validCollectionCount + len(list(o for o in bpy.data.scenes['Scene'].collection.all_objects if o.type == 'MESH' and o.users_collection[0] == bpy.data.scenes['Scene'].collection)))) #Component Count
    #Ref Points
    if ('Ref Points' in bpy.data.collections):
        file.write(ctypes.c_short(len(list(o for o in bpy.data.collections['Ref Points'].all_objects if o.type == 'EMPTY'))))
    else:
        file.write(ctypes.c_short(0))
    file.write(ctypes.c_short(0)) #Anim Node count (Hard code for now to 0 until animation stuff is done)
    #Come back on the second pass for offset
    componentDescOffset = file.tell()
    file.write(ctypes.c_int(0)) #Fill with a blank int for now
    refPointsOffset = file.tell()
    file.write(ctypes.c_int(0))
    animNodeOffset = file.tell()
    file.write(struct.pack('III', 0, 0, 0))

    #Bounding Box
    #Use existing bounding box
    if ('Bounding Box' in bpy.data.objects):
        boundingBox = bpy.data.objects['Bounding Box']
        boundingBoxStart = (boundingBox.location - boundingBox.scale) * ModelScaleRatio
        boundingBoxLength = boundingBox.scale * ModelScaleRatio * 2
        file.write(struct.pack('ffff', boundingBoxStart.x, boundingBoxStart.z, boundingBoxStart.y, 0.0)) #Bounding Box Start Point (Including the seemingly unused W value)
        file.write(struct.pack('ffff', boundingBoxLength.x, boundingBoxLength.z, boundingBoxLength.y, 0.0)) #Bounding Box Length (Including the seemingly unused W value)
    #Or calculate a new one
    else:
        bbox_corners = []
        meshes = list(o for o in bpy.data.objects if o.type == 'MESH')
        #Loop through all the meshes getting their bounding box corners
        for mesh in meshes:
            bbox_corners = bbox_corners + [mesh.matrix_world @ Vector(corner) for corner in mesh.bound_box]
        #Get the min and max values of all the bounding boxes for each axis
        x_min, y_min, z_min = np.array(bbox_corners).min(axis=0)
        boundingBoxMin = Vector([x_min, z_min, y_min]) * ModelScaleRatio #make sure to scale by 100 to get the right scale for the game and flip the y and z
        x_max, y_max, z_max = np.array(bbox_corners).max(axis=0)
        boundingBoxMax = Vector([x_max, z_max, y_max]) * ModelScaleRatio #make sure to scale by 100 to get the right scale for the game and flip the y and z

        file.write(struct.pack('ffff', boundingBoxMin.x, boundingBoxMin.y, boundingBoxMin.z, 0.0)) #Bounding Box Start Point (Including the seemingly unused W value)
        length = Vector(np.absolute(boundingBoxMin) + boundingBoxMax)
        file.write(struct.pack('ffff', length.x, length.y, length.z, 0.0)) #Bounding Box Length (Including the seemingly unused W value)

    dictionaryCountOffset = file.tell()
    file.write(ctypes.c_int(0)) #Come back to the dictionary entry count later
    dictionaryOffset = file.tell()
    file.write(ctypes.c_int(0)) 

    file.write(struct.pack('BBBBI', 0, 0, 0, 0, 0)) #Unknown values

    file.write(ctypes.c_uint(int(time.time()))) #Creation Data

    originalFileNameOffset = file.tell()
    file.write(ctypes.c_int(0))

    file.write(struct.pack('IIIIII', 0, 0, 0, 0, 0, 0)) #Unknown values
    
    #Add the component offset
    componentLocation = file.tell()
    file.seek(componentDescOffset)
    file.write(ctypes.c_int(componentLocation))

    file.seek(componentLocation)

    headerTime = time.time() - startTime
    startTime = time.time()

    ##--------------------------------------------------------------
    
    #Component Descriptor
    componentNameOffsets = []
    parentedBoneOffsets = []
    meshDescOffsets = []
    #Collections that have atlest 1 mesh in them
    vaildCollections = []

    for collection in bpy.data.collections:
        #Get all the meshes in the collection
        meshes = list(o for o in collection.all_objects if o.type == 'MESH')
        #If theres no meshes don't add it
        if (len(meshes) > 0):
            vaildCollections.append(collection)
            offsets = WriteComponentDesc(meshes, file)
            componentNameOffsets.append(offsets[0])
            parentedBoneOffsets.append(offsets[1])
            meshDescOffsets.append(offsets[2])

    #Meshes that are not in any collection, only in the scene collection
    sceneMeshes = list(o for o in bpy.data.scenes['Scene'].collection.all_objects if o.type == 'MESH' and o.users_collection[0] == bpy.data.scenes['Scene'].collection)
    sceneComponentNameOffsets = []
    sceneParentedBoneOffsets = []
    sceneMeshDescOffsets = []
    for mesh in sceneMeshes:
        offsets = WriteComponentDesc([mesh], file) #make it a list so its iterable so I don't have to have a check with the for loop
        sceneComponentNameOffsets.append(offsets[0])
        sceneParentedBoneOffsets.append(offsets[1])
        sceneMeshDescOffsets.append(offsets[2])

    componentTime = time.time() - startTime
    startTime = time.time()

    ##-----------------------------------------------------------

    #RefPoints
    refPointNameOffsets = []

    if ('Ref Points' in bpy.data.collections):
        refPoints = list(o for o in bpy.data.collections['Ref Points'].all_objects if o.type == 'EMPTY')

        #Add the ref points offset
        refPointLocation = file.tell()
        file.seek(refPointsOffset)
        file.write(ctypes.c_int(refPointLocation))
        file.seek(refPointLocation)

        #Add all the data for the ref points
        for point in refPoints:
            pointLocation = point.location.xzy * 100
            file.write(struct.pack("ffff", pointLocation.x, pointLocation.y, pointLocation.z, point.empty_display_size * 100))

            refPointNameOffsets.append(file.tell())
            file.write(ctypes.c_int(0))

            file.write(ctypes.c_int(0)) #Unknown

            file.write(ctypes.c_float(1)) #Unknown Weight Value (This one is usually 1)
            file.write(ctypes.c_float(0)) #Unknown Weight Value

    refPointsTime = time.time() - startTime
    startTime = time.time()
    
    ##-----------------------------------------------------------

    #Mesh Descriptor
    textureNameOffsets = []
    stripListOffsets = []

    for index, collection in enumerate(vaildCollections):
        meshes = list(o for o in collection.all_objects if o.type == 'MESH')
            
        meshDescLocation = file.tell()
        file.seek(meshDescOffsets[index])
        file.write(ctypes.c_int(meshDescLocation))
        file.seek(meshDescLocation)

        for mesh in meshes:
            textureNameOffsets.append(file.tell())
            file.write(ctypes.c_int(0))
            stripListOffsets.append(file.tell())
            file.write(ctypes.c_int(0))
                
            file.write(ctypes.c_int(0)) #Max Offset? Seemingly Unused
            file.write(ctypes.c_int(0)) #Mesh Strip Count

    sceneTextureNameOffsets = []
    sceneStripListOffsets = []

    #All the meshes in the scene collection
    for index, mesh in enumerate(sceneMeshes):
        meshDescLocation = file.tell()
        file.seek(sceneMeshDescOffsets[index])
        file.write(ctypes.c_int(meshDescLocation))
        file.seek(meshDescLocation)

        sceneTextureNameOffsets.append(file.tell())
        file.write(ctypes.c_int(0))
        sceneStripListOffsets.append(file.tell())
        file.write(ctypes.c_int(0))
            
        file.write(ctypes.c_int(0)) #Max Offset? Seemingly Unused
        file.write(ctypes.c_int(0)) #Mesh Strip Count

    meshDescriptorTime = time.time() - startTime
    startTime = time.time()

    ##-----------------------------------------------------------

    meshIndex = 0
    #Strips
    originalSelectedObjects = bpy.context.selected_objects
    originalActiveObject = bpy.context.view_layer.objects.active
    #If no object is the active object than this will have a error
    if (originalActiveObject != None):
        originalMode = bpy.context.object.mode
    
    for index, collection in enumerate(vaildCollections):
        meshes = list(o for o in collection.all_objects if o.type == 'MESH')

        meshIndex = WriteStrips(meshes, file, stripListOffsets, meshIndex)

    #Do the same for all the scene meshes
    for index, mesh in enumerate(sceneMeshes):
        #Make mesh a list so can iterate on it
        WriteStrips([mesh], file, sceneStripListOffsets, index)
    
    #Restore it to the state it was in before
    bpy.ops.object.select_all(action='DESELECT')
    for object in originalSelectedObjects:
        object.select_set(True)
    bpy.context.view_layer.objects.active = originalActiveObject
    #Check if there was a active object, if there is none then no mode can be set so can assume it was in object mode
    if (originalActiveObject != None):
        bpy.ops.object.mode_set(mode = originalMode)

    stripTime = time.time() - startTime
    startTime = time.time()

    ##-----------------------------------------------------------
    
    meshIndex = 0
    textureDict = {}
    dictionaryCount = 0
    noAnimIDsOffset = 0

    componentNameLocation = file.tell()
    file.seek(dictionaryOffset)
    file.write(ctypes.c_int(componentNameLocation))
    file.seek(componentNameLocation)

    #String List
    for index, collection in enumerate(vaildCollections):
        #Set the offset
        componentNameLocation = file.tell()
        file.seek(componentNameOffsets[index])
        file.write(ctypes.c_int(componentNameLocation))
        file.seek(componentNameLocation)

        #Add the component name
        file.write(bytes(collection.name, 'utf-8'))
        file.write(ctypes.c_byte(0)) #String terminator
        dictionaryCount += 1

        #Anim ID Stuff
        if (noAnimIDsOffset == 0):
            noAnimIDsOffset = file.tell()
            #Just write a empty string
            file.write(ctypes.c_byte(0)) #String terminator
            dictionaryCount += 1
        file.seek(parentedBoneOffsets[index])
        file.write(ctypes.c_int(noAnimIDsOffset))
        file.seek(0, 2) #Seek to the end of the file

        #Mesh textures
        meshes = list(o for o in collection.all_objects if o.type == 'MESH')

        tempDictionaryCount, meshIndex = WriteStringList(file, meshes, textureNameOffsets, textureDict, meshIndex)
        dictionaryCount += tempDictionaryCount

    for index, mesh in enumerate(sceneMeshes):
        #Set the offset
        componentNameLocation = file.tell()
        file.seek(sceneComponentNameOffsets[index])
        file.write(ctypes.c_int(componentNameLocation))
        file.seek(componentNameLocation)

        #Add the component name
        file.write(bytes(mesh.name, 'utf-8'))
        file.write(ctypes.c_byte(0)) #String terminator
        dictionaryCount += 1

        #Anim ID Stuff
        if (noAnimIDsOffset == 0):
            noAnimIDsOffset = file.tell()
            #Just write a empty string
            file.write(ctypes.c_byte(0)) #String terminator
            dictionaryCount += 1
        file.seek(sceneParentedBoneOffsets[index])
        file.write(ctypes.c_int(noAnimIDsOffset))
        file.seek(0, 2) #Seek to the end of the file

        tempDictionaryCount, meshIndex = WriteStringList(file, [mesh], sceneTextureNameOffsets, textureDict, index)
        dictionaryCount += tempDictionaryCount
        

    originalFileName = file.tell()
    file.seek(originalFileNameOffset)
    file.write(ctypes.c_int(originalFileName))
    file.seek(originalFileName)
    file.write(bytes('Untitled.blend', 'utf-8') if bpy.data.filepath == "" else bytes(Path(bpy.data.filepath).name, 'utf-8'))
    file.write(ctypes.c_byte(0)) #String terminator
    dictionaryCount += 1
    
    #RefPoints
    if ('Ref Points' in bpy.data.collections):
        refPoints = list(o for o in bpy.data.collections['Ref Points'].all_objects if o.type == 'EMPTY')

        #Add all the data for the ref points
        for index, point in enumerate(refPoints):
            refPointLocation = file.tell()
            file.seek(refPointNameOffsets[index])
            file.write(ctypes.c_int(refPointLocation))
            file.seek(refPointLocation)
            file.write(bytes(point.name, 'utf-8'))
            file.write(ctypes.c_byte(0)) #String terminator
            dictionaryCount += 1

    file.seek(dictionaryCountOffset)
    file.write(ctypes.c_int(dictionaryCount))
    file.seek(0, 2)

    #Doesn't seem to be needed just adding it though just in case
    #Also don't need to add it to the dictionary count and doesn't need a string terminator
    file.write(bytes('end', 'utf-8'))

    stringListTime = time.time() - startTime

    file.close

    print('Header Time (Sec): ', headerTime)
    print('Component Time (Sec): ', componentTime)
    print('Ref Points Time (Sec): ', refPointsTime)
    print('Mesh Descriptor Time (Sec): ', meshDescriptorTime)
    print('Strip Gen Time (Sec): ', stripTime)
    print('String List Time (Sec): ', stringListTime)
    print('Total Time (Sec): ', (headerTime + componentTime + refPointsTime + meshDescriptorTime + stripTime + stringListTime))
    print('')#Padding Line to separate different imports or exports

    return {'FINISHED'}

def WriteStringList(file, meshes, textureNameOffsets, textureDict, meshIndex):
    dictionaryCount = 0

    for mesh in meshes:
        if (mesh.MDLCollisions.CollisionTypes != 'None'):
            collisionType = ''
            collisionType = mesh.MDLCollisions.CollisionTypes
            #Make sure custom collision isn't blank
            if (mesh.MDLCollisions.CollisionTypes == 'Custom' and (mesh.MDLCollisions.CustomCollision != "")):
                #Override it with the custom collision text box value if its custom
                collisionType = mesh.MDLCollisions.CustomCollision
                if (mesh.MDLCollisions.CustomCollision not in textureDict):
                    textureDict[collisionType] = file.tell()
                    file.write(bytes(collisionType, 'utf-8'))
                    file.write(ctypes.c_byte(0)) #String terminator
                    dictionaryCount += 1

            elif (mesh.MDLCollisions.CollisionTypes not in textureDict):
                textureDict[collisionType] = file.tell()
                file.write(bytes(collisionType, 'utf-8'))
                file.write(ctypes.c_byte(0)) #String terminator
                dictionaryCount += 1
                
            if (collisionType != 'Custom'):
                #Update the offset
                file.seek(textureNameOffsets[meshIndex])
                file.write(ctypes.c_int(textureDict[collisionType]))
                file.seek(0, 2) #Seek to the end of the file
        elif (len(mesh.data.materials) > 0):
            #Add it to the dictionary and write it to the file if its a new texture
            if (mesh.data.materials[0].name not in textureDict):
                textureDict[mesh.data.materials[0].name] = file.tell()
                file.write(bytes(mesh.data.materials[0].name, 'utf-8'))
                file.write(ctypes.c_byte(0)) #String terminator
                dictionaryCount += 1
                #Update the offset
            file.seek(textureNameOffsets[meshIndex])
            file.write(ctypes.c_int(textureDict[mesh.data.materials[0].name]))
            file.seek(0, 2) #Seek to the end of the file
        else:
            if ('NoMaterialPresent' not in textureDict):
                textureDict['NoMaterialPresent'] = file.tell()
                #Just write a empty string
                file.write(ctypes.c_byte(0)) #String terminator
                dictionaryCount += 1
            file.seek(textureNameOffsets[meshIndex])
            file.write(ctypes.c_int(textureDict['NoMaterialPresent']))
            file.seek(0, 2) #Seek to the end of the file

        meshIndex += 1
    return dictionaryCount, meshIndex 

def WriteComponentDesc(meshes, file):

    #Component bounding box (seems unneeded but might as well include it just incase)
    bbox_corners = []
    #The origin for all the objects in the collection
    allObjestOrigin = Vector([0,0,0]) 
    #Loop through all the meshes getting their bounding box corners
    for mesh in meshes:
        bbox_corners = bbox_corners + [mesh.matrix_world @ Vector(corner) for corner in mesh.bound_box]
        allObjestOrigin += mesh.location
    #Get the min and max values of all the bounding boxes for each axis
    x_min, y_min, z_min = np.array(bbox_corners).min(axis=0)
    boundingBoxMin = Vector([x_min, z_min, y_min]) * ModelScaleRatio #make sure to scale by 100 to get the right scale for the game and flip the y and z
    x_max, y_max, z_max = np.array(bbox_corners).max(axis=0)
    boundingBoxMax = Vector([x_max, z_max, y_max]) * ModelScaleRatio #make sure to scale by 100 to get the right scale for the game and flip the y and z

    file.write(struct.pack('ffff', boundingBoxMin.x, boundingBoxMin.y, boundingBoxMin.z, 0.0)) #Bounding Box Start Point (Including the seemingly unused W value)
    length = Vector(np.absolute(boundingBoxMin) + boundingBoxMax)
    file.write(struct.pack('ffff', length.x, length.y, length.z, 0.0)) #Bounding Box Length (Including the seemingly unused W value)

    #Get the center point
    allObjestOrigin = (allObjestOrigin / len(meshes)) * ModelScaleRatio #multiply by 100 to get the right scale
    file.write(struct.pack('ffff', allObjestOrigin.x, allObjestOrigin.z, allObjestOrigin.y, 0.0))

    componentNameOffset = file.tell()
    file.write(ctypes.c_int(0))
        
    parentedBoneOffset = file.tell()
    file.write(ctypes.c_int(0))
        
    file.write(ctypes.c_int(0)) #Unknown

    file.write(ctypes.c_int(0)) #Sub object type
    file.write(ctypes.c_short(0)) #Render thing?

    file.write(ctypes.c_short(len(meshes))) #Mesh count
    MeshDescOffset = file.tell()
    file.write(ctypes.c_int(0))
        
    file.write(ctypes.c_int(0)) #Unknown
        
    file.write(ctypes.c_int(0)) #Misc Pointer?

    return componentNameOffset, parentedBoneOffset, MeshDescOffset

def WriteStrips(meshes: Object, file, stripListOffsets, meshIndex):

    firstStripHeaderPart1 = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x02\x6C'
    secondStripHeaderPart1 = b'\xFF\xFF\x00\x01\x00\x00\x00\x14\x00\x80\x02\x6C'
    stripHeaderPart2 = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x40\x3E\x30\x12\x04\x00\x00\x00\x00\x00\x00\x04\x01\x00\x01'

    stripEnd = b'\xFF\xFF\x00\x01\x00\x00\x00\x14'
    stripLastRow = b'\x00\x00\x00\x60\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

    vertexIdentifier = b'\x02\x80\x08\x68'
    normalIdentifier = b'\x03\x80\x08\x6E'
    uvIdentifier = b'\x04\x80\x08\x6D'
    colorIdentifier = b'\x05\xC0\x08\x6E'

    #Loop through all the different screen areas open in blender and find which one is the viewport
    for screenArea in bpy.context.screen.areas:
        if screenArea.type == 'VIEW_3D':
            break
    #From that screen area get its context for the context override used for the rip operation
    contextOverride = {}
    contextOverride["area"] = screenArea
    contextOverride["space_data"] = screenArea.spaces.active
    contextOverride["region"] = screenArea.regions[-1]
    
    mesh: Object
    for mesh in meshes:
        #Make sure something is a active object otherwise will get a error
        if (bpy.context.active_object != None):
            #Make sure to be in object mode to avoid the deselect error
            bpy.ops.object.mode_set(mode = 'OBJECT')

        originalMesh = bmesh.new()
        originalMesh.from_mesh(mesh.data)

        #Split the mesh on the UV seams so that it'll export the UVs correctly and not connect any that shouldn't be connected
        bpy.context.view_layer.objects.active = mesh
        bpy.ops.object.select_all(action='DESELECT')
        mesh.select_set(True)
        bpy.ops.object.mode_set(mode = 'EDIT')
        context = bpy.context
        obj = context.edit_object
        seamMesh = obj.data
        bm = bmesh.from_edit_mesh(seamMesh)
        #Old seams
        OldSeams = [e for e in bm.edges if e.seam]
        #Unmark
        for e in OldSeams:
            e.seam = False
        #Mark seams from uv islands
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.uv.seams_from_islands()
        seams = [e for e in bm.edges if e.seam]
        # split on seams
        bmesh.ops.split_edges(bm, edges=seams)
        bmesh.update_edit_mesh(seamMesh)
        bm.clear
        bm.free()
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_mode(type="VERT")
        bpy.ops.object.mode_set(mode = 'OBJECT')

        #Check for any vertices that have more than one UV, otherwise they will have a glitched UV (This only occurs on faces that are connected by 1 vertex)
        #Kept the edge split method above because its much more efficient than using this for the edges too
        UVCoordsDictionary = {}
        linkedUVs = []
        for vertexLoop in mesh.data.loops:
            #If it doesn't have the same coordinate can assume that the vertex has more than one UV
            if (vertexLoop.vertex_index in UVCoordsDictionary and mesh.data.uv_layers[0].data[vertexLoop.index].uv != UVCoordsDictionary[vertexLoop.vertex_index]):
                if (vertexLoop.vertex_index not in linkedUVs):
                    linkedUVs.append(vertexLoop.vertex_index)
            UVCoordsDictionary[vertexLoop.vertex_index] = mesh.data.uv_layers[0].data[vertexLoop.index].uv

        #Loop through all of the verts that have more than one UV, if any, and split them
        for vert in linkedUVs:
            mesh.data.vertices[vert].select = True
            bpy.ops.object.mode_set(mode = 'EDIT', toggle=False)
            bpy.ops.mesh.rip(contextOverride, 'INVOKE_DEFAULT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode = 'OBJECT')

        #Get all the indices of the mesh
        bm = bmesh.new()
        bm.from_mesh(mesh.data)
        #Make sure to triangulate the bmesh otherwise Zawata's strip gen code won't work
        bmesh.ops.triangulate(bm, faces=bm.faces)
            
        bm.verts.ensure_lookup_table()
        invalidEdges = []
        for e in bm.edges:
            if (len(e.link_faces) > 2):
                invalidEdges.append(e)
        if (len(invalidEdges) > 0):
            bmesh.ops.split_edges(bm, edges=invalidEdges)

        bm.faces.ensure_lookup_table()
        uv_layer = bm.loops.layers.uv.active
        if (len(mesh.data.vertex_colors) > 0):
            vertexColourLayer = bm.loops.layers.color.active
            vertexColoursDict = {}
        VertexLoop = []
        #Using a dictionary only works because the mesh got split based on the UV island, 
        #meaning now every vertex is only assigned to one UV vertex
        UVCoordsDictionary = {}
        faceIDX = []
        for f in bm.faces:
            faceIDX.append([v.index for v in f.verts])
            #Index all the UVs for exporting
            for loop in f.loops:
                VertexLoop.append(loop.vert.index)
                UVCoordsDictionary[loop.vert.index] = loop[uv_layer].uv
                if (len(mesh.data.vertex_colors) > 0):
                    vertexColoursDict[loop.vert.index] = loop[vertexColourLayer]

        sg = StripGenerater(faceIDX)
        stripsIDX = sg.gen_strips()

        stripLocation = file.tell()
        file.seek(stripListOffsets[meshIndex])
        file.write(ctypes.c_int(stripLocation)) #Strip offset
        file.write(ctypes.c_int(0)) #Max offset?
        file.write(ctypes.c_int(len(stripsIDX))) #Strip count
        file.seek(stripLocation)

        firstStrip = True
        #Stop a error from happening when getting the vertex location
        bm.verts.ensure_lookup_table()
        for strip in stripsIDX:
            file.write(firstStripHeaderPart1 if firstStrip else secondStripHeaderPart1)
            file.write(ctypes.c_int(len(strip)))
            file.write(stripHeaderPart2)
            firstStrip= False

            file.write(vertexIdentifier)
            for index in strip:
                #Multiply by the world matrix to apply the transforms to the mesh
                vertexPosition = (mesh.matrix_world @ bm.verts[index].co) * 100
                file.write(struct.pack('fff', vertexPosition.x, vertexPosition.z, vertexPosition.y))
                
            file.write(normalIdentifier)
            for index in strip:
                vertexNormal = Vector(np.clip((bm.verts[index].normal) * 127, -128, 127)) #Clamp(clip) just in case, sometimes goes over the limit of a byte
                file.write(struct.pack('bbb', int(vertexNormal.x), int(vertexNormal.z), int(vertexNormal.y)))
                file.write(ctypes.c_byte(0)) #Bone 2
                
            file.write(uvIdentifier)
            for index in strip:
                WriteUVs(UVCoordsDictionary[index], file)

            file.write(colorIdentifier)
            if (len(mesh.data.vertex_colors) > 0):
                for index in strip:
                    colours = EncodeColour(Vector(vertexColoursDict[index]))
                    file.write(struct.pack('BBBB', int(colours.x), int(colours.y), int(colours.z), int(colours.w)))
            else:
                for index in strip:
                    #Make it all white and fully opaque if no vertex colours
                    file.write(struct.pack('BBBB', 0x80, 0x80, 0x80, 0x80,))

        bm.clear
        bm.free()
        originalMesh.to_mesh(mesh.data)
        originalMesh.clear
        originalMesh.free()
        meshIndex += 1
        #Add the strip ending and pad it like is in Krome's MDLs
        file.write(stripEnd)
        rowPosition = file.tell() % 16 #0 when on a new row
        if (rowPosition == 0):
            file.write(stripLastRow)
        else:
            file.write(bytes(16 - rowPosition)) #pad out the rest of the row like the MDLs do
            file.write(stripLastRow)
    
    return meshIndex

def WriteUVs(UVCoords: Vector, file):
    #Copy it so it doesn't edit the original so its still intact when another vertex references it
    UVCoordsCopy = UVCoords.copy()
    #Vertically flip it with this method if not in the 0-1 range
    if (UVCoordsCopy.y > 1 or UVCoordsCopy.y < 0):
        UVCoordsCopy.y = (UVCoordsCopy.y * -1) + 1
    #Else Vertically flip with this
    else:
        #UVs are inverted vertically so 1 - the vector to invert the 0-1 range, eg. 0 becomes 1, 1 become 0, 0.25 becomes 0.75
        UVCoordsCopy.y = 1 - UVCoordsCopy.y
                    
    UVCoordsCopy = UVCoordsCopy * 4096
    file.write(struct.pack('hh', int(UVCoordsCopy.x), int(UVCoordsCopy.y)))
    file.write(ctypes.c_short(0)) #Bone weight
    file.write(ctypes.c_short(0)) #Bone 1

def EncodeColour(Colours):
        #Loop through each colour channel and convert them to a 0-255 range
        for b in range(4):
            if (Colours[b] == 0):
                continue
            Colours[b] = Colours[b] * 255
            #expression_if_true *if* condition *else* expression_if_false
            Colours[b] = ((Colours[b] + 1)/2) if (int(Colours[b]) & 1) else int((Colours[b]/2)+1)
        return Colours

#Credit to Zawata for his strip gen code
class StripGenerater():
    # [ (<v_idxs of face>), (<v_idxs of face>), (<v_idxs of face>)]
    face_list = None

    # {
    #   <'sorted_edge'>: <list of faces using said edge>
    # }
    edge_dict = None

    # [
    #   [<face_index>,<list of adj faces>],
    #   ...
    # ]
    conn_list = None

    # [<face_used?>, <face_used?>, <face_used?>]
    face_usage = None

    @staticmethod
    def _sort_edge(e):
        assert(len(e) == 2)
        return (min(e), max(e))

    @staticmethod
    def _add_or_append(dct, key, val):
        if key in dct:
            dct[key].append(val)
        else:
            dct[key] = [val]

    @staticmethod
    def _get_third_vert(face, edge):
        f_list = list(face)
        f_list.remove(edge[0])
        f_list.remove(edge[1])

        assert(len(f_list) == 1)
        return f_list[0]

    def __init__(self, faces):
        self.face_list = faces

        edge_dict = {}
        for i,f in enumerate(faces):
            assert(len(f) == 3)

            self._add_or_append(edge_dict, self._sort_edge(f[:2]), i)
            self._add_or_append(edge_dict, self._sort_edge(f[0::2]), i)
            self._add_or_append(edge_dict, self._sort_edge(f[1:]), i)

        self.edge_dict = edge_dict

        adj_list = [[i,0] for i in range(len(faces))]
        for _,face_list in edge_dict.items():
            if len(face_list) > 1:
                adj_list[face_list[0]][1] += 1
                adj_list[face_list[1]][1] += 1
        adj_list.sort(key=lambda x:x[1])

        self.conn_list = adj_list

        self.face_usage = [False] * len(faces)

    def get_edges_of_face(self, face):
        edges = []
        for e,f_list in self.edge_dict.items():
            if face in f_list:
                edges.append(e)

        assert(len(edges) == 3)
        return edges

    def mark_face_as_done(self, face):
        assert(not self.face_usage[face])
        self.face_usage[face] = True

    def get_next_start_face(self):
        for i,_ in self.conn_list:
            if not self.face_usage[i]:
                return i
        return None


    def get_next_face(self, edge, not_face):
        f_list = self.edge_dict[self._sort_edge(edge)]
        assert(len(f_list) in [1,2])
        for f in f_list:
            if f != not_face:
                return f
        return None

    def compute_best_strip(self, face):
        #iterate all 3 sides of the triangle
        tristrip = []
        for i,e in enumerate(self.get_edges_of_face(face)):
            tristrip.append(self.gen_strip(face, e))

        best_len = max([len(l) for l,_ in tristrip])
        for l,f_list in tristrip:
            if len(l) == best_len:
                for f in f_list:
                    self.mark_face_as_done(f)
                return l

    def gen_strip(self, face, edge):
        this_face = face
        this_edge = edge
        strip_faces = []
        tristrip = []

        tristrip.append(this_edge[0])
        tristrip.append(this_edge[1])
        while True:
            tristrip.append(self._get_third_vert(self.face_list[this_face], this_edge))
            strip_faces.append(this_face)

            this_edge = self._sort_edge(tristrip[-2:])
            this_face = self.get_next_face(this_edge, this_face)
            if not this_face or this_face in strip_faces or self.face_usage[this_face]:
                break
        #TODO: reverse generation
        return (tristrip, strip_faces)

    def gen_strips(self):
        strip_list = []

        while False in self.face_usage:
            next_face = self.get_next_start_face()
            strip_list.append(self.compute_best_strip(next_face))
        return strip_list