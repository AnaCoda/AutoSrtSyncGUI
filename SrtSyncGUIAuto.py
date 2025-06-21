from __future__ import division

import FreeSimpleGUI as sg
import os.path
from typing import List, Tuple, Optional, Dict, Any, Union

import srt
import datetime
import srt_tools.utils
import logging

import speech_recognition as sr 
import moviepy as mp
import re

# For similar subtitles, will be implemented soon
from difflib import SequenceMatcher
def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

import sys
import threading

log = logging.getLogger(__name__)

#region Helper Functions

def load_saved_times() -> List[str]:
    """Load previously saved times or return defaults.
    
    Returns:
        List[str]: A list of 4 time strings in SRT timestamp format.
                  Returns default values ['00:00:00,000', ...] if file doesn't exist or can't be read.
    """
    if os.path.exists("savedtimes.txt"):
        try:
            with open("savedtimes.txt", "r") as fr:
                times_list = fr.read().split('\n')
                if len(times_list) >= 4:
                    return times_list[:4]
        except:
            pass
    return ['00:00:00,000', '00:00:00,000', '00:00:00,000', '00:00:00,000']

def save_times(f1: str, t1: str, f2: str, t2: str) -> None:
    """Save timing values to file.
    
    Args:
        f1 (str): First SRT timestamp (from subtitle)
        t1 (str): First video timestamp (target time)
        f2 (str): Second SRT timestamp (from subtitle)
        t2 (str): Second video timestamp (target time)
        
    Returns:
        None: This function doesn't return anything, saves to 'savedtimes.txt'
    """
    try:
        with open("savedtimes.txt", "w") as f:
            f.write(f"{f1}\n{t1}\n{f2}\n{t2}")
    except Exception as e:
        print(f"Error saving times: {e}")

def update_file_list(folder: str, file_extension: str, is_srt: bool = True) -> List[str]:
    """Update file list based on folder and extension.
    
    Args:
        folder (str): Path to the folder to scan for files
        file_extension (str): File extension to filter by (e.g., '.srt')
        is_srt (bool, optional): If True, include files with the extension; 
                                if False, exclude .srt files. Defaults to True.
    
    Returns:
        List[str]: List of filenames matching the criteria. Empty list if folder can't be read.
    """
    try:
        file_list = os.listdir(folder)
    except:
        return []
    
    if is_srt:
        return [f for f in file_list 
                if os.path.isfile(os.path.join(folder, f)) 
                and f.lower().endswith(file_extension)]
    else:
        return [f for f in file_list 
                if os.path.isfile(os.path.join(folder, f)) 
                and not f.lower().endswith(".srt")]

def setup_sync_args(filename: str, values: Dict[str, Any], output_suffix: str) -> Any:
    """Setup arguments for SRT synchronization.
    
    Args:
        filename (str): Path to the input SRT file
        values (Dict[str, Any]): Dictionary of GUI values containing timing and encoding settings
        output_suffix (str): Suffix to append to output filename (e.g., '_c.srt', '_autosync.srt')
    
    Returns:
        Any: Parsed arguments object from argparse, containing all synchronization parameters
    """
    sys.argv = ["SrtSyncGUI.py", "--input", filename, 
                "--f1", values["-F1-"], "--f2", values["-F2-"], 
                "--t1", values["-T1-"], "--t2", values["-T2-"], 
                "--output", filename.replace('.srt', output_suffix), 
                "--encoding", values["-encoding-"]]
    return parse_args()

def perform_sync(args: Any) -> Tuple[bool, str]:
    """Perform the actual subtitle synchronization.
    
    Args:
        args (Any): Parsed arguments object containing synchronization parameters
    
    Returns:
        Tuple[bool, str]: (success_flag, status_message)
                         - success_flag: True if sync completed successfully, False otherwise
                         - status_message: Human-readable status or error message
    """
    try:
        logging.basicConfig(level=args.log_level)
        angular, linear = calc_correction(
            args.to_start, args.to_end, args.from_start, args.from_end
        )
        
        srt_tools.utils.set_basic_args(args)
        corrected_subs = linear_correct_subs(args.input, angular, linear)
        output = srt_tools.utils.compose_suggest_on_fail(corrected_subs, strict=args.strict)
        
        try:
            args.output.write(output)
            args.output.close()
        except (UnicodeEncodeError, TypeError):  # Python 2 fallback
            args.output.write(output.encode(args.encoding))
        
        return True, f"Success! Synced subtitles saved as: {args.output.name}"
    except UnicodeDecodeError:
        return False, "Try a different encoding"
    except Exception as e:
        return False, f"Try a different encoding\n{str(e)}"

