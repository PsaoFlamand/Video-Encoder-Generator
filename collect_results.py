import os
import sys
import glob
import re
import csv
import multiprocessing
import subprocess
from datetime import date
import time
from collections import OrderedDict


HEADERS = {
    'classical' : '{codec}\t{enc_name}\t{width}x{height}\t{bit_depth}\t{input_sequence}\t{rc_value}\t{frame_count}\t{bitrate}\t{psnr_y}\t{psnr_u}\t{psnr_v}\t{psnr_all}\t{ssim_y}\t{ssim_u}\t{ssim_v}\t{ssim_all}\t{vmaf}\t{cpu_usage}\t{cpu_usage_by_preset}\t{avg_speed}\t{encode_user_time}\t{encode_wall_time}\t{wall_time_by_preset}\t{max_memory}\t{encode_sys_time}\t{avg_latency}\t{max_latency}\t{r2r_found}\t{decode_time}\t{vmaf_neg}\t{file_size}\t{target_bitrate}\t{clip_fps}\t{filesize_derived_from_bitrate}',
    'convex hull' : '{codec}\t{enc_name}\t{width}x{height}\t{bit_depth}\t{input_sequence}\t{rc_value}\t{bitrate}\t{psnr_y}\t{psnr_u}\t{psnr_v}\t{psnr_all}\t{ssim_y}\t{ssim_u}\t{ssim_v}\t{ssim_all}\t{vmaf}\t{vmaf_neg}\t{cpu_usage}\t{avg_speed}\t{avg_latency}\t{frame_count}\t{encode_user_time}\t{wall_time_by_preset}\t{max_memory}\t{encode_sys_time}\t{decode_sys_time}\t{decode_user_time}\t{file_size}\t{max_latency}\t{target_bitrate}\t{filesize_derived_from_bitrate}\t{clip_fps}'
    }

'''System Variables'''
cwd = os.getcwd()
number_of_cores = multiprocessing.cpu_count()

'''Collection Settings'''
tools_folder = '/home/tools'
force_classical_header = 0
use_simple_naming = 1
max_cvh_bitrate = False
min_cvh_qp = 0
multi_pass_collection = 0
debug = 0

#'''Modify the lambda function to reuturn the metric result you are looking for. Regex and split methods are suggested, Any method is supported'''
#'''Modify the files_to_search list to target the file where you expect the metric to be contained'''

'''Encode log patterns'''

ENCODER_PATTERNS = OrderedDict()

ENCODER_PATTERNS['ffmpeg']  = {
        'codec' : {'patterns':[lambda x: x.split('Command being timed: "./')[1].split(' ')[0].strip()],
                    'files_to_search': ['txt']},
        'width': {'patterns': [lambda x: x.split('  Stream #0:0: Video: ')[-1].split('), ')[1].split(' ')[0].split('x')[0].strip().replace('\n','').replace(',','')],
                    'files_to_search': ['log']},
        'height': {'patterns': [lambda x: x.split('  Stream #0:0: Video: ')[-1].split('), ')[1].split(' ')[0].split('x')[1].strip().replace('\n','').replace(',','')],
                    'files_to_search': ['log']},
        'bit_depth': {'patterns': [lambda x: 'n\a'],
                    'files_to_search': ['txt']},
        'bitrate': {'patterns': [lambda x: x.split('bitrate=')[-1].split('kbits/s')[0].strip()],
                    'files_to_search': ['txt']},
        'frame_count': {'patterns': [lambda x: x.split('-vframes ')[1].split(' ')[0].strip(), lambda x: x.split('frame=')[-1].split('fps=')[0].split('  ')[1].strip()],
                    'files_to_search': ['txt']},
        'commit': {'patterns': [lambda x: ''],
                    'files_to_search': ['txt']},
        'avg_speed': {'patterns': [lambda x: 'n/a'],
                    'files_to_search': ['txt']},
        'avg_latency': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']},    
        'max_latency': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']}, 
        'target_bitrate': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']},   
        'clip_fps' : {'patterns': [lambda x: 'n/a'],
                        'files_to_search': ['txt']},   
                        
        }

ENCODER_PATTERNS['VTM']  = {
        'codec' : {'patterns':[lambda x: x.split('VVCSoftware:')[1].split('Encoder')[0].strip().replace('\n','')],
                    'files_to_search': ['txt']},
        'width': {'patterns': [lambda x: x.split('Stream #0:0:')[1].split('Input #1')[0].split(',')[2].split('x')[0].strip().replace('\n','')],
                    'files_to_search': ['log']},
        'height': {'patterns': [lambda x: x.split('Stream #0:0:')[1].split('Input #1')[0].split(',')[2].split('x')[1].strip().replace('\n','')],
                    'files_to_search': ['log']},
        'bit_depth': {'patterns': [lambda x: 'n\a'],
                    'files_to_search': ['txt']},
        'bitrate': {'patterns': [lambda x: x.split('Total Frames |  Bitrate')[1].split('a')[1].split(' ')[0].strip().replace('\n','')],
                    'files_to_search': ['txt']},
        'frame_count': {'patterns': [lambda x: x.split('Total Frames |')[1].split('YUV-PSNR')[1].split('a')[0].strip().replace('\n','')],
                    'files_to_search': ['txt']},
        'commit': {'patterns': [lambda x: x.split('VVCSoftware,:')[1].split('[Linux]')[0].split('Version')[1].replace('\n','')],
                    'files_to_search': ['txt']},
        'avg_speed': {'patterns': [lambda x: 'n/a'],
                    'files_to_search': ['txt']},
        'avg_latency': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']},     
        'max_latency': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']}, 
        'target_bitrate': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']},                            
                    
        }

ENCODER_PATTERNS['SVT-AV1']  = {
        'codec': {'patterns': [lambda x: x.split('SVT [version]:')[1].split(' ')[0]],
                    'files_to_search': ['txt']},
        'width': {'patterns': [lambda x: x.split('width / height')[1].split('\n')[0].split(': ')[1].split('/')[0].strip()],
                    'files_to_search': ['txt']},
        'height': {'patterns': [lambda x: x.split('width / height')[1].split('\n')[0].split(': ')[1].split('/')[1].strip()],
                    'files_to_search': ['txt']},
        'bit_depth': {'patterns': [lambda x: x.split('SVT [config]: bit-depth')[1].split(':')[1].split('/')[0].strip()],
                    'files_to_search': ['txt']},
        'bitrate': {'patterns': [lambda x: x.split('Total Frames')[1].split('kbps')[0].split('\t')[-1].strip()],
                    'files_to_search': ['txt']},
        'frame_count': {'patterns': [lambda x: x.split('Total Frames')[1].strip().split('\n')[1].split('\t')[0].strip()],
                    'files_to_search': ['txt']},
        'commit': {'patterns': [lambda x: x.split('SVT [version]:')[1].split('\n')[0].split('g')[1]],
                    'files_to_search': ['txt']},
        'avg_speed': {'patterns': [lambda x: x.split('Average Speed:\t\t')[1].split('\n')[0].split(' ')[0]],
                    'files_to_search': ['txt']},
        
        'avg_latency': {'patterns': [lambda x: x.split('Average Latency:\t')[1].split('\n')[0].split(' ')[0]],                  
                        'files_to_search': ['txt']},
        'clip_fps' : {'patterns': [lambda x: x.split('Total Frames')[1].split('fps')[0].split('\t')[-1].strip(), lambda x: x.split('SAR 1:1 DAR 16:9],')[1].split('fps')[0].split(',')[-1].strip(), lambda x: x.split('--fps=')[1].split(' ')[0].split('"')[0].strip()],
                        'files_to_search': ['txt','log']},
        'max_latency': {'patterns': [lambda x: x.split('Max Latency:\t\t')[1].split('\n')[0].split(' ')[0]],
                        'files_to_search': ['txt','log']},
        'target_bitrate': {'patterns': [lambda x: x.split('target bitrate (kbps)\t\t\t\t: CBR / ')[1].split('\n')[0]],
                            'files_to_search': ['txt','log']},


    }

