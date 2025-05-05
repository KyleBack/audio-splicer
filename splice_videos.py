from flask import send_file, make_response
from werkzeug.exceptions import BadRequest
from werkzeug.utils import secure_filename
from pydub import AudioSegment
from functools import partial
from queue import LifoQueue
from typing import List, Final
import shutil
import yt_dlp
import os


class VideoMetadata:
    def __init__(self, video_id: str, start_time: float, end_time: float):
        self.video_id = video_id
        self.start_time = start_time
        self.end_time = end_time

class SpliceVideosRequest:
    def __init__(self, splice_offset: int, video_details_list: List[VideoMetadata]):
        self.splice_offset = splice_offset
        self.video_details_list = video_details_list

# Constants
TEMP_FILE_DIR_NAME: Final[str] = 'temp'
COMBINED_AUDIO_FILE_NAME: Final[str] = 'combined_audio.m4a'

def validate_request(request_json):
    # Validate splice_offset exists with correct type
    if (splice_offset := request_json.get('splice_offset')) is None:
        raise BadRequest('Request body did not contain \'splice_offset\' field.')
    if type(splice_offset) is not int:
        raise BadRequest('The \'splice_offset\' must be an integer.')

    # Validate video_details_list exists with correct type
    if (video_details_list := request_json.get('video_details_list')) is None:
        raise BadRequest('Request body did not contain \'video_details_list\' field.')
    if type(video_details_list) is not list:
        raise BadRequest('The \'video_details_list\' must be a list.')

    try:
        # Convert request_json to SpliceVideosRequest
        splice_videos_request = SpliceVideosRequest(0, [])
        splice_videos_request.splice_offset = splice_offset
        splice_videos_request.video_details_list = []
        for item in video_details_list:
            splice_videos_request.video_details_list.append(VideoMetadata(**item))
    except TypeError:
        raise BadRequest('Error occurred while converting request body.')

    # Perform numeric validations for splice_offset and video_details_list
    if splice_videos_request.splice_offset < 0:
        raise BadRequest('The \'splice_offset\' field must be greater than or equal to 0.')
    if len(splice_videos_request.video_details_list) < 1:
        raise BadRequest('The \'video_details_list\' field must contain the details for at least one video.')

    # Perform numeric validations for each start_time and end_time
    for video_metadata in splice_videos_request.video_details_list:
        if video_metadata.start_time < 0:
            raise BadRequest('The \'start_time\' field must be greater than or equal to 0.')
        if video_metadata.end_time < 0:
            raise BadRequest('The \'end_time\' field must be greater than or equal to 0.')
        if video_metadata.start_time > video_metadata.end_time:
            raise BadRequest('The \'start_time\' field must be less than the \'end_time\' field.')

    return splice_videos_request

def execute(splice_videos_request: SpliceVideosRequest):
    # Remove combined audio file if it exists
    if os.path.exists(COMBINED_AUDIO_FILE_NAME):
        os.remove(COMBINED_AUDIO_FILE_NAME)

    # Create empty /temp directory where YouTube videos will be downloaded
    if not os.path.exists(TEMP_FILE_DIR_NAME):
        os.mkdir(TEMP_FILE_DIR_NAME)

    for index, video_metadata in enumerate(splice_videos_request.video_details_list):
        error_code, file_name = download_video(
            video_metadata.video_id,
            video_metadata.start_time,
            video_metadata.end_time
        )

        if error_code == 0:
            new_segment = AudioSegment.from_file(file_name)

            if index == 0:
                # Export first audio segment to combined m4a file
                combined_segment = new_segment
            else:
                # Splice audio segments together in combined m4a file
                combined_segment = (combined_segment + AudioSegment.silent(splice_videos_request.splice_offset * 1000)
                                    + new_segment)
        else:
            raise make_response(f"Error occurred while downloading YouTube Video. Error code: {error_code}", 500)

    # Delete contents of /temp directory
    shutil.rmtree(TEMP_FILE_DIR_NAME)

    combined_segment.export(COMBINED_AUDIO_FILE_NAME)

    try:
        # Send combined audio file
        sanitized_filename = secure_filename(COMBINED_AUDIO_FILE_NAME)
        if os.path.isfile(sanitized_filename):
            return send_file(sanitized_filename, as_attachment=True)
        else:
            return make_response(f"File '{sanitized_filename}' not found.", 404)
    except Exception as e:
        return make_response(f"Error occurred while sending audio file: {str(e)}", 500)

def yt_dlp_hook(queue: LifoQueue, download):
    queue.put(download)

def download_video(video_id: str, start: float, end: float):
    queue = LifoQueue()
    yt_dlp_hook_partial = partial(yt_dlp_hook, queue)
    youtube_video_url = f'https://www.youtube.com/watch?v={video_id}'

    # Options to download specified start/end seconds only
    ffmpeg_args = {
        "ffmpeg_i": ["-ss", str(start), "-to", str(end)]
    }

    ydl_opts = {
        'format': 'm4a/bestaudio/best',
        'external_downloader': 'ffmpeg',
        'external_downloader_args': ffmpeg_args,
        'progress_hooks': [yt_dlp_hook_partial],
        'outtmpl': f'{os.getcwd()}/{TEMP_FILE_DIR_NAME}/%(title)s.%(ext)s',
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        error_code = ydl.download(youtube_video_url)

    return error_code, queue.get()['filename']