def validate_files(filename: Optional[str], filenamev: Optional[str] = None) -> Tuple[bool, str]:
    """Validate that required files are selected.
    
    Args:
        filename (Optional[str]): Path to subtitle file, can be None
        filenamev (Optional[str], optional): Path to video file, can be None. 
                                           Only validated if provided. Defaults to None.
    
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
                         - is_valid: True if all required files are present, False otherwise
                         - error_message: Descriptive error message if validation fails, empty string if valid
    """
    if not filename:
        return False, "Error: Subtitle file not selected."
    if filenamev is not None and not filenamev:
        return False, "Error: Video file not selected."
    return True, ""

def run_auto_sync_threaded(filenamev: str, filename: str, window: sg.Window) -> Dict[str, Any]:
    """Run auto sync in a separate thread and return results.
    
    Args:
        filenamev (str): Path to video file for audio extraction
        filename (str): Path to subtitle file for text matching
        window (sg.Window): GUI window object to keep responsive during processing
    
    Returns:
        Dict[str, Any]: Dictionary containing sync results with keys:
                       - 'success' (bool): True if sync completed successfully
                       - 'btime1', 'btime2' (str): First sync point timestamps if successful
                       - 'etime1', 'etime2' (str): Second sync point timestamps if successful  
                       - 'error' (str): Error message if sync failed
    """
    results: Dict[str, Any] = {}
    
    def auto_sync() -> None:
        try:
            result1 = auto_sub_sync(1/4, filenamev, filename)
            result2 = auto_sub_sync(3/4, filenamev, filename)
            
            if result1 and result1[0] and result1[1] and result2 and result2[0] and result2[1]:
                results['btime1'], results['btime2'] = result1
                results['etime1'], results['etime2'] = result2
                results['success'] = True
            else:
                results['success'] = False
                results['error'] = "Auto sync failed to find matching subtitles"
        except Exception as e:
            results['success'] = False
            results['error'] = str(e)

    auto_sync_thread = threading.Thread(target=auto_sync, daemon=True)
    auto_sync_thread.start()
    
    # Keep the GUI responsive while waiting for the thread to finish
    while auto_sync_thread.is_alive():
        window.read(timeout=100)
    
    return results

#endregion

#region Subtitle Functions from srt/srt_tools/srt-linear-timeshift

def timedelta_to_milliseconds(delta: datetime.timedelta) -> float:
    """Convert a timedelta object to milliseconds.
    
    Args:
        delta (datetime.timedelta): Time duration object to convert
        
    Returns:
        float: Total duration in milliseconds as a floating point number
    """
    return delta.days * 86400000 + delta.seconds * 1000 + delta.microseconds / 1000


def parse_args() -> Any:
    """Parse command line arguments for SRT linear time shift.
    
    Returns:
        Any: Parsed arguments object containing timing parameters and file paths
             for subtitle synchronization operations
    """
    def srt_timestamp_to_milliseconds(parser, arg):
        try:
            delta = srt.srt_timestamp_to_timedelta(arg)
        except ValueError:
            parser.error("not a valid SRT timestamp: %s" % arg)
        else:
            return timedelta_to_milliseconds(delta)

    examples = {
        "Stretch out a subtitle so that second 1 is 2, 2 is 4, etc": "srt linear-timeshift --f1 00:00:01,000 --t1 00:00:01,000 --f2 00:00:02,000 --t2 00:00:03,000"
    }

    parser = srt_tools.utils.basic_parser(description=__doc__, examples=examples)
    parser.add_argument(
        "--from-start",
        "--f1",
        type=lambda arg: srt_timestamp_to_milliseconds(parser, arg),
        required=True,
        help="the first desynchronised timestamp",
    )
    parser.add_argument(
        "--to-start",
        "--t1",
        type=lambda arg: srt_timestamp_to_milliseconds(parser, arg),
        required=True,
        help="the first synchronised timestamp",
    )
    parser.add_argument(
        "--from-end",
        "--f2",
        type=lambda arg: srt_timestamp_to_milliseconds(parser, arg),
        required=True,
        help="the second desynchronised timestamp",
    )
    parser.add_argument(
        "--to-end",
        "--t2",
        type=lambda arg: srt_timestamp_to_milliseconds(parser, arg),
        required=True,
        help="the second synchronised timestamp",
    )
    return parser.parse_args()


