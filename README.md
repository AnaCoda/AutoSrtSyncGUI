# AutoSrtSyncGUI

A Python program with a GUI to automatically sync subtitles with the wrong framerate by comparing speech in the movie to text in the subtitles. If your SRT subtitles keep getting out of sync with audio/video (a single shift doesn't work for long), this is the tool for you.

This will sync SRT subtitles automatically using Google speech recognition.
Takes some time (really depends on the video, can be from seconds to minutes), but you don't need to find the subtitle and movie times yourself making it much more convenient.

Works pretty reliably for English movies, and I've tested it on some French movies as well.
NOTE: only works for subtitles that are in the same language as the video right now

This program will not work if the video has a commercial that subtitles don't. It uses two points to do a linear sync for a difference in framerate and/or start time between the subtitles and video (the most common problem I come across)

## Features

### Single File Sync
- Manual time input for precise control
- Auto-fill times using speech recognition
- Real-time progress tracking with timestamp display
- Multiple encoding support (UTF-8, Latin-1)

### Batch Sync (NEW!)
Perfect for syncing entire TV seasons or multiple episodes at once:
- **Simple Process**: Select folders → Multi-select files with Ctrl+Click → Switch to Batch Sync tab → Start processing
- **Automatic Pairing**: Files are matched alphabetically (e.g., `episode01.srt` ↔ `episode01.mkv`)
- **Progress Tracking**: See both overall batch progress and individual file analysis progress
- **Robust Processing**: Continues even if some files fail, with detailed error reporting
- **Consistent Naming Required**: Files should follow patterns like `S01E01.srt`/`S01E01.mkv` for best results

## Main Libraries Used
- srt/srt_tools for parsing .srt subtitle files
- speech_recognition for interface with Google speech recognition API
- moviepy for cutting short audio clips from a video
- FreeSimpleGUI for the user interface

## How to Use

### Single File Sync:
1. Pip install dependencies (srt, FreeSimpleGUI, speech_recognition, srt_tools, moviepy)
2. Run program
3. Select SRT file and the video you want to sync it to
4. Choose settings (encoding, auto sync options)
5. Press "Auto Fill Times" and wait until complete

### Batch Sync:
1. Use folder browsers to select your subtitle and video folders
2. Use **Ctrl+Click** or **Shift+Click** to select multiple files from each list
3. Switch to the "Batch Sync" tab to preview file pairings
4. Click "Start Batch Sync" and monitor progress

### Settings & Tips:
- **Encoding**: Try different encodings if you get errors (UTF-8 vs Latin-1)
- **Language**: Choose the correct language for speech recognition
- **Confidence**: Higher values (70%+) reduce false matches
- **File Naming**: Use consistent patterns like `episode01.srt`/`episode01.mkv` for batch processing
- **Output Files**: Single sync creates `_autosync.srt`, batch creates `_batch_autosync.srt`

If you get an encoding error, try another encoding from the dropdown and press OK.
You can also edit the generated times manually and press OK to resync.

TODO:
- ~~Add an option to choose how much confidence is needed in the speech recognition (currently 70%)~~
- ~~Add an option to choose the minimum number of words needed to match (currently 3 words)~~
- ~~Add an option to choose how many seconds of speech to recognize with (currently 2.5 seconds)~~
- Add an option to allow near matches
- Add GIFs of video with unsynced vs synced subs to README

Images:

**Initial GUI**<br>
<img src="ExamplePics/OpeningScreen.jpg" width="700"><br>
**Files Selected**<br>
<img src="ExamplePics/SelectedFiles.jpg" width="700"><br>
**Sync Completed**<br>
<img src="ExamplePics/CompletedSync.jpg" width="700"><br>
**Files Created**<br>
<img src="ExamplePics/EndResult.jpg" width="700">