ENCODER_PATTERNS['AV1'] = {
        'codec': {'patterns':[lambda x: x.split('Codec: ')[1].split('\n')[0].split(' ')[-3]],
                    'files_to_search': ['txt']},
        'width': {'patterns':[lambda x: x.split('g_w = ')[1].split('\n')[0], lambda x: x.split(' g_w ')[1].split('\n')[0].split('=')[1].strip()],
                    'files_to_search': ['txt']},
        'height': {'patterns':[lambda x: x.split('g_h = ')[1].split('\n')[0], lambda x: x.split(' g_h ')[1].split('\n')[0].split('=')[1].strip()],
                    'files_to_search': ['txt']},
        'bit_depth': {'patterns':[lambda x: x.split('g_bit_depth = ')[1].split('\n')[0], lambda x: x.split(' g_bit_depth ')[1].split('\n')[0].split('=')[1].strip()],
                    'files_to_search': ['txt']},
        'bitrate': {'patterns':[lambda x: x.split('b/s')[-2].split('b/f ')[-1]],
                    'files_to_search': ['txt']},
        'frame_count': {'patterns':[lambda x: x.split(' frame ')[-1].strip().split(' ')[0].split('/')[1]],
                    'files_to_search': ['txt']},
        'commit': {'patterns':[lambda x: x.split('Codec: ')[1].split('\n')[0].split(' ')[-1]],
                    'files_to_search': ['txt']},
        'avg_speed': {'patterns': [lambda x: 'n/a'],
                    'files_to_search': ['txt']},
        'avg_latency': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']},    
        'clip_fps' : {'patterns': [lambda x: x.split('Total Frames')[1].split('fps')[0].split('\t')[-1].strip(), lambda x: x.split('SAR 1:1 DAR 16:9],')[1].split('fps')[0].split(',')[-1].strip(), lambda x: x.split('--fps=')[1].split(' ')[0].split('"')[0].strip()],
                        'files_to_search': ['txt','log']},   
        'max_latency': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']}, 
        'target_bitrate': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']},                            
    }

ENCODER_PATTERNS['vvencapp'] = {
        'codec': {'patterns':[lambda x: x.split('Command being timed: "./')[1].split(' ')[0]],
                    'files_to_search': ['txt']},
        'width': {'patterns':[lambda x: x.split('vvenc [info]: Real Format')[1].split('yuv420p')[0].split(':')[1].split('x')[0].strip(), lambda x: x.split('vvdecapp [info]: SizeInfo:')[1].split('x')[0].strip()],
                    'files_to_search': ['txt','log']},
        'height': {'patterns':[lambda x: x.split('vvenc [info]: Real Format')[1].split('yuv420p')[0].split(':')[1].split('x')[1].strip(), lambda x: x.split('[info]:')[1].split('x')[1].split(' ')[0].strip().replace('p','')],
                    'files_to_search': ['txt','log']},
        'bit_depth': {'patterns':[lambda x: x.split('[info]: profile ')[1].split('\n')[0].split(',')[-1].split('-')[0].strip(), lambda x: x.split('vvdecapp [info]: SizeInfo:')[1].split('(')[1].split('b')[0].strip()],
                    'files_to_search': ['txt','log']},
        'bitrate': {'patterns':[lambda x: x.split('Total Frames')[1].strip().split('\n')[1].split('a')[1].strip().split(' ')[0].strip()],
                    'files_to_search': ['txt']},
        'frame_count': {'patterns':[lambda x: x.split('Total Frames')[1].strip().split('\n')[1].split('a')[0].split('\t')[1].strip()],
                    'files_to_search': ['txt']},
        'commit': {'patterns':[lambda x: x.split('vvencapp: Fraunhofer VVC Encoder ver.')[1].split('[Linux]')[0].strip()],
                    'files_to_search': ['txt']},
        'avg_speed': {'patterns': [lambda x: 'n/a'],
                    'files_to_search': ['txt']},
        'avg_latency': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']},         
        'clip_fps' : {'patterns': [lambda x: x.split('Total Frames')[1].split('fps')[0].split('\t')[-1].strip(), lambda x: x.split('SAR 1:1 DAR 16:9],')[1].split('fps')[0].split(',')[-1].strip(), lambda x: x.split('--fps=')[1].split(' ')[0].split('"')[0].strip()],
                        'files_to_search': ['txt','log']},  
        'max_latency': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']}, 
        'target_bitrate': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']},                            
    }

ENCODER_PATTERNS['aomenc'] = {
        'codec': {'patterns': [lambda x: x.split('Command being timed: "./')[1].split(' ')[0]],
                    'files_to_search': ['txt']},
        'width': {'patterns': [lambda x: x.split('Input format')[1].split('x')[0].split(',')[-1].strip()],
                    'files_to_search': ['txt']},
        'height': {'patterns': [lambda x: x.split('Input format')[1].split('x')[1].split(',')[0].strip()],
                    'files_to_search': ['txt']},
        'bit_depth': {'patterns': [lambda x: x.split('Input format')[1].split('FPS')[1].split(',')[1].split('bit')[0].strip()],
                    'files_to_search': ['txt']},
        'bitrate': {'patterns': [lambda x: str(float(x.split('Summary:    ')[1].split('|')[0].strip()) * 1000)],
                    'files_to_search': ['txt']},
        'frame_count': {'patterns': [lambda x: str(int(x.split('<frames>')[1].split('<frame frameNum="')[-1].split('"')[0].strip()) + 1), \
                                     lambda x : str(int(x.split('POC:')[-1].split('[ KEY ]')[0].strip()) + 1)],
                    'files_to_search': ['txt']},
        'commit': {'patterns': [lambda x: x.split('Codec')[1].split('Encoder')[1].split('\n')[0].strip()],
                    'files_to_search': ['txt']},
        'avg_speed': {'patterns': [lambda x: 'n/a'],
                    'files_to_search': ['txt']},
        'avg_latency': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']},            
        'clip_fps' : {'patterns': [lambda x: x.split('Total Frames')[1].split('fps')[0].split('\t')[-1].strip(), lambda x: x.split('SAR 1:1 DAR 16:9],')[1].split('fps')[0].split(',')[-1].strip(), lambda x: x.split('--fps=')[1].split(' ')[0].split('"')[0].strip()],
                        'files_to_search': ['txt','log']},   
        'max_latency': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']}, 
        'target_bitrate': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']},                            
    }

ENCODER_PATTERNS['VP9'] = {
        'codec': {'patterns': [lambda x: x.split('Codec: ')[1].split('\n')[0].split(' ')[-3]],
                    'files_to_search': ['txt']},
        'width': {'patterns': [lambda x: x.split('g_w = ')[1].split('\n')[0]],
                    'files_to_search': ['txt']},
        'height': {'patterns': [lambda x: x.split('g_h = ')[1].split('\n')[0]],
                    'files_to_search': ['txt']},
        'bit_depth': {'patterns': [lambda x: x.split('g_bit_depth = ')[1].split('\n')[0]],
                    'files_to_search': ['txt']},
        'bitrate': {'patterns': [lambda x: x.split('b/s')[-2].split('b/f ')[-1]],
                    'files_to_search': ['txt']},
        'frame_count': {'patterns': [lambda x: x.split(' frame ')[-1].strip().split(' ')[0].split('/')[1]],
                    'files_to_search': ['txt']},
        'commit': {'patterns': [lambda x: x.split('Codec: ')[1].split('\n')[0].split(' ')[-1]],
                    'files_to_search': ['txt']},
        'avg_speed': {'patterns': [lambda x: 'n/a'],
                    'files_to_search': ['txt']},
        'avg_latency': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']},   
        'clip_fps' : {'patterns': [lambda x: x.split('Total Frames')[1].split('fps')[0].split('\t')[-1].strip(), lambda x: x.split('SAR 1:1 DAR 16:9],')[1].split('fps')[0].split(',')[-1].strip(), lambda x: x.split('--fps=')[1].split(' ')[0].split('"')[0].strip()],
                        'files_to_search': ['txt','log']},        
        'max_latency': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']}, 
        'target_bitrate': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']},                            
    }

