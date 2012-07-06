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

            self.zoom = 1;
            self.pan = {x: 0, y: 0};
            self.zoomCenter = {x: 0, y: 0};

            self.imageObj = new Image();

            self.canvas.style.width = '100%'
            self.canvas.width = self.canvas.offsetWidth;
            self.canvas.style.width = '';

            self.ctxt.canvas.width = self.container.scrollWidth;
            self.ctxt.canvas.height = window.innerHeight;

            if (options.doTouch) {
              self.canvas.addEventListener('touchstart', self.onTouchStart, false);
              self.canvas.addEventListener('touchmove', self.onTouchMove, false);
              self.canvas.addEventListener('touchend', self.onTouchEnd, false);
            };
            self.canvas.addEventListener('mousedown', self.onMouseDown, false);
            self.canvas.addEventListener('mousemove', self.onMouseMove, false);
            self.canvas.addEventListener('mouseup', self.onMouseUp, false);

            self.mouseDragging = false;
            self.nextImageSource = "";
            self.requestingImage = false;

            self.view = options.view;
            self.view_color =
                typeof options.view !== 'undefined' ? options.view : "";
        },

        //
        // TOUCH events
        //
        onTouchStart: function(event) {
            $.each(event.touches, function(i, touch) {
            });

            _log =  "Start: " + event.touches.length + ", ";

            self.startTime = new Date().getTime();

            if (event.touches.length == 1) {
              self.startMode = 1;
              self.startX = (1. * event.touches[0].pageX);
              self.startY = (1. * event.touches[0].pageY);
              self.requestAndRender({mode: 'start'});

              _log +=  self.startX + ", " + self.startY;
            } else {
              self.startMode = 2;
              self.startX = (event.touches[0].pageX + event.touches[1].pageX)/2.;
              self.startY = (event.touches[0].pageY + event.touches[1].pageY)/2.;

              self.startX -= self.canvas.offsetLeft;
              self.startY -= self.canvas.offsetTop;

              dx = event.touches[0].pageX - event.touches[1].pageX;
              dy = event.touches[0].pageY - event.touches[1].pageY;
              self.startDist = Math.sqrt( dx*dx + dy*dy );
              self.startZoom = self.zoom;
              self.startPan = self.pan;

              prev_ZC_x = self.zoomCenter.x;
              prev_ZC_y = self.zoomCenter.y;

              self.zoomCenter = {
                x: (self.startX + (self.startZoom * prev_ZC_x) - prev_ZC_x - self.startPan.x ) / self.startZoom,
                y: (self.startY + (self.startZoom * prev_ZC_y) - prev_ZC_y - self.startPan.y ) / self.startZoom
              };

              _log +=  self.startX + ", " + self.startY + ", " +
                      dx + ", " + dy + ", " + self.startDist + ", " + self.startZoom;
            }

            // $("#log").html( _log );
            event.preventDefault();
        },

        onTouchMove: function(event) {

            if (self.startMode == 1) {
              // single touch
              deltaX = (event.touches[0].pageX - self.startX) / self.ctxt.canvas.width;
              deltaY = (event.touches[0].pageY - self.startY) / self.ctxt.canvas.height;
              selection = $('#sliceModeBar').data('selected');
              if ( selection == 'ThreeD' ) {
                self.requestAndRender({mode: 'drag', orbitX: deltaX, orbitY: deltaY});
              } else {
                if ( false ) {
                  // scrollTo mode
                  scrollTo = (1. * event.touches[0].pageY) / self.ctxt.canvas.height;
                  scrollTo = scrollTo.toFixed(2);
                  self.requestAndRender({scrollTo: scrollTo, size: 'native'});
                } else {
                  // offset mode
                  offset = 30 * deltaY;
                  self.requestAndRender({offset: offset, size: 'native'});
                }

                if (typeof self.ganged_ViewControl !== 'undefined') {
                  self.ganged_ViewControl.requestAndRender({copySliceGeometryFrom: self.view, size: 'native'});
                }
              }
            } else {
              // multitouch (only look at first 2 touch points)
              nowX = (event.touches[0].pageX + event.touches[1].pageX)/2.;
              nowY = (event.touches[0].pageY + event.touches[1].pageY)/2.;

              nowX -= self.canvas.offsetLeft;
              nowY -= self.canvas.offsetTop;

              self.pan = {
                x: (nowX - self.startX) + self.startPan.x,
                y: (nowY - self.startY) + self.startPan.y
              };

              dx = event.touches[0].pageX - event.touches[1].pageX;
              dy = event.touches[0].pageY - event.touches[1].pageY;
              nowDist = Math.sqrt( dx*dx + dy*dy );

              self.zoom = self.startZoom * nowDist / self.startDist;

              panZoom = {pan: self.pan, zoom: self.zoom, zoomCenter: self.zoomCenter};

              self.setPanZoom(panZoom);
              self.render();

              if (typeof self.ganged_ViewControl !== 'undefined') {
                self.ganged_ViewControl.setPanZoom(panZoom);
                self.ganged_ViewControl.render();
              }
            }

            event.preventDefault();
        },

        onTouchEnd: function(event) {
            if (event.touches.length == 1) {
              // single touch
            } else {
              // multitouch
            }
            endTime = new Date().getTime();
            if ((endTime - self.startTime) < 100) {
              self.zoom = 1;
              self.pan = {x: 0, y: 0};
              self.zoomCenter = {x: 0, y: 0};

              panZoom = {pan: self.pan, zoom: self.zoom, zoomCenter: self.zoomCenter};
              self.setPanZoom(panZoom);

              if (typeof self.ganged_ViewControl !== 'undefined') {
                self.ganged_ViewControl.setPanZoom(panZoom);
              }
            }

            self.render();
            if (typeof self.ganged_ViewControl !== 'undefined') {
              self.ganged_ViewControl.render();
            }
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
                scrollTo = scrollTo.toFixed(2);
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

        setPanZoom: function(args) {
          if (typeof args.pan === 'undefined') {
            args.pan = {x: 0, y: 0};
          }
          if (typeof args.zoomCenter === 'undefined') {
            args.zoomCenter = {x: 0, y: 0};
          }
          if (typeof args.zoom === 'undefined') {
            args.zoom = 1;
          }
          z = args.zoom;
          x = args.zoomCenter.x;
          y = args.zoomCenter.y;
          px = args.pan.x;
          py = args.pan.y;

          // set attributes for "ganged" viewControl
          self.zoom = args.zoom;
          self.zoomCenter.x = args.zoomCenter.x;
          self.zoomCenter.y = args.zoomCenter.y;
          self.pan.x = px;
          self.pan.y = py;

          self.ctxt.setTransform( z,0, 0,z, -z*(x)+x+px,-z*(y)+y+py );
        },

        render: function(args) {
          if (self.requestingImage) {
            // don't render incomplete imageObj - it will be white
            // It will be rendered when load is completed (see onload)
            return;
          }
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
          self.ctxt.save();
          self.ctxt.setTransform( 1,0, 0,1, 0,0 );
          self.ctxt.clearRect( 0, 0, self.ctxt.canvas.width, self.ctxt.canvas.height );
          self.ctxt.restore();
          self.ctxt.drawImage( self.imageObj, /* margin */ 0, 0, drawWidth, drawHeight );
        },

        onLoaded: function() {
          self.requestingImage = false;
          self.render();
          if (self.nextImageSource != '') {
            self.requestingImage = true;
            self.imageObj.src = self.nextImageSource;
            self.nextImageSource = '';
          }
        },

        requestAndRender: function(args) {
          args = typeof args !== 'undefined' ? args : {};
          force = typeof args.force !== 'undefined' ? args.force : false;


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
            if (typeof args.copySliceGeometryFrom !== 'undefined') {
              src += "&copySliceGeometryFrom=" + args.copySliceGeometryFrom;
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
            self.nextImageSource = '';
            self.imageObj.onload = self.onLoaded;
            self.imageObj.src = src;
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
    view: "Red",
    doTouch: true
  });

  touchViewControl_2 = new touchView( {
    id:"touchView_2",
    containerID: "touchViewContainer_2",
    size: 'native',
    view: "Yellow",
    doTouch: true
  });

  touchViewControl.ganged_ViewControl = touchViewControl_2;
  touchViewControl_2.ganged_ViewControl = touchViewControl;

  $.get('slicer/preset?id=amigo-2012-07-02', function(data){
    touchViewControl.requestAndRender();
    touchViewControl_2.requestAndRender(
                        {copySliceGeometryFrom: touchViewControl.view});
  });
});
