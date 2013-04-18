SlicerWeb
=========

Slicer modules that support web services and web applications.

*Note* this is still experimental and can't be used by normal people yet :)

Requires: PIL (see Experiments/slicr.sh for example installation
script).  Also requires python executable and distutils module in Slicer's
python.
These are available in a local slicer superbuild, but must be added manually if
you are using a binary download of slicer from slicer.org.


5/20/2012 dtc
=============
Starting integration to AWS instance. Next step is to hookup the locally running
Slicer to this repo


5/24/2012 sp
============
Can now access image data in nrrd format!

curl -v http://localhost:8070/slicer/volume\&id='MRHead' -o /tmp/local.nrrd
