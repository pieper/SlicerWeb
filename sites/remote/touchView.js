var touchView = function(options) {
    // grab canvas element
    var canvas = document.getElementById(options.id),
        ctxt = canvas.getContext("2d"),
        container = document.getElementById(options.containerID);
        
    canvas.style.width = '100%'
    canvas.width = canvas.offsetWidth;
    canvas.style.width = '';

    ctxt.canvas.width = container.scrollWidth;
    ctxt.canvas.height = window.innerHeight;

    var self = {
        //
        // - bind events
        // - initialize variables
        //
        init: function() {
            canvas.addEventListener('touchstart', self.onTouchStart, false);
            canvas.addEventListener('touchmove', self.onTouchMove, false);
            canvas.addEventListener('touchend', self.onTouchEnd, false);
            canvas.addEventListener('mousedown', self.onMouseDown, false);
            canvas.addEventListener('mousemove', self.onMouseMove, false);
            canvas.addEventListener('mouseup', self.onMouseUp, false);

            self.mouseDragging = false;
            self.nextImageSource = "";
        },

        //
        // TOUCH events
        //
        onTouchStart: function(event) {

            // TODO: different behaviors based on multitouch
            $.each(event.touches, function(i, touch) {
            });
            self.draw({mode: 'start'});
            self.startX = (1. * event.touches[0].pageX);
            self.startY = (1. * event.touches[0].pageY);

            event.preventDefault();
        },

        onTouchMove: function(event) {

            deltaX = (event.touches[0].pageX - self.startX) / ctxt.canvas.width;
            deltaY = (event.touches[0].pageY - self.startY) / ctxt.canvas.height;
            selection = $('#sliceModeBar').data('selected');
            if ( selection == 'ThreeD' ) {
              self.draw({mode: 'drag', orbitX: deltaX, orbitY: deltaY});
            } else {
              scrollTo = (1. * event.touches[0].pageY) / ctxt.canvas.height;
              self.draw({scrollTo: scrollTo, size: 256});
            }

            event.preventDefault();
        },

        onTouchEnd: function(event) {
            self.draw({force: true});
            event.preventDefault();
        },

        //
        // MOUSE events
        //
        onMouseDown: function(event) {

            self.mouseDragging = true;
            self.draw({mode: 'start'});
            self.startX = (1. * event.offsetX);
            self.startY = (1. * event.offsetY);
            event.preventDefault();
        },

        onMouseMove: function(event) {
            if (self.mouseDragging) {
              deltaX = (event.offsetX - self.startX) / ctxt.canvas.width;
              deltaY = (event.offsetY - self.startY) / ctxt.canvas.height;
              if ( selection == 'ThreeD' ) {
                self.draw({mode: 'drag', orbitX: deltaX, orbitY: deltaY,size: 10});
              } else {
                scrollTo = (1. * event.offsetY) / ctxt.canvas.height;
                self.draw({scrollTo: scrollTo, size: 256});
                event.preventDefault();
              }
            }
        },

        onMouseUp: function(event) {
            self.mouseDragging = false;
            self.draw({force: true});
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

        draw: function(args) {
          args = typeof args !== 'undefined' ? args : {};
          force = typeof args.force !== 'undefined' ? args.force : false;

          var imageObj = new Image();

          imageObj.onload = function() {
            widthScale = ctxt.canvas.width / imageObj.width;
            heightScale = ctxt.canvas.height / imageObj.height;
            if (widthScale > heightScale) {
              scale = heightScale;
            } else {
              scale = widthScale;
            }
            drawWidth = scale * imageObj.width;
            drawHeight = scale * imageObj.height;
            margin = (ctxt.canvas.width - drawWidth) / 2;
            ctxt.clearRect( 0, 0, ctxt.canvas.width, ctxt.canvas.height );
            ctxt.drawImage( imageObj, margin, 0, drawWidth, drawHeight );
            if (self.nextImageSource != '') {
              imageObj.src = self.nextImageSource;
              self.nextImageSource = '';
            }
          };      

          var time = (new Date()).getTime();
          view = "Red"
          selection = $('#sliceModeBar').data('selected');
          if ( selection == 'Axial' ) view = 'Red';
          if ( selection == 'Sagittal' ) view = 'Yellow';
          if ( selection == 'Coronal' ) view = 'Green';
          if ( selection == 'ThreeD' ) view = 'ThreeD';

          if ( selection == 'ThreeD' ) {
            src = "slicer/threeD?view=1"
          } else {
            src = "slicer/slice?view=" + view 

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
            self.stopDownloads();
            self.nextImageSource == '';
          }
          if ( self.nextImageSource == '' ) {
            imageObj.src = src;
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
$(function(){
  touchViewControl = new touchView({id:"touchView", containerID: "touchViewContainer", size: 15 }); 
  touchViewControl.draw();
});
