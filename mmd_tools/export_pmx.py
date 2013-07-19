# -*- coding: utf-8 -*-
from . import pmx
from . import bpyutils

import collections
import os
import copy
import logging

import mathutils
import bpy
import bmesh


class __PmxExporter:
    TO_PMX_MATRIX = mathutils.Matrix([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0]])

    def __init__(self):
        self.__model = None
        self.__targetMesh = None

    @staticmethod
    def flipUV_V(uv):
        u, v = uv
        return [u, 1.0-v]

    @staticmethod
    def __getVertexGroupIndexToPmxBoneIndexMap(meshObj, nameMap):
        """ Create the dictionary to map vertex group indices to bone indices of the pmx.model instance.
        @param meshObj the object which has the target vertex groups.
        @param nameMap the dictionary to map Blender bone name to bone indices of the pmx.model instance.
        """
        r = {}
        for i in meshObj.vertex_groups:
            r[i.index] = nameMap.get(i.name, -1)
        return r

    @staticmethod
    def __getVerticesTable(mesh, vertexGroupToBoneIndexMap):
        """ Create the list which has pmx.Vertex instances.
        @param vertexGroupToBoneIndexMap the dictionary to map vertex group indices to bone indices of the pmx.model instance.
        """
        r = []
        for bv in mesh.vertices:
            pv = pmx.Vertex()
            pv.co = bv.co
            pv.normal = bv.normal * -1
            pv.uv = None

            t = len(bv.groups)
            if t == 0:
                weight = pmx.BoneWeight()
                weight.type = pmx.BoneWeight.BDEF1
                weight.bones = [-1]
                pv.weight = weight
            elif t == 1:
                weight = pmx.BoneWeight()
                weight.type = pmx.BoneWeight.BDEF1
                weight.bones = [vertexGroupToBoneIndexMap[bv.groups[0].group]]
                pv.weight = weight
            elif t == 2:
                vg1, vg2 = bv.groups
                weight = pmx.BoneWeight()
                weight.type = pmx.BoneWeight.BDEF2
                weight.bones = [vertexGroupToBoneIndexMap[vg1.group], vertexGroupToBoneIndexMap[vg2.group]]
                weight.weights = [vg1.weight]
                pv.weight = weight
            else:
                weight = pmx.BoneWeight()
                weight.type = pmx.BoneWeight.BDEF4
                weight.bones = [-1, -1, -1, -1]
                weight.weights = [0.0, 0.0, 0.0, 0.0]
                for i in range(min(len(bv.groups), 4)):
                    vg = bv.groups[i]
                    weight.bones[i] = vertexGroupToBoneIndexMap[vg.group]
                    weight.weights[i] = vg.weight
                pv.weight = weight
            r.append(pv)
        return r

    @staticmethod
    def __getFaceTable(mesh, verticesTable):
        r = []
        for f, uv in zip(mesh.tessfaces, mesh.tessface_uv_textures.active.data):
            if len(f.vertices) != 3:
                raise Exception
            t = []
            for i in f.vertices:
                t.append(verticesTable[i])
            r.append((f, uv, t))
        return r

    @staticmethod
    def __convertFaceUVToVertexUV(vertex, uv, cloneVertexMap):
        if vertex.uv is None:
            vertex.uv = uv
        elif (vertex.uv[0] - uv[0])**2 + (vertex.uv[1] - uv[1])**2 > 0.0001:
            for i in cloneVertexMap.get(vertex, []):
                if (i.uv[0] - uv[0])**2 + (i.uv[1] - uv[1])**2 < 0.0001:
                    return i
            n = copy.deepcopy(vertex)
            n.uv = uv
            if vertex not in cloneVertexMap:
                cloneVertexMap[vertex] = [n]
            else:
                cloneVertexMap[vertex].append(n)
            return n
        return vertex

    def __exportFaces(self, vertexTable, faceTable):
        materialIndexDict = collections.defaultdict(list)
        cloneVertexMap = {}
        for f, uv, vertices in faceTable:
            vertices[0] = self.__convertFaceUVToVertexUV(vertices[0], self.flipUV_V(uv.uv1), cloneVertexMap)
            vertices[1] = self.__convertFaceUVToVertexUV(vertices[1], self.flipUV_V(uv.uv2), cloneVertexMap)
            vertices[2] = self.__convertFaceUVToVertexUV(vertices[2], self.flipUV_V(uv.uv3), cloneVertexMap)

        verticesSet = set()
        for f, uv, vertices in faceTable:
            verticesSet.update(set(vertices))

        self.__model.vertices = list(verticesSet)
        invertMap = {}
        for i, v in enumerate(self.__model.vertices):
            invertMap[v] = i
        for f, uv, vertices in faceTable:
            v1 = invertMap[vertices[0]]
            v2 = invertMap[vertices[1]]
            v3 = invertMap[vertices[2]]
            materialIndexDict[f.material_index].append([v1, v2, v3])

        # make the map from vertex indices of Blender to them of pmx.
        vertexIndexMap = {}
        for i, v in enumerate(vertexTable):
            vertexIndexMap[i] = [invertMap[v]]
            if v in cloneVertexMap:
                for c in cloneVertexMap[v]:
                    vertexIndexMap[i].append(invertMap[c])

        for i in sorted(materialIndexDict.keys()):
            self.__model.faces.extend(materialIndexDict[i])
        return (materialIndexDict, vertexIndexMap)

    def __exportTexture(self, texture):
        if not isinstance(texture, bpy.types.ImageTexture):
            return -1
        t = pmx.Texture()
        t.path = texture.image.filepath
        self.__model.textures.append(t)
        if not os.path.isfile(t.path):
            logging.warning('  The texture file does not exist: %s', t.path)
        return len(self.__model.textures) - 1

    def __exportMaterials(self, materialIndexDict):
        mesh = self.__targetMesh
        textureList = []
        for m_index, i in enumerate(mesh.materials):
            num_faces = len(materialIndexDict[m_index])
            if num_faces == 0:
                continue
            p_mat = pmx.Material()
            p_mat.name = i.name
            p_mat.name_e = i.name
            p_mat.diffuse = list(i.diffuse_color) + [i.alpha]
            p_mat.ambient = i.mmd_ambient_color or [0.5, 0.5, 0.5]
            p_mat.specular = list(i.specular_color) + [i.specular_alpha]
            p_mat.edge_color = [0.25, 0.3, 0.5, 0.5]
            p_mat.vertex_count = num_faces * 3
            #p_mat.is_double_sided = True
            if len(i.texture_slots) > 0 and i.texture_slots[0] is not None:
                tex = i.texture_slots[0].texture
                index = -1
                if tex not in textureList:
                    index = self.__exportTexture(tex)
                    textureList.append(tex)
                else:
                    index = textureList.index(tex)
                p_mat.texture = index
                p_mat.diffuse[3] = 1.0 # Set the alpha value to 1.0 if the material has textures.
            self.__model.materials.append(p_mat)

    def __exportBones(self):
        """ Export bones.
        @return the dictionary to map Blender bone names to bone indices of the pmx.model instance.
        """
        arm = self.__armature
        boneMap = {}
        pmx_bones = []
        pose_bones = arm.pose.bones
        world_mat = arm.matrix_world
        r = {}
        with bpyutils.edit_object(arm) as data:
            for bone in data.edit_bones:
                pmx_bone = pmx.Bone()
                p_bone = pose_bones[bone.name]
                if p_bone.is_mmd_shadow_bone:
                    continue
                if p_bone.mmd_bone.name_j != '':
                    pmx_bone.name = p_bone.mmd_bone.name_j
                else:
                    pmx_bone.name = bone.name
                pmx_bone_e = p_bone.mmd_bone.name_e or ''
                pmx_bone.location = world_mat * mathutils.Vector(bone.head) * self.__scale * self.TO_PMX_MATRIX
                pmx_bone.parent = bone.parent
                pmx_bone.visible = not p_bone.bone.hide
                pmx_bone.isMovable = not all(p_bone.lock_location)
                pmx_bone.isRotatable = not all(p_bone.lock_rotation)
                pmx_bones.append(pmx_bone)
                boneMap[bone] = pmx_bone
                r[bone.name] = len(pmx_bones) - 1

                if len(bone.children) == 0 and not p_bone.mmd_bone.is_tip:
                    pmx_tip_bone = pmx.Bone()
                    pmx_tip_bone.name = 'tip_' + bone.name
                    pmx_tip_bone.location =  world_mat * mathutils.Vector(bone.tail) * self.__scale * self.TO_PMX_MATRIX
                    pmx_tip_bone.parent = bone
                    pmx_bones.append(pmx_tip_bone)
                    pmx_bone.displayConnection = pmx_tip_bone
                elif len(bone.children) > 0:
                    pmx_bone.displayConnection = list(filter(lambda x: not pose_bones[x.name].is_mmd_shadow_bone, sorted(bone.children, key=lambda x: 1 if pose_bones[x.name].mmd_bone.is_tip else 0)))[0]

            for i in pmx_bones:
                if i.parent is not None:
                    i.parent = pmx_bones.index(boneMap[i.parent])
                    logging.debug('the parent of %s: %s', i.name, i.parent)
                if isinstance(i.displayConnection, pmx.Bone):
                    i.displayConnection = pmx_bones.index(i.displayConnection)
                elif isinstance(i.displayConnection, bpy.types.EditBone):
                    i.displayConnection = pmx_bones.index(boneMap[i.displayConnection])

            self.__model.bones = pmx_bones
        return r

    def __exportIKLinks(self, pose_bone, pmx_bones, bone_map, ik_links, count):
        if count <= 0:
            return ik_links

        logging.debug('    Create IK Link for %s', pose_bone.name)
        ik_link = pmx.IKLink()
        ik_link.target = bone_map[pose_bone.name]
        if pose_bone.use_ik_limit_x or pose_bone.use_ik_limit_y or pose_bone.use_ik_limit_z:
            minimum = []
            maximum = []
            if pose_bone.use_ik_limit_x:
                minimum.append(-pose_bone.ik_max_x)
                maximum.append(-pose_bone.ik_min_x)
            else:
                minimum.append(0.0)
                maximum.append(0.0)

            if pose_bone.use_ik_limit_y:
                minimum.append(pose_bone.ik_min_y)
                maximum.append(pose_bone.ik_max_y)
            else:
                minimum.append(0.0)
                maximum.append(0.0)

            if pose_bone.use_ik_limit_z:
                minimum.append(pose_bone.ik_min_z)
                maximum.append(pose_bone.ik_max_z)
            else:
                minimum.append(0.0)
                maximum.append(0.0)
            ik_link.minimumAngle = minimum
            ik_link.maximumAngle = maximum

        if pose_bone.parent is not None:
            return self.__exportIKLinks(pose_bone.parent, pmx_bones, bone_map, ik_links + [ik_link], count - 1)
        else:
            return ik_link + [ik_link]


    def __exportIK(self, bone_map):
        """ Export IK constraints
         @param bone_map the dictionary to map Blender bone names to bone indices of the pmx.model instance.
        """
        pmx_bones = self.__model.bones
        arm = self.__armature
        pose_bones = arm.pose.bones
        for bone in pose_bones:
            for c in bone.constraints:
                if c.type == 'IK':
                    logging.debug('  Found IK constraint.')
                    ik_pose_bone = pose_bones[c.subtarget]
                    if ik_pose_bone.mmd_shadow_bone_type == 'IK_PROXY':
                        ik_bone_index = bone_map[ik_pose_bone.parent.name]
                        logging.debug('  Found IK proxy bone: %s -> %s', ik_pose_bone.name, ik_pose_bone.parent.name)
                    else:
                        ik_bone_index = bone_map[c.subtarget]

                    pmx_ik_bone = pmx_bones[ik_bone_index]
                    pmx_ik_bone.isIK = True
                    pmx_ik_bone.transform_order += 1
                    pmx_ik_bone.target = pmx_bones[bone_map[bone.name]].displayConnection
                    pmx_ik_bone.ik_links = self.__exportIKLinks(bone, pmx_bones, bone_map, [], c.chain_count)



    def __exportVertexMorphs(self, obj, vertexIndexMap):
        """ Export VertexMorphs
        @param obj the target mesh object
        @param vertexIndexMap the dictionary to map vertex indices in blender to vertex indices in pmx.
        """
        if obj.data.shape_keys is None:
            logging.info('%s has no shape keys', obj.name)
            return
        baseShape = obj.data.shape_keys.reference_key
        for shapeKey in obj.data.shape_keys.key_blocks:
            morph = pmx.VertexMorph(shapeKey.name, '', 4)
            for i, v in enumerate(shapeKey.data):
                offset = (v.co - baseShape.data[i].co)
                if offset.length > 0.001:
                    for j in vertexIndexMap[i]:
                        mo = pmx.VertexMorphOffset()
                        mo.index = j
                        mo.offset = offset * self.TO_PMX_MATRIX * self.__scale
                        morph.offsets.append(mo)
            self.__model.morphs.append(morph)



    @staticmethod
    def __triangulate(mesh):
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        bm.free()

    def execute(self, filepath, **args):
        self.__model = pmx.Model()
        self.__model.name = 'test'
        self.__model.name_e = 'test eng'

        self.__model.comment = 'exported by mmd_tools'

        target = None
        arm = None
        for i in bpy.context.selected_objects:
            if i.type == 'MESH':
                target = i
            elif i.type == 'ARMATURE':
                arm = i

        target = args.get('mesh', target)
        self.__armature = args.get('armature', arm)
        self.__scale = 1.0/float(args.get('scale', 0.2))



        mesh = target.to_mesh(bpy.context.scene, True, 'PREVIEW', False)
        mesh.transform(target.matrix_world)
        mesh.transform(self.TO_PMX_MATRIX*self.__scale)
        self.__triangulate(mesh)
        mesh.update(calc_tessface=True)

        self.__targetMesh = mesh


        nameMap = self.__exportBones()
        self.__exportIK(nameMap)
        vgi_to_pbi = self.__getVertexGroupIndexToPmxBoneIndexMap(target, nameMap)
        verticesTable = self.__getVerticesTable(mesh, vgi_to_pbi)
        facesTable = self.__getFaceTable(mesh, verticesTable)
        materialIndexDict, vertexIndexMap = self.__exportFaces(verticesTable, facesTable)
        self.__exportVertexMorphs(target, vertexIndexMap)
        self.__exportMaterials(materialIndexDict)
        pmx.save(filepath, self.__model)

def export(filepath, **kwargs):
    exporter = __PmxExporter()
    exporter.execute(filepath, **kwargs)