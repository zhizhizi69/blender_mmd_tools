# -*- coding: utf-8 -*-

import bpy
import math

class MMDCamera:
    def __init__(self, obj):
        if obj.type != 'EMPTY':
            if obj.parent is None or obj.type != 'CAMERA':
                raise ValueError('%s is not MMDCamera'%str(obj))
            obj = obj.parent
        if obj.type == 'EMPTY' and obj.mmd_type == 'CAMERA':
            self.__emptyObj = obj
        else:
            raise ValueError('%s is not MMDCamera'%str(obj))


    @staticmethod
    def isMMDCamera(obj):
        if obj.type != 'EMPTY':
            if obj.parent is None or obj.type != 'CAMERA':
                return False
            obj = obj.parent
        return obj.type == 'EMPTY' and obj.mmd_type == 'CAMERA'

    @staticmethod
    def convertToMMDCamera(cameraObj, scale=1.0):
        if MMDCamera.isMMDCamera(cameraObj):
            return MMDCamera(cameraObj)

        empty = bpy.data.objects.new(name='MMD_Camera', object_data=None)
        bpy.context.scene.objects.link(empty)

        cameraObj.parent = empty
        cameraObj.data.dof_object = empty
        cameraObj.data.sensor_fit = 'VERTICAL'
        cameraObj.data.lens_unit = 'MILLIMETERS' # MILLIMETERS, FOV
        cameraObj.data.ortho_scale = 25*scale
        cameraObj.data.clip_end = 500*scale
        cameraObj.data.draw_size = 5*scale
        cameraObj.location = (0, -45*scale, 0)
        cameraObj.rotation_mode = 'XYZ'
        cameraObj.rotation_euler = (math.radians(90), 0, 0)
        cameraObj.lock_location = (True, False, True)
        cameraObj.lock_rotation = (True, True, True)
        cameraObj.lock_scale = (True, True, True)

        empty.location = (0, 0, 10*scale)
        empty.rotation_mode = 'YXZ'
        empty.empty_draw_size = 5*scale
        empty.lock_scale = (True, True, True)
        empty.mmd_type = 'CAMERA'
        empty.mmd_camera.angle = math.radians(30)
        empty.mmd_camera.persp = True
        return MMDCamera(empty)

    @staticmethod
    def newMMDCameraAnimation(cameraObj, cameraTarget=None, scale=1.0):
        if cameraTarget is None:
            cameraTarget = cameraObj

        scene = bpy.context.scene
        mmd_cam = bpy.data.objects.new(name='Camera', object_data=bpy.data.cameras.new('Camera'))
        scene.objects.link(mmd_cam)
        MMDCamera.convertToMMDCamera(mmd_cam, scale=scale)
        mmd_cam_root = mmd_cam.parent

        action_name = mmd_cam_root.name
        parent_action = bpy.data.actions.new(name=action_name)
        distance_action = bpy.data.actions.new(name=action_name+'_dis')

        fcurves = []
        for i in range(3):
            fcurves.append(parent_action.fcurves.new(data_path='location', index=i))
        for i in range(3):
            fcurves.append(parent_action.fcurves.new(data_path='rotation_euler', index=i))
        fcurves.append(distance_action.fcurves.new(data_path='location', index=1))
        fcurves.append(parent_action.fcurves.new(data_path='mmd_camera.angle'))

        frame_start, frame_end, frame_current = scene.frame_start, scene.frame_end+1, scene.frame_current
        frame_count = frame_end - frame_start
        for c in fcurves:
            c.keyframe_points.add(frame_count)

        from math import atan
        from mathutils import Matrix

        render = scene.render
        factor = (render.resolution_y*render.pixel_aspect_y)/(render.resolution_x*render.pixel_aspect_x)

        matrix_rotation = Matrix(([1,0,0,0], [0,0,1,0], [0,-1,0,0], [0,0,0,1]))
        for f in range(frame_start, frame_end):
            scene.frame_set(f)
            cam_matrix_world = cameraObj.matrix_world
            cam_target_loc = cam_matrix_world.translation
            if cameraTarget:
                cam_target_loc = cameraTarget.matrix_world.translation

            #assert(cameraObj.data.type != 'ORTHO') # TODO 'ORTHO' type animation
            tan_val = cameraObj.data.sensor_height/cameraObj.data.lens/2
            if cameraObj.data.sensor_fit != 'VERTICAL':
                ratio = cameraObj.data.sensor_width/cameraObj.data.sensor_height
                if cameraObj.data.sensor_fit == 'HORIZONTAL':
                    tan_val *= factor*ratio
                else: # cameraObj.data.sensor_fit == 'AUTO'
                    tan_val *= min(ratio, factor*ratio)

            values = list(cam_target_loc)
            values += list((cam_matrix_world * matrix_rotation).to_euler(mmd_cam_root.rotation_mode))
            values.append(-(cam_matrix_world.translation - cam_target_loc).length)
            values.append(2*atan(tan_val))
            for c, v in zip(fcurves, values):
                c.keyframe_points[f-frame_start].co = (f, v)

        for c in fcurves:
            c.update()

        mmd_cam_root.animation_data_create().action = parent_action
        mmd_cam.animation_data_create().action = distance_action
        scene.frame_set(frame_current)
        return MMDCamera(mmd_cam_root)

    def object(self):
        return self.__emptyObj

    def camera(self):
        for i in self.__emptyObj.children:
            if i.type == 'CAMERA':
                return i
        raise Exception