ENCODER_PATTERNS['x264'] = {
        'codec': {'patterns': [lambda x: x.split('[info]: using')[1].split('\n')[1].split('[info]')[0].strip()],
                    'files_to_search': ['txt']},
        'width': {'patterns': [lambda x: x.split(' [info]:')[1].split('x')[0].strip()],
                    'files_to_search': ['txt']},
        'height': {'patterns': [lambda x: x.split('[info]:')[1].split('x')[1].split(' ')[0].strip().replace('p', '')],
                    'files_to_search': ['txt']},
        'bit_depth': {'patterns': [lambda x: x.split('[info]: profile ')[1].split('\n')[0].split(',')[-1].split('-')[0].strip()],
                    'files_to_search': ['txt']},
        'bitrate': {'patterns': [lambda x: x.split('kb/s\n')[-2].split(',')[-1].strip()],
                    'files_to_search': ['txt']},
        'frame_count': {'patterns': [lambda x: x.split(' frames')[-2].split('encoded')[1].strip()],
                    'files_to_search': ['txt']},
        'commit': {'patterns': [lambda x: x.split('Codec: ')[1].split('\n')[0].split(' ')[-1]],
                    'files_to_search': ['txt']},
        'avg_speed': {'patterns': [lambda x: 'n/a'],
                    'files_to_search': ['txt']},
        'avg_latency': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']},             
        'clip_fps' : {'patterns': [lambda x: x.split('Total Frames')[1].split('fps')[0].split('\t')[-1].strip(), lambda x: x.split('SAR 1:1 DAR 16:9],')[1].split('fps')[0].split(',')[-1].strip(), lambda x: x.split('--fps=')[1].split(' ')[0].split('"')[0].strip()],
                        'files_to_search': ['txt','log']},  
        'max_latency': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']}, 
        'target_bitrate': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']},                            
    }

ENCODER_PATTERNS['x265'] = {
        'codec': {'patterns': [lambda x: x.split('Command being timed: "./')[1].split(' ')[0]],
                    'files_to_search': ['txt']},
        'width': {'patterns': [lambda x: x.split(' [info]:')[1].split('x')[0].strip()],
                    'files_to_search': ['txt']},
        'height': {'patterns': [lambda x: x.split('[info]:')[1].split('x')[1].split(' ')[0].strip().replace('p', '')],
                    'files_to_search': ['txt']},
        'bit_depth': {'patterns': [lambda x: x.split('[info]:')[1].split('i')[1].split(' ')[0].split('p')[1]],
                    'files_to_search': ['txt']},
        'bitrate': {'patterns': [lambda x: x.split('kb/s,')[-2].split(',')[-1].strip()],
                    'files_to_search': ['txt']},
        'frame_count': {'patterns': [lambda x: x.split(' frames')[-2].split('encoded')[1].strip()],
                    'files_to_search': ['txt']},
        'commit': {'patterns': [lambda x: x.split('Codec: ')[1].split('\n')[0].split(' ')[-1]],
                    'files_to_search': ['txt']},
        'avg_speed' : {'patterns': [lambda x: x.split('encoded')[1].split('frames')[1].split('fps),')[0].split('s (')[1].strip()],
                    'files_to_search': ['txt']},  
        'avg_latency': {'patterns': [lambda x: x.split('Avg Latency:')[1].split('\n')[0].strip()],                  
                        'files_to_search': ['txt']},    
        'clip_fps' : {'patterns': [lambda x: str(float(x.split(' fps ')[1].split(' ')[0].split('/')[0]) / float(x.split(' fps ')[1].split(' ')[0].split('/')[1]))],
                        'files_to_search': ['txt','log']},   
        'max_latency': {'patterns': [lambda x:  x.split('Max Latency:')[1].split('\n')[0].strip()],                  
                        'files_to_search': ['txt']}, 
        'target_bitrate': {'patterns': [lambda x: 'n/a'],                  
                        'files_to_search': ['txt']},                            
    }

METRIC_PATTERNS = {
    'cpu_usage': [lambda x: x.split('Percent of CPU this job got: ')[1].split('\n')[0].split('%')[0]],
    'encode_user_time': [lambda x: x.split('User time (seconds): ')[1].split('\n')[0]],
    'encode_sys_time': [lambda x: x.split('System time (seconds): ')[1].split('\n')[0]],
    'encode_wall_time': [lambda x: x.split('Elapsed (wall clock) time (h:mm:ss or m:ss): ')[1].split('\n')[0]],
    'max_memory': [lambda x: x.split('Maximum resident set size (kbytes): ')[1].split('\n')[0]],
    'psnr_y': [lambda x: x.split('psnr_y"')[1].split('mean="')[1].split('"')[0], lambda x: x.split('PSNR y:')[1].split(' ')[0]],
    'psnr_u': [lambda x: x.split('psnr_cb"')[1].split('mean="')[1].split('"')[0], lambda x: x.split(' u:')[1].split(' ')[0]],
    'psnr_v': [lambda x: x.split('psnr_cr"')[1].split('mean="')[1].split('"')[0], lambda x: x.split(' v:')[1].split(' ')[0]],
    'psnr_all': [lambda x: 'n/a'],
    'ssim_y': [lambda x: x.split('float_ssim"')[1].split('mean="')[1].split('"')[0], lambda x: x.split('] SSIM Y:')[1].split(' (')[1].split(') ')[0]],
    'ssim_u': [lambda x: x.split(') U:')[1].split(' (')[1].split(') ')[0]],
    'ssim_v': [lambda x: x.split(') V:')[1].split(' (')[1].split(') ')[0]],
    'ssim_all': [lambda x: 'n/a'],
    'vmaf': [lambda x: x.split('vmaf"')[1].split('mean="')[1].split('"')[0], lambda x: x.split('VMAF score: ')[1].split('\n')[0].strip()],
    'vmaf_neg': [lambda x: x.split('vmaf_neg"')[1].split('mean="')[1].split('"')[0]],
    
    #The Decode times need to stay empty as they are collected in a different folder later on
    'decode_sys_time': [lambda x: ''],
    'decode_user_time': [lambda x: ''],
    'decode_time': [lambda x: ''],

    
    'r2r_found':  [lambda x: 'n/a'],
    'cpu_usage_by_preset' :   [lambda x: ''],
    'wall_time_by_preset' : [lambda x: ''],


    'filesize_derived_from_bitrate' : [lambda x : ''],    
}



def main():
    global line_template
    
    global token_to_add_to_naming
    t0 = time.time()
    second_pass_encodings_found = False
    
    bitstreams = []
    metric_results = []
    token_to_add_to_naming = []
    bitstream_folders = glob.glob('{}*'.format(os.path.join(cwd, 'bitstreams')))

    decode_bitstreams_folder = os.path.join(cwd, 'decode_log_bitstreams')
    decode_strings = None
    bitstream_folders = sorted(bitstream_folders)
    pull_private_configs()

    for iteration, bitstream_folder in enumerate(bitstream_folders):


        bitstream_folder_name = os.path.split(bitstream_folder)[-1]

        '''Get the per preset metrics from the overall time logs'''
        per_preset_wall_time, per_preset_cpu_usage = get_preset_metrics()
        
        '''Gather the log files we will be scanning for metrics'''
        log_files, decode_log_files, bitstreams = get_files(bitstream_folder, decode_bitstreams_folder)
        
        '''Check for any params files for tokens to add to naming'''
        get_special_token_to_naming()

        '''Check for any cvh related info to trigger cvh collection'''        
        collect_cvh, max_number_of_cvh_points =  get_cvh_params(log_files)

        '''determine the format of collection to be done'''
        line_template, second_pass_encodings_found = collection_settings(collect_cvh, second_pass_encodings_found)

        '''Check bitstreams for ivf headers'''
        remove_ivf_header = has_ivf_header(bitstreams)
            
        '''Extract Decode and Metric results'''
        metric_results, stream_file_sizes, decode_strings = extract_metrics_from_logs(log_files, decode_log_files, bitstreams)

        '''Fill in the result line with the remaining filesize and decode metrics'''
        sorted_data_for_writing, all_presets, enc_name, codecs = fill_remaining_metrics(metric_results, stream_file_sizes, decode_strings, per_preset_cpu_usage, per_preset_wall_time,remove_ivf_header, second_pass_encodings_found, line_template)
        
        '''Safety Guard that checks that the filesize subtracted header matches within reasonable limits with the filesize derived from bitrate'''
        deviations_found = check_filesize_for_deviations(sorted_data_for_writing, enc_name)
            
        '''For tests where multiple runs of the same encoder were run for speed reasons, average out the data to a single result line'''
        sorted_data_for_writing = minimize_duplicate_data(sorted_data_for_writing,codecs)
        
        '''Detect encodings that did not generate similar metrics to other encodings. These anomalies indicate error in the encodings'''
        error_column_indices = get_error_columns(sorted_data_for_writing)
        
        '''Fill in errored cells with err'''
        sorted_data_for_writing = overwrite_error_values(error_column_indices, sorted_data_for_writing)

        '''Write results to output txt file'''
        write_results_to_txt(sorted_data_for_writing, enc_name, all_presets)

        print('second_pass_encodings_found',second_pass_encodings_found)
        if not force_classical_header and collect_cvh:
            get_cvh_results(['\t'.join(x) for x in sorted_data_for_writing], all_presets, enc_name, max_number_of_cvh_points)

        print('Time taken: ', time.time() - t0)


