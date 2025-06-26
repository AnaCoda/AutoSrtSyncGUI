# SrtSyncGUIAuto.py
# Main script for SRT synchronization GUI with auto-fill functionality.

from __future__ import division

import FreeSimpleGUI as sg
import os.path

import logging

# Import utility modules
from utils.file_utils import (
    load_saved_times,
    save_times,
    update_file_list,
    validate_files,
)
from utils.srt_utils import setup_sync_args, perform_sync
from utils.audio_utils import run_auto_sync_threaded
from utils.batch_utils import (
    get_file_pairs,
    validate_batch_files,
    process_batch_sync,
    format_batch_results,
)

log = logging.getLogger(__name__)

# region Window Layout

file_list_column = [
    [
        sg.Text("Subtitle Folder"),
        sg.In(size=(40, 1), enable_events=True, key="-FOLDER-"),
        sg.FolderBrowse(initial_folder="D:/Video/"),
    ],
    [sg.Listbox(values=[], enable_events=True, size=(70, 10), key="-FILE LIST-", select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED)],
    [
        sg.Text("Video Folder (auto only)"),
        sg.In(size=(40, 1), enable_events=True, key="-FOLDER2-"),
        sg.FolderBrowse(initial_folder="D:/Video/"),
    ],
    [sg.Listbox(values=[], enable_events=True, size=(70, 10), key="-FILE LIST2-", select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED)],
    [sg.Text("💡 Tip: Use Ctrl+Click or Shift+Click for multi-selection in Batch mode", font=("Arial", 8), text_color="gray")],
]

# Open previously used times for a subtitle sync
times_list = load_saved_times()

# Single file sync tab
single_sync_tab = [
    [sg.Text("Choose an SRT from list on left:")],
    [sg.Text(size=(60, 2), key="-TOUT-")],
    [
        sg.Text(text="First SRT time: "),
        sg.InputText(key="-F1-", default_text=times_list[0]),
    ],
    [
        sg.Text(text="First Video time: "),
        sg.InputText(key="-T1-", default_text=times_list[1]),
    ],
    [
        sg.Text(text="Second SRT time: "),
        sg.InputText(key="-F2-", default_text=times_list[2]),
    ],
    [
        sg.Text(text="Second Video time: "),
        sg.InputText(key="-T2-", default_text=times_list[3]),
    ],
    [
        sg.Text(text="Encoding: "),
        sg.DropDown(["utf-8", "latin-1"], default_value="utf-8", key="-encoding-"),
    ],
    [sg.Button("SYNC", key="-SYNC-")],
    [sg.Text(size=(60, 3), key="-TOUT2-")],
    [sg.Text(text="AUTO: ")],
    [sg.Button("Auto Fill Times", key="-AUTO-")],
    [sg.Text("Progress:"), sg.ProgressBar(100, orientation='h', size=(30, 20), key='-PROGRESS-', visible=False)],
    [sg.Text(size=(60, 1), key="-PROGRESS_TEXT-", visible=False)],
    [sg.Text(size=(60, 2), key="-TOUT3-")],
    [
        sg.Text(text="Language: "),
        sg.DropDown(
            ["en-US", "en-GB", "fr-FR"], default_value="en-US", key="-language-"
        ),
    ],
    [sg.Text(text="Speech Confidence: "), sg.InputText(key="-SC-", default_text="70")],
    [
        sg.Text(text="Minimum words to match: "),
        sg.DropDown(["1", "2", "3", "4", "5"], default_value="3", key="-words-"),
        sg.Checkbox("Match substrings", key="-MSUB-"),
    ],
    [
        sg.Text(text="Seconds recognized: "),
        sg.InputText(key="-SR-", default_text="2.5"),
    ],
]

# Batch sync tab
batch_sync_tab = [
    [sg.Text("BATCH SYNC - Process Multiple Files", font=("Arial", 12, "bold"))],
    [sg.Text("📁 Use the folder browsers on the left to select folders")],
    [sg.Text("📋 Then use Ctrl+Click or Shift+Click to select multiple files from the lists")],
    [sg.Text("")],  # Spacer
    [sg.Text("File Pairing Preview (SRT ↔ Video):")],
    [sg.Listbox(values=[], size=(70, 8), key="-BATCH_PAIRS-")],
    [sg.Button("Start Batch Sync", key="-BATCH_SYNC-", disabled=True, size=(15, 1))],
    [sg.Text("")],  # Spacer
    [sg.Text("Batch Progress:")],
    [sg.ProgressBar(100, orientation='h', size=(50, 20), key='-BATCH_PROGRESS-', visible=False)],
    [sg.Text(size=(60, 2), key="-BATCH_STATUS-", visible=False)],
    [sg.Text(size=(60, 6), key="-BATCH_RESULTS-", font=("Courier", 9))],
]

