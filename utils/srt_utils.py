# srt_utils.py
# Utility functions for SRT subtitle operations

from typing import Any, Tuple, Dict
import datetime
import srt
import srt_tools.utils
import logging
import sys

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

    parser = srt_tools.utils.basic_parser(description="Perform linear time correction on a subtitle.", examples=examples)
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
