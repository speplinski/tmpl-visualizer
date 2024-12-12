import argparse
import time
import sys
import sdl2
import ctypes
from config import Config
from sdl_app import SDLApp
from texture_manager import TextureManager
from video_player import VideoPlayer
from image_sequence_player import ImageSequencePlayer
from transition_manager import TransitionManager
from playback_stats import PlaybackStatistics

class Application:
    def __init__(self, monitor_index):
        self.config = Config()
        self.sdl_app = SDLApp(monitor_index)
        self.texture_manager = TextureManager(self.sdl_app.renderer)
        self.sequence_player = ImageSequencePlayer(self.config, self.texture_manager)
        self.transition_manager = TransitionManager(self.sdl_app.renderer, self.config)
        self.stats = PlaybackStatistics()

        self.running = True
        self.video_mode_started = False
        self.is_fading = False
        self.fade_completed = False
        self.pre_fade_prepared = False
        self.fade_preparation_started = False
        self.pre_fade_threshold = 0.5
        self.fade_textures = None
        self.white_transition = None
        self.video_player = None

        self.frame_in_sequence = 0
        self.interpolated_frames = []
        self.current_texture = None
        self.next_texture = None
        self.last_full_frame_texture = None

        self.last_display_time = time.time()
        self.fade_start_time = 0

        self.dest_rect = sdl2.SDL_Rect(
            0, 
            self.config.final_resolution_offset,
            self.config.final_resolution_model[0],
            1280
        )

        self.loop_mode = True
        self.sequence_starting = False

    def handle_events(self):
        event = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(ctypes.byref(event)):
            if event.type == sdl2.SDL_QUIT:
                self.running = False
            elif event.type == sdl2.SDL_KEYDOWN:
                if event.key.keysym.sym in (sdl2.SDLK_ESCAPE, sdl2.SDLK_q):
                    self.running = False

    def run(self):
        self._initialize()

        while self.running:
            current_time = time.time()

            if current_time - self.last_display_time < 1.0 / self.config.total_fps:
                time.sleep(0.001)
                continue

            self.last_display_time = current_time

            self.handle_events()

            sdl2.SDL_SetRenderDrawColor(self.sdl_app.renderer, 0, 0, 0, 255)
            sdl2.SDL_RenderClear(self.sdl_app.renderer)

            if self.is_fading:
                self._handle_fade_transition(current_time)
            elif self.fade_completed and self.video_mode_started:
                if self.white_transition:
                    self._handle_white_transition()
                else:
                    self._handle_video_playback()
            else:
                self._handle_image_sequence()

            stats_text = self.stats.format_stats()
            self.sdl_app.render_text(stats_text, 10, 10)

            sdl2.SDL_RenderPresent(self.sdl_app.renderer)

            self.stats.update_playback_time(current_time)
            self.stats.total_displayed_frames += 1

        self._cleanup()

    def _initialize(self):
        current_seq = self.config.get_current_sequence()
        self.overlay_texture = self.texture_manager.load_image(
            current_seq['overlay_path'],
            self.config.final_resolution,
            keep_aspect=True
        )

        if not self.overlay_texture:
            raise Exception("Failed to create overlay texture")

        self.sequence_player.set_directory(current_seq['image_directory'])
        self.sequence_player.start_loader_thread(self.config.sequence_start_frame)

        while self.sequence_player.frame_buffer.empty():
            time.sleep(0.1)

        _, self.current_texture = self.sequence_player.frame_buffer.get()
        self.last_full_frame_texture = self.current_texture

    def _handle_fade_transition(self, current_time):
        if not self.fade_textures:
            self.is_fading = False
            return

        progress = (current_time - self.fade_start_time) / self.config.fade_duration
        frame_index = min(int(progress * len(self.fade_textures)), len(self.fade_textures) - 1)

        if frame_index < len(self.fade_textures):
            sdl2.SDL_RenderCopy(self.sdl_app.renderer, self.fade_textures[frame_index], None, None)

        if progress >= 1.0:
            self.is_fading = False
            self._cleanup_fade_textures()

            if self.video_mode_started:
                self.video_mode_started = False
                self.stats = PlaybackStatistics()
            else:
                current_seq = self.config.get_current_sequence()
                self.fade_completed = True
                self._cleanup_image_resources()
                self.white_transition = self.transition_manager.create_white_transition_texture()
                self.video_player = VideoPlayer(current_seq['video_path'], self.sdl_app.renderer)
                self.video_mode_started = True

    def _cleanup_fade_textures(self):
        if self.fade_textures:
            for texture in self.fade_textures:
                sdl2.SDL_DestroyTexture(texture)
            self.fade_textures = None

    def _handle_white_transition(self):
        sdl2.SDL_RenderClear(self.sdl_app.renderer)
        sdl2.SDL_RenderCopy(
            self.sdl_app.renderer,
            self.white_transition,
            None,
            self.dest_rect
        )

        if self.video_player and self.video_player.texture is None:
            print("Getting first video frame")
            self.video_player.texture = self.video_player.get_next_frame_texture()
            if self.video_player.texture:
                print("Successfully got first video frame")
                sdl2.SDL_DestroyTexture(self.white_transition)
                self.white_transition = None

    def _handle_video_playback(self):
        if self.video_player.video_finished:
            if True:
                last_white = self._cleanup_video()
                self._reset_sequence_with_transition(last_white)
                return

        if self.video_player.texture:
            ret = sdl2.SDL_RenderCopy(
                self.sdl_app.renderer,
                self.video_player.texture,
                None,
                self.dest_rect
            )
            if ret != 0:
                print(f"SDL_RenderCopy failed: {sdl2.SDL_GetError()}")

            old_texture = self.video_player.texture
            self.video_player.texture = self.video_player.get_next_frame_texture()
            sdl2.SDL_DestroyTexture(old_texture)

    def _render_white_screen(self):
        sdl2.SDL_SetRenderDrawColor(self.sdl_app.renderer, 0, 0, 0, 255)
        sdl2.SDL_RenderClear(self.sdl_app.renderer)
        sdl2.SDL_RenderCopy(self.sdl_app.renderer, self.white_transition, None, self.dest_rect)
        sdl2.SDL_RenderPresent(self.sdl_app.renderer)

    def _cleanup_video(self):
        # Keep white screen
        white_transition = self.transition_manager.create_white_transition_texture()
    
        if self.video_player:
            self.video_player.video_finished = True
            self.video_player = None
        if self.white_transition:
            sdl2.SDL_DestroyTexture(self.white_transition)

        # Switch to next sequence
        next_seq = self.config.next_sequence()

        return white_transition

    def _reset_sequence_with_transition(self, white_transition):
        current_seq = self.config.get_current_sequence()

        # Update overlay
        if self.overlay_texture:
            sdl2.SDL_DestroyTexture(self.overlay_texture)
        self.overlay_texture = self.texture_manager.load_image(
            current_seq['overlay_path'],
            self.config.final_resolution,
            keep_aspect=True
        )

        self.white_transition = white_transition
        self.fade_completed = False
        self.frame_in_sequence = 0

        self.sequence_player = ImageSequencePlayer(self.config, self.texture_manager)
        self.sequence_player.set_directory(current_seq['image_directory'])
        self.sequence_player.start_loader_thread(self.config.sequence_start_frame)

        self._render_white_screen()

        while self.sequence_player.frame_buffer.empty():
            self._render_white_screen()
            time.sleep(0.1)

        _, self.current_texture = self.sequence_player.frame_buffer.get()
        self.last_full_frame_texture = self.current_texture
        self.fade_textures = self.transition_manager.create_fade_from_white(
            self.current_texture,
            self.overlay_texture
        )
        self.is_fading = True
        self.fade_start_time = time.time()

    def _handle_image_sequence(self):
        current_time = time.time()
        current_frame_rendered = False

        # Check if we should start fade first
        if ((self.stats.playback_time >= self.config.video_trigger_time or 
             self.stats.total_source_frames >= self.config.video_trigger_frame)
            and not self.is_fading and not self.fade_completed):
            print(f"Starting fade at: Time={self.stats.playback_time:.2f}s, Frame={self.stats.total_source_frames}")
            self._render_frame_with_overlay(self.last_full_frame_texture)
            current_frame_rendered = True
            # Then prepare fade using that same frame
            self.fade_textures = self.transition_manager.create_fade_to_white(
                self.last_full_frame_texture,
                self.overlay_texture
            )
            self.is_fading = True
            self.fade_start_time = current_time
            return

        if not current_frame_rendered:
            if self.frame_in_sequence == 0:
                if not self.sequence_player.frame_buffer.empty():
                    if not self.stats.playing:
                        self.stats.start_playback()

                    next_index, self.next_texture = self.sequence_player.frame_buffer.get()
                    self._cleanup_interpolated_frames()

                    for i in range(self.config.frames_to_interpolate):
                        alpha = (i + 1) / (self.config.frames_to_interpolate + 1)
                        interpolated = self._interpolate_textures(self.current_texture, self.next_texture, alpha)
                        if interpolated:
                            self.interpolated_frames.append(interpolated)

                    self._render_frame_with_overlay(self.current_texture)
                    self.stats.total_source_frames += 1
                    self.last_full_frame_texture = self.current_texture
                    self.frame_in_sequence = 1
                else:
                    self._render_frame_with_overlay(self.last_full_frame_texture)
                    if self.stats.playing:
                        self.stats.pause_playback()
            else:
                if self.frame_in_sequence <= self.config.frames_to_interpolate:
                    interp_index = self.frame_in_sequence - 1
                    if interp_index < len(self.interpolated_frames):
                        self._render_frame_with_overlay(self.interpolated_frames[interp_index])
                    self.frame_in_sequence += 1
                else:
                    self._render_frame_with_overlay(self.next_texture)
                    if self.last_full_frame_texture and self.last_full_frame_texture != self.current_texture:
                        sdl2.SDL_DestroyTexture(self.last_full_frame_texture)
                    self.last_full_frame_texture = self.next_texture
                    self.current_texture = self.next_texture
                    self.next_texture = None
                    self.frame_in_sequence = 0

    def _render_frame_with_overlay(self, texture):
        sdl2.SDL_RenderCopy(self.sdl_app.renderer, texture, None, self.dest_rect)
        sdl2.SDL_RenderCopy(self.sdl_app.renderer, self.overlay_texture, None, None)

    def _interpolate_textures(self, texture1, texture2, alpha):
        target = sdl2.SDL_CreateTexture(
            self.sdl_app.renderer,
            sdl2.SDL_PIXELFORMAT_RGBA8888,
            sdl2.SDL_TEXTUREACCESS_TARGET,
            self.config.final_resolution_model[0],
            self.config.final_resolution_model[1]
        )

        if not target:
            return None

        sdl2.SDL_SetRenderTarget(self.sdl_app.renderer, target)
        sdl2.SDL_RenderClear(self.sdl_app.renderer)

        sdl2.SDL_SetTextureAlphaMod(texture1, 255)
        sdl2.SDL_RenderCopy(self.sdl_app.renderer, texture1, None, None)

        eased_alpha = self._ease_in_out_quad(alpha)
        sdl2.SDL_SetTextureBlendMode(texture2, sdl2.SDL_BLENDMODE_BLEND)
        sdl2.SDL_SetTextureAlphaMod(texture2, int(eased_alpha * 255))
        sdl2.SDL_RenderCopy(self.sdl_app.renderer, texture2, None, None)

        sdl2.SDL_SetTextureAlphaMod(texture1, 255)
        sdl2.SDL_SetTextureAlphaMod(texture2, 255)

        sdl2.SDL_SetRenderTarget(self.sdl_app.renderer, None)
        return target

    def _ease_in_out_quad(self, t):
        return 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t

    def _cleanup_interpolated_frames(self):
        for texture in self.interpolated_frames:
            sdl2.SDL_DestroyTexture(texture)
        self.interpolated_frames = []

    def _cleanup_image_resources(self):
        if self.current_texture:
            sdl2.SDL_DestroyTexture(self.current_texture)
            self.current_texture = None
        if self.next_texture:
            sdl2.SDL_DestroyTexture(self.next_texture)
            self.next_texture = None
        if self.last_full_frame_texture:
            sdl2.SDL_DestroyTexture(self.last_full_frame_texture)
            self.last_full_frame_texture = None
        self._cleanup_interpolated_frames()
        while not self.sequence_player.frame_buffer.empty():
            _, texture = self.sequence_player.frame_buffer.get()
            sdl2.SDL_DestroyTexture(texture)

    def _cleanup(self):
        if self.video_player:
            self.video_player.video_finished = True
        if self.white_transition:
            sdl2.SDL_DestroyTexture(self.white_transition)
        if self.fade_textures:
            for texture in self.fade_textures:
                sdl2.SDL_DestroyTexture(texture)
        self._cleanup_image_resources()
        if self.overlay_texture:
            sdl2.SDL_DestroyTexture(self.overlay_texture)

def main(monitor_index):
    try:
        app = Application(monitor_index)
        app.run()
    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Video player with monitor selection')
    parser.add_argument('--monitor', type=int, default=1,
                      help='Monitor index (0 is usually the main display)')
    args = parser.parse_args()

    main(args.monitor)
