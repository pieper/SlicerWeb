
import urllib
import time

url = 'http://localhost:2016/slicer/threeD'
url = 'http://quantome.org:2016/slicer/threeD'
filePath = '/tmp/threeD.png'
interval = 0

for req in range(100):
  startTime = time.time()
  urllib.urlretrieve(url, filePath)
  print "okay %d in %f" % (req, time.time() - startTime)
  time.sleep(interval)
