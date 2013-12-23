
var widgets = {};

$(function(){

  $('.slicerView').each(function(index,item) {
    options = {
      id:item.id,
      containerID: item.id,
      size: $.attr(item,'size') || 'native',
      view: $.attr(item,'view') || 'Red',
      doTouch: true
    };
    widgets[item.id] = new view( options );
  });

  // demo scene for testing
  var demoScene = 'slicer/preset?id=amigo-2012-07-02';


  $.get(demoScene, function(data){
    $.each(widgets, function(widget) {
      widgets[widget].requestAndRender();
    });
  });

});

