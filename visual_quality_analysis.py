import cv2
import glob
import time
import numpy as np
import subprocess
import os

mod_clip_folder = 'mod_clips' 
ref_clip_folder = 'ref_clips'
'''
View Modes
Frame by Frame: MOD1 -> REF1 -> MOD2 -> REF2 -> MOD3 -> REF3 etc...
Section by Section: MOD1 -> MOD2 -> MOD3 -> REF1 -> REF2 -> REF3 etc...
Interweave: MOD1 -> MOD2 -> MOD3 -> REF3 -> REF4 -> REF5 etc...

'''
VIEW_MODE = 2 #0:Frame by Frame | 1: Section by Section | 2:Interweave

'''Delay between frame switch for Frame by Frame'''
MILLISECONDS_PER_FRAME = 500

'''Delay between frame switch for Section by Section and Interweave'''
SECTION_SPEED = 200

'''Resolution settings for Viewing'''
FRAME_WIDTH = 1920
FRAME_HEIGHT = 1080

'''Stream extensions to target in the mod/ref folder'''
STREAM_PREFIX = 'bin'

'''Number of frame segments to include in each mini clip section'''
FRAMES_IN_SECTION = 5


def main():
    width = FRAME_WIDTH
    height = FRAME_HEIGHT

    mod_clips = glob.glob('%s/*.%s' % (mod_clip_folder,STREAM_PREFIX))
    ref_clips = glob.glob('%s/*.%s' % (ref_clip_folder,STREAM_PREFIX))

    t0 = time.time()

    for ref_clip_name,mod_clip_name in zip(ref_clips,mod_clips):
        print('mod_clip_name',mod_clip_name)
        print('ref_clip_name',ref_clip_name)
        
        frame_by_frame = list()
        section_by_section = list()
        interweave_frames = list()
        
        mod_frames = read_stream(mod_clip_name,width,height) # [82:84] # [82:90] # [82:83]
        ref_frames = read_stream(ref_clip_name,width,height) # [82:84] # [82:90] # [82:83]

        frame_number = 0
        
        for mod, ref in zip(mod_frames,ref_frames):
            cv2.putText(mod, 'MOD', (30,30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3, cv2.LINE_AA)
            cv2.putText(ref, 'REF', (30,30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3, cv2.LINE_AA)

            cv2.putText(mod, str(frame_number), (30,80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3, cv2.LINE_AA)
            cv2.putText(ref, str(frame_number), (30,80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3, cv2.LINE_AA)

            frame_by_frame.append(mod)
            frame_by_frame.append(ref)
            frame_number += 1
            
        start = 0
        even_odd = 0
        for end in range(0,len(mod_frames),FRAMES_IN_SECTION):
            mod = mod_frames[start:end]
            ref = ref_frames[start:end]
            if even_odd % 2 == 0:
                interweave_frames.extend(mod)
            else:
                interweave_frames.extend(ref)

            section_by_section.extend(mod+ref)
            
            start = end
            even_odd += 1

        if VIEW_MODE == 1:
            display_frames(section_by_section)
        elif VIEW_MODE == 2:
            display_frames(interweave_frames)
            
        else:
            display_frames(frame_by_frame)


def display_frames(mod_ref_frames):
    index = 0
    outter_break = False
    while index < len(mod_ref_frames):
        show_frame = mod_ref_frames[index]
        cv2.imshow('image', show_frame)
        if VIEW_MODE:
            key = cv2.waitKey(SECTION_SPEED)
        else:
            key = cv2.waitKey(MILLISECONDS_PER_FRAME)

        if key == 32:
            cv2.waitKey()
        if key == 113:
            break
        if key == 97:
            if index>0:
                index -= 1
        elif key == 100:
            if index<len(mod_ref_frames):
                index += 5               
        else:
            index+=1
        
def read_stream(input_stream,width,height):
    frames = list()
    count = 0

    ffmpeg_command = r'C:/ffmpeg/bin/ffmpeg.exe -threads 0  -i {input_stream} -s:v {width}x{height} -f image2pipe -vcodec rawvideo -pix_fmt bgr24 -an -'.format(**vars())

    '''Open sub-process that gets in_stream as input and uses stdout as an output PIPE.'''
    p1 = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE)

    while True:
        '''read width*height*3 bytes from stdout (1 frame)'''
        raw_frame = p1.stdout.read(width*height*3)

        '''Break the loop in case of an error (too few bytes were read).'''
        if len(raw_frame) != (width*height*3):
            print('Error reading frame!!!')  
            break

        '''Rebuild the frame data into an image'''
        frame = np.frombuffer(raw_frame, np.uint8)
        frame = frame.reshape((height, width, 3))
        frames.append(frame)

    return frames


if __name__ == '__main__':
    main()
