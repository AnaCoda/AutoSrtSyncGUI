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

log = logging.getLogger(__name__)

# region Window Layout

file_list_column = [
    [
        sg.Text("Subtitle Folder"),
        sg.In(size=(40, 1), enable_events=True, key="-FOLDER-"),
        sg.FolderBrowse(initial_folder="D:/Video/"),
    ],
    [sg.Listbox(values=[], enable_events=True, size=(70, 10), key="-FILE LIST-")],
    [
        sg.Text("Video Folder (auto only)"),
        sg.In(size=(40, 1), enable_events=True, key="-FOLDER2-"),
        sg.FolderBrowse(initial_folder="D:/Video/"),
    ],
    [sg.Listbox(values=[], enable_events=True, size=(70, 10), key="-FILE LIST2-")],
]

# Open previously used times for a subtitle sync
times_list = load_saved_times()

# Input part
srt_column = [
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

# ----- Full layout -----
layout = [
    [
        sg.Column(file_list_column, vertical_alignment="top"),
        sg.VSeperator(),
        sg.Column(srt_column, vertical_alignment="top"),
    ]
]

window = sg.Window("Srt Sync", layout)
# endregion

filename = None
filenamev = None

while True:
    event, values = window.read()
    if event == "Exit" or event == sg.WIN_CLOSED:
        break    # region UI control
    # Folder name was filled in, make a list of files in the folder
    if event == "-FOLDER-":
        folder = values["-FOLDER-"]
        fnames = update_file_list(folder, ".srt", is_srt=True)
        window["-FILE LIST-"].update(fnames)
    elif event == "-FOLDER2-":
        folder = values["-FOLDER2-"]
        fnames = update_file_list(folder, ".srt", is_srt=False)
        window["-FILE LIST2-"].update(fnames)
    elif event == "-FILE LIST-":  # A file was chosen from the listbox
        try:
            filename = os.path.join(values["-FOLDER-"], values["-FILE LIST-"][0])
            window["-TOUT-"].update(filename)
        except:
            pass
    elif event == "-FILE LIST2-":  # A file was chosen from the listbox
        try:
            filenamev = os.path.join(values["-FOLDER2-"], values["-FILE LIST2-"][0])
            window["-TOUT3-"].update(filenamev)
        except:
            pass
    # endregion
    elif event == "-SYNC-":
        valid, error_msg = validate_files(filename)
        if not valid:
            window["-TOUT2-"].update(error_msg)
            continue

        # Setup arguments and save times
        args = setup_sync_args(filename, values, "_c.srt")
        save_times(values["-F1-"], values["-T1-"], values["-F2-"], values["-T2-"])        # Perform synchronization
        success, message = perform_sync(args)
        window["-TOUT2-"].update(message)

    elif event == "-AUTO-":
        valid, error_msg = validate_files(filename, filenamev, require_video=True)
        if not valid:
            if "Video" in error_msg:
                window["-TOUT3-"].update(error_msg)
            else:
                window["-TOUT2-"].update(error_msg)
            continue

        window["-TOUT2-"].update("Working on auto filling times...")
        window.refresh()  # Perform the auto sync in a separate thread to prevent GUI freezing
        results = run_auto_sync_threaded(filenamev, filename, window, values)

        if not results.get("success", False):
            window["-TOUT2-"].update(
                f"Auto sync failed: {results.get('error', 'Unknown error')}"
            )
            continue

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


window.close()
