#!/usr/bin/env python3
import os
import sys
import io
import pygame
import traceback
from mutagen.mp3 import MP3
from mutagen.id3 import ID3NoHeaderError, APIC
from pygame import gfxdraw  # For anti-aliased shapes

# Add these color constants at the top with other constants
COLORS = {
    'background': (248, 250, 252),    # Light clean background
    'highlight': (56, 114, 250),      # Modern blue highlight
    'highlight_light': (236, 242, 254),  # Very light blue for backgrounds
    'text': (31, 41, 55),            # Dark gray text
    'text_secondary': (107, 114, 128),  # Secondary text
    'progress': (34, 197, 94),        # Progress bar green
    'volume': (56, 114, 250),         # Volume bar (same as highlight)
    'inactive': (229, 231, 235),      # Inactive elements
    'shadow': (226, 232, 240),        # Subtle shadow color
    'white': (255, 255, 255),          # Pure white for contrast
    # Dark mode colors
    'dark_background': (18, 18, 18),    
    'dark_highlight': (56, 114, 250),   # Keep highlight color
    'dark_highlight_light': (30, 41, 59),
    'dark_text': (229, 231, 235),     
    'dark_text_secondary': (156, 163, 175),
    'dark_progress': (34, 197, 94),    # Keep progress color
    'dark_volume': (56, 114, 250),     # Keep volume color
    'dark_inactive': (55, 65, 81),     
    'dark_shadow': (17, 24, 39),       
    'dark_white': (31, 41, 55),        
}

# Handle Windows-specific imports
WINDOWS = sys.platform.startswith('win')
LINUX = sys.platform.startswith('linux')
MACOS = sys.platform.startswith('darwin')
if WINDOWS:
    try:
        import win32api
        import win32file
        HAVE_WIN32 = True
    except ImportError:
        print("PyWin32 not found. Installing...")
        try:
            import subprocess
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pywin32'])
            import win32api
            import win32file
            HAVE_WIN32 = True
        except Exception as e:
            print(f"Error installing pywin32: {e}")
            HAVE_WIN32 = False
else:
    HAVE_WIN32 = False

# Initialize Pygame
pygame.init()

def format_time(milliseconds):
    """Convert milliseconds to M:SS format"""
    total_seconds = int(milliseconds / 1000)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"

# Update display dimensions
DISPLAY_WIDTH = 480
DISPLAY_HEIGHT = 800
display = pygame.display.set_mode((DISPLAY_WIDTH, DISPLAY_HEIGHT))
pygame.display.set_caption("Music Player")

# Scale fonts
font = pygame.font.SysFont('Arial', 40)  # Double the size from 20
small_font = pygame.font.SysFont('Arial', 30)  # Double from 15

# Options setup
main_menu_options = ['Browse Music', 'Show Current Track', 'Settings', 'Sync USB', 'Option 5']
options = main_menu_options[:]
selected_option = 0

# Initialize music mixer
pygame.mixer.init()

# Update music path handling
if WINDOWS:
    current_path = os.getcwd()
elif LINUX:
    current_path = os.path.expanduser('~/Music')  # Use standard XDG music directory
    if not os.path.exists(current_path):
        current_path = os.path.expanduser('~')  # Fallback to home directory
else:
    current_path = os.path.expanduser('~')

music_path = os.path.join(current_path, 'music')

# Global variables for song metadata and current state
current_mp3_file = None
current_track_index = -1  # To track the currently playing track index
song_title = "Unknown Song"
artist_name = "Unknown Artist"
cover_image = None  # For storing the image
show_metadata_screen = False
song_length = 0  # Total length of the song in milliseconds
mp3_files = []  # List of MP3 files in the current folder
is_playing = False  # State of music playback
in_metadata_screen = False  # To track if we are in the metadata screen
in_settings_menu = False  # To track if we are in the settings menu
in_browse_music = False  # To track if we are in the browse music screen
in_sync_screen = False  # To track if we are in the sync screen
previous_folders = []  # To track the history of browsed folders
volume = 0.5  # Initial volume level (50%)
volume_visible = True  # Flag to control visibility of volume bars
volume_timer = 0  # Timer for tracking volume visibility duration
repeat_playlist = False  # Flag to control repeating
# Add with other global variables
sync_attempted = False  # Track if sync has been attempted this session
sync_result = False    # Track the result of the last sync attempt
dark_mode = False  # Track dark mode state

# Set the initial volume
pygame.mixer.music.set_volume(volume)

