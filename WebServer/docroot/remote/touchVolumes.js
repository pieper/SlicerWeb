$(function(){
 $('#Next').click(function(event) {
   $.ajax({ url: "slicer/volume?cmd=Next" 
   }).done(function() {
     touchViewControl.draw(0);
   });
 });
 $('#Previous').click(function(event) {
   $.ajax({ url: "slicer/volume?cmd=Previous" 
   }).done(function() {
     touchViewControl.draw(0);
   });
 });
});
