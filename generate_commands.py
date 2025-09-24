import os
import sys
import re
import glob
import stat
import subprocess
import binascii
import multiprocessing
from datetime import datetime
import shutil
import hashlib
import ast
import time
import argparse
import csv
'''
SPIE Intraperiod Settings

SPIE2020 8bit : 128
SPIE2020 10bit : 119
SPIE2021 : -1
'''
TEST_SETTINGS = {

    ##'''Add special parameters to commands for testing (i.e. --pred-struct 1, --tune 0)'''##
    'insert_special_parameters' : [],
    
    'test_name': {''},

    'stream_dir': r'',
    'presets': [],
    'intraperiod': -1,
    'tools_folder': r'/home/tools',

    ##'''Execution Settings'''##
    'number_of_parallel_encodes': multiprocessing.cpu_count(),
    'number_of_parallel_metrics': multiprocessing.cpu_count(),
    'number_of_parallel_decodes': multiprocessing.cpu_count(),
    'single_cmd_files' : 1,
    'live_bash_execution' : 0,

    ##'''Additional Encode Settings'''
    'encode_iterations' : 1,
    'add_encoding_burner_run' : 0, 
    'derive_bitrate_from_crf_encodings' : 0,
    'run_encoders_in_parallel' : 0,
    'live_encode' : 0,

    ##'''Additional Metric Settings'''
    'do_not_generate_metrics' : 0,

    ##'''Additional Decode Settings'''
    'generate_decode_times': 0,  
    'threads_per_decode': 1,
    'decode_iterations': 10,

    ##'''Two Pass CVH Options'''
    'cvh_metric' : {'PSNR_Y' : 0,
                    'SSIM_Y' : 0,
                    'VMAF' : 0,
                    'VMAF_NEG' : 0},
}