def calc_correction(to_start: float, to_end: float, from_start: float, from_end: float) -> Tuple[float, float]:
    """Calculate linear time correction coefficients.
    
    Args:
        to_start (float): Target start time in milliseconds (corrected time)
        to_end (float): Target end time in milliseconds (corrected time) 
        from_start (float): Source start time in milliseconds (original subtitle time)
        from_end (float): Source end time in milliseconds (original subtitle time)
    
    Returns:
        Tuple[float, float]: (angular_coefficient, linear_coefficient)
                            - angular_coefficient: Scaling factor for time transformation
                            - linear_coefficient: Offset factor for time transformation
    """
    angular = (to_end - to_start) / (from_end - from_start)
    linear = to_end - angular * from_end
    return angular, linear


def correct_time(current_msecs: float, angular: float, linear: float) -> int:
    """Apply linear time correction to a timestamp.
    
    Args:
        current_msecs (float): Original timestamp in milliseconds
        angular (float): Angular coefficient from calc_correction
        linear (float): Linear coefficient from calc_correction
    
    Returns:
        int: Corrected timestamp in milliseconds, rounded to nearest integer
    """
    return round(current_msecs * angular + linear)


def correct_timedelta(bad_delta: datetime.timedelta, angular: float, linear: float) -> datetime.timedelta:
    """Apply linear time correction to a timedelta object.
    
    Args:
        bad_delta (datetime.timedelta): Original time duration to correct
        angular (float): Angular coefficient from calc_correction
        linear (float): Linear coefficient from calc_correction
    
    Returns:
        datetime.timedelta: Corrected time duration object
    """
    bad_msecs = timedelta_to_milliseconds(bad_delta)
    good_msecs = correct_time(bad_msecs, angular, linear)
    good_delta = datetime.timedelta(milliseconds=good_msecs)
    return good_delta


def linear_correct_subs(subtitles: Any, angular: float, linear: float) -> Any:
    """Apply linear time correction to all subtitles in a collection.
    
    Args:
        subtitles (Any): Collection of subtitle objects (typically from srt.parse())
        angular (float): Angular coefficient from calc_correction
        linear (float): Linear coefficient from calc_correction
    
    Returns:
        Any: Generator yielding corrected subtitle objects with updated start/end times
    """
    for subtitle in subtitles:
        subtitle.start = correct_timedelta(subtitle.start, angular, linear)
        subtitle.end = correct_timedelta(subtitle.end, angular, linear)
        yield subtitle

#endregion

# Open a speech recognizer
rec = sr.Recognizer()

def process_audio_clip(clip: mp.VideoFileClip, time: float, time_clip: float) -> Optional[sr.AudioData]:
    """Extract and process audio clip for speech recognition.
    
    Args:
        clip (mp.VideoFileClip): MoviePy video clip object containing audio
        time (float): Start time in seconds for audio extraction
        time_clip (float): Duration in seconds of audio to extract
    
    Returns:
        Optional[sr.AudioData]: Audio data ready for speech recognition, 
                               or None if extraction fails
    """
    audioClip = clip.audio.subclipped(time, time + time_clip)
    audioClip.write_audiofile(r"audioCut.wav")
    audio = sr.AudioFile("audioCut.wav")
    
    with audio as source:
        return rec.record(source)

def get_speech_recognition_result(recAudio: sr.AudioData, language: str) -> Tuple[float, Optional[str]]:
    """Get speech recognition result with confidence and text.
    
    Args:
        recAudio (sr.AudioData): Audio data from speech_recognition library
        language (str): Language code for recognition (e.g., 'en-US', 'fr-FR')
    
    Returns:
        Tuple[float, Optional[str]]: (confidence_score, recognized_text)
                                   - confidence_score: 0.0-1.0 confidence level, 0 if failed
                                   - recognized_text: Transcribed text or None if recognition failed
    """
    try:
        result = rec.recognize_google(recAudio, language=language, show_all=True)
        print(result)
        
        if not result or 'alternative' not in result or not result['alternative']:
            return 0, None
            
        confidence = result['alternative'][0].get('confidence', 0)
        text = result['alternative'][0].get('transcript', '')
        
        # Ensure confidence is never None
        if confidence is None:
            confidence = 0
            
        return confidence, text
    except (sr.UnknownValueError, sr.RequestError) as e:
        print(f"Speech recognition error: {e}")
        return 0, None

