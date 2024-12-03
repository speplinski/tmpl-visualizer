import depthai as dai
import numpy as np
import cv2

# Create pipeline
pipeline = dai.Pipeline()

# Define sources and outputs
monoLeft = pipeline.create(dai.node.MonoCamera)
monoRight = pipeline.create(dai.node.MonoCamera)
stereo = pipeline.create(dai.node.StereoDepth)
spatialLocationCalculator = pipeline.create(dai.node.SpatialLocationCalculator)

xoutDepth = pipeline.create(dai.node.XLinkOut)
xoutSpatialData = pipeline.create(dai.node.XLinkOut)
xinSpatialCalcConfig = pipeline.create(dai.node.XLinkIn)

xoutDepth.setStreamName("depth")
xoutSpatialData.setStreamName("spatialData")
xinSpatialCalcConfig.setStreamName("spatialCalcConfig")

# Properties
monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
monoLeft.setCamera("left")
monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
monoRight.setCamera("right")

stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
stereo.setLeftRightCheck(True)
stereo.setSubpixel(True)
spatialLocationCalculator.inputConfig.setWaitForMessage(False)

# divide depth frame into segments
nH = 10
nV = 6

for y in range(nV):
    for x in range(nH):
        config = dai.SpatialLocationCalculatorConfigData()
        config.depthThresholds.lowerThreshold = 200
        config.depthThresholds.upperThreshold = 10000
        config.roi = dai.Rect(dai.Point2f((x)/nH, y/nV), dai.Point2f((x+1)/nH, (y+1)/nV))
        spatialLocationCalculator.initialConfig.addROI(config)

# Linking
monoLeft.out.link(stereo.left)
monoRight.out.link(stereo.right)
spatialLocationCalculator.passthroughDepth.link(xoutDepth.input)
stereo.depth.link(spatialLocationCalculator.inputDepth)
spatialLocationCalculator.out.link(xoutSpatialData.input)
xinSpatialCalcConfig.out.link(spatialLocationCalculator.inputConfig)

def create_heatmap(distances, nH, nV, threshold=2.3):
    # Convert distances to numpy array and reshape
    heatmap = np.array(distances).reshape(nV, nH)
    
    # Create mask for values <= threshold
    mask = heatmap <= threshold
    
    # Normalize the data to 0-255 range for visualization, but only for values <= threshold
    min_dist = np.min(heatmap[mask]) if np.any(mask) else 0
    max_dist = threshold
    
    # Create normalized array
    normalized = np.zeros_like(heatmap)
    normalized[mask] = ((heatmap[mask] - min_dist) / (max_dist - min_dist) * 255)
    normalized = normalized.astype(np.uint8)
    
    # Apply colormap
    heatmap_colored = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
    
    # Set pixels with distance > threshold to black
    heatmap_colored[~mask] = [0, 0, 0]
    
    # Scale up the image for better visibility
    scale_factor = 40
    heatmap_scaled = cv2.resize(heatmap_colored, 
                               (nH * scale_factor, nV * scale_factor), 
                               interpolation=cv2.INTER_NEAREST)
    
    # Add distance values as text only for distances <= threshold
    for y in range(nV):
        for x in range(nH):
            distance = distances[y * nH + x]
            if distance <= threshold:
                text_x = x * scale_factor + 5
                text_y = y * scale_factor + scale_factor//2
                cv2.putText(heatmap_scaled, 
                           f"{distance:.1f}", 
                           (text_x, text_y),
                           cv2.FONT_HERSHEY_SIMPLEX,
                           0.5,
                           (255, 255, 255),
                           1)
    
    return heatmap_scaled

# Connect to device and start pipeline
#device_info = dai.DeviceInfo("192.168.1.109")
#with dai.Device(pipeline, device_info) as device:

with dai.Device(pipeline) as device:
    device.setIrLaserDotProjectorIntensity(0.5)

    depthQueue = device.getOutputQueue(name="depth", maxSize=4, blocking=False)
    spatialCalcQueue = device.getOutputQueue(name="spatialData", maxSize=4, blocking=False)

    while True:
        inDepth = depthQueue.get()
        depthFrame = inDepth.getFrame()
        spatialData = spatialCalcQueue.get().getSpatialLocations()
        
        # Extract distances
        distances = []
        for depthData in spatialData:
            distance = depthData.spatialCoordinates.z / 1000  # Convert to meters
            distances.append(distance)
        
        # Create and display heatmap
        heatmap = create_heatmap(distances, nH, nV, threshold=2.3)
        
        # Display depth information
        cv2.imshow("Depth Heatmap", heatmap)
        
        # Break loop on 'q' press
        if cv2.waitKey(1) == ord('q'):
            break

cv2.destroyAllWindows()