def pull_private_configs():
    if os.path.isfile('private_configs_2025_04_16.py'):
        from private_configs_2025_04_16 import private_configs
            
        private_test_configurations, private_encoder_patterns = private_configs()
        for key, value in private_encoder_patterns.items():
            ENCODER_PATTERNS[key] = value


    
def get_preset_metrics():
    per_preset_wall_time = {}
    per_preset_cpu_usage = {}
    per_preset_logs = glob.glob('%s/*.log' % os.getcwd())
    
    for time_encode_log in per_preset_logs:
        if 'time_encode' in time_encode_log:
            time_preset = 'M{}'.format(re.search('time_encode_(.*?)\.',time_encode_log).group(1))
            with open(time_encode_log) as log:
                content = log.read()
                if 'Elapsed (wall clock) time (h:mm:ss or m:ss): ' in content:
                    wall_time_by_preset = content.split('Elapsed (wall clock) time (h:mm:ss or m:ss): ')[1].split('\n')[0]
                    
                    if wall_time_by_preset.count(":") == 1:
                        m, s = wall_time_by_preset.split(":")
                        wall_time_by_preset = float(m) * 60 + float(s)
                    else:
                        h, m, s = wall_time_by_preset.split(":")
                        wall_time_by_preset = float(h) * 3600 + float(m) * 60 + float(s)
                    wall_time_by_preset = wall_time_by_preset * 1000
                else:
                    wall_time_by_preset = 'n/a'
                    
                per_preset_wall_time[time_preset] = wall_time_by_preset
                
                if 'Percent of CPU this job got: ' in content:
                    cpu_usage_by_preset = float(content.split('Percent of CPU this job got: ')[1].split('\n')[0].split('%')[0])
                else:
                    cpu_usage_by_preset = 'n/a'
                per_preset_cpu_usage[time_preset] = cpu_usage_by_preset
                
    sum_wall_time_overall = 0
    sum_cpu_usage_overall = 0
    
    for wall_time in per_preset_wall_time:
        if 'overall' in wall_time:
            sum_wall_time_overall += per_preset_wall_time[wall_time]
            sum_cpu_usage_overall += per_preset_cpu_usage[wall_time]
            
    per_preset_wall_time['overall'] = sum_wall_time_overall
    per_preset_cpu_usage['overall'] = sum_cpu_usage_overall

    return per_preset_wall_time, per_preset_cpu_usage


def get_files(bitstream_folder, decode_bitstreams_folder):
    log_files = [log for log in glob.glob('%s/*.log' % bitstream_folder)]
    log_files = sorted(log_files)
    bitstreams = [stream.replace('.log','.bin') for stream in log_files]
    
    if os.path.isdir(decode_bitstreams_folder):
        decode_log_files = [log for log in glob.glob('%s/*.log' % decode_bitstreams_folder)]
    else:
        decode_log_files = None
    return log_files, decode_log_files, bitstreams


def get_cvh_params(log_files):
    max_number_of_cvh_points = 40
    
    collect_cvh = False
    parameter_logs = sorted([log for log in glob.glob('%s/*.txt' % cwd) if 'parameters' in log])

    if parameter_logs:
        parameter_log = parameter_logs[-1]

        with open(parameter_log) as log:
            log_content = log.read()

            if 'resolutions' in log_content:
                resolutions = log_content.split('resolutions: ')[1].split('\n')[0]
                if resolutions != 'None':
                    collect_cvh = True

    if 'time_downscale.log' in [os.path.split(x)[-1] for x in glob.glob('%s/*.log' % os.getcwd())]:
        collect_cvh = True
        
    if collect_cvh:
        print("Auto collecting a maximum of {} CVH points".format(max_number_of_cvh_points))

    return collect_cvh, max_number_of_cvh_points


def collection_settings(collect_cvh, second_pass_encodings_found):
    global token_to_add_to_naming
    if collect_cvh:
        line_template = HEADERS['convex hull']
    else:
        line_template = HEADERS['classical']

    if force_classical_header:
        line_template = HEADERS['classical']

    if multi_pass_collection:
        if '_' in bitstream_folder_name:
            second_pass_encodings_found = True

        if second_pass_encodings_found:
            token_to_add_to_naming = token_to_add_to_naming + ['_'.join(bitstream_folder_name.split('_')[1:])]
            print('token_to_add_to_naming',token_to_add_to_naming)
    return line_template, second_pass_encodings_found


def has_ivf_header(bitstreams):
    # IVF signature "DKIF" (in little-endian format)
    ivf_signature = b'DKIF'
    ivf_detected = set()
    xyz_detected = False
    for file_path in bitstreams:
        if re.search('_Mh\d+_',os.path.split(file_path)[1]):
            xyz_detected = True
        try:
            with open(file_path, 'rb') as file:
                # Read the first 32 bytes from the file
                bitstream = file.read(32)

                # Check if the bitstream is at least the size of a minimal IVF header
                if len(bitstream) < 32:
                    ivf_detected.add(False)
                    continue
                    
                # Check for the IVF signature at the beginning of the bitstream
                if bitstream[:4] != ivf_signature:
                    ivf_detected.add(False)
                    continue

                ivf_detected.add(True)
                
        except FileNotFoundError:
            print("File not found: {file_path}".format(**vars()))
            ivf_detected.add(False)
        except Exception as e:
            print("Error reading file: {e}".format(**vars()))
            ivf_detected.add(False)

    if len(ivf_detected) == 1:
        if list(ivf_detected)[0] == True:
            print('\n[Check 1]: IVF Header: Found')
        else:
            print('\n[Check 1]: IVF Header: Not Found')
            
        return list(ivf_detected)[0]
    else:
        if not xyz_detected:
            check = input('[ERROR]: Mixture of IVF and Non IVF header bitstreams detected! Please debug. Continue? (1/0)...')
            if str(check) == '0':
                sys.exit()

    
def extract_metrics_from_logs(log_files, decode_log_files, bitstreams):
    log_files = sorted([x for x in log_files], key=lambda x: (os.path.split(x)[-1]))
    bitstreams = sorted([x for x in bitstreams], key=lambda x: (os.path.split(x)[-1]))    
    if decode_log_files:
        decode_log_files = sorted([x for x in decode_log_files], key=lambda x: (os.path.split(x)[-1]))
        decode_strings = execute_parallel_commands(number_of_cores, decode_log_files, cwd, 'decode_metrics')
    else:
        decode_strings = None
    '''Gather metric result from the logs in a multithreaded fashion'''
    metric_results = execute_parallel_commands(number_of_cores, log_files, cwd, 'metrics')
    
    '''Extract the filesizes from the encoded bitstreams'''
    stream_file_sizes = execute_parallel_commands(number_of_cores, bitstreams, cwd, 'file_size')
    
    return metric_results, stream_file_sizes, decode_strings