def get_folder_contents(folder_path):
    """Returns a list of MP3 files (sorted by track number) and directories in the specified folder."""
    try:
        contents = []
        
        # Add "All Songs" option only in the root music folder
        if folder_path == music_path:
            contents.append("All Songs")
        
        # Get directories
        directories = sorted([
            item for item in os.listdir(folder_path)
            if os.path.isdir(os.path.join(folder_path, item))
        ])
        contents.extend(directories)
        
        # Then get MP3 files with their track numbers
        mp3_files_with_tracks = []
        for f in os.listdir(folder_path):
            if f.lower().endswith('.mp3'):
                try:
                    audio = MP3(os.path.join(folder_path, f))
                    track = audio.tags.get('TRCK', ['0'])[0]
                    track_num = int(track.split('/')[0])
                    mp3_files_with_tracks.append((f, track_num))
                except:
                    mp3_files_with_tracks.append((f, 999))
        
        # Sort MP3 files by track number
        mp3_files_with_tracks.sort(key=lambda x: x[1])
        contents.extend([f[0] for f in mp3_files_with_tracks])
        
        print(f"Found contents in {folder_path}: {contents}")
        return contents
    except Exception as e:
        print(f"Error reading folder contents: {e}")
        return []

def get_all_songs(root_path):
    """Returns a list of all MP3 files in all subdirectories."""
    all_songs_with_tracks = []
    for root, dirs, files in os.walk(root_path):
        for file in files:
            if file.lower().endswith('.mp3'):
                full_path = os.path.join(root, file)
                try:
                    audio = MP3(full_path)
                    # Get track number, default to 0 if not found
                    track = audio.tags.get('TRCK', ['0'])[0]
                    # Handle track numbers like '1/12' by taking first number
                    track_num = int(track.split('/')[0])
                    all_songs_with_tracks.append((full_path, track_num))
                except:
                    # If we can't get track number, use 999 to put it at the end
                    all_songs_with_tracks.append((full_path, 999))
    
    # Sort by track number
    all_songs_with_tracks.sort(key=lambda x: x[1])
    # Extract just the paths in track order
    return [f[0] for f in all_songs_with_tracks]

def play_music(mp3_file):
    """Load and play the selected MP3 file and extract its metadata."""
    global current_mp3_file, song_title, artist_name, cover_image, song_length, is_playing
    try:
        pygame.mixer.music.load(mp3_file)
        pygame.mixer.music.play()
        current_mp3_file = mp3_file
        audio = MP3(mp3_file)
        song_title = audio.tags.get('TIT2', ['Unknown Song'])[0]
        artist_name = audio.tags.get('TPE1', ['Unknown Artist'])[0]
        song_length = int(audio.info.length * 1000)
        cover_image = None
        is_playing = True  # Make sure this is set to True
        print(f"Now playing: {song_title} from {mp3_file}")
    except Exception as e:
        print(f"Error in play_music: {e}")
        is_playing = False

def check_and_sync_usb():
    """Check for PIPOD USB drive and sync contents"""
    global sync_result
    pipod_found = False
    
    try:
        if WINDOWS and HAVE_WIN32:
            # Existing Windows detection code...
            pass
        elif WINDOWS:
            # Existing fallback Windows detection code...
            pass
        elif LINUX:
            # Linux/Debian detection
            mount_points = ['/media', '/mnt']
            for base in mount_points:
                if os.path.exists(base):
                    for user_dir in os.listdir(base):
                        user_path = os.path.join(base, user_dir)
                        if os.path.isdir(user_path):
                            for volume in os.listdir(user_path):
                                volume_path = os.path.join(user_path, volume)
                                if volume == "PIPOD" and os.path.ismount(volume_path):
                                    print(f"Found PIPOD drive at {volume_path}")
                                    pipod_found = True
                                    handle_pipod_drive(volume_path)
                                    break
        elif MACOS:
            # Existing macOS detection code...
            pass
        
        if pipod_found:
            sync_result = True
        else:
            sync_result = False
            
    except Exception as e:
        print(f"Error during drive detection: {e}")
        traceback.print_exc()
        sync_result = False
    
    return sync_result

