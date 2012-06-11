$(function(){
 $('#sliceModeBar').data('selected', 'Axial');
 $('#Axial').click(function(event) {
   $('#sliceModeBar').data('selected', 'Axial');
   touchViewControl.draw(0);
   touchViewControl_2.draw(0);
   });
 $('#Sagittal').click(function(event) {
   $('#sliceModeBar').data('selected', 'Sagittal');
   touchViewControl.draw(0);
   touchViewControl_2.draw(0);
   });
 $('#Coronal').click(function(event) {
   $('#sliceModeBar').data('selected', 'Coronal');
   touchViewControl.draw(0);
   touchViewControl_2.draw(0);
   });
 $('#ThreeD').click(function(event) {
   $('#sliceModeBar').data('selected', 'ThreeD');
   touchViewControl.draw(0);
   touchViewControl_2.draw(0);
   });
});
