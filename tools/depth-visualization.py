import depthai as dai
import numpy as np
import cv2
import os
import time
import sys
import select
import tty
import termios

# Create pipeline for DepthAI
pipeline = dai.Pipeline()

# Define sources and outputs for the pipeline
monoLeft = pipeline.create(dai.node.MonoCamera)
monoRight = pipeline.create(dai.node.MonoCamera)
stereo = pipeline.create(dai.node.StereoDepth)
spatialLocationCalculator = pipeline.create(dai.node.SpatialLocationCalculator)

# Create XLink connections
xoutDepth = pipeline.create(dai.node.XLinkOut)
xoutSpatialData = pipeline.create(dai.node.XLinkOut)
xinSpatialCalcConfig = pipeline.create(dai.node.XLinkIn)

# Set names for the streams
xoutDepth.setStreamName("depth")
xoutSpatialData.setStreamName("spatialData")
xinSpatialCalcConfig.setStreamName("spatialCalcConfig")

# Configure camera properties
monoLeft.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
monoLeft.setCamera("left")
monoRight.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
monoRight.setCamera("right")

# Configure stereo depth properties
stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.DEFAULT)
stereo.setLeftRightCheck(True)
stereo.setSubpixel(True)
spatialLocationCalculator.inputConfig.setWaitForMessage(False)

# Define distance thresholds (in meters)
MIN_THRESHOLD = 0.4  # 40 cm
MAX_THRESHOLD = 1.8  # 1.8 meters

# Display configuration
DISPLAY_WINDOW = False  # CV2 window display flag
SHOW_STATS = True      # Statistics display flag
MIRROR_MODE = True     # Mirror mode flag
REFRESH_RATE = 30     # Stats refresh rate (in frames)

# Define grid dimensions for depth analysis
nH = 10  # Horizontal divisions
nV = 6   # Vertical divisions

# Configure spatial calculator ROIs (Regions of Interest)
for y in range(nV):
    for x in range(nH):
        config = dai.SpatialLocationCalculatorConfigData()
        config.depthThresholds.lowerThreshold = 200
        config.depthThresholds.upperThreshold = 10000
        config.roi = dai.Rect(dai.Point2f((x)/nH, y/nV), dai.Point2f((x+1)/nH, (y+1)/nV))
        spatialLocationCalculator.initialConfig.addROI(config)

# Link nodes in the pipeline
monoLeft.out.link(stereo.left)
monoRight.out.link(stereo.right)
spatialLocationCalculator.passthroughDepth.link(xoutDepth.input)
stereo.depth.link(spatialLocationCalculator.inputDepth)
spatialLocationCalculator.out.link(xoutSpatialData.input)
xinSpatialCalcConfig.out.link(spatialLocationCalculator.inputConfig)

def is_data():
    """Check if there is data available on stdin."""
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])

def get_key():
    """Get a keypress from stdin without blocking."""
    if is_data():
        return sys.stdin.read(1)
    return None