def handle_pipod_drive(drive_path):
    """Set up or sync PiPod drive"""
    usb_music_path = os.path.join(drive_path, "music")
    
    # Check if music folder exists on drive
    if not os.path.exists(usb_music_path):
        print("Setting up new PiPod drive...")
        # Create folder structure on USB
        os.makedirs(usb_music_path, exist_ok=True)
        for folder in ['Albums', 'Artists', 'Playlists']:
            os.makedirs(os.path.join(usb_music_path, folder), exist_ok=True)
        print("PiPod folders created successfully")
        return

    # If we get here, drive has existing structure, sync contents
    print("Syncing PiPod contents...")
    try:
        # Sync each subfolder
        for folder in ['Albums', 'Artists', 'Playlists']:
            usb_folder = os.path.join(usb_music_path, folder)
            local_folder = os.path.join(music_path, folder)
            
            if not os.path.exists(usb_folder):
                print(f"Warning: {folder} folder not found on PiPod")
                continue
                
            # Create destination folder if it doesn't exist
            os.makedirs(local_folder, exist_ok=True)
            
            # Copy new files from USB to local
            for root, dirs, files in os.walk(usb_folder):
                # Get relative path from USB music folder
                rel_path = os.path.relpath(root, usb_folder)
                dest_root = os.path.join(local_folder, rel_path)
                
                # Create subdirectories
                for dir_name in dirs:
                    os.makedirs(os.path.join(dest_root, dir_name), exist_ok=True)
                
                # Copy files
                for file_name in files:
                    if file_name.lower().endswith('.mp3'):
                        src_file = os.path.join(root, file_name)
                        dest_file = os.path.join(dest_root, file_name)
                        if not os.path.exists(dest_file):
                            print(f"Copying: {file_name}")
                            import shutil
                            shutil.copy2(src_file, dest_file)
        
        print("Sync completed successfully")
    except Exception as e:
        print(f"Error during sync: {e}")
        traceback.print_exc()

# Required folders creation without "All songs"
required_folders = ['Playlists', 'Albums', 'Artists']
for folder in required_folders:
    folder_path = os.path.join(music_path, folder)
    os.makedirs(folder_path, exist_ok=True)

# Fix indentation - remove the extra spaces
check_and_sync_usb()

# Initialize current folder and mp3_files
current_folder = music_path  # Track the current folder
mp3_files = get_folder_contents(current_folder)  # Initialize with the contents of the music folder

def slide_in_from_right(display, draw_func):
    clock = pygame.time.Clock()
    temp_surface = display.copy()
    for x in range(DISPLAY_WIDTH, -1, -20):
        display.fill((255, 255, 255))
        draw_func(temp_surface)
        display.blit(temp_surface, (x, 0))
        pygame.display.flip()
        clock.tick(60)

def slide_out_to_right(display, draw_func):
    clock = pygame.time.Clock()
    temp_surface = display.copy()
    for x in range(0, DISPLAY_WIDTH + 1, 20):
        display.fill((255, 255, 255))
        draw_func(temp_surface)
        display.blit(temp_surface, (x, 0))
        pygame.display.flip()
        clock.tick(60)

def slide_in_from_left(display, draw_func):
    clock = pygame.time.Clock()
    temp_surface = display.copy()
    for x in range(-DISPLAY_WIDTH, 1, 20):
        display.fill((255, 255, 255))
        draw_func(temp_surface)
        display.blit(temp_surface, (x, 0))
        pygame.display.flip()
        clock.tick(60)

def slide_out_to_left(display, draw_func):
    clock = pygame.time.Clock()
    temp_surface = display.copy()
    for x in range(0, -DISPLAY_WIDTH - 1, -20):
        display.fill((255, 255, 255))
        draw_func(temp_surface)
        display.blit(temp_surface, (x, 0))
        pygame.display.flip()
        clock.tick(60)

# Update draw_main_menu
def draw_main_menu(display):
    display.fill(COLORS['background'] if not dark_mode else COLORS['dark_background'])
    for i, option in enumerate(options):
        y_pos = 30 + i * 70
        if i == selected_option:
            # Draw shadow and highlight with consistent style
            draw_rounded_rect(display, COLORS['shadow'], (23, y_pos + 3, 440, 50), 15)
            draw_rounded_rect(display, COLORS['highlight'], (20, y_pos, 440, 50), 15)
            text_color = COLORS['white']
        else:
            text_color = COLORS['text']
        text_surface = font.render(option, True, text_color)
        text_rect = text_surface.get_rect(midleft=(40, y_pos + 25))
        display.blit(text_surface, text_rect)

