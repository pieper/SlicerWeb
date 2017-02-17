import os
from __main__ import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *

import logging
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
        response_headers += [('Content-Type','text/plain')]
      elif ACTION == "eulers":
        response_headers += [('Content-Type','text/plain')]
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
      # self.send_error(404, "File not found")
      self.logMessage("Exception in do_GET")
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
      if cmd.find('/eulers') == 0:
        self.logMessage ("got request for eulers")
        return (self.eulers(cmd))
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

  def transform(self,cmd):
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
    self.timeout = 1.
    self.socket.settimeout(5.)
    self.logFile = logFile
    if logMessage:
      self.logMessage = logMessage
    self.notifiers = {}
    self.connections = {}
    self.data = {}

  def onConnectionSocketNotify(self,fileno):
    terminate = False
    connection = self.connections[fileno]
    try:
      data = connection.recv(16)
      self.data[fileno] += data
      if self.data[fileno].endswith('\r\n\r\n'):
        self.logMessage('Got complete message: ', self.data[fileno])
        terminate = True
    except socket.error, e:
      terminate = True
    if len(data) == 0 or terminate:
      body = "<b>hoot</b>"
      answer = "HTTP/1.1 200 OK\r\n"
      answer += "Content-Type: text/html\r\n"
      answer += "Content-Length: %d\r\n" % len(body)
      answer += "\r\n"
      answer += body
      connection.sendall(answer)
      self.logMessage('closing')
      self.notifiers[fileno].disconnect('activated(int)', self.onConnectionSocketNotify)
      del self.notifiers[fileno]
      del self.connections[fileno]
      connection.close()

  def onServerSocketNotify(self,fileno):
      # based on SocketServer.py: self.serve_forever()
      self.logMessage('got request on %d' % fileno)
      try:
        # self.handle_request_noblock()
        #self._handle_request_noblock()
        (connection, clientAddress) = self.socket.accept()
        fileno = connection.fileno()
        self.connections[fileno] = connection
        self.data[fileno] = ""
        self.logMessage('Connected on %d' % connection.fileno())
        self.notifiers[fileno] = qt.QSocketNotifier(connection.fileno(),qt.QSocketNotifier.Read)
        self.notifiers[fileno].connect('activated(int)', self.onConnectionSocketNotify)

      except socket.error, e:
        self.logMessage('Socket Notify Error', socket.error, e)

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
    self.server = SlicerHTTPServer(docroot=self.docroot,server_address=("",self.port),logFile=self.logFile,logMessage=self.logMessage)
    self.server.start()

  def stop(self):
    if self.server:
      self.server.stop()
