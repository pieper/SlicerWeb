import sys,os

class ServerHelper(object):
  """ This runs in a process that listens for web
  requests and then communicates with slicer as a parent
  program by communicating via stdio"""
  # TODO: set header so client knows that image refreshes are needed (avoid
  # using the &time=xxx trick)
  def __init__(self, docroot='.', logFile=None, port=8070, server_name='SlicerWebServer'):
    self.count = 0
    self.port = port
    self.server_name = server_name
    self.docroot = docroot
    self.logFile = logFile
    # use this as a mutex on the stdio connection
    self.communicatingWithSlicer = False

  def app(self, environ, start_response):
    """This is the actual app server that responds to web
    requests by creating cherrypy ResponseObject instances.
    http://www.cherrypy.org/wiki/ResponseObject
    """
    status = '200 OK'
    rest = environ['PATH_INFO'] 
    if os.path.dirname(rest).endswith('slicer'):
      self.logMessage('splitting path')
      rest = '/slicer/' + os.path.split(rest)[1]
    self.logMessage("path is: " + rest)
    if environ['QUERY_STRING'] != '':
      rest += "?" + environ['QUERY_STRING']
    self.logMessage("Handling: " + rest)
    if rest.find("/env") == 0:
      response_headers = [('Content-Type','text/plain')]
      start_response(status, response_headers)
      return [str(environ)]
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

  def logMessage(self,message):
    if self.logFile:
      fp = open(self.logFile, "a")
      fp.write(message + '\n')
      fp.close()

# When ServerHelper is run as a command line script, use
# this to start the server itself
if __name__ == '__main__':
  global serverHelper
  if len(sys.argv) > 1:
    docroot = sys.argv[1]
  logFile = "/tmp/helper.log"
  if len(sys.argv) > 2:
    logFile = sys.argv[2]
  serverHelper = ServerHelper(docroot=docroot, logFile=logFile, port=8070)
  try:
    serverHelper.start()
  except KeyboardInterrupt:
    serverHelper.stop()
