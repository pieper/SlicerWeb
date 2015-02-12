import os
from __main__ import vtk, qt, ctk, slicer

import sys
import select
import urlparse
import urllib
import json
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

import string,time
import socket

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler

import numpy

# Note: this needs to be installed in slicer's python
# in order for any of the image operations to work
hasImage = True
try:
  from PIL import Image
except ImportError:
  hasImage = False
hasImage = False

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
    self.guiMessages = True
    self.consoleMessages = True

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

  def setLogging(self):
    self.consoleMessages = self.logToConsole.checked
    self.guiMessages = self.logToGUI.checked

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
    self.localConnectionButton = qt.QPushButton("Open Page")
    self.localConnectionButton.toolTip = "Open a connection to the server on the local machine."
    self.layout.addWidget(self.localConnectionButton)
    self.localConnectionButton.connect('clicked()', self.openLocalConnection)


    self.logic = WebServerLogic(logMessage=self.logMessage)
    self.logic.start()

    # Add spacer to layout
    self.layout.addStretch(1)

  def openLocalConnection(self):
    qt.QDesktopServices.openUrl(qt.QUrl('http://localhost:8080'))

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
    if self.guiMessages:
      for arg in args:
        self.log.insertHtml(arg)
      self.log.insertPlainText('\n')
      self.log.ensureCursorVisible()
      self.log.repaint()
      #slicer.app.processEvents(qt.QEventLoop.ExcludeUserInputEvents)


#
# SlicerRequestHandler
#