# Update draw_metadata_screen
def draw_metadata_screen(display):
    display.fill(COLORS['background'] if not dark_mode else COLORS['dark_background'])
    
    # Draw pause indicator with unified style
    if not pygame.mixer.music.get_busy() and current_mp3_file:
        pause_x = 30
        pause_y = 30
        bar_width = 8
        bar_height = 25
        gap = 8
        
        for x_offset in [0, bar_width + gap]:
            draw_rounded_rect(display, COLORS['text'], 
                            (pause_x + x_offset, pause_y, bar_width, bar_height), 3)
    
    if cover_image:
        # Add subtle background behind cover art
        cover_bg_size = 220
        draw_rounded_rect(display, COLORS['highlight_light'],
                         (DISPLAY_WIDTH//2 - cover_bg_size//2, 40,
                          cover_bg_size, cover_bg_size), 20)
        cover_rect = cover_image.get_rect(center=(DISPLAY_WIDTH // 2, 150))
        display.blit(cover_image, cover_rect)
    
    # Title section with refined styling
    title_bg_rect = (20, 220, DISPLAY_WIDTH - 40, 60)
    draw_rounded_rect(display, COLORS['highlight_light'], title_bg_rect, 15)
    title_text = font.render(song_title, True, COLORS['text'])
    title_rect = title_text.get_rect(center=(DISPLAY_WIDTH // 2, 250))
    display.blit(title_text, title_rect)
    
    # Artist name with subtle styling
    artist_text = small_font.render(artist_name, True, COLORS['text_secondary'])
    artist_rect = artist_text.get_rect(center=(DISPLAY_WIDTH // 2, 300))
    display.blit(artist_text, artist_rect)
    
    # Progress bar with refined styling
    if song_length > 0:
        bar_height = 6  # Slightly thinner for elegance
        bar_y = 350
        margin = 40
        
        # Get accurate current time
        current_time = pygame.mixer.music.get_pos()
        if current_time == -1:  # If get_pos returns -1, use previous valid time
            current_time = 0
        
        # Calculate remaining time based on song_length and current_time
        remaining_time = song_length - current_time
        
        # Calculate progress for progress bar
        progress = current_time / song_length if song_length > 0 else 0
        
        # Background track
        pygame.draw.rect(display, COLORS['inactive'],
                        (margin, bar_y, DISPLAY_WIDTH - (2 * margin), bar_height),
                        border_radius=bar_height//2)
        
        # Progress fill
        if progress > 0:
            progress_width = int((DISPLAY_WIDTH - (2 * margin)) * progress)
            if progress_width > 0:
                pygame.draw.rect(display, COLORS['progress'],
                               (margin, bar_y, progress_width, bar_height),
                               border_radius=bar_height//2)
        
        # Time display with refined positioning
        time_font = small_font
        # Format times ensuring they're non-negative
        current_time_str = format_time(max(0, current_time))
        remaining_time_str = format_time(max(0, remaining_time))
        
        current_time_text = time_font.render(current_time_str, 
                                           True, COLORS['text_secondary'])
        remaining_time_text = time_font.render(f"-{remaining_time_str}", 
                                             True, COLORS['text_secondary'])
        
        # Position time text
        display.blit(current_time_text, (margin, bar_y + 15))
        remaining_time_rect = remaining_time_text.get_rect(right=DISPLAY_WIDTH - margin)
        display.blit(remaining_time_text, (remaining_time_rect.x, bar_y + 15))
    
    # Volume bars with refined styling
    if volume_visible:
        bar_width = 20
        bar_height = 8
        max_bars = 10
        filled_bars = int(volume * max_bars)
        total_width = (bar_width + 4) * max_bars
        start_x = (DISPLAY_WIDTH - total_width) // 2
        y = DISPLAY_HEIGHT - 80
        
        for i in range(max_bars):
            x = start_x + (i * (bar_width + 4))
            if i < filled_bars:
                # Active bars with subtle shadow
                draw_rounded_rect(display, COLORS['shadow'], 
                                (x + 1, y + 1, bar_width, bar_height), 3)
                draw_rounded_rect(display, COLORS['volume'], 
                                (x, y, bar_width, bar_height), 3)
            else:
                draw_rounded_rect(display, COLORS['inactive'], 
                                (x, y, bar_width, bar_height), 3)

def draw_settings_menu(display):
    display.fill(COLORS['background'] if not dark_mode else COLORS['dark_background'])
    for i, option in enumerate(options):
        y_pos = 30 + i * 70
        if i == selected_option:
            draw_rounded_rect(display, 
                            COLORS['shadow'] if not dark_mode else COLORS['dark_shadow'],
                            (23, y_pos + 3, 440, 50), 15)
            draw_rounded_rect(display, COLORS['highlight'], (20, y_pos, 440, 50), 15)
            text_color = COLORS['white'] if not dark_mode else COLORS['dark_white']
        else:
            text_color = COLORS['text'] if not dark_mode else COLORS['dark_text']
        
        text_surface = font.render(option, True, text_color)
        text_rect = text_surface.get_rect(midleft=(40, y_pos + 25))
        display.blit(text_surface, text_rect)
        
        # Only display the current state, don't modify it
        if option in ['Repeat Playlist', 'Dark Mode']:
            status = 'On' if (
                (option == 'Repeat Playlist' and repeat_playlist) or
                (option == 'Dark Mode' and dark_mode)
            ) else 'Off'
            status_text = small_font.render(status, True, 
                                          COLORS['text_secondary'] if not dark_mode else COLORS['dark_text_secondary'])
            status_rect = status_text.get_rect(midright=(DISPLAY_WIDTH - 40, y_pos + 25))
            display.blit(status_text, status_rect)

def draw_browse_music(display):
    display.fill(COLORS['background'] if not dark_mode else COLORS['dark_background'])
    for i, option in enumerate(options):
        y_pos = 30 + i * 70  # Consistent spacing with main menu
        if i == selected_option:
            # Draw shadow and highlight with consistent style
            draw_rounded_rect(display, COLORS['shadow'], (23, y_pos + 3, 440, 50), 15)
            draw_rounded_rect(display, COLORS['highlight'], (20, y_pos, 440, 50), 15)
            text_color = COLORS['white']
        else:
            text_color = COLORS['text']
        text_surface = font.render(option, True, text_color)
        text_rect = text_surface.get_rect(midleft=(40, y_pos + 25))
        display.blit(text_surface, text_rect)

def draw_sync_screen(display):
    display.fill(COLORS['background'])
    global sync_attempted
    
    # Center status message with consistent styling
    if not sync_attempted:
        if check_and_sync_usb():
            message = "Transfer Complete"
        else:
            message = "No PIPOD drive found"
        sync_attempted = True
    else:
        message = "Transfer Complete" if sync_result else "No PIPOD drive found"
    
    # Draw status message with background
    status_bg_rect = (20, DISPLAY_HEIGHT//2 - 40, DISPLAY_WIDTH - 40, 80)
    draw_rounded_rect(display, COLORS['highlight_light'], status_bg_rect, 15)
    status_text = font.render(message, True, COLORS['text'])
    status_rect = status_text.get_rect(center=(DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2))
    display.blit(status_text, status_rect)
    
    # Back button with consistent styling
    back_text = small_font.render("Press LEFT to go back", True, COLORS['text_secondary'])
    back_rect = back_text.get_rect(center=(DISPLAY_WIDTH // 2, DISPLAY_HEIGHT - 60))
    draw_rounded_rect(display, COLORS['highlight_light'], 
                     (back_rect.x - 20, back_rect.y - 10, 
                      back_rect.width + 40, back_rect.height + 20), 10)
    display.blit(back_text, back_rect)

def draw_rounded_rect(surface, color, rect, radius):
    """Draw a rounded rectangle with anti-aliasing"""
    x, y, width, height = rect
    
    # Draw the main rectangle
    if width > 2*radius and height > 2*radius:
        pygame.draw.rect(surface, color, (x + radius, y, width - 2*radius, height))
        pygame.draw.rect(surface, color, (x, y + radius, width, height - 2*radius))
    
    # Draw the corners with anti-aliasing
    for point in [(x + radius, y + radius),
                 (x + width - radius, y + radius),
                 (x + radius, y + height - radius),
                 (x + width - radius, y + height - radius)]:
        pygame.gfxdraw.aacircle(surface, int(point[0]), int(point[1]), radius, color)
        pygame.gfxdraw.filled_circle(surface, int(point[0]), int(point[1]), radius, color)

# Main event loop
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN:
                # Only handle menu navigation, no settings toggle
                selected_option = (selected_option + 1) % len(options)
            elif event.key == pygame.K_UP:
                # Only handle menu navigation, no settings toggle
                selected_option = (selected_option - 1) % len(options)
            elif event.key == pygame.K_RETURN:
                if in_settings_menu:
                    if options[selected_option] == 'Repeat Playlist':
                        repeat_playlist = not repeat_playlist
                        print(f"Repeat playlist: {'On' if repeat_playlist else 'Off'}")
                    elif options[selected_option] == 'Dark Mode':
                        dark_mode = not dark_mode
                        print(f"Dark mode: {'On' if dark_mode else 'Off'}")
                elif not in_metadata_screen:
                    if options[selected_option] == 'Sync USB':
                        slide_out_to_left(display, draw_main_menu)
                        sync_attempted = False  # Reset sync attempt flag
                        slide_in_from_right(display, draw_sync_screen)
                        in_sync_screen = True
                    elif options[selected_option] == 'Browse Music':
                        slide_out_to_left(display, draw_main_menu)
                        if current_folder != music_path:
                            previous_folders.append(current_folder)  # Save current folder to history
                        current_folder = music_path
                        mp3_files = get_folder_contents(current_folder)  # Refresh the folder contents
                        options = mp3_files if mp3_files else ['No MP3 Files']  # Update options
                        selected_option = 0 if options else selected_option  # Reset selection if empty
                        in_browse_music = True
                        slide_in_from_right(display, draw_browse_music)
                    elif options[selected_option] == 'Show Current Track':
                        slide_out_to_left(display, draw_main_menu)
                        show_metadata_screen = True  # Enter the metadata screen
                        in_metadata_screen = True  # Update the in_metadata_screen flag
                        slide_in_from_right(display, draw_metadata_screen)
                    elif options[selected_option] == 'Settings':
                        slide_out_to_left(display, draw_main_menu)
                        in_settings_menu = True
                        options = ['Repeat Playlist', 'Dark Mode']  # Add Dark Mode option
                        selected_option = 0
                        slide_in_from_right(display, draw_settings_menu)
                    elif options[selected_option] == "All Songs":
                        # Add animation transitions
                        slide_out_to_left(display, draw_browse_music)
                        
                        # Get all songs but keep them in the browse music view
                        all_songs = get_all_songs(music_path)
                        if all_songs:
                            # Convert full paths to just filenames for display
                            song_names = [os.path.basename(song) for song in all_songs]
                            options = song_names
                            mp3_files = all_songs  # Keep full paths for playback
                            selected_option = 0
                            current_folder = None  # Special case to indicate we're in all songs view
                            print(f"Showing all songs: {len(song_names)} songs found")
                        else:
                            options = ['No MP3 Files']
                            mp3_files = []
                            selected_option = 0
                            print("No songs found")
                        
                        # Add animation for new screen
                        slide_in_from_right(display, draw_browse_music)
                    else:
                        selected_folder = options[selected_option]
                        if current_folder is None:  # We're in all songs view
                            # Handle selection in all songs view
                            current_track_index = options.index(selected_folder)
                            play_music(mp3_files[current_track_index])
                        else:  # We're in normal folder view
                            selected_path = os.path.join(current_folder, selected_folder)
                            if os.path.isdir(selected_path):
                                slide_out_to_left(display, draw_browse_music)
                                if current_folder != selected_path:
                                    previous_folders.append(current_folder)
                                current_folder = selected_path
                                mp3_files = get_folder_contents(current_folder)
                                options = mp3_files if mp3_files else ['No MP3 Files']
                                selected_option = 0 if options else selected_option
                                slide_in_from_right(display, draw_browse_music)
                            else:  # Play the MP3 file
                                if selected_folder != 'No MP3 Files':
                                    current_track_index = mp3_files.index(selected_folder) if selected_folder in mp3_files else -1
                                    play_music(selected_path)
            elif event.key == pygame.K_LEFT:
                if in_sync_screen:
                    slide_out_to_right(display, draw_sync_screen)
                    in_sync_screen = False
                    slide_in_from_left(display, draw_main_menu)
                if show_metadata_screen:
                    slide_out_to_right(display, draw_metadata_screen)
                    show_metadata_screen = False  # Hide metadata when going back
                    in_metadata_screen = False  # Reset the in_metadata_screen flag
                    slide_in_from_left(display, draw_main_menu)
                elif in_settings_menu:
                    slide_out_to_right(display, draw_settings_menu)
                    in_settings_menu = False  # Exit settings menu and return to main menu
                    options = main_menu_options[:]  # Reset options to main menu
                    selected_option = 0
                    slide_in_from_left(display, draw_main_menu)
                elif in_browse_music:
                    if previous_folders:
                        previous_folder = previous_folders.pop()  # Get the previous folder from history
                        slide_out_to_right(display, draw_browse_music)
                        current_folder = previous_folder
                        if current_folder == music_path:  # If we're back at the root music folder
                            mp3_files = get_folder_contents(current_folder)  # This will include "All Songs" and folders
                            options = mp3_files if mp3_files else ['No MP3 Files']
                        else:  # In a subfolder
                            mp3_files = get_folder_contents(current_folder)
                            options = mp3_files if mp3_files else ['No MP3 Files']
                        selected_option = 0 if options else selected_option
                        slide_in_from_left(display, draw_browse_music)
                    else:
                        slide_out_to_right(display, draw_browse_music)
                        in_browse_music = False
                        current_folder = music_path  # Reset to root music folder
                        options = main_menu_options[:]  # Reset options to main menu
                        selected_option = 0
                        slide_in_from_left(display, draw_main_menu)
                else:
                    options = main_menu_options[:]  # Reset options to main menu
                    selected_option = 0
            # Adjust volume with up and down arrows
            if in_metadata_screen:
                if event.key == pygame.K_UP:  # Increase volume
                    volume = min(volume + 0.1, 1.0)
                    pygame.mixer.music.set_volume(volume)
                    volume_visible = True
                    volume_timer = pygame.time.get_ticks() / 1000
                    print(f"Volume increased to {volume:.1f}")
                elif event.key == pygame.K_DOWN:  # Decrease volume
                    volume = max(volume - 0.1, 0.0)
                    pygame.mixer.music.set_volume(volume)
                    volume_visible = True
                    volume_timer = pygame.time.get_ticks() / 1000
                    print(f"Volume decreased to {volume:.1f}")
                
            # Move these out of the elif to make them independent key checks
            if event.key == pygame.K_i and in_metadata_screen:  # Previous song or restart
                print("I key pressed - checking current time")
                current_time = pygame.mixer.music.get_pos()
                print(f"Current time: {current_time}ms")
                
                if current_time > 30000:  # Over 30 seconds - restart current song
                    pygame.mixer.music.play()
                    print("Restarting current song")
                else:  # Under 30 seconds - try to go to previous song
                    if current_mp3_file:  # Only proceed if we have a current file
                        try:
                            current_folder = os.path.dirname(current_mp3_file)
                            print(f"Current folder: {current_folder}")
                            mp3_files_with_tracks = []
                            for f in os.listdir(current_folder):
                                if f.lower().endswith('.mp3'):
                                    try:
                                        audio = MP3(os.path.join(current_folder, f))
                                        track = audio.tags.get('TRCK', ['0'])[0]
                                        track_num = int(track.split('/')[0])
                                        mp3_files_with_tracks.append((f, track_num))
                                    except:
                                        mp3_files_with_tracks.append((f, 999))
                            
                            mp3_files_with_tracks.sort(key=lambda x: x[1])
                            mp3_files = [f[0] for f in mp3_files_with_tracks]
                            
                            if current_track_index > 0:
                                current_track_index -= 1
                                prev_song = os.path.join(current_folder, mp3_files[current_track_index])
                                print(f"Going to previous song: {mp3_files[current_track_index]}")
                                play_music(prev_song)
                            else:
                                pygame.mixer.music.play()  # Restart current song if at first track
                                print("At first song - restarting current song")
                        except Exception as e:
                            print(f"Error handling previous track: {e}")
                            pygame.mixer.music.play()  # Restart current song on error

            if event.key == pygame.K_o and in_metadata_screen:  # Skip to next song
                print("O key pressed - attempting to skip to next song")
                if current_mp3_file:
                    try:
                        current_folder = os.path.dirname(current_mp3_file)
                        print(f"Current folder: {current_folder}")
                        mp3_files_with_tracks = []
                        for f in os.listdir(current_folder):
                            if f.lower().endswith('.mp3'):
                                try:
                                    audio = MP3(os.path.join(current_folder, f))
                                    track = audio.tags.get('TRCK', ['0'])[0]
                                    track_num = int(track.split('/')[0])
                                    mp3_files_with_tracks.append((f, track_num))
                                except:
                                    mp3_files_with_tracks.append((f, 999))
                        
                        mp3_files_with_tracks.sort(key=lambda x: x[1])
                        mp3_files = [f[0] for f in mp3_files_with_tracks]
                        print(f"Found {len(mp3_files)} MP3 files")
                        
                        if current_track_index < len(mp3_files) - 1:
                            current_track_index += 1
                        else:
                            current_track_index = 0  # Loop back to first song regardless of repeat setting
                        
                        next_song = os.path.join(current_folder, mp3_files[current_track_index])
                        print(f"Playing next song: {mp3_files[current_track_index]}")
                        play_music(next_song)
                    except Exception as e:
                        print(f"Error handling next track: {e}")
                        traceback.print_exc()
                else:
                    print("No current song playing")

            # In the KEYDOWN event handler section, add this with the other key checks
            elif event.key == pygame.K_RIGHT and in_metadata_screen:  # Pause/Resume
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.pause()
                    is_playing = False
                    print("Music paused")
                else:
                    pygame.mixer.music.unpause()
                    is_playing = True
                    print("Music resumed")

    # Handle timer for volume invisibility
    if volume_visible:
        current_time = pygame.time.get_ticks() / 1000  # Current time in seconds
        if current_time - volume_timer >= 5:  # If 5 seconds have passed
            volume_visible = False  # Hide the volume bars

    # Check if the current song has ended and play the next one
    if not pygame.mixer.music.get_busy() and is_playing and current_track_index != -1:
        try:
            # Use current_mp3_file to get the current folder path
            current_folder = os.path.dirname(current_mp3_file)
            
            # Get list of MP3 files and their track numbers
            mp3_files_with_tracks = []
            for f in os.listdir(current_folder):
                if f.lower().endswith('.mp3'):
                    try:
                        audio = MP3(os.path.join(current_folder, f))
                        # Get track number, default to 0 if not found
                        track = audio.tags.get('TRCK', ['0'])[0]
                        # Handle track numbers like '1/12' by taking first number
                        track_num = int(track.split('/')[0])
                        mp3_files_with_tracks.append((f, track_num))
                    except:
                        # If we can't get track number, use 999 to put it at the end
                        mp3_files_with_tracks.append((f, 999))
            
            # Sort by track number
            mp3_files_with_tracks.sort(key=lambda x: x[1])
            # Extract just the filenames in track order
            mp3_files = [f[0] for f in mp3_files_with_tracks]
            
            print(f"Current folder: {current_folder}")
            print(f"Current track index: {current_track_index}")
            print(f"Total files in folder: {len(mp3_files)}")
            print(f"Files in folder (sorted by track): {mp3_files}")
            
            if current_track_index < len(mp3_files) - 1:
                current_track_index += 1
                next_song = os.path.join(current_folder, mp3_files[current_track_index])
                print(f"Playing next song: {mp3_files[current_track_index]}")
                play_music(next_song)
            elif repeat_playlist and mp3_files:
                current_track_index = 0
                next_song = os.path.join(current_folder, mp3_files[current_track_index])
                print(f"Restarting playlist with: {mp3_files[current_track_index]}")
                play_music(next_song)
            else:
                is_playing = False
                print("Playback complete - no more songs")
        except Exception as e:
            print(f"Error during playback continuation: {e}")
        traceback.print_exc()
        is_playing = False

    # Draw the appropriate screen
    if in_metadata_screen:
        draw_metadata_screen(display)
    elif in_settings_menu:
        draw_settings_menu(display)
    elif in_browse_music:
        draw_browse_music(display)
    elif in_sync_screen:
        draw_sync_screen(display)
    else:
        draw_main_menu(display)

    pygame.display.flip()  # Update display
    pygame.time.Clock().tick(60)  # Limit frame rate

# Add Debian-specific package installation check
def check_dependencies():
    """Check and install required dependencies"""
    try:
        if LINUX:
            # Check for required packages
            packages = ['python3-pygame', 'python3-mutagen']
            missing = []
            
            for pkg in packages:
                try:
                    subprocess.check_call(['dpkg', '-s', pkg], 
                                        stdout=subprocess.DEVNULL, 
                                        stderr=subprocess.DEVNULL)
                except subprocess.CalledProcessError:
                    missing.append(pkg)
            
            if missing:
                print("Missing required packages. Installing...")
                try:
                    subprocess.check_call(['sudo', 'apt-get', 'update'])
                    subprocess.check_call(['sudo', 'apt-get', 'install', '-y'] + missing)
                    print("Dependencies installed successfully")
                except subprocess.CalledProcessError as e:
                    print(f"Error installing dependencies: {e}")
                    sys.exit(1)
    except Exception as e:
        print(f"Error checking dependencies: {e}")

# Add dependency check at startup
if __name__ == '__main__':
    if LINUX:
        check_dependencies()
