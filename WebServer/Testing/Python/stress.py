
import urllib

url = 'http://localhost:2016/slicer/threeD'
filePath = '/tmp/threeD.png'

for req in range(100):
  urllib.urlretrieve(url, filePath)
