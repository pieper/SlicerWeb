import string,cgi,time
import os,sys

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
from urlparse import urlparse

class SlicerRequestHandler(SimpleHTTPRequestHandler):

  def start_response(self, status, response_headers):
    self.send_response(status)
    for keyword,value in response_headers:
      self.send_header(keyword, value)
    self.end_headers()

  def logMessage(self, message):
     self.server.logMessage(message)


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
      if self.server.communicatingWithSlicer:
        # But we're busy ... write response and return
        response_headers = [('Content-Type','text/plain')]
        self.logMessage('Server busy')
        self.start_response(status, response_headers)
        self.wfile.write( 'Busy' )
        return

      # Now we're talking to Slicer...
      URL = urlparse( rest )
      ACTION = os.path.basename( URL.path )
      self.logMessage('Parsing url, action is {' + ACTION +
        '} query is {' + URL.query + '}')

      # and do the write to stdout / Slicer:stdin
      self.server.communicatingWithSlicer = True
      sys.stdout.write( "/" + ACTION + "?"+ URL.query + "\n")
      sys.stdout.flush()

      # and read back from stdin / Slicer:stdout
      count = int(sys.stdin.readline())
      self.logMessage('Trying to read %d bytes from Slicer stdin ...' % count)
      body = sys.stdin.read(count)
      self.logMessage("  [done]")
      self.server.communicatingWithSlicer = False

      response_headers = [('Content-length', str(count))]

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

    except:
      self.send_error(404, "File not found")

    # end do_GET


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


      comment = """
      ctype, pdict = cgi.parse_header(self.headers.getheader('content-type'))
      if ctype == 'multipart/form-data':
        query=cgi.parse_multipart(self.rfile, pdict)
        self.send_response(301)
        self.end_headers()
        upfilecontent = query.get('upfile')
        # print "filecontent", upfilecontent[0]
        self.wfile.write("<HTML>PUT OK.<BR><BR>");
        self.wfile.write(upfilecontent[0]);
        """
      xx = """
          if environ['REQUEST_METHOD'] == 'PUT':
            #TODO
            self.logMessage("got a PUT")
            body = cherrypy.request.body.read()
            self.logMessage("body is: %s" % body)
      """
    except :
        self.server.logMessage('could not PUT')

  def do_POST(self):
    #TODO
    pass


class SlicerHTTPServer(HTTPServer):
  """ This runs in a process that listens for web
  requests and then communicates with slicer as a parent
  program by communicating via stdio"""
  # TODO: set header so client knows that image refreshes are needed (avoid
  # using the &time=xxx trick)
  def __init__(self, server_address=("",8070), RequestHandlerClass=SlicerRequestHandler, docroot='.', logFile=None):
    HTTPServer.__init__(self,server_address, RequestHandlerClass)
    self.docroot = docroot
    self.logFile = logFile
    # use this as a mutex on the stdio connection
    self.communicatingWithSlicer = False

  def start(self):
    """start the server
    - use one thread since we are going to communicate 
    via stdin/stdout, which will get corrupted with more threads
    """
    try:
      self.logMessage('started httpserver...')
      self.serve_forever()
    except KeyboardInterrupt:
      self.logMessage('KeyboardInterrupt - stopping')
      self.stop()

  def stop(self):
    self.socket.close()

  def logMessage(self,message):
    if self.logFile:
      fp = open(self.logFile, "a")
      fp.write(message + '\n')
      fp.close()

if __name__ == '__main__':
  if len(sys.argv) > 1:
    docroot = sys.argv[1]
  logFile = "/tmp/helper.log"
  if len(sys.argv) > 2:
    logFile = sys.argv[2]
  server = SlicerHTTPServer(docroot=docroot,logFile=logFile)
  server.start()
