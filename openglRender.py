from mm import importObj, rotMat2angle, Bunch
from OpenGL.GL import *
from OpenGL.GLUT import *
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

# Global variables
shaderProgram = None
vertexBufferObject = None
indexBufferObject = None
framebufferObject = None
vertexArrayObject = None

# Strings containing shader programs written in GLSL
vertexShaderString = """
#version 330

layout(location = 0) in vec3 windowCoordinates;
layout(location = 1) in vec3 vertexColor;

smooth out vec3 fragmentColor;

uniform mat4 windowToClipMat;

void main()
{
    gl_Position = windowToClipMat * vec4(windowCoordinates, 1.0f);
    fragmentColor = vertexColor;
}
"""

fragmentShaderString = """
#version 330

smooth in vec3 fragmentColor;

out vec4 pixelColor;

void main()
{
    pixelColor = vec4(fragmentColor, 1.);
}
"""

def initializeShaders(shaderDict):
    """
    Compiles each shader defined in shaderDict, attaches them to a program object, and links them (i.e., creates executables that will be run on the vertex, geometry, and fragment processors on the GPU). This is more-or-less boilerplate.
    """
    shaderObjects = []
    global shaderProgram
    shaderProgram = glCreateProgram()
    
    for shaderType, shaderString in shaderDict.items():
        shaderObjects.append(glCreateShader(shaderType))
        glShaderSource(shaderObjects[-1], shaderString)
        
        glCompileShader(shaderObjects[-1])
        status = glGetShaderiv(shaderObjects[-1], GL_COMPILE_STATUS)
        if status == GL_FALSE:
            if shaderType is GL_VERTEX_SHADER:
                strShaderType = "vertex"
            elif shaderType is GL_GEOMETRY_SHADER:
                strShaderType = "geometry"
            elif shaderType is GL_FRAGMENT_SHADER:
                strShaderType = "fragment"
            raise RuntimeError("Compilation failure (" + strShaderType + " shader):\n" + glGetShaderInfoLog(shaderObjects[-1]).decode('utf-8'))
        
        glAttachShader(shaderProgram, shaderObjects[-1])
    
    glLinkProgram(shaderProgram)
    status = glGetProgramiv(shaderProgram, GL_LINK_STATUS)
    
    if status == GL_FALSE:
        raise RuntimeError("Link failure:\n" + glGetProgramInfoLog(shaderProgram).decode('utf-8'))
        
    for shader in shaderObjects:
        glDetachShader(shaderProgram, shader)
        glDeleteShader(shader)

def windowToClip(width, height, zNear, zFar):
    """
    Creates elements for an OpenGL-style column-based homogenous transformation matrix that maps points from window space to clip space.
    """
    windowToClipMat = np.zeros(16, dtype = np.float32)
    windowToClipMat[0] = 2 / width
    windowToClipMat[3] = -1
    windowToClipMat[5] = 2 / height
    windowToClipMat[7] = -1
    windowToClipMat[10] = 2 / (zFar - zNear)
    windowToClipMat[11] = -(zFar + zNear) / (zFar - zNear)
    windowToClipMat[15] = 1
    
    return windowToClipMat

def configureShaders(var):
    """
    Modifies the window-to-clip space transform matrix in the vertex shader, but you can use this to configure your shaders however you'd like, of course.
    """
    # Grabs the handle for the uniform input from the shader
    windowToClipMatUnif = glGetUniformLocation(shaderProgram, "windowToClipMat")
    
    # Get input parameters to define a matrix that will be used as the uniform input
    width, height, zNear, zFar = var
    windowToClipMat = windowToClip(width, height, zNear, zFar)
    
    # Assign the matrix to the uniform input in our shader program. Note that GL_TRUE here transposes the matrix because of OpenGL conventions
    glUseProgram(shaderProgram)
    glUniformMatrix4fv(windowToClipMatUnif, 1, GL_TRUE, windowToClipMat)
    
    # We're finished modifying our shader, so we set the program to be used as null to be proper
    glUseProgram(0)

def initializeVertexBuffer(meshData, indexData):
    """
    Assign the triangular mesh data and the triplets of vertex indices that form the triangles (index data) to VBOs
    """
    # Create a handle and assign the VBO for the mesh data to it
    global vertexBufferObject
    vertexBufferObject = glGenBuffers(1)
    
    # Bind the VBO to the GL_ARRAY_BUFFER target in the OpenGL context
    glBindBuffer(GL_ARRAY_BUFFER, vertexBufferObject)
    
    # Allocate enough memory for this VBO to contain the mesh data
    glBufferData(GL_ARRAY_BUFFER, meshData, GL_STATIC_DRAW)
    
    # Unbind the VBO from the target to be proper
    glBindBuffer(GL_ARRAY_BUFFER, 0)
    
    # Similar to the above, but for the index data
    global indexBufferObject
    indexBufferObject = glGenBuffers(1)
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, indexBufferObject)
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, indexData, GL_STATIC_DRAW)
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

