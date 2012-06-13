var touchView = function(options) {

    var self = {
        //
        // - bind events
        // - initialize variables
        //
        init: function() {
            // grab canvas element
            self.canvas = document.getElementById(options.id);
            self.ctxt = self.canvas.getContext("2d");
            self.container = document.getElementById(options.containerID);

            self.pan = {x: 0, y:0};
            self.zoom = 1;
            self.imageObj = new Image();

            self.canvas.style.width = '100%'
            self.canvas.width = self.canvas.offsetWidth;
            self.canvas.style.width = '';

            self.ctxt.canvas.width = self.container.scrollWidth;
            self.ctxt.canvas.height = window.innerHeight;

            self.canvas.addEventListener('touchstart', self.onTouchStart, false);
            self.canvas.addEventListener('touchmove', self.onTouchMove, false);
            self.canvas.addEventListener('touchend', self.onTouchEnd, false);
            self.canvas.addEventListener('mousedown', self.onMouseDown, false);
            self.canvas.addEventListener('mousemove', self.onMouseMove, false);
            self.canvas.addEventListener('mouseup', self.onMouseUp, false);

            self.mouseDragging = false;
            self.nextImageSource = "";
            self.requestingImage = false;

            self.view_color =
                typeof options.view !== 'undefined' ? options.view : "";
        },

        //
        // TOUCH events
        //
        onTouchStart: function(event) {

            // TODO: different behaviors based on multitouch
            $.each(event.touches, function(i, touch) {
            });
            self.requestAndRender({mode: 'start'});
            self.startX = (1. * event.touches[0].pageX);
            self.startY = (1. * event.touches[0].pageY);
            self.startTouches = event.touches;

            event.preventDefault();
        },

        onTouchMove: function(event) {

            if (event.touches.length == 1) {
              // single touch
              deltaX = (event.touches[0].pageX - self.startX) / self.ctxt.canvas.width;
              deltaY = (event.touches[0].pageY - self.startY) / self.ctxt.canvas.height;
              selection = $('#sliceModeBar').data('selected');
              if ( selection == 'ThreeD' ) {
                self.requestAndRender({mode: 'drag', orbitX: deltaX, orbitY: deltaY});
              } else {
                scrollTo = (1. * event.touches[0].pageY) / self.ctxt.canvas.height;
                self.requestAndRender({scrollTo: scrollTo, size: 'native'});

                if (typeof self.ganged_ViewControl !== 'undefined') {
                  self.ganged_ViewControl.requestAndRender({scrollTo: scrollTo, size: 'native'});
                }
              }
            } else {
              // multitouch (only look at first 2)
              startX = (self.startTouches[0].pageX + self.startTouches[1].pageX)/2.;
              startY = (self.startTouches[0].pageY + self.startTouches[1].pageY)/2.;
              nowX = (event.touches[0].pageX + event.touches[1].pageX)/2.;
              nowY = (event.touches[0].pageY + event.touches[1].pageY)/2.;
              self.pan.x = (nowX - self.startX);
              self.pan.y = (nowY - self.startY);
              self.render();
            }

            event.preventDefault();
        },

        onTouchEnd: function(event) {
            self.requestAndRender({force: true});
            event.preventDefault();
        },

        //
        // MOUSE events
        //
        onMouseDown: function(event) {

            self.mouseDragging = true;
            self.requestAndRender({mode: 'start'});
            self.startX = (1. * event.offsetX);
            self.startY = (1. * event.offsetY);
            event.preventDefault();
        },

        onMouseMove: function(event) {
            if (self.mouseDragging) {
              deltaX = (event.offsetX - self.startX) / self.ctxt.canvas.width;
              deltaY = (event.offsetY - self.startY) / self.ctxt.canvas.height;
              if ( selection == 'ThreeD' ) {
                self.requestAndRender({mode: 'drag', orbitX: deltaX, orbitY: deltaY});
              } else {
                scrollTo = (1. * event.offsetY) / self.ctxt.canvas.height;
                self.requestAndRender({scrollTo: scrollTo, size: 'native'});

                if (typeof self.ganged_ViewControl !== 'undefined') {
                  self.ganged_ViewControl.requestAndRender({scrollTo: scrollTo, size: 'native'});
                }
                event.preventDefault();
              }
            }
        },

        onMouseUp: function(event) {
            self.mouseDragging = false;
            self.requestAndRender({force: true});
            event.preventDefault();
        },

        //
        // Downloads and Drawing
        //

        stopDownloads: function() {
          //cancel image downloads
          if (window.stop !== undefined) {
            window.stop();
          }
          else if (document.execCommand !== undefined) {
            document.execCommand("Stop", false);
          }
        },

        render: function(args) {
            widthScale = self.ctxt.canvas.width / self.imageObj.width;
            heightScale = self.ctxt.canvas.height / self.imageObj.height;
            if (widthScale > heightScale) {
              scale = heightScale;
            } else {
              scale = widthScale;
            }
            drawWidth = scale * self.imageObj.width;
            drawHeight = scale * self.imageObj.height;
            margin = (self.ctxt.canvas.width - drawWidth) / 2;
            self.ctxt.clearRect( 0, 0, self.ctxt.canvas.width, self.ctxt.canvas.height );
            self.ctxt.drawImage( self.imageObj, self.pan.x + margin, self.pan.y + 0, self.zoom * drawWidth, self.zoom * drawHeight );
        },

        requestAndRender: function(args) {
          args = typeof args !== 'undefined' ? args : {};
          force = typeof args.force !== 'undefined' ? args.force : false;

          self.imageObj.onload = function() {
            self.render();
            if (self.nextImageSource != '') {
              self.requestingImage = true;
              self.imageObj.src = self.nextImageSource;
              self.nextImageSource = '';
            } else {
              self.requestingImage = false;
            }
          };

          var time = (new Date()).getTime();
          selection = $('#sliceModeBar').data('selected');

          if (self.view_color != "") {
            view = self.view_color;
          }

          if ( selection == 'ThreeD' ) {
            src = "slicer/threeD?view=1"
          } else {
            src = "slicer/slice?view=" + view + "&orientation=" + selection;

            if (typeof args.offset !== 'undefined') {
              src += "&offset=" + args.offset;
            }
            if (typeof args.scrollTo !== 'undefined') {
              src += "&scrollTo=" + args.scrollTo;
            }
          }

          if (typeof args.mode !== 'undefined') {
            src += "&mode=" + args.mode;
          }
          if (typeof args.size !== 'undefined') {
            src += "&size=" + args.size;
          }
          if (typeof args.orbitX !== 'undefined') {
            src += "&orbitX=" + args.orbitX;
          }
          if (typeof args.orbitY !== 'undefined') {
            src += "&orbitY=" + args.orbitY;
          }
          if (typeof args.panX !== 'undefined') {
            src += "&panX=" + args.panX;
          }
          if (typeof args.panY !== 'undefined') {
            src += "&panY=" + args.panY;
          }
          if (typeof args.zoom !== 'undefined') {
            src += "&zoom=" + args.zoom;
          }
          if (typeof args.roll !== 'undefined') {
            src += "&roll=" + args.roll;
          }
          src += "&time=" + time;
          src += "&fmt=" + "png";

          if ( force ) {
            //self.stopDownloads();
            self.nextImageSource == '';
          }
          if ( !self.requestingImage ) {
            self.requestingImage = true;
            self.imageObj.src = src;
            self.nextImageSource = '';
          } else {
            self.nextImageSource = src;
          }
        },
    };

    self.init();
    return self;
};


var touchViewControl;
var touchViewControl_2;

$(function(){
  touchViewControl = new touchView( {
    id:"touchView",
    containerID: "touchViewContainer",
    size: 'native',
    view: "Red"
  });

  touchViewControl_2 = new touchView( {
    id:"touchView_2",
    containerID: "touchViewContainer_2",
    size: 'native',
    view: "Yellow"
  });

  touchViewControl.ganged_ViewControl = touchViewControl_2;
  touchViewControl_2.ganged_ViewControl = touchViewControl;

  $.get('slicer/preset?id=compareView', function(data){
    touchViewControl.requestAndRender();
    touchViewControl_2.requestAndRender();
  });
});
