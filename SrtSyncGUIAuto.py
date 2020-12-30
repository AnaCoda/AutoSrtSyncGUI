# img_viewer.py
"""Perform linear time correction on a subtitle."""

from __future__ import division

import PySimpleGUI as sg
import os.path

import srt
import datetime
import srt_tools.utils
import logging

import speech_recognition as sr 
import moviepy.editor as mp
import json
import re

import sys

log = logging.getLogger(__name__)

# Subtitle Functions

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

rec = sr.Recognizer()
def auto_sub_sync(start_frac, video_file, sub_file):
    regex = re.compile('[^a-zA-Z ]')
    clip = mp.VideoFileClip(video_file)

    confidence = 0
    lineFound = False
    time = round(clip.audio.duration * start_frac, ndigits=2)
    time_clip = 2.5

    subfile = open(sub_file, "r", encoding=values["-encoding-"])
    sub = subfile.read()
    subList = list(srt.parse(sub))

    while confidence < 0.7 or not lineFound:
        lineFound = False
        audioClip = clip.audio.subclip(time, time + time_clip)
        audioClip.write_audiofile(r"audioCut.wav")
        audio = sr.AudioFile("audioCut.wav")
        with audio as source:
            recAudio = rec.record(source)
        try:
            result = rec.recognize_google(recAudio, language=values["-language-"], show_all=True)
            print(result)
            print(str(datetime.timedelta(seconds=(time))))
            try:
                confidence = result['alternative'][0]['confidence']
            except KeyError:
                time += 2.5
                continue
            except TypeError:
                time += 2.5
                continue
            print(confidence)
            try:
                text = result['alternative'][0]['transcript']
            except TypeError:
                time += 2.5
                continue
            
            text = regex.sub('', text.lower())
            print(text)
            if len(text.split(' ')) > 2:
                for line in subList:
                    subText = line.content.lower()
                    subText = regex.sub('', subText)
                    if(text in subText):
                        #print("Found match")
                        print("Sub time: " + str(line.start))
                        #print(text)
                        #print(subText)
                        lineFound = True
                        break
        except sr.UnknownValueError:
            print("Google Speech Recognition could not understand audio")
        except sr.RequestError as e:
            print("Could not request results from Google Speech Recognition service; {0}".format(e))
        if confidence >= 0.7 and lineFound == True:
            print(line)
            print(confidence)
            lineMatch = line
        time += time_clip
    print(lineMatch)
    return [srt.timedelta_to_srt_timestamp(datetime.timedelta(seconds=(time - time_clip))), srt.timedelta_to_srt_timestamp(lineMatch.start)]

# First the window layout in 2 columns

file_list_column = [
    [
        sg.Text("Subtitle Folder"),
        sg.In(size=(25, 1), enable_events=True, key="-FOLDER-"),
        sg.FolderBrowse(initial_folder="D:/Video/"),
    ],
    [
        sg.Listbox(
            values=[], enable_events=True, size=(40, 20), key="-FILE LIST-"
        )
    ],
]
file_list_column2 = [
    [
        sg.Text("Video Folder (auto only)"),
        sg.In(size=(25, 1), enable_events=True, key="-FOLDER2-"),
        sg.FolderBrowse(initial_folder="D:/Video/"),
    ],
    [
        sg.Listbox(
            values=[], enable_events=True, size=(40, 20), key="-FILE LIST2-"
        )
    ],
]

if os.path.exists("savedtimes.txt"):
    fr = open("savedtimes.txt", "r")
    times_list = fr.read().split('\n')
    print(times_list)
else:
    times_list = ['00:00:00,000', '00:00:00,000', '00:00:00,000', '00:00:00,000']

# For now will only show the name of the file that was chosen
srt_column = [
    [sg.Text("Choose an SRT from list on left:")],
    [sg.Text(size=(80, 1), key="-TOUT-")],
    [sg.Button("Auto", key="-AUTO-")],
    [sg.Text(size=(80, 1), key="-TAUTO-")],
    [sg.Text(text="First SRT time: "), sg.InputText(key='-F1-', default_text=times_list[0])],
    [sg.Text(text="First Video time: "), sg.InputText(key='-T1-', default_text=times_list[1])],
    [sg.Text(text="Second SRT time: "), sg.InputText(key='-F2-', default_text=times_list[2])],
    [sg.Text(text="Second Video time: "), sg.InputText(key='-T2-', default_text=times_list[3])],
    [sg.Text(text="Encoding: "), sg.DropDown(['utf-8', 'latin-1'], default_value='utf-8', key='-encoding-')],
    [sg.Text(text="Language (auto): "), sg.DropDown(['en-US', 'en-GB', 'fr-FR'], default_value='en-US', key='-language-')],
    [sg.Button("OK", key='-SYNC-')],
    [sg.Text(size=(80, 3), key="-TOUT2-")]
]

