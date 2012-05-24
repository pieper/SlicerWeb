$(function(){
 $('#Next').click(function(event) {
   $.ajax({ url: "slicer/volumeSelection?cmd=Next" 
   }).done(function() {
     touchViewControl.draw(0);
   });
 });
 $('#Previous').click(function(event) {
   $.ajax({ url: "slicer/volumeSelection?cmd=Previous" 
   }).done(function() {
     touchViewControl.draw(0);
   });
 });
});
