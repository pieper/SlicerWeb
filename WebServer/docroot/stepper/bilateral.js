class BilateralGenerator extends FilterGenerator {
  // Performs a bilateral filter
  // inputFields are:
  // - 0 grayscale image
  // outputFields are:
  // - 0 new filtered image
  constructor(options={}) {
    super(options);
  }

  updateProgram() {
    // recreate the program and textures for the current field list
    super.updateProgram();
    let gl = this.gl;
  }

  _fragmentShaderSource() {
    let radius = 9;
    let sigma_px = 4.0;
    console.log ( `Bilateral brute... radius = ${radius} sigma_px = ${sigma_px}` );
    return (`${this.headerSource()}

      // Bilateral
      //
      // Filter inputTexture0 using a bilateral filter.  This is a single pass algorithm,
      // with fixed sigmas for intensity and range.
      //


      // these are the function definitions for sampleVolume*
      // and transferFunction*
      // that define a field at a sample point in space
      ${function() {
          let perFieldSamplingShaderSource = '';
          this.inputFields.forEach(field=>{
            perFieldSamplingShaderSource += field.samplingShaderSource();
          });
          return(perFieldSamplingShaderSource);
        }.bind(this)()
      }

      // Number of pixels in each dimension
      uniform ivec3 pixelDimensions;

      // scaling between texture coordinates and pixels, i.e. 1/256.0
      uniform vec3 textureToPixel;

      // integer sampler for first input Field
      uniform isampler3D inputTexture0;

      // output into first Field
      layout(location = 0) out int value;

      // Coordinate of input location, could be resampled elsewhere.
      in vec3 interpolatedTextureCoordinate;

      // Radius
      const int r = ${radius};
      const float sigma_s = float(${sigma_px});
      const float sigma_r = 50.0;
      const float sigma_s2 = sigma_s * sigma_s;
      const float sigma_r2 = sigma_r * sigma_r;
      const float pi = 3.1415926535897932384626433832795;
      const float sqrt_2_pi = 2.5066282746310002;

      float gaussian ( float v, float sigma, float sigma_squared ) {
        float num = exp ( - ( v*v ) / ( 2.0 * sigma_squared ));
        float den = sqrt_2_pi * sigma;
        return num / den;
      }

      // From https://people.csail.mit.edu/sparis/bf_course/course_notes.pdf
      void doBilateralFilter()
      {
        float background = float(texture(inputTexture0, interpolatedTextureCoordinate).r);
        float v = 0.0;
        float w = 0.0;
        for (int i = -r; i <= r; i++) {
          for (int j = -r; j <= r; j++) {
            for (int k = -r; k <= r; k++) {
              vec3 offset_px = vec3(i,j,k);
              vec3 offset = offset_px * textureToPixel;
              vec3 neighbor = interpolatedTextureCoordinate + offset;
              float neighborStrength = float(texture(inputTexture0, neighbor).r);

              float ww = 0.0;
              ww = gaussian ( length(offset_px), sigma_s, sigma_s2 ) ;
              ww *= gaussian ( background - neighborStrength, sigma_r, sigma_r2 );
              w += ww;
              v += ww * neighborStrength;
            }
          }
        }
        v = v / w;
        value = int ( v );
      }
      void main()
      {
        doBilateralFilter();
      }
 
    `);
  }
}
