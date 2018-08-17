import bpy
from bpy.types import Operator
from mmd_tools.core.sdef import FnSDEF

class BindSDEF(Operator):
    bl_idname = 'mmd_tools.bind_sdef'
    bl_label = 'Bind SDEF Driver'
    bl_description = 'Bind MMD SDEF data of active object'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    mode = bpy.props.EnumProperty(
        name='Mode',
        description='Select mode',
        items = [
            ('2', 'Bulk', 'Speed up with numpy (may be slower in some cases)', 2),
            ('1', 'Normal', 'Normal mode', 1),
            ('0', '- Auto -', 'Select best mode by benchmark result', 0),
            ],
        default='0',
        )
    use_skip = bpy.props.BoolProperty(
        name='Skip',
        description='Skip when the bones are not moving',
        default=True,
        )
    use_scale = bpy.props.BoolProperty(
        name='Scale',
        description='Support bone scaling (slow)',
        default=False,
        )

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
                    (None, False, True)[int(self.mode)],
                    use_skip=self.use_skip, use_scale=self.use_scale)
        return {'FINISHED'}

class UnbindSDEF(Operator):
    bl_idname = 'mmd_tools.unbind_sdef'
    bl_label = 'Unbind SDEF Driver'
    bl_description = 'Unbind MMD SDEF data of active object'
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
