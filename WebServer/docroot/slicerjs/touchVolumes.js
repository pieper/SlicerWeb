$(function(){
 $('#Next').click(function(event) {
   $.ajax({ url: "slicer/volumeSelection?cmd=Next"
   }).done(function() {
     touchViewControl.requestAndRender();
   });
 });
 $('#Previous').click(function(event) {
   $.ajax({ url: "slicer/volumeSelection?cmd=Previous"
   }).done(function() {
     touchViewControl.requestAndRender();
   });
 });
});
