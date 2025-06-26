# batch_utils.py
# Utility functions for batch processing multiple SRT and video files

from typing import List, Tuple, Dict, Any
import os
import FreeSimpleGUI as sg
from .audio_utils import run_auto_sync_threaded
from .srt_utils import setup_sync_args, perform_sync
from .file_utils import validate_files, save_times


def get_file_pairs(srt_files: List[str], video_files: List[str]) -> List[Tuple[str, str]]:
    """
    Pair SRT and video files alphabetically.
    
    Args:
        srt_files (List[str]): List of SRT file paths
        video_files (List[str]): List of video file paths
    
    Returns:
        List[Tuple[str, str]]: List of (srt_file, video_file) pairs
    """
    # Sort both lists alphabetically by filename (not full path)
    srt_sorted = sorted(srt_files, key=lambda x: os.path.basename(x).lower())
    video_sorted = sorted(video_files, key=lambda x: os.path.basename(x).lower())
    
    # Pair them up
    return list(zip(srt_sorted, video_sorted))


def validate_batch_files(srt_files: List[str], video_files: List[str]) -> Tuple[bool, str]:
    """
    Validate that batch files are ready for processing.
    
    Args:
        srt_files (List[str]): List of SRT file paths
        video_files (List[str]): List of video file paths
    
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    if not srt_files:
        return False, "No SRT files selected"
    
    if not video_files:
        return False, "No video files selected"
    
    if len(srt_files) != len(video_files):
        return False, f"Number of SRT files ({len(srt_files)}) must match number of video files ({len(video_files)})"
    
    # Check if all files exist
    for srt_file in srt_files:
        if not os.path.exists(srt_file):
            return False, f"SRT file not found: {os.path.basename(srt_file)}"
    
    for video_file in video_files:
        if not os.path.exists(video_file):
            return False, f"Video file not found: {os.path.basename(video_file)}"
    
    return True, "Files validated successfully"


def process_batch_sync(file_pairs: List[Tuple[str, str]], values: Dict[str, Any], 
                      window: sg.Window, progress_callback=None) -> Dict[str, Any]:
    """
    Process multiple file pairs for batch synchronization.
    
    Args:
        file_pairs (List[Tuple[str, str]]): List of (srt_file, video_file) pairs
        values (Dict[str, Any]): GUI values containing sync settings
        window (sg.Window): GUI window for updates
        progress_callback: Optional callback for progress updates
    
    Returns:
        Dict[str, Any]: Results summary with success/failure counts and details
    """
    results = {
        'total_files': len(file_pairs),
        'successful': 0,
        'failed': 0,
        'details': [],
        'errors': []
    }
    
    for i, (srt_file, video_file) in enumerate(file_pairs):
        try:
            # Update progress
            if progress_callback:
                progress_callback(i, len(file_pairs), srt_file, video_file)
            
            # Update window status
            if window:
                progress_percent = (i / len(file_pairs)) * 100
                window['-BATCH_PROGRESS-'].update(progress_percent)
                window['-BATCH_STATUS-'].update(
                    f"Processing {i+1}/{len(file_pairs)}: {os.path.basename(srt_file)}"
                )
                window.refresh()
            
            # Validate individual files
            valid, error_msg = validate_files(srt_file, video_file, require_video=True)
            if not valid:
                results['failed'] += 1
                results['errors'].append(f"{os.path.basename(srt_file)}: {error_msg}")
                results['details'].append({
                    'srt_file': srt_file,
                    'video_file': video_file,
                    'status': 'failed',
                    'error': error_msg
                })
                continue
            
            # Perform auto sync
            sync_results = run_auto_sync_threaded(video_file, srt_file, window, values)
            
            if not sync_results.get("success", False):
                results['failed'] += 1
                error_msg = sync_results.get('error', 'Unknown error during auto sync')
                results['errors'].append(f"{os.path.basename(srt_file)}: {error_msg}")
                results['details'].append({
                    'srt_file': srt_file,
                    'video_file': video_file,
                    'status': 'failed',
                    'error': error_msg
                })
                continue
            
            # Save times and perform final sync
            save_times(
                sync_results["btime2"], sync_results["btime1"], 
                sync_results["etime2"], sync_results["etime1"]
            )
            
            # Create output filename
            output_suffix = "_batch_autosync.srt"
            args = setup_sync_args(srt_file, {
                "-F1-": sync_results["btime2"],
                "-T1-": sync_results["btime1"],
                "-F2-": sync_results["etime2"],
                "-T2-": sync_results["etime1"],
                "-encoding-": values.get("-encoding-", "utf-8")
            }, output_suffix)
            
            success, message = perform_sync(args)
            
            if success:
                results['successful'] += 1
                results['details'].append({
                    'srt_file': srt_file,
                    'video_file': video_file,
                    'status': 'success',
                    'output_file': srt_file.replace('.srt', output_suffix),
                    'message': message
                })
            else:
                results['failed'] += 1
                results['errors'].append(f"{os.path.basename(srt_file)}: {message}")
                results['details'].append({
                    'srt_file': srt_file,
                    'video_file': video_file,
                    'status': 'failed',
                    'error': message
                })
                
        except Exception as e:
            results['failed'] += 1
            error_msg = f"Unexpected error: {str(e)}"
            results['errors'].append(f"{os.path.basename(srt_file)}: {error_msg}")
            results['details'].append({
                'srt_file': srt_file,
                'video_file': video_file,
                'status': 'failed',
                'error': error_msg
            })
    
    # Final progress update
    if window:
        window['-BATCH_PROGRESS-'].update(100)
        window['-BATCH_STATUS-'].update(
            f"Completed: {results['successful']} successful, {results['failed']} failed"
        )
    
    return results


def format_batch_results(results: Dict[str, Any]) -> str:
    """
    Format batch processing results for display.
    
    Args:
        results (Dict[str, Any]): Results from process_batch_sync
    
    Returns:
        str: Formatted results string
    """
    summary = f"Batch processing completed!\n"
    summary += f"Total files: {results['total_files']}\n"
    summary += f"Successful: {results['successful']}\n"
    summary += f"Failed: {results['failed']}\n\n"
    
    if results['errors']:
        summary += "Errors:\n"
        for error in results['errors'][:5]:  # Show first 5 errors
            summary += f"• {error}\n"
        if len(results['errors']) > 5:
            summary += f"... and {len(results['errors']) - 5} more errors\n"
    
    return summary
