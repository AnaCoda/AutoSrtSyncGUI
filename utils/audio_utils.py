from typing import List, Tuple, Optional, Any, Dict
import re
import speech_recognition as sr
import moviepy as mp
from difflib import SequenceMatcher
import srt
import datetime
import threading
import FreeSimpleGUI as sg

def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

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
        return sr.Recognizer().record(source)

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
    rec = sr.Recognizer()
    try:
        result = rec.recognize_google(recAudio, language=language, show_all=True)
        if not result or 'alternative' not in result or not result['alternative']:
            return 0, None
        confidence = result['alternative'][0].get('confidence', 0)
        text = result['alternative'][0].get('transcript', '')
        if confidence is None:
            confidence = 0
        return confidence, text
    except (sr.UnknownValueError, sr.RequestError):
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
    matchCount = subLowerAlpha.count(text.replace(' ', ''))
    if matchCount > 1:
        return None, 0, 0
    if not use_substring_match and matchCount == 0:
        return None, 0, 0
    if len(text.split()) < min_words:
        return None, 0, 0
    for line in subList:
        try:
            subText = regex.sub('', line.content.lower())
            if not subText:
                continue
            if not use_substring_match:
                if text in subText:
                    indFrac = (subText.index(text)) / len(subText)
                    return line, indFrac, 0
            else:
                match = SequenceMatcher(None, text, subText).find_longest_match(0, len(text), 0, len(subText))
                matchStr = text[match.a: match.a + match.size]
                if subLowerAlpha.count(matchStr.replace(' ', '')) > 1:
                    continue
                if len(matchStr.split()) >= min_words:
                    indFrac = (subText.index(matchStr)) / len(subText)
                    indFrac2 = (text.index(matchStr)) / len(text)
                    return line, indFrac, indFrac2
        except (ValueError, ZeroDivisionError, AttributeError):
            continue
    return None, 0, 0

def auto_sub_sync(start_frac: float, video_file: str, sub_file: str, values: dict, window: sg.Window) -> Optional[List[str]]:
    """Automatically synchronize subtitles by matching speech recognition with subtitle text.
    
    Args:
        start_frac (float): Fraction of video duration to start analysis (0.0-1.0, e.g., 0.25 for 25%)
        video_file (str): Path to video file for audio extraction and speech recognition
        sub_file (str): Path to SRT subtitle file for text matching
        values (dict): GUI values dictionary containing settings
        window (sg.Window): GUI window for status updates
    
    Returns:
        Optional[List[str]]: List containing [video_timestamp, subtitle_timestamp] in SRT format,
                            or None if synchronization fails or no match is found.
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
        if window:
            window["-TOUT2-"].update("Try a different encoding\n")
        return None

    # Make a string of the subtitles with only lowercase alphabetic characters
    subLowerAlpha = regex.sub('', sub.lower()).replace(' ', '')
    
    # Use the SRT library to parse the string into sub classes
    subList = list(srt.parse(sub))
    
    # While we haven't found a high-confidence match with subtitles
    max_attempts = 50  # Prevent infinite loops
    attempts = 0
    
    while (confidence * 100 < confidence_threshold or not lineFound) and attempts < max_attempts:
        lineFound = False
        attempts += 1

        # Check if we've gone past the video duration
        if time + time_clip > clip.audio.duration:
            print("Reached end of video without finding match")
            break

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
        return None
        
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
        return None

def run_auto_sync_threaded(filenamev: str, filename: str, window: sg.Window, values: dict) -> Dict[str, Any]:
    """Run auto sync in a separate thread and return results.
    
    Args:
        filenamev (str): Path to video file for audio extraction
        filename (str): Path to subtitle file for text matching
        window (sg.Window): GUI window object to keep responsive during processing
        values (dict): GUI values dictionary containing settings
    
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
            result1 = auto_sub_sync(1/4, filenamev, filename, values, window)
            result2 = auto_sub_sync(3/4, filenamev, filename, values, window)
            
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
