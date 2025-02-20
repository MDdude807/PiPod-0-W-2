import os
import sys
import io
import pygame
import traceback
from mutagen.mp3 import MP3
from mutagen.id3 import ID3NoHeaderError, APIC

# Handle Windows-specific imports
WINDOWS = sys.platform.startswith('win')
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

# Set music path
current_path = os.getcwd()
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
            # Windows detection with win32api
            drives = win32api.GetLogicalDriveStrings().split('\000')[:-1]
            for drive in drives:
                try:
                    volume_name = win32api.GetVolumeInformation(drive)[0]
                    print(f"Checking drive {drive} with volume name: {volume_name}")
                    if volume_name == "PIPOD":
                        print(f"Found PIPOD drive at {drive}")
                        pipod_found = True
                        handle_pipod_drive(drive)
                        break
                except Exception as e:
                    print(f"Error checking Windows drive {drive}: {e}")
                    continue
        elif WINDOWS:
            # Fallback Windows detection without win32api
            drives = [f"{d}:\\" for d in "DEFGHIJKLMNOPQRSTUVWXYZ"]
            for drive in drives:
                try:
                    if os.path.exists(drive):
                        volume_name = os.path.basename(drive.rstrip(':\\'))
                        if volume_name == "PIPOD":
                            print(f"Found PIPOD drive at {drive}")
                            pipod_found = True
                            handle_pipod_drive(drive)
                            break
                except Exception as e:
                    print(f"Error checking drive {drive}: {e}")
                    continue
        elif sys.platform == "darwin":
            # macOS detection
            volumes_path = "/Volumes"
            if os.path.exists(volumes_path):
                for volume in os.listdir(volumes_path):
                    volume_path = os.path.join(volumes_path, volume)
                    if volume == "PIPOD" and os.path.ismount(volume_path):
                        print(f"Found PIPOD drive at {volume_path}")
                        pipod_found = True
                        handle_pipod_drive(volume_path)
                        break
                if pipod_found:
                    return pipod_found
        
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
    display.fill((255, 255, 255))
    for i, option in enumerate(options):
        if i == selected_option:
            pygame.draw.rect(display, (200, 200, 255), (20, 30 + i * 60, 600, 50))  # Scale up rectangle
        text_surface = font.render(option, True, (0, 0, 0) if i == selected_option else (128, 128, 128))
        display.blit(text_surface, (40, 40 + i * 60))  # Double the spacing

