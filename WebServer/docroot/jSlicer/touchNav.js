$(function(){
 $('#sliceModeBar').data('selected', 'Axial');
 $('#Axial').click(function(event) {
   $('#sliceModeBar').data('selected', 'Axial');
   touchViewControl.requestAndRender();
   touchViewControl_2.requestAndRender();
   });
 $('#Sagittal').click(function(event) {
   $('#sliceModeBar').data('selected', 'Sagittal');
   touchViewControl.requestAndRender();
   touchViewControl_2.requestAndRender();
   });
 $('#Coronal').click(function(event) {
   $('#sliceModeBar').data('selected', 'Coronal');
   touchViewControl.requestAndRender();
   touchViewControl_2.requestAndRender();
   });
 $('#ThreeD').click(function(event) {
   $('#sliceModeBar').data('selected', 'ThreeD');
   touchViewControl.requestAndRender();
   touchViewControl_2.requestAndRender();
   });
});