def init_terminal():
    """Initialize terminal for raw input."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
    except termios.error:
        pass
    return old_settings

def restore_terminal(old_settings):
    """Restore terminal settings."""
    fd = sys.stdin.fileno()
    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except termios.error:
        pass

def move_cursor(x: int, y: int):
    """Move terminal cursor to specified position."""
    sys.stdout.write(f"\033[{y};{x}H")
    sys.stdout.flush()

def create_buffer(nH: int, nV: int) -> list[list[str]]:
    """Create a buffer for storing previous state of the heatmap."""
    return [[" " for _ in range(nH)] for _ in range(nV)]

def get_stats(distances):
    """Calculate basic statistics for the distances."""
    distances_array = np.array(distances)
    valid_distances = distances_array[
        (distances_array >= MIN_THRESHOLD) & 
        (distances_array <= MAX_THRESHOLD)
    ]
    
    if len(valid_distances) == 0:
        return 0, 0, 0
    
    return (np.min(valid_distances), 
            np.mean(valid_distances), 
            np.max(valid_distances))

def analyze_columns(distances, nH, nV, mirror=True):
    """
    Analyze columns for object presence and return binary representation.
    Returns array where 1 indicates object presence in column, 0 indicates no object.
    """
    heatmap = np.array(distances).reshape(nV, nH)
    if mirror:
        heatmap = np.fliplr(heatmap)
    
    # Create mask for values between thresholds
    mask = (heatmap >= MIN_THRESHOLD) & (heatmap <= MAX_THRESHOLD)
    
    # Check each column for object presence
    column_presence = np.zeros(nH, dtype=int)
    for col in range(nH):
        if np.any(mask[:, col]):
            column_presence[col] = 1
    
    return column_presence

def safe_save_column_data(column_presence, filename="data.txt", max_retries=3, retry_delay=0.01):
    """
    Safely save current column state to file with retry mechanism.
    
    Args:
        column_presence: Array of binary values indicating object presence
        filename: Name of the output file
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
    """
    data_str = ','.join(map(str, column_presence))
    
    for attempt in range(max_retries):
        try:
            # Try to open and write to file
            with open(filename, 'w') as f:
                f.write(data_str)
            return True  # Success
        except (IOError, OSError) as e:
            if attempt < max_retries - 1:  # If not the last attempt
                time.sleep(retry_delay)  # Wait before retry
                continue
            return False  # Failed all attempts
    
    return False  # Should never reach here, but just in case

def create_heatmap(distances, nH, nV, mirror=True):
    """Create a CV2 heatmap visualization of the depth data."""
    heatmap = np.array(distances).reshape(nV, nH)
    
    if mirror:
        heatmap = np.fliplr(heatmap)
    
    mask = (heatmap >= MIN_THRESHOLD) & (heatmap <= MAX_THRESHOLD)
    
    normalized = np.zeros_like(heatmap)
    normalized[mask] = ((heatmap[mask] - MIN_THRESHOLD) / 
                       (MAX_THRESHOLD - MIN_THRESHOLD) * 255)
    normalized = normalized.astype(np.uint8)
    
    heatmap_colored = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
    heatmap_colored[~mask] = [0, 0, 0]
    
    scale_factor = 80
    heatmap_scaled = cv2.resize(heatmap_colored, 
                               (nH * scale_factor, nV * scale_factor), 
                               interpolation=cv2.INTER_NEAREST)
    
    return heatmap_scaled

def create_console_heatmap(distances, nH, nV, prev_buffer, mirror=True):
    """Create and update console-based heatmap visualization."""
    heatmap = np.array(distances).reshape(nV, nH)
    
    if mirror:
        heatmap = np.fliplr(heatmap)
    
    mask = (heatmap >= MIN_THRESHOLD) & (heatmap <= MAX_THRESHOLD)
    normalized = np.zeros_like(heatmap, dtype=float)
    normalized[mask] = ((heatmap[mask] - MIN_THRESHOLD) / 
                       (MAX_THRESHOLD - MIN_THRESHOLD))
    
    chars = ' ░▒▓█'
    current_buffer = [[" " for _ in range(nH)] for _ in range(nV)]
    
    if all(all(cell == " " for cell in row) for row in prev_buffer):
        print("\033[2J")  # Clear screen
        print("\033[?25l")  # Hide cursor
        
        # Draw frame
        move_cursor(1, 1)
        print("┏" + "━" * (nH * 2) + "┓")
        for i in range(nV):
            move_cursor(1, i + 2)
            print("┃" + " " * (nH * 2) + "┃")
        move_cursor(1, nV + 2)
        print("┗" + "━" * (nH * 2) + "┛")
        
        # Print legend and controls
        move_cursor(1, nV + 4)
        print(f"Range: {MIN_THRESHOLD:.1f}m to {MAX_THRESHOLD:.1f}m")
        move_cursor(1, nV + 5)
        print("Controls:")
        move_cursor(1, nV + 6)
        print("  'q' - Exit")
        move_cursor(1, nV + 7)
        print("  'w' - Toggle window")
        move_cursor(1, nV + 8)
        print("  's' - Toggle stats")
        move_cursor(1, nV + 9)
        print("  'm' - Toggle mirror mode")

    for i in range(nV):
        for j in range(nH):
            if mask[i, j]:
                char_idx = int(normalized[i, j] * (len(chars) - 1))
                current_char = chars[char_idx]
            else:
                current_char = " "
            
            current_buffer[i][j] = current_char
            
            if current_char != prev_buffer[i][j]:
                move_cursor(j * 2 + 2, i + 2)
                sys.stdout.write(f"\033[94m{current_char}\033[0m ")
                sys.stdout.flush()
    
    return current_buffer

# Initialize display buffer and performance counters
prev_buffer = create_buffer(nH, nV)
frame_count = 0
start_time = time.time()

# Main processing loop
# Connect to device and start pipeline
#device_info = dai.DeviceInfo("192.168.1.109")
with dai.Device(pipeline) as device:
    device.setIrLaserDotProjectorIntensity(0.5)
    
    # Get output queues
    depthQueue = device.getOutputQueue(name="depth", maxSize=4, blocking=False)
    spatialCalcQueue = device.getOutputQueue(name="spatialData", maxSize=4, blocking=False)
    
    try:
        # Save terminal settings and initialize raw mode
        old_terminal_settings = init_terminal()

        while True:
            frame_count += 1
            
            inDepth = depthQueue.get()
            spatialData = spatialCalcQueue.get().getSpatialLocations()
            
            distances = []
            for depthData in spatialData:
                distance = depthData.spatialCoordinates.z / 1000
                distances.append(distance)
            
            # Analyze columns and save data
            column_presence = analyze_columns(distances, nH, nV, MIRROR_MODE)
            if not safe_save_column_data(column_presence):
                if frame_count % REFRESH_RATE == 0:
                    move_cursor(1, nV + 17)
                    print("Warning: Unable to save column data    ")
            elif frame_count % REFRESH_RATE == 0:
                move_cursor(1, nV + 17)
                print(" " * 40)  # Clear warning if save was successful
            
            # Update console visualization
            prev_buffer = create_console_heatmap(distances, nH, nV, prev_buffer, MIRROR_MODE)
            
            # Update statistics
            if frame_count % REFRESH_RATE == 0:
                current_time = time.time()
                fps = frame_count / (current_time - start_time)
                
                move_cursor(1, nV + 11)
                print(f"FPS: {fps:.1f}        ")
                move_cursor(1, nV + 12)
                print(f"Mirror: {'ON ' if MIRROR_MODE else 'OFF'}")
                
                if SHOW_STATS:
                    min_dist, avg_dist, max_dist = get_stats(distances)
                    move_cursor(1, nV + 13)
                    print(f"Min dist: {min_dist:.2f}m     ")
                    move_cursor(1, nV + 14)
                    print(f"Avg dist: {avg_dist:.2f}m     ")
                    move_cursor(1, nV + 15)
                    print(f"Max dist: {max_dist:.2f}m     ")
                    move_cursor(1, nV + 16)
                    print(f"Columns: {','.join(map(str, column_presence))}     ")
            
            # Update CV2 window if enabled
            if DISPLAY_WINDOW:
                heatmap = create_heatmap(distances, nH, nV, MIRROR_MODE)
                cv2.imshow("Depth Heatmap", heatmap)
                key = cv2.waitKey(1)
                if key != -1:
                    key = chr(key & 0xFF)
                else:
                    key = None
            else:
                key = get_key()

            # Handle key presses
            if key:
                if key == 'q':
                    break
                elif key == 'w':
                    DISPLAY_WINDOW = not DISPLAY_WINDOW
                    if not DISPLAY_WINDOW:
                        cv2.destroyAllWindows()
                elif key == 's':
                    SHOW_STATS = not SHOW_STATS
                    if not SHOW_STATS:
                        for i in range(13, 17):
                            move_cursor(1, nV + i)
                            print(" " * 30)
                elif key == 'm':
                    MIRROR_MODE = not MIRROR_MODE

    finally:
        # Restore terminal settings
        restore_terminal(old_terminal_settings)
        print("\033[?25h")  # Show cursor
        if DISPLAY_WINDOW:
            cv2.destroyAllWindows()