class SlicerRequestHandler(SimpleHTTPRequestHandler):

  def start_response(self, status, response_headers):
    self.send_response(status)
    for keyword,value in response_headers:
      self.send_header(keyword, value)
    self.end_headers()

  def logMessage(self, message):
     self.server.logMessage(message)

  def log_message(self, format, *args):
      """Log an arbitrary message.

      This is used by all other logging functions.  Override
      it if you have specific logging wishes.

      The first argument, FORMAT, is a format string for the
      message to be logged.  If the format string contains
      any % escapes requiring parameters, they should be
      specified as subsequent arguments (it's just like
      printf!).

      The client host and current date/time are prefixed to
      every message.

      """

      self.logMessage("%s - - [%s] %s\n" %
                       (self.address_string(),
                        self.log_date_time_string(),
                        format%args))

  def do_GET(self):
    self.protocol_version = 'HTTP/1.1'
    try:
      status = 200
      rest = self.path
      self.logMessage("Handling: " + rest)

      # Handle this as a standard request
      #
      if not(os.path.dirname(rest).endswith('slicer')):
        os.chdir(self.server.docroot)
        self.logMessage(" ... using SimpleHTTPRequestHandler" )
        SimpleHTTPRequestHandler.do_GET(self)
        return

      # Got a /slicer request
      #
      if False:
        # TODO
        # But we're busy ... write response and return
        response_headers = [('Content-Type','text/plain')]
        self.logMessage('Server busy')
        self.start_response(status, response_headers)
        self.wfile.write( 'Busy' )
        return

      # Now we're talking to Slicer...
      URL = urlparse.urlparse( rest )
      ACTION = os.path.basename( URL.path )
      self.logMessage('Parsing url, action is {' + ACTION +
        '} query is {' + URL.query + '}')

      body = self.handleSlicerCommand('/' + ACTION + '?' + URL.query)
      count = len(body)
      self.logMessage("  [done]")

      response_headers = [
          ('Content-length', str(count)),
          ('Cache-Control', 'no-cache'),
      ]

      if ACTION == "repl":
        response_headers += [('Content-Type','text/plain')]
      elif ACTION == "preset":
        response_headers += [('Content-Type','text/plain')]
      elif ACTION == "mrml":
        response_headers += [('Content-Type','application/json')]
      elif ACTION == "scene":
        response_headers += [('Content-Type','application/json')]
      elif ACTION == "timeimage":
        response_headers += [('Content-Type','image/png')]
      elif ACTION == "slice":
        response_headers += [('Content-Type','image/png')]
      elif ACTION == "threeD":
        response_headers += [('Content-Type','image/png')]
      elif ACTION == "transform":
        response_headers += [('Content-Type','image/png')]
      elif ACTION == "volumeSelection":
        response_headers += [('Content-Type','text/plain')]
      elif ACTION == "volume":
        response_headers += [('Content-Type','application/octet-stream')]
      elif URL.query.endswith("png"):
        response_headers += [('Content-Type','image/png')]
      else:
        # didn't match known slicer API commands, so we shouldn't
        # prevent other slicer connections from completing
        self.logMessage( 'WARNING: no matching action for:' + rest )
        response_headers += [('Content-Type','text/plain')]

      # FINALLY, write the "body" returned by Slicer as the response
      self.start_response(status, response_headers)
      self.wfile.write( body )

    except Exception, e:
      self.send_error(404, "File not found")
      import traceback
      traceback.print_exc()

    # end do_GET

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

  def dumpReq( self, formInput=None ):
      response= "<html><head></head><body>"
      response+= "<p>HTTP Request</p>"
      response+= "<p>self.command= <tt>%s</tt></p>" % ( self.command )
      response+= "<p>self.path= <tt>%s</tt></p>" % ( self.path )
      response+= "</body></html>"
      self.sendPage( "text/html", response )

  def sendPage( self, type, body ):
      self.send_response( 200 )
      self.send_header( "Content-type", type )
      self.send_header( "Content-length", str(len(body)) )
      self.end_headers()
      self.wfile.write( body )

  def do_PUT(self):
    try:
      self.server.logMessage( "Command: %s Path: %s Headers: %r"
                        % ( self.command, self.path, self.headers.items() ) )
      if self.headers.has_key('content-length'):
          length= int( self.headers['content-length'] )
          body = self.rfile.read( length )
          self.logMessage("Got: %s" % body)
          self.dumpReq( self.rfile.read( length ) )
      else:
          self.dumpReq( None )

    except :
        self.server.logMessage('could not PUT')

  def do_POST(self):
    #TODO
    pass

  def handleSlicerCommand(self, cmd):
    import traceback
    message = "No error"
    try:
      if cmd.find('/repl') == 0:
        return (self.repl(cmd))
      if cmd.find('/preset') == 0:
        return (self.preset(cmd))
      if cmd.find('/timeimage') == 0:
        return (self.timeimage(cmd))
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
      self.logMessage("Could not handle slicer command: %s" % cmd)
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
        self.modelDisplay.SetPolyData(self.cube.GetOutputPort())
        # Create model node
        self.idevice = slicer.vtkMRMLModelNode()
        self.idevice.SetScene(slicer.mrmlScene)
        self.idevice.SetName("idevice")
        self.idevice.SetAndObservePolyData(self.cube.GetOutputPort())
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
    pngMethod = 'PIL'
    if not hasImage:
      pngMethod = 'VTK'
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
      if orientation.lower() == 'axial':
        sliceNode.SetOrientationToAxial()
      if orientation.lower() == 'sagittal':
        sliceNode.SetOrientationToSagittal()
      if orientation.lower() == 'coronal':
        sliceNode.SetOrientationToCoronal()

    imageData = sliceLogic.GetImageData()
    pngData = self.vtkImageDataToPNG(imageData,method=pngMethod)
    self.logMessage('returning an image of %d length' % len(pngData))
    return pngData

  def threeD(self,cmd):
    """return a png for a threeD view
    Args:
     view={nodeid} (currently ignored)
    """
    pngMethod = 'PIL'
    if not hasImage:
      pngMethod = 'VTK'
    import numpy
    import vtk.util.numpy_support
    import slicer
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
    self.logFile = logFile
    if logMessage:
      self.logMessage = logMessage


  def onSocketNotify(self,fileno):
      # based on SocketServer.py: self.serve_forever()
      self.logMessage('got request on %d' % fileno)
      self._handle_request_noblock()

  def start(self):
    """start the server
    - use one thread since we are going to communicate
    via stdin/stdout, which will get corrupted with more threads
    """
    try:
      self.logMessage('started httpserver...')
      self.notifier = qt.QSocketNotifier(self.socket.fileno(),qt.QSocketNotifier.Read)
      self.notifier.connect('activated(int)', self.onSocketNotify)

    except KeyboardInterrupt:
      self.logMessage('KeyboardInterrupt - stopping')
      self.stop()

  def stop(self):
    self.socket.close()
    self.notifier = None

  def logMessage(self,message):
    if self.logFile:
      fp = open(self.logFile, "a")
      fp.write(message + '\n')
      fp.close()

  @classmethod
  def findFreePort(self,port=8080):
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
    self.port = 8080
    self.server = None
    self.logFile = '/tmp/WebServerLogic.log'

    moduleDirectory = os.path.dirname(slicer.modules.webserver.path)
    self.docroot = moduleDirectory + "/docroot"


  def logMessage(self,*args):
    for arg in args:
      print("Logic: " + arg)

  def start(self):
    """Create the subprocess and set up a polling timer"""
    self.stop()
    self.port = SlicerHTTPServer.findFreePort(self.port)
    self.logMessage("Starting server on port %d" % self.port)
    self.server = SlicerHTTPServer(docroot=self.docroot,server_address=("",self.port),logFile=self.logFile,logMessage=self.logMessage)
    self.server.start()

  def stop(self):
    if self.server:
      self.server.stop()
