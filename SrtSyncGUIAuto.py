# img_viewer.py
"""Perform linear time correction on a subtitle."""

from __future__ import division

import FreeSimpleGUI as sg
import os.path

import srt
import datetime
import srt_tools.utils
import logging

import speech_recognition as sr 
import moviepy as mp
import re

# For similar subtitles, will be implemented soon
from difflib import SequenceMatcher
def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

import sys

log = logging.getLogger(__name__)

#region Subtitle Functions from srt/srt_tools/srt-linear-timeshift

def timedelta_to_milliseconds(delta):
    return delta.days * 86400000 + delta.seconds * 1000 + delta.microseconds / 1000


def parse_args():
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


def calc_correction(to_start, to_end, from_start, from_end):
    angular = (to_end - to_start) / (from_end - from_start)
    linear = to_end - angular * from_end
    return angular, linear


def correct_time(current_msecs, angular, linear):
    return round(current_msecs * angular + linear)


def correct_timedelta(bad_delta, angular, linear):
    bad_msecs = timedelta_to_milliseconds(bad_delta)
    good_msecs = correct_time(bad_msecs, angular, linear)
    good_delta = datetime.timedelta(milliseconds=good_msecs)
    return good_delta


def linear_correct_subs(subtitles, angular, linear):
    for subtitle in subtitles:
        subtitle.start = correct_timedelta(subtitle.start, angular, linear)
        subtitle.end = correct_timedelta(subtitle.end, angular, linear)
        yield subtitle

#endregion

# Open a speech recognizer
rec = sr.Recognizer()
def auto_sub_sync(start_frac, video_file, sub_file):
    # For removing anything non-alphabetic
    regex = re.compile('[^a-zA-Z0-9 ]')

    # Create a moviepy clip of the videofile, will be used to get audio
    clip = mp.VideoFileClip(video_file)

    confidence = 0
    lineFound = False
    # The first time in the video we're going to recognize speech
    time = round(clip.audio.duration * start_frac, ndigits=2)
    # How many seconds of audio we're going to recognize
    time_clip = float(values["-SR-"])
    # Minimum words needed to classify as a match
    min_words = int(values['-words-'])

    try:
        # Read the subtitle file into a string
        subfile = open(sub_file, "r", encoding=values["-encoding-"])
        sub = subfile.read()
    except UnicodeDecodeError:
        window["-TOUT2-"].update("Try a different encoding\n")
        pass

    # Make a string of the subtitles with only lowercase alphabetic characters
    # This is used to check if there are multiple matches for the recognized speech
    subLowerAlpha = regex.sub('', sub.lower())
    subLowerAlpha = subLowerAlpha.replace(' ', '')
    '''f = open('test.txt', 'w')
    f.write(subLowerAlpha)'''

    # Use the SRT library to parse the string into sub classes
    subList = list(srt.parse(sub))

    # While we haven't found a high-confidence match with subtitles
    while confidence*100 < int(values["-SC-"]) or not lineFound:
        lineFound = False

        # Make a time_clip long audio clip from the video file
        audioClip = clip.audio.subclipped(time, time + time_clip)
        # Write it to a file and give it to the speech recognizer
        audioClip.write_audiofile(r"audioCut.wav")
        audio = sr.AudioFile("audioCut.wav")

        with audio as source:
            # Read the audio
            recAudio = rec.record(source)
        try:
            # Try to recognize speech
            result = rec.recognize_google(recAudio, language=values["-language-"], show_all=True)
            print(result)
            print(str(datetime.timedelta(seconds=(time))))
            try:
                # Get the confidence that the recognition is correct
                confidence = result['alternative'][0]['confidence']
            except KeyError:
                time += time_clip
                continue
            except TypeError:
                time += time_clip
                continue
            print(confidence)
            try:
                # Get the text for the speech recognized
                text = result['alternative'][0]['transcript']
            except TypeError:
                time += time_clip
                continue
            
            # Make all the text lowercase, and remove anything non-alphabetic
            text = regex.sub('', text.lower())
            print(text)

            # Go to the next iteration if there are multiple matches in the subtitle file or if there are none
            matchCount = subLowerAlpha.count(text.replace(' ', ''))
            if matchCount > 1:
                time += time_clip
                continue
            # Without substring matches, we can simply skip if the string is not in the subtitle file.
            if (values['-MSUB-'] == False) and matchCount == 0:
                time += time_clip
                continue
            # Only check for a match if it meets the minimum amount of words
            if len(text.split()) >= min_words:
                # Check against each subtitle line
                for line in subList:
                    # Make sublines lowercase and alphabetic
                    subText = line.content.lower()
                    subText = regex.sub('', subText)
                    # If we found a match in a subtitle line
                    if values['-MSUB-'] == False:
                        if(text in subText):
                            print("Sub time: " + str(line.start))
                            # Check the fraction of where the recognized text starts in the subtitle line
                            # This is done to correct for time if the recognized speech is not at the beginning of the subtitle
                            indFrac = (subText.index(text))/len(subText)
                            indFrac2 = 0
                            lineFound = True
                            break
                    else:
                        match = SequenceMatcher(None, text, subText).find_longest_match(0, len(text), 0, len(subText))
                        matchStr = text[match.a: match.a + match.size]
                        # Make sure this substring only occurs once in the subtitles
                        if subLowerAlpha.count(matchStr.replace(' ', '')) > 1:
                            continue
                        if len(matchStr.split()) >= min_words:
                            print("Sub time: " + str(line.start))
                            # Check the fraction of where the recognized text starts in the subtitle line
                            # This is done to correct for time if the recognized speech is not at the beginning of the subtitle
                            indFrac = (subText.index(matchStr))/len(subText)
                            indFrac2 = (text.index(matchStr))/len(text)
                            lineFound = True
                            print(matchStr)
                            print(text)
                            print(subText)
                            break

        except sr.UnknownValueError:
            print("Google Speech Recognition could not understand audio")
        except sr.RequestError as e:
            print("Could not request results from Google Speech Recognition service; {0}".format(e))
        # We found a match
        if confidence*100 >= int(values["-SC-"]) and lineFound == True:
            print(line)
            print(confidence)
            lineMatch = line
        time += time_clip
    print(lineMatch)
    # Get the correct subtime based on the indFrac we found earlier
    subTime = srt.timedelta_to_srt_timestamp(lineMatch.start + ((lineMatch.end - lineMatch.start) * indFrac) - ((lineMatch.end - lineMatch.start) * indFrac2))
    return [srt.timedelta_to_srt_timestamp(datetime.timedelta(seconds=(time - time_clip))), subTime]


