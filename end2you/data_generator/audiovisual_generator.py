import torch
import numpy as np
import h5py

from pathlib import Path
from moviepy.editor import VideoFileClip

from .generator import Generator
from .file_reader import FileReader
from .face_extractor import FaceExtractor


class AudioVisualGenerator(Generator):
    """Generates the audiovisual data."""

    def __init__(self,
                 labelfile_reader:FileReader, 
                 detector:FaceExtractor = None,
                 fps:int = 30, 
                 sr:int = 16000,
                 *args, **kwargs):
        """ Initialize object class.
        
        Args:
          labelfile_reader (FileReader): Class to read label files.
          detector (FaceExtractor): Instance of face detector (default FaceExtractor()).
          fps (int): The frames per second to use for the visual modality.
          sr (int): The sampling rate to use for the visual modality.
        """
        if not detector:
            detector = FaceExtractor()
        
        super().__init__(*args, **kwargs)
        
        self.detector = detector
        self.labelfile_reader = labelfile_reader
        self.fps = fps
        self.sr = sr
    
    def _get_samples(self, data_file:str, label_file:str):
        """ Read audiovisual data from file.
        
        Args:
          data_file (str): File to read the data from.
          label_file (str): File to read the labels from.
        
        Returns:
          frames (list): Audio and visual frames of each file.
          labels (np.array): Labels for each frame.
          seq_num (int): Number of samples in file.
          num_samples (int): Number of samples per frame.
          attrs_name (str): Label names.
        """
        
        file_data, attrs_name = self.labelfile_reader.read_file(label_file)
        file_data = np.array(file_data).astype(np.float32)
        timestamps = file_data[:,0]
        labels = file_data[:-1,1:]
        
        clip = VideoFileClip(str(data_file))
        clip.audio.set_fps(self.sr)
        clip.audio.set_fps(self.fps)
        
        seq_num = labels.shape[0] - 1
        visual_num_samples = int(np.around(self.fps * (timestamps[1] - timestamps[0]), decimals=6))
        audio_num_samples = int(np.around(self.sr * (timestamps[1] - timestamps[0]), decimals=6))
        
        visual_frames, audio_frames = [], []        
        for i in range(len(timestamps) - 1):
            start_time = timestamps[i]
            end_time = timestamps[i + 1]
            
            visual_frame = np.array(list(clip.subclip(start_time, end_time).iter_frames()))
            visual_frame = visual_frame[:visual_num_samples]
            
            if self.detector:
                try:
                    visual_frame = self.detector.extract_and_resize_face(visual_frame)
                except:
                    visual_frame = np.zeros(
                        (1, self.detector.resize[0], self.detector.resize[0], 3), dtype=np.float32)
            
            visual_frame = visual_frame.transpose(0, 3, 1, 2)
            visual_frames.append(visual_frame.astype(np.float32))
            
            audio_frame = np.array(list(clip.audio.subclip(start_time, end_time).iter_frames()))
            audio_frame = audio_frame.mean(1)[:audio_num_samples]
            
            audio_frames.append(audio_frame.astype(np.float32))
                
        visual_frames = np.array(visual_frames).astype(np.float32)
        audio_frames = np.array(audio_frames).astype(np.float32)
        labels = np.array(labels).astype(np.float32)
        
        num_samples = [audio_num_samples, visual_num_samples]
        data = [audio_frames, visual_frames]
        return data, labels, seq_num, num_samples, attrs_name
    
    def serialize_samples(self, writer:h5py.File, data_file:str, label_file:str):
        """ Write data to `hdf5` file.
        
        Args:
          writer (h5py.File): Open file to write data.
          data_file (str): Data file name.
          label_file (str): Label file name.
        """

        frames, labels, seq_num, num_samples, names = self._get_samples(data_file, label_file)
        audio_frames, visual_frames = frames
        
        audio_num_samples, visual_num_samples = num_samples
        
        # store data
        writer.create_dataset('audio', data=audio_frames)
        writer.create_dataset('visual', data=visual_frames)
        writer.create_dataset('labels', data=labels)
        
        # Save meta-data
        writer.attrs['data_file'] = str(data_file)
        writer.attrs['label_file'] = str(label_file)
        writer.attrs['seq_num'] = seq_num
        writer.attrs['num_samples'] = [audio_num_samples, visual_num_samples]
        writer.attrs['label_names'] = names[1:]
    