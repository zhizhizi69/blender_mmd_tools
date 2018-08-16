# -*- coding: utf-8 -*-
import bpy
from mathutils import Vector, Matrix, Quaternion
import numpy as np
import time

class FnSDEF():
    g_verts = {} # global cache
    g_shapekey_data = {}
    g_bone_check = {}
    SHAPEKEY_NAME = 'mmd_sdef_skinning'
    MASK_NAME = 'mmd_sdef_mask'

    def __init__(self):
        raise NotImplementedError('not allowed')

    @classmethod
    def __init_cache(cls, obj, shapekey):
        if obj.name not in cls.g_verts:
            cls.g_verts[obj.name] = cls.__find_vertices(obj)
            cls.g_bone_check[obj.name] = {}
            shapekey_co = np.zeros(len(shapekey.data) * 3, dtype=np.float32)
            shapekey.data.foreach_get('co', shapekey_co)
            shapekey_co = shapekey_co.reshape(len(shapekey.data), 3)
            cls.g_shapekey_data[obj.name] = shapekey_co
            return True
        return False

    @classmethod
    def __check_bone_update(cls, obj, bone0, bone1):
        key = bone0.name + '::' + bone1.name
        if obj.name not in cls.g_bone_check:
            cls.g_bone_check[obj.name] = {}
        if key not in cls.g_bone_check[obj.name]:
            cls.g_bone_check[obj.name][key] = (bone0.matrix.copy(), bone0.matrix.copy())
            return True
        else:
            if (bone0.matrix, bone1.matrix) == cls.g_bone_check[obj.name][key]:
                return False
            else:
                cls.g_bone_check[obj.name][key] = (bone0.matrix.copy(), bone1.matrix.copy())
                return True

    @classmethod
    def __find_vertices(cls, obj):
        vg_map = {}
        for g in obj.vertex_groups:
            vg_map[g.index] = g.name
        arm = None
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.name == 'mmd_bone_order_override':
                arm = mod.object
        assert(arm is not None)
        pose_bones = arm.pose.bones

        vertices = {}
        kb = obj.data.shape_keys.key_blocks
        if ('mmd_sdef_c' in kb and
                'mmd_sdef_r0' in kb and
                'mmd_sdef_r1' in kb):
            sdef_c = obj.data.shape_keys.key_blocks['mmd_sdef_c']
            sdef_r0 = obj.data.shape_keys.key_blocks['mmd_sdef_r0']
            sdef_r1 = obj.data.shape_keys.key_blocks['mmd_sdef_r1']
            sd = sdef_c.data
            vd = obj.data.vertices
            c = 0

            for i in range(len(sd)):
                if vd[i].co != sd[i].co:
                    bones = []
                    for g in vd[i].groups:
                        name = vg_map[g.group]
                        if name in pose_bones:
                            bones.append({'index': g.group, 'pose_bone': pose_bones[name], 'weight': g.weight})
                    bones = sorted(bones, key=lambda x: x['index'])
                    if len(bones) >= 2:
                        # preprocessing
                        w0, w1 = (bones[0]['weight'], bones[1]['weight'])
                        all_weight = w0 + w1
                        if all_weight > 0:
                            # w0 + w1 == 1
                            w0 = w0 / all_weight
                            w1 = 1 - w0
                        c = sdef_c.data[i].co
                        r0 = sdef_r0.data[i].co
                        r1 = sdef_r1.data[i].co
                        rw = r0 * w0 + r1 * w1
                        r0 = c + r0 - rw
                        r1 = c + r1 - rw

                        key = bones[0]['pose_bone'].name + '::' + bones[1]['pose_bone'].name
                        if key not in vertices:
                            vertices[key] = (bones[0]['pose_bone'], bones[1]['pose_bone'], [], [])
                        vertices[key][2].append((i, w0, w1, vd[i].co-c, (c+r0)/2, (c+r1)/2))
                        vertices[key][3].append(i)
        return vertices

    @classmethod
    def driver_function(cls, shapekey, obj_name, bulk_update, use_skip, use_scale):
        obj = bpy.data.objects[obj_name]
        cls.__init_cache(obj, shapekey)

        if not bulk_update:
            shapekey_data = shapekey.data
            if use_scale:
                # with scale
                for bone0, bone1, sdef_data, vids in cls.g_verts[obj.name].values():
                    if use_skip and not cls.__check_bone_update(obj, bone0, bone1):
                        continue
                    mat0 = bone0.matrix * bone0.bone.matrix_local.inverted()
                    mat1 = bone1.matrix * bone1.bone.matrix_local.inverted()
                    rot0 = mat0.to_quaternion()
                    rot1 = mat1.to_quaternion()
                    if rot1.dot(rot0) < 0:
                        rot1 = -rot1
                    s0, s1 = mat0.to_scale(), mat1.to_scale()
                    for vid, w0, w1, pos_c, cr0, cr1 in sdef_data:
                        mat_rot = (rot0*w0 + rot1*w1).normalized().to_matrix()
                        s = s0*w0 + s1*w1
                        mat_rot *= Matrix([[s[0],0,0], [0,s[1],0], [0,0,s[2]]])
                        shapekey_data[vid].co = mat_rot * pos_c + mat0 * cr0 * w0 + mat1 * cr1 * w1
            else:
                # default
                for bone0, bone1, sdef_data, vids in cls.g_verts[obj.name].values():
                    if use_skip and not cls.__check_bone_update(obj, bone0, bone1):
                        continue
                    mat0 = bone0.matrix * bone0.bone.matrix_local.inverted()
                    mat1 = bone1.matrix * bone1.bone.matrix_local.inverted()
                    rot0 = mat0.to_quaternion()
                    rot1 = mat1.to_quaternion()
                    if rot1.dot(rot0) < 0:
                        rot1 = -rot1
                    for vid, w0, w1, pos_c, cr0, cr1 in sdef_data:
                        mat_rot = (rot0*w0 + rot1*w1).normalized().to_matrix()
                        shapekey_data[vid].co = mat_rot * pos_c + mat0 * cr0 * w0 + mat1 * cr1 * w1
        else: # bulk update
            shapekey_data = cls.g_shapekey_data[obj.name]
            if use_scale:
                # scale & bulk update
                for bone0, bone1, sdef_data, vids in cls.g_verts[obj.name].values():
                    if use_skip and not cls.__check_bone_update(obj, bone0, bone1):
                        continue
                    mat0 = bone0.matrix * bone0.bone.matrix_local.inverted()
                    mat1 = bone1.matrix * bone1.bone.matrix_local.inverted()
                    rot0 = mat0.to_quaternion()
                    rot1 = mat1.to_quaternion()
                    if rot1.dot(rot0) < 0:
                        rot1 = -rot1
                    s0, s1 = mat0.to_scale(), mat1.to_scale()
                    def scale(mat_rot, w0, w1):
                        s = s0*w0 + s1*w1
                        return mat_rot * Matrix([[s[0],0,0], [0,s[1],0], [0,0,s[2]]])
                    shapekey_data[vids] = [scale((rot0*w0 + rot1*w1).normalized().to_matrix(), w0, w1) * pos_c + mat0 * cr0 * w0 + mat1 * cr1 * w1 for vid, w0, w1, pos_c, cr0, cr1 in sdef_data]
            else:
                # bulk update
                for bone0, bone1, sdef_data, vids in cls.g_verts[obj.name].values():
                    if use_skip and not cls.__check_bone_update(obj, bone0, bone1):
                        continue
                    mat0 = bone0.matrix * bone0.bone.matrix_local.inverted()
                    mat1 = bone1.matrix * bone1.bone.matrix_local.inverted()
                    rot0 = mat0.to_quaternion()
                    rot1 = mat1.to_quaternion()
                    if rot1.dot(rot0) < 0:
                        rot1 = -rot1
                    shapekey_data[vids] = [(rot0*w0 + rot1*w1).normalized().to_matrix() * pos_c + mat0 * cr0 * w0 + mat1 * cr1 * w1 for vid, w0, w1, pos_c, cr0, cr1 in sdef_data]
            shapekey.data.foreach_set('co', shapekey_data.reshape(3 * len(shapekey.data)))

        return 1.0 # shapkey value

    @classmethod
    def register_driver_function(cls):
        if 'mmd_sdef_driver' not in bpy.app.driver_namespace:
            bpy.app.driver_namespace['mmd_sdef_driver'] = cls.driver_function

    BENCH_LOOP=10
    @classmethod
    def __get_fastest_driver_function(cls, obj, shapkey, use_scale, use_skip):
        # warmed up
        cls.driver_function(shapkey, obj.name, bulk_update=True, use_skip=False, use_scale=use_scale)
        cls.driver_function(shapkey, obj.name, bulk_update=False, use_skip=False, use_scale=use_scale)
        # benchmark
        t = time.time()
        for i in range(cls.BENCH_LOOP):
            cls.driver_function(shapkey, obj.name, bulk_update=False, use_skip=False, use_scale=use_scale)
        default_time = time.time() - t
        t = time.time()
        for i in range(cls.BENCH_LOOP):
            cls.driver_function(shapkey, obj.name, bulk_update=True, use_skip=False, use_scale=use_scale)
        bulk_time = time.time() - t
        func = 'mmd_sdef_driver(self, obj, bulk_update={}, use_skip={}, use_scale={})'.format(default_time > bulk_time, use_skip, use_scale)
        print('FnSDEF:benchmark: default %.4f vs bulk_update %.4f => use `%s`' % (default_time, bulk_time, func))
        return func

    @classmethod
    def bind(cls, obj, use_skip=True, use_scale=False):
        # Unbind first
        cls.unbind(obj)
        # Create the shapekey for the driver
        shapekey = obj.shape_key_add(name=cls.SHAPEKEY_NAME, from_mix=False)
        cls.__init_cache(obj, obj.data.shape_keys.key_blocks[cls.SHAPEKEY_NAME])
        # Create the vertex mask for the armature modifier
        vg = obj.vertex_groups.new(name=cls.MASK_NAME)
        mask = tuple(i[0] for v in cls.g_verts[obj.name].values() for i in v[2])
        vg.add(mask, 1, 'REPLACE')
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.name == 'mmd_bone_order_override':
                # Disable deformation for SDEF vertices
                mod.vertex_group = vg.name
                mod.invert_vertex_group = True
                break
        cls.register_driver_function()
        # Add the driver to the shapekey
        f = obj.data.shape_keys.driver_add('key_blocks["'+cls.SHAPEKEY_NAME+'"].value', -1)
        f.driver.use_self = True
        f.driver.show_debug_info = False
        f.driver.type = 'SCRIPTED'
        ov = f.driver.variables.new()
        ov.name = 'obj'
        ov.type = 'SINGLE_PROP'
        ov.targets[0].id = obj
        ov.targets[0].data_path = 'name'
        # Choose the fastest driver setting with benchmark
        f.driver.expression = cls.__get_fastest_driver_function(obj, shapekey, use_skip=use_skip, use_scale=use_scale)

    @classmethod
    def unbind(cls, obj):
        if obj.data.shape_keys:
            if obj.data.shape_keys.animation_data:
                for d in obj.data.shape_keys.animation_data.drivers:
                    if cls.SHAPEKEY_NAME in d.data_path:
                        obj.data.shape_keys.driver_remove(d.data_path, -1)
            if cls.SHAPEKEY_NAME in obj.data.shape_keys.key_blocks:
                obj.shape_key_remove(obj.data.shape_keys.key_blocks[cls.SHAPEKEY_NAME])
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.vertex_group == cls.MASK_NAME:
                mod.vertex_group = ''
                mod.invert_vertex_group = False
                break
        if cls.MASK_NAME in obj.vertex_groups:
            obj.vertex_groups.remove(obj.vertex_groups[cls.MASK_NAME])
        cls.clear_cache(obj)

    @classmethod
    def clear_cache(cls, obj=None):
        if obj is not None:
            if obj.name in cls.g_verts:
                del cls.g_verts[obj.name]
            if obj.name in cls.g_shapekey_data:
                del cls.g_shapekey_data[obj.name]
            if obj.name in cls.g_bone_check:
                del cls.g_bone_check[obj.name]
        else:
            cls.g_verts = {}
            cls.g_bone_check = {}
            cls.g_shapekey_data = {}
