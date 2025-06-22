from typing import List, Optional, Tuple
import os

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

def validate_files(filename: Optional[str], filenamev: Optional[str] = None, require_video: bool = False) -> Tuple[bool, str]:
    """Validate that required files are selected.
    
    Args:
        filename (Optional[str]): Path to subtitle file, can be None
        filenamev (Optional[str], optional): Path to video file, can be None. 
                                           Only validated if provided or if require_video is True. Defaults to None.
        require_video (bool, optional): If True, video file is required. Defaults to False.
    
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
                         - is_valid: True if all required files are present, False otherwise
                         - error_message: Descriptive error message if validation fails, empty string if valid
    """
    if not filename:
        return False, "Error: Subtitle file not selected."
    if require_video and not filenamev:
            return False, "Error: Video file not selected."
    
    return True, ""