def find_subtitle_match(text: str, subList: List[srt.Subtitle], subLowerAlpha: str, 
                       regex: re.Pattern, use_substring_match: bool, min_words: int) -> Tuple[Optional[srt.Subtitle], float, float]:
    """Find matching subtitle line for recognized text.
    
    Args:
        text (str): Processed text from speech recognition (lowercase, alphanumeric only)
        subList (List[srt.Subtitle]): List of parsed subtitle objects from SRT file
        subLowerAlpha (str): Processed subtitle text (lowercase, alphanumeric, no spaces)
        regex (re.Pattern): Compiled regex pattern for text cleaning
        use_substring_match (bool): If True, use fuzzy substring matching; if False, exact matching
        min_words (int): Minimum number of words required for a valid match
    
    Returns:
        Tuple[Optional[srt.Subtitle], float, float]: (matched_subtitle, index_fraction1, index_fraction2)
                                                   - matched_subtitle: Subtitle object that matched, or None
                                                   - index_fraction1: Position fraction within subtitle text (0.0-1.0)
                                                   - index_fraction2: Position fraction within recognized text (0.0-1.0)
    """
    if not text or not text.strip():
        return None, 0, 0
        
    # Go to the next iteration if there are multiple matches in the subtitle file or if there are none
    matchCount = subLowerAlpha.count(text.replace(' ', ''))
    if matchCount > 1:
        return None, 0, 0
    
    # Without substring matches, we can simply skip if the string is not in the subtitle file.
    if not use_substring_match and matchCount == 0:
        return None, 0, 0
    
    # Only check for a match if it meets the minimum amount of words
    if len(text.split()) < min_words:
        return None, 0, 0
    
    # Check against each subtitle line
    for line in subList:
        try:
            # Make sublines lowercase and alphabetic
            subText = regex.sub('', line.content.lower())
            
            if not subText:  # Skip empty subtitle lines
                continue
            
            if not use_substring_match:
                if text in subText:
                    print("Sub time: " + str(line.start))
                    indFrac = (subText.index(text)) / len(subText)
                    return line, indFrac, 0
            else:
                match = SequenceMatcher(None, text, subText).find_longest_match(0, len(text), 0, len(subText))
                matchStr = text[match.a: match.a + match.size]
                
                # Make sure this substring only occurs once in the subtitles
                if subLowerAlpha.count(matchStr.replace(' ', '')) > 1:
                    continue
                    
                if len(matchStr.split()) >= min_words:
                    print("Sub time: " + str(line.start))
                    indFrac = (subText.index(matchStr)) / len(subText)
                    indFrac2 = (text.index(matchStr)) / len(text)
                    print(f"Match found: {matchStr}")
                    print(f"Recognition: {text}")
                    print(f"Subtitle: {subText}")
                    return line, indFrac, indFrac2
        except (ValueError, ZeroDivisionError, AttributeError) as e:
            print(f"Error processing subtitle line: {e}")
            continue
    
    return None, 0, 0

