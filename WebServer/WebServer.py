import os
from __main__ import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *

import logging
import random
import sys
import select
import urlparse
import urllib
import json
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

import string
import time
import socket
import uuid

from BaseHTTPServer import HTTPServer
import mimetypes

import numpy
import vtk.util.numpy_support

# Note: this needs to be installed in slicer's python
# in order for any of the image operations to work
hasImage = True
try:
  from PIL import Image
except ImportError:
  hasImage = False
hasImage = False

#
# glTFExporter
#

import base64

class glTFExporter:
  """
  Export a subset of mrml data to glTF format (https://www.khronos.org/gltf).

  This could be factored to a separate module, but it's developed
  here for simplicity of reloading and debugging.

  This work was partially funded by NIH grant 3P41RR013218.
  """
  def __init__(self,mrmlScene):
    self.mrmlScene = mrmlScene
    self.sceneDefaults()

  def export(self,nodeFilter=lambda node: True, options={}):
    """
    Returns a json document string in the format supported by glTF
    and described here: https://github.com/KhronosGroup/glTF/blob/master/specification/1.0/README.md
    some defaults and structure pulled from the Box sample at https://github.com/KhronosGroup/glTF-Sample-Models

    nodeFilter is a callable that returns true if the node should be included in the export
    options includes:
      targetFiberCount : can be None for no limit or an integer
      fiberMode : can be "lines" or "tubes"
      modelMode : can be "lines" or "triangles"
    """

    self.targetFiberCount = options['targetFiberCount'] if "targetFiberCount" in options else None
    self.fiberMode = options['fiberMode'] if "fiberMode" in options else "tubes"
    self.modelMode = "lines" if self.fiberMode == "lines" else "triangles"

    if self.fiberMode not in ["lines", "tubes"]:
      print('Bad fiber mode %s' % self.fiberMode)
      return None

    if self.modelMode not in ["lines", "triangles"]:
      print('Bad model mode %s' % self.modelMode)
      return None

    # things specific to each model node
    models = slicer.util.getNodes('vtkMRMLModelNode*')
    for model in models.values():
      if nodeFilter(model):
        self.addModel(model)

    # things specific to each fiber node
    fibers = slicer.util.getNodes('vtkMRMLFiberBundleNode*')
    for fiber in fibers.values():
      if nodeFilter(fiber):
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
      triangles = vtk.vtkTriangleFilter()
      triangles.SetInputDataObject(model.GetPolyData())
      triangles.Update()
      polyData = triangles.GetOutput()
    elif self.modelMode == "lines":
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
    base64PointArray = base64.b64encode(pointNumpyArray)
    bounds = polyData.GetBounds()

    self.glTF["buffers"]["Buffer_Position_"+modelID] = {
        "byteLength": len(base64PointArray),
        "type": "arraybuffer",
        "uri": "data:application/octet-stream;base64,"+base64PointArray,
    }
    self.glTF["bufferViews"]["BufferView_Position_"+modelID] = {
        "buffer": "Buffer_Position_"+modelID,
        "byteLength": len(base64PointArray),
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
      base64NormalArray = base64.b64encode(normalNumpyArray)

      self.glTF["buffers"]["Buffer_Normal_"+modelID] = {
          "byteLength": len(base64NormalArray),
          "type": "arraybuffer",
          "uri": "data:application/octet-stream;base64,"+base64NormalArray,
      }
      self.glTF["bufferViews"]["BufferView_Normal_"+modelID] = {
          "buffer": "Buffer_Normal_"+modelID,
          "byteLength": len(base64NormalArray),
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

      # indices for triangle strips
      # (not finished because it turns out aframe's glTF loader
      # only supports lines and triangles)
      stripFolly = """
      stripCount = polyData.GetNumberOfStrips()
      stripIndices = polyData.GetStrips().GetData()
      stripVTKIndices = vtk.util.numpy_support.vtk_to_numpy(stripIndices).astype('uint32')
      stripGLIndices = numpy.zeros(stripCount+len(stripVTKIndices), dtype='uint32')

      stripVTKIndex = 0
      stripGLIndex = 0
      while stripVTKIndex < len(stripVTKIndices):
        stripSize = stripVTKIndices[stripVTKIndex]
        stripGLIndices[stripGLIndex:stripGLIndex+stripSize] = stripVTKIndices[stripVTKIndex+1:stripVTKIndex+1+stripSize]
        stripGLIndices[stripGLIndex+stripSize+1] = stripGLIndices[stripGLIndex+stripSize]
        firstIndexNextStrip = stripVTKIndex + stripSize + 2
        if firstIndexNextStrip < len(stripVTKIndices):
          stripGLIndices[stripGLIndex+stripSize+2] = stripVTKIndices[firstIndexNextStrip]
        stripVTKIndex += 1+stripSize
        stripGLIndex += stripSize

      print(stripVTKIndices)
      print(stripGLIndices)

      base64StripIndices = base64.b64encode(stripGLIndices)
      """

      # indices
      triangleCount = polyData.GetNumberOfPolys()
      triangleIndices = polyData.GetPolys().GetData()
      triangleIndexNumpyArray = vtk.util.numpy_support.vtk_to_numpy(triangleIndices).astype('uint32')
      # vtk stores the vertext count per triangle (so delete the 3 at every 4th entry)
      triangleIndexNumpyArray = numpy.delete(triangleIndexNumpyArray, slice(None,None,4))
      base64Indices = base64.b64encode(numpy.asarray(triangleIndexNumpyArray, order='C'))

      self.glTF["buffers"]["Buffer_Indices_"+modelID] = {
          "byteLength": len(base64PointArray),
          "type": "arraybuffer",
          "uri": "data:application/octet-stream;base64,"+base64Indices
      }
      self.glTF["bufferViews"]["BufferView_Indices_"+modelID] = {
          "buffer": "Buffer_Indices_"+modelID,
          "byteOffset": 0,
          "byteLength": 4 * len(triangleIndexNumpyArray),
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

      base64Indices = base64.b64encode(numpy.asarray(linesArray, order='C'))

      self.glTF["buffers"]["Buffer_Indices_"+modelID] = {
          "byteLength": len(base64PointArray),
          "type": "arraybuffer",
          "uri": "data:application/octet-stream;base64,"+base64Indices
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

#
# WebServer
#

class WebServer:
  def __init__(self, parent):
    parent.title = "Web Server"
    parent.categories = ["Servers"]
    parent.dependencies = []
    parent.contributors = ["Steve Pieper (Isomics)"] # replace with "Firstname Lastname (Org)"
    parent.helpText = """Provides an embedded web server for slicer that provides a web services API for interacting with slicer.
    """
    parent.acknowledgementText = """
This work was partially funded by NIH grant 3P41RR013218.
""" # replace with organization, grant and thanks.
    self.parent = parent


#
# WebServer widget
#

class WebServerWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """


  def __init__(self, parent=None):
    ScriptedLoadableModuleWidget.__init__(self, parent)
    self.observerTags = []
    self.guiMessages = True
    self.consoleMessages = True

  def enter(self):
    pass

  def exit(self):
    pass

  def setLogging(self):
    self.consoleMessages = self.logToConsole.checked
    self.guiMessages = self.logToGUI.checked

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # reload button
    self.reloadButton = qt.QPushButton("Reload")
    self.reloadButton.name = "WebServer Reload"
    self.reloadButton.toolTip = "Reload this module."
    self.layout.addWidget(self.reloadButton)
    self.reloadButton.connect('clicked(bool)', self.onReload)

    self.log = qt.QTextEdit()
    self.log.readOnly = True
    self.layout.addWidget(self.log)
    self.logMessage('<p>Status: <i>Idle</i>\n')

    # log to console
    self.logToConsole = qt.QCheckBox('Log to Console')
    self.logToConsole.setChecked(self.consoleMessages)
    self.logToConsole.toolTip = "Copy log messages to the python console and parent terminal"
    self.layout.addWidget(self.logToConsole)
    self.logToConsole.connect('clicked()', self.setLogging)

    # log to GUI
    self.logToGUI = qt.QCheckBox('Log to GUI')
    self.logToGUI.setChecked(self.guiMessages)
    self.logToGUI.toolTip = "Copy log messages to the log widget"
    self.layout.addWidget(self.logToGUI)
    self.logToGUI.connect('clicked()', self.setLogging)

    # clear log button
    self.clearLogButton = qt.QPushButton("Clear Log")
    self.clearLogButton.toolTip = "Clear the log window."
    self.layout.addWidget(self.clearLogButton)
    self.clearLogButton.connect('clicked()', self.log.clear)

    # TODO: button to start/stop server
    # TODO: warning dialog on first connect
    # TODO: config option for port

    # open local connection button
    self.localConnectionButton = qt.QPushButton("Open Browser Page")
    self.localConnectionButton.toolTip = "Open a connection to the server on the local machine with your system browser."
    self.layout.addWidget(self.localConnectionButton)
    self.localConnectionButton.connect('clicked()', self.openLocalConnection)

    # open local connection button
    self.localQtConnectionButton = qt.QPushButton("Open QtWebKit Page")
    self.localQtConnectionButton.toolTip = "Open a connection with Qt to the server on the local machine."
    self.layout.addWidget(self.localQtConnectionButton)
    self.localQtConnectionButton.connect('clicked()', self.openQtLocalConnection)

    # open local connection button
    self.qiicrChartButton = qt.QPushButton("Open QIICR Chart Demo")
    self.qiicrChartButton.toolTip = "Open the QIICR chart demo.  You need to be on the internet to access the page and you need to have the QIICR Iowa data loaded in your DICOM database in order to drill down to the image level."
    self.layout.addWidget(self.qiicrChartButton)
    self.qiicrChartButton.connect('clicked()', self.openQIICRChartDemo)

    self.logic = WebServerLogic(logMessage=self.logMessage)
    self.logic.start()

    # Add spacer to layout
    self.layout.addStretch(1)

  def openLocalConnection(self):
    qt.QDesktopServices.openUrl(qt.QUrl('http://localhost:2016'))

  def openQtLocalConnection(self):
    self.webView = qt.QWebView()
    html = """
    <h1>Loading from <a href="http://localhost:2016">Localhost 2016</a></h1>
    """
    self.webView.setHtml(html)
    self.webView.settings().setAttribute(qt.QWebSettings.DeveloperExtrasEnabled, True)
    self.webView.setUrl(qt.QUrl('http://localhost:2016/work'))
    self.webView.show()

  def openQIICRChartDemo(self):
    self.qiicrWebView = qt.QWebView()
    self.qiicrWebView.setGeometry(50, 50, 1750, 1200)
    url = "http://localhost:12345/dcsr/qiicr-chart/index.html"
    url = "http://pieper.github.io/qiicr-chart/dcsr/qiicr-chart"
    html = """
    <h1>Loading from <a href="%(url)s">%(url)s/a></h1>
    """ % {'url' : url}
    self.qiicrWebView.setHtml(html)
    self.qiicrWebView.settings().setAttribute(qt.QWebSettings.DeveloperExtrasEnabled, True)
    self.qiicrWebView.setUrl(qt.QUrl(url))
    self.qiicrWebView.show()

    page = self.qiicrWebView.page()
    if not page.connect('statusBarMessage(QString)', self.qiicrChartMessage):
      logging.error('statusBarMessage connect failed')

  def qiicrChartMessage(self,message):
    if message == "":
      return
    import json
    doc = json.loads(message)
    instanceUID = doc['instanceUID']

    print('want to load', instanceUID)
    # instanceUID = '1.2.276.0.7230010.3.1.4.8323329.10006.1436811198.81030'
    print('instead loading', instanceUID)

    seriesUID = slicer.dicomDatabase.instanceValue(instanceUID,'0020,000E')
    print('actually offering', seriesUID)


    from DICOMLib import DICOMDetailsPopup
    self.detailsPopup = DICOMDetailsPopup()
    self.detailsPopup.offerLoadables(seriesUID, 'Series')
    self.detailsPopup.examineForLoading()
    self.detailsPopup.loadCheckedLoadables()

  def onReload(self):
    self.logic.stop()
    ScriptedLoadableModuleWidget.onReload(self)
    slicer.modules.WebServerWidget.logic.start()


  def logMessage(self,*args):
    if self.consoleMessages:
      for arg in args:
        print(arg)
    if self.guiMessages:
      if len(self.log.html) > 1024*256:
        self.log.clear()
        self.log.insertHtml("Log cleared\n")
      for arg in args:
        self.log.insertHtml(arg)
      self.log.insertPlainText('\n')
      self.log.ensureCursorVisible()
      self.log.repaint()
      #slicer.app.processEvents(qt.QEventLoop.ExcludeUserInputEvents)

#
# StaticRequestHandler
#

class StaticRequestHandler(object):

  def __init__(self, docroot, logMessage):
    self.docroot = docroot
    self.logMessage = logMessage
    self.logMessage('docroot: %s' % self.docroot)

  def handleStaticRequest(self,uri,requestBody):
    """Return directory listing or binary contents of files
    TODO: other header fields like modified time
    """
    contentType = 'text/plain'
    responseBody = None
    if uri.startswith('/'):
      uri = uri[1:]
    path = os.path.join(self.docroot,uri)
    self.logMessage('docroot: %s' % self.docroot)
    if os.path.isdir(path):
      for index in "index.html", "index.htm":
        index = os.path.join(path, index)
        if os.path.exists(index):
          path = index
    self.logMessage('Serving: %s' % path)
    if os.path.isdir(path):
      contentType = "text/html"
      responseBody = "<ul>"
      for entry in os.listdir(path):
        responseBody += "<li><a href='%s'>%s</a></li>" % (os.path.join(uri,entry), entry)
    else:
      ext = os.path.splitext(path)[-1]
      if ext in mimetypes.types_map:
        contentType = mimetypes.types_map[ext]
      try:
        fp = open(path, 'rb')
        responseBody = fp.read()
        fp.close()
      except IOError:
        responseBody = None
    return contentType, responseBody

#
# SlicerRequestHandler
#

class SlicerRequestHandler(object):

  def __init__(self, logMessage):
    self.logMessage = logMessage

  def vtkImageDataToPNG(self,imageData,method='VTK'):
    """Return a buffer of png data using the data
    from the vtkImageData.
    """
    if method == 'PIL':
      if imageData:
        imageData.Update()
        imageScalars = imageData.GetPointData().GetScalars()
        imageArray = vtk.util.numpy_support.vtk_to_numpy(imageScalars)
        d = imageData.GetDimensions()
        im = Image.fromarray( numpy.flipud( imageArray.reshape([d[1],d[0],4]) ) )
      else:
        # no data available, make a small black opaque image
        a = numpy.zeros(100*100*4, dtype='uint8').reshape([100,100,4])
        a[:,:,3] = 255
        im = Image.fromarray( a )
      #if size:
        #im.thumbnail((size,size), Image.ANTIALIAS)
      pngStringIO = StringIO.StringIO()
      im.save(pngStringIO, format="PNG")
      pngData = pngStringIO.getvalue()
    elif method == 'VTK':
      writer = vtk.vtkPNGWriter()
      writer.SetWriteToMemory(True)
      writer.SetInputData(imageData)
      writer.SetCompressionLevel(0)
      writer.Write()
      result = writer.GetResult()
      pngArray = vtk.util.numpy_support.vtk_to_numpy(result)
      pngStringIO = StringIO.StringIO()
      pngStringIO.write(pngArray)
      pngData = pngStringIO.getvalue()

    return pngData

  def handleSlicerCommand(self, cmd, requestBody):
    import traceback
    responseBody = None
    contentType = 'text/plain'
    try:
      if cmd.find('/repl') == 0:
        responseBody = self.repl(cmd, requestBody)
      elif cmd.find('/preset') == 0:
        responseBody = self.preset(cmd)
      elif cmd.find('/timeimage') == 0:
        responseBody = self.timeimage(cmd)
      elif cmd.find('/slice') == 0:
        responseBody = self.slice(cmd)
        contentType = 'image/png',
      elif cmd.find('/threeD') == 0:
        responseBody = self.threeD(cmd)
        contentType = 'image/png',
      elif cmd.find('/mrml') == 0:
        responseBody = self.mrml(cmd)
        contentType = 'application/json',
      elif cmd.find('/tracking') == 0:
        responseBody = self.tracking(cmd)
      elif cmd.find('/eulers') == 0:
        responseBody = self.eulers(cmd)
      elif cmd.find('/volumeSelection') == 0:
        responseBody = self.volumeSelection(cmd)
      elif cmd.find('/volumes') == 0:
        responseBody = self.volumes(cmd, requestBody)
        contentType = 'application/json',
      elif cmd.find('/volume') == 0:
        responseBody = self.volume(cmd, requestBody)
        contentType = 'application/octet-stream',
      elif cmd.find('/transform') == 0:
        responseBody = self.transform(cmd, requestBody)
        contentType = 'application/octet-stream',
      elif cmd.find('/fiducial') == 0:
        responseBody = self.fiducial(cmd, requestBody)
        contentType = 'application/json',
      else:
        responseBody = "unknown command \"" + cmd + "\""
    except:
      message = traceback.format_exc()
      self.logMessage("Could not handle slicer command: %s" % cmd)
      self.logMessage(message)

    return contentType, responseBody

  def repl(self,cmd, requestBody):
    self.logMessage('repl with body %s' % requestBody)
    p = urlparse.urlparse(cmd)
    q = urlparse.parse_qs(p.query)
    if requestBody:
      source = requestBody
    else:
      try:
        source = urllib.unquote(q['source'][0])
      except KeyError:
        self.logMessage('need to supply source code to run')
        return ""
    self.logMessage('will run %s' % source)
    code = compile(source, '<slicr-repl>', 'single')
    result = str(eval(code, globals()))
    self.logMessage('result: %s' % result)
    return result

  def preset(self,cmd):
    p = urlparse.urlparse(cmd)
    q = urlparse.parse_qs(p.query)
    try:
      id = q['id'][0].strip().lower()
    except KeyError:
      id = 'default'

    if id == 'compareview':
      #
      # first, get the sample data
      #
      if not slicer.util.getNodes('MRBrainTumor*'):
        import SampleData
        sampleDataLogic = SampleData.SampleDataLogic()
        tumor1 = sampleDataLogic.downloadMRBrainTumor1()
        tumor2 = sampleDataLogic.downloadMRBrainTumor2()
      else:
        tumor1 = slicer.util.getNode('MRBrainTumor1')
        tumor2 = slicer.util.getNode('MRBrainTumor2')
      # set up the display in the default configuration
      layoutManager = slicer.app.layoutManager()
      redComposite = layoutManager.sliceWidget('Red').mrmlSliceCompositeNode()
      yellowComposite = layoutManager.sliceWidget('Yellow').mrmlSliceCompositeNode()
      redComposite.SetBackgroundVolumeID( tumor1.GetID() )
      yellowComposite.SetBackgroundVolumeID( tumor2.GetID() )
      yellowSlice = layoutManager.sliceWidget('Yellow').mrmlSliceNode()
      yellowSlice.SetOrientationToAxial()
      redSlice = layoutManager.sliceWidget('Red').mrmlSliceNode()
      redSlice.SetOrientationToAxial()
      tumor1Display = tumor1.GetDisplayNode()
      tumor2Display = tumor2.GetDisplayNode()
      tumor2Display.SetAutoWindowLevel(0)
      tumor2Display.SetWindow(tumor1Display.GetWindow())
      tumor2Display.SetLevel(tumor1Display.GetLevel())
      applicationLogic = slicer.app.applicationLogic()
      applicationLogic.FitSliceToAll()
      return ( json.dumps([tumor1.GetName(), tumor2.GetName()]) )
    if id == 'amigo-2012-07-02':
      #
      # first, get the data
      #
      if not slicer.util.getNodes('ID_1'):
        tumor1 = slicer.util.loadVolume('/Users/pieper/data/2July2012/bl-data1/ID_1.nrrd')
        tumor2 = slicer.util.loadVolume('/Users/pieper/data/2July2012/bl-data2/ID_6.nrrd')
      else:
        tumor1 = slicer.util.getNode('ID_1')
        tumor2 = slicer.util.getNode('ID_6')
      # set up the display in the default configuration
      layoutManager = slicer.app.layoutManager()
      redComposite = layoutManager.sliceWidget('Red').mrmlSliceCompositeNode()
      yellowComposite = layoutManager.sliceWidget('Yellow').mrmlSliceCompositeNode()
      yellowSlice = layoutManager.sliceWidget('Yellow').mrmlSliceNode()
      yellowSlice.SetOrientationToAxial()
      redSlice = layoutManager.sliceWidget('Red').mrmlSliceNode()
      redSlice.SetOrientationToAxial()
      redComposite.SetBackgroundVolumeID( tumor1.GetID() )
      yellowComposite.SetBackgroundVolumeID( tumor2.GetID() )
      applicationLogic.FitSliceToAll()
      return ( json.dumps([tumor1.GetName(), tumor2.GetName()]) )
    elif id == 'default':
      #
      # first, get the sample data
      #
      if not slicer.util.getNodes('MR-head*'):
        import SampleData
        sampleDataLogic = SampleData.SampleDataLogic()
        head = sampleDataLogic.downloadMRHead()
        return ( json.dumps([head.GetName(),]) )

    return ( "no matching preset" )

  def setupMRMLTracking(self):
    if not hasattr(self, "trackingDevice"):
      """ set up the mrml parts or use existing """
      nodes = slicer.mrmlScene.GetNodesByName('trackingDevice')
      if nodes.GetNumberOfItems() > 0:
        self.trackingDevice = nodes.GetItemAsObject(0)
        nodes = slicer.mrmlScene.GetNodesByName('tracker')
        self.tracker = nodes.GetItemAsObject(0)
      else:
        # trackingDevice cursor
        self.cube = vtk.vtkCubeSource()
        self.cube.SetXLength(30)
        self.cube.SetYLength(70)
        self.cube.SetZLength(5)
        self.cube.Update()
        # display node
        self.modelDisplay = slicer.vtkMRMLModelDisplayNode()
        self.modelDisplay.SetColor(1,1,0) # yellow
        slicer.mrmlScene.AddNode(self.modelDisplay)
        # self.modelDisplay.SetPolyData(self.cube.GetOutputPort())
        # Create model node
        self.trackingDevice = slicer.vtkMRMLModelNode()
        self.trackingDevice.SetScene(slicer.mrmlScene)
        self.trackingDevice.SetName("trackingDevice")
        self.trackingDevice.SetAndObservePolyData(self.cube.GetOutputDataObject(0))
        self.trackingDevice.SetAndObserveDisplayNodeID(self.modelDisplay.GetID())
        slicer.mrmlScene.AddNode(self.trackingDevice)
        # tracker
        self.tracker = slicer.vtkMRMLLinearTransformNode()
        self.tracker.SetName('tracker')
        slicer.mrmlScene.AddNode(self.tracker)
        self.trackingDevice.SetAndObserveTransformNodeID(self.tracker.GetID())

  def eulers(self,cmd):
    p = urlparse.urlparse(cmd)
    q = urlparse.parse_qs(p.query)
    self.logMessage (q)
    alpha,beta,gamma = map(float,q['angles'][0].split(','))

    self.setupMRMLTracking()
    transform = vtk.vtkTransform()
    transform.RotateZ(alpha)
    transform.RotateX(beta)
    transform.RotateY(gamma)
    self.tracker.SetMatrixTransformToParent(transform.GetMatrix())

    return ( "got it" )

  def tracking(self,cmd):
    p = urlparse.urlparse(cmd)
    q = urlparse.parse_qs(p.query)
    self.logMessage (q)
    transformMatrix = map(float,q['m'][0].split(','))

    self.setupMRMLTracking()
    m = self.tracker.GetMatrixTransformToParent()
    m.Identity()
    for row in xrange(3):
      for column in xrange(3):
        m.SetElement(row,column, transformMatrix[3*row+column])
        m.SetElement(row,column, transformMatrix[3*row+column])
        m.SetElement(row,column, transformMatrix[3*row+column])
        #m.SetElement(row,column, transformMatrix[3*row+column])
    self.tracker.SetMatrixTransformToParent(m)

    return ( "got it" )

  def volumeSelection(self,cmd):
    p = urlparse.urlparse(cmd)
    q = urlparse.parse_qs(p.query)
    try:
      cmd = q['cmd'][0].strip().lower()
    except KeyError:
      cmd = 'next'
    options = ['next', 'previous']
    if not cmd in options:
      cmd = 'next'

    applicationLogic = slicer.app.applicationLogic()
    selectionNode = applicationLogic.GetSelectionNode()
    currentNodeID = selectionNode.GetActiveVolumeID()
    currentIndex = 0
    if currentNodeID:
      nodes = slicer.util.getNodes('vtkMRML*VolumeNode*')
      for nodeName in nodes:
        if nodes[nodeName].GetID() == currentNodeID:
          break
        currentIndex += 1
    if currentIndex >= len(nodes):
      currentIndex = 0
    if cmd == 'next':
      newIndex = currentIndex + 1
    elif cmd == 'previous':
      newIndex = currentIndex - 1
    if newIndex >= len(nodes):
      newIndex = 0
    if newIndex < 0:
      newIndex = len(nodes) - 1
    volumeNode = nodes[nodes.keys()[newIndex]]
    selectionNode.SetReferenceActiveVolumeID( volumeNode.GetID() )
    applicationLogic.PropagateVolumeSelection(0)
    return ( "got it" )

  def volumes(self, cmd, requestBody):
    volumes = []
    mrmlVolumes = slicer.util.getNodes('vtkMRMLScalarVolumeNode*')
    for id_ in mrmlVolumes.keys():
      volumeNode = mrmlVolumes[id_]
      volumes.append({"name": volumeNode.GetName(), "id": volumeNode.GetID()})
    return ( json.dumps( volumes ) )

  def volume(self, cmd, requestBody):
    p = urlparse.urlparse(cmd)
    q = urlparse.parse_qs(p.query)
    try:
      volumeID = q['id'][0].strip()
    except KeyError:
      volumeID = 'vtkMRMLScalarVolumeNode*'

    if requestBody:
      return self.postNRRD(volumeID, requestBody)
    else:
      return self.getNRRD(volumeID)

  def transform(self, cmd, requestBody):
    p = urlparse.urlparse(cmd)
    q = urlparse.parse_qs(p.query)
    try:
      transformID = q['id'][0].strip()
    except KeyError:
      transformID = 'vtkMRMLTransformNode*'

    if requestBody:
      return self.postTransformNRRD(transformID, requestBody)
    else:
      return self.getTransformNRRD(transformID)

  def postNRRD(self, volumeID, requestBody):
    """Convert a binary blob of nrrd data into a node in the scene.
    Overwrite volumeID if it exists, otherwise create new"""

    if requestBody[:4] != "NRRD":
      self.logMessage('Cannot load non-nrrd file (magic is %s)' % requestBody[:4])
      return

    fields = {}
    endOfHeader = requestBody.find('\n\n') #TODO: could be \r\n
    header = requestBody[:endOfHeader]
    self.logMessage(header)
    for line in header.split('\n'):
      colonIndex = line.find(':')
      if line[0] != '#' and colonIndex != -1:
        key = line[:colonIndex]
        value = line[colonIndex+2:]
        fields[key] = value

    if fields['type'] != 'short':
      self.logMessage('Can only read short volumes')
      return "{'status': 'failed'}"
    if fields['dimension'] != '3':
      self.logMessage('Can only read 3D, 1 component volumes')
      return "{'status': 'failed'}"
    if fields['endian'] != 'little':
      self.logMessage('Can only read little endian')
      return "{'status': 'failed'}"
    if fields['encoding'] != 'raw':
      self.logMessage('Can only read raw encoding')
      return "{'status': 'failed'}"
    if fields['space'] != 'left-posterior-superior':
      self.logMessage('Can only read space in LPS')
      return "{'status': 'failed'}"

    imageData = vtk.vtkImageData()
    imageData.SetDimensions(map(int,fields['sizes'].split(' ')))
    imageData.AllocateScalars(vtk.VTK_SHORT, 1)

    origin = map(float, fields['space origin'].replace('(','').replace(')','').split(','))
    origin[0] *= -1
    origin[1] *= -1

    directions = []
    directionParts = fields['space directions'].split(')')[:3]
    for directionPart in directionParts:
      part = directionPart.replace('(','').replace(')','').split(',')
      directions.append(map(float, part))

    ijkToRAS = vtk.vtkMatrix4x4()
    ijkToRAS.Identity()
    for row in range(3):
      ijkToRAS.SetElement(row,3, origin[row])
      for column in range(3):
        element = directions[column][row]
        if row < 2:
          element *= -1
        ijkToRAS.SetElement(row,column, element)

    node = slicer.util.getNode(volumeID)
    if not node:
      node = slicer.vtkMRMLScalarVolumeNode()
      node.SetName(volumeID)
      slicer.mrmlScene.AddNode(node)
      node.CreateDefaultDisplayNodes()
    node.SetAndObserveImageData(imageData)
    node.SetIJKToRASMatrix(ijkToRAS)

    pixels = numpy.frombuffer(requestBody[endOfHeader+2:],dtype=numpy.dtype('int16'))
    array = slicer.util.array(node.GetID())
    array[:] = pixels.reshape(array.shape)
    imageData.GetPointData().GetScalars().Modified()

    displayNode = node.GetDisplayNode()
    displayNode.ProcessMRMLEvents(displayNode, vtk.vtkCommand.ModifiedEvent, "")
    #TODO: this could be optional
    slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveVolumeID(node.GetID())
    slicer.app.applicationLogic().PropagateVolumeSelection()

    return "{'status': 'success'}"

  def getNRRD(self, volumeID):
    """Return a nrrd binary blob with contents of the volume node"""
    volumeNode = slicer.util.getNode(volumeID)
    volumeArray = slicer.util.array(volumeID)

    if volumeNode is None or volumeArray is None:
      self.logMessage('Could not find requested volume')
      return None
    supportedNodes = ["vtkMRMLScalarVolumeNode","vtkMRMLLabelMapVolumeNode"]
    if not volumeNode.GetClassName() in supportedNodes:
      self.logMessage('Can only get scalar volumes')
      return None

    imageData = volumeNode.GetImageData()

    if imageData.GetScalarTypeAsString() != "short":
      self.logMessage('Can only get volumes of type short')
      self.logMessage('Converting to short, but may cause data loss.')
      volumeArray = numpy.array(volumeArray, dtype='int16')

    sizes = imageData.GetDimensions()
    sizes = " ".join(map(str,sizes))

    originList = [0,]*3
    directionLists = [[0,]*3,[0,]*3,[0,]*3]
    ijkToRAS = vtk.vtkMatrix4x4()
    volumeNode.GetIJKToRASMatrix(ijkToRAS)
    for row in xrange(3):
      originList[row] = ijkToRAS.GetElement(row,3)
      for column in xrange(3):
        element = ijkToRAS.GetElement(row,column)
        if row < 2:
          element *= -1
        directionLists[column][row] = element
    originList[0] *=-1
    originList[1] *=-1
    origin = '('+','.join(map(str,originList))+')'
    directions = ""
    for directionList in directionLists:
      direction = '('+','.join(map(str,directionList))+')'
      directions += direction + " "
    directions = directions[:-1]

    # should look like:
    #space directions: (0,1,0) (0,0,-1) (-1.2999954223632812,0,0)
    #space origin: (86.644897460937486,-133.92860412597656,116.78569793701172)

    nrrdHeader = """NRRD0004
# Complete NRRD file format specification at:
# http://teem.sourceforge.net/nrrd/format.html
type: short
dimension: 3
space: left-posterior-superior
sizes: %%sizes%%
space directions: %%directions%%
kinds: domain domain domain
endian: little
encoding: raw
space origin: %%origin%%

""".replace("%%sizes%%", sizes).replace("%%directions%%", directions).replace("%%origin%%", origin)


    nrrdData = StringIO.StringIO()
    nrrdData.write(nrrdHeader)
    nrrdData.write(volumeArray.data)
    return nrrdData.getvalue()

  def getTransformNRRD(self, transformID):
    """Return a nrrd binary blob with contents of the transform node"""
    transformNode = slicer.util.getNode(transformID)
    transformArray = slicer.util.array(transformID)

    if transformNode is None or transformArray is None:
      self.logMessage('Could not find requested transform')
      return None
    supportedNodes = ["vtkMRMLGridTransformNode",]
    if not transformNode.GetClassName() in supportedNodes:
      self.logMessage('Can only get grid transforms')
      return None

    # map the vectors to be in the LPS measurement frame
    # (need to make a copy so as not to change the slicer transform)
    lpsArray = numpy.array(transformArray)
    lpsArray *= numpy.array([-1,-1,1])

    imageData = transformNode.GetTransformFromParent().GetDisplacementGrid()

    # for now, only handle non-oriented grid transform as
    # generated from LandmarkRegistration
    # TODO: generalize for any GridTransform node

    sizes = (3,) + imageData.GetDimensions()
    sizes = " ".join(map(str,sizes))

    spacing = list(imageData.GetSpacing())
    spacing[0] *= -1 # RAS to LPS
    spacing[1] *= -1 # RAS to LPS
    directions = '(%g,0,0) (0,%g,0) (0,0,%g)' % tuple(spacing)

    origin = list(imageData.GetOrigin())
    origin[0] *= -1 # RAS to LPS
    origin[1] *= -1 # RAS to LPS
    origin = '(%g,%g,%g)' % tuple(origin)

    # should look like:
    #space directions: (0,1,0) (0,0,-1) (-1.2999954223632812,0,0)
    #space origin: (86.644897460937486,-133.92860412597656,116.78569793701172)

    nrrdHeader = """NRRD0004
# Complete NRRD file format specification at:
# http://teem.sourceforge.net/nrrd/format.html
type: float
dimension: 4
space: left-posterior-superior
sizes: %%sizes%%
space directions: %%directions%%
kinds: vector domain domain domain
endian: little
encoding: raw
space origin: %%origin%%

""".replace("%%sizes%%", sizes).replace("%%directions%%", directions).replace("%%origin%%", origin)


    nrrdData = StringIO.StringIO()
    nrrdData.write(nrrdHeader)
    nrrdData.write(lpsArray.data)
    return nrrdData.getvalue()

  def fiducial(self, cmd, requestBody):
    p = urlparse.urlparse(cmd)
    q = urlparse.parse_qs(p.query)
    try:
      fiducialID = q['id'][0].strip()
    except KeyError:
      fiducialID = 'vtkMRMLMarkupsFiducialNode*'
    try:
      index = q['index'][0].strip()
    except KeyError:
      index = 0
    try:
      r = q['r'][0].strip()
    except KeyError:
      r = 0
    try:
      a = q['a'][0].strip()
    except KeyError:
      a = 0
    try:
      s = q['s'][0].strip()
    except KeyError:
      s = 0

    fiducialNode = slicer.util.getNode(fiducialID)
    fiducialNode.SetNthFiducialPosition(index, float(r), float(a), float(s));
    return "{'result': 'ok'}"

  def mrml(self,cmd):
    p = urlparse.urlparse(cmd)
    q = urlparse.parse_qs(p.query)
    try:
      format = q['format'][0].strip().lower()
    except KeyError:
      format = 'glTF'
    try:
      targetFiberCount = q['targetFiberCount'][0].strip().lower()
    except KeyError:
      targetFiberCount = None
    try:
      fiberMode = q['fiberMode'][0].strip().lower()
    except KeyError:
      fiberMode = 'lines'
    try:
      id_ = q['id'][0].strip().lower()
    except KeyError:
      id_ = None
    if format == 'glTF':
      nodeFilter = lambda node: True
      if id_:
        nodeFilter = lambda node: node.GetID().lower() == id_
      exporter = glTFExporter(slicer.mrmlScene)
      return (exporter.export(nodeFilter, options={
        "targetFiberCount": targetFiberCount,
        "fiberMode": fiberMode
      }))
    else:
      return ( json.dumps( slicer.util.getNodes('*').keys() ) )

  def slice(self,cmd):
    """return a png for a slice view.
    Args:
     view={red, yellow, green}
     scrollTo= 0 to 1 for slice position within volume
     offset=mm offset relative to slice origin (position of slice slider)
     size=pixel size of output png
    """
    pngMethod = 'PIL'
    if not hasImage:
      pngMethod = 'VTK'
    import vtk.util.numpy_support
    import numpy

    p = urlparse.urlparse(cmd)
    q = urlparse.parse_qs(p.query)
    try:
      view = q['view'][0].strip().lower()
    except KeyError:
      view = 'red'
    options = ['red', 'yellow', 'green']
    if not view in options:
      view = 'red'
    layoutManager = slicer.app.layoutManager()
    sliceLogic = layoutManager.sliceWidget(view.capitalize()).sliceLogic()
    try:
      mode = str(q['mode'][0].strip())
    except (KeyError, ValueError):
      mode = None
    try:
      offset = float(q['offset'][0].strip())
    except (KeyError, ValueError):
      offset = None
    try:
      copySliceGeometryFrom = q['copySliceGeometryFrom'][0].strip()
    except (KeyError, ValueError):
      copySliceGeometryFrom = None
    try:
      scrollTo = float(q['scrollTo'][0].strip())
    except (KeyError, ValueError):
      scrollTo = None
    try:
      size = int(q['size'][0].strip())
    except (KeyError, ValueError):
      size = None
    try:
      orientation = q['orientation'][0].strip()
    except (KeyError, ValueError):
      orientation = None

    offsetKey = 'offset.'+view
    #if mode == 'start' or not self.interactionState.has_key(offsetKey):
      #self.interactionState[offsetKey] = sliceLogic.GetSliceOffset()

    if scrollTo:
      volumeNode = sliceLogic.GetBackgroundLayer().GetVolumeNode()
      bounds = [0,] * 6
      sliceLogic.GetVolumeSliceBounds(volumeNode,bounds)
      sliceLogic.SetSliceOffset(bounds[4] + (scrollTo * (bounds[5] - bounds[4])))
    if offset:
      #startOffset = self.interactionState[offsetKey]
      sliceLogic.SetSliceOffset(startOffset + offset)
    if copySliceGeometryFrom:
      otherSliceLogic = layoutManager.sliceWidget(copySliceGeometryFrom.capitalize()).sliceLogic()
      otherSliceNode = otherSliceLogic.GetSliceNode()
      sliceNode = sliceLogic.GetSliceNode()
      # technique from vtkMRMLSliceLinkLogic (TODO: should be exposed as method)
      sliceNode.GetSliceToRAS().DeepCopy( otherSliceNode.GetSliceToRAS() )
      fov = sliceNode.GetFieldOfView()
      otherFOV = otherSliceNode.GetFieldOfView()
      sliceNode.SetFieldOfView( otherFOV[0],
                                otherFOV[0] * fov[1] / fov[0],
                                fov[2] );

    if orientation:
      sliceNode = sliceLogic.GetSliceNode()
      previousOrientation = sliceNode.GetOrientationString().lower()
      if orientation.lower() == 'axial':
        sliceNode.SetOrientationToAxial()
      if orientation.lower() == 'sagittal':
        sliceNode.SetOrientationToSagittal()
      if orientation.lower() == 'coronal':
        sliceNode.SetOrientationToCoronal()
      if orientation.lower() != previousOrientation:
        sliceLogic.FitSliceToAll()

    imageData = sliceLogic.GetBlend().Update(0)
    imageData = sliceLogic.GetBlend().GetOutputDataObject(0)
    pngData = self.vtkImageDataToPNG(imageData,method=pngMethod)
    self.logMessage('returning an image of %d length' % len(pngData))
    return pngData

  def threeD(self,cmd):
    """return a png for a threeD view
    Args:
     view={nodeid} (currently ignored)
     mode= (currently ignored)
     lookFromAxis = {L, R, A, P, I, S}
    """
    pngMethod = 'PIL'
    if not hasImage:
      pngMethod = 'VTK'
    import numpy
    import vtk.util.numpy_support
    try:
        import cStringIO as StringIO
    except ImportError:
        import StringIO

    p = urlparse.urlparse(cmd)
    q = urlparse.parse_qs(p.query)
    try:
      view = q['view'][0].strip().lower()
    except KeyError:
      view = '1'
    try:
      lookFromAxis = q['lookFromAxis'][0].strip().lower()
    except KeyError:
      lookFromAxis = None
    try:
      size = int(q['size'][0].strip())
    except (KeyError, ValueError):
      size = None
    try:
      mode = str(q['mode'][0].strip())
    except (KeyError, ValueError):
      mode = None
    try:
      roll = float(q['roll'][0].strip())
    except (KeyError, ValueError):
      roll = None
    try:
      panX = float(q['panX'][0].strip())
    except (KeyError, ValueError):
      panX = None
    try:
      panY = float(q['panY'][0].strip())
    except (KeyError, ValueError):
      panY = None
    try:
      orbitX = float(q['orbitX'][0].strip())
    except (KeyError, ValueError):
      orbitX = None
    try:
      orbitY = float(q['orbitY'][0].strip())
    except (KeyError, ValueError):
      orbitY = None

    layoutManager = slicer.app.layoutManager()
    view = layoutManager.threeDWidget(0).threeDView()
    view.renderEnabled = False

    if lookFromAxis:
      axes = ['None', 'r','l','s','i','a','p']
      try:
        axis = axes.index(lookFromAxis[0])
        view.lookFromViewAxis(axis)
      except ValueError:
        pass

    if False and mode:
      # TODO: 'statefull' interaction with the camera
      # - save current camera when mode is 'start'
      # - increment relative to the start camera during interaction
      cameraNode = slicer.util.getNode('*Camera*')
      camera = cameraNode.GetCamera()
      #if mode == 'start' or not self.interactionState.has_key('camera'):
        #startCamera = vtk.vtkCamera()
        #startCamera.DeepCopy(camera)
        #self.interactionState['camera'] = startCamera
      #startCamera = self.interactionState['camera']
      cameraNode.DisableModifiedEventOn()
      camera.DeepCopy(startCamera)
      if roll:
        camera.Roll(roll*100)
      position = numpy.array(startCamera.GetPosition())
      focalPoint = numpy.array(startCamera.GetFocalPoint())
      viewUp = numpy.array(startCamera.GetViewUp())
      viewPlaneNormal = numpy.array(startCamera.GetViewPlaneNormal())
      viewAngle = startCamera.GetViewAngle()
      viewRight = numpy.cross(viewUp,viewPlaneNormal)
      viewDistance = numpy.linalg.norm(focalPoint - position)
      self.logMessage("position", position)
      self.logMessage("focalPoint", focalPoint)
      self.logMessage("viewUp", viewUp)
      self.logMessage("viewPlaneNormal", viewPlaneNormal)
      self.logMessage("viewAngle", viewAngle)
      self.logMessage("viewRight", viewRight)
      self.logMessage("viewDistance", viewDistance)
      if panX and panY:
        offset = viewDistance * -panX * viewRight + viewDistance * viewUp * panY
        newPosition = position + offset
        newFocalPoint = focalPoint + offset
        camera.SetPosition(newPosition)
        camera.SetFocalPoint(newFocalPoint)
      if orbitX and orbitY:
        offset = viewDistance * -orbitX * viewRight + viewDistance * viewUp * orbitY
        newPosition = position + offset
        newFPToEye = newPosition - focalPoint

        newPosition = focalPoint + viewDistance * newFPToEye / numpy.linalg.norm(newFPToEye)
        camera.SetPosition(newPosition)
      cameraNode.DisableModifiedEventOff()
      cameraNode.InvokePendingModifiedEvent()

    view.renderWindow().Render()
    view.renderEnabled = True
    view.forceRender()
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(view.renderWindow())
    w2i.SetReadFrontBuffer(0)
    w2i.Update()
    imageData = w2i.GetOutput()

    pngData = self.vtkImageDataToPNG(imageData,method=pngMethod)
    self.logMessage('threeD returning an image of %d length' % len(pngData))
    return pngData

  def timeimagePIL(self):
    """For debugging - return an image with the current time
    rendered as text down to the hundredth of a second"""
    if not hasImage:
      self.logMessage('No image support')
      return
    from PIL import Image, ImageDraw, ImageFilter
    try:
        import cStringIO as StringIO
    except ImportError:
        import StringIO

    # make an image
    size = (100,30)             # size of the image to create
    im = Image.new('RGB', size) # create the image
    draw = ImageDraw.Draw(im)   # create a drawing object that is
                                # used to draw on the new image
    red = (255,200,100)    # color of our text
    text_pos = (10,10) # top-left position of our text
    text = str(time.time()) # text to draw
    # Now, we'll do the drawing:
    draw.text(text_pos, text, fill=red)
    del draw # I'm done drawing so I don't need this anymore
    im = im.filter(ImageFilter.SMOOTH)
    # now, we tell the image to save as a PNG to the provided file-like object
    pngData = StringIO.StringIO()
    im.save(pngData, format="PNG")
    return pngData.getvalue()

  def timeimage(self,cmd=''):
    """For debugging - return an image with the current time
    rendered as text down to the hundredth of a second"""

    # check arguments
    p = urlparse.urlparse(cmd)
    q = urlparse.parse_qs(p.query)
    try:
      color = "#" + q['color'][0].strip().lower()
    except KeyError:
      color = "#330"

    #
    # make a generally transparent image,
    #
    imageWidth = 128
    imageHeight = 32
    timeImage = qt.QImage(imageWidth, imageHeight, qt.QImage().Format_ARGB32)
    timeImage.fill(0)

    # a painter to use for various jobs
    painter = qt.QPainter()

    # draw a border around the pixmap
    painter.begin(timeImage)
    pen = qt.QPen()
    color = qt.QColor(color)
    color.setAlphaF(0.8)
    pen.setColor(color)
    pen.setWidth(5)
    pen.setStyle(3) # dotted line (Qt::DotLine)
    painter.setPen(pen)
    rect = qt.QRect(1, 1, imageWidth-2, imageHeight-2)
    painter.drawRect(rect)
    color = qt.QColor("#333")
    pen.setColor(color)
    painter.setPen(pen)
    position = qt.QPoint(10,20)
    text = str(time.time()) # text to draw
    painter.drawText(position, text)
    painter.end()

    # convert the image to vtk, then to png from there
    vtkTimeImage = vtk.vtkImageData()
    slicer.qMRMLUtils().qImageToVtkImageData(timeImage, vtkTimeImage)
    pngData = self.vtkImageDataToPNG(vtkTimeImage)
    return pngData

#
# SlicerHTTPServer
#

class SlicerHTTPServer(HTTPServer):
  """
  This web server is configured to integrate with the Qt main loop
  by listenting activity on the fileno of the servers socket.
  """
  # TODO: set header so client knows that image refreshes are needed (avoid
  # using the &time=xxx trick)
  def __init__(self, server_address=("",8070), RequestHandlerClass=SlicerRequestHandler, docroot='.', logFile=None,logMessage=None):
    HTTPServer.__init__(self,server_address, RequestHandlerClass)
    self.docroot = docroot
    self.timeout = 1.
    self.socket.settimeout(5.)
    self.logFile = logFile
    if logMessage:
      self.logMessage = logMessage
    self.notifiers = {}
    self.connections = {}
    self.requestCommunicators = {}


  class RequestCommunicator(object):
    """Encapsulate elements for handling event driven read of request"""
    def __init__(self, connectionSocket, docroot, logMessage):
      self.connectionSocket = connectionSocket
      self.docroot = docroot
      self.logMessage = logMessage
      self.slicerRequestHandler = SlicerRequestHandler(logMessage)
      self.staticRequestHandler = StaticRequestHandler(self.docroot, logMessage)
      self.expectedRequestSize = -1
      self.requestSoFar = ""
      fileno = self.connectionSocket.fileno()
      self.readNotifier = qt.QSocketNotifier(fileno, qt.QSocketNotifier.Read)
      self.readNotifier.connect('activated(int)', self.onReadable)
      self.logMessage('Waiting on %d...' % fileno)

    def onReadable(self, fileno):
      self.logMessage('Reading...')
      requestHeader = ""
      requestBody = ""
      requestComplete = False
      requestPart = ""
      try:
        requestPart = self.connectionSocket.recv(1024*1024)
        self.logMessage('Just received... %d' % len(requestPart))
        self.requestSoFar += requestPart
        endOfHeader = self.requestSoFar.find('\r\n\r\n')
        if self.expectedRequestSize > 0:
          self.logMessage('received... %d of %d expected' % (len(self.requestSoFar), self.expectedRequestSize))
          if len(self.requestSoFar) >= self.expectedRequestSize:
            requestHeader = self.requestSoFar[:endOfHeader+2]
            requestBody = self.requestSoFar[4+endOfHeader:]
            requestComplete = True
        else:
          if endOfHeader != -1:
            self.logMessage('Looking for content in header...')
            contentLengthTag = self.requestSoFar.find('Content-Length:')
            if contentLengthTag != -1:
              tag = self.requestSoFar[contentLengthTag:]
              numberStartIndex = tag.find(' ')
              numberEndIndex = tag.find('\r\n')
              contentLength = int(tag[numberStartIndex:numberEndIndex])
              self.expectedRequestSize = 4 + endOfHeader + contentLength
              self.logMessage('Expecting a body of %d, total size %d' % (contentLength, self.expectedRequestSize))
            else:
              self.logMessage('Found end of header with no content, so body is empty')
              requestHeader = self.requestSoFar[:-2]
              requestComplete = True
      except socket.error, e:
        requestComplete = True

      if len(requestPart) == 0 or requestComplete:
        self.logMessage('Got complete message of header size %d, body size %d' % (len(requestHeader), len(requestBody)))
        self.readNotifier.disconnect('activated(int)', self.onReadable)
        del self.readNotifier

        if len(self.requestSoFar) == 0:
          self.logMessage("Ignoring empty request")
          return

        requestLines = requestHeader.split('\r\n')
        self.logMessage(requestLines[0])
        method,uri,version = requestLines[0].split(' ')
        if version != "HTTP/1.1":
          self.logMessage("Warning, we don't speak %s", version)

        # TODO: methods = ["GET", "POST", "PUT", "DELETE"]
        methods = ["GET", "POST"]
        if not method in methods:
          self.logMessage("Warning, we only handle %s" % methods)
          return

        contentType = 'text/plain'
        responseBody = 'No body'
        if not(os.path.dirname(uri).endswith('slicer')):
          contentType, responseBody = self.staticRequestHandler.handleStaticRequest(uri, requestBody)
        else:
          url = urlparse.urlparse( uri )
          action = os.path.basename( url.path )
          request = '/' + action + '?' + url.query
          self.logMessage('Parsing url: %s' % request)
          contentType, responseBody = self.slicerRequestHandler.handleSlicerCommand(request, requestBody)

        if responseBody:
          self.response = "HTTP/1.1 200 OK\r\n"
          self.response += "Access-Control-Allow-Origin: *\r\n"
          self.response += "Content-Type: %s\r\n" % contentType
          self.response += "Content-Length: %d\r\n" % len(responseBody)
          self.response += "Cache-Control: no-cache\r\n"
          self.response += "\r\n"
          self.response += responseBody
        else:
          self.response = "HTTP/1.1 404 Not Found\r\n"
          self.response += "\r\n"

        self.toSend = len(self.response)
        self.sentSoFar = 0
        fileno = self.connectionSocket.fileno()
        self.writeNotifier = qt.QSocketNotifier(fileno, qt.QSocketNotifier.Write)
        self.writeNotifier.connect('activated(int)', self.onWritable)

    def onWritable(self, fileno):
      self.logMessage('Sending...')
      sendError = False
      try:
        sent = self.connectionSocket.send(self.response)
        self.response = self.response[sent:]
        self.sentSoFar += sent
        self.logMessage('sent: %d (%d of %d, %f%%)' % (sent, self.sentSoFar, self.toSend, 100.*self.sentSoFar / self.toSend))
      except socket.error, e:
        self.logMessage('Socket error while sending: %s' % e)
        sendError = True

      if self.sentSoFar >= self.toSend or sendError:
        self.writeNotifier.disconnect('activated(int)', self.onWritable)
        del self.writeNotifier
        self.connectionSocket.close()
        del self.connectionSocket
        self.logMessage('closed')

  def onServerSocketNotify(self,fileno):
      self.logMessage('got request on %d' % fileno)
      try:
        (connectionSocket, clientAddress) = self.socket.accept()
        fileno = connectionSocket.fileno()
        self.requestCommunicators[fileno] = self.RequestCommunicator(connectionSocket, self.docroot, self.logMessage)
        self.logMessage('Connected on %s fileno %d' % (connectionSocket, connectionSocket.fileno()))
      except socket.error, e:
        self.logMessage('Socket Error', socket.error, e)

  def start(self):
    """start the server
    - use one thread since we are going to communicate
    via stdin/stdout, which will get corrupted with more threads
    """
    try:
      self.logMessage('started httpserver...')
      self.notifier = qt.QSocketNotifier(self.socket.fileno(),qt.QSocketNotifier.Read)
      self.logMessage('listening on %d...' % self.socket.fileno())
      self.notifier.connect('activated(int)', self.onServerSocketNotify)

    except KeyboardInterrupt:
      self.logMessage('KeyboardInterrupt - stopping')
      self.stop()

  def stop(self):
    self.socket.close()
    if self.notifier:
      self.notifier.disconnect('activated(int)', self.onServerSocketNotify)
    self.notifier = None

  def handle_error(self, request, client_address):
    """Handle an error gracefully.  May be overridden.

    The default is to print a traceback and continue.

    """
    print ('-'*40)
    print ('Exception happened during processing of request', request)
    print ('From', client_address)
    import traceback
    traceback.print_exc() # XXX But this goes to stderr!
    print ('-'*40)


  def logMessage(self,message):
    if self.logFile:
      fp = open(self.logFile, "a")
      fp.write(message + '\n')
      fp.close()

  @classmethod
  def findFreePort(self,port=2016):
    """returns a port that is not apparently in use"""
    portFree = False
    while not portFree:
      try:
        s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
        s.setsockopt( socket.SOL_SOCKET, socket.SO_REUSEADDR, 1 )
        s.bind( ( "", port ) )
      except socket.error, e:
        portFree = False
        port += 1
      finally:
        s.close()
        portFree = True
    return port



#
# WebServer logic
#

class WebServerLogic:
  """Include a concrete subclass of SimpleHTTPServer
  that speaks slicer.
  """
  def __init__(self, logMessage=None):
    if logMessage:
      self.logMessage = logMessage
    self.port = 2016
    self.server = None
    self.logFile = '/tmp/WebServerLogic.log'

    moduleDirectory = os.path.dirname(slicer.modules.webserver.path)
    self.docroot = moduleDirectory + "/docroot"

  def logMessage(self,*args):
    for arg in args:
      print("Logic: " + arg)

  def start(self):
    """Set up the server"""
    self.stop()
    self.port = SlicerHTTPServer.findFreePort(self.port)
    self.logMessage("Starting server on port %d" % self.port)
    self.logMessage('docroot: %s' % self.docroot)
    self.server = SlicerHTTPServer(docroot=self.docroot,server_address=("",self.port),logFile=self.logFile,logMessage=self.logMessage)
    self.server.start()

  def stop(self):
    if self.server:
      self.server.stop()
