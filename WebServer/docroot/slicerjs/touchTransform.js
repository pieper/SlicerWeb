var touchTransform = function(options) {

    var self = {
        //
        // - bind events
        // - initialize variables
        //
        init: function() {
            // grab canvas element
            self.log(options.id);
            self.canvas = document.getElementById(options.id);
            self.ctxt = self.canvas.getContext("2d");
            self.container = document.getElementById(options.containerID);

            self.canvas.style.width = '100%'
            self.canvas.width = self.canvas.offsetWidth;
            self.canvas.style.width = '';

            self.ctxt.canvas.width = self.container.scrollWidth;
            self.ctxt.canvas.height = window.innerHeight;

            self.canvas.addEventListener('touchstart', self.onTouchStart, false);
            self.canvas.addEventListener('touchmove', self.onTouchMove, false);
            self.canvas.addEventListener('touchend', self.onTouchEnd, false);
        },

        //
        // TOUCH events
        //
        onTouchStart: function(event) {
            if (event.touches.length == 1) {
              // single touch
            } else {
              // multitouch (only look at first 2 touch points)
              self.startX = (event.touches[0].pageX + event.touches[1].pageX)/2.;
              self.startX = (event.touches[0].pageY + event.touches[1].pageY)/2.;
              dx = event.touches[0].pageX - event.touches[1].pageX;
              dy = event.touches[0].pageY - event.touches[1].pageY;
              self.startDist = Math.sqrt( dx*dx + dy*dy );
              self.startZoom = self.zoom;
            }
            event.preventDefault();
        },

        onTouchMove: function(event) {
            if (event.touches.length == 1) {
              // single touch
            } else {
              // multitouch (only look at first 2 touch points)
              nowX = (event.touches[0].pageX + event.touches[1].pageX)/2.;
              nowY = (event.touches[0].pageY + event.touches[1].pageY)/2.;
              pan = {x: (nowX - self.startX), y: (nowY - self.startY)};

              dx = event.touches[0].pageX - event.touches[1].pageX;
              dy = event.touches[0].pageY - event.touches[1].pageY;
              nowDist = Math.sqrt( dx*dx + dy*dy );

              self.zoom = self.startZoom * nowDist / self.startDist;

              zoomCenter = {x: nowX, y: nowY};
              panZoom = {pan: pan, zoom: self.zoom, zoomCenter: zoomCenter};
              self.setPanZoom(panZoom);
              self.render();
            }

            event.preventDefault();
        },

        onTouchEnd: function(event) {
            if (event.touches.length == 1) {
              // single touch
            } else {
              // multitouch
            }
            event.preventDefault();
        },

        log: function(message) {
          console.log(message);
          $('#log').html(message);
        },
    };

    self.init();
    return self;
};


var touchTransformControl;

$(function(){
  touchTransformControl = new touchTransform( {
    id:"touchTransform",
    containerID: "touchTransformContainer",
  });

  $.get('slicer/preset?id=transform', function(data){
    // TODO: have a wait animation that gets cleared here...
  });
});