# ----- Full layout -----
layout = [
    [
        sg.Column(file_list_column),
        sg.Column(file_list_column2),
        sg.VSeperator(),
        sg.Column(srt_column),
    ]
]

window = sg.Window("Srt Sync", layout)

while True:
    event, values = window.read()
    if event == "Exit" or event == sg.WIN_CLOSED:
        break
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
        except:
            pass
    elif event == "-SYNC-":
        # window["-TOUT2-"].update(values["-F1-"])
        sys.argv = ["SrtSyncGUI.py", "--input", filename, "--f1", values["-F1-"], "--f2", values["-F2-"], "--t1", values["-T1-"],
                    "--t2",  values["-T2-"], "--output", filename.replace('.srt', '_c.srt'), "--encoding", values["-encoding-"]]
        
        print(sys.argv)
        args = parse_args()

        f = open("savedtimes.txt", "w")
        f.write(values["-F1-"] + '\n' + values["-T1-"] + '\n' + values["-F2-"] + '\n' + values["-T2-"])
        f.close()

        logging.basicConfig(level=args.log_level)
        angular, linear = calc_correction(
            args.to_start, args.to_end, args.from_start, args.from_end
        )
        '''angular, linear = calc_correction(
            values["-T1-"], values["-T2-"], values["-F1-"], values["-F2-"]
        )'''
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
    elif event == "-AUTO-":
        window["-TAUTO-"].update("Working...")
        btime1, btime2 = auto_sub_sync(1/4, filenamev, filename)
        window.FindElement('-T1-').Update(btime1)
        window.FindElement('-F1-').Update(btime2)
        values["-T1-"] = btime1
        values["-F1-"] = btime2

        etime1, etime2 = auto_sub_sync(3/4, filenamev, filename)
        window.FindElement('-T2-').Update(etime1)
        window.FindElement('-F2-').Update(etime2)
        values["-T2-"] = etime1
        values["-F2-"] = etime2
        window["-TAUTO-"].update("Done.")

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
        '''angular, linear = calc_correction(
            values["-T1-"], values["-T2-"], values["-F1-"], values["-F2-"]
        )'''
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
        '''time_clip = 2.5
        regex = re.compile('[^a-zA-Z ]')
        clip = mp.VideoFileClip(filenamev)
        rec = sr.Recognizer()

        confidence = 0
        lineFound = False
        time = round(clip.audio.duration/4)

        subfile = open(filename, "r", encoding=values["-encoding-"])
        sub = subfile.read()
        subList = list(srt.parse(sub))

        while confidence < 0.8 or not lineFound:
            audioClip = clip.audio.subclip(time, time + time_clip)
            audioClip.write_audiofile(r"audioCut.wav")
            audio = sr.AudioFile("audioCut.wav")
            with audio as source:
                recAudio = rec.record(source)
            try:
                result = rec.recognize_google(recAudio, language="en-GB", show_all=True)
                try:
                    confidence = result['alternative'][0]['confidence']
                except KeyError:
                    pass
                except TypeError:
                    pass
                #print(confidence)
                try:
                    text = result['alternative'][0]['transcript']
                except TypeError:
                    pass
                text = regex.sub('', text.lower())
                for line in subList:
                    subText = line.content.lower()
                    subText = regex.sub('', subText)
                    if(text in subText):
                        #print("Found match")
                        print("Sub time: " + str(line.start))
                        lineFound = True
                        break
                        
            except sr.UnknownValueError:
                print("Google Speech Recognition could not understand audio")
            except sr.RequestError as e:
                print("Could not request results from Google Speech Recognition service; {0}".format(e))
            time += time_clip
        window.FindElement('-T1-').Update(srt.timedelta_to_srt_timestamp(datetime.timedelta(seconds=(time - time_clip))))
        window.FindElement('-F1-').Update(srt.timedelta_to_srt_timestamp(line.start))'''

        window["-TAUTO-"].update("Done.")
            
        

window.close()



