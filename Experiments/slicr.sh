#!/bin/bash

# might also need:
# sudo apt-get build-dep python-imaging
# sudo apt-get install mercurial

# on ubuntu:
# sudo ln -s /usr/lib/x86_64-linux-gnu/libz.so /usr/lib

# for a superbuild:
SLICER_SUPERBUILD="${HOME}/slicer4/latest/Slicer-superbuild"
if [ -e ${SLICER_SUPERBUILD} ]; then
  SLICER_BUILD="${SLICER_SUPERBUILD}/Slicer-build"
  PYTHONEXE="${SLICER_SUPERBUILD}/python-build/bin/python"
  LAUNCH="${SLICER_BUILD}/Slicer --launcher-no-splash --launch"
  PYTHON="${LAUNCH} ${PYTHONEXE}"
fi

# for an installation:
SLICER_INSTALL="/extra/pieper/Slicer-4.1.0-linux-amd64"
if [ -e ${SLICER_INSTALL} ]; then
  PYTHONEXE="${SLICER_INSTALL}/bin/python"
  LAUNCH="${SLICER_INSTALL}/Slicer --launcher-no-splash --launch"
  PYTHON="${LAUNCH} ${PYTHONEXE}"
fi

tmpdir=`mktemp -d /tmp/slicr.XXXX`

cd ${tmpdir}
git clone git@github.com:pieper/Pillow.git
cd Pillow
${PYTHON} setup.py install

### not used
# echo ${tmpdir}
# cd ${tmpdir}
# hg clone https://bitbucket.org/cherrypy/cherrypy
# cd cherrypy
# ${PYTHON} setup.py install

# cd ${tmpdir}
# #curl -O http://effbot.org/downloads/Imaging-1.1.7.tar.gz
# curl -O http://boggs.bwh.harvard.edu/tmp/Imaging-1.1.7.tar.gz
# tar xvfz Imaging-1.1.7.tar.gz
# cd Imaging-1.1.7
# ${PYTHON} setup.py install