def fill_remaining_metrics(metric_results, stream_file_sizes, decode_strings, per_preset_cpu_usage, per_preset_wall_time, remove_ivf,second_pass_encodings_found, line_template):
    full_data_for_writing = []
    all_presets = []

    header = line_template.replace('{', '').replace('}', '').upper()
    cpu_usage_by_preset = 'n/a'
    wall_time_by_preset = 'n/a'
    codecs = set()
    decode_index = 0
    for metric_result, file_size in zip(metric_results, stream_file_sizes):
        if decode_strings:
            decode_user_time = decode_strings[decode_index].split(',')[0]
            decode_sys_time = decode_strings[decode_index].split(',')[1]
            decode_time = float(decode_user_time) + float(decode_sys_time)
        else:
            decode_user_time = 'n/a'
            decode_sys_time = 'n/a'
            decode_time = 'n/a'
        try:
            for index,name in enumerate(header.split('\t')):
                if name == 'FRAME_COUNT':
                    number_of_frames = int(metric_result.split('\t')[index])

        except BaseException:
            print(header.split('\t'))
            print(metric_result.split('\t'))
            print("Could not find number of frames for an encoding! Exiting...")
            sys.exit()
        try:
            for index,name in enumerate(header.split('\t')):
                if name == 'CLIP_FPS':
                    clip_fps = float(metric_result.split('\t')[index])
        except BaseException:
            clip_fps = None

        codec = metric_result.split('\t')[0]
        codecs.add(codec)
        preset = metric_result.split('\t')[1].split('_')[-1]
        enc_name = '_'.join(metric_result.split('\t')[1].split('_')[:-1])
        
        all_presets.append(preset)
        
        if second_pass_encodings_found:
            preset = 'overall'
        if preset in per_preset_cpu_usage:
            cpu_usage_by_preset = per_preset_cpu_usage[preset]
            wall_time_by_preset = per_preset_wall_time[preset]
           # print('wall_time_by_preset',wall_time_by_preset)
        if remove_ivf:
            file_size = file_size - (32 + (12 * number_of_frames))

        filesize_derived_from_bitrate = file_size
        
        # Calculate bitrate manually for the case where the pattern doesn't find it
        if 'bitrate' in metric_result and clip_fps and str(clip_fps)[0].isdigit():
            print('Bitrate not found in encode logs, computing manually using clip fps, file size and number of frames')
            bitrate = clip_fps * file_size * 8/ number_of_frames /1000
        else:
            bitrate = 'n/a'
        line_to_write = metric_result.format(**vars())
        full_data_for_writing.append(line_to_write)
        decode_index += 1
        
    all_presets = sorted(list(set(all_presets)))
    
    if len(codecs) == 1:
        sorted_data_for_writing = sorted([x.split('\t') for x in full_data_for_writing], key=lambda x: (x[1], x[4], x[2], x[5]))
    else:
        sorted_data_for_writing = sorted([x.split('\t') for x in full_data_for_writing], key=lambda x: (x[4], x[2], x[1], x[5]))

    sorted_data_for_writing.insert(0, header.split('\t'))
    
    return sorted_data_for_writing, all_presets, enc_name, codecs


def check_filesize_for_deviations(sorted_data_for_writing, enc_name):
    file_size_index = None
    filesize_derived_from_bitrate_index = None
    deviations_found = dict()
    
    for index, name in enumerate(sorted_data_for_writing[0]):
        if name == 'file_size'.upper():
            file_size_index = index
        if name == 'filesize_derived_from_bitrate'.upper():
            filesize_derived_from_bitrate_index = index
            
    if file_size_index and filesize_derived_from_bitrate_index:
        for result in sorted_data_for_writing[1:]:
            try:
                deviation = ((float(result[filesize_derived_from_bitrate_index]) / float(result[file_size_index])) - 1) * 100
            except:
                #print('Issue in filesize/bitrate deviation check')
                continue
            if abs(deviation) > 0.5:
                deviations_found['{}_{}'.format(result[4],result[5])] = str(deviation)
                
    if deviations_found and 'x265' not in enc_name:
        with open('UNACCEPTABLE_DEVIATIONS_BETWEEN_FILESIZE_AND_BITRATE.txt','w') as bug:
            for sequence_name in deviations_found:
                deviation = deviations_found[sequence_name]
                bug.write(sequence_name)
                bug.write('\t')
                bug.write(deviation)
                bug.write('\n')
        print('{} deviation found'.format(str(deviations_found)))
        print('[ERROR:] There are unacceptable deviations between the measured file size and the bitrate derived file size...')
        
    else:
        print('[Check 2]: Bitrate/Filesize Deviation: Good\n')  
        
    return deviations_found
    
    
def remove_duplicates(nested_list):
    seen = set()
    unique_list = []
    for sublist in nested_list:
        sublist_tuple = tuple(sublist)  # Convert the list to a tuple
        if sublist_tuple not in seen:
            seen.add(sublist_tuple)  # Add the tuple to the set
            unique_list.append(sublist)  # Add the original list to the result
    return unique_list            


def select_float_value(input_list):
    for item in input_list:
        if isinstance(item, float):
            return item
    return item  # Return None if no float value is found


def minimize_duplicate_data(sorted_data_for_writing,codecs):
    minimized_data = dict()
    header = sorted_data_for_writing[0]
    sorted_data = csv.DictReader(['\t'.join(x) for x in sorted_data_for_writing], delimiter='\t')
    minimized_data_for_writing = []
    for data in sorted_data:
        codec = data['CODEC']
        enc_name = data['ENC_NAME']
        input_sequence = data['INPUT_SEQUENCE']
        resolution = data['WIDTHXHEIGHT']
        rc_value = data['RC_VALUE']
        minimized_data.setdefault(codec, {}).setdefault(enc_name, {}).setdefault(input_sequence, {}).setdefault(resolution, {}).setdefault(rc_value, {})

        '''If a number that can be averaged is found, add it to a list to be averaged later'''
        for metric in data:
            try:
               # float(data[metric])
                if metric in minimized_data[codec][enc_name][input_sequence][resolution][rc_value]:
                    if data[metric].isdigit():
                        minimized_data[codec][enc_name][input_sequence][resolution][rc_value][metric].append(int(data[metric]))
                    else:
                        minimized_data[codec][enc_name][input_sequence][resolution][rc_value][metric].append(float(data[metric]))
                        
                else:
                    if data[metric].isdigit():
                        minimized_data[codec][enc_name][input_sequence][resolution][rc_value][metric]= [int(data[metric])]
                    else:
                        minimized_data[codec][enc_name][input_sequence][resolution][rc_value][metric]= [float(data[metric])]
                    
            except ValueError:
                
                if metric not in minimized_data[codec][enc_name][input_sequence][resolution][rc_value]:
                    minimized_data[codec][enc_name][input_sequence][resolution][rc_value][metric]= [data[metric]]
                    
    '''Take min of the lists'''
    for codec in minimized_data:
        for enc_name in minimized_data[codec]:
            for input_sequence in minimized_data[codec][enc_name]:
                for resolution in minimized_data[codec][enc_name][input_sequence]:
                    for rc_value in minimized_data[codec][enc_name][input_sequence][resolution]:
                        for metric in minimized_data[codec][enc_name][input_sequence][resolution][rc_value]:
                            values = minimized_data[codec][enc_name][input_sequence][resolution][rc_value][metric]
                            values = list(set(values))
                            if len(values) > 1:
                                try:
                                    min_of_metrics = min(minimized_data[codec][enc_name][input_sequence][resolution][rc_value][metric])
                                    minimized_data[codec][enc_name][input_sequence][resolution][rc_value][metric] = min_of_metrics
                                except TypeError:
                                    input_list = minimized_data[codec][enc_name][input_sequence][resolution][rc_value][metric]
                                    minimized_data[codec][enc_name][input_sequence][resolution][rc_value][metric] = select_float_value(input_list)
                            else:
                                minimized_data[codec][enc_name][input_sequence][resolution][rc_value][metric] = values[0]
    sorted_data = csv.DictReader(['\t'.join(x) for x in sorted_data_for_writing], delimiter='\t')
    fieldnames = sorted_data.fieldnames
    
    minimized_data_for_writing = []
    sorted_data = [OrderedDict(row) for row in sorted_data]  # Convert each row to a dictionary

    for data in sorted_data:
        sub = []
        for metric in fieldnames:
            sub.append(str(minimized_data[data['CODEC']][data['ENC_NAME']][data['INPUT_SEQUENCE']][data['WIDTHXHEIGHT']][data['RC_VALUE']][metric]))
            
        minimized_data_for_writing.append(sub)
    
    minimized_data_for_writing = remove_duplicates(minimized_data_for_writing)
    
    '''For the case where we are running hybrid encoders and there are several encoders in the results'''
    if len(codecs) == 1:
        sorted_minimized_data_for_writing = sorted([x for x in minimized_data_for_writing], key=lambda x: (x[1], x[4], x[2], x[5]))
    else:
        sorted_minimized_data_for_writing = sorted([x for x in minimized_data_for_writing], key=lambda x: (x[4], x[2], x[1], x[5]))

    sorted_minimized_data_for_writing.insert(0,header)
    return sorted_minimized_data_for_writing
    
    
def get_error_columns(results):
    error_column_indices = list()

    for index, result_column in enumerate(zip(*results)):
        if 'n/a' in list(set(result_column)):
            if len(list(set(result_column))) > 2:
                error_column_indices.append(index)
    for error in error_column_indices:
        print("Error in {}".format(results[0][error]))  
        
    return error_column_indices
 
 
