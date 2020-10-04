#
# glTFExporter
#

import base64
import json
import numpy
import vtk
import vtk.util.numpy_support
import slicer

class glTFExporter:
  """
  Export a subset of mrml data to glTF 1.0 format (https://www.khronos.org/gltf).

  This could be factored to a separate module, but it's developed
  here for simplicity of reloading and debugging.

  This work was partially funded by NIH grant 3P41RR013218.
  """
  def __init__(self,mrmlScene):
    self.mrmlScene = mrmlScene
    self.sceneDefaults()
    self.buffers = {} # binary data for later access

  def export(self, options={}):
    """
    Returns a json document string in the format supported by glTF
    and described here: https://github.com/KhronosGroup/glTF/blob/master/specification/1.0/README.md
    some defaults and structure pulled from the Box sample at https://github.com/KhronosGroup/glTF-Sample-Models

    options includes:
      nodeFilter : a callable that returns true if the node should be included in the export
      targetFiberCount : can be None for no limit or an integer
      fiberMode : can be "lines" or "tubes"
      modelMode : can be "lines" or "triangles"
    """

    self.nodeFilter= options['nodeFilter'] if 'nodeFilter' in options else lambda node: True
    self.targetFiberCount = options['targetFiberCount'] if "targetFiberCount" in options else None
    self.fiberMode = options['fiberMode'] if "fiberMode" in options else "tubes"
    # TODO: sort out line mode for fibers - use tubes for now
    # self.modelMode = "lines" if self.fiberMode == "lines" else "triangles"
    self.modelMode = "triangles"


    if self.fiberMode not in ["lines", "tubes"]:
      print('Bad fiber mode %s' % self.fiberMode)
      return None

    if self.modelMode not in ["lines", "triangles"]:
      print('Bad model mode %s' % self.modelMode)
      return None

    # things specific to each model node
    models = slicer.util.getNodes('vtkMRMLModelNode*')
    for model in models.values():
      if self.nodeFilter(model):
        self.addModel(model)

    # things specific to each fiber node
    fibers = slicer.util.getNodes('vtkMRMLFiberBundleNode*')
    for fiber in fibers.values():
      if self.nodeFilter(fiber):
        model = self.fiberToModel(fiber)
        if model:
          self.addModel(model)

    return(json.dumps(self.glTF))

  def sceneDefaults(self):
    self.glTF = {
      "scene": "defaultScene",
      "scenes": {
        "defaultScene": {
          "nodes": []
        }
      },
      "extensionsUsed": [
        "KHR_materials_common"
      ],
      "asset": {
        "generator": "SlicerWeb.glTFExporter",
        "premultipliedAlpha": False,
        "profile": {
          "api": "WebGL",
          "version": "1.0"
        },
        "version": "1.1"
      },
      # these are populated by addModel
      "nodes": {},
      "meshes": {},
      "accessors": {},
      "buffers": {},
      "bufferViews": {},
      "materials": {},
    }
    self.glTF["animations"] = {}
    self.glTF["skins"] = {}
    self.glTF["shaders"] = {
        "FragmentShader": {
            "type": 35632,
            "uri": "data:text/plain;base64,cHJlY2lzaW9uIGhpZ2hwIGZsb2F0Owp2YXJ5aW5nIHZlYzMgdl9ub3JtYWw7CnVuaWZvcm0gdmVjNCB1X2RpZmZ1c2U7CnVuaWZvcm0gdmVjNCB1X3NwZWN1bGFyOwp1bmlmb3JtIGZsb2F0IHVfc2hpbmluZXNzOwp2b2lkIG1haW4odm9pZCkgewp2ZWMzIG5vcm1hbCA9IG5vcm1hbGl6ZSh2X25vcm1hbCk7CnZlYzQgY29sb3IgPSB2ZWM0KDAuLCAwLiwgMC4sIDAuKTsKdmVjNCBkaWZmdXNlID0gdmVjNCgwLiwgMC4sIDAuLCAxLik7CnZlYzQgc3BlY3VsYXI7CmRpZmZ1c2UgPSB1X2RpZmZ1c2U7CnNwZWN1bGFyID0gdV9zcGVjdWxhcjsKZGlmZnVzZS54eXogKj0gbWF4KGRvdChub3JtYWwsdmVjMygwLiwwLiwxLikpLCAwLik7CmNvbG9yLnh5eiArPSBkaWZmdXNlLnh5ejsKY29sb3IgPSB2ZWM0KGNvbG9yLnJnYiAqIGRpZmZ1c2UuYSwgZGlmZnVzZS5hKTsKZ2xfRnJhZ0NvbG9yID0gY29sb3I7Cn0K"
        },
        "VertexShader": {
            "type": 35633,
            "uri": "data:text/plain;base64,cHJlY2lzaW9uIGhpZ2hwIGZsb2F0OwphdHRyaWJ1dGUgdmVjMyBhX3Bvc2l0aW9uOwphdHRyaWJ1dGUgdmVjMyBhX25vcm1hbDsKdmFyeWluZyB2ZWMzIHZfbm9ybWFsOwp1bmlmb3JtIG1hdDMgdV9ub3JtYWxNYXRyaXg7CnVuaWZvcm0gbWF0NCB1X21vZGVsVmlld01hdHJpeDsKdW5pZm9ybSBtYXQ0IHVfcHJvamVjdGlvbk1hdHJpeDsKdm9pZCBtYWluKHZvaWQpIHsKdmVjNCBwb3MgPSB1X21vZGVsVmlld01hdHJpeCAqIHZlYzQoYV9wb3NpdGlvbiwxLjApOwp2X25vcm1hbCA9IHVfbm9ybWFsTWF0cml4ICogYV9ub3JtYWw7CmdsX1Bvc2l0aW9uID0gdV9wcm9qZWN0aW9uTWF0cml4ICogcG9zOwp9Cg=="
        }
    }
    self.glTF["techniques"] = {
        "technique0": {
            "attributes": {
                "a_normal": "normal",
                "a_position": "position"
            },
            "parameters": {
                "diffuse": {
                    "type": 35666
                },
                "modelViewMatrix": {
                    "semantic": "MODELVIEW",
                    "type": 35676
                },
                "normal": {
                    "semantic": "NORMAL",
                    "type": 35665
                },
                "normalMatrix": {
                    "semantic": "MODELVIEWINVERSETRANSPOSE",
                    "type": 35675
                },
                "position": {
                    "semantic": "POSITION",
                    "type": 35665
                },
                "projectionMatrix": {
                    "semantic": "PROJECTION",
                    "type": 35676
                },
                "shininess": {
                    "type": 5126
                },
                "specular": {
                    "type": 35666
                }
            },
            "program": "program_0",
            "states": {
                "enable": [
                    2929,
                    2884
                ]
            },
            "uniforms": {
                "u_diffuse": "diffuse",
                "u_modelViewMatrix": "modelViewMatrix",
                "u_normalMatrix": "normalMatrix",
                "u_projectionMatrix": "projectionMatrix",
                "u_shininess": "shininess",
                "u_specular": "specular"
            }
        }
    }
    self.glTF["programs"] = {
        "program_0": {
            "attributes": [
                "a_normal",
                "a_position"
            ],
            "fragmentShader": "FragmentShader",
            "vertexShader": "VertexShader"
        }
    }

  def addModel(self, model):
    """Add a mrml model node as a glTF node"""
    if self.modelMode == "triangles":
      print('adding triangles')
      triangles = vtk.vtkTriangleFilter()
      triangles.SetInputDataObject(model.GetPolyData())
      triangles.Update()
      polyData = triangles.GetOutput()
      normalFloatArray = polyData.GetPointData().GetArray('Normals')
      if not normalFloatArray:
        normals = vtk.vtkPolyDataNormals()
        normals.SetInputDataObject(polyData)
        normals.Update()
        polyData = normals.GetOutput()
    elif self.modelMode == "lines":
      print('adding lines')
      polyData = model.GetPolyData()
    if not polyData.GetPoints():
      print ('Skipping model with no points %s)' % model.GetName())
      return
    display = model.GetDisplayNode()
    diffuseColor = [0.2, 0.6, 0.8]
    visible = True
    nonOpaque = False
    if display:
      diffuseColor = list(display.GetColor())
      visible = display.GetVisibility() == 1
      nonOpaque = display.GetOpacity() < 1.0
    else:
      # hack for dealing with fiber bundles - see fiberToModel
      color = model.GetAttribute('color')
      if color:
        diffuseColor = json.loads(color)
      visible = model.GetAttribute('visibility') == '1'
    if not visible:
      print('skipping invisible')
      return
    modelID = model.GetID()
    if modelID is None:
      modelID = model.GetName()

    if model.GetName().endswith('Volume Slice'):
      print('skipping ', model.GetName())
      return

    self.glTF["nodes"][modelID] = {
            "children": [],
            "matrix": [ 1, 0, 0, 0,
                        0, 1, 0, 0,
                        0, 0, 1, 0,
                        0, 0, 0, 1. ],
            "meshes": [
                "Mesh_"+modelID
            ],
            "name": "Mesh"
        }
    self.glTF["scenes"]["defaultScene"]["nodes"].append(modelID)
    glLines = 1
    glTriangles = 4
    if self.modelMode == "triangles":
      self.glTF["meshes"]["Mesh_"+modelID] = {
          "name": "Mesh_"+modelID,
          "primitives": [
              {
                  "attributes": {
                      "NORMAL": "Accessor_Normal_"+modelID,
                      "POSITION": "Accessor_Position_"+modelID
                  },
                  "indices": "Accessor_Indices_"+modelID,
                  "material": "Material_"+modelID,
                  "mode": glLines if nonOpaque else glTriangles
              }
          ]
      }
    elif self.modelMode == "lines":
      self.glTF["meshes"]["Mesh_"+modelID] = {
          "name": "Mesh_"+modelID,
          "primitives": [
              {
                  "attributes": {
                      "POSITION": "Accessor_Position_"+modelID
                  },
                  "indices": "Accessor_Indices_"+modelID,
                  "material": "Material_"+modelID,
                  "mode": glLines
              }
          ]
      }

    self.glTF["materials"]["Material_"+modelID] = {
        "name": "Material_"+modelID,
        "extensions": {
            "KHR_materials_common": {
                "doubleSided": False,
                "technique": "PHONG",
                "transparent": False,
                "values": {
                    "ambient": [ 0, 0, 0, 1 ],
                    "diffuse": diffuseColor,
                    "emission": [ 0, 0, 0, 1 ],
                    "specular": [ 0.174994, 0.174994, 0.174994, 1 ]
                }
            }
        },
    }

    #
    # for the polyData, create a set of
    # buffer, bufferView, and accessor
    # for the position, normal, and triangle strip indices
    #

    # position
    pointFloatArray = polyData.GetPoints().GetData()
    pointNumpyArray = vtk.util.numpy_support.vtk_to_numpy(pointFloatArray) / 1000.  # convert to meters
    pointNumpyArrayByteLength = pointNumpyArray.size * pointNumpyArray.itemsize
    pointBufferFileName = "Buffer_Position_"+modelID+".bin"
    self.buffers[pointBufferFileName] = pointNumpyArray
    bounds = polyData.GetBounds()

    self.glTF["buffers"]["Buffer_Position_"+modelID] = {
        "byteLength": pointNumpyArrayByteLength,
        "type": "arraybuffer",
        "uri": pointBufferFileName,
    }
    self.glTF["bufferViews"]["BufferView_Position_"+modelID] = {
        "buffer": "Buffer_Position_"+modelID,
        "byteLength": pointNumpyArrayByteLength,
        "byteOffset": 0,
        "target": 34962
    }
    self.glTF["accessors"]["Accessor_Position_"+modelID] = {
        "bufferView": "BufferView_Position_"+modelID,
        "byteOffset": 0,
        "byteStride": 12,
        "componentType": 5126,
        "count": pointFloatArray.GetNumberOfTuples(),
        "type": "VEC3",
        "min": [bounds[0],bounds[2],bounds[4]],
        "max": [bounds[1],bounds[3],bounds[5]]
    }

    if self.modelMode == "triangles":

      # normal
      normalFloatArray = polyData.GetPointData().GetArray('Normals')
      normalNumpyArray = vtk.util.numpy_support.vtk_to_numpy(normalFloatArray)
      normalNumpyArrayByteLength = normalNumpyArray.size * normalNumpyArray.itemsize
      normalBufferFileName = "Buffer_Normal_"+modelID+".bin"
      self.buffers[normalBufferFileName] = normalNumpyArray

      self.glTF["buffers"]["Buffer_Normal_"+modelID] = {
          "byteLength": normalNumpyArrayByteLength,
          "type": "arraybuffer",
          "uri": normalBufferFileName,
      }
      self.glTF["bufferViews"]["BufferView_Normal_"+modelID] = {
          "buffer": "Buffer_Normal_"+modelID,
          "byteLength": normalNumpyArrayByteLength,
          "byteOffset": 0,
          "target": 34962
      }
      self.glTF["accessors"]["Accessor_Normal_"+modelID] = {
          "bufferView": "BufferView_Normal_"+modelID,
          "byteOffset": 0,
          "byteStride": 12,
          "componentType": 5126,
          "min": [ -1., -1., -1. ],
          "max": [ 1., 1., 1. ],
          "count": normalFloatArray.GetNumberOfTuples(),
          "type": "VEC3"
      }

      # indices
      triangleCount = polyData.GetNumberOfPolys()
      triangleIndices = polyData.GetPolys().GetData()
      triangleIndexNumpyArray = vtk.util.numpy_support.vtk_to_numpy(triangleIndices).astype('uint32')
      # vtk stores the vertext count per triangle (so delete the 3 at every 4th entry)
      triangleIndexNumpyArray = numpy.delete(triangleIndexNumpyArray, slice(None,None,4))
      triangleIndexCNumpyArray = numpy.asarray(triangleIndexNumpyArray, order='C')
      triangleIndexCNumpyArrayByteLength = triangleIndexCNumpyArray.size * triangleIndexCNumpyArray.itemsize
      indexBufferFileName = "Buffer_Indices_"+modelID+".bin"
      self.buffers[indexBufferFileName] = numpy.array(triangleIndexCNumpyArray)

      self.glTF["buffers"]["Buffer_Indices_"+modelID] = {
          "byteLength": triangleIndexCNumpyArrayByteLength,
          "type": "arraybuffer",
          "uri": indexBufferFileName,
      }
      self.glTF["bufferViews"]["BufferView_Indices_"+modelID] = {
          "buffer": "Buffer_Indices_"+modelID,
          "byteOffset": 0,
          "byteLength": triangleIndexCNumpyArrayByteLength,
          "target": 34963
      }
      self.glTF["accessors"]["Accessor_Indices_"+modelID] = {
          "bufferView": "BufferView_Indices_"+modelID,
          "byteOffset": 0,
          "byteStride": 0,
          "componentType": 5125,
          "count": len(triangleIndexNumpyArray),
          "type": "SCALAR"
      }

    elif self.modelMode == "lines":

      # indices
      polylineCount = polyData.GetNumberOfLines()
      lineIndices = polyData.GetLines().GetData()
      polylineArray = vtk.util.numpy_support.vtk_to_numpy(lineIndices).astype('uint32')
      # vtk stores the vertext count at the start of each polyline, but we need lines, meaning repeated indices unfortunately
      # no way to know how many until we loop through
      polylineIndex = 0
      lineCount = 0
      for polyline in xrange(polylineCount):
        vertexCount = polylineArray[polylineIndex]
        lineCount += 2 * (vertexCount - 1) # each pair in polyline is one line
        polylineIndex += vertexCount + 1 # includes the vertexCount slot

      linesArray = numpy.zeros(2 * lineCount, dtype='uint32') # two indices for each line
      linesIndex = 0
      polylineIndex = 0
      for polyline in xrange(polylineCount):
        vertexCount = polylineArray[polylineIndex]
        polylineIndex += 1
        linesCount = 2 * (vertexCount - 1) # all but one are doubled
        for vertex in xrange(vertexCount-1):
          linesArray[linesIndex] = polylineArray[polylineIndex + vertex]
          linesIndex += 1
          linesArray[linesIndex] = polylineArray[polylineIndex + vertex+1]
          linesIndex += 1
        polylineIndex += vertexCount

      polylineIndicesArray = numpy.asarray(linesArray, order='C')
      polylineIndicesArrayByteLength = polylineIndicesArray.size * polylineIndicesArray.itemsize
      polylineIndicesBufferFileName = "Buffer_Indices_"+modelID+".bin"
      self.buffers[polylineIndicesBufferFileName] = polylineIndicesArray

      self.glTF["buffers"]["Buffer_Indices_"+modelID] = {
          "byteLength": polylineIndicesArrayByteLength,
          "type": "arraybuffer",
          "uri": polylineIndicesBufferFileName
      }
      self.glTF["bufferViews"]["BufferView_Indices_"+modelID] = {
          "buffer": "Buffer_Indices_"+modelID,
          "byteOffset": 0,
          "byteLength": 4 * len(linesArray),
          "target": 34963
      }
      self.glTF["accessors"]["Accessor_Indices_"+modelID] = {
          "bufferView": "BufferView_Indices_"+modelID,
          "byteOffset": 0,
          "byteStride": 0,
          "componentType": 5125,
          "count": len(linesArray),
          "type": "SCALAR"
      }

  def copyFirstNLines(self, sourcePolyData, lineCount):
    """make a polydata with only the first N polylines"""

    polyData = vtk.vtkPolyData()
    points = vtk.vtkPoints()
    polyData.SetPoints(points)

    lines = vtk.vtkCellArray()
    polyData.SetLines(lines)

    sourcePoints = sourcePolyData.GetPoints()
    sourceLines = sourcePolyData.GetLines()
    sourceIdList = vtk.vtkIdList()
    sourceLines.InitTraversal()
    while sourceLines.GetNextCell(sourceIdList):
        pointCount = sourceIdList.GetNumberOfIds()
        idList = vtk.vtkIdList()
        for idIndex in range(pointCount):
            sourceId = sourceIdList.GetId(idIndex)
            point = sourcePoints.GetPoint(sourceId)
            id = points.InsertNextPoint(point)
            idList.InsertNextId(id)
        lines.InsertNextCell(idList)
        if lines.GetNumberOfCells() > lineCount:
            break

    return polyData


  def fiberToModel(self,fiber):
    """Convert a vtkMRMLFiberBundleNode into a dummy vtkMRMLModelNode
    so it can use the same converter.
    Note: need to use attributes to send color since we cannot
    add a display node to the dummy node since it is not in a scene.
    If fiberMode is tube, create tubes from fiber tracts, else use lines from tracts
    """
    if self.targetFiberCount and int(self.targetFiberCount) < fiber.GetPolyData().GetNumberOfCells():
      fiberPolyData = self.copyFirstNLines(fiber.GetPolyData(), int(self.targetFiberCount))
    else:
      fiberPolyData = fiber.GetPolyData()

    model = slicer.vtkMRMLModelNode()
    model.SetName("ModelFrom_"+fiber.GetID())
    displayNode = None
    if self.fiberMode == "tubes":
      tuber = vtk.vtkTubeFilter()
      tuber.SetInputDataObject(fiberPolyData)
      tuber.Update()
      polyData = tuber.GetOutput()
      model.SetAndObservePolyData(polyData)
      normalsArray = polyData.GetPointData().GetArray('TubeNormals')
      if not normalsArray:
        return None
      normalsArray.SetName('Normals')
      displayNode = fiber.GetTubeDisplayNode()
    elif self.fiberMode == "lines":
      model.SetAndObservePolyData(fiberPolyData)
      displayNode = fiber.GetLineDisplayNode()
    if displayNode:
      color = json.dumps(list(displayNode.GetColor()))
      model.SetAttribute("color", color)
      model.SetAttribute("visibility", str(displayNode.GetVisibility()))
    return(model)

    notes = """
      # TODO
      # fa colors per vertex
      scalars = tubes.GetPointData().GetArray(0)
      scalars.SetName("scalars")

      colorNode = lineDisplayNode.GetColorNode()
      lookupTable = vtk.vtkLookupTable()
      lookupTable.DeepCopy(colorNode.GetLookupTable())
      lookupTable.SetTableRange(0,1)
   """

