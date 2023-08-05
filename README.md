# MDL2-Blender-Plugin
Plugin for blender to import and export MDL2 from Ty the Tasmanian Tiger 1

# Installation
To install the plugin just put the mdl2 folder in the blender add-ons folder usually located at this directory C:\Users\\*YourPCsName*\AppData\Roaming\Blender Foundation\Blender\2.93\scripts\addons, then in blender go to Edit>Preferences>Add-ons then search for the mdl2 tool plugin and enable it, now there should be new import and export options. To quickly get to the roaming folder you can just type %appdata% into the search bar near the start menu.

# Setting the Texture and Collision
The exporter for the texture name uses the material name, not the name of the texture in the texture node inside of the material, if you're adding a texture to be used by the exported model all you need is at least a empty material with its name as the texture's name (excluding the .dds part) or a name of one in global.mad. Keep in mind that the collision property overrides the texture name and with the exporter they take priority over the name on the material.

There is also a custom collision panel to be able to easily select collision types, and even supports custom ones that you can add to the global.mad file

![CollisionPanel](CollisionPanel.PNG?raw=true) ![CollisionPanel](CollisionTypes.PNG?raw=true)
