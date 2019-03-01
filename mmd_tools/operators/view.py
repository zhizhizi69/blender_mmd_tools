# -*- coding: utf-8 -*-

import re
import bpy
from bpy.types import Operator
from mathutils import Matrix

from mmd_tools import register_wrap
from mmd_tools.bpyutils import matmul

@register_wrap
class SetGLSLShading(Operator):
    bl_idname = 'mmd_tools.set_glsl_shading'
    bl_label = 'GLSL View'
    bl_description = 'Use GLSL shading with additional lighting'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.mmd_tools.reset_shading()
        if bpy.app.version >= (2, 80, 0):
            shading = context.area.spaces[0].shading
            shading.light = 'STUDIO'
            shading.color_type = 'TEXTURE'
            return {'FINISHED'}

        for i in filter(lambda x: x.type == 'MESH', context.scene.objects):
            for s in i.material_slots:
                if s.material is None:
                    continue
                s.material.use_shadeless = False
        if len(list(filter(lambda x: x.is_mmd_glsl_light, context.scene.objects))) == 0:
            light = bpy.data.objects.new('Hemi', bpy.data.lamps.new('Hemi', 'HEMI'))
            light.is_mmd_glsl_light = True
            light.hide = True
            context.scene.objects.link(light)

        context.area.spaces[0].viewport_shade='TEXTURED'
        context.scene.game_settings.material_mode = 'GLSL'
        return {'FINISHED'}

@register_wrap
class SetShadelessGLSLShading(Operator):
    bl_idname = 'mmd_tools.set_shadeless_glsl_shading'
    bl_label = 'Shadeless GLSL View'
    bl_description = 'Use only toon shading'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.mmd_tools.reset_shading()
        if bpy.app.version >= (2, 80, 0):
            shading = context.area.spaces[0].shading
            shading.light = 'FLAT'
            shading.color_type = 'TEXTURE'
            return {'FINISHED'}

        for i in filter(lambda x: x.type == 'MESH', context.scene.objects):
            for s in i.material_slots:
                if s.material is None:
                    continue
                s.material.use_shadeless = True
        try:
            context.scene.display_settings.display_device = 'None'
        except TypeError:
            pass # Blender was built without OpenColorIO:

        context.area.spaces[0].viewport_shade='TEXTURED'
        context.scene.game_settings.material_mode = 'GLSL'
        return {'FINISHED'}

@register_wrap
class ResetShading(Operator):
    bl_idname = 'mmd_tools.reset_shading'
    bl_label = 'Reset View'
    bl_description = 'Reset to default Blender shading'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if bpy.app.version >= (2, 80, 0):
            context.scene.render.engine = 'BLENDER_EEVEE'
            shading = context.area.spaces[0].shading
            shading.type = 'SOLID'
            shading.light = 'STUDIO'
            shading.color_type = 'MATERIAL'
            shading.show_object_outline = False
            shading.show_backface_culling = True
            return {'FINISHED'}

        context.scene.render.engine = 'BLENDER_RENDER'
        for i in filter(lambda x: x.type == 'MESH', context.scene.objects):
            for s in i.material_slots:
                if s.material is None:
                    continue
                s.material.use_shadeless = False
                s.material.use_nodes = False

        for i in filter(lambda x: x.is_mmd_glsl_light, context.scene.objects):
            context.scene.objects.unlink(i)

        try:
            context.scene.display_settings.display_device = 'sRGB'
        except TypeError:
            pass
        context.area.spaces[0].viewport_shade='SOLID'
        context.area.spaces[0].show_backface_culling = True
        context.scene.game_settings.material_mode = 'MULTITEXTURE'
        return {'FINISHED'}

@register_wrap
class FlipPose(Operator):
    bl_idname = 'mmd_tools.flip_pose'
    bl_label = 'Flip Pose'
    bl_description = 'Apply the current pose of selected bones to matching bone on opposite side of X-Axis.'
    bl_options = {'REGISTER', 'UNDO'}

    # https://docs.blender.org/manual/en/dev/rigging/armatures/bones/editing/naming.html
    __LR_REGEX = [
        {"re": re.compile(r'^(.+)(RIGHT|LEFT)(\.\d+)?$', re.IGNORECASE), "lr": 1},
        {"re": re.compile(r'^(.+)([\.\- _])(L|R)(\.\d+)?$', re.IGNORECASE), "lr": 2},
        {"re": re.compile(r'^(LEFT|RIGHT)(.+)$', re.IGNORECASE), "lr": 0},
        {"re": re.compile(r'^(L|R)([\.\- _])(.+)$', re.IGNORECASE), "lr": 0},
        {"re": re.compile(r'^(.+)(左|右)(\.\d+)?$'), "lr": 1},
        {"re": re.compile(r'^(左|右)(.+)$'), "lr": 0},
        ]
    __LR_MAP = {
        "RIGHT": "LEFT",
        "Right": "Left",
        "right": "left",
        "LEFT": "RIGHT",
        "Left": "Right",
        "left": "right",
        "L": "R",
        "l": "r",
        "R": "L",
        "r": "l",
        "左": "右",
        "右": "左",
        }
    @classmethod
    def flip_name(cls, name):
        for regex in cls.__LR_REGEX:
            match = regex["re"].match(name)
            if match:
                groups = match.groups()
                lr = groups[regex["lr"]]
                if lr in cls.__LR_MAP:
                    flip_lr = cls.__LR_MAP[lr]
                    name = ''
                    for i, s in enumerate(groups):
                        if i == regex["lr"]:
                            name += flip_lr
                        elif s:
                            name += s
                    return name
        return ''

    @staticmethod
    def __cmul(vec1, vec2):
        return type(vec1)([x * y for x, y in zip(vec1, vec2)])

    @staticmethod
    def __matrix_compose(loc, rot, scale):
        return matmul(matmul(Matrix.Translation(loc), rot.to_matrix().to_4x4()),
                    Matrix([(scale[0],0,0,0), (0,scale[1],0,0), (0,0,scale[2],0), (0,0,0,1)]))

    @classmethod
    def __flip_pose(cls, matrix_basis, bone_src, bone_dest):
        from mathutils import Quaternion
        m = bone_dest.bone.matrix_local.to_3x3().transposed()
        mi = bone_src.bone.matrix_local.to_3x3().transposed().inverted() if bone_src != bone_dest else m.inverted()
        loc, rot, scale = matrix_basis.decompose()
        loc = cls.__cmul(matmul(mi, loc), (-1, 1, 1))
        rot = cls.__cmul(Quaternion(matmul(mi, rot.axis), rot.angle).normalized(), (1, 1, -1, -1))
        bone_dest.matrix_basis = cls.__matrix_compose(matmul(m, loc), Quaternion(matmul(m, rot.axis), rot.angle).normalized(), scale)

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                    context.active_object.type == 'ARMATURE' and
                    context.active_object.mode == 'POSE')

    def execute(self, context):
        pose_bones = context.active_object.pose.bones
        for b, mat in [(x, x.matrix_basis.copy()) for x in context.selected_pose_bones]:
            self.__flip_pose(mat, b, pose_bones.get(self.flip_name(b.name), b))
        return {'FINISHED'}

