# -*- coding: utf-8 -*-

from bpy.props import FloatProperty
from bpy.types import Operator

import mmd_tools.core.camera as mmd_camera

class ConvertToMMDCamera(Operator):
    bl_idname = 'mmd_tools.convert_to_mmd_camera'
    bl_label = 'Convert to MMD Camera'
    bl_description = 'Create a camera rig for MMD'

    scale = FloatProperty(
        name='Scale',
        description='Scaling factor for initializing the camera',
        default=1.0,
        )

    def invoke(self, context, event):
        vm = context.window_manager
        return vm.invoke_props_dialog(self)

    def execute(self, context):
        mmd_camera.MMDCamera.convertToMMDCamera(context.active_object, self.scale)
        return {'FINISHED'}
