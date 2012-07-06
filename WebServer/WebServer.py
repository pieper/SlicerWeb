import os
from __main__ import vtk, qt, ctk, slicer

import sys
import select
import urlparse
import urllib
import subprocess
import json
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

import numpy

import PIL

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

class WebServerWidget:

  def __init__(self, parent=None):
    self.observerTags = []
    self.qtMessages = False
    self.consoleMessages = False

    if not parent:
      self.parent = slicer.qMRMLWidget()
      self.parent.setLayout(qt.QVBoxLayout())
      self.parent.setMRMLScene(slicer.mrmlScene)
      self.layout = self.parent.layout()
      self.setup()
      self.parent.show()
    else:
      self.parent = parent
      self.layout = parent.layout()

  def enter(self):
    pass
    
  def exit(self):
    pass

  def setup(self):

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

    # clear log button
    self.clearLogButton = qt.QPushButton("Clear Log")
    self.clearLogButton.toolTip = "Clear the log window."
    self.layout.addWidget(self.clearLogButton)
    self.clearLogButton.connect('clicked()', self.log.clear)

    # TODO: button to start/stop server
    # TODO: warning dialog on first connect
    # TODO: config option for port

    self.logic = WebServerLogic(logMessage=self.logMessage)
    self.logic.start()

    # Add spacer to layout
    self.layout.addStretch(1)

  def onReload(self):
    import imp, sys, os

    try:
      self.logic.stop()
    except AttributeError:
      # can happen if logic failed to load
      pass

    filePath = slicer.modules.webserver.path
    p = os.path.dirname(filePath)
    if not sys.path.__contains__(p):
      sys.path.insert(0,p)

    mod = "WebServer"
    fp = open(filePath, "r")
    globals()[mod] = imp.load_module(mod, fp, filePath, ('.py', 'r', imp.PY_SOURCE))
    fp.close()

    # rebuild the widget
    # - find and hide the existing widget
    # - remove all the layout items
    # - create a new widget in the existing parent
    parent = slicer.util.findChildren(name='WebServer Reload')[0].parent()
    for child in parent.children():
      try:
        child.hide()
      except AttributeError:
        pass
    item = parent.layout().itemAt(0)
    while item:
      parent.layout().removeItem(item)
      item = parent.layout().itemAt(0)

    globals()['web'] = web = globals()[mod].WebServerWidget(parent)
    web.setup()

    web.logic.start()


  def logMessage(self,*args):
    if self.consoleMessages:
      for arg in args:
        print(arg)
    if self.qtMessages:
      for arg in args:
        self.log.insertHtml(arg)
      self.log.insertPlainText('\n')
      self.log.ensureCursorVisible()
      self.log.repaint()
      slicer.app.processEvents(qt.QEventLoop.ExcludeUserInputEvents)

#
# WebServer logic
#