def overwrite_error_values(column_indices, results):
    for row_number, result in enumerate(results):
        for column_index in column_indices:
            if result[column_index] == 'n/a':
                results[row_number][column_index] = 'err_{}'.format(results[0][column_index])
    return results


def write_results_to_txt(sorted_data_for_writing, enc_name, all_presets):
    result_file_name = '_result_{}.txt'.format(enc_name).replace('/', '')

    preset = None
    with open(result_file_name, 'w') as out:
        for index,data in enumerate(sorted_data_for_writing):
            if index < len(sorted_data_for_writing)-1:
                enc_preset = sorted_data_for_writing[index+1][1].split('_')[-1]
            data = '\t'.join(data)
            out.write(data)
            out.write('\n')
            if not preset and index !=0:
                preset = enc_preset
            elif preset and enc_preset != preset:
                out.write('\n')    
                preset = enc_preset    
            
    
def get_special_token_to_naming():
    global token_to_add_to_naming
    parameter_logs = sorted([log for log in glob.glob('%s/.*.txt' % cwd) if 'parameters' in log])
    print('parameter_logs',parameter_logs)
    if not parameter_logs:
        return list()
    parameter_log = parameter_logs[-1]
    print('extracting info from', parameter_log)
    with open(parameter_log) as log:
        log_content = log.read()
        if 'insert_special_parameters' in log_content:
            token_to_add_to_naming = log_content.split('insert_special_parameters:')[1].strip(' ').strip('\n').strip('[]').replace("'", '').split(',')
        else:
            token_to_add_to_naming = log_content.split('INSERT_SPECIAL_PARAMETERS:')[1].strip(' ').strip('\n').strip('[]').replace("'", '').split(',')
       
        test_name = log_content.split('test_name:')[1].split('\n')[0].strip(' ').replace(' ','')
        token_to_add_to_naming = [test_name] + token_to_add_to_naming #'%s_%s'%(test_name,token_to_add_to_naming)#token_to_add_to_naming.split(',')





def get_data_to_search(root_file, prefixes_to_search):
    data_to_search = list()

    '''prepare the nested list of data to be searched through by check_for_metric'''
    for prefix in prefixes_to_search:
        file_to_search = '%s.%s' % (root_file, prefix)

        if os.path.exists(file_to_search):
            with open(file_to_search, 'rb') as log:
                try:
                    log_content = log.read().decode('utf-8')
                except UnicodeDecodeError:
                    log.seek(0)
                    log_content = log.read().decode('latin-1', 'replace')
                data_to_search.append(log_content)
    return data_to_search  


def get_metrics(file):
    global token_to_add_to_naming
    RESULT = dict()
    root_file = os.path.splitext(file)[0]

    metric_prefixes_to_search = ['xml', 'txt', 'log','vmaf']#, 'vmaf_log']
                
    encoder_match = False
    
    '''Match patterns for the encoder we are collecting. Collect the Encoder specific patterns'''
    for encoder_type in ENCODER_PATTERNS:
        for metric in ENCODER_PATTERNS[encoder_type]:
            data_to_search = get_data_to_search(root_file,  ENCODER_PATTERNS[encoder_type][metric]['files_to_search'])
            RESULT[metric] = check_for_metric(data_to_search, ENCODER_PATTERNS[encoder_type][metric]['patterns'],metric).strip('\t')

            if str(metric) == 'codec' and str(RESULT[metric]) != encoder_type:
                break
            elif str(RESULT[metric]) == encoder_type:
                encoder_match = True
        if encoder_match:
            break
            
    if not encoder_match:
        print("Collection not supported for this encoder",file)



    data_to_search = get_data_to_search(root_file, metric_prefixes_to_search)

    '''Grab all metrics in the pattern dict'''
    for metric in METRIC_PATTERNS:
        RESULT[metric] = check_for_metric(data_to_search, METRIC_PATTERNS[metric],metric).strip('\t')

    '''Get following metrics from filename'''
    file_name = os.path.split(file)[-1]
    
    rc_found = re.search(r'M-?h?\d+_*(.*?)_*RC(\d+)-?\d?\..*?', file_name)
    
    if not rc_found:
        rc_found = re.search(r'M-?h?\d+_*(.*?)_*Q(\d+)-?\d?\..*?', file_name)
        
    if rc_found:
        RESULT['input_sequence'] = rc_found.group(1)
        RESULT['rc_value'] = rc_found.group(2)
    else:
        RESULT['input_sequence'] = 'err_sequence_name'
        RESULT['rc_value'] = 'err_rc'
        print('ERROR: Could not find a matching pattern in the bitstream file name. EXITTING')
        sys.exit()
        
    if re.search(r'\d+x\d+to\d+x\d+', RESULT['input_sequence']):
        RESULT['sequence_resolution'] = re.search(r'\d+x\d+to\d+x\d+', RESULT['input_sequence']).group(0)
    elif re.search(r'\d+x\d+', RESULT['input_sequence']):
        RESULT['sequence_resolution'] = re.search(r'\d+x\d+', RESULT['input_sequence']).group(0)
    else:
        RESULT['sequence_resolution'] = ''

    '''Refining section'''
    if RESULT['encode_wall_time'] == 'n/a':
        print('file', file)

    if RESULT['encode_wall_time'].count(":") == 1:
        m, s = RESULT['encode_wall_time'].split(":")
        RESULT['encode_wall_time'] = float(m) * 60 + float(s)
    else:
        h, m, s = RESULT['encode_wall_time'].split(":")
        RESULT['encode_wall_time'] = float(h) * 3600 + float(m) * 60 + float(s)

    if RESULT['codec'] in ['AV1', 'VP9', 'aomenc']:
        RESULT['bitrate'] = float(RESULT['bitrate']) / 1000

    RESULT['collection_date'] = date.today().strftime("%Y-%m-%d")

    '''Dummy variables to be collected in other functions'''
    RESULT['file_size'] = '{file_size}'
    RESULT['decode_sys_time'] = '{decode_sys_time}'
    RESULT['decode_user_time'] = '{decode_user_time}'
    RESULT['decode_time'] = '{decode_time}'

    RESULT['wall_time_by_preset'] = '{wall_time_by_preset}'
    RESULT['cpu_usage_by_preset'] = '{cpu_usage_by_preset}'

    '''Metrics to be grabbed from filename'''
    RESULT['bit_depth'] = '{}bit'.format(RESULT['bit_depth'])
    preset_found = re.search(r'_M(-?h?\d+)_', file_name)#.group(1)
    
    if preset_found:
        RESULT['preset'] = preset_found.group(1)
    else:
        RESULT['preset'] = 'err_preset'
        
    parent_folder = os.path.split(os.getcwd())[-1]
    preset = RESULT['preset']
    commit = RESULT['commit']
    
    if 'h' in RESULT['preset']:
       RESULT['enc_name'] = '_'.join([parent_folder] + ['xyz_M{preset}'.format(**RESULT).replace(' ', '_')])  
    elif use_simple_naming:
        RESULT['enc_name'] = '{parent_folder}_M{preset}'.format(**vars()).replace(' ', '_')
    else:
        token = '_'.join(token_to_add_to_naming)
        if commit != 'n/a':
            RESULT['enc_name'] = '{parent_folder}_{commit}_{token}_M{preset}'.format(**vars()).replace(' ', '_').replace('__','_')
        else:
            RESULT['enc_name'] = '{parent_folder}_{token}_M{preset}'.format(**vars()).replace(' ', '_').replace('__','_')
        
    '''Calcualte avg_speed manually if not found in the logs'''
    if not RESULT['avg_speed'][0].isdigit() and RESULT['frame_count'][0].isdigit():
        RESULT['avg_speed'] = float(RESULT['frame_count'])/float(RESULT['encode_wall_time'])
    if not str(RESULT['bitrate'])[0].isdigit():
        RESULT['bitrate'] = '{bitrate}'

    '''Convert time into ms'''
    RESULT['encode_wall_time'] = float(RESULT['encode_wall_time']) * 1000
    RESULT['encode_user_time'] = float(RESULT['encode_user_time']) * 1000
    RESULT['encode_sys_time']  = float(RESULT['encode_sys_time']) * 1000
    
    if RESULT['psnr_u'] == 'inf':
        RESULT['psnr_u'] = '0'
    if RESULT['psnr_v'] == 'inf':
        RESULT['psnr_v'] = '0'
        
    if RESULT['ssim_u'] == 'inf':
        RESULT['ssim_u'] = '0'
    if RESULT['ssim_v'] == 'inf':
        RESULT['ssim_v'] = '0'

    if 'Animation_720p' in RESULT['input_sequence'] or 'Animation_HighMotion_1080p' in RESULT['input_sequence'] or "Math_Lecture_1080p" in RESULT['input_sequence'] or "PingPong_Animation_1080p" in RESULT['input_sequence'] or "Train_B_and_W_720P" in RESULT['input_sequence']:
        RESULT['psnr_u'] = '0'
        RESULT['psnr_v'] = '0'
        RESULT['ssim_u'] = '0'
        RESULT['ssim_v'] = '0'
        
    y_scale = 8
    
    if RESULT['psnr_y'][0].isdigit() and RESULT['psnr_u'][0].isdigit() and RESULT['psnr_v'][0].isdigit():
        RESULT['psnr_all'] = (y_scale * float(RESULT['psnr_y']) + float(RESULT['psnr_u']) + float(RESULT['psnr_v'])) / (y_scale + 1 + 1)
    else:
        RESULT['psnr_all'] = 'n/a'
        
    if RESULT['ssim_y'][0].isdigit() and RESULT['ssim_u'][0].isdigit() and RESULT['ssim_v'][0].isdigit():
        RESULT['ssim_all'] = (y_scale * float(RESULT['ssim_y']) + float(RESULT['ssim_u']) + float(RESULT['ssim_v'])) / (y_scale + 1 + 1)
    else:
        RESULT['ssim_all'] = 'n/a'

    try:
        RESULT['filesize_derived_from_bitrate'] = ( (float(RESULT['bitrate']) * 1000) / 8 ) * ( float(RESULT['frame_count']) / float(RESULT['clip_fps']) ) 
    except:
        RESULT['filesize_derived_from_bitrate'] = 'n/a'
        
    '''Add Id to the bitdepth column so that it is compatible with Excel categorization checks'''

    RESULT = add_ids_to_bitdepth_metric(RESULT)
    
    line_to_write = line_template.format(**RESULT)

    return line_to_write


