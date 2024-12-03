import os
import pygame
import time
import numpy as np
from collections import deque
from threading import Thread, Lock

# Configuration
image_directory = "results/tmpl/"
overlay_path = "results/overlay.png"
final_resolution = (1728, 540)  
final_resolution_model = (1728, 576)
final_resolution_offset = -18
buffer_size = 4
frame_step = 1
source_fps = 4
frames_to_interpolate = 4  
total_fps = source_fps * (frames_to_interpolate + 1)

# Globalne bufory i locki
frame_buffer = deque(maxlen=buffer_size)
buffer_lock = Lock()

def load_and_prepare_image(image_path):
    if os.path.exists(image_path):
        image = pygame.image.load(image_path)
        if image:
            image = image.convert()
            return prepare_image(image, final_resolution_model[0], final_resolution_model[1])
    return None

def buffer_loader_thread(start_index):
    """Wątek ładujący kolejne klatki do bufora"""
    current_index = start_index
    
    while True:
        if len(frame_buffer) < buffer_size:
            image_path = os.path.join(image_directory, f"{current_index:09d}.jpg")
            prepared_image = load_and_prepare_image(image_path)
            
            if prepared_image:
                with buffer_lock:
                    frame_buffer.append((current_index, prepared_image))
                current_index += frame_step
            else:
                time.sleep(0.1)  # Jeśli nie ma obrazka, czekamy chwilę
        else:
            time.sleep(0.1)  # Bufor pełny, czekamy

def interpolate_images(image1, image2, alpha):
    arr1 = pygame.surfarray.array3d(image1)
    arr2 = pygame.surfarray.array3d(image2)
    interpolated = (arr1 * (1 - alpha) + arr2 * alpha).astype(np.uint8)
    return pygame.surfarray.make_surface(interpolated)

def scale_image_maintain_ratio(image, target_width, target_height):
    original_width, original_height = image.get_size()
    width_ratio = target_width / original_width
    height_ratio = target_height / original_height
    scale_ratio = min(width_ratio, height_ratio)
    
    new_width = int(original_width * scale_ratio)
    new_height = int(original_height * scale_ratio)
    
    scaled_image = pygame.transform.smoothscale(image, (new_width, new_height))
    final_surface = pygame.Surface((target_width, target_height), pygame.SRCALPHA)
    
    x_offset = (target_width - new_width) // 2
    y_offset = (target_height - new_height) // 2
    
    final_surface.blit(scaled_image, (x_offset, y_offset))
    return final_surface

def prepare_image(image, target_width, target_height):
    return scale_image_maintain_ratio(image, target_width, target_height)

def draw_text(screen, text, x, y):
    font = pygame.font.SysFont("Arial", 24)
    text_surface = font.render(text, True, (255, 255, 255))
    background_surface = pygame.Surface(text_surface.get_size())
    background_surface.fill((0, 0, 0))
    screen.blit(background_surface, (x, y))
    screen.blit(text_surface, (x, y))

def format_stats(elapsed_time, total_source_frames, total_displayed_frames):
    hours, remainder = divmod(elapsed_time, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    source_fps = total_source_frames / max(elapsed_time, 0.001)
    total_fps = total_displayed_frames / max(elapsed_time, 0.001)
    
    return (
        f"{int(hours):02}:{int(minutes):02}:{seconds:05.2f} | "
        f"Step: {frame_step} | "
        f"Source frames: {total_source_frames} ({source_fps:.1f}/s) | "
        f"Total frames: {total_displayed_frames} ({total_fps:.1f}/s)"
    )

def main():
    pygame.init()
    #screen = pygame.display.set_mode(final_resolution_model)
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    screen.fill((0, 0, 0))
    
    pygame.display.set_caption("The Most Polish Landscape")
    clock = pygame.time.Clock()
    
    # Ładowanie overlay
    overlay_image = pygame.image.load(overlay_path).convert_alpha()
    overlay_image = scale_image_maintain_ratio(overlay_image, final_resolution[0], final_resolution[1])
    
    # Startujemy wątek ładujący
    loader_thread = Thread(target=buffer_loader_thread, args=(1,), daemon=True)
    loader_thread.start()
    
    # Czekamy na załadowanie pierwszej klatki
    while len(frame_buffer) == 0:
        time.sleep(0.1)
    
    current_index, current_image = frame_buffer[0]
    next_image = None
    
    running = True
    start_time = time.time()
    total_source_frames = 1
    total_displayed_frames = 1
    frame_in_sequence = 0
    interpolated_frames = []  # Bufor na klatki interpolowane
    
    while running:
        # Jeśli potrzebujemy nowej klatki źródłowej
        if frame_in_sequence == 0:
            with buffer_lock:
                if len(frame_buffer) > 1:
                    # Bierzemy następną klatkę z bufora
                    _, next_image = frame_buffer[1]
                    
                    # Przygotowujemy klatki interpolowane
                    interpolated_frames = []
                    for i in range(frames_to_interpolate):
                        alpha = (i + 1) / (frames_to_interpolate + 1)
                        interpolated = interpolate_images(current_image, next_image, alpha)
                        interpolated_frames.append(interpolated)
                    
                    # Wyświetlamy klatkę źródłową
                    screen.fill((0, 0, 0))
                    screen.blit(current_image, (0, final_resolution_offset))
                    screen.blit(overlay_image, (0, 0))
                    total_source_frames += 1
                    
                    # Usuwamy wykorzystaną klatkę z bufora
                    frame_buffer.popleft()
                    current_image = next_image
        else:
            # Klatka interpolowana
            if interpolated_frames:
                screen.fill((0, 0, 0))
                screen.blit(interpolated_frames[frame_in_sequence-1], (0, final_resolution_offset))
                screen.blit(overlay_image, (0, 0))
        
        # Wyświetl statystyki
        current_time = time.time()
        elapsed_time = current_time - start_time
        info_text = format_stats(elapsed_time, total_source_frames, total_displayed_frames)
        draw_text(screen, info_text, 10, 10)
        
        pygame.display.flip()
        total_displayed_frames += 1
        
        # Przygotuj następną klatkę
        frame_in_sequence = (frame_in_sequence + 1) % (frames_to_interpolate + 1)
        
        # Wymuszenie stałego FPS
        clock.tick(total_fps)
        
        # Obsługa zdarzeń
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False

    pygame.quit()

if __name__ == "__main__":
    main()
