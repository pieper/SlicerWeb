#!/bin/bash

SLICER_SUPERBUILD="${HOME}/slicer4/latest/Slicer-superbuild"
SLICER_BUILD="${SLICER_SUPERBUILD}/Slicer-build"
PYTHONEXE="${SLICER_SUPERBUILD}/python-build/bin/python"
LAUNCH="${SLICER_BUILD}/Slicer --launcher-no-splash --launch"
PYTHON="${LAUNCH} ${PYTHONEXE}"


tmpdir=`mktemp -d /tmp/slicr.XXXX`
echo ${tmpdir}
cd ${tmpdir}
hg clone https://bitbucket.org/cherrypy/cherrypy
cd cherrypy
${PYTHON} setup.py install

cd ${tmpdir}
#curl -O http://effbot.org/downloads/Imaging-1.1.7.tar.gz
curl -O http://boggs.bwh.harvard.edu/tmp/Imaging-1.1.7.tar.gz
tar xvfz Imaging-1.1.7.tar.gz
cd Imaging-1.1.7
${PYTHON} setup.py install