# Update draw_metadata_screen
def draw_metadata_screen(display):
    display.fill((255, 255, 255))
    if cover_image:
        cover_rect = cover_image.get_rect(center=(DISPLAY_WIDTH // 2, 120))  # Move down
        display.blit(cover_image, cover_rect)
    title_text = font.render(song_title, True, (0, 0, 0))
    title_rect = title_text.get_rect(center=(DISPLAY_WIDTH // 2, 280))  # Double from 140
    display.blit(title_text, title_rect)
    artist_text = small_font.render(artist_name, True, (0, 0, 0))
    artist_rect = artist_text.get_rect(center=(DISPLAY_WIDTH // 2, 340))  # Double from 170
    display.blit(artist_text, artist_rect)
    
    # Scale volume bars
    if volume_visible:
        bar_width = 40  # Double from 20
        bar_height = 20  # Double from 10
        max_bars = 10
        filled_bars = int(volume * max_bars)
        for i in range(max_bars):
            x = 20 + (i * (bar_width + 4))  # Double spacing
            y = DISPLAY_HEIGHT - 60  # Move up from bottom
            color = (0, 255, 0) if i < filled_bars else (200, 200, 200)
            pygame.draw.rect(display, color, (x, y, bar_width, bar_height))
    
    # Scale progress bar and time display
    if song_length > 0:
        current_time = pygame.mixer.music.get_pos()
        remaining_time = song_length - current_time
        progress = current_time / song_length
        progress_bar_width = int(DISPLAY_WIDTH * progress)
        pygame.draw.rect(display, (0, 255, 0), (0, 400, progress_bar_width, 40))  # Double height
        
        current_time_formatted = format_time(current_time)
        remaining_time_formatted = f"-{format_time(remaining_time)}"
        
        current_time_text = small_font.render(current_time_formatted, True, (0, 0, 0))
        remaining_time_text = small_font.render(remaining_time_formatted, True, (0, 0, 0))
        display.blit(current_time_text, (20, 460))  # Double from 230
        display.blit(remaining_time_text, (DISPLAY_WIDTH - 100, 460))  # Adjust position

# Update draw_settings_menu
def draw_settings_menu(display):
    display.fill((255, 255, 255))
    for i, option in enumerate(options):
        if i == selected_option:
            pygame.draw.rect(display, (200, 200, 255), (20, 30 + i * 60, 600, 50))
        text_surface = font.render(option, True, (0, 0, 0) if i == selected_option else (128, 128, 128))
        display.blit(text_surface, (40, 40 + i * 60))
        if option == 'Repeat Playlist':
            status_text = small_font.render(f"{'On' if repeat_playlist else 'Off'}", True, (0, 0, 0))
            display.blit(status_text, (DISPLAY_WIDTH - 120, 40 + i * 60))
    return_text = small_font.render("Press LEFT to go back", True, (0, 0, 0))
    display.blit(return_text, (DISPLAY_WIDTH // 2 - 160, DISPLAY_HEIGHT - 100))

# Update draw_browse_music
def draw_browse_music(display):
    display.fill((255, 255, 255))
    for i, option in enumerate(options):
        if i == selected_option:
            pygame.draw.rect(display, (200, 200, 255), (20, 30 + i * 60, 600, 50))
        text_surface = font.render(option, True, (0, 0, 0) if i == selected_option else (128, 128, 128))
        display.blit(text_surface, (40, 40 + i * 60))

def draw_sync_screen(display):
    """Draw the sync screen with transfer status"""
    display.fill((255, 255, 255))
    global sync_attempted  # Add this at the start of the function
    
    if not sync_attempted:
        if check_and_sync_usb():
            status_text = font.render("Transfer Complete", True, (0, 0, 0))
        else:
            status_text = font.render("No PIPOD drive found", True, (0, 0, 0))
        sync_attempted = True  # Mark that we've attempted sync
    else:
        # Show last sync result
        if sync_result:
            status_text = font.render("Transfer Complete", True, (0, 0, 0))
        else:
            status_text = font.render("No PIPOD drive found", True, (0, 0, 0))
    
    text_rect = status_text.get_rect(center=(DISPLAY_WIDTH // 2, DISPLAY_HEIGHT // 2))
    display.blit(status_text, text_rect)
    return_text = small_font.render("Press LEFT to go back", True, (0, 0, 0))
    display.blit(return_text, (DISPLAY_WIDTH // 2 - 160, DISPLAY_HEIGHT - 100))

# Main event loop
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN:
                selected_option = (selected_option + 1) % len(options)
            elif event.key == pygame.K_UP:
                selected_option = (selected_option - 1) % len(options)
            elif event.key == pygame.K_RETURN:
                if not in_metadata_screen:
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
                        in_settings_menu = True  # Enter the settings menu
                        options = ['Repeat Playlist']  # Add the repeat option in the settings menu
                        selected_option = 0
                        slide_in_from_right(display, draw_settings_menu)
                    elif options[selected_option] == "All Songs":
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
                    elif in_settings_menu and options[selected_option] == 'Repeat Playlist':
                        # Toggle the repeat option
                        repeat_playlist = not repeat_playlist
                        print(f"Repeat {'enabled' if repeat_playlist else 'disabled'}")
                    else:
                        selected_folder = options[selected_option]
                        if current_folder is None:  # We're in all songs view
                            # Handle selection in all songs view
                            current_track_index = options.index(selected_folder)
                            play_music(mp3_files[current_track_index])
                            show_metadata_screen = True
                            in_metadata_screen = True
                            slide_out_to_left(display, draw_browse_music)
                            slide_in_from_right(display, draw_metadata_screen)
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
                                    show_metadata_screen = True
                                    in_metadata_screen = True
                                    slide_out_to_left(display, draw_browse_music)
                                    slide_in_from_right(display, draw_metadata_screen)
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
                        mp3_files = get_folder_contents(current_folder)  # Refresh the folder contents
                        options = mp3_files if mp3_files else ['No MP3 Files']  # Update options
                        selected_option = 0 if options else selected_option  # Reset selection if empty
                        slide_in_from_left(display, draw_browse_music)
                    else:
                        slide_out_to_right(display, draw_browse_music)
                        in_browse_music = False  # Exit browse music
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