def auto_sub_sync(start_frac: float, video_file: str, sub_file: str) -> Optional[List[str]]:
    """Automatically synchronize subtitles by matching speech recognition with subtitle text.
    
    Args:
        start_frac (float): Fraction of video duration to start analysis (0.0-1.0, e.g., 0.25 for 25%)
        video_file (str): Path to video file for audio extraction and speech recognition
        sub_file (str): Path to SRT subtitle file for text matching
    
    Returns:
        Optional[List[str]]: List containing [video_timestamp, subtitle_timestamp] in SRT format,
                            or None if synchronization fails or no match is found.
                            
    Example:
        result = auto_sub_sync(0.25, "movie.mp4", "subtitles.srt")
        if result:
            video_time, sub_time = result  # e.g., ["00:05:30,000", "00:05:32,500"]
    """
    # For removing anything non-alphabetic
    regex = re.compile('[^a-zA-Z0-9 ]')

    # Create a moviepy clip of the videofile, will be used to get audio
    clip = mp.VideoFileClip(video_file)

    confidence = 0
    lineFound = False
    lineMatch = None
    indFrac = 0
    indFrac2 = 0
    
    # The first time in the video we're going to recognize speech
    time = round(clip.audio.duration * start_frac, ndigits=2)
    # How many seconds of audio we're going to recognize
    time_clip = float(values["-SR-"])
    # Minimum words needed to classify as a match
    min_words = int(values['-words-'])
    # Speech confidence threshold
    confidence_threshold = int(values["-SC-"])
    # Whether to use substring matching
    use_substring_match = values['-MSUB-']

    try:
        # Read the subtitle file into a string
        with open(sub_file, "r", encoding=values["-encoding-"]) as subfile:
            sub = subfile.read()
    except UnicodeDecodeError:
        window["-TOUT2-"].update("Try a different encoding\n")
        return None, None

    # Make a string of the subtitles with only lowercase alphabetic characters
    # This is used to check if there are multiple matches for the recognized speech
    subLowerAlpha = regex.sub('', sub.lower()).replace(' ', '')
    
    # Use the SRT library to parse the string into sub classes
    subList = list(srt.parse(sub))    # While we haven't found a high-confidence match with subtitles
    max_attempts = 50  # Prevent infinite loops
    attempts = 0
    
    while (confidence * 100 < confidence_threshold or not lineFound) and attempts < max_attempts:
        lineFound = False
        attempts += 1

        # Check if we've gone past the video duration
        if time + time_clip > clip.audio.duration:
            print("Reached end of video without finding match")
            break
        lineFound = False

        # Process audio clip
        recAudio = process_audio_clip(clip, time, time_clip)
        if recAudio is None:
            time += time_clip
            continue
            
        print(str(datetime.timedelta(seconds=(time))))
          # Get speech recognition result
        confidence, text = get_speech_recognition_result(recAudio, values["-language-"])
        if text is None or text.strip() == "":
            time += time_clip
            continue
            
        print(f"Confidence: {confidence}")
        
        # Make all the text lowercase, and remove anything non-alphabetic
        text = regex.sub('', text.lower())
        print(f"Processed text: {text}")

        # Skip if processed text is empty
        if not text.strip():
            time += time_clip
            continue

        # Find subtitle match
        lineMatch, indFrac, indFrac2 = find_subtitle_match(
            text, subList, subLowerAlpha, regex, use_substring_match, min_words
        )
        
        if lineMatch is not None:
            lineFound = True
              # We found a match
        if confidence * 100 >= confidence_threshold and lineFound:
            break
            
        time += time_clip
    
    if lineMatch is None or not lineFound:
        print(f"No suitable match found after {attempts} attempts")
        return None, None
        
    print(f"Final match found: {lineMatch}")
    print(f"Final confidence: {confidence}")
    
    # Get the correct subtime based on the indFrac we found earlier
    try:
        subTime = srt.timedelta_to_srt_timestamp(
            lineMatch.start + 
            ((lineMatch.end - lineMatch.start) * indFrac) - 
            ((lineMatch.end - lineMatch.start) * indFrac2)
        )
        video_time = srt.timedelta_to_srt_timestamp(datetime.timedelta(seconds=(time - time_clip)))
        return [video_time, subTime]
    except Exception as e:
        print(f"Error calculating timestamps: {e}")
        return None, None


#region Window Layout

file_list_column = [
    [
        sg.Text("Subtitle Folder"),
        sg.In(size=(40, 1), enable_events=True, key="-FOLDER-"),
        sg.FolderBrowse(initial_folder="D:/Video/"),
    ],
    [
        sg.Listbox(
            values=[], enable_events=True, size=(70, 10), key="-FILE LIST-"
        )
    ],
    [
        sg.Text("Video Folder (auto only)"),
        sg.In(size=(40, 1), enable_events=True, key="-FOLDER2-"),
        sg.FolderBrowse(initial_folder="D:/Video/"),
    ],
    [
        sg.Listbox(
            values=[], enable_events=True, size=(70, 10), key="-FILE LIST2-"
        )
    ],
]

# Open previously used times for a subtitle sync
times_list = load_saved_times()