class WebServerLogic:
  """This class runs inside slicer itself and 
  communitates with the server via stdio.  A QTimer 
  is used to periodically check the read pipe for content
  # TODO: integrate stdio pipes into Qt event loop
  Likely approach: 
    Subclass CherryPyWSGIServer and override the tick() method
    Get the sockect member and call fileno() on it.
    Create a QTcpServer and call setSocketDescriptor.
    Then observe newConnection signals and call a skeleton tick
    which will accept the connection and send it to a thread.
    Need to be careful that slicer code (Qt, VTK, etc is not
    modified from multiple server threads.
  """
  def __init__(self, logMessage=None):
    if logMessage:
      self.logMessage = logMessage
    self.interactionState = {}
    self.interval = 20
    self.process = None
    self.pythonPath = slicer.app.slicerHome +"/bin/python"
    if not os.path.exists(self.pythonPath) or os.path.isdir(self.pythonPath):
      self.pythonPath = slicer.app.slicerHome +"/../python-build/bin/python"
    if not os.path.exists(self.pythonPath):
      self.logMessage ("Cannot find python executable cannot start server")
      return

    moduleDirectory = os.path.dirname(slicer.modules.webserver.path)
    self.docroot = moduleDirectory + "/docroot"
    self.serverHelperPath = moduleDirectory + "/Helper/ServerHelper.py"
    self.timer = qt.QTimer()

  def logMessage(self,*args):
    for arg in args:
      print(arg)

  def start(self):
    """Create the subprocess and set up a polling timer"""
    if self.process:
      self.stop()
    self.logMessage("running:", self.pythonPath, self.serverHelperPath, self.docroot)
    self.process = subprocess.Popen([self.pythonPath, self.serverHelperPath, self.docroot],
                                      bufsize=-1,
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
    # call the tick method every so often
    self.timer.setInterval(self.interval)
    self.timer.connect('timeout()', self.tick)
    self.timer.start()
    self.logMessage('Timer started...')

  def stop(self):
    self.timer.stop()
    if self.process:
      self.process.kill()
      self.process = None

  def tick(self):
    """Check to see if there's anything to do"""

    # first, clear stderr
    inputs = [self.process.stderr]
    outputs = []
    readable,writable,exceptional = select.select(inputs, outputs, inputs, 0)
    if readable.__contains__(self.process.stderr):
      error = self.process.stderr.readline()
      if error:
        print ("stderr: %s" % error)
      
    # now check stdin to see if there is work to do
    inputs = [self.process.stdout]
    outputs = []
    readable,writable,exceptional = select.select(inputs, outputs, inputs, 0)
    if readable.__contains__(self.process.stdout):
      # the subprocss is has something to say, read it and respond
      cmd = self.process.stdout.readline()
      #print('got cmd: \"' + cmd + '\"')
      if len(cmd) > 0:
        response = self.handle(cmd)
        try:
          if response:
            contentLength = len(response)
            self.logMessage('writing length: \"' + str(contentLength) + "\"")
            self.process.stdin.write(str(contentLength) + "\n")
            self.logMessage('wrote length')
            self.process.stdin.write(response)
            self.logMessage('wrote response')
          else:
            self.logMessage('no response')
          self.process.stdin.flush()
          self.logMessage ("handled a " + cmd)
        except IOError:
          self.stop()
          self.logMessage ("Needed to abort - IO error in subprocess")

  def handle(self, cmd):
    import traceback
    message = "No error"
    try:
      if cmd.find('/repl') == 0:
        return (self.repl(cmd))
      if cmd.find('/preset') == 0:
        return (self.preset(cmd))
      if cmd.find('/timeimage') == 0:
        return (self.timeimage())
      if cmd.find('/slice') == 0:
        self.logMessage ("got request for slice ("+cmd+")")
        return (self.slice(cmd))
      if cmd.find('/threeD') == 0:
        self.logMessage ("got request for threeD ("+cmd+")")
        return (self.threeD(cmd))
      if cmd.find('/mrml') == 0:
        self.logMessage ("got request for mrml")
        return (self.mrml(cmd))
      if cmd.find('/transform') == 0:
        self.logMessage ("got request for transform")
        return (self.transform(cmd))
      if cmd.find('/volumeSelection') == 0:
        self.logMessage ("got request for volumeSelection")
        return (self.volumeSelection(cmd))
      if cmd.find('/volume') == 0:
        self.logMessage ("got request for volume")
        return (self.volume(cmd))
      response = "unknown command \"" + cmd + "\""
      self.logMessage (response)
      return response
    except:
      message = traceback.format_exc()
      self.logMessage("Could not handle command: %s" % cmd)
      self.logMessage(message)
      return message

  def repl(self,cmd):
    p = urlparse.urlparse(cmd)
    q = urlparse.parse_qs(p.query)
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

  def transform(self,cmd):
    if not hasattr(self,'p'):
      self.p = numpy.zeros(3)
      self.dpdt = numpy.zeros(3)
      self.d2pdt2 = numpy.zeros(3)
      self.o = numpy.zeros(3)
      self.dodt = numpy.zeros(3)
      self.d2odt2 = numpy.zeros(3)
    p = urlparse.urlparse(cmd)
    q = urlparse.parse_qs(p.query)
    self.logMessage (q)
    dt = float(q['interval'][0])
    self.d2pdt2 = 1000 * numpy.array([float(q['x'][0]), float(q['y'][0]), float(q['z'][0])])
    if not hasattr(self,'g0'):
      self.g0 = self.d2pdt2
    self.d2pdt2 = self.d2pdt2 - self.g0
    self.dpdt = self.dpdt + dt * self.d2pdt2
    self.p = self.p + dt * self.dpdt
    # TODO: integrate rotations

    if not hasattr(self, "idevice"):
      """ set up the mrml parts or use existing """
      nodes = slicer.mrmlScene.GetNodesByName('idevice')
      if nodes.GetNumberOfItems() > 0:
        self.idevice = nodes.GetItemAsObject(0)
        nodes = slicer.mrmlScene.GetNodesByName('tracker')
        self.tracker = nodes.GetItemAsObject(0)
      else:
        # idevice cursor
        self.cube = vtk.vtkCubeSource()
        self.cube.SetXLength(30)
        self.cube.SetYLength(70)
        self.cube.SetZLength(5)
        self.cube.Update()
        # display node
        self.modelDisplay = slicer.vtkMRMLModelDisplayNode()
        self.modelDisplay.SetColor(1,1,0) # yellow
        slicer.mrmlScene.AddNode(self.modelDisplay)
        self.modelDisplay.SetPolyData(self.cube.GetOutput())
        # Create model node
        self.idevice = slicer.vtkMRMLModelNode()
        self.idevice.SetScene(slicer.mrmlScene)
        self.idevice.SetName("idevice")
        self.idevice.SetAndObservePolyData(self.cube.GetOutput())
        self.idevice.SetAndObserveDisplayNodeID(self.modelDisplay.GetID())
        slicer.mrmlScene.AddNode(self.idevice)
        # tracker
        self.tracker = slicer.vtkMRMLLinearTransformNode()
        self.tracker.SetName('tracker')
        slicer.mrmlScene.AddNode(self.tracker)
        self.idevice.SetAndObserveTransformNodeID(self.tracker.GetID())
    m = self.tracker.GetMatrixTransformToParent()
    m.Identity()
    up = numpy.zeros(3)
    up[2] = 1
    d = self.d2pdt2
    dd = d / numpy.sqrt(numpy.dot(d,d))
    xx = numpy.cross(dd,up)
    yy = numpy.cross(dd,xx)
    for row in xrange(3):
      m.SetElement(row,0, dd[row])
      m.SetElement(row,1, xx[row])
      m.SetElement(row,2, yy[row])
      #m.SetElement(row,3, self.p[row])

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

    import slicer
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

  def volume(self,cmd):
    p = urlparse.urlparse(cmd)
    q = urlparse.parse_qs(p.query)
    try:
      volumeID = q['id'][0].strip().lower()
    except KeyError:
      volumeID = '*'
      volumeID = 'MRHead'

    import slicer
    volumeNode = slicer.util.getNode(volumeID)
    volumeArray = slicer.util.array(volumeID)
    nrrdHeader = """NRRD0004
# Complete NRRD file format specification at:
# http://teem.sourceforge.net/nrrd/format.html
type: short
dimension: 3
space: left-posterior-superior
sizes: 256 256 130
space directions: (0,1,0) (0,0,-1) (-1.2999954223632812,0,0)
kinds: domain domain domain
endian: little
encoding: raw
space origin: (86.644897460937486,-133.92860412597656,116.78569793701172)

"""
    nrrdData = StringIO.StringIO()
    nrrdData.write(nrrdHeader)
    nrrdData.write(volumeArray.data)
    return nrrdData.getvalue()


  def mrml(self,cmd):
    import slicer
    return ( json.dumps( slicer.util.getNodes('*').keys() ) )

  def slice(self,cmd):
    """return a png for a slice view.
    Args:
     view={red, yellow, green}
     scrollTo= 0 to 1 for slice position within volume
     offset=mm offset relative to slice origin (position of slice slider)
     size=pixel size of output png
    """
    from PIL import Image
    import vtk.util.numpy_support
    import numpy
    import slicer

    p = urlparse.urlparse(cmd)
    q = urlparse.parse_qs(p.query)
    try:
      view = q['view'][0].strip().lower()
    except KeyError:
      view = 'red'
    options = ['red', 'yellow', 'green']
    if not view in options:
      view = 'red'
    sliceLogic = eval( "slicer.sliceWidget%s_sliceLogic" % view.capitalize() )
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

    if scrollTo:
      volumeNode = sliceLogic.GetBackgroundLayer().GetVolumeNode()
      bounds = [0,] * 6
      sliceLogic.GetVolumeSliceBounds(volumeNode,bounds)
      sliceLogic.SetSliceOffset(bounds[4] + (scrollTo * (bounds[5] - bounds[4])))
    if offset:
      currentOffset = sliceLogic.GetSliceOffset()
      sliceLogic.SetSliceOffset(currentOffset + offset)
    if copySliceGeometryFrom:
      otherSliceLogic = eval( "slicer.sliceWidget%s_sliceLogic" % copySliceGeometryFrom.capitalize() )
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
      if orientation.lower() == 'axial':
        sliceNode.SetOrientationToAxial()
      if orientation.lower() == 'sagittal':
        sliceNode.SetOrientationToSagittal()
      if orientation.lower() == 'coronal':
        sliceNode.SetOrientationToCoronal()

    imageData = sliceLogic.GetImageData()
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
    if size:
      im.thumbnail((size,size), Image.ANTIALIAS)
    pngData = StringIO.StringIO()
    im.save(pngData, format="PNG")
    self.logMessage('returning an image of %d length' % len(pngData.getvalue()))
    return pngData.getvalue()

  def threeD(self,cmd):
    """return a png for a threeD view
    Args:
     view={nodeid} (currently ignored)
    """
    from PIL import Image
    import numpy
    import vtk.util.numpy_support
    import slicer
    import urlparse
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

    if mode:
      cameraNode = slicer.util.getNode('*Camera*')
      camera = cameraNode.GetCamera()
      if mode == 'start' or not self.interactionState.has_key('camera'):
        startCamera = vtk.vtkCamera()
        startCamera.DeepCopy(camera)
        self.interactionState['camera'] = startCamera
      startCamera = self.interactionState['camera']
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
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(view.renderWindow())
    w2i.SetReadFrontBuffer(0)
    w2i.Update()
    imageData = w2i.GetOutput()

    if imageData:
      imageScalars = imageData.GetPointData().GetScalars()
      imageArray = vtk.util.numpy_support.vtk_to_numpy(imageScalars)
      d = imageData.GetDimensions()
      im = Image.fromarray( numpy.flipud( imageArray.reshape([d[1],d[0],3]) ) )
    else:
      # no data available, make a small black opaque image
      a = numpy.zeros(100*100*4, dtype='uint8').reshape([100,100,4])
      a[:,:,3] = 255
      im = Image.fromarray( a )
    if size:
      im.thumbnail((size,size), Image.ANTIALIAS)
    pngData = StringIO.StringIO()
    im.save(pngData, format="PNG")
    self.logMessage('threeD returning an image of %d length' % len(pngData.getvalue()))
    return pngData.getvalue()

  def timeimage(self):
    """For debugging - return an image with the current time
    rendered as text down to the hundredth of a second"""
    import time
    from PIL import Image, ImageDraw, ImageFilter
    import slicer
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