# Create tabbed layout
srt_column = [
    [sg.TabGroup([
        [sg.Tab('Single File Sync', single_sync_tab, key='-SINGLE_TAB-')],
        [sg.Tab('Batch Sync', batch_sync_tab, key='-BATCH_TAB-')]
    ])]
]

# ----- Full layout -----
layout = [
    [
        sg.Column(file_list_column, vertical_alignment="top"),
        sg.VSeperator(),
        sg.Column(srt_column, vertical_alignment="top"),
    ]
]

window = sg.Window("Srt Sync", layout, resizable=True)
# endregion

def update_batch_pairing(srt_files, video_files, window):
    """Update the batch pairing preview and enable/disable batch sync button."""
    if srt_files and video_files:
        try:
            pairs = get_file_pairs(srt_files, video_files)
            pair_display = [f"{os.path.basename(srt)} ↔ {os.path.basename(video)}" 
                          for srt, video in pairs]
            window["-BATCH_PAIRS-"].update(pair_display)
            
            # Store the file lists for batch processing
            window["-BATCH_PAIRS-"].metadata = {'srt_files': srt_files, 'video_files': video_files}
            
            # Validate and enable/disable batch sync button
            valid, msg = validate_batch_files(srt_files, video_files)
            window["-BATCH_SYNC-"].update(disabled=not valid)
            
            if not valid:
                window["-BATCH_RESULTS-"].update(f"Validation: {msg}")
            else:
                window["-BATCH_RESULTS-"].update(f"Ready to sync {len(pairs)} file pairs")
        except Exception as e:
            window["-BATCH_RESULTS-"].update(f"Error creating pairs: {str(e)}")
    else:
        # Clear pairing if insufficient files
        window["-BATCH_PAIRS-"].update([])
        window["-BATCH_SYNC-"].update(disabled=True)
        if srt_files or video_files:
            window["-BATCH_RESULTS-"].update("Select files from both SRT and Video lists for batch sync")


def handle_file_selection(event, values, window):
    """Handle file selection for both single and batch modes."""
    global filename, filenamev
    
    if event == "-FILE LIST-":
        selected_files = values["-FILE LIST-"]
        if len(selected_files) > 1:  # Batch mode
            folder = values["-FOLDER-"]
            srt_files = [os.path.join(folder, f) for f in selected_files]
            
            video_files = []
            if values["-FILE LIST2-"] and len(values["-FILE LIST2-"]) > 0:
                video_folder = values["-FOLDER2-"]
                video_files = [os.path.join(video_folder, f) for f in values["-FILE LIST2-"]]
            
            update_batch_pairing(srt_files, video_files, window)
        else:  # Single mode
            filename = os.path.join(values["-FOLDER-"], selected_files[0])
            window["-TOUT-"].update(filename)
            
    elif event == "-FILE LIST2-":
        selected_files = values["-FILE LIST2-"]
        if len(selected_files) > 1:  # Batch mode
            folder = values["-FOLDER2-"]
            video_files = [os.path.join(folder, f) for f in selected_files]
            
            srt_files = []
            if values["-FILE LIST-"] and len(values["-FILE LIST-"]) > 0:
                srt_folder = values["-FOLDER-"]
                srt_files = [os.path.join(srt_folder, f) for f in values["-FILE LIST-"]]
            
            update_batch_pairing(srt_files, video_files, window)
        else:  # Single mode
            filenamev = os.path.join(values["-FOLDER2-"], selected_files[0])
            window["-TOUT3-"].update(filenamev)


def handle_single_sync(filename, values, window):
    """Handle single file sync operation."""
    valid, error_msg = validate_files(filename)
    if not valid:
        window["-TOUT2-"].update(error_msg)
        return
    
    # Setup arguments and save times
    args = setup_sync_args(filename, values, "_c.srt")
    save_times(values["-F1-"], values["-T1-"], values["-F2-"], values["-T2-"])
    
    # Perform synchronization
    success, message = perform_sync(args)
    window["-TOUT2-"].update(message)


