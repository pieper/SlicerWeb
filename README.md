*Note* This repository was for development of the WebServer feature for [3D Slicer](https://slicer.org).  The feature has been merged into the [main repository](https://github.com/Slicer/Slicer/tree/main/Modules/Scripted/WebServer) and is being further developed there.

SlicerWeb
=========

Slicer modules that support web services and web applications.

(Still a work in progress, but starting to be useable)

Installation
============

This module can now be run from any slicer 4.2 binary download (release or nightly).

Simply run slicer with these arguments:

 ./path/to/Slicer --additional-module-paths path/to/SlicerWeb/WebServer

where 'path/to' is replaced with the appropriate paths.  You could alternatively
register the path/to/SlicerWeb/WebServer in the Module paths of the Application Settings dialog.

Usage
=====

Go to the Servers->WebServer module and the server will start.

Access http://localhost:8080 with a web browser.

NOTE: after you select a demo, use the Reload button to trigger it.

NOTE: some demos require a WebGL compatible browser.

Direct API access:
 
* get a json dump of the names of all nodes in mrml:

 http://localhost:8080/slicer/mrml

* get a png image of the threeD View

 http://localhost:8080/slicer/threeD

* get a png image of the yellow slice view

 http://localhost:8080/slicer/slice?view=yellow


5/24/2012 sp
============
Can now access image data in nrrd format!

curl -v http://localhost:8070/slicer/volume\&id='MRHead' -o /tmp/local.nrrd
