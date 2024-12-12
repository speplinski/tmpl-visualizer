class Config:
    """Configuration class storing all constants and settings"""
    def __init__(self):
        self.sequences = [
            {
                'id': '0145',
                'image_directory': 'results/sequences/0145/',
                'overlay_path': 'results/overlays/0145.png',
                'video_path': 'results/movies/0145.mp4'
            },
            {
                'id': '0200',
                'image_directory': 'results/sequences/0200/',
                'overlay_path': 'results/overlays/0200.png',
                'video_path': 'results/movies/0200.mp4'
            },
            {
                'id': '0400',
                'image_directory': 'results/sequences/0400/',
                'overlay_path': 'results/overlays/0400.png',
                'video_path': 'results/movies/0400.mp4'
            }
        ]
        self.current_sequence_index = 0

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
        self.video_trigger_time = 5.0  # Time (seconds) to start video
        self.fade_duration = 2.0

    def get_current_sequence(self):
        return self.sequences[self.current_sequence_index]

    def next_sequence(self):
        self.current_sequence_index = (self.current_sequence_index + 1) % len(self.sequences)
        return self.get_current_sequence()