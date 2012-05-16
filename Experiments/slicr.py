import sys
import os
import select
import urlparse
import urllib
import subprocess
import json
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

import cherrypy
import PIL

notes = """

run slicer4 (with .slicerrc.py)
load volume
open python console
type Control-6

connect to:

http://localhost:8070/slicer/slice?Red

"""



class slicr_command_processor(object):
  """This class runs inside slicer itself and 
  communitates with the server via stdio.  A QTimer 
  is used to periodically check the read pipe for content
  # TODO: integrate stdio pipes into Qt event loop
  """
  def __init__(self):
    import sys,os
    import qt
    import numpy
    import vtk
    import slicer
    import slicer.util
    self.interactionState = {}
    self.interval = 20
    self.process = None
    #self.python_path = os.environ['PYTHON_DIR']+"/bin/python"
    self.python_path = slicer.app.slicerHome +"/../python-build/bin/python"
    print(self.python_path)
    if sys.platform == 'darwin':
      self.docroot = "/Users/pieper/Dropbox/webgl/slicr"
    else:
      self.docroot = "/home/pieper/Dropbox/webgl/slicr"
    self.slicr_path = self.docroot + "/slicr.py"
    self.timer = qt.QTimer()
    
  def start(self):
    """Create the subprocess and set up a polling timer"""
    if self.process:
      self.stop()
    self.process = subprocess.Popen([self.python_path, self.slicr_path],
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
    # call the tick method every so often
    self.timer.setInterval(self.interval)
    self.timer.connect('timeout()', self.tick)
    self.timer.start()

  def stop(self):
    self.timer.stop()
    self.process.kill()
    self.process = None

  def tick(self):
    """Check to see if there's anything to do"""
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
            print('writing length: \"' + str(len(response)) + "\"")
            self.process.stdin.write(str(len(response)) + "\n")
            print('wrote length')
            self.process.stdin.write(response)
            print('wrote response')
          else:
            print('no response')
          self.process.stdin.flush()
          print ("handled a " + cmd)
        except IOError:
          self.stop()
          print ("Needed to abort - IO error in subprocess")

  def handle(self, cmd):
    import traceback
    message = "No error"
    try:
      if cmd.find('/repl') == 0:
        return (self.repl(cmd))
      if cmd.find('/timeimage') == 0:
        return (self.timeimage())
      if cmd.find('/slice') == 0:
        print ("got request for slice ("+cmd+")")
        return (self.slice(cmd))
      if cmd.find('/threeD') == 0:
        print ("got request for threeD ("+cmd+")")
        return (self.threeD(cmd))
      if cmd.find('/mrml') == 0:
        print ("got request for mrml")
        return (self.mrml(cmd))
      if cmd.find('/transform') == 0:
        print ("got request for transform")
        return (self.transform(cmd))
      if cmd.find('/volume') == 0:
        print ("got request for volume")
        return (self.volume(cmd))
      print ("unknown command \"" + cmd + "\"")
      return ""
    except:
      message = traceback.format_exc()
    finally:
      print("Could not handle command: %s" % cmd)
      print message

  def repl(self,cmd):
    p = urlparse.urlparse(cmd)
    q = urlparse.parse_qs(p.query)
    try:
      source = urllib.unquote(q['source'][0])
    except KeyError:
      print('need to supply source code to run')
      return ""
    print('will run %s' % source)
    code = compile(source, '<slicr-repl>', 'single')
    result = str(eval(code, globals()))
    print('result: %s' % result)
    return result

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
    print (q)
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

  def volume(self,cmd):
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


  def mrml(self,cmd):
    import slicer
    return ( json.dumps( slicer.util.getNodes().keys() ) )

  def slice(self,cmd):
    """return a png for a slice view.
    Args:
     view={red, yellow, green}
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
      scrollTo = float(q['scrollTo'][0].strip())
    except (KeyError, ValueError):
      scrollTo = None
    try:
      size = int(q['size'][0].strip())
    except (KeyError, ValueError):
      size = None

    if scrollTo:
      volumeNode = sliceLogic.GetBackgroundLayer().GetVolumeNode()
      bounds = [0,] * 6
      sliceLogic.GetVolumeSliceBounds(volumeNode,bounds)
      sliceLogic.SetSliceOffset(bounds[4] + (scrollTo * (bounds[5] - bounds[4])))
    if offset:
      currentOffset = sliceLogic.GetSliceOffset()
      sliceLogic.SetSliceOffset(currentOffset + offset)

    imageData = sliceLogic.GetImageData()
    imageData.Update()
    if imageData:
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
    print('returning an image of %d length' % len(pngData.getvalue()))
    cherrypy.response.headers['Content-Type']= 'image/png'
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

    if mode:
      camera = slicer.util.getNode('*Camera*').GetCamera()
      if mode == 'start' or not self.interactionState.has_key('camera'):
        startCamera = vtk.vtkCamera()
        startCamera.DeepCopy(camera)
        self.interactionState['camera'] = startCamera
      startCamera = self.interactionState['camera']
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
      print("position", position)
      print("focalPoint", focalPoint)
      print("viewUp", viewUp)
      print("viewPlaneNormal", viewPlaneNormal)
      print("viewAngle", viewAngle)
      print("viewRight", viewRight)
      print("viewDistance", viewDistance)
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

    layoutManager = slicer.app.layoutManager()
    view = layoutManager.threeDWidget(0).threeDView()
    view.forceRender()
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(view.renderWindow())
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
    print('returning an image of %d length' % len(pngData.getvalue()))
    cherrypy.response.headers['Content-Type']= 'image/png'
    return pngData.getvalue()

  def red(self):
    from PIL import Image
    import numpy
    import vtk.util.numpy_support
    import slicer
    try:
        import cStringIO as StringIO
    except ImportError:
        import StringIO

    redLogic = slicer.sliceWidgetRed_sliceLogic
    imageData = redLogic.GetImageData()
    if imageData:
      imageScalars = imageData.GetPointData().GetScalars()
      imageArray = vtk.util.numpy_support.vtk_to_numpy(imageScalars)
      d = imageData.GetDimensions()
      im = Image.fromarray( numpy.flipud( imageArray.reshape([d[1],d[0],4]) ) )
    else:
      # no data available, make a small black opaque image
      a = numpy.zeros(100*100*4, dtype='uint8').reshape([100,100,4])
      a[:,:,3] = 255
      im = Image.fromarray( a )
    pngData = StringIO.StringIO()
    im.save(pngData, format="PNG")
    cherrypy.response.headers['Content-Type']= 'image/png'
    return pngData.getvalue()

  def timeimage(self):
    import time
    from PIL import Image, ImageDraw, ImageFilter
    import slicer
    try:
        import cStringIO as StringIO
    except ImportError:
        import StringIO

    # make an image
    size = (100,30)             # size of the image to create
    size = (1000,300)             # size of the image to create
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
    # now, we tell the image to save as a PNG to the 
    # provided file-like object
    pngData = StringIO.StringIO()
    im.save(pngData, format="PNG")
    cherrypy.response.headers['Content-Type']= 'image/png'
    return pngData.getvalue()


class slicr_web_server(object):
  """ This runs in a process that listens for web
  requests and then communicates with slicer as a parent
  program by communicating via stdio"""
  # TODO: set header so client knows that image refreshes are needed (avoid
  # using the &time=xxx trick)
  def __init__(self, docroot='.', port=8070, server_name='slicr'):
    self.count = 0
    self.port = port
    self.server_name = server_name
    self.docroot = docroot
    # use this as a mutex on the stdio connection
    self.communicatingWithSlicer = False

  def app(self, environ, start_response):
    """This is the actual app server that responds to web
    requests by creating cherrypy ResponseObject instances.
    http://www.cherrypy.org/wiki/ResponseObject
    """
    status = '200 OK'
    rest = environ['PATH_INFO'] 
    if environ['QUERY_STRING'] != '':
      rest = environ['PATH_INFO'] + "?" + environ['QUERY_STRING']
    if rest.find("/env") == 0:
      print("env")
      response_headers = [('Content-Type','text/plain')]
      start_response(status, response_headers)
      return [str(environ)]
    if rest.find("/slow") == 0:
      print("slow")
      print ("requested")
      ii = 10
      for i in xrange(10000000):
        ii = i*i+ii
      response_headers = [('Content-Type','text/plain')]
      start_response(status, response_headers)
      print("responded")
      return ["done" + str(ii)]
    if rest.find("/timeimage") == 0:
      import time
      from PIL import Image, ImageDraw, ImageFilter
      try:
          import cStringIO as StringIO
      except ImportError:
          import StringIO
      response_headers = [('Content-Type','image/png')]
      start_response(status, response_headers)

      # make an image
      size = (100,30)             # size of the image to create
      size = (1000,300)             # size of the image to create
      im = Image.new('RGB', size) # create the image
      draw = ImageDraw.Draw(im)   # create a drawing object that is
                                  # used to draw on the new image
      red = (255,200,100)    # color of our text
      for p in xrange(100):
        text_pos = (p+10,10) # top-left position of our text
        text = str(time.time()) # text to draw
        # Now, we'll do the drawing: 
        draw.text(text_pos, text, fill=red)
      
      del draw # I'm done drawing so I don't need this anymore

      #im = im.filter(ImageFilter.SMOOTH)
      
      # now, we tell the image to save as a PNG to the 
      # provided file-like object
      pngData = StringIO.StringIO()
      im.save(pngData, format="PNG")
      cherrypy.response.headers['Content-Type']= 'image/png'
      return pngData.getvalue()
    if rest.find("/ask") == 0:
      print("ask")
      resp = raw_input("what should I say? ")
      response_headers = [('Content-Type','text/plain')]
      start_response(status, response_headers)
      self.count += 1
      print ("got " + resp)
      return [str(self.count) + resp]
    if rest.find("/slicer") == 0:
      if self.communicatingWithSlicer:
        response_headers = [('Content-Type','text/plain')]
        start_response(status, response_headers)
        return ['Busy']
      self.communicatingWithSlicer = True
      subcmd = rest[len("/slicer"):]
      sys.stdout.write(subcmd + "\n")
      sys.stdout.flush()
      if subcmd.find("/repl") == 0:
        count = int(sys.stdin.readline())
        im = sys.stdin.read(count)
        self.communicatingWithSlicer = False
        response_headers = [('Content-Type','text/plain')]
        start_response(status, response_headers)
        self.count += 1
        return [im]
      if subcmd.find("/mrml") == 0:
        count = int(sys.stdin.readline())
        im = sys.stdin.read(count)
        self.communicatingWithSlicer = False
        response_headers = [('Content-Type','application/json')]
        start_response(status, response_headers)
        self.count += 1
        return [im]
      if subcmd.find("/scene") == 0:
        count = int(sys.stdin.readline())
        im = sys.stdin.read(count)
        self.communicatingWithSlicer = False
        response_headers = [('Content-Type','application/json')]
        start_response(status, response_headers)
        self.count += 1
        return [im]
      if subcmd.find("/timeimage") == 0:
        count = int(sys.stdin.readline())
        im = sys.stdin.read(count)
        self.communicatingWithSlicer = False
        response_headers = [('Content-Type','image/png')]
        start_response(status, response_headers)
        self.count += 1
        return [im]
      if subcmd.find("/slice") == 0:
        count = int(sys.stdin.readline())
        im = sys.stdin.read(count)
        self.communicatingWithSlicer = False
        response_headers = [('Content-Type','image/png')]
        start_response(status, response_headers)
        self.count += 1
        return [im]
      if subcmd.find("/threeD") == 0:
        count = int(sys.stdin.readline())
        im = sys.stdin.read(count)
        self.communicatingWithSlicer = False
        response_headers = [('Content-Type','image/png')]
        start_response(status, response_headers)
        self.count += 1
        return [im]
      if subcmd.find("/transform") == 0:
        count = int(sys.stdin.readline())
        im = sys.stdin.read(count)
        self.communicatingWithSlicer = False
        response_headers = [('Content-Type','image/png')]
        start_response(status, response_headers)
        self.count += 1
        return [im]
      if subcmd.find("/volume") == 0:
        count = int(sys.stdin.readline())
        im = sys.stdin.read(count)
        self.communicatingWithSlicer = False
        response_headers = [('Content-Type','image/png')]
        start_response(status, response_headers)
        self.count += 1
        return [im]
      if subcmd.endswith("png"):
        count = int(sys.stdin.readline())
        im = sys.stdin.read(count)
        self.communicatingWithSlicer = False
        response_headers = [('Content-Type','image/png')]
        start_response(status, response_headers)
        self.count += 1
        return [im]
    # handle regular doctypes
    if rest.endswith(".html"):
      response_headers = [('Content-Type','text/html')]
      start_response(status, response_headers)
      html_path = self.docroot + rest
      fp = open(html_path, 'r')
      resp = fp.read()
      fp.close()
      return [resp]
    if rest.endswith(".json"):
      response_headers = [('Content-Type','application/json')]
      start_response(status, response_headers)
      html_path = self.docroot + rest
      fp = open(html_path, 'r')
      resp = fp.read()
      fp.close()
      return [resp]
    if rest.endswith(".js"):
      response_headers = [('Content-Type','application/javascript')]
      start_response(status, response_headers)
      html_path = self.docroot + rest
      fp = open(html_path, 'r')
      resp = fp.read()
      fp.close()
      return [resp]
    if rest.endswith(".css"):
      response_headers = [('Content-Type','text/css')]
      start_response(status, response_headers)
      html_path = self.docroot + rest
      fp = open(html_path, 'r')
      resp = fp.read()
      fp.close()
      return [resp]
    if rest.endswith("png"):
      response_headers = [('Content-Type','image/png')]
      start_response(status, response_headers)
      html_path = self.docroot + rest
      fp = open(html_path, 'r')
      resp = fp.read()
      fp.close()
      return [resp]
      
    # don't know - send an error mesage
    status = 404
    response_headers = [('Content-Type','text/plain')]
    start_response(status, response_headers)
    self.count += 1
    return [str(self.count)+" Didn't understand the message: " + rest]


  def start(self):
    """start the server
    - use one thread since we are going to communicate 
    via stdin/stdout, which will get corrupted with more threads
    """
    global server
    from cherrypy import wsgiserver
    self.server = wsgiserver.CherryPyWSGIServer(
        ('0.0.0.0', self.port), 
        self.app,
        numthreads=10,
        server_name=self.server_name)

    self.server.nodelay=False
    self.server.start()

  def stop(self):
    self.server.stop()

# When slicr_web_server is run as a command line script, use
# this to start the server itself
if __name__ == '__main__':
  global s
  if sys.platform == 'darwin':
    docroot = "/Users/pieper/Dropbox/webgl/slicr"
  else:
    docroot = "/home/pieper/Dropbox/webgl/slicr"
  s = slicr_web_server(docroot=docroot, port=8070)
  try:
    s.start()
  except KeyboardInterrupt:
    s.stop()