def add_ids_to_bitdepth_metric(RESULT):
    if RESULT['input_sequence'] in ['BigBuckBunnyStudio_1920x1080_60p_8byuv420_0000_0200',
                                   'BigBuckBunnyStudio_1920x1080_60p_8byuv420_0300_0404',
                                   'CSGO_1080p60_clip_65f',
                                   'KristenAndSaraScreen_1920x1080_60p_8byuv420p',
                                   'KristenAndSaraScreen_1920x1080_60p_8byuv420p_300f',
                                   'LyricVideo_1080P-41ee_horizontal_clip_0_k_7',
                                   'MINECRAFT_1080p_60_8bit',
                                   'MissionControlClip1_1920x1080_60fps_10bit_420_0450_0579',
                                   'NETFLIX_ElFuente_1920x1080to1280x720_lanc_14296frames_2997fps_000090_000179_crf_0.264',
                                   'NETFLIX_ElFuente_1920x1080_14296frames_2997fps_000090_000179_crf_0.264',
                                   'SceneComposition_1',
                                   'SceneComposition_3',
                                   'SceneComposition_1920x1080_15fps_000_200',
                                   'SlideShow_1280x720_20_60f',
                                   'Spreadsheet_1920x1080_30fps_8bit_420_200f',
                                   'Spreadsheet_1920x1080_30fps_8bit_420',
                                   'wikipedia_420',
                                   'Wikipedia_1920x1080p30']:
        RESULT['bit_depth'] += ', SC'
    else:
        RESULT['bit_depth'] += ', ' + 'Non-SC'
       
    class_240p_th = 0x28500
    class_360p_th = 0x4ce00
    class_480p_th = 0xa1400
    class_720p_th = 0x16da00
    class_1080p_th = 0x535200
    class_4k_th = 0x140a000
    pixels_per_frame = int(RESULT['width']) * int(RESULT['height'])

    if pixels_per_frame < class_240p_th:
        RESULT['bit_depth'] += ', ' + '240p'
    elif pixels_per_frame < class_360p_th:
        RESULT['bit_depth'] += ', ' + '360p'
    elif pixels_per_frame < class_480p_th:
        RESULT['bit_depth'] += ', ' + '480p'
    elif pixels_per_frame < class_720p_th:
        RESULT['bit_depth'] += ', ' + '720p'
    elif pixels_per_frame < class_1080p_th:
        RESULT['bit_depth'] += ', ' + '1080p'
    elif pixels_per_frame < class_4k_th:
        RESULT['bit_depth'] += ', ' + '4k'
    else:
        # 8k class clips labelled as 4k here for spreadsheet grouping; they are actually detected as 8k in the code
        RESULT['bit_depth'] += ', ' + '4k'

    return RESULT
    
    
def check_for_metric(data_to_search, pattern_list, metric_name):
    '''Order of files to search, first found first served'''
    for data in data_to_search:
        for pattern_index, pattern in enumerate(pattern_list):

            content_split = 'data%s' % pattern
            try:
                metric = pattern(data)

                return metric
            except IndexError:
                pass
    return 'n/a'
    

def get_metric_indices(result_lines):
    metric_indices = list()
    header = result_lines[0].split('\t')
    
    #Hard code the rate index to the 6th element of the cvh result file header
    rate_index = 6 # header.index('FILE_SIZE')
    
    for index, name in enumerate(result_lines[0].split('\t')):

        if name in ['PSNR_Y','SSIM_Y', 'VMAF', 'VMAF_NEG'] and result_lines[1].split('\t')[index][0].isdigit():#,'AVERAGE_QUALITY'
            print('Running Convex Hull selections on {} Metric'.format(name))

            metric_indices.append(index)


    return metric_indices, rate_index, header
    
    
def build_cvh_commands(header, result_lines, rate_index, metric_index):
    rates = list()
    metrics = list()
    cvh_commands = list()
    filtered_result_lines = list()
    
    prev_sequence_name = None
    number_of_elements_tracker = [0]

    vmaf_index = header.index('VMAF')
    rc_index = header.index('RC_VALUE')
    resolution_index = header.index('WIDTHXHEIGHT')
    
    for line in result_lines:
        line_split = line.split('\t')
        if line_split[vmaf_index][0].isdigit() and float(line_split[vmaf_index]) < 30.0:
            continue
        if max_cvh_bitrate and line_split[rate_index][0].isdigit() and float(line_split[rate_index]) > max_cvh_bitrate:
            continue
        if line_split[rc_index][0].isdigit() and float(line_split[rc_index]) < min_cvh_qp:
            continue           
        
        filtered_result_lines.append(line)
        
    for index, line in enumerate(filtered_result_lines):
        line_split = line.split('\t')

        if len(line_split) > 5 and line_split[5].strip().isdigit():
            sequence_name = line_split[4]
            
            root_sequence_name = re.search(r"(.*?)_\d+x\d+", sequence_name).group(1)
            rate = line_split[rate_index]
            metric = line_split[metric_index]

            if not prev_sequence_name or root_sequence_name == prev_sequence_name:
                prev_sequence_name = root_sequence_name
                rates.append(rate)
                metrics.append(metric)
                # cvh_result_lines.append(line)

            if root_sequence_name != prev_sequence_name or index == len(filtered_result_lines) - 1:
                number_of_elements = len(rates)
                number_of_elements_tracker.append(number_of_elements)
                prev_sequence_name = root_sequence_name
            
                cvh_command = '{0}/convex_hull_exe {1} {2} {3}'.format(tools_folder, str(len(rates)), ' '.join(rates), ' '.join(metrics))

                cvh_commands.append(cvh_command)

                rates = list()
                metrics = list()
                rates.append(rate)
                metrics.append(metric)
    return cvh_commands, number_of_elements_tracker, filtered_result_lines
    
    