def updateVertexBuffer(meshData):
    # Set the VAO as the currently used object in the OpenGL context
    glBindVertexArray(vertexArrayObject)
    
    # Bind the VBO to the GL_ARRAY_BUFFER target in the OpenGL context
    glBindBuffer(GL_ARRAY_BUFFER, vertexBufferObject)
    
    # Allocate enough memory for this VBO to contain the mesh data
    glBufferData(GL_ARRAY_BUFFER, meshData, GL_STATIC_DRAW)
    
    # Unbind the VBO from the target to be proper
    glBindBuffer(GL_ARRAY_BUFFER, 0)
    
    # Unset the VAO as the current object in the OpenGL context
    glBindVertexArray(0)

def initializeFramebufferObject(width, height, img = None):
    """
    Create an FBO and assign a texture buffer to it for the purpose of offscreen rendering to the texture buffer
    """
    # Create a handle and assign a texture buffer to it
    renderedTexture = glGenTextures(1)
    
    # Bind the texture buffer to the GL_TEXTURE_2D target in the OpenGL context
    glBindTexture(GL_TEXTURE_2D, renderedTexture)
    
    # Attach a texture 'img' (which should be of unsigned bytes) to the texture buffer. If you don't want a specific texture, you can just replace 'img' with 'None'.
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, width, height, 0, GL_RGB, GL_FLOAT, img)
    
    # Does some filtering on the texture in the texture buffer
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    
    # Unbind the texture buffer from the GL_TEXTURE_2D target in the OpenGL context
    glBindTexture(GL_TEXTURE_2D, 0)
    
    # Create a handle and assign a renderbuffer to it
    depthRenderbuffer = glGenRenderbuffers(1)
    
    # Bind the renderbuffer to the GL_RENDERBUFFER target in the OpenGL context
    glBindRenderbuffer(GL_RENDERBUFFER, depthRenderbuffer)
    
    # Allocate enough memory for the renderbuffer to hold depth values for the texture
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT, width, height)
    
    # Unbind the renderbuffer from the GL_RENDERBUFFER target in the OpenGL context
    glBindRenderbuffer(GL_RENDERBUFFER, 0)
    
    # Create a handle and assign the FBO to it
    global framebufferObject
    framebufferObject = glGenFramebuffers(1)
    
    # Use our initialized FBO instead of the default GLUT framebuffer
    glBindFramebuffer(GL_FRAMEBUFFER, framebufferObject)
    
    # Attaches the texture buffer created above to the GL_COLOR_ATTACHMENT0 attachment point of the FBO
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, renderedTexture, 0)
    
    # Attaches the renderbuffer created above to the GL_DEPTH_ATTACHMENT attachment point of the FBO
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, depthRenderbuffer)
    
    # Sees if your GPU can handle the FBO configuration defined above
    if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
        raise RuntimeError('Framebuffer binding failed, probably because your GPU does not support this FBO configuration.')
    
    # Unbind the FBO, relinquishing the GL_FRAMEBUFFER back to the window manager (i.e. GLUT)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)

def resetFramebufferObject():
    # Use our initialized FBO instead of the default GLUT framebuffer
    glBindFramebuffer(GL_FRAMEBUFFER, framebufferObject)
    
    # Clears any color or depth information in the FBO
    glClearColor(0.0, 0.0, 0.0, 1.0)
    glClearDepth(1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    
    # Unbind the FBO, relinquishing the GL_FRAMEBUFFER back to the window manager (i.e. GLUT)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)

def initializeVertexArray(vertexDim = 3, numVertices = 28588):
    """
    Creates the VAO to store the VBOs for the mesh data and the index data, 
    """
    # Create a handle and assign a VAO to it
    global vertexArrayObject
    vertexArrayObject = glGenVertexArrays(1)
    
    # Set the VAO as the currently used object in the OpenGL context
    glBindVertexArray(vertexArrayObject)
    
    # Bind the VBO for the mesh data to the GL_ARRAY_BUFFER target in the OpenGL context
    glBindBuffer(GL_ARRAY_BUFFER, vertexBufferObject)
    
    # Specify the location indices for the types of inputs to the shaders
    glEnableVertexAttribArray(0)
    glEnableVertexAttribArray(1)
    
    # Assign the first type of input (which is stored in the VBO beginning at the offset in the fifth argument) to the shaders
    glVertexAttribPointer(0, vertexDim, GL_FLOAT, GL_FALSE, 0, None)
    
    # Calculate the offset in the VBO for the second type of input, specified in bytes (because we used np.float32, each element is 4 bytes)
    colorOffset = c_void_p(vertexDim * numVertices * 4)
    
    # Assign the second type of input, beginning at the offset calculated above, to the shaders
    glVertexAttribPointer(1, vertexDim, GL_FLOAT, GL_FALSE, 0, colorOffset)
    
    # Bind the VBO for the index data to the GL_ELEMENT_ARRAY_BUFFER target in the OpenGL context
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, indexBufferObject)
    
    # Unset the VAO as the current object in the OpenGL context
    glBindVertexArray(0)