def test_configurations():
    TEST_REPOSITORY = {   

       # SPIE2021 Configs
        'SPIE2021_svt'       : [RC_VALUES['SPIE2021_svt_aom'],   RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale'],       ENCODE_COMMAND['SPIE2021_svt_CRF_1lp_1p']],
        'SPIE2021_aom'       : [RC_VALUES['SPIE2021_svt_aom'],   RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale'],       ENCODE_COMMAND['SPIE2021_aom_CRF_2p']],
        'SPIE2021_x264'      : [RC_VALUES['SPIE2021_x264_x265'], RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale'],       ENCODE_COMMAND['SPIE2021_x264_CRF_1p']],
        'SPIE2021_x265'      : [RC_VALUES['SPIE2021_x264_x265'], RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale'],       ENCODE_COMMAND['SPIE2021_x265_CRF_1p']],
        'SPIE2021_vp9'       : [RC_VALUES['SPIE2021_svt_aom'],   RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale'],       ENCODE_COMMAND['SPIE2021_vp9_CRF_2p']],
        'SPIE2021_vvenc'     : [RC_VALUES['SPIE2021_svt_aom'],   RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale_vvenc'], ENCODE_COMMAND['SPIE2021_vvenc_CRF_1p']],
        'SPIE2021_svt_cqp'   : [RC_VALUES['SPIE2021_svt_aom'],   RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale'],       ENCODE_COMMAND['svt_CRF_1lp_1p_aq0']],
        'SPIE2021_avm_5L'    : [RC_VALUES['avm_11qp'],           RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_avm_ffmpeg_rescale'],           ENCODE_COMMAND['avm_CRF_1p']],
        'SPIE2021_vtm_RA'    : [RC_VALUES['SPIE2021_svt_aom'],   RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_vtm_rescale_ffmpeg'],   ENCODE_COMMAND['vtm_CRF_1p']],
        'SPIE2021_ffmpeg_svt_fast_decode': [RC_VALUES['SPIE2021_svt_aom'], RESOLUTION['SPIE2021_8bit'], DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale'], ENCODE_COMMAND['ffmpeg_svt_fast_decode']],

        'SPIE2021_svt_psnr_ssim_vmaf_vmaf_neg'       : [RC_VALUES['SPIE2021_svt_aom'], RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale'], ENCODE_COMMAND['SPIE2021_svt_CRF_1lp_1p']],
        'SPIE2021_svt_psnr_ssim_vmaf'       : [RC_VALUES['SPIE2021_svt_aom'], RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale_psnr_ssim_vmaf'], ENCODE_COMMAND['SPIE2021_svt_CRF_1lp_1p']],
        'SPIE2021_svt_psnr_ssim'       : [RC_VALUES['SPIE2021_svt_aom'], RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale_psnr_ssim'], ENCODE_COMMAND['SPIE2021_svt_CRF_1lp_1p']],
       
        #skip 1080p, 7 qp CVH
        'SPIE2021_svt_psnr_ssim_vmaf_vmaf_neg_7qp_skip_1080p'       : [RC_VALUES['SPIE2021_svt_aom_7qp'], RESOLUTION['SPIE2021_8bit_skip_1080p'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale'], ENCODE_COMMAND['SPIE2021_svt_CRF_1lp_1p']],
        'SPIE2021_svt_psnr_ssim_vmaf_7qp_skip_1080p'       : [RC_VALUES['SPIE2021_svt_aom_7qp'], RESOLUTION['SPIE2021_8bit_skip_1080p'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale_psnr_ssim_vmaf'], ENCODE_COMMAND['SPIE2021_svt_CRF_1lp_1p']],
        'SPIE2021_svt_psnr_ssim_7qp_skip_1080p'       : [RC_VALUES['SPIE2021_svt_aom_7qp'], RESOLUTION['SPIE2021_8bit_skip_1080p'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale_psnr_ssim'], ENCODE_COMMAND['SPIE2021_svt_CRF_1lp_1p']],
        
        #preset tuning
        'svt_CRF_1lp_1p_tuning_5qp': [RC_VALUES['5qp_preset_tuning'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['svt_CRF_1lp_1p']],
        'svt_CRF_1lp_1p_tuning_7qp': [RC_VALUES['new_7qp_preset_tuning'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['svt_CRF_1lp_1p']],
        'svt_CRF_1lp_1p_tuning_11qp': [RC_VALUES['11qp_preset_tuning'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['svt_CRF_1lp_1p']],
        'svt_CRF_1lp_1p_tuning_20qp': [RC_VALUES['20qp_preset_tuning'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['svt_CRF_1lp_1p']],
        'svt_allintra_cqp': [RC_VALUES['ctc_allintra_qps'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['svt_allintra_cqp_cmds']],
        'svt_still_image_cqp': [RC_VALUES['ctc_still_image_qps'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['svt_still_image_cqp_cmds']],
        'svt_ld_cqp': [RC_VALUES['ctc_crf_ld_as_qps'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['svt_ld_cqp_cmds']],
        'libaom_allintra_ctc': [RC_VALUES['ctc_allintra_qps'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['libaom_allintra_ctc_cmds']],
        'libaom_still_image_ctc': [RC_VALUES['ctc_still_image_qps'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['libaom_still_image_ctc_cmds']],
        'libaom_ld_constrained': [RC_VALUES['ctc_crf_ld_as_qps'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['libaom_ld_constrained_cmds']],
        'libavm_allintra_ctc': [RC_VALUES['ctc_allintra_qps'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf_AVM_DEOCODE'], ENCODE_COMMAND['libaom_allintra_ctc_cmds']],

        'svt_webrtc_cbr': [RC_VALUES['webrtc_ultra_LD'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim'], ENCODE_COMMAND['svt_webrtc']],
        'svt_rtc_cbr_psnr_low_tbrs': [RC_VALUES['svt_rtc_low_tbrs'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim'], ENCODE_COMMAND['svt_webrtc']],
        'aom_webrtc_cbr': [RC_VALUES['webrtc_ultra_LD'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['aom_webrtc']],
        'aom_webrtc_cbr_2': [RC_VALUES['webrtc_ultra_LD'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['aom_webrtc_2']],

        #Release Testing
        'svt_CRF'       : [RC_VALUES['7qp_preset_tuning'],   None,   None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'],       ENCODE_COMMAND['svt_CRF_1lp_1p']],
        'svt_1pass_VBR' : [RC_VALUES['7qp_preset_tuning'],   None,   None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'],       ENCODE_COMMAND['svt_VBR_1lp_1p']],
        'svt_2pass_VBR' : [RC_VALUES['7qp_preset_tuning'],   None,   None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'],       ENCODE_COMMAND['svt_VBR_1lp_2p']],
        'libaom_CRF'    : [RC_VALUES['7qp_preset_tuning'],   None,   None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'],       ENCODE_COMMAND['libaom_CRF_1lp']],
        'libaom_VBR'    : [RC_VALUES['7qp_preset_tuning'],   None,   None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'],       ENCODE_COMMAND['libaom_VBR_1lp_2p']],

        'SPIE2021_svt_reduced'       : [RC_VALUES['spie2021_reduced_qps'],  RESOLUTION['SPIE2021_8bit_reduced'], DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2020_ffmpeg_rescale_psnr_ssim'],       ENCODE_COMMAND['SPIE2021_svt_CRF_1lp_1p']],

    }

    return TEST_REPOSITORY


def main():
    '''Process Command Line Arguments'''
    parse_command_line()
    
    for test in TEST_SETTINGS['test_name']:
        
        '''Settings Check'''
        test_groups, cvh_data = configure_run(test)

        for cvh_metric in cvh_data: 
            if cvh_metric and not TEST_SETTINGS['cvh_metric'][cvh_metric]:
                continue
                
            for test_group in test_groups:
                generated_commands_list = list()
                for test_config in test_group:
                    for test_name in test_config:
                        TEST_SETTINGS['number_of_parallel_encodes'] = test_config[test_name]['number_of_parallel_encodes'] ###
                        TEST_SETTINGS['number_of_parallel_metrics'] = test_config[test_name]['number_of_parallel_metrics'] ###
                         
                        '''Generate commands for test being performed'''
                        generated_commands = process_command_template(test_name, cvh_data,cvh_metric)
                        generated_commands_list.append(generated_commands)
                        
                generated_commands = merge_dicts_by_index(generated_commands_list)

                '''Write commands to file'''
                encode_file_id, metric_file_id, decode_file_id, burner_file_id = write_commands_to_files(generated_commands, test_name, cvh_metric)
                
                '''Create the bash files to execute the commands'''
                bash_exe = generate_bash_driver_file(encode_file_id, metric_file_id, decode_file_id, burner_file_id, test_name, cvh_metric)
        


def parse_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--test-name', help='Name of test to run')
    parser.add_argument('-s', '--stream', help='Target stream folder')
    parser.add_argument('-p', '--presets', help='presets to test')
    parser.add_argument('-i', '--intraperiod', help='intraperiod to test')
    parser.add_argument('-c', '--commit', help='Commit to tests')
    parser.add_argument('-a', '--added_params', help='Additional parameters to add')
    parser.add_argument('-r', '--run', help='Execute Tests After Generation')

    args = parser.parse_args()
    if args.test_name:
        TEST_SETTINGS['test_name'] = [args.test_name]
    if args.stream:
        TEST_SETTINGS['stream_dir'] = args.stream
    if args.presets:
        if ',' in args.presets:
            TEST_SETTINGS['presets'] = [int(x) for x in args.presets.split(',')]
        else:
             TEST_SETTINGS['presets'] = [int(args.presets.strip())]        
    if args.intraperiod:
        TEST_SETTINGS['intraperiod'] = args.intraperiod
    if args.commit:
        EXECUTION_SETTINGS['commit'] = args.commit
    if args.added_params:
        TEST_SETTINGS['insert_special_parameters'] = [args.added_params]
    if args.run:        
        TEST_SETTINGS['run_after_generation'] = args.run


def configure_run(test):
    cvh_data = {None}
    stat_files = glob.glob('{}/*.stat'.format(os.getcwd()))
    test_names = []
    
    handle_errors(test, stat_files)
    if stat_files:
        cvh_data = parse_stat_files(stat_files)
    
    # Check the presets list for any indication of "h" indicating xyz preset
    for preset in TEST_SETTINGS['presets']:
        if 'h' in str(preset):
            TEST_SETTINGS['xyz_preset'] = preset

    if isinstance(TEST_SETTINGS['test_name'], dict):
        TEST_SETTINGS['presets'] = TEST_SETTINGS['test_name'][test]['presets']
        TEST_SETTINGS['number_of_parallel_encodes'] = TEST_SETTINGS['test_name'][test]['number_of_parallel_encodes']
        TEST_SETTINGS['number_of_parallel_metrics'] = TEST_SETTINGS['test_name'][test]['number_of_parallel_metrics']

    if 'xyz_preset' in TEST_SETTINGS and os.path.isfile('xyz_presets.py'):
        from xyz_presets import get_presets
        print('[TEST]: {}\n\t[TEST TYPE]: xyz'.format(test))
        xyz_preset = TEST_SETTINGS['xyz_preset']
        for cvh_metric in TEST_SETTINGS['cvh_metric']:
            if TEST_SETTINGS['cvh_metric'][cvh_metric]:
                for test_group in get_presets()[cvh_metric][xyz_preset]:
                    grouped_tests = [
                        {test: get_presets()[cvh_metric][xyz_preset][test_group][test]}
                        for test in get_presets()[cvh_metric][xyz_preset][test_group]
                    ]
                    test_names.append(grouped_tests)
        if isinstance(cvh_data, set):
            for test_group in get_presets()['one_pass'][xyz_preset]:
                print('test_group',test_group)
                grouped_tests = [
                    {test: get_presets()['one_pass'][xyz_preset][test_group][test]}
                    for test in get_presets()['one_pass'][xyz_preset][test_group]
                ]
                test_names.append(grouped_tests)                    
    else:
        if not any(TEST_SETTINGS['cvh_metric'].values()):
            print('[TEST]: {}\n\t[TEST TYPE]: Normal'.format(test))
        else:
            print('[TEST]: {}\n\t[TEST TYPE]: Two Pass CVH'.format(test))
            
        parsed_test = {
            test: {
                'number_of_parallel_encodes': TEST_SETTINGS['number_of_parallel_encodes'],
                'number_of_parallel_metrics': TEST_SETTINGS['number_of_parallel_metrics']
            }
        }
        if isinstance(TEST_SETTINGS['test_name'], dict):
            parsed_test = {
                test: {
                    'number_of_parallel_encodes': TEST_SETTINGS['test_name'][test]['number_of_parallel_encodes'],
                    'number_of_parallel_metrics': TEST_SETTINGS['test_name'][test]['number_of_parallel_metrics']
                }
            }
        return [[parsed_test]], cvh_data
    return test_names, cvh_data


def parse_stat_files(stat_files):
    cvh_data = dict()
    for stat_file in stat_files:
        with open(stat_file, mode='r') as stat:
            content = list(csv.DictReader(stat, delimiter='\t'))
            for cvh in content:
                metric = os.path.split(stat_file)[1].split('cvh_')[1].split('.')[0]
                cvh_data.setdefault(metric, {}).setdefault(cvh['rc_value'], {}).setdefault(cvh['sequence_name'], {})[cvh['codec']] = cvh['bitrate']
    return cvh_data


def handle_errors(test, stat_files):
    if 'xyz_preset' in TEST_SETTINGS and not os.path.isfile('xyz_presets.py'):
        print('\n[ERROR!]: xyz Preset Repo file not detected while a xyz preset was selected. Exiting...\n')
        sys.exit()

    if not stat_files and 'xyz_preset' in TEST_SETTINGS:
        print('\n[ERROR!]: First pass cvh data not found for xyz generation. Exiting...\n')
        sys.exit()

    if not os.path.isdir(TEST_SETTINGS['stream_dir']):
        print(TEST_SETTINGS['stream_dir'])
        print('[ERROR] The stream folder specified does not exist. Exiting...')
        sys.exit()

    if test not in test_configurations() and not os.path.isfile('private_configs_2025_04_16.py'):
        print('[ERROR] Invalid test configuration specified. Exiting...')
        sys.exit()
        

def filter_xyz_second_pass_bitrate(rc_value, cvh_data, cvh_metric, clip_name,test_name):
    from xyz_presets import get_presets
    xyz_preset = TEST_SETTINGS['xyz_preset']
    
    preset = ''
    skip = True
    xyz_presets = get_presets()
    '''Second pass configs'''
    for test_type in xyz_presets[cvh_metric][xyz_preset]:
        for xyz_test_name in xyz_presets[cvh_metric][xyz_preset][test_type]:
            if '{}_{}'.format(xyz_test_name,cvh_metric) != test_name:
                continue
            if cvh_metric in cvh_data and str(rc_value) in cvh_data[cvh_metric] and clip_name in cvh_data[cvh_metric][str(rc_value)]:
                for codec in cvh_data[cvh_metric][str(rc_value)][clip_name]:
                    bitrate = cvh_data[cvh_metric][str(rc_value)][clip_name][codec]
                    
                    for bitrate_range in xyz_presets[cvh_metric][xyz_preset][test_type][xyz_test_name]['bitrate_ranges']:
                        bitrate_range_preset = xyz_presets[cvh_metric][xyz_preset][test_type][xyz_test_name]['bitrate_ranges'][bitrate_range]
                       
                        if '-' in bitrate_range:
                            lower = int(bitrate_range.split('-')[0])
                            upper = int(bitrate_range.split('-')[1])
                        if '+' in bitrate_range:
                            lower = int(bitrate_range.split('+')[0])
                            upper = 999999999999

                        if float(bitrate) > lower and float(bitrate) <= upper:
                            # print('bitrate_range_preset',bitrate_range_preset)
                            preset = bitrate_range_preset.split('M')[1]
                            skip = False

    preset = preset.replace('M', '')
    return preset, skip

def filter_xyz_ABR_bitrate(rc_value, cvh_data, cvh_metric, clip_name,test_name):
    from xyz_presets import get_presets
    xyz_preset = TEST_SETTINGS['xyz_preset']
    
    preset = ''
    skip = True
    xyz_presets = get_presets()
    cvh_metric = 'one_pass'
    '''ABR configs'''

    for test_type in xyz_presets[cvh_metric][xyz_preset]:
        for test in xyz_presets[cvh_metric][xyz_preset][test_type]:
            if test != test_name:
                continue
            bitrate = rc_value
            
            for bitrate_range in xyz_presets[cvh_metric][xyz_preset][test_type][test]['bitrate_ranges']:
                bitrate_range_preset = xyz_presets[cvh_metric][xyz_preset][test_type][test]['bitrate_ranges'][bitrate_range]
                if '-' in bitrate_range:
                    lower = int(bitrate_range.split('-')[0])
                    upper = int(bitrate_range.split('-')[1])
                if '+' in bitrate_range:
                    lower = int(bitrate_range.split('+')[0])
                    upper = 999999999999
                if float(bitrate) > lower and float(bitrate) <= upper:
                    preset = bitrate_range_preset.split('M')[1]
                    skip = False

    preset = preset.replace('M', '')
    return preset, skip


def filter_encodings(test_name, rc_value, width, height, clip_name, resolution, cvh_data, cvh_metric, preset, first_pass_results,scaling_resolutions):
    skip = False

    clip_name = clip_name.strip().rstrip('_')
    '''Filter out clips if not in the source resolution list'''
    if scaling_resolutions:
        skip = True
        for source_resolution in scaling_resolutions:
            if str(width) == str(source_resolution[0]) and str(height) == str(source_resolution[1]):
                skip = False
                break

    '''parse the vbr ladder in to rc and resolution'''
    if isinstance(rc_value, list):
        resolution = rc_value[0]
        rc_value = rc_value[1]

    '''Check if the given clip/qp was selected by the first pass CVH. If not, skip'''
    if cvh_metric and  'xyz_preset' not in TEST_SETTINGS:
        # print('Entering standard second Pass CVH seleciton methods')
        try:
            bitrate = cvh_data[cvh_metric][str(rc_value)][clip_name]
        except Exception as e:
            skip = True
            return preset, rc_value, skip, resolution
            
    '''Change the preset based on the bitrate from the first pass'''
    if cvh_metric and 'xyz_preset' in TEST_SETTINGS:
        preset, skip = filter_xyz_second_pass_bitrate(rc_value, cvh_data, cvh_metric, clip_name, test_name)

    elif not cvh_metric and  'xyz_preset' in TEST_SETTINGS:
        preset, skip = filter_xyz_ABR_bitrate(rc_value, cvh_data, cvh_metric, clip_name, test_name)    
        
    '''VBR Ladder filtering'''
    if resolution and str(width) not in str(resolution) and str(height) not in str(resolution):
        skip = True

    '''EXTRACT BITRATE FROM THE RESULTS FILES OF A CRF ENCODINGS RUN'''
    if TEST_SETTINGS['derive_bitrate_from_crf_encodings']:
        rc_value  = int(round(float(first_pass_results[str(preset)][clip_name][str(rc_value)]),0))

    return preset, rc_value, skip, resolution


def get_configs(test_name):
    if os.path.isfile('private_configs_2025_04_16.py'):
        from private_configs_2025_04_16 import private_configs
            
        private_test_configurations, private_encoder_patterns = private_configs()
        for key, value in test_configurations().items():
            private_test_configurations[key] = value        
        test_config = private_test_configurations
    else:
        test_config = test_configurations()

    rc_values = test_config[test_name][0]
    resolutions = test_config[test_name][1]
    downscale_command_template = test_config[test_name][2]
    metric_command_template = test_config[test_name][3]
    encoding_command_template = test_config[test_name][4]            
        
    return rc_values, resolutions, downscale_command_template, metric_command_template, encoding_command_template
    
    
def get_first_pass_results():
    first_pass_results = dict()
    result_files = glob.glob('{}/*.txt'.format(os.getcwd()))
    for result_file in result_files:
        if 'result' in result_file:
            with open(result_file, mode='r') as csv_file:
                content = list(csv.DictReader(csv_file, delimiter='\t'))
                for index, row in enumerate(content):                
                    preset = row['ENC_NAME'].split('_M')[-1]
                    clip_name = row['INPUT_SEQUENCE']
                    rc_value = row['RC_VALUE']
                    bitrate = row['BITRATE']
                    first_pass_results.setdefault(preset, {}).setdefault(clip_name, {}).setdefault(rc_value, {})
                    first_pass_results[preset][clip_name][rc_value] = bitrate

    return first_pass_results


def configure_runs(test_name,rc_values):
    '''Process iterations if any are specified in the test name'''
    if TEST_SETTINGS['encode_iterations']:
        iterations = TEST_SETTINGS['encode_iterations']
    else:
        iterations = 1
        
    '''Parse the VBR ladder RC config if detected'''
    if isinstance(rc_values, dict):
        rc_values = [[resolution, tbr] for resolution in rc_values for tbr in rc_values[resolution]]
    return iterations, rc_values
    


'''   Core Sample Command processing functions  '''
def process_command_template(test_name, cvh_data = None, cvh_metric = None):
    generated_commands = {}
    encode_commands = []
    metric_commands = []
    decode_commands = []
    burner_commands = []
    
    copy_commands = None
    downscale_commands = None
    resolution = None
    rawvideo = 'rawvideo'
    vmaf_pixfmt = '420'
    bitstream_folder = 'bitstreams'
    ffmpeg_path = '{}/ffmpeg'.format(TEST_SETTINGS['tools_folder'])
    
    '''Pull test info from Test repo'''
    rc_values, scaling_resolutions, downscale_command_template, metric_command_template, encoding_command_template = get_configs(test_name)
    
    '''Configure for multi-iteration, 2nd pass cvh naming, and VBR ladder configs'''
    iterations, rc_values = configure_runs(test_name,rc_values)
    
    '''If a results file exists in the current director, use that as a basis for all non-cvh second pass tests'''
    first_pass_results = get_first_pass_results()
    
    '''Insert a extra tokens for if specified in TEST_SETTINGS'''
    encoding_command_template = insert_special_parameters(encoding_command_template)
    
    encoder_executable_found = re.search(r'\s*\.\/(.*?)\s', encoding_command_template)
    if encoder_executable_found:
        encoder_exe = encoder_executable_found.group(1)
    else:
        encoder_exe = None
    if not TEST_SETTINGS['presets']:
        print('[ERROR!]: No presets specified. Exitting')
        sys.exit()
        
    if cvh_metric:
        bitstream_folder = '{}_{}'.format(bitstream_folder, cvh_metric)
        test_name = '{}_{}'.format(test_name, cvh_metric)         
                    
    for preset in TEST_SETTINGS['presets']:
        vvenc_presets = ["slower", "slow", "medium", "fast", "faster"]
        count = 0
        '''Set the vvenc presets according to the preset number'''
        if str(preset).isdigit() and int(preset) < 4:
            vvenc_preset = vvenc_presets[int(preset)]
        else:
            vvenc_preset = "faster"
                            
        per_preset_encode_commands = []
        per_preset_metric_commands = []
        per_preset_decode_commands = []
        per_preset_burner_commands = []
        
        '''Sort the clips so that the encodings will start with the bottlenecks'''
        clip_lists = sort_clip_list_by_complexity(TEST_SETTINGS['stream_dir'])
        

        if scaling_resolutions:
            copy_commands, downscale_commands, clip_lists, parameter_tracker = get_downscaled_clip_list(clip_lists, scaling_resolutions, downscale_command_template)
        encode_splitter = 0
        
        for clip in clip_lists:
            for rc_value in rc_values:
                for iteration in range(iterations):
                    '''Retrieve the relevant parameters for the given clip'''
                    if clip.endswith('yuv') and scaling_resolutions:
                        width, height, width_x_height, fps_num, fps_denom, bitdepth, number_of_frames, fps_ratio, fps_decimal, vvenc_pixel_format, pixel_format = parameter_tracker[clip]
                    elif clip.endswith('y4m') and scaling_resolutions:
                        width, height, framerate, number_of_frames,target_width = parameter_tracker[clip]
                    elif clip.endswith('yuv') and yuv_library_found:
                        width, height, width_x_height, fps_num, fps_denom, bitdepth, number_of_frames, fps_ratio, fps_decimal, vvenc_pixel_format, pixel_format = get_YUV_PARAMS(clip)
                    elif clip.endswith('y4m') and encoder_exe == 'SvtAv1EncApp':
                        width = height = framerate = number_of_frames = ''
                        pass
                    elif clip.endswith('y4m'):
                        width, height, framerate, number_of_frames = read_y4m_header(clip)
                    else:
                        print('[Warning]: Skipping Clip: {}'.format(clip))
                        continue

                    clip_name = os.path.split(clip)[-1].replace('.y4m','').replace('.yuv','')                            
                    preset, rc_value, skip, resolution = filter_encodings(test_name, rc_value, width, height, clip_name, resolution, cvh_data, cvh_metric, preset, first_pass_results, scaling_resolutions)

                    # if rc_value > 51 and ('x264' in test_name or 'x265' in test_name):
                        # print('\n\n[ERROR!]: x264/x265 do not support rc values greater than 51. Please change your RC value settings. Exitting...\n\n')
                        # sys.exit()
                    '''SKip certain encodings according to different testing conditions'''
                    if skip:
                        continue
                        
                    # if 'xyz_preset' in TEST_SETTINGS:
                        # preset, _ = get_xyz_ladder_config(test_name, preset)
                        
                    if (encode_splitter % 2 == 0):
                       renderX = 'renderD128'
                    else:
                       renderX = 'renderD129'
                    encode_splitter += 1
                    preset = str(preset).replace('M','')
                    bufsize_value = 2.5*float(rc_value)
                    bufsize_value_cbr = 1*float(rc_value)         
                    '''Set the intraperiod to +1 number of frames for encoders that do not support -1 keyint'''
                    if 'SvtAv1EncApp' not in encoding_command_template and str(TEST_SETTINGS['intraperiod']) == '-1':
                        intraperiod = number_of_frames + 1
                    else:
                        intraperiod = TEST_SETTINGS['intraperiod']

                    '''Set the pixfmt according to the bitdepth'''
                    if clip.endswith('yuv'):
                        if bitdepth == 10:
                            pixfmt = "yuv420p10le"
                            vvenc_pixfmt = 'yuv420_10'
                        else:
                            pixfmt = "yuv420p"
                            vvenc_pixfmt = 'yuv420'

                    if scaling_resolutions:
                        '''Get reference clip resolution for the rescale case'''
                        scaling_found = re.search(r'(\d+)x(\d+)to(\d+)x(\d+)', clip)

                        if scaling_found:
                            ref_width = scaling_found.group(1)
                            ref_height = scaling_found.group(2)
                            mod_width = scaling_found.group(3)
                            mod_height = scaling_found.group(4)
                            ref_clip = re.sub('to\\d+x\\d+', '', clip)
                        else:
                            ref_width = mod_width = width
                            ref_height = mod_height = height
                            ref_clip = clip

                    '''Generic setup of parameters and conditionals'''
                    clip_name = os.path.split(clip)[1]
                    
                    if 'xyz_preset' in TEST_SETTINGS:
                        preset_name = TEST_SETTINGS['xyz_preset']
                    else:
                        preset_name = preset
                    
                    encoder = encoding_command_template.split('./')[1].split(' ')[0].strip()
                    if TEST_SETTINGS['single_cmd_files']:
                        output_filename = '{}/{}_M$1_{}_RC{}'.format(bitstream_folder,encoder, clip_name[:-4], rc_value)
                        encoding_command_template = encoding_command_template.replace('{preset}','$1')
                    else:
                        output_filename = '{}/{}_M{}_{}_RC{}'.format(bitstream_folder,encoder, preset_name,clip_name[:-4], rc_value)

                    '''Append iteration index to file name if the current iteration is > 0'''
                    if iteration > 0:
                    
                        output_filename = "{}-{}".format(output_filename, int(iteration))
                        
                    '''remove yuv tokens in case of y4m clip'''
                    if clip.endswith('y4m'):
                        encode_command = remove_yuv_tokens(encoding_command_template)
                        metric_command = remove_yuv_tokens(metric_command_template)
                    elif clip.endswith('yuv'):
                        encode_command = encoding_command_template
                        metric_command = metric_command_template

                    '''temp clip for temporary decoding cases'''
                    temp_clip = '/dev/shm/{}.{}'.format(output_filename, clip[-3:])
                    '''Fill Encode Commands'''
                    encode_command = encode_command.format(**vars())
                    '''Fill Metric Command'''
                    metric_command = metric_command.format(**vars())

                    if TEST_SETTINGS['generate_decode_times']:
                        decode_command = generate_decode_commands(output_filename)
                        per_preset_decode_commands.append(decode_command)

                    dummy_metric = 'echo "This is solely for generating a log id file for the encoding" > {}.log'.format(output_filename)
                    
                    if TEST_SETTINGS['do_not_generate_metrics']:
                        metric_command = dummy_metric
                   
                    if TEST_SETTINGS['live_encode']:
                        sequence_name = re.search(r'M-?h?\$1_*(.*?)_*RC(\d+)-?\d?', output_filename).group(1)
                        root_search = re.search(r"(.*?)_\d+x\d+", sequence_name)
                        if root_search:
                            root_sequence_name = root_search.group(1)
                        else:
                            root_sequence_name = sequence_name
                        if 'xyz_preset' in TEST_SETTINGS:
                            live_encodes.setdefault(TEST_SETTINGS['xyz_preset'], {}).setdefault(root_sequence_name, []).append(encode_command)
                            live_metrics.setdefault(TEST_SETTINGS['xyz_preset'], []).setdefault(root_sequence_name, []).append(metric_command)

                        else:
                            live_encodes.setdefault(preset, {}).setdefault(root_sequence_name, []).append(encode_command)
                            live_metrics.setdefault(preset, {}).setdefault(root_sequence_name, []).append(metric_command)


                    if not TEST_SETTINGS['live_encode']:
                        per_preset_encode_commands.append(encode_command)  
                        if iteration == 0:
                            per_preset_metric_commands.append(metric_command)
                            per_preset_burner_commands.append(encode_command)
                        else:
                            per_preset_metric_commands.append(dummy_metric)                         
                   
        if TEST_SETTINGS['live_encode']:
            if 'xyz_preset' in TEST_SETTINGS:
                preset = TEST_SETTINGS['xyz_preset']
            for sequence in live_encodes[preset]:
                sub_commands = live_encodes[preset][sequence]
                sub_metrics  = live_metrics[preset][sequence]
                per_preset_metric_commands.extend(sub_metrics)
                
                if TEST_SETTINGS['live_bash_execution']:
                    encode_command = ' & '.join(sub_commands)
                    encode_command = encode_command.replace('(','').replace(')','')
                    encode_command = '({} & wait)'.format(encode_command)
                    per_preset_encode_commands.append(encode_command)
                else:
                    per_preset_encode_commands.extend(sub_commands)
                    


        encode_commands.append(per_preset_encode_commands)
        metric_commands.append(per_preset_metric_commands)
        decode_commands.append(per_preset_decode_commands)
        burner_commands.append(per_preset_burner_commands)

    generated_commands['encode_commands']    = encode_commands
    generated_commands['metric_commands']    = metric_commands
    if copy_commands:
        generated_commands['copy_commands']      = copy_commands
        generated_commands['downscale_commands'] = downscale_commands
    else:
        generated_commands['copy_commands']      = []
        generated_commands['downscale_commands'] = []    
    generated_commands['decode_commands']    = decode_commands
    generated_commands['burner_commands']    = burner_commands

    '''Write the important parameters to a log to act as a double checking mechanism'''
    write_parameters(test_name, rc_values, scaling_resolutions, downscale_command_template, encoding_command_template, metric_command_template)
    
    return generated_commands


def get_downscaled_clip_list(clip_lists, downscale_target_resolutions, downscale_command_template):
    downscaled_clip_map = dict()
    parameter_tracker = dict()
    downscaled_clip_list = list()
    copy_commands = list()
    downscale_commands = list()
    rawvideo = 'rawvideo'
    fps = '30000/1001'
    ffmpeg_path = '{}/ffmpeg'.format(TEST_SETTINGS['tools_folder'])
    # resolution_id = list(RESOLUTION.keys())[list(RESOLUTION.values()).index(downscale_target_resolutions)]
    
    for clip in clip_lists:
        if clip.endswith('yuv') and yuv_library_found:
            width, height, width_x_height, fps_num, fps_denom, bitdepth, number_of_frames, fps_ratio, fps_decimal, vvenc_pixel_format, pixel_format = get_YUV_PARAMS(clip)
        elif clip.endswith('y4m'):
            width, height, framerate, number_of_frames = read_y4m_header(clip)
        else:
            print('[Warning]: Skipping Clip: {}'.format(clip))
            continue
        source_width = width
        source_height = height
        '''Assign the pixel format variable based on bitdepth'''
        if clip.endswith('yuv'):
            if bitdepth == 10:
                pixfmt = "yuv420p10le"
            else:
                pixfmt = "yuv420p"

        '''remove yuv tokens in case of y4m clip'''
        if clip.endswith('y4m'):
            cleaned_downscale_command_template = remove_yuv_tokens(downscale_command_template)
        else:
            cleaned_downscale_command_template = downscale_command_template
            
        if isinstance(downscale_target_resolutions, dict):
            source_resolutions = []

            for source_resolution in downscale_target_resolutions:
                source_resolutions.append(source_resolution.split('x'))
        else:
            source_resolutions = [[width,height]]
            
        for source_resolution in source_resolutions:
            width = source_resolution[0]
            height = source_resolution[1]

            resized_clips_folder = os.path.join(TEST_SETTINGS['stream_dir'], 'resized_clips')

            '''Assign target path for source and scaled clip'''
            resized_clip = os.path.join(resized_clips_folder, os.path.split(clip)[-1])

            '''Remove widthxheight occurences from clip name to avoid detection issues'''
            resized_clip = re.sub(r'\d+x\d+', '', resized_clip).replace('__', '_')

            '''Append source resolution to end of clip'''
            ref_clip = resized_clip[:-4] + '_{source_width}x{source_height}'.format(**vars()) + resized_clip[-4:]
            
            '''Create copy command'''
            if str(width) == str(source_width) and str(height) == str(source_height):
                copy_command = 'cp {clip} {ref_clip}'.format(**vars())
                copy_commands.append(copy_command)
            else:
                #If the source clip is diff resoltuion than the targetted new source, we need to downscale it instead of copying
                target_width = width
                target_height = height
                ref_clip = clip
                scaled_clip_name = resized_clip[:-4] + '_{target_width}x{target_height}'.format(**vars()) + resized_clip[-4:]
                copy_commands.append(cleaned_downscale_command_template.format(**vars()))
                ref_clip = scaled_clip_name

            '''Check if resolution is in dict'''
            if "{width}x{height}".format(**vars()) not in downscaled_clip_map:
                downscaled_clip_map["{width}x{height}".format(**vars())] = [ref_clip]
            else:
                downscaled_clip_map["{width}x{height}".format(**vars())].append(ref_clip)
                
            if isinstance(downscale_target_resolutions, dict):
                target_resolutions = downscale_target_resolutions['{}x{}'.format(width,height)]
            else:
                target_resolutions = downscale_target_resolutions
                
            for target_width, target_height in target_resolutions:

                if int(target_width) >= int(width) and int(target_height) >= int(height):
                    continue

                '''Name of output downscaled clip'''
                scaled_clip_name = resized_clip[:-4] + '_{width}x{height}to{target_width}x{target_height}'.format(**vars()) + resized_clip[-4:]

                if "{target_width}x{target_height}".format(**vars()) not in downscaled_clip_map:
                    downscaled_clip_map["{target_width}x{target_height}".format(**vars())] = [scaled_clip_name]
                else:
                    downscaled_clip_map["{target_width}x{target_height}".format(**vars())].append(scaled_clip_name)
                
                #Need to set the ref clip back to its original source so we dont scale using an already dowcsaled clip
                ref_clip = clip
                
                '''Fill in downscale template'''
                downscale_command = cleaned_downscale_command_template.format(**vars())
                ref_clip = resized_clip[:-4] + '_{width}x{height}'.format(**vars()) + resized_clip[-4:]
                '''Keep track of parameters of downscaled clips'''
                if resized_clip.endswith('yuv'):
                    parameter_tracker[scaled_clip_name] = [target_width, target_height, width_x_height, fps_num, fps_denom, bitdepth, number_of_frames, fps_ratio, fps_decimal, vvenc_pixel_format, pixel_format]
                    parameter_tracker[ref_clip] = [width, height, width_x_height, fps_num, fps_denom, bitdepth, number_of_frames, fps_ratio, fps_decimal, vvenc_pixel_format, pixel_format]
                if resized_clip.endswith('y4m'):
                    parameter_tracker[scaled_clip_name] = [target_width, target_height, framerate, number_of_frames,target_width]
                    parameter_tracker[ref_clip] = [width, height, framerate, number_of_frames,width]

                downscale_commands.append(downscale_command)

    key_list = sorted(downscaled_clip_map.keys(), key=lambda k: int(k.split("x")[0]) * int(k.split("x")[1]), reverse=True)

    for target_res in key_list:
        downscaled_clip_list.extend(downscaled_clip_map[target_res])
        
    return copy_commands, downscale_commands, downscaled_clip_list, parameter_tracker

encoder_bash_files = []
metric_file_ids = {}
presetss = []


def generate_bash_driver_file(encode_file_id, metric_file_id, decode_file_id, burner_file_id, test_name,  cvh_metric = None):
    rc_values, resolutions, downscale_command_template, metric_command_template, encoding_command_template = get_configs(test_name)
    resized_clips_folder = os.path.join(TEST_SETTINGS['stream_dir'], 'resized_clips')
    encoder_executable_found = re.search(r'\s*\.\/(.*?)\s', encoding_command_template)
    group_type = None
    
    if 'xyz_preset' in TEST_SETTINGS:
        from xyz_presets import get_presets
        
        xyz_preset = TEST_SETTINGS['xyz_preset']
        if cvh_metric and TEST_SETTINGS['cvh_metric'][cvh_metric]:
            for test_group in get_presets()[cvh_metric][xyz_preset]:
                if test_name in get_presets()[cvh_metric][xyz_preset][test_group]:
                    group_type = test_group
                    
    if encoder_executable_found:
        encoder_exec = encoder_executable_found.group(1)
        bash_id = encoder_exec       
    else:
        print("Warning encoder executable not specified in bash script")
        
    if group_type:
        bash_id = group_type
        TEST_SETTINGS['presets'] = [xyz_preset]
       
    if TEST_SETTINGS['live_encode']:
        bash_id = 'live_encode'
    
    run_all_paral_file_name = 'run-{}.sh'.format(bash_id)

    if cvh_metric:
        run_all_paral_file_name = '{}_{}.sh'.format(run_all_paral_file_name[:-3], cvh_metric)
        time_id = 'time_{}'.format(cvh_metric)
    else:
        time_id = 'time'
        
    run_all_paral_filepath = os.path.join(os.getcwd(), run_all_paral_file_name)
    
    if TEST_SETTINGS['run_encoders_in_parallel']:
        if cvh_metric:
            run_parallel_encoders_name = 'run_in_parallel_{}.sh'.format(cvh_metric)
        else:
            run_parallel_encoders_name = 'run_in_parallel.sh'
        
        encoder_bash_files.append(run_all_paral_file_name)
        metric_file_ids[metric_file_id] = "presets=({})".format(' '.join(map(str, TEST_SETTINGS['presets'])))
        presetss.append("presets=({})".format(' '.join(map(str, TEST_SETTINGS['presets']))))
        run_parallel_encoders = []
        
    run_all_paral_script = []
    run_all_paral_script.append("#!/bin/bash")
    run_all_paral_script.append("presets=({})".format(' '.join(map(str, TEST_SETTINGS['presets']))))
    
    if cvh_metric:
        bitstream_folder = 'bitstreams_{}'.format(cvh_metric)
    else:
        bitstream_folder = 'bitstreams'
   
    run_all_paral_script.append('# Overwrite presets if any arguments are provided')

    run_all_paral_script.append('if [ "$#" -gt 0 ]; then')
    run_all_paral_script.append('  presets=("$@")')
    run_all_paral_script.append('fi')

    
    
    run_all_paral_script.append("mkdir {}".format(bitstream_folder))
    run_all_paral_script.append("rm -rf /dev/shm/bitstreams")    
    run_all_paral_script.append("mkdir /dev/shm/bitstreams")    
    run_all_paral_script.append("chmod +rx {}".format(TEST_SETTINGS['tools_folder']))
    run_all_paral_script.append("chmod +rx {}/*".format(TEST_SETTINGS['tools_folder']))
    run_all_paral_script.append("chmod +rx *.sh")
    run_all_paral_script.append("chmod +x {}".format(encoder_exec))

    if encoder_exec == 'vvencapp':
        run_all_paral_script.append("chmod +x vvdecapp")

    if TEST_SETTINGS['generate_decode_times']:
        run_all_paral_script.append("mkdir {}".format('decode_log_bitstreams/'))

    if resolutions:
        if TEST_SETTINGS['run_encoders_in_parallel']:
            run_parallel_encoders.append("#!/bin/bash")
            run_parallel_encoders.append("rm -rf {resized_clips_folder}".format(**vars()))
            run_parallel_encoders.append("mkdir {resized_clips_folder}".format(**vars()))
            run_parallel_encoders.append("parallel -j {} < cli-copy_clips.txt".format(TEST_SETTINGS['number_of_parallel_metrics']))
            run_parallel_encoders.append("(/usr/bin/time --verbose parallel -j {} < cli-downscale.txt) &> time_downscale.log".format(TEST_SETTINGS['number_of_parallel_metrics']))
            run_parallel_encoders.append("echo \'Downscaling Finished\'")
        else:
            run_all_paral_script.append("rm -rf {resized_clips_folder}".format(**vars()))
            run_all_paral_script.append("mkdir {resized_clips_folder}".format(**vars()))
            run_all_paral_script.append("parallel -j {} < cli-copy_clips.txt".format(TEST_SETTINGS['number_of_parallel_metrics']))
            run_all_paral_script.append("(/usr/bin/time --verbose parallel -j {} < cli-downscale.txt) &> time_downscale.log".format(TEST_SETTINGS['number_of_parallel_metrics']))
            run_all_paral_script.append("echo \'Downscaling Finished\'")
            
    '''Add burner run'''
    if TEST_SETTINGS['add_encoding_burner_run']:
        run_all_paral_script.append("for i in \"${presets[@]}\"; do")
        run_all_paral_script.append("\techo \'Running M\'$i \'Burner run\'")
        if TEST_SETTINGS['single_cmd_files']:
            run_all_paral_script.append('\t(/usr/bin/time --verbose parallel -j {} < <(sed "s/\$1/$i/g" {}.txt)) &> {}_burner_$i.log'.format(TEST_SETTINGS['number_of_parallel_encodes'],burner_file_id, time_id))
        else:
            run_all_paral_script.append("\t(/usr/bin/time --verbose parallel -j {} < {}-m$i.txt) &> {}_burner_$i.log".format(TEST_SETTINGS['number_of_parallel_encodes'], burner_file_id, time_id))
        run_all_paral_script.append("\techo \'Encoding Burner for Encode Mode \'$i\' Finished\'")
        run_all_paral_script.append("done")
        
    '''Encoding Loop'''
    run_all_paral_script.append("for i in \"${presets[@]}\"; do")
    run_all_paral_script.append("\techo \'Running M\'$i \'Encodings\'")
   
    if TEST_SETTINGS['single_cmd_files']:
        run_all_paral_script.append('\t(/usr/bin/time --verbose parallel -j {} < <(sed "s/\$1/$i/g" {}.txt)) &> {}_encode_$i.log'.format(TEST_SETTINGS['number_of_parallel_encodes'], encode_file_id, time_id))        
    else:
        run_all_paral_script.append("\t(/usr/bin/time --verbose parallel -j {} < {}-m$i.txt) &> {}_encode_$i.log".format(TEST_SETTINGS['number_of_parallel_encodes'], encode_file_id, time_id))
  
    if not TEST_SETTINGS['run_encoders_in_parallel']:
        '''Metric Loop'''
        run_all_paral_script.append("\techo \'Running M\'$i \'Metrics\'")
    
        if TEST_SETTINGS['single_cmd_files']:
            run_all_paral_script.append('\t(/usr/bin/time --verbose parallel -j {} < <(sed "s/\$1/$i/g" {}.txt)) &> {}_metric_$i.log'.format(TEST_SETTINGS['number_of_parallel_metrics'], metric_file_id, time_id))                
        else:
            run_all_paral_script.append("\t(/usr/bin/time --verbose parallel -j {} < {}-m$i.txt) &> {}_metric_$i.log".format(TEST_SETTINGS['number_of_parallel_metrics'], metric_file_id, time_id))
    
    if not TEST_SETTINGS['run_encoders_in_parallel']:
        run_all_paral_script.append("\tpython3 collect_results.py")

    run_all_paral_script.append("\techo \'Encode Mode \'$i\' Finished\'")
    run_all_paral_script.append("done")
    
    if TEST_SETTINGS['generate_decode_times']:
        run_all_paral_script.append("for i in \"${presets[@]}\"; do")
        run_all_paral_script.append("\techo \'Running M\'$i \'Decodings\'")
        if TEST_SETTINGS['single_cmd_files']:
            run_all_paral_script.append('\t(/usr/bin/time --verbose parallel -j {} < <(sed "s/\$1/$i/g" {}.txt)) &> {}_decode_$i.log'.format(TEST_SETTINGS['number_of_parallel_encodes'], decode_file_id, time_id))                
            
        else:    
            run_all_paral_script.append("\t(/usr/bin/time --verbose parallel -j {} < {}-m$i.txt) &> {}_decode_$i.log".format(TEST_SETTINGS['number_of_parallel_decodes'], decode_file_id, time_id))
        run_all_paral_script.append("\techo \'Running ffmpeg decode for Encode Mode \'$i\' Finished\'")
        run_all_paral_script.append("done")

    if TEST_SETTINGS['run_encoders_in_parallel']:
        if 'xyz_preset' in TEST_SETTINGS or cvh_metric:      
            run_parallel_encoders.append("/usr/bin/time -v -o %s_encode_overall2.log bash -c '{" % time_id)
        else:
            run_parallel_encoders.append("/usr/bin/time -v -o %s_encode_overall1.log bash -c '{" % time_id)
            
        
        for index, encoder_bash in enumerate(sorted(list(set(encoder_bash_files)))):
            run_parallel_encoders.append('\t(/usr/bin/time -v -o {}_{}.log ./{}) &'.format(time_id, encoder_bash.replace('.sh',''),encoder_bash))
            run_parallel_encoders.append('\tpid{}=$!'.format(index))
            
        pids = ['$pid{}'.format(index) for index in range(len(sorted(list(set(encoder_bash_files)))))]
        
        run_parallel_encoders.append("wait {}".format(' '.join(pids)))
        run_parallel_encoders.append("}'")
        
        # print('metric_file_ids',metric_file_ids)
        
        for metric_file_id in metric_file_ids:
            presets = metric_file_ids[metric_file_id]
            run_parallel_encoders.append(presets)
            run_parallel_encoders.append("for i in \"${presets[@]}\"; do")
            run_parallel_encoders.append("\techo \'Running M\'$i \'Metrics\'")
            run_parallel_encoders.append("\t(/usr/bin/time --verbose parallel -j {} < {}-m$i.txt) &> {}_metric_$i.log".format(TEST_SETTINGS['number_of_parallel_metrics'], metric_file_id, time_id))
            run_parallel_encoders.append("echo \'Running metric commands for Encode Mode \'$i\' Finished\'")

            run_parallel_encoders.append("done")
                    
        run_parallel_encoders.append("python3 collect_results.py")
        '''Create the run-in-parallel file'''

        with open(run_parallel_encoders_name, 'w') as file:
            for line in run_parallel_encoders:
                file.write(line + '\n')
           
    '''Create the run-all-paral file'''
    with open(run_all_paral_filepath, 'w') as file:
        for line in run_all_paral_script:
            file.write(line + '\n')

    # chmoding bash files
    # NOTE: os.chmod is finicky -> may not work
    file_stat = os.stat(run_all_paral_filepath)
    os.chmod(run_all_paral_filepath, file_stat.st_mode | stat.S_IEXEC)
    
    if TEST_SETTINGS['run_encoders_in_parallel']:
    
        file_stat = os.stat(run_parallel_encoders_name)
        os.chmod(run_parallel_encoders_name, file_stat.st_mode | stat.S_IEXEC)

    spawn_all = '''#!/bin/bash
#sudo sysctl -w kernel.sched_rt_runtime_us=990000
sed -i 's/\\r$//' *.sh 
sed -i 's/\\r$//' *.txt
for folder in ./*/;
do
	cd $folder

	name=$(echo $folder | cut -d'/' -f 2)
	echo $name
	cp ../*.sh .
	cp ../*.txt .
	cp ../*.py .
	./{}

	cd ..	

done

more ./*/*.log | cat
'''.format(run_all_paral_file_name)
    spawn_all_filepath = os.path.join(os.getcwd(), 'spawn_all.sh')

    with open(spawn_all_filepath,'w') as output:
        output.write(spawn_all)
    os.chmod(spawn_all_filepath, file_stat.st_mode | stat.S_IEXEC)
        
    return run_all_paral_filepath


def remove_yuv_tokens(command_template):
    command_tokens = re.findall('\\s*\\S*\\s*{.*?}', command_template)

    for command_token in command_tokens:
        command_param = command_token.split('{')[-1].strip('}')

        if command_param in YUV_PARAMS:
            command_template = command_template.replace(command_token, '')

    return command_template


def write_parameters(test_name, rc_values, resolutions, downscale_command_template, encoding_command_template, metric_command_template):
    file_name = '.{}-parameters-{}.txt'.format(test_name, datetime.now().strftime("%Y-%m-%d_H%H-M%M-S%S"))
    file_path = os.path.join(os.getcwd(), file_name)
    
    with open(file_path, 'w') as file:
        file.write('test_name: {test_name}\n'.format(**vars()))
        file.write('rc_values: {rc_values}\n'.format(**vars()))
        file.write('resolutions: {resolutions}\n'.format(**vars()))
        file.write('downscale_command_template: {downscale_command_template}\n'.format(**vars()))
        file.write('encoding_command_template: {encoding_command_template}\n'.format(**vars()))
        file.write('metric_command_template: {metric_command_template}\n'.format(**vars()))
        file.write('insert_special_parameters: {}\n'.format(TEST_SETTINGS['insert_special_parameters']))


def merge_dicts_by_index(dict_list):
    merged_dict = {}
    for key in set().union(*dict_list):
        merged_lists = []
        for lists in zip(*(d.get(key, []) if isinstance(d.get(key), list) else [[d.get(key, None)]] for d in dict_list)):
            if all(isinstance(lst, list) for lst in lists):
                merged_list = [item for sublist in lists for item in sublist]
                merged_lists.append(merged_list)
            else:
                merged_lists.append(lists)
        merged_dict[key] = merged_lists
    return merged_dict


def write_commands_to_files(generated_commands,test_name, cvh_metric):  # Good
    rc_values, resolutions, downscale_command_template, metric_command_template, encoding_command_template = get_configs(test_name)
    group_type = None

    '''Get metric command dict name for file naming purposes'''
    if 'xyz_preset' in TEST_SETTINGS and os.path.isfile('xyz_presets.py'):
        from xyz_presets import get_presets
        
        xyz_preset = TEST_SETTINGS['xyz_preset']
        if cvh_metric and TEST_SETTINGS['cvh_metric'][cvh_metric]:
            for test_group in get_presets()[cvh_metric][xyz_preset]:
                if test_name in get_presets()[cvh_metric][xyz_preset][test_group]:
                    group_type = test_group
                    
    if group_type:
        TEST_SETTINGS['presets'] = [xyz_preset]
        
    if TEST_SETTINGS['live_encode']:
        if 'xyz_preset' in TEST_SETTINGS:
            TEST_SETTINGS['presets'] = [TEST_SETTINGS['xyz_preset']]
            

    encode_commands = generated_commands['encode_commands']
    metric_commands = generated_commands['metric_commands']
    copy_commands = generated_commands['copy_commands']
    downscale_commands = generated_commands['downscale_commands']
    decode_commands = generated_commands['decode_commands']
    burner_commands  = generated_commands['burner_commands']
    
    '''Define command file names according to their configuration name'''  
    if 'xyz_preset' in TEST_SETTINGS:
        encode_file_id = 'cli-encode_{}'.format(test_name)
        metric_file_id = 'cli-metric_{}'.format(test_name)
        decode_file_id = 'cli-decode_{}'.format(test_name)
        burner_file_id = 'cli-burner_{}'.format(test_name)
    else:
        encode_file_id = 'cli-encode'
        metric_file_id = 'cli-metric'
        decode_file_id = 'cli-decode'
        burner_file_id = 'cli-burner'
    
        
    '''Write Encode and metric Commands'''
    for preset, encode_commands, metric_commands in zip(TEST_SETTINGS['presets'], encode_commands, metric_commands):
        
        if TEST_SETTINGS['single_cmd_files']:
            if cvh_metric:
                '''Define command file names according to their configuration name'''
                encode_file_id = 'encodes_{}'.format(cvh_metric)
                metric_file_id = 'metrics_{}'.format(cvh_metric)
                decode_file_id = 'decodes_{}'.format(cvh_metric)
                burner_file_id = 'burns_{}'.format(cvh_metric)
                
             
            else:
                encode_file_id = 'encodes'
                metric_file_id = 'metrics'
                decode_file_id = 'decodes'
                burner_file_id = 'burns'
                
            encode_filename = '{}.txt'.format(encode_file_id)
            metric_filename = '{}.txt'.format(metric_file_id)

        else:
            encode_filename = '{}-m{}.txt'.format(encode_file_id, preset)
            metric_filename = '{}-m{}.txt'.format(metric_file_id, preset)
            
        encode_filepath = os.path.join(os.getcwd(),encode_filename)
        metric_filepath = os.path.join(os.getcwd(),metric_filename)
        
        with open(encode_filepath, 'w') as encode_file,\
             open(metric_filepath, 'w') as metric_file:
                 
            for command in encode_commands:
                encode_file.write('{}\n'.format(command))
            for command in metric_commands:
                metric_file.write('{}\n'.format(command))
                
    '''Write burner commands'''
    if any(burner_commands) and TEST_SETTINGS['add_encoding_burner_run']:
        for preset, burner_commands in zip(TEST_SETTINGS['presets'], burner_commands):
            if TEST_SETTINGS['single_cmd_files']:
                burner_filename = 'burns.txt'
            else:
                burner_filename = '{}-m{}.txt'.format(burner_file_id, preset)
            burner_filepath = os.path.join(os.getcwd(),burner_filename)
    
            with open(burner_filepath, 'w') as burner_file:
                for command in burner_commands:
                    burner_file.write('{}\n'.format(command))  
                    
    '''Write Decode commands'''
    if any(decode_commands):
        for preset, decode_commands in zip(TEST_SETTINGS['presets'], decode_commands):
            if TEST_SETTINGS['single_cmd_files']:
                decode_filename = 'decodes.txt'
            else:
                decode_filename = '{}-m{}.txt'.format(decode_file_id, preset)
            decode_filepath = os.path.join(os.getcwd(),decode_filename)
    
            with open(decode_filepath, 'w') as decode_file:
                for command in decode_commands:
                    decode_file.write('{}\n'.format(command))
                    
    if any(copy_commands) and any(downscale_commands):
        copy_filename = 'cli-copy_clips.txt'
        copy_filepath = os.path.join(os.getcwd(),copy_filename)

        downscale_filename = 'cli-downscale.txt'
        downscale_filepath = os.path.join(os.getcwd(),downscale_filename)
                
        '''Write Scaling commands'''
        with open(copy_filepath, 'w') as copy_file,\
             open(downscale_filepath, 'w') as downscale_file:
                 
            for command in copy_commands:
                copy_file.write('{}\n'.format(command[0]))
                
            for command in downscale_commands:
                downscale_file.write('{}\n'.format(command[0]))

    return encode_file_id, metric_file_id, decode_file_id, burner_file_id


def insert_special_parameters(encoding_command_template):
    if not TEST_SETTINGS['insert_special_parameters']:
        return encoding_command_template
        
    sub_string_first_half = encoding_command_template.rpartition('-i')[0]
    sub_string_second_half = encoding_command_template.rpartition('-i')[2]

    for param in TEST_SETTINGS['insert_special_parameters']:
        sub_string_first_half += param + " "

    sample_command = sub_string_first_half + "-i" + sub_string_second_half
    return sample_command


def generate_decode_commands(input_bin):  # Good
    decode_command_template = "/usr/bin/time --verbose bash -c ' %s ' > %s.log 2>&1"

    threads_per_decode = TEST_SETTINGS['threads_per_decode']

    ffmpeg_path = '{}/ffmpeg'.format(TEST_SETTINGS['tools_folder'])
    # Generate individual decode commands for each input bin file
    decode_commands = "for i in {1..%s}; do %s -threads %s -i %s.bin -f null -; done" % (TEST_SETTINGS['decode_iterations'],ffmpeg_path,threads_per_decode,input_bin )

    # Extract the stream name from the input_bin variable
    stream_name = os.path.split(input_bin)[-1]

    # Format the combined decode command into the final command
    output_decode_log = os.path.join('decode_log_bitstreams', stream_name)
    decode_command = decode_command_template % (decode_commands, output_decode_log)

    return decode_command

'''Two functions to extract clip info from its y4m header'''
def read_y4m_header_helper(readByte, buffer):
    if sys.version_info[0] == 3:
        if (readByte == b'\n' or readByte == b' '):
            clip_parameter = buffer
            buffer = b""
            return clip_parameter, buffer
        else:
            buffer += readByte
            return -1, buffer
    else:
        if (readByte == '\n' or readByte == ' '):
            clip_parameter = buffer
            buffer = ""
            return clip_parameter, buffer
        else:
            buffer += readByte
            return -1, buffer


def read_y4m_header(clip):
    if sys.version_info[0] == 3:
        header_delimiters = {b"W": 'width', b"H": 'height', b"F": 'frame_ratio', b"I": 'interlacing', b"A": 'pixel_aspect_ratio', b"C": 'bitdepth'}
    else:
        header_delimiters = {"W": 'width', "H": 'height', "F": 'frame_ratio', "I": 'interlacing', "A": 'pixel_aspect_ratio', "C": 'bitdepth'}

    y4m_params = {'width': -1,
                  'height': -1,
                  'frame_ratio': -1,
                  'framerate': -1,
                  'number_of_frames': 1,
                  'bitdepth': -1
                  }

    with open(clip, "rb") as f:
        f.seek(10)

        if sys.version_info[0] == 3:
            buffer = b""
        else:
            buffer = ""

        while True:
            readByte = f.read(1)
            if (readByte in header_delimiters.keys()):
                y4m_key = readByte
                while True:
                    readByte = f.read(1)

                    '''Use helper function to interpret byte'''
                    y4m_params[header_delimiters[y4m_key]], buffer = read_y4m_header_helper(readByte, buffer)

                    if y4m_params[header_delimiters[y4m_key]] != -1:
                        break

            if sys.version_info[0] == 3:
                if binascii.hexlify(readByte) == b'0a':
                    break
            else:
                if binascii.hexlify(readByte) == '0a':
                    break

        if sys.version_info[0] == 3:
            frame_ratio_pieces = y4m_params['frame_ratio'].split(b":")
            if b'10' in y4m_params['bitdepth']:
                frame_length = int(float(2) * float(int(y4m_params['width']) * int(y4m_params['height']) * float(3) / 2))
                y4m_params['bitdepth'] = '10bit'
            else:
                frame_length = int(int(y4m_params['width']) * int(y4m_params['height']) * float(3) / 2)
                y4m_params['bitdepth'] = '8bit'
        else:
            frame_ratio_pieces = y4m_params['frame_ratio'].split(":")
            if '10' in y4m_params['bitdepth']:
                frame_length = int(float(2) * float(int(y4m_params['width']) * int(y4m_params['height']) * float(3) / 2))
                y4m_params['bitdepth'] = '10bit'
            else:
                frame_length = int(int(y4m_params['width']) * int(y4m_params['height']) * float(3) / 2)
                y4m_params['bitdepth'] = '8bit'

        y4m_params['framerate'] = float(frame_ratio_pieces[0]) / float(frame_ratio_pieces[1])

        while f.tell() < os.path.getsize(clip):
            readByte = f.read(1)
            if binascii.hexlify(readByte) == b'0a':
                f.seek(frame_length, 1)
                buff = binascii.hexlify(f.read(5))
                if buff == b'4652414d45':
                    y4m_params['number_of_frames'] += 1

    return int(y4m_params['width']), int(y4m_params['height']), y4m_params['framerate'], y4m_params['number_of_frames']


'''functions to get clip info'''
def get_fps(clipdir, clip):
    clip = os.path.split(clip)[-1]
    if(".yuv" in clip and yuv_library_found):
        seq_table_index = get_seq_table_loc(seq_list, clip)
        if seq_table_index < 0:
            return 0
        fps = float(seq_list[seq_table_index]["fps_num"]) / seq_list[seq_table_index]["fps_denom"]
        return fps
    elif(".y4m" in clip):
        _, _, framerate, number_of_frames = read_y4m_header(os.path.join(clipdir, clip))
        return framerate
    else:
        return 0


def get_seq_table_loc(seq_table, clip_name):
    for i in range(len(seq_table)):
        if seq_table[i]["name"] == clip_name[:-4]:
            return i
    print('{} not found in yuvb library. Exiting...'.format(clip_name))
    sys.exit()


def get_YUV_PARAMS(clip):
    clip_name = os.path.split(clip)[-1]
    seq_table_index = get_seq_table_loc(seq_list, clip_name)

    bitdepth = seq_list[seq_table_index]['bitdepth']
    ten_bit_format = seq_list[seq_table_index]['unpacked']
    width = seq_list[seq_table_index]['width']
    height = seq_list[seq_table_index]['height']
    width_x_height = '%sx%s' % (width, height)
    fps_num = int(seq_list[seq_table_index]['fps_num'])
    fps_denom = int(seq_list[seq_table_index]['fps_denom'])

    if (bitdepth == 8):
        number_of_frames = (int)(os.path.getsize(clip) / (width * height + (width * height / 2)))
        pixel_format = 'yuv420p'
        vvenc_pixel_format = 'yuv420'
    elif (bitdepth == 10):
        pixel_format = 'yuv420p10le'
        vvenc_pixel_format = 'yuv42010'  # Not sure what the real one is
        if ten_bit_format == 2:
            number_of_frames = (int)(((float)(os.path.getsize(clip)) / (width * height + (width * height / 2))) / 1.25)
        else:
            number_of_frames = (int)(((os.path.getsize(clip)) / (width * height + (width * height / 2))) / 2)

    return width, height, width_x_height, fps_num, fps_denom, bitdepth, number_of_frames, '%s/%s' % (fps_num, fps_denom), float(float(fps_num) / float(fps_denom)), vvenc_pixel_format, pixel_format


def sort_clip_list_by_complexity(input_folder):
    files = glob.glob('%s/*' % input_folder)

    '''For the case where the key being sorted are identical, perform sub-sorts base on the preceding sorts.'''
    files.sort(key=lambda f: get_fps(input_folder, f), reverse=True)
    files.sort(key=lambda f: f.lower())
    files.sort(key=lambda f: (os.stat(os.path.join(input_folder, f)).st_size), reverse=True)
    Y4M_HEADER_SIZE = 80

    '''Group sorted clips into nested lists based on filesize'''
    clip_lists = []
    clip_list = []
    size_0 = os.stat(os.path.join(input_folder, files[0])).st_size
    for file_ in files:
        if (file_.endswith('yuv') or file_.endswith('y4m')):
            if file_.endswith('yuv') and os.stat(os.path.join(input_folder, file_)).st_size == size_0:
                clip_list.append(file_)
            elif file_.endswith('y4m') and size_0 - Y4M_HEADER_SIZE <= os.stat(os.path.join(input_folder, file_)).st_size <= size_0 + Y4M_HEADER_SIZE:
                clip_list.append(file_)
            else:
                clip_lists.extend(clip_list)
                clip_list = []
                size_0 = os.stat(os.path.join(input_folder, file_)).st_size
                clip_list.append(file_)
    clip_lists.extend(clip_list)

    return clip_lists

live_encodes = dict() 
live_metrics = dict()
if __name__ == '__main__':
    '''Import the YUV Library to assign parameters for YUV clips which have no embedded meta data'''
    try:
        from yuv_library import getyuvlist
        seq_list = getyuvlist()
        yuv_library_found = 1
    except ImportError:
        print("[WARNING!]: yuv_library not found, only generating commands for y4m files.\n")
        seq_list = []
        yuv_library_found = 0

    '''Python 2 input() doesnt accept strings, replace with raw_input for python 2 case'''
    try:
        input = raw_input
    except NameError:
        pass

    '''Initialize Parameter settings'''
    YUV_PARAMS = ['width', 'height', 'ref_width', 'mod_width', 'ref_height', 'mod_height', 'bitdepth', 'fps_num', 'fps_denom', 'fps', 'vvenc_pixfmt', 'rawvideo', 'pixfmt', 'vmaf_pixfmt', 'frames', 'fps_decimal']

    RESOLUTION = {
        'xilften': [(2560, 1440), (1920, 1080), (1280, 720), (960, 540), (768, 432), (608, 342), (480, 270), (384, 216), (2560, 1088), (1920, 816), (1280, 544), (960, 408), (748, 318), (588, 250), (480, 204), (372, 158)],
        'xilften_test': [(372, 158)],
        'SPIE2020_8bit': [(1920, 1080), (1280, 720), (960, 540), (640, 360), (480, 270)],
        'SPIE2020_10bit': [(1920, 1080), (1280, 720), (960, 540), (768, 432), (608, 342), (480, 270), (384, 216)],
        'SPIE2021_8bit': [(1920, 1080), (1280, 720), (960, 540), (768, 432), (640, 360), (512, 288), (384, 216), (256, 144)],
        'SPIE2021_8bit_skip_1080p': [(1280, 720), (960, 540), (768, 432), (640, 360), (512, 288), (384, 216), (256, 144)],
        
        'fast_testing_resolutions': [(384, 216), (256, 144)],
        'ffmpeg_svt' : [(720,1280),(576,1024),(432,768),(288,512)],

        'SPIE2021_8bit_vertical_horizontal_square': {'1920x1080' : [(1280, 720), (960, 540), (768, 432), (640, 360), (512, 288), (384, 216), (256, 144)],
                                                     '1080x1920' : [(720, 1280), (540, 960, ), (432, 768), (360, 640), (288, 512), (216, 384), (144, 256)],
                                                     '1080x1080' : [(720, 720), (540, 540), (432, 432), (360, 360), (288, 288), (216, 216), (144, 144)],},

        'SPIE2021_8bit_720p' : {'1280x720' : [(1280, 720), (960, 540), (768, 432), (640, 360), (512, 288), (384, 216), (256, 144)]},
        'SPIE2021_sub_360p': [(640, 360), (512, 288), (384, 216), (256, 144)],

        'M13_resolutions' : [(1920, 1080), (1280, 720), (832, 480), (640, 360), (416, 240)],

        'SPIE2021_8bit_reduced': [(1920, 1080), (1280,720), (960,544), (640,360), (480,272)],

    }

    RC_VALUES = {
        'SPIE2020_x264_x265': [14, 18, 22, 27, 32, 37, 42, 47, 51],
        'SPIE2020_svt_aom': [20, 26, 32, 37, 43, 48, 55, 59, 63],

        'SPIE2021_x264_x265': [19, 21, 23, 25, 27, 29, 31, 33, 35, 37, 41],
        'SPIE2021_svt_aom': [23, 27, 31, 35, 39, 43, 47, 51, 55, 59, 63],
        'SPIE2021_svt_aom_7qp': [39, 43, 47, 51, 55, 59, 63],

        'xilften_crf': [16, 20, 24, 28, 32, 36, 39, 43, 47, 51, 55, 59, 63],
        'generic_tbr': [5000, 4000, 3000, 2000],
        'fast_testing_qps': [50, 51],
        'ffmpeg_svt' : [36, 40, 44, 48, 52, 56],
        
        'svt_mr_testing' : [20,32,43,55,63],
        'webrtc': [75, 150, 300, 600],
        'webrtc_ultra_LD': [300, 600, 1200, 2400],
        'svt_rtc_low_tbrs': [100, 200, 300, 400, 500, 600, 700, 800],

        'vvenc_5qp' : [22, 27, 32, 42, 51],
        '5qp_preset_tuning' : [32,40,48,55,63],
        '7qp_preset_tuning' : [32,37,43,48,55,59,63],
        '11qp_preset_tuning' : [23, 27, 31, 35, 39, 43, 47, 51, 55, 59, 63],
        '20qp_preset_tuning' : [23, 27, 31, 35, 39, 43, 47, 51, 55, 59, 63, 24, 40, 44, 53, 54, 56, 57, 60, 61],
        
        'avm' : [110, 141, 172, 203, 234],
        'avm_11qp' : [110, 122, 134, 146, 158,170,182,194,206,218,230],

        'vvenc_11qp' :  [19, 21, 23, 25, 27, 29, 31, 33, 35, 37, 41],  
        
        'vbr_ladder' : {'1920x1080' : [6000,3000],
                        '1280x720' : [2000],
                        '960x544' : [900],
                        '856x480' : [300],
                        '640x360' : [150],
                        },

        # 'hw_ladder' : {'1920x1080' : [23, 27, 31, 35, 39, 43, 47, 51, 55]},
        
        'hw_ladder' : {'1920x1080' : [23, 27, 31, 35, 39, 43, 47, 51]},        
        
        'sw_ladder' : {'1920x1080' : [59, 63],
                        '1280x720' : [23, 27, 31, 35, 39, 43, 47, 51, 55, 59, 63],
                        '960x540' : [23, 27, 31, 35, 39, 43, 47, 51, 55, 59, 63],
                        '768x432' : [23, 27, 31, 35, 39, 43, 47, 51, 55, 59, 63],
                        '640x360' : [23, 27, 31, 35, 39, 43, 47, 51, 55, 59, 63],
                        '512x288' : [23, 27, 31, 35, 39, 43, 47, 51, 55, 59, 63],
                        '384x216' : [23, 27, 31, 35, 39, 43, 47, 51, 55, 59, 63],
                        '256x144' : [23, 27, 31, 35, 39, 43, 47, 51, 55, 59, 63],
                       
                        },
                        
        'even_qps' : [i for i in range(2,63,2)],
        'odd_qps' : [i for i in range(1,64,2)],
        'all_qps' : [i for i in range(1,64)],
        
        'contribution' : [1000,3000,8000,15000,25000],    

        'new_7qp_preset_tuning' : [42, 47, 51, 54, 57, 60, 63],
        
        'ctc_allintra_qps' : [15,23,31,39,47,55],
        'ctc_still_image_qps' : [15,23,31,39,47,55],
        'ctc_crf_ld_as_qps' : [23,31,39,47,55,63],

        'spie2021_reduced_qps' : [39, 44, 47, 52, 55, 59],

    }

    DOWNSCALE_COMMAND = {
        'SPIE2021_scaling': "{ffmpeg_path}  -y -f {rawvideo} -s:v {width}x{height} -pix_fmt {pixfmt} -r {fps} -i {ref_clip} -sws_flags lanczos+accurate_rnd+full_chroma_int -sws_dither none -param0 5  -strict -1 -f {rawvideo} -s:v {target_width}x{target_height} -pix_fmt {pixfmt} -r {fps} {scaled_clip_name}",
        'SPIE2020_scaling': "{ffmpeg_path}  -y -f {rawvideo} -s:v {width}x{height} -pix_fmt {pixfmt} -r {fps} -i {ref_clip} -sws_flags lanczos+accurate_rnd+print_info -strict -1 -f {rawvideo} -s:v {target_width}x{target_height} -pix_fmt {pixfmt} -r {fps} {scaled_clip_name}",
    }

    METRIC_COMMAND = {

        'SPIE2020_ffmpeg_psnr_ssim': r'''(/usr/bin/time --verbose {ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s   {width}x{height} -r 25  -i {clip} -lavfi "ssim=stats_file={output_filename}.ssim;[0:v][1:v]psnr=stats_file={output_filename}.psnr" -f null - ) > {output_filename}.log 2>&1''',
        'SPIE2020_ffmpeg_vmaf': r'''(/usr/bin/time --verbose {ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s   {width}x{height} -r 25  -i {clip} -lavfi '[0:v][1:v]libvmaf=model=version=vmaf_v0.6.1\\:name=vmaf|version=vmaf_v0.6.1neg\\:name=vmaf_neg:feature=name=psnr\\:reduced_hbd_peak=true\\:enable_apsnr=true\\:min_sse=0.5|name=float_ssim\\:enable_db=true\\:clip_db=true:log_path={output_filename}.xml:log_fmt=xml' -threads 1 -f null - ) > {output_filename}.log 2>&1''',
        'SPIE2020_ffmpeg_psnr_ssim_vmaf_vmaf_neg': r'''(/usr/bin/time --verbose {ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s:v {width}x{height} -r 25  -i {clip}  -lavfi 'ssim=stats_file={output_filename}.ssim;[0:v][1:v]psnr=stats_file={output_filename}.psnr;[0:v][1:v]libvmaf=model=version=vmaf_v0.6.1\\:name=vmaf|version=vmaf_v0.6.1neg\\:name=vmaf_neg:feature=name=psnr\\:reduced_hbd_peak=true\\:enable_apsnr=true\\:min_sse=0.5|name=float_ssim\\:enable_db=true\\:clip_db=true:log_path={output_filename}.vmaf:log_fmt=xml' -f null - ) > {output_filename}.log 2>&1''',
        'SPIE2020_ffmpeg_rescale': r'''(/usr/bin/time --verbose {ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s:v {ref_width}x{ref_height} -r 25  -i {ref_clip} -lavfi 'scale2ref=flags=lanczos+accurate_rnd+print_info [scaled][ref];[scaled] split=3 [scaled1][scaled2][scaled3]; [scaled1][1:v]ssim=stats_file={output_filename}.ssim;[scaled2][1:v]psnr=stats_file={output_filename}.psnr;[scaled3][1:v]libvmaf=model_path=tools/model/vmaf_v0.6.1.pkl:log_path={output_filename}.vmaf'  -map "[ref]" -f null - ) > {output_filename}.log 2>&1''',
        'SPIE2020_ffmpeg_rescale_psnr_ssim': r'''(/usr/bin/time --verbose {ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s:v {ref_width}x{ref_height} -r 25  -i {ref_clip} -lavfi 'scale2ref=flags=lanczos+accurate_rnd+print_info [scaled][ref];[scaled] split=2 [scaled1][scaled2]; [scaled1][1:v]ssim=stats_file={output_filename}.ssim;[scaled2][1:v]psnr=stats_file={output_filename}.psnr'  -map "[ref]" -f null - ) > {output_filename}.log 2>&1''',

        'SPIE2020_ffmpeg_psnr_ssim_vmaf_neg': r'''(/usr/bin/time --verbose {ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s:v {width}x{height} -r 25  -i {clip}  -lavfi 'ssim=stats_file={output_filename}.ssim;[0:v][1:v]psnr=stats_file={output_filename}.psnr;[0:v][1:v]libvmaf=model=version=vmaf_v0.6.1neg\\:feature=name=vmaf_neg:log_path={output_filename}.vmaf:log_fmt=xml' -f null - ) > {output_filename}.log 2>&1''',
        'SPIE2020_ffmpeg_psnr_ssim_vmaf': r'''(/usr/bin/time --verbose {ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s:v {width}x{height} -r 25  -i {clip}  -lavfi 'ssim=stats_file={output_filename}.ssim;[0:v][1:v]psnr=stats_file={output_filename}.psnr;[0:v][1:v]libvmaf=model=version=vmaf_v0.6.1\\:name=vmaf:log_path={output_filename}.vmaf:log_fmt=xml' -f null - ) > {output_filename}.log 2>&1''',
        'SPIE2020_ffmpeg_psnr_ssim_vmaf_ss_vmaf': r'''(/usr/bin/time --verbose {ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s:v {width}x{height} -r 25  -i {clip}  -lavfi 'ssim=stats_file={output_filename}.ssim;[0:v][1:v]psnr=stats_file={output_filename}.psnr;[0:v][1:v]libvmaf=model=version=vmaf_v0.6.1\\:name=vmaf:n_subsample=4:log_path={output_filename}.vmaf:log_fmt=xml' -f null - ) > {output_filename}.log 2>&1''',

        'SPIE2021_ffmpeg_vmaf_aom_ctc': r'''(/usr/bin/time --verbose {ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s:v {width}x{height} -r 25  -i {clip} -lavfi '[0:v][1:v]libvmaf=aom_ctc=1:log_path={output_filename}.xml:log_fmt=xml' -f null -) > {output_filename}.log 2>&1''',
        'SPIE2021_ffmpeg_rescale':      r'''(/usr/bin/time --verbose {ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s:v {ref_width}x{ref_height} -r 25  -i {ref_clip} -lavfi 'scale2ref=flags=lanczos+accurate_rnd+full_chroma_int:sws_dither=none:param0=5:threads=1 [scaled][ref];[scaled] split=1 [scaled1]; [scaled1][1:v]libvmaf=aom_ctc=1:log_path={output_filename}.xml:log_fmt=xml' -map "[ref]" -f null - ) > {output_filename}.log 2>&1''',
        'SPIE2021_ffmpeg_vmaf_rescale' :r'''(/usr/bin/time --verbose {ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s:v {ref_width}x{ref_height} -r 25  -i {ref_clip} -lavfi 'scale2ref=flags=lanczos+accurate_rnd+full_chroma_int:sws_dither=none:param0=5:threads=1 [scaled][ref];[scaled] split=1 [scaled1]; [scaled1][1:v]libvmaf=model=version=vmaf_v0.6.1\\:name=vmaf:feature=name=psnr\\:reduced_hbd_peak=true\\:enable_apsnr=true\\:min_sse=0.5|name=float_ssim\\:enable_db=true\\:clip_db=true:log_path={output_filename}.xml:log_fmt=xml' -map "[ref]" -f null - ) > {output_filename}.log 2>&1''',

        'SPIE2021_ffmpeg_vmaf_exe_rescale': r'''(/usr/bin/time --verbose {ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s:v {ref_width}x{ref_height} -r 25  -i {ref_clip} -lavfi "scale2ref=flags=lanczos+accurate_rnd+full_chroma_int:sws_dither=none:param0=5:threads=1 [scaled][ref]" -map "[ref]" -f null - -map "[scaled]" -strict -1 -pix_fmt {pixfmt} {temp_clip} && tools/vmaf --reference {ref_clip} --distorted {temp_clip} --width {ref_width} --height {ref_height} --pixel_format {vmaf_pixfmt} --bitdepth {bitdepth} --output {output_filename}.xml --aom_ctc v1.0 && rm {temp_clip})> {output_filename}.log 2>&1''',


        'SPIE2021_ffmpeg_rescale_vvenc' : r'''(./vvdecapp -b {output_filename}.bin -o {temp_clip} -t 1 && {ffmpeg_path} -f {rawvideo} -pix_fmt {pixfmt} -s:v {width}x{height} -r 25  -i {temp_clip} -f {rawvideo} -pix_fmt {pixfmt} -s:v {ref_width}x{ref_height} -r 25  -i {ref_clip} -lavfi 'scale2ref=flags=lanczos+accurate_rnd+full_chroma_int:sws_dither=none:param0=5:threads=1 [scaled][ref];[scaled] split=1 [scaled1]; [scaled1][1:v]libvmaf=aom_ctc=1:log_path={output_filename}.xml:log_fmt=xml' -map "[ref]" -f null - && rm {temp_clip}) > {output_filename}.log 2>&1''',

        'SPIE2021_vvenc_ffmpeg_vmaf_exe': r'''(./vvdecapp -b {output_filename}.bin -o {temp_clip} -t 1 && tools/vmaf --reference {clip} --distorted {temp_clip} -w {width} -h {height} -p 420{vmaf_pixfmt} --aom_ctc v1.0 -b {bitdepth} -o {output_filename}.xml && rm {temp_clip}) > {output_filename}.log 2>&1 ''',

        'SPIE2021_ffmpeg_vmaf_vmaf_neg' : r'''(/usr/bin/time --verbose {ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s   {width}x{height} -r 25  -i {clip} -lavfi '[0:v][1:v]libvmaf=model=version=vmaf_v0.6.1\\:name=vmaf|version=vmaf_v0.6.1neg\\:name=vmaf_neg:feature=name=psnr\\:reduced_hbd_peak=true\\:enable_apsnr=true\\:min_sse=0.5|name=float_ssim\\:enable_db=true\\:clip_db=true:log_path={output_filename}.xml:log_fmt=xml' -threads 1 -f null - ) > {output_filename}.log 2>&1''',
        
        'SPIE2021_ffmpeg_rescale_psnr_ssim' : r'''(/usr/bin/time --verbose {ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s:v {ref_width}x{ref_height} -r 25  -i {ref_clip} -lavfi 'scale2ref=flags=lanczos+accurate_rnd+full_chroma_int:sws_dither=none:param0=5:threads=1 [scaled][ref];[scaled] split=2 [scaled1][scaled2]; [scaled1][1:v]ssim=stats_file={output_filename}.ssim;[scaled2][1:v]psnr=stats_file={output_filename}.psnr'  -map "[ref]" -f null - ) > {output_filename}.log 2>&1''',
        'SPIE2021_ffmpeg_rescale_psnr_ssim_vmaf' : r'''(/usr/bin/time --verbose {ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s:v {ref_width}x{ref_height} -r 25  -i {ref_clip} -lavfi 'scale2ref=flags=lanczos+accurate_rnd+full_chroma_int:sws_dither=none:param0=5:threads=1 [scaled][ref];[scaled] split=1 [scaled1]; [scaled1][1:v]libvmaf=model=version=vmaf_v0.6.1\\:name=vmaf:feature=name=psnr\\:reduced_hbd_peak=true\\:enable_apsnr=true\\:min_sse=0.5|name=float_ssim\\:enable_db=true\\:clip_db=true:log_path={output_filename}.xml:log_fmt=xml' -map "[ref]" -f null - ) > {output_filename}.log 2>&1''',
        'SPIE2021_ffmpeg_rescale_psnr_ssim_vmaf_ss_fixed' : r'''(/usr/bin/time --verbose {ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s:v {ref_width}x{ref_height} -r 25  -i {ref_clip} -lavfi 'scale2ref=flags=lanczos+accurate_rnd+full_chroma_int:sws_dither=none:param0=5:threads=1 [scaled][ref];[scaled] split=3 [scaled1][scaled2][scaled3]; [scaled1][1:v]ssim=stats_file={output_filename}.ssim;[scaled2][1:v]psnr=stats_file={output_filename}.psnr;[scaled3][1:v]libvmaf=model=version=vmaf_v0.6.1\\:name=vmaf:n_subsample=4:log_path={output_filename}.xml:log_fmt=xml'  -map "[ref]" -threads 1 -f null - ) > {output_filename}.log 2>&1''',

        'xilften_ffmpeg_vmaf_exe_rescale': r'''({ffmpeg_path} -y -r 25 -i {output_filename}.bin -s:v {ref_width}x{ref_height}  -pix_fmt {pixfmt} -f {rawvideo} -r 25 -i {ref_clip}  -lavfi "scale2ref=flags=lanczos+accurate_rnd+print_info:threads=1 [scaled][ref];[scaled] split=2 [scaled1][scaled2]; [scaled1][1:v]psnr=stats_file={output_filename}.psnr" -map "[ref]" -f null - -map "[scaled2]" -strict -1 -pix_fmt {pixfmt} -f {rawvideo} {temp_clip} && tools/vmaf --reference {ref_clip} --distorted {temp_clip} --width {ref_width} --height {ref_height} --pixel_format {vmaf_pixfmt} --bitdepth {bitdepth} --output {output_filename}.xml --nflx_ctc v1.0 --threads 19 && rm {temp_clip}) > {output_filename}.log 2>&1''',

        'webrtc_psnr_ssim': r'''{ffmpeg_path} -r 25  -i {output_filename}.bin -r 25 -i {clip} -lavfi "ssim=stats_file={output_filename}.ssim;[0:v][1:v]psnr=stats_file={output_filename}.psnr" -f null - > {output_filename}.log 2>&1''',

        'SPIE2021_vtm_ffmpeg' : r'''(tools/DecoderAppStatic -b {output_filename}.bin -o {temp_clip} && {ffmpeg_path} -y -nostdin  -r 25 -f {rawvideo} -pix_fmt {pixfmt} -s:v {width}x{height} -i {temp_clip} -f {rawvideo} -pix_fmt {pixfmt} -s:v {width}x{height} -r 25  -i {clip} -lavfi '[0:v][1:v]libvmaf=aom_ctc=1:log_path={output_filename}.xml:log_fmt=xml' -f null -  && rm {temp_clip}) > {output_filename}.log 2>&1''',
        'SPIE2021_vvenc_ffmpeg' : r'''(tools/vvdecapp -b {output_filename}.bin -o {temp_clip} && {ffmpeg_path} -y -nostdin  -r 25 -f {rawvideo} -pix_fmt {pixfmt} -s:v {width}x{height} -i {temp_clip} -f {rawvideo} -pix_fmt {pixfmt} -s:v {width}x{height} -r 25  -i {clip} -lavfi '[0:v][1:v]libvmaf=aom_ctc=1:log_path={output_filename}.xml:log_fmt=xml' -f null -  && rm {temp_clip}) > {output_filename}.log 2>&1''',

        'SPIE2021_avm_ffmpeg' : r'''(tools/aomdec --codec=av1 --summary -o {temp_clip} {output_filename}.bin && {ffmpeg_path} -y -nostdin  -r 25 -i {temp_clip} -f {rawvideo} -pix_fmt {pixfmt} -s:v {width}x{height} -r 25  -i {clip} -lavfi '[0:v][1:v]libvmaf=aom_ctc=1:log_path={output_filename}.xml:log_fmt=xml' -f null -  && rm {temp_clip}) > {output_filename}.log 2>&1''',
        'SPIE2021_vtm_rescale_ffmpeg' : r'''(tools/DecoderAppStatic -b {output_filename}.bin -o {temp_clip} && {ffmpeg_path} -f {rawvideo} -pix_fmt {pixfmt} -s:v {width}x{height} -r 25  -i {temp_clip} -f {rawvideo} -pix_fmt {pixfmt} -s:v {ref_width}x{ref_height} -r 25  -i {ref_clip} -lavfi 'scale2ref=flags=lanczos+accurate_rnd+full_chroma_int:sws_dither=none:param0=5:threads=1 [scaled][ref];[scaled] split=1 [scaled1]; [scaled1][1:v]libvmaf=aom_ctc=1:log_path={output_filename}.xml:log_fmt=xml' -map "[ref]" -f null - && rm {temp_clip}) > {output_filename}.log 2>&1''',
        'SPIE2021_avm_ffmpeg_rescale' : r'''(tools/aomdec --codec=av1 --summary -o {temp_clip} {output_filename}.bin && {ffmpeg_path} -f {rawvideo} -pix_fmt {pixfmt} -s:v {width}x{height} -r 25  -i {temp_clip} -f {rawvideo} -pix_fmt {pixfmt} -s:v {ref_width}x{ref_height} -r 25  -i {ref_clip} -lavfi 'scale2ref=flags=lanczos+accurate_rnd+full_chroma_int:sws_dither=none:param0=5:threads=1 [scaled][ref];[scaled] split=1 [scaled1]; [scaled1][1:v]libvmaf=aom_ctc=1:log_path={output_filename}.xml:log_fmt=xml' -map "[ref]" -f null -  && rm {temp_clip}) > {output_filename}.log 2>&1''',
       
        'SPIE2020_ffmpeg_psnr_ssim_community_tools': r'''(/usr/bin/time --verbose /home/inteladmin/{ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s   {width}x{height} -r 25  -i {clip} -lavfi "ssim=stats_file={output_filename}.ssim;[0:v][1:v]psnr=stats_file={output_filename}.psnr" -f null - ) > {output_filename}.log 2>&1''',
        'SPIE2020_ffmpeg_psnr_ssim_vmaf_community_tools': r'''(/usr/bin/time --verbose /home/inteladmin/{ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s:v {width}x{height} -r 25  -i {clip}  -lavfi 'ssim=stats_file={output_filename}.ssim;[0:v][1:v]psnr=stats_file={output_filename}.psnr;[0:v][1:v]libvmaf=model=version=vmaf_v0.6.1\\:name=vmaf:log_path={output_filename}.vmaf:log_fmt=xml' -f null - ) > {output_filename}.log 2>&1''',

        'SPIE2020_ffmpeg_psnr_ssim_vmaf_AVM_DEOCODE': r'''(./aomdec {output_filename}.bin -o {temp_clip} && {ffmpeg_path} -y -nostdin  -r 25 -i {temp_clip} -f {rawvideo} -pix_fmt {pixfmt} -s:v {width}x{height} -r 25  -i {clip}  -lavfi 'ssim=stats_file={output_filename}.ssim;[0:v][1:v]psnr=stats_file={output_filename}.psnr;[0:v][1:v]libvmaf=model=version=vmaf_v0.6.1\\:name=vmaf:log_path={output_filename}.vmaf:log_fmt=xml' -f null - && rm {temp_clip}) > {output_filename}.log 2>&1''',
        'SPIE2020_ffmpeg_psnr_ms_ssim_vmaf': r'''(/usr/bin/time --verbose {ffmpeg_path} -y -nostdin  -r 25 -i {output_filename}.bin -f {rawvideo} -pix_fmt {pixfmt} -s:v {width}x{height} -r 25  -i {clip}  -lavfi '[0:v][1:v]psnr=stats_file={output_filename}.psnr;[0:v][1:v]libvmaf=model=version=vmaf_v0.6.1\\:name=vmaf:feature=name=float_ms_ssim:log_path={output_filename}.xml:log_fmt=xml' -f null - ) > {output_filename}.log 2>&1''',
    }

    ENCODE_COMMAND = {
        # '''SPIE2020'''
        'SPIE2020_svt_CRF_1lp_1p': '''(/usr/bin/time --verbose ./SvtAv1EncApp -enc-mode {preset} -q {rc_value} -intra-period {intraperiod} -enable-tpl-la 1 -w {width} -h {height} --input-depth {bitdepth} --fps-num {fps_num} --fps-denom {fps_denom} --lp 1 -i  {clip}  -b  {output_filename}.bin )  > {output_filename}.txt 2>&1 ''',
        'SPIE2020_aom_CRF_2p':     '''(/usr/bin/time --verbose ./aomenc  --cpu-used={preset} --cq-level={rc_value} --kf-min-dist={intraperiod} --kf-max-dist={intraperiod} --passes=2 --verbose  --lag-in-frames=25 --auto-alt-ref=1 --end-usage=q  --bit-depth={bitdepth} --input-bit-depth={bitdepth} --width={width} --height={height} --fps={fps_num}/{fps_denom} -o  {output_filename}.bin  {clip}  )  > {output_filename}.txt 2>&1 ''',
        'SPIE2020_x264_CRF_1p':    '''(/usr/bin/time --verbose ./x264  --preset {preset} --crf {rc_value}  --keyint {intraperiod}  --min-keyint {intraperiod}  --input-res {width}x{height}  --fps {fps_num}/{fps_denom}  --input-depth {bitdepth}  --threads 1  --tune psnr  --stats {output_filename}.stat   -o {output_filename}.bin  {clip})  > {output_filename}.txt 2>&1 ''',
        'SPIE2020_x265_CRF_1p':    '''(/usr/bin/time --verbose ./x265  --preset {preset} --crf {rc_value}  --keyint {intraperiod}  --min-keyint {intraperiod}  --input-res {width}x{height}  --fps {fps_num}/{fps_denom}  --input-depth {bitdepth} --frame-threads 1 --no-wpp  --tune  psnr  --stats {output_filename}.stat  {clip}  -o {output_filename}.bin)  > {output_filename}.txt 2>&1 ''',
        'SPIE2020_vp9_CRF_2p':     '''(/usr/bin/time --verbose ./vpxenc  --cpu-used={preset} --cq-level={rc_value} --kf-min-dist={intraperiod} --kf-max-dist={intraperiod} --verbose   --passes=2 --end-usage=q  --lag-in-frames=25 --auto-alt-ref=6 --bit-depth={bitdepth} --input-bit-depth={bitdepth} --width={width} --height={height} --fps={fps_num}/{fps_denom} -o  {output_filename}.bin  {clip}  )  > {output_filename}.txt 2>&1 ''',


        # '''SPIE2021'''
        'SPIE2021_svt_CRF_1lp_1p': '''(/usr/bin/time --verbose ./SvtAv1EncApp --preset {preset} -q {rc_value} --lp 1 --keyint {intraperiod} -w {width} -h {height} --input-depth {bitdepth} --fps-num {fps_num} --fps-denom {fps_denom} --lp 1  --passes 1 -i  {clip}  -b  {output_filename}.bin )  > {output_filename}.txt 2>&1 ''',
        'SPIE2021_aom_CRF_2p':     '''(/usr/bin/time --verbose ./aomenc --ivf --cpu-used={preset} --cq-level={rc_value} --kf-min-dist={intraperiod} --kf-max-dist={intraperiod} --passes=2 --verbose  --lag-in-frames=35 --auto-alt-ref=1 --end-usage=q  --bit-depth={bitdepth} --input-bit-depth={bitdepth} --width={width} --height={height} --fps={fps_num}/{fps_denom}  -o  {output_filename}.bin  {clip}  )  > {output_filename}.txt 2>&1 ''',
        'SPIE2021_x265_CRF_1p':    '''(/usr/bin/time --verbose ./x265  --preset {preset} --crf {rc_value} --keyint {intraperiod}  --min-keyint {intraperiod} --input-res {width}x{height}  --fps {fps_num}/{fps_denom}  --input-depth {bitdepth}  --tune  psnr  --stats {output_filename}.stat  --pools 1  --no-scenecut   --no-wpp   {clip}  -o {output_filename}.bin)  > {output_filename}.txt 2>&1 ''',
        'SPIE2021_x264_CRF_1p':    '''(/usr/bin/time --verbose ./x264  --preset {preset}  --crf {rc_value}  --keyint {intraperiod}  --min-keyint {intraperiod}  --input-res {width}x{height}  --fps {fps_num}/{fps_denom}  --input-depth {bitdepth}  --threads 1  --tune psnr  --stats {output_filename}.stat  --no-scenecut   -o {output_filename}.bin  {clip})  > {output_filename}.txt 2>&1 ''',
        'SPIE2021_vvenc_CRF_1p':   '''(/usr/bin/time --verbose ./vvencapp  --input {clip} --preset {vvenc_preset}  --qp {rc_value} --intraperiod {intraperiod} --size {width}x{height}  --format  {vvenc_pixfmt}  --internal-bitdepth {bitdepth}  --fps {fps_num}/{fps_denom}  --threads 1  --output {output_filename}.bin )  > {output_filename}.txt 2>&1 ''',
        'SPIE2021_vp9_CRF_2p':     '''(/usr/bin/time --verbose ./vpxenc --ivf --codec=vp9  --tile-columns=0 --arnr-maxframes=7 --arnr-strength=5 --aq-mode=0 --bias-pct=100 \
            --minsection-pct=1 --maxsection-pct=10000 --i420 --min-q=0 --frame-parallel=0 --min-gf-interval=4 --max-gf-interval=16 --verbose   --passes=2 --end-usage=q  --lag-in-frames=25 \
            --auto-alt-ref=6  --threads=1  --profile=0  --bit-depth={bitdepth} --input-bit-depth={bitdepth} --fps={fps_num}/{fps_denom} --kf-min-dist={intraperiod} --kf-max-dist={intraperiod} --cq-level={rc_value} --cpu-used={preset} -o  {output_filename}.bin    {clip})  > {output_filename}.txt 2>&1''',

        #'''Default commands'''
        'svt_CRF_1lp_1p':   '''(/usr/bin/time --verbose ./SvtAv1EncApp --preset {preset} -q {rc_value} --keyint {intraperiod} -w {width} -h {height} --input-depth {bitdepth} --fps-num {fps_num} --fps-denom {fps_denom} --lp 1 -i {clip} -b {output_filename}.bin ) > {output_filename}.txt 2>&1''',
        'svt_CRF_nonlp_1p': '''(/usr/bin/time --verbose ./SvtAv1EncApp --preset {preset} -q {rc_value} --keyint {intraperiod} -w {width} -h {height} --input-depth {bitdepth} --fps-num {fps_num} --fps-denom {fps_denom} -i {clip} -b {output_filename}.bin ) > {output_filename}.txt 2>&1 ''',
        'svt_VBR_1lp_1p':   '''(/usr/bin/time --verbose ./SvtAv1EncApp --preset {preset} --tbr {rc_value} --keyint {intraperiod} -w {width} -h {height} --input-depth {bitdepth} --fps-num {fps_num} --fps-denom {fps_denom}  --lp 1  --passes 1 --rc 1 -i  {clip}  -b  {output_filename}.bin )  > {output_filename}.txt 2>&1 ''',
        'svt_VBR_1lp_2p':   '''(/usr/bin/time --verbose ./SvtAv1EncApp --preset {preset} --tbr {rc_value} --keyint {intraperiod} -w {width} -h {height} --input-depth {bitdepth} --fps-num {fps_num} --fps-denom {fps_denom}  --lp 1  --passes 2 --rc 1 --irefresh-type 2  -i  {clip} --stats {output_filename}.stat -b  {output_filename}.bin )  > {output_filename}.txt 2>&1''',

        'x264_VBR_1lp_1p' : '''(/usr/bin/time --verbose ./x264  --preset {preset}  --bitrate {rc_value}  --keyint {intraperiod}  --min-keyint {intraperiod}  --input-res {width}x{height}  --fps {fps_num}/{fps_denom}  --input-depth {bitdepth}  --threads 1  --tune psnr --no-scenecut   -o {output_filename}.bin  {clip})  > {output_filename}.txt 2>&1''',
        'x265_VBR_1lp_1p' : '''(/usr/bin/time --verbose ./x265  --preset {preset}  --bitrate {rc_value}  --keyint {intraperiod}  --min-keyint {intraperiod}  --input-res {width}x{height}  --fps {fps_num}/{fps_denom}  --input-depth {bitdepth}  --pools 1  --no-scenecut   --no-wpp   -o {output_filename}.bin  {clip})  > {output_filename}.txt 2>&1''',
        
        'libaom_CRF_1lp' : '''(/usr/bin/time --verbose ./aomenc --ivf --verbose --kf-min-dist={intraperiod} --kf-max-dist={intraperiod}  --cq-level={rc_value} --end-usage=q --cpu-used={preset}  -o  {output_filename}.bin    {clip} )  > {output_filename}.txt 2>&1 ''',
        'libaom_VBR_1lp_2p' : '''(/usr/bin/time --verbose ./aomenc --ivf --verbose --passes=2 --kf-min-dist={intraperiod} --kf-max-dist={intraperiod}  --end-usage=vbr --target-bitrate={rc_value} --cpu-used={preset}  -o  {output_filename}.bin    {clip} )  > {output_filename}.txt 2>&1 ''',

        'x264_VBR_1lp_2p' : ''' /usr/bin/time --verbose bash -c './x264  --preset {preset}  --bitrate {rc_value}  --keyint {intraperiod}  --min-keyint {intraperiod}  --input-res {width}x{height}  --fps {fps_num}/{fps_denom}  --input-depth {bitdepth}  --threads 1  --tune psnr --no-scenecut --pass 1 --stats {output_filename}.stat    -o {output_filename}.bin  {clip};  ./x264  --preset {preset}  --bitrate {rc_value}  --keyint {intraperiod}  --min-keyint {intraperiod}  --input-res {width}x{height}  --fps {fps_num}/{fps_denom}  --input-depth {bitdepth}  --threads 1  --tune psnr --no-scenecut --pass 2 --stats {output_filename}.stat    -o {output_filename}.bin  {clip}' > {output_filename}.txt 2>&1''',
        'x265_VBR_1lp_2p' : ''' /usr/bin/time --verbose bash -c './x265  --preset {preset}  --bitrate {rc_value}  --keyint {intraperiod}  --min-keyint {intraperiod}  --input-res {width}x{height}  --fps {fps_num}/{fps_denom}  --input-depth {bitdepth}  --pools 1  --no-scenecut   --no-wpp --pass 1 --stats {output_filename}.stat  -o {output_filename}.bin  {clip}; ./x265  --preset {preset}  --bitrate {rc_value}  --keyint {intraperiod}  --min-keyint {intraperiod}  --input-res {width}x{height}  --fps {fps_num}/{fps_denom}  --input-depth {bitdepth}  --pools 1  --no-scenecut   --no-wpp  --pass 2 --stats {output_filename}.stat -o {output_filename}.bin  {clip}'  > {output_filename}.txt 2>&1''',


        'svt_CRF_lp8_1p':   '''(/usr/bin/time --verbose ./SvtAv1EncApp --preset {preset} -q {rc_value}    --keyint {intraperiod} -w {width} -h {height} --input-depth {bitdepth} --fps-num {fps_num} --fps-denom {fps_denom} --lp 8 --passes 1 -i  {clip}  -b  {output_filename}.bin )  > {output_filename}.txt 2>&1''',
        'svt_ld_cqp_cmds' : '''(/usr/bin/time --verbose ./SvtAv1EncApp --preset {preset} -q {rc_value} --pred-struct 1 --rtc-mode 0 --keyint -1 -w {width} -h {height} --input-depth {bitdepth} --fps-num {fps_num} --fps-denom {fps_denom} --lp 1 --passes 1 -i  {clip}  -b  {output_filename}.bin )  > {output_filename}.txt 2>&1''',
        'svt_allintra_cqp_cmds':'''(/usr/bin/time --verbose ./SvtAv1EncApp --preset {preset} -q {rc_value} --keyint 1 -w {width} -h {height} --input-depth {bitdepth} --fps-num {fps_num} --fps-denom {fps_denom} --lp 1 --passes 1 -i  {clip}  -b  {output_filename}.bin )  > {output_filename}.txt 2>&1''',
        'svt_still_image_cqp_cmds':'''(/usr/bin/time --verbose ./SvtAv1EncApp --avif 1 --preset {preset} -q {rc_value} --keyint 1 -w {width} -h {height} --input-depth {bitdepth} --fps-num {fps_num} --fps-denom {fps_denom} --lp 1 --passes 1 -i  {clip}  -b  {output_filename}.bin )  > {output_filename}.txt 2>&1''',

        'ffmpeg_svt_fast_decode': '''(/usr/bin/time --verbose ./ffmpeg -y  -s:v {width}x{height}  -pix_fmt {pixfmt}  -r {fps} -f {rawvideo}  -i {clip}  -crf {rc_value}  -preset {preset}  -g {intraperiod}  -threads 1  -c:v libsvtav1  -f ivf   -svtav1-params lp=1:fast-decode=1  {output_filename}.bin ) > {output_filename}.txt 2>&1''',
        'ffmpeg_svt_embedded_scaling' : '''(/usr/bin/time --verbose  ./ffmpeg -hide_banner -y -f {rawvideo} -pix_fmt {pixfmt} -s:v {width}x{height} -r {fps_decimal} -i {ref_clip} -an -threads 1 -pix_fmt {pixfmt} -crf {rc_value} -g {intraperiod} -keyint_min {intraperiod} -movflags faststart -vf scale={target_width}:-2:flags=lanczos:param0=5 -preset {preset} -sc_threshold 0 -c:v libsvtav1 -svtav1-params lp=1 -f mp4 {output_filename}.bin) > {output_filename}.txt 2>&1''',

        'svt_webrtc': '''(/usr/bin/time --verbose ./SvtAv1EncApp --preset {preset} --lp 1  --rc 2 --tbr {rc_value} --keyint {intraperiod} --rtc 1 --pred-struct 1 -i  {clip} -b {output_filename}.bin ) > {output_filename}.txt 2>&1''',
        'svt_webrtc_SC': '''(/usr/bin/time --verbose ./SvtAv1EncApp --preset {preset} --lp 1  --rc 2 --tbr {rc_value} --keyint {intraperiod} --rtc 1 --pred-struct 1 --scm 1 -i {clip} -b {output_filename}.bin ) > {output_filename}.txt 2>&1 ''',
        'aom_webrtc': '''(/usr/bin/time --verbose ./aomenc --ivf --verbose --passes=1 --rt --end-usage=cbr --disable-trellis-quant=1 --enable-order-hint=0 --enable-global-motion=0  --enable-interintra-comp=0 --enable-cdef=1 --enable-warped-motion=0 --enable-dist-wtd-comp=0 --enable-masked-comp=0  --enable-diff-wtd-comp=0 --enable-interinter-wedge=0 --enable-obmc=0 --enable-filter-intra=0 --enable-dual-filter=0  --enable-restoration=0 --enable-qm=0 --enable-ref-frame-mvs=0 --enable-rect-partitions=0 --enable-intra-edge-filter=0  --enable-smooth-interintra=0 --enable-tx64=0 --enable-smooth-intra=0 --enable-paeth-intra=0 --enable-cfl-intra=0  --enable-palette=0 --enable-intrabc=0 --enable-angle-delta=0 --reduced-tx-type-set=0 --use-intra-dct-only=0  --use-inter-dct-only=0 --use-intra-default-tx-only=0 --enable-interintra-wedge=0 --enable-cfl-intra=0 --aq-mode=3  --tile-rows=0 --tile-columns=0 --row-mt=0 --enable-tpl-model=0 --deltaq-mode=0 --mv-cost-upd-freq=3  --coeff-cost-upd-freq=3 --mode-cost-upd-freq=3 --max-reference-frames=3 --psnr --lag-in-frames=0 --undershoot-pct=50  --overshoot-pct=50 --buf-sz=1000 --buf-initial-sz=600 --buf-optimal-sz=600 --max-intra-rate=300 --threads=1  --kf-min-dist={intraperiod} --kf-max-dist={intraperiod} --target-bitrate={rc_value} --cpu-used={preset}  -o  {output_filename}.bin    {clip}  )  > {output_filename}.txt 2>&1 ''',
        'aom_webrtc_2': '''(/usr/bin/time --verbose ./aomenc --ivf --verbose --passes=1 --rt --end-usage=cbr --profile=0 --static-thresh=0 --usage=1 --noise-sensitivity=0 --error-resilient=0 --enable-order-hint=0 --enable-global-motion=0 --enable-cdef=1 --enable-warped-motion=0 --enable-obmc=0 --enable-ref-frame-mvs=0  --aq-mode=3 --tile-columns=0 --enable-tpl-model=0 --deltaq-mode=0 --mv-cost-upd-freq=3  --coeff-cost-upd-freq=3 --mode-cost-upd-freq=3 --psnr --lag-in-frames=0 --min-q=2 --max-q=63 --undershoot-pct=50 --overshoot-pct=10 --buf-sz=1000 --buf-initial-sz=600 --buf-optimal-sz=600 --max-intra-rate=300 --threads=1  --kf-min-dist={intraperiod} --kf-max-dist={intraperiod} --target-bitrate={rc_value} --cpu-used={preset}  -o  {output_filename}.bin    {clip}  )  > {output_filename}.txt 2>&1 ''',
        'aom_webrtc_SC': '''(/usr/bin/time --verbose ./aomenc --ivf --verbose --passes=1 --rt --end-usage=cbr --disable-trellis-quant=1 --enable-order-hint=0 --enable-global-motion=0  --enable-interintra-comp=0 --enable-cdef=1 --enable-warped-motion=0 --enable-dist-wtd-comp=0 --enable-masked-comp=0  --enable-diff-wtd-comp=0 --enable-interinter-wedge=0 --enable-obmc=0 --enable-filter-intra=0 --enable-dual-filter=0  --enable-restoration=0 --enable-qm=0 --enable-ref-frame-mvs=0 --enable-rect-partitions=0 --enable-intra-edge-filter=0  --enable-smooth-interintra=0 --enable-tx64=0 --enable-smooth-intra=0 --enable-paeth-intra=0 --enable-cfl-intra=0  --enable-palette=1 --enable-intrabc=0 --tune-content=screen --enable-angle-delta=0 --reduced-tx-type-set=0 --use-intra-dct-only=0  --use-inter-dct-only=0 --use-intra-default-tx-only=0 --enable-interintra-wedge=0 --enable-cfl-intra=0 --aq-mode=3  --tile-rows=0 --tile-columns=0 --row-mt=0 --enable-tpl-model=0 --deltaq-mode=0 --mv-cost-upd-freq=3  --coeff-cost-upd-freq=3 --mode-cost-upd-freq=3 --max-reference-frames=3 --psnr --lag-in-frames=0 --undershoot-pct=50  --overshoot-pct=50 --buf-sz=1000 --buf-initial-sz=600 --buf-optimal-sz=600 --max-intra-rate=300 --threads=1  --kf-min-dist={intraperiod} --kf-max-dist={intraperiod} --target-bitrate={rc_value} --cpu-used={preset}  -o  {output_filename}.bin    {clip}  )  > {output_filename}.txt 2>&1 ''',

        'vtm_CRF_1p' : '''(/usr/bin/time --verbose ./EncoderAppStatic  --InputFile={clip} --QP={rc_value} -c encoder_randomaccess_vtm.cfg --SourceWidth={width} --SourceHeight={height}  --InputChromaFormat=420  --InputBitDepth={bitdepth}  --FrameRate={fps_decimal} --FramesToBeEncoded={number_of_frames}  --BitstreamFile={output_filename}.bin )  > {output_filename}.txt 2>&1 ''',

        'vvenc_CRF_1p' : '''(/usr/bin/time --verbose ./vvencapp  --input {clip} --preset {vvenc_preset}  --qp {rc_value} --intraperiod {intraperiod} --size {width}x{height}  --format  {vvenc_pixfmt} --internal-bitdepth {bitdepth}  --fps {fps_num}/{fps_denom}  --threads 1  --output {output_filename}.bin )  > {output_filename}.txt 2>&1''',

        'svt_CRF_1lp_1p_open_gop' : '''(/usr/bin/time --verbose ./SvtAv1EncApp --preset {preset} -q {rc_value} --keyint {intraperiod} -w {width} -h {height}  --input-depth {bitdepth} --fps-num {fps_num} --fps-denom {fps_denom} --lp 1 --irefresh-type 1  --passes 1 -i  {clip}  -b  {output_filename}.bin )  > {output_filename}.txt 2>&1 ''',
        'SPIE2021_vvenc_CRF_1p_closedGOP':   '''(/usr/bin/time --verbose ./vvencapp  --input {clip} --preset {vvenc_preset}  --qp {rc_value} --intraperiod {intraperiod} --size {width}x{height}  --format  {vvenc_pixfmt}  --internal-bitdepth {bitdepth}  --fps {fps_num}/{fps_denom}  --threads 1 --refreshtype idr --output {output_filename}.bin )  > {output_filename}.txt 2>&1 ''',

        'avm_CRF_1p' : '''(/usr/bin/time --verbose ./aomenc --verbose --codec=av1 -v --psnr --obu --cpu-used={preset} --frame-parallel=0 --passes=1 --end-usage=q --i420  --use-fixed-qp-offsets=1 --deltaq-mode=0  --enable-tpl-model=0 --fps={fps_num}/{fps_denom}  --input-bit-depth={bitdepth} --bit-depth={bitdepth} -w {width} -h {height} --qp={rc_value} --tile-columns=0 --threads=1  --enable-fwd-kf=0  --enable-keyframe-filtering=0  --min-gf-interval=16 --max-gf-interval=16 --gf-min-pyr-height=4 --gf-max-pyr-height=4 --kf-min-dist={intraperiod} --kf-max-dist={intraperiod} --lag-in-frames=19 --auto-alt-ref=1  -o {output_filename}.bin {clip})  > {output_filename}.txt 2>&1''',
        'avm_CRF_6L_1p' : '''(/usr/bin/time --verbose ./aomenc --verbose --codec=av1 -v --psnr --obu --cpu-used={preset} --frame-parallel=0 --passes=1 --end-usage=q --i420  --use-fixed-qp-offsets=1 --deltaq-mode=0  --enable-tpl-model=0 --fps={fps_num}/{fps_denom}  --input-bit-depth={bitdepth} --bit-depth={bitdepth} -w {width} -h {height} --qp={rc_value} --tile-columns=0 --threads=1  --enable-fwd-kf=0  --enable-keyframe-filtering=0  --min-gf-interval=32 --max-gf-interval=32 --gf-min-pyr-height=5 --gf-max-pyr-height=5 --kf-min-dist={intraperiod} --kf-max-dist={intraperiod} --lag-in-frames=35 --auto-alt-ref=1  -o {output_filename}.bin {clip})  > {output_filename}.txt 2>&1''',
        'svt_CRF_1lp_1p_aq0':   '''(/usr/bin/time --verbose ./SvtAv1EncApp --preset {preset} -q {rc_value}    --keyint {intraperiod} -w {width} -h {height} --input-depth {bitdepth} --fps-num {fps_num} --fps-denom {fps_denom} --lp 1 --aq-mode 0 --passes 1 -i  {clip}  -b  {output_filename}.bin )  > {output_filename}.txt 2>&1''',
        'libaom_allintra_ctc_cmds': '''(/usr/bin/time --verbose ./aomenc --ivf --verbose --cpu-used={preset} --cq-level={rc_value} --kf-min-dist=0 --kf-max-dist=0 --passes=1 --end-usage=q --deltaq-mode=0 --enable-tpl-model=0 --enable-keyframe-filtering=0  --bit-depth={bitdepth} --input-bit-depth={bitdepth} --width={width} --height={height} --fps={fps_num}/{fps_denom} -o  {output_filename}.bin  {clip}  )  > {output_filename}.txt 2>&1 ''',
        'libaom_still_image_ctc_cmds': '''(/usr/bin/time --verbose ./aomenc --ivf --verbose --cpu-used={preset} --cq-level={rc_value} --kf-min-dist=0 --kf-max-dist=0 --passes=1 --end-usage=q --deltaq-mode=0 --enable-tpl-model=0 --enable-keyframe-filtering=0  --bit-depth={bitdepth} --input-bit-depth={bitdepth} --width={width} --height={height} --fps={fps_num}/{fps_denom} -o  {output_filename}.bin  {clip}  )  > {output_filename}.txt 2>&1 ''',
        'libaom_ld_constrained_cmds' : '''(/usr/bin/time --verbose ./aomenc --ivf --verbose --codec=av1 -v --psnr --frame-parallel=0 --skip=0 --passes=1 --end-usage=q --use-fixed-qp-offsets=1 --deltaq-mode=0 --enable-tpl-model=0 --tile-rows=0 --tile-columns=0 --threads=1 --row-mt=0  --enable-fwd-kf=0  --enable-keyframe-filtering=0  --kf-min-dist=9999 --kf-max-dist=9999 --lag-in-frames=0 --min-gf-interval=16 --max-gf-interval=16 --gf-min-pyr-height=4  --gf-max-pyr-height=4  --cpu-used={preset} --cq-level={rc_value} -o  {output_filename}.bin    {clip} )  > {output_filename}.txt 2>&1 ''',

    }

    main()

#Archived Test Configs
        ## SPIE2020 Configs
        # 'SPIE2020_8bit_svt'  : [RC_VALUES['SPIE2020_svt_aom'],   RESOLUTION['SPIE2020_8bit'],   DOWNSCALE_COMMAND['SPIE2020_scaling'], METRIC_COMMAND['SPIE2020_ffmpeg_rescale'], ENCODE_COMMAND['svt_CRF_1lp_1p']],
        # 'SPIE2020_8bit_aom'  : [RC_VALUES['SPIE2020_svt_aom'],   RESOLUTION['SPIE2020_8bit'],   DOWNSCALE_COMMAND['SPIE2020_scaling'], METRIC_COMMAND['SPIE2020_ffmpeg_rescale'], ENCODE_COMMAND['SPIE2020_aom_CRF_2p']],
        # 'SPIE2020_8bit_x264' : [RC_VALUES['SPIE2020_x264_x265'], RESOLUTION['SPIE2020_8bit'], DOWNSCALE_COMMAND['SPIE2020_scaling'], METRIC_COMMAND['SPIE2020_ffmpeg_rescale'], ENCODE_COMMAND['SPIE2020_x264_CRF_1p']],
        # 'SPIE2020_8bit_x265' : [RC_VALUES['SPIE2020_x264_x265'], RESOLUTION['SPIE2020_8bit'], DOWNSCALE_COMMAND['SPIE2020_scaling'], METRIC_COMMAND['SPIE2020_ffmpeg_rescale'], ENCODE_COMMAND['SPIE2020_x265_CRF_1p']],
        # 'SPIE2020_8bit_vp9'  : [RC_VALUES['SPIE2020_svt_aom'],   RESOLUTION['SPIE2020_8bit'],   DOWNSCALE_COMMAND['SPIE2020_scaling'], METRIC_COMMAND['SPIE2020_ffmpeg_rescale'], ENCODE_COMMAND['SPIE2020_vp9_CRF_2p']],
        # 'SPIE2020_10bit_svt' : [RC_VALUES['SPIE2020_svt_aom'],   RESOLUTION['SPIE2020_10bit'],   DOWNSCALE_COMMAND['SPIE2020_scaling'], METRIC_COMMAND['SPIE2020_ffmpeg_rescale'], ENCODE_COMMAND['svt_CRF_1lp_1p']],
        # 'SPIE2020_10bit_aom' : [RC_VALUES['SPIE2020_svt_aom'],   RESOLUTION['SPIE2020_10bit'],   DOWNSCALE_COMMAND['SPIE2020_scaling'], METRIC_COMMAND['SPIE2020_ffmpeg_rescale'], ENCODE_COMMAND['SPIE2020_aom_CRF_2p']],
        # 'SPIE2020_10bit_x264': [RC_VALUES['SPIE2020_x264_x265'], RESOLUTION['SPIE2020_10bit'], DOWNSCALE_COMMAND['SPIE2020_scaling'], METRIC_COMMAND['SPIE2020_ffmpeg_rescale'], ENCODE_COMMAND['SPIE2020_x264_CRF_1p']],
        # 'SPIE2020_10bit_x265': [RC_VALUES['SPIE2020_x264_x265'], RESOLUTION['SPIE2020_10bit'], DOWNSCALE_COMMAND['SPIE2020_scaling'], METRIC_COMMAND['SPIE2020_ffmpeg_rescale'], ENCODE_COMMAND['SPIE2020_x265_CRF_1p']],
        # 'SPIE2020_10bit_vp9' : [RC_VALUES['SPIE2020_svt_aom'],   RESOLUTION['SPIE2020_10bit'],   DOWNSCALE_COMMAND['SPIE2020_scaling'], METRIC_COMMAND['SPIE2020_ffmpeg_rescale'], ENCODE_COMMAND['SPIE2020_vp9_CRF_2p']],
        # 'SPIE2020_ffmpeg_svt': [RC_VALUES['ffmpeg_svt'], RESOLUTION['ffmpeg_svt'], DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2020_ffmpeg_rescale_psnr_ssim'], ENCODE_COMMAND['ffmpeg_svt_embedded_scaling']],

        # 'xilften_svt': [RC_VALUES['xilften_crf'], RESOLUTION['xilften'], DOWNSCALE_COMMAND['SPIE2020_scaling'], METRIC_COMMAND['xilften_ffmpeg_vmaf_exe_rescale'], ENCODE_COMMAND['svt_CRF_1lp_1p']],
        # 'xilften_libaom': [RC_VALUES['xilften_crf'], RESOLUTION['xilften'], DOWNSCALE_COMMAND['SPIE2020_scaling'], METRIC_COMMAND['xilften_ffmpeg_vmaf_exe_rescale'], ENCODE_COMMAND['SPIE2021_aom_CRF_2p']],
        ##5QP vtm/vvenc/svt 480p testings
        # 'vtm_5qp_RA_test' : [RC_VALUES['vvenc_5qp'], None,   None, METRIC_COMMAND['SPIE2021_vtm_ffmpeg'], ENCODE_COMMAND['vtm_CRF_1p']],
        # 'vvenc_5qp_crf_closedGOP' : [RC_VALUES['vvenc_5qp'], None,   None, METRIC_COMMAND['SPIE2021_vvenc_ffmpeg'], ENCODE_COMMAND['SPIE2021_vvenc_CRF_1p_closedGOP']],
        # 'vvenc_5qp_crf_openGOP' : [RC_VALUES['vvenc_5qp'], None,   None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim'], ENCODE_COMMAND['SPIE2021_vvenc_CRF_1p']],        
        # 'svt_CRF_1lp_1p_open_gop': [RC_VALUES['svt_mr_testing'], None, None, METRIC_COMMAND['SPIE2021_ffmpeg_vmaf'], ENCODE_COMMAND['svt_CRF_1lp_1p_open_gop']],
        # 'svt_CRF_1lp_1p_closed_gop': [RC_VALUES['svt_mr_testing'], None, None, METRIC_COMMAND['SPIE2021_ffmpeg_vmaf'], ENCODE_COMMAND['svt_CRF_1lp_1p']],
        # 'avm_test_5L' : [RC_VALUES['avm'], None, None, METRIC_COMMAND['SPIE2021_avm_ffmpeg'], ENCODE_COMMAND['avm_CRF_1p']],
        # 'avm_test_6L' : [RC_VALUES['avm'], None, None, METRIC_COMMAND['SPIE2021_avm_ffmpeg'], ENCODE_COMMAND['avm_CRF_6L_1p']],

        ##360p Elfuente
        # 'SPIE2021_avm_5L_sub_360p'  : [RC_VALUES['avm_11qp'],         RESOLUTION['SPIE2021_sub_360p'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_avm_ffmpeg'],           ENCODE_COMMAND['avm_CRF_1p']],
        # 'SPIE2021_vtm_RA_sub_360p'  : [RC_VALUES['SPIE2021_svt_aom'], RESOLUTION['SPIE2021_sub_360p'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_vtm_rescale_ffmpeg'],   ENCODE_COMMAND['vtm_CRF_1p']],
        # 'SPIE2021_svt_cqp_sub_360p' : [RC_VALUES['SPIE2021_svt_aom'], RESOLUTION['SPIE2021_sub_360p'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale'],       ENCODE_COMMAND['svt_CRF_1lp_1p_aq0']],
        # 'SPIE2021_aom_sub_360p'     : [RC_VALUES['SPIE2021_svt_aom'], RESOLUTION['SPIE2021_sub_360p'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale'],       ENCODE_COMMAND['SPIE2021_aom_CRF_2p']],
        # 'SPIE2021_vvenc_sub_360p'   : [RC_VALUES['SPIE2021_svt_aom'], RESOLUTION['SPIE2021_sub_360p'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale_vvenc'], ENCODE_COMMAND['SPIE2021_vvenc_CRF_1p']],
        # 'svt_CRF_lp8_1p_tuning_5qp': [RC_VALUES['5qp_preset_tuning'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf_neg'], ENCODE_COMMAND['svt_CRF_lp8_1p']],
        #MR testing
        # 'svt_CRF_1lp_1p_MR': [RC_VALUES['svt_mr_testing'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim'], ENCODE_COMMAND['svt_CRF_1lp_1p']],
        # 'svt_CRF_1lp_2p_MR': [RC_VALUES['svt_mr_testing'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim'], ENCODE_COMMAND['svt_CRF_1lp_2p']],
        # 'svt_CRF_nonlp_1p_MR': [RC_VALUES['svt_mr_testing'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim'], ENCODE_COMMAND['svt_CRF_nonlp_1p']],
        # 'svt_CRF_nonlp_2p_MR': [RC_VALUES['svt_mr_testing'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim'], ENCODE_COMMAND['svt_CRF_nonlp_2p']],
        # 'svt_VBR_1lp_1p_MR': [RC_VALUES['svt_mr_testing'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim'], ENCODE_COMMAND['svt_VBR_1lp_1p']],
        # 'svt_VBR_1lp_2p_MR': [RC_VALUES['svt_mr_testing'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim'], ENCODE_COMMAND['svt_VBR_1lp_2p']],
        
       # #webrtc
        # 'webrtc_svt': [RC_VALUES['webrtc'], None, None, METRIC_COMMAND['webrtc_psnr_ssim'], ENCODE_COMMAND['svt_webrtc']],
        # 'webrtc_svt_SC': [RC_VALUES['webrtc'], None, None, METRIC_COMMAND['webrtc_psnr_ssim'], ENCODE_COMMAND['svt_webrtc_SC']],
        # 'webrtc_svt_ultra_LD': [RC_VALUES['webrtc_ultra_LD'], None, None, METRIC_COMMAND['webrtc_psnr_ssim'], ENCODE_COMMAND['svt_webrtc']],
        # 'webrtc_aom': [RC_VALUES['webrtc'], None, None, METRIC_COMMAND['webrtc_psnr_ssim'], ENCODE_COMMAND['aom_webrtc']],
        # 'webrtc_aom_SC': [RC_VALUES['webrtc'], None, None, METRIC_COMMAND['webrtc_psnr_ssim'], ENCODE_COMMAND['aom_webrtc_SC']],
        # 'webrtc_svt_iterations-3': [RC_VALUES['webrtc'], None, None, METRIC_COMMAND['webrtc_psnr_ssim'], ENCODE_COMMAND['svt_webrtc']],
        # 'webrtc_svt_SC_iterations-3': [RC_VALUES['webrtc'], None, None, METRIC_COMMAND['webrtc_psnr_ssim'], ENCODE_COMMAND['svt_webrtc_SC']],
        # 'webrtc_aom_iterations-3': [RC_VALUES['webrtc'], None, None, METRIC_COMMAND['webrtc_psnr_ssim'], ENCODE_COMMAND['aom_webrtc']],
        # 'webrtc_aom_SC_iterations-3': [RC_VALUES['webrtc'], None, None, METRIC_COMMAND['webrtc_psnr_ssim'], ENCODE_COMMAND['aom_webrtc_SC']],

        ##Performance Tracking
        # 'aom_test' : [RC_VALUES['svt_mr_testing'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim'], ENCODE_COMMAND['SPIE2021_aom_CRF_2p']],
        # 'svt_test'  : [RC_VALUES['SPIE2021_svt_aom'], RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale'], ENCODE_COMMAND['SPIE2021_svt_CRF_1lp_1p']],
      
        # 2025-03-27 Archive
        # 'SPIE2021_svt_psnr_ssim_vertical_horizontal_square'       : [RC_VALUES['SPIE2021_svt_aom'], RESOLUTION['SPIE2021_8bit_vertical_horizontal_square'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale_psnr_ssim'], ENCODE_COMMAND['SPIE2021_svt_CRF_1lp_1p']],
        # 'SPIE2021_svt_psnr_ssim_720p'       : [RC_VALUES['SPIE2021_svt_aom'], RESOLUTION['SPIE2021_8bit_720p'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale_psnr_ssim'], ENCODE_COMMAND['SPIE2021_svt_CRF_1lp_1p']],
        # 'SPIE2021_svt_psnr_ssim_vmaf_ss_720p'       : [RC_VALUES['SPIE2021_svt_aom'], RESOLUTION['SPIE2021_8bit_720p'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale_psnr_ssim_vmaf_ss_fixed'], ENCODE_COMMAND['SPIE2021_svt_CRF_1lp_1p']],
        # 'svt_CRF_1lp_1p_tuning_11qp_ss_vmaf': [RC_VALUES['11qp_preset_tuning'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf_ss_vmaf'], ENCODE_COMMAND['svt_CRF_1lp_1p']],

        # 'svt_CRF_1lp_1p_tuning_11qp_iterations-3': [RC_VALUES['11qp_preset_tuning'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['svt_CRF_1lp_1p']],
        # 'svt_CRF_1lp_1p_tuning_11qp_iterations-2': [RC_VALUES['11qp_preset_tuning'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim'], ENCODE_COMMAND['svt_CRF_1lp_1p']],

        #2 pass method
        # 'SPIE2021_svt_2pass'       : [RC_VALUES['sw_ladder'],   RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale'], ENCODE_COMMAND['SPIE2021_svt_CRF_1lp_1p']],
        # 'SPIE2021_x265_2pass'      : [RC_VALUES['hw_ladder'], RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale'], ENCODE_COMMAND['SPIE2021_x265_CRF_1p']],
        # 'SPIE2021_x264_2pass'      : [RC_VALUES['hw_ladder'], RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale'], ENCODE_COMMAND['SPIE2021_x264_CRF_1p']],

        # 'SPIE2021_svt_vbr_ladder'       : [RC_VALUES['vbr_ladder'],   RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale'], ENCODE_COMMAND['svt_VBR_1lp_2p']],
        # 'SPIE2021_x265_2pass_fast_testing'      : [RC_VALUES['hw_ladder'], RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim'], ENCODE_COMMAND['SPIE2021_x265_CRF_1p']],
        # 'SPIE2021_x264_2pass_fast_testing'      : [RC_VALUES['hw_ladder'], RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim'], ENCODE_COMMAND['SPIE2021_x264_CRF_1p']],

        # 'SPIE2021_x265_2pass_psnr_ssim'      : [RC_VALUES['hw_ladder'], RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale_psnr_ssim'], ENCODE_COMMAND['SPIE2021_x265_CRF_1p']],
        # 'SPIE2021_x264_2pass_psnr_ssim'      : [RC_VALUES['hw_ladder'], RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2021_ffmpeg_rescale_psnr_ssim'], ENCODE_COMMAND['SPIE2021_x264_CRF_1p']],
              
        # 'SPIE2021_xyz_2pass_fast_testing'      : [RC_VALUES['hw_ladder'], RESOLUTION['SPIE2021_8bit'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim'],       ENCODE_COMMAND['SPIE2021_x264_CRF_1p']],
       
       
       #VBR
        # 'svt_contribution_1p_vbr'       : [RC_VALUES['contribution'],   None,   None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'],       ENCODE_COMMAND['svt_VBR_1lp_1p']],
        # 'svt_contribution_2p_vbr'       : [RC_VALUES['contribution'],   None,   None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'],       ENCODE_COMMAND['svt_VBR_1lp_2p']],

        # 'x264_contribution_1lp_1p_vbr': [RC_VALUES['contribution'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['x264_VBR_1lp_1p']],
        # 'x265_contribution_1lp_1p_vbr': [RC_VALUES['contribution'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['x265_VBR_1lp_1p']],
        # 'libaom_contribution_1lp_1p_vbr': [RC_VALUES['contribution'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['libaom_VBR_1lp_2p']],

        # 'x264_contribution_1lp_2p_vbr': [RC_VALUES['contribution'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['x264_VBR_1lp_2p']],
        # 'x265_contribution_1lp_2p_vbr': [RC_VALUES['contribution'], None, None, METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf'], ENCODE_COMMAND['x265_VBR_1lp_2p']],
        #M13 testing
        
        # "M13_testing_psnr_ssim" : [RC_VALUES['SPIE2021_svt_aom'],   RESOLUTION['M13_resolutions'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_community_tools'],       ENCODE_COMMAND['SPIE2021_svt_CRF_1lp_1p']],
        # "M13_testing_psnr_ssim_vmaf" : [RC_VALUES['SPIE2021_svt_aom'],   RESOLUTION['M13_resolutions'],   DOWNSCALE_COMMAND['SPIE2021_scaling'], METRIC_COMMAND['SPIE2020_ffmpeg_psnr_ssim_vmaf_community_tools'],       ENCODE_COMMAND['SPIE2021_svt_CRF_1lp_1p']],