def generate_cvh_points(cvh_commands, number_of_elements_tracker):   
    cvh_indices = list()    
    temp_cvh_results = execute_parallel_commands(number_of_cores, cvh_commands, cwd, 'cvh')

    '''Get optimal metric indices from convex hull exe'''
    index = 0
    current_line_number = 0
    for temp_cvh_result, number_of_elements in zip(temp_cvh_results, number_of_elements_tracker):
        temp_cvh_indices = list()
        current_line_number = current_line_number + number_of_elements
        
        if isinstance(temp_cvh_result, bytes):
            temp_cvh_result = temp_cvh_result.decode()
        
        for cvh_line in str(temp_cvh_result).split('\n'):
            if '=' in cvh_line:
                cvh_index = int(cvh_line.split(',')[0].split('=')[1]) + current_line_number + 1  # (index*(number_of_elements)) +1
                temp_cvh_indices.append(cvh_index)
        cvh_indices.append(temp_cvh_indices)
        index += 1
    return cvh_indices


def write_cvh_selections_to_file(cvh_metric, enc_name, all_presets, header, cvh_indices, filtered_result_lines, rate_index, metric_index, max_number_of_cvh_points):
    cvh_filename = '_{}_convex_hull_data_result_{}.txt'.format(cvh_metric, enc_name).replace('/', '')
    qp_index = 0
    if multi_pass_collection:
        if not os.path.isfile('multipass_cvh_{}.stat'.format(cvh_metric)):  
            multi_out = open('multipass_cvh_{}.stat'.format(cvh_metric),'w')
            multi_out.write('codec\tpreset\tsequence_name\trc_value\tresolution\tbitrate\n')#.format(**vars()))
        else:
            multi_out = None
    bitrate_index = header.index('BITRATE')     
    rc_index = header.index('RC_VALUE')
    '''Write selected convex hull selections to output and add filler lines for conformity'''
    with open(cvh_filename, 'w') as out:
        out.write('\t'.join(header))
        out.write('\n')

        for temp_cvh_indices in cvh_indices:
            for count, cvh_index in enumerate(temp_cvh_indices[::-1]):
                if count >= max_number_of_cvh_points:
                    print('Max number of CVH points exceeded, excluding extra points %s' % count)
                    break

                result_line_split = filtered_result_lines[cvh_index].split('\t')
                codec = result_line_split[0]
                
                qp = result_line_split[rc_index]
                resolution = result_line_split[2]
                sequence_name = result_line_split[4]
                bitrate = result_line_split[bitrate_index]
                preset = result_line_split[1].split('_')[-1]
                # print('sequence_name',sequence_name)
                root_sequence_name = re.search(r"(.*?)_\d+x\d+", sequence_name).group(1)
                
                if multi_pass_collection:
                    if multi_out:
                        multi_out.write('{codec}\t{preset}\t{sequence_name}\t{qp}\t{resolution}\t{bitrate}\n'.format(**vars()))
                
                '''Overwrite the encoding name and sequence name to cvh format'''
                qp_index +=1
                result_line_split[4] = root_sequence_name
                result_line_split[1] = '%s_%s' % (result_line_split[1], cvh_metric)
                result_line_split[5] = str(qp_index)
                indices_to_keep = []
                columns_to_keep = ['CPU_USAGE',	'AVG_SPEED',	'AVG_LATENCY',	'FRAME_COUNT',	'ENCODE_USER_TIME',	'WALL_TIME_BY_PRESET',	'MAX_MEMORY',	'ENCODE_SYS_TIME',	'DECODE_SYS_TIME',	'DECODE_USER_TIME',	'BITRATE',	'MAX_LATENCY',	'TARGET_BITRATE',	'FILESIZE_DERIVED_FROM_BITRATE']
                for header_index, name in enumerate(header):
                    if name in columns_to_keep:
                        indices_to_keep.append(header_index)
                '''Overwrite the irrelevant data columns'''
                for i in range(rate_index + 1, len(header)):
                    if not result_line_split[i].isdigit() and i != metric_index and i not in indices_to_keep:
                        result_line_split[i] = 'n/a'
                    # elif result_line_split[i].isdigit():
                        # break

                '''Write the resulting line'''
                out.write('\t'.join(result_line_split))
                out.write('\n')
            # print('len(temp_cvh_indices)',len(temp_cvh_indices))
            # print('max_number_of_cvh_points',max_number_of_cvh_points)
            if len(temp_cvh_indices) < max_number_of_cvh_points:
                for i in range(0, max_number_of_cvh_points - len(temp_cvh_indices)):
                    qp_index += 1
                    filler_line = result_line_split[:rate_index - 1] + [str(qp_index)] + ['n/a'] * (len(result_line_split) - len(result_line_split[:rate_index - 1]) -1 )
                    out.write('%s' % '\t'.join(filler_line))
                    out.write('\n')
    if multi_pass_collection:
        if multi_out:
            multi_out.close()


def get_cvh_results(result_lines, all_presets, enc_name, max_number_of_cvh_points):
    metric_indices = list()
    # cvh_result_lines = list()
    number_of_elements = 0
    if not os.path.isfile('{}/convex_hull_exe'.format(tools_folder)):
        print('\n\n[ERROR!]: cvh exe not found in tools folder, SKIPPING CVH, exitting...\n\n')
        sys.exit()
    '''Get the index of rate and a list of potential metrics to perform cvh on'''
    '''Note, Metric index gathering is greedy and may include invalid indices.'''
    '''Doesnt matter as we only gather the metric columns with reference to the header'''
    # May include for fix above in future
    if not metric_indices:
        metric_indices, rate_index, header = get_metric_indices(result_lines)

    all_cvh_commands = []
    
    '''Perform CVH analysis on the various metrics'''
    for metric_index in metric_indices:
        if '_Y' in header[metric_index] or 'VMAF' in header[metric_index]:# or 'AVERAGE_QUALITY' in header[metric_index]:
            cvh_metric = header[metric_index]
        else:
            continue    
        '''Build CVH commands for the current metric using the header and result lines'''
        cvh_commands, number_of_elements_tracker, filtered_result_lines = build_cvh_commands(header, result_lines, rate_index, metric_index)
        # print('cvh_commands',cvh_commands[0])
        '''Append the CVH commands to the list of all CVH commands'''
        all_cvh_commands.append(cvh_commands)
        
        '''Generate CVH points based on the CVH commands'''
        cvh_indices = generate_cvh_points(cvh_commands, number_of_elements_tracker)
        
        '''Write the CVH selections to a file for the current metric'''
        write_cvh_selections_to_file(cvh_metric, enc_name, all_presets, header, cvh_indices, filtered_result_lines, rate_index,metric_index, max_number_of_cvh_points)


def execute_cvh_commands(inputs):
    cmd, work_dir = inputs

    pipe = subprocess.Popen(cmd, shell=True, cwd=work_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = pipe.communicate()
    pipe.wait()
    return output


def execute_file_size_commands(inputs):
    stream, work_dir = inputs

    file_size = os.path.getsize(stream)
    return file_size


def get_decode_metrics(file):
    data_to_search = list()
    with open(file) as decode_log:
        decode_log_content = decode_log.read()
        data_to_search.append(decode_log_content)

    decode_sys_time = check_for_metric(data_to_search, METRIC_PATTERNS['encode_sys_time'], 'decode_sys_time').strip('\t')
    decode_user_time = check_for_metric(data_to_search, METRIC_PATTERNS['encode_user_time'], 'decode_user_time').strip('\t')

    decode_sys_time = float(decode_sys_time) * 1000
    decode_user_time = float(decode_user_time) * 1000

    decode_string = '{decode_user_time},{decode_sys_time}'.format(**vars())
    return decode_string


def execute_parallel_commands(number_of_processes, command_list, execution_directory, execution_type):
    
    # for command in command_list:
        # try:
            # command.strip()
        # except:
            # print(command)
    command_lines = [command.strip() for command in command_list]
    execution_directory_list = [execution_directory for i in enumerate(command_lines)]
    inputs = zip(command_lines, execution_directory_list)
    Pooler = multiprocessing.Pool(processes=number_of_processes, maxtasksperchild=30)
    output = []
    if execution_type == 'cvh':
        output = Pooler.map(execute_cvh_commands, inputs)
    elif execution_type == 'file_size':
        output = Pooler.map(execute_file_size_commands, inputs)
    elif execution_type == 'metrics':
        if debug:
            for command in command_list:
                output.append(get_metrics(command))
        else:
            output = Pooler.map(get_metrics, command_list)
    elif execution_type == 'decode_metrics':
        output = Pooler.map(get_decode_metrics, command_list)

    Pooler.close()
    Pooler.join()

    if sys.platform == 'Linux':
        os.system('stty sane')

    return output



if __name__ == '__main__':
    try:
        input = raw_input
    except NameError:
        pass

    

    main()
