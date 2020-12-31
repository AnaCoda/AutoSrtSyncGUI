# AutoSrtSyncGUI
A version of my SrtSyncGUI program that will sync SRT subtitles automatically using Google speech recognition.
Takes some time (a few minutes, but can be less), but you don't need to find the subtitle and movie times yourself making it much more convenient
This is heavier than the other version as it uses the MoviePy and SpeechRecognition libraries.

Works pretty reliably for English movies, currently testing it out on French.
I decided to publish this as a separate project from my original one because of many differences.

TODO:
- ~~Add an option to choose how much confidence is needed in the speech recognition (currently 70%)~~
- ~~Add an option to choose the minimum number of words needed to match (currently 3 words)~~
- ~~Add an option to choose how many seconds of speech to recognize with (currently 2.5 seconds)~~
- Add an option to allow near matches
