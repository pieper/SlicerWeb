class GrowCutGenerator extends ProgrammaticGenerator {
  // Performs on iteration of GrowCut.
  // inputFields are:
  // - 0 grayscale image
  // - 1 current label image
  // - 2 current strength image
  // outputFields are:
  // - 0 new label image
  // - 1 new strength image
  constructor(options={}) {
    super(options);
    this.uniforms.iteration = { type: '1i', value: 0 };
    this.uniforms.iterations = { type: '1i', value: 0 };
  }

  updateProgram() {
    // recreate the program and textures for the current field list
    super.updateProgram();
    let gl = this.gl;
  }

  _fragmentShaderSource() {
    return (`${this.headerSource()}
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

      #define MAX_STRENGTH 10000

      uniform int iterations;
      uniform int iteration;
      uniform ivec3 pixelDimensions;
      uniform vec3 textureToPixel;
      uniform float slice;

      uniform isampler3D inputTexture0; // background
      uniform isampler3D inputTexture1; // label
      uniform isampler3D inputTexture2; // strength

      in vec3 interpolatedTextureCoordinate;

      layout(location = 0) out int label;
      layout(location = 1) out int strength;

      void main()
      {
        ivec3 size = textureSize(inputTexture0, 0);
        vec3 coordinate = vec3(interpolatedTextureCoordinate.st, slice);
        ivec3 texelIndex = ivec3(floor(coordinate * vec3(size)));

        int background = texelFetch(inputTexture0, texelIndex, 0).r;
        label = texelFetch(inputTexture1, texelIndex, 0).r;

        if (iteration == 0) {
          if (label > 0) {
            strength = MAX_STRENGTH;
          } else {
            strength = 0;
          }
        } else {
          strength = texelFetch(inputTexture2, texelIndex, 0).r;
          for (int k = -1; k <= 1; k++) {
            for (int j = -1; j <= 1; j++) {
              for (int i = -1; i <= 1; i++) {
                if ( !(i == 0 && j == 0 && k == 0) ) {
                  ivec3 neighborIndex = texelIndex + ivec3(i,j,k);
                  int neighborBackground = texelFetch(inputTexture0, neighborIndex, 0).r;
                  int neighborStrength = texelFetch(inputTexture2, neighborIndex, 0).r;
                  int strengthCost = abs(neighborBackground - background);
                  int takeoverStrength = neighborStrength - strengthCost;
                  if (takeoverStrength > strength) {
                    strength = takeoverStrength;
                    label = texelFetch(inputTexture1, neighborIndex, 0).r;
                  }
                }
              }
            }
          }
        }
      }
    `);
  }
}
