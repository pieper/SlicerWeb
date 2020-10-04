# This is a custom script for working with Lauren O'Donnell's clustered
# tract files generated with SlicerDMRI (as of 2017-08-01)


import os
import WebServer

# update this with the path to your output
exportDirectory = '/Volumes/encrypted/data/AG/AG1622-SlicerWeb/tracts'

tracts = ['AF', 'CST_M1', 'IFOF', 'ILF', 'UF'];
targetTubeCount = 100

for tract in tracts:
    tubeNodes = slicer.util.getNodes('vtkMRMLFiberBundleTubeDisplayNode*', useLists=True).values()
    for tubeNode in tubeNodes[0]:
        tubeNode.SetVisibility(0)
    node = slicer.util.getNode(tract+'*')
    clusters = vtk.vtkCollection()
    node.GetChildrenDisplayableNodes(clusters)
    for clusterIndex in range(clusters.GetNumberOfItems()):
        cluster = clusters.GetItemAsObject(clusterIndex)
        tubeNode = cluster.GetNthDisplayNode(1)
        tubeNode.SetVisibility(1)
    slicer.util.delayDisplay(tract, 100)
    exporter = WebServer.glTFExporter(slicer.mrmlScene)
    exporter.targetTubeCount = targetTubeCount
    outPath = os.path.join(exportDirectory, tract+".gltf")
    fp = open(outPath, 'w');
    fp.write(exporter.export())
    fp.close()

slicer.util.delayDisplay("done")


# You need to run this in a version of Slicer with SlicerDMRI installed.
#
# Also, use this work-in-progress scripted module web server
# https://github.com/pieper/SlicerWeb/blob/master/WebServer/WebServer.py
#
# then start Slicer like this:
startSlicer  """

/Applications/Slicer-4.7.0-2017-05-29.app/Contents/MacOS/Slicer --additional-module-paths ~/slicer4/latest/SlicerWeb/WebServer/

"""

# load the clustered mrml file and turn off visibility of all lines
# leave models visible that you want included in the scene.
#
# then paste the command below into the python interactor
toRun = """

execfile('/Users/pieper/slicer4/latest/SlicerWeb/Experiments/AG-export.py')

"""

# place this in a file named index.html and then put the exported tracts
# into a subdirectory called 'tracts'
indexDotHTML = """

<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <script src="https://aframe.io/releases/0.6.1/aframe.min.js"></script>
    <script src="https://cdn.rawgit.com/tizzle/aframe-orbit-controls-component/v0.1.12/dist/aframe-orbit-controls-component.min.js"></script>
  </head>
  <body>


    <input id='AFcb' type="checkbox" disabled='true'>AF</input>
    <input id='CST_M1cb' type="checkbox" disabled='true'>CST_M1</input>
    <input id='IFOFcb' type="checkbox" disabled='true'>IFOF</input>
    <input id='ILFcb' type="checkbox" disabled='true'>ILF</input>
    <input id='UFcb' type="checkbox" disabled='true'>UF</input>
    <label id='status'>Waiting for downloads...</label>

    <a-scene >
      <a-entity
          id="camera"
          camera="fov: 80; zoom: 1;"
          position="0 0 2"
          orbit-controls="
              autoRotate: false;
              target: #target;
              enableDamping: true;
              dampingFactor: 0.125;
              rotateSpeed:0.25;
              minDistance:1;
              maxDistance:100;
              "
          >

      </a-entity>

      <!--
      -->
      <a-entity id="target">
        <a-entity id="tracts" position="0 0 0" scale="15 15 15" rotation="-90 180 0">
          <a-gltf-model id='AF' src="tracts/AF.gltf"></a-gltf-model>
          <a-gltf-model id='CST_M1' src="tracts/CST_M1.gltf"></a-gltf-model>
          <a-gltf-model id='IFOF' src="tracts/IFOF.gltf"></a-gltf-model>
          <a-gltf-model id='ILF' src="tracts/ILF.gltf"></a-gltf-model>
          <a-gltf-model id='UF' src="tracts/UF.gltf"></a-gltf-model>
        </a-entity>
      </a-entity>
      <a-sky color="#ECECEC"></a-sky>
    </a-scene>

    <script>
      var tracts = ['AF', 'CST_M1', 'IFOF', 'ILF', 'UF'];
      document.addEventListener("DOMContentLoaded", function(event) {
        var downloadCount = 0;
        tracts.forEach(tract => {
          var entity = document.getElementById(tract);
          var checkbox = document.getElementById(tract+'cb');
          var status = document.getElementById('status');
          checkbox.addEventListener('change', function() {
            entity.object3D.visible = checkbox.checked;
          });
          entity.addEventListener('model-loaded', function() {
            checkbox.checked = true;
            checkbox.disabled = false;
            downloadCount += 1;
            if (downloadCount != tracts.length) {
              status.textContent = `Downloaded ${downloadCount} of ${tracts.length}`;
            } else {
              status.textContent = '';
            }
          });
        });

      })
    </script>

  </body>
</html>


"""