#region Window Layout

file_list_column = [
    [
        sg.Text("Subtitle Folder"),
        sg.In(size=(25, 1), enable_events=True, key="-FOLDER-"),
        sg.FolderBrowse(initial_folder="D:/Video/"),
    ],
    [
        sg.Listbox(
            values=[], enable_events=True, size=(40, 10), key="-FILE LIST-"
        )
    ],
    [
        sg.Text("Video Folder (auto only)"),
        sg.In(size=(25, 1), enable_events=True, key="-FOLDER2-"),
        sg.FolderBrowse(initial_folder="D:/Video/"),
    ],
    [
        sg.Listbox(
            values=[], enable_events=True, size=(40, 10), key="-FILE LIST2-"
        )
    ],
]

# Open previously used times for a subtitle sync
if os.path.exists("savedtimes.txt"):
    fr = open("savedtimes.txt", "r")
    times_list = fr.read().split('\n')
    print(times_list)
else:
    times_list = ['00:00:00,000', '00:00:00,000', '00:00:00,000', '00:00:00,000']

# Input part
srt_column = [
    [sg.Text("Choose an SRT from list on left:")],
    [sg.Text(size=(60, 2), key="-TOUT-")],
    [sg.Text(size=(60, 1), key="-TAUTO-")],
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
    #region UI control
    # Folder name was filled in, make a list of files in the folder
    if event == "-FOLDER-":
        folder = values["-FOLDER-"]
        try:
            # Get list of files in folder
            file_list = os.listdir(folder)
        except:
            file_list = []

        fnames = [
            f
            for f in file_list
            if os.path.isfile(os.path.join(folder, f))
            and f.lower().endswith((".srt"))
        ]
        window["-FILE LIST-"].update(fnames)
    if event == "-FOLDER2-":
        folder = values["-FOLDER2-"]
        try:
            # Get list of files in folder
            file_list = os.listdir(folder)
        except:
            file_list = []

        fnames = [
            f
            for f in file_list
            if os.path.isfile(os.path.join(folder, f))
        ]
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
    #endregion
    elif event == "-SYNC-":
        if not filename:
            window["-TOUT2-"].update("Error: Subtitle file not selected.")
            continue

        # Simulating arguments to use functions from the SRT lineartimeshift library
        sys.argv = ["SrtSyncGUI.py", "--input", filename, "--f1", values["-F1-"], "--f2", values["-F2-"], "--t1", values["-T1-"],
                    "--t2",  values["-T2-"], "--output", filename.replace('.srt', '_c.srt'), "--encoding", values["-encoding-"]]
        print(sys.argv)
        args = parse_args()

        # Save times entered by the user, very useful if the program crashes
        f = open("savedtimes.txt", "w")
        f.write(values["-F1-"] + '\n' + values["-T1-"] + '\n' + values["-F2-"] + '\n' + values["-T2-"])
        f.close()

        # Calculate the correction variables
        logging.basicConfig(level=args.log_level)
        angular, linear = calc_correction(
            args.to_start, args.to_end, args.from_start, args.from_end
        )
        
        try:
            srt_tools.utils.set_basic_args(args)
        except UnicodeDecodeError:
            window["-TOUT2-"].update("Try a different encoding\n")
        try:
            corrected_subs = linear_correct_subs(args.input, angular, linear)
            output = srt_tools.utils.compose_suggest_on_fail(corrected_subs, strict=args.strict)
            try:
                args.output.write(output)
                args.output.close()
            except (UnicodeEncodeError, TypeError):  # Python 2 fallback
                args.output.write(output.encode(args.encoding))
            window["-TOUT2-"].update("Success!")
        except Exception as e:
            window["-TOUT2-"].update("Try a different encoding\n" + str(e))
    elif event == "-AUTO-":
        if not filenamev:
            window["-TOUT3-"].update("Error: Video file not selected.")
            continue
        if not filename:
            window["-TOUT2-"].update("Error: Subtitle file not selected.")
            continue

        window["-TAUTO-"].update("Working...")
        # Call the auto_sub_sync function to get the auto times for 1/4 into the video file
        btime1, btime2 = auto_sub_sync(1/4, filenamev, filename)

        # Update the UI with the correct values
        window['-T1-'].update(btime1)
        window['-F1-'].update(btime2)

        # Do the same but 3/4 into the video file
        etime1, etime2 = auto_sub_sync(3/4, filenamev, filename)
        window['-T2-'].update(etime1)
        window['-F2-'].update(etime2)

        window["-TAUTO-"].update("Done.")

        # Set parameters so we can sync (just like in the SYNC event)
        sys.argv = ["SrtSyncGUI.py", "--input", filename, "--f1", values["-F1-"], "--f2", values["-F2-"], "--t1", values["-T1-"],
                    "--t2",  values["-T2-"], "--output", filename.replace('.srt', '_autosync.srt'), "--encoding", values["-encoding-"]]
        
        print(sys.argv)
        args = parse_args()

        f = open("savedtimes.txt", "w")
        f.write(values["-F1-"] + '\n' + values["-T1-"] + '\n' + values["-F2-"] + '\n' + values["-T2-"])
        f.close()

        logging.basicConfig(level=args.log_level)

        angular, linear = calc_correction(
            args.to_start, args.to_end, args.from_start, args.from_end
        )

        srt_tools.utils.set_basic_args(args)
        try:
            corrected_subs = linear_correct_subs(args.input, angular, linear)
            output = srt_tools.utils.compose_suggest_on_fail(corrected_subs, strict=args.strict)
            try:
                args.output.write(output)
                args.output.close()
            except (UnicodeEncodeError, TypeError):  # Python 2 fallback
                args.output.write(output.encode(args.encoding))
            window["-TOUT2-"].update("Success!")
        except Exception as e:
            window["-TOUT2-"].update("Try a different encoding\n" + str(e))
        
        window["-TAUTO-"].update("Done.")
            
        

window.close()



