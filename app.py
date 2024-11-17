import os
import pygame
import time
import numpy as np


image_directory = "results/tmpl/" # Path to the directory for AI-generated image results
overlay_path = "results/overlay.png"  # Path to the overlay for specific landscape types

target_fps = 30  # Target frames per second
frames_to_interpolate = 3  # Number of interpolated frames
final_resolution = (3840, 1200)  # Target display resolution

def load_image(image_path):
    if os.path.exists(image_path):
        print(f"Loaded image: {image_path}")
        return pygame.image.load(image_path)
    return None

def interpolate_images(image1, image2, alpha):
    arr1 = pygame.surfarray.array3d(image1)
    arr2 = pygame.surfarray.array3d(image2)
    interpolated = (arr1 * (1 - alpha) + arr2 * alpha).astype(np.uint8)
    return pygame.surfarray.make_surface(interpolated)

def prepare_image(image, crop_width, crop_height):
    cropped_surface = pygame.Surface((crop_width, crop_height), pygame.SRCALPHA)
    cropped_surface.blit(image, (0, -50))
    return cropped_surface

def main():
    pygame.init()

    screen = pygame.display.set_mode(final_resolution, pygame.FULLSCREEN)
    pygame.display.set_caption("The Most Polish Landscape")
    clock = pygame.time.Clock()

    # Load the overlay with transparency
    overlay_image = pygame.image.load(overlay_path).convert_alpha()

    current_index = 1
    current_image_path = os.path.join(image_directory, f"{current_index}.bmp")
    current_image = load_image(current_image_path)

    if current_image is None:
        print(f"Image {current_image_path} not found. Waiting...")
        while current_image is None:
            time.sleep(0.1)
            current_image = load_image(current_image_path)

    current_image = current_image.convert()

    running = True
    start_time = time.time()
    total_images = 1
    last_image_time = start_time

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key in [pygame.K_ESCAPE, pygame.K_q]):
                print("Closing the program...")
                running = False

        next_image_path = os.path.join(image_directory, f"{current_index + 1}.bmp")
        next_image = load_image(next_image_path)

        if next_image:
            print(f"Interpolating between images {current_index} and {current_index + 1}...")
            next_image = next_image.convert()

            total_images += 1
            last_image_time = time.time()

            for frame in range(frames_to_interpolate):
                alpha = frame / frames_to_interpolate
                interpolated_image = interpolate_images(current_image, next_image, alpha)
                final_image = prepare_image(interpolated_image, final_resolution[0], final_resolution[1])
                
                screen.blit(final_image, (0, 0)) # Render the frame
                screen.blit(overlay_image, (0, 0)) # Overlay at the top

                elapsed_time = time.time() - start_time
                time_since_last_image = time.time() - last_image_time
                average_images_per_second = total_images / elapsed_time if time_since_last_image < 1 else 0

                # Format elapsed time as HH:MM:SS.ss
                hours, remainder = divmod(elapsed_time, 3600)
                minutes, seconds = divmod(remainder, 60)
                formatted_time = f"{int(hours):02}:{int(minutes):02}:{seconds:05.2f}"

                info_text = f"{formatted_time}, {total_images} ({average_images_per_second:.2f})"
                draw_text(screen, info_text, 10, 10)

                pygame.display.flip()
                clock.tick(target_fps)

            current_index += 1
            current_image = next_image
        else:
            print(f"Waiting for image: {current_index + 1}...")
            final_image = prepare_image(current_image, final_resolution[0], final_resolution[1])
            
            screen.blit(final_image, (0, 0)) # Render the frame
            screen.blit(overlay_image, (0, 0)) # Overlay at the top

            elapsed_time = time.time() - start_time
            time_since_last_image = time.time() - last_image_time
            average_images_per_second = total_images / elapsed_time if time_since_last_image < 1 else 0
            info_text = f"{elapsed_time:.2f}, {total_images} ({average_images_per_second:.2f})"
            draw_text(screen, info_text, 10, 10)

            pygame.display.flip()
            time.sleep(0.1)

    pygame.quit()

def draw_text(screen, text, x, y):
    font = pygame.font.SysFont("Arial", 24)
    text_surface = font.render(text, True, (255, 255, 255))
    background_surface = pygame.Surface(text_surface.get_size())
    background_surface.fill((0, 0, 0))
    screen.blit(background_surface, (x, y))
    screen.blit(text_surface, (x, y))

if __name__ == "__main__":
    main()