def handle_auto_sync(filename, filenamev, values, window):
    """Handle auto sync operation."""
    valid, error_msg = validate_files(filename, filenamev, require_video=True)
    if not valid:
        if "Video" in error_msg:
            window["-TOUT3-"].update(error_msg)
        else:
            window["-TOUT2-"].update(error_msg)
        return
    
    window["-TOUT2-"].update("Working on auto filling times...")
    window.refresh()
    
    # Perform the auto sync in a separate thread to prevent GUI freezing
    results = run_auto_sync_threaded(filenamev, filename, window, values)
    
    if not results.get("success", False):
        window["-TOUT2-"].update(
            f"Auto sync failed: {results.get('error', 'Unknown error')}"
        )
        return
    
    # Update the UI with the calculated values
    window["-T1-"].update(results["btime1"])
    window["-F1-"].update(results["btime2"])
    window["-T2-"].update(results["etime1"])
    window["-F2-"].update(results["etime2"])
    window["-TOUT2-"].update("Successfully auto filled times!")
    
    # Save and sync
    save_times(
        results["btime2"], results["btime1"], results["etime2"], results["etime1"]
    )
    
    # Setup arguments and perform sync
    args = setup_sync_args(filename, values, "_autosync.srt")
    save_times(values["-F1-"], values["-T1-"], values["-F2-"], values["-T2-"])
    
    success, message = perform_sync(args)
    window["-TOUT2-"].update(message)


def handle_batch_sync(window, values):
    """Handle batch sync operation."""
    # Get file lists from the stored metadata
    pair_data = getattr(window["-BATCH_PAIRS-"], 'metadata', {})
    srt_files = pair_data.get('srt_files', [])
    video_files = pair_data.get('video_files', [])
    
    valid, error_msg = validate_batch_files(srt_files, video_files)
    if not valid:
        window["-BATCH_RESULTS-"].update(f"Error: {error_msg}")
        return
    
    # Show progress elements (both batch and individual)
    window['-BATCH_PROGRESS-'].update(visible=True)
    window['-BATCH_STATUS-'].update("Starting batch processing...", visible=True)
    window['-PROGRESS-'].update(visible=True)  # Show individual progress bar
    window['-PROGRESS_TEXT-'].update(visible=True)  # Show individual progress text
    window["-BATCH_RESULTS-"].update("Processing files...")
    window.refresh()
    
    # Get file pairs
    file_pairs = get_file_pairs(srt_files, video_files)
    
    # Process batch
    batch_results = process_batch_sync(file_pairs, values, window)
    
    # Update results
    results_text = format_batch_results(batch_results)
    window["-BATCH_RESULTS-"].update(results_text)
    
    # Hide progress elements (both batch and individual)
    window['-BATCH_PROGRESS-'].update(visible=False)
    window['-BATCH_STATUS-'].update(visible=False)
    window['-PROGRESS-'].update(visible=False)  # Hide individual progress bar
    window['-PROGRESS_TEXT-'].update(visible=False)  # Hide individual progress text

filename = None
filenamev = None

# Main event loop
while True:
    event, values = window.read()
    if event == "Exit" or event == sg.WIN_CLOSED:
        break
    
    # File/folder selection events
    if event == "-FOLDER-":
        folder = values["-FOLDER-"]
        fnames = update_file_list(folder, ".srt", is_srt=True)
        window["-FILE LIST-"].update(fnames)
        
    elif event == "-FOLDER2-":
        folder = values["-FOLDER2-"]
        fnames = update_file_list(folder, ".srt", is_srt=False)
        window["-FILE LIST2-"].update(fnames)
        
    elif event in ["-FILE LIST-", "-FILE LIST2-"]:
        try:
            handle_file_selection(event, values, window)
        except:
            pass
    
    # Sync operation events
    elif event == "-SYNC-":
        handle_single_sync(filename, values, window)
        
    elif event == "-AUTO-":
        handle_auto_sync(filename, filenamev, values, window)
        
    elif event == "-BATCH_SYNC-":
        handle_batch_sync(window, values)


window.close()