# Input part
srt_column = [
    [sg.Text("Choose an SRT from list on left:")],
    [sg.Text(size=(60, 2), key="-TOUT-")],
    [sg.Text(text="First SRT time: "), sg.InputText(key='-F1-', default_text=times_list[0])],
    [sg.Text(text="First Video time: "), sg.InputText(key='-T1-', default_text=times_list[1])],
    [sg.Text(text="Second SRT time: "), sg.InputText(key='-F2-', default_text=times_list[2])],
    [sg.Text(text="Second Video time: "), sg.InputText(key='-T2-', default_text=times_list[3])],
    [sg.Text(text="Encoding: "), sg.DropDown(['utf-8', 'latin-1'], default_value='utf-8', key='-encoding-')],
    [sg.Button("SYNC", key='-SYNC-')],
    [sg.Text(size=(60, 3), key="-TOUT2-")],
    [sg.Text(text="AUTO: ")],
    [sg.Button("Auto Fill Times", key="-AUTO-")],
    [sg.Text(size=(60, 2), key="-TOUT3-")],
    [sg.Text(text="Language: "), sg.DropDown(['en-US', 'en-GB', 'fr-FR'], default_value='en-US', key='-language-')],
    [sg.Text(text="Speech Confidence: "), sg.InputText(key='-SC-', default_text='70')],
    [sg.Text(text="Minimum words to match: "), sg.DropDown(['1', '2', '3', '4', '5'], default_value='3', key='-words-'),sg.Checkbox('Match substrings', key='-MSUB-')],
    [sg.Text(text="Seconds recognized: "), sg.InputText(key='-SR-', default_text='2.5')]
]

# ----- Full layout -----
layout = [
    [
        sg.Column(file_list_column, vertical_alignment='top'),
        sg.VSeperator(),
        sg.Column(srt_column, vertical_alignment='top'),
    ]
]

window = sg.Window("Srt Sync", layout)
#endregion

filename = None
filenamev = None

while True:
    event, values = window.read()
    if event == "Exit" or event == sg.WIN_CLOSED:
        break
    #region UI control    # Folder name was filled in, make a list of files in the folder
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
            filename = os.path.join(
                values["-FOLDER-"], values["-FILE LIST-"][0]
            )
            window["-TOUT-"].update(filename)
        except:
            pass
    elif event == "-FILE LIST2-":  # A file was chosen from the listbox
        try:
            filenamev = os.path.join(
                values["-FOLDER2-"], values["-FILE LIST2-"][0]
            )
            window["-TOUT3-"].update(filenamev)
        except:
            pass
    #endregion    elif event == "-SYNC-":
        valid, error_msg = validate_files(filename)
        if not valid:
            window["-TOUT2-"].update(error_msg)
            continue

        # Setup arguments and save times
        args = setup_sync_args(filename, values, '_c.srt')
        save_times(values["-F1-"], values["-T1-"], values["-F2-"], values["-T2-"])
          # Perform synchronization
        success, message = perform_sync(args)
        window["-TOUT2-"].update(message)
        
    elif event == "-AUTO-":
        valid, error_msg = validate_files(filename, filenamev)
        if not valid:
            if "Video" in error_msg:
                window["-TOUT3-"].update(error_msg)
            else:
                window["-TOUT2-"].update(error_msg)
            continue

        window["-TOUT2-"].update("Working on auto filling times...")
        window.refresh()

        # Perform the auto sync in a separate thread to prevent GUI freezing
        results = run_auto_sync_threaded(filenamev, filename, window)
        
        if not results.get('success', False):
            window["-TOUT2-"].update(f"Auto sync failed: {results.get('error', 'Unknown error')}")
            continue

        # Update the UI with the calculated values
        window['-T1-'].update(results['btime1'])
        window['-F1-'].update(results['btime2'])
        window['-T2-'].update(results['etime1'])
        window['-F2-'].update(results['etime2'])
        window['-TOUT2-'].update("Successfully auto filled times!")

        # Save and sync
        save_times(results['btime2'], results['btime1'], results['etime2'], results['etime1'])
        
        # Setup arguments and perform sync
        args = setup_sync_args(filename, values, '_autosync.srt')
        save_times(values["-F1-"], values["-T1-"], values["-F2-"], values["-T2-"])
        
        success, message = perform_sync(args)
        window["-TOUT2-"].update(message)
            
        

window.close()