def initializeContext(width, height, meshData, indexData, img = None):
    # You can use any means to initialize an OpenGL context (e.g. GLUT), but since we're rendering offscreen to an FBO, we don't need to bother to display, which is why we hide the GLUT window.
    glutInit()
    window = glutCreateWindow('Merely creating an OpenGL context...')
    glutHideWindow()
    
    # Organize the strings defining our shaders into a dictionary
    shaderDict = {GL_VERTEX_SHADER: vertexShaderString, GL_FRAGMENT_SHADER: fragmentShaderString}
    
    # Use this dictionary to compile the shaders and link them to the GPU processors
    initializeShaders(shaderDict)
    
    # A utility function to modify uniform inputs to the shaders
    configureShaders([width, height, -1000, 1000])
    
    # Set the dimensions of the viewport
    glViewport(0, 0, width, height)
    
    # Performs face culling
    glEnable(GL_CULL_FACE)
    glCullFace(GL_BACK)
    glFrontFace(GL_CW)
    
    # Performs z-buffer testing
    glEnable(GL_DEPTH_TEST)
    glDepthMask(GL_TRUE)
    glDepthFunc(GL_LEQUAL)
    glDepthRange(0.0, 1.0)
    
    # Initialize OpenGL objects
    initializeVertexBuffer(meshData, indexData)
    initializeFramebufferObject(width, height, img)
    initializeVertexArray()

def render(indexData):
    # Defines what shaders to use
    glUseProgram(shaderProgram)
    
    # Use our initialized FBO instead of the default GLUT framebuffer
    glBindFramebuffer(GL_FRAMEBUFFER, framebufferObject)
    
    # Set our initialized VAO as the currently used object in the OpenGL context
    glBindVertexArray(vertexArrayObject)
    
    # Draws the mesh triangles defined in the VBO of the VAO above according to the vertices defining the triangles in indexData, which is of unsigned shorts
    glDrawElements(GL_TRIANGLES, indexData.size, GL_UNSIGNED_SHORT, None)
    
    # Being proper
    glBindVertexArray(0)
    glUseProgram(0)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)

def grabRendering(width, height):
    # Use our initialized FBO instead of the default GLUT framebuffer
    glBindFramebuffer(GL_FRAMEBUFFER, framebufferObject)
    
    # Configure how we store the pixels in memory for our subsequent reading of the FBO to store the rendering into memory. The second argument specifies that our pixels will be in bytes.
#    glPixelStorei(GL_PACK_ALIGNMENT, 1)
    
    # Set the color buffer that we want to read from. The GL_COLORATTACHMENT0 target is where we assigned our texture buffer in the FBO.
    glReadBuffer(GL_COLOR_ATTACHMENT0)
    
    # Now we do the actual reading, noting that we read the pixels in the buffer as unsigned bytes to be consistent will how they are stored
    data = glReadPixels(0, 0, width, height, GL_RGB, GL_FLOAT)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    
    # Convert the unsigned bytes to a NumPy array for whatever needs you may have
    return np.frombuffer(data, dtype = np.float32).reshape(height, width, 3)

if __name__ == '__main__':
    
    frame = 0
    img = Image.open('obama/orig/%05d.png' % (frame + 1))
    width, height = img.size
    img = np.array(img)
    
    vertexCoords, indexData = importObj('obama/shapes/%05d.obj' % (frame + 1), dataToImport = ['v', 'f'])
    indexData -= 1
    
    RTS = np.load('obama/RTS.npy')
    # The Euler angles for the rotation matrix are the first 3 columns
    eulerAngles = RTS[frame, :3]
    # The translation vector is the next 3 columns
    T = RTS[frame, 3: 6]
    # The scale factor is the last column
    S = RTS[frame, 6]
    
    vertexCoords = S * np.dot(vertexCoords, rotMat2angle(eulerAngles).T) + T
    zNear = vertexCoords[:, 2].min() - 1000
    zFar = vertexCoords[:, 2].max() + 1000
    
    m = Bunch(np.load('./models/bfm2017.npz'))
    vertexColors = m.texMean.T
    
    numVertices = vertexCoords.shape[0]
    meshData = np.r_[vertexCoords, vertexColors].astype(np.float32)
    indexData = indexData.astype(np.uint16)
    
    vertexDim = 3
    numVertices = vertexCoords.shape[0]
    
    initializeContext(width, height, meshData, indexData, img.tobytes())
    
    # Then we render offscreen to the FBO
#    render(indexData)
    
    rendering = grabRendering(width, height)
    plt.figure()
    plt.imshow(rendering)
    
#    for frame in range(1, 52, 10):
#        img = Image.open('obama/orig/%05d.png' % (frame + 1))
#        img = img.tobytes()
#        
#        vertexCoords = importObj('obama/shapes/%05d.obj' % (frame + 1), dataToImport = ['v'])[0]
#        eulerAngles = RTS[frame, :3]
#        T = RTS[frame, 3: 6]
#        S = RTS[frame, 6]
#        
#        vertexCoords = S * np.dot(vertexCoords, rotMat2angle(eulerAngles).T) + T
#        
#        meshData = np.r_[vertexCoords, vertexColors].astype(np.float32)
#        
#        updateVertexBuffer()
#        resetFramebufferObject()
#        render()
#        
#        rendering = grabRendering()
#        plt.figure()
#        plt.imshow(rendering)