import bpy
from bpy.props import *
from bpy.types import Operator
from mmd_tools.core.sdef import FnSDEF

class BindSDEF(Operator):
    bl_idname = 'mmd_tools.bind_sdef'
    bl_label = 'Bind SDEF Driver'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    use_skip = BoolProperty(name='Skip',
                            description='Skip when the bones are not moving',
                            default=True)
    use_scale = BoolProperty(name='Scale',
                            description='Support bone scaling(slow)',
                            default=False)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is not None and obj.type == 'MESH':
            for m in obj.modifiers:
                if m.type == 'ARMATURE':
                    return True
        return False

    def invoke(self, context, event):
        vm = context.window_manager
        return vm.invoke_props_dialog(self)

    def execute(self, context):
        FnSDEF.bind(context.active_object,
                    use_skip=self.use_skip, use_scale=self.use_scale)
        return {'FINISHED'}

class UnbindSDEF(Operator):
    bl_idname = 'mmd_tools.unbind_sdef'
    bl_label = 'Unbind SDEF Driver'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is not None and obj.type == 'MESH':
            for m in obj.modifiers:
                if m.type == 'ARMATURE':
                    return True
        return False

    def execute(self, context):
        FnSDEF.unbind(context.active_object)
        return {'FINISHED'}
