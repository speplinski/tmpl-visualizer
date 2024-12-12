class Config:
    """Configuration class storing all constants and settings"""
    def __init__(self):
        self.image_directory = "results/tmpl/"
        self.overlay_path = "results/overlay.png"
        self.video_path = "results/0145.mp4"

        self.final_resolution = (3840, 2160)
        self.final_resolution_model = (3840, 1280)
        self.final_resolution_offset = (self.final_resolution[1] - self.final_resolution_model[1]) >> 1

        # 15,1,12,2
        # 15,1,6,4
        # 12,1,4,4
        # 12,1,2,4
        # 12,2,1,12
        # 12,4,1,24
        self.buffer_size = 12
        self.frame_step = 1
        self.source_fps = 4
        self.frames_to_interpolate = 4
        self.total_fps = self.source_fps * (self.frames_to_interpolate + 1)

        self.sequence_start_frame = 50  # initial frame number to begin playback from

        # Video starts at frame 200 OR after 15 seconds
        self.video_trigger_frame = 200  # Frame to start video
        self.video_trigger_time = 15.0  # Time (seconds) to start video
        self.fade_duration = 2.0
