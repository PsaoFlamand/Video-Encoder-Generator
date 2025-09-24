import os
import sys
import re
import glob
import stat
import hashlib
import random
import subprocess
import binascii
import shutil
from multiprocessing import Pool
import multiprocessing
from datetime import date
from distutils.dir_util import copy_tree
import time
import argparse
# Sample usage: python PyFeaturesControl.py --test-name UnrestrictedMotionVector_%s_test --debug 0 --mode 0 --parameters "--fast-decode 1"


MAIN_CLIP_SET = "test_set_seq_table"

'''Change hardcoded bitstreams to current dir'''
CI_MODE = 1

'''Ignore custom presets that are in the feature repo dict'''
USE_TEST_SETTINGS_PRESETS_FOR_ALL = 0


'''Add special parameters to commands for testing (i.e. --pred-struct 1, --tune 0)'''
INSERT_SPECIAL_PARAMETERS = []


'''
$$$ Encoding settings $$$
presets: List of presets that each clip is be encoded at
qp_values: Rate control values for Constant Rate Factor (CRF) encodings
tbr_values: Rate control values for Target Bit Rate (TBR) encodings


$$$ Folder Preferences $$$
hard_coded_bitstreams: Bitstreams from individual tests are copied to this master bitstreams folder
stream_dir: This folder will be searched for the clips specified in the selected CLIP_SET


$$$ Run to Run Test Settings $$$
number_of_r2r_runs: Number of duplicated encodings to test for bitstream mismatches

preset_threshold_to_reduce: When this preset value is reached, The "reduced_number_of_r2r_runs" value is used


$$$ Execution Settings $$$
number_of_encoding_processes: Default number of jobs to run in parallel


'''


TEST_SETTINGS = {

    'encoder' : 'svt',
    'presets' : [5,6,8,10],
    'qp_values'  :  [20,32,47,55,63],
    'tbr_values' :  [7500, 5000, 2500, 1000],

    'hard_coded_bitstreams' : '/home/CI_Script/bitstreams',
    'hard_coded_logs': '/home/CI_Script/logs',
    'stream_dir' : '/home/inteladmin/stream',
    'r2r_stream_folder' : 'weekend_run_set',

    'number_of_r2r_runs' : 8,
    'reduced_number_of_r2r_runs' : 3,
    'preset_threshold_to_reduce' : 4,
    
    'number_of_encoding_processes' : 16,


    ### Dummy token below ###
    'intra_period'  : -1,
    'weekend_presets' : [0,1,2,3,4,5,6,7,8,9,10],
    
}




## To exclude certain test from the PSNR Check, as this test will have a mismatch amount of encoded frames compared to the original clip
PSNR_CHECK_EXCLUSION = {

'BufferedInput_test_', 
'MaxBitrate_test_VBR_1080p_rate_', 
'MaxBitrate_test_VBR_360p_rate_', 
'MaxBitrate_test_CRF_rate_', 
'OvershootPct_test', 
'tbr_abr_deviation_1080p_CBR_test', 
'tbr_abr_deviation_1080p_LD_VBR_test', 
'tbr_abr_deviation_1080p_VBR_test', 
'tbr_abr_deviation_360p_CBR_test', 
'tbr_abr_deviation_360p_LD_VBR_test', 
'tbr_abr_deviation_360p_VBR_test', 
'skip_30_frames_test',
'skip_30_frames_compare',
'skip_30_frames_compare_ref',

}

# To compare md5sums with previous tests
COMPARISON_TESTS = {
    "lp_comparison_test" : "non-lp_comparison_test",
    "avx512_comparison" : "avx2_comparison",
    "sse4_2_comparison" : "avx2_comparison",
    "c_comparison" : "avx2_comparison",
    "recon_compare" : "recon_test",
    "MBR_on_CRF_compare" : "MBR_off_CRF_compare",
    "skip_30_frames_compare" : "skip_30_frames_compare_ref",
    "config_compare" : "config_test"
}

'''
Generic FEATURES_COMMAND_REPOSITORY Format
[[<0>"--xxx"<0>],[<1>"x-xx"<1>],"<2>x<2>",[<3>x<3>],"<4>xx_xx_xx<4>",\
"<5>(/xx/xx/xx ./xxx --xx x --xx x --xx xxx) > xx/xx.xxx 2>&1 <5>",\
]

<0>: token to change
<1>: valid_range
<2>: Number of randomized Parameters | -1: Randomization OFF
<3>: Optional preset override
<4>: Test SET
<5>: sample_command
'''

FEATURES_COMMAND_REPOSITORY = {
                                    
    'ColorPrimariesTest_%s' :           [['--color-primaries'],[1,7,22],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --color-primaries 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'EnableAltRefs_%s_test' :           [['--enable-tf'],[0,2],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2  --enable-tf 0 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'SCM_%s_test' :                     [['--scm'],[2],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --scm 2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'mfmv_%s_test' :                    [['--enable-mfmv'],[1],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --enable-mfmv 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'StatReport_%s_test' :              [['--enable-stat-report'],[1],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --enable-stat-report 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'TileCol%s_test' :                  [['--tile-columns'],['0-4'],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 -n 5 --tile-columns 0 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'TileRow%s_test' :                  [['--tile-rows'],['0-6'],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 -n 5 --tile-rows 6 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'TransferCharacteristics_%s_test' : [['--transfer-characteristics'],[0,11,22],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --transfer-characteristics 22 --lp 1 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'UnrestrictedMotionVector_%s_test' :[['--rmv'],[1],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --rmv 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'hierarchical_level_%s_test' :      [['--hierarchical-levels'],[3,4,5],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --hierarchical-levels 4 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'irefresh_type_%s_test' :           [['--irefresh-type'],[1],-1,[8],'partyScene_test_set',\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 8 --input-depth 8 -n 1 -w 832 -h 480 --fps-num 50 --fps-denom 1 -q 9 --lp 1 --asm avx2 --keyint 150 --irefresh-type 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'IntraPeriod_%s_test' :             [['--keyint'],['0-120'],5,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --keyint 94 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'long_clip_%s_test' :               [['--keyint'],[60,-1],-1,[8],'long_clip_set',\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 8 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --keyint 60 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'CDEF_mode_%s_test' :                [['--enable-cdef'],[0,1],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --enable-cdef 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'ColorRangeTest_%s' :               [['--color-range'],[0,1],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --color-range 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'EnableOverlays_%s_test' :          [['--enable-overlays'],[1],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 11 --input-depth 10 -n 1 -w 1920 -h 1080 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --enable-overlays 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'MatrixCoefficientsTest_%s' :       [['--matrix-coefficients'],['1-14'],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --matrix-coefficients 14 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'RateControl_%s_test' :             [['--rc'],[1],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 --tbr 8000 --lp 1 --asm avx2 --rc 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'RestorationFilter_%s_test' :       [['--enable-restoration'],[1],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --enable-restoration 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'SuperResFixed_%s_test' :           [['--superres-denom', '--superres-kf-denom'],['8-16'],1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 11 --input-depth 10 -n 1 -w 1920 -h 1080 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --superres-denom 16 --superres-kf-denom 16 --superres-mode 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'SuperResQThres_%s_test' :          [['--superres-qthres', '--superres-kf-qthres'],['1-62'],1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 11 --input-depth 10 -n 1 -w 1920 -h 1080 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --superres-qthres 32 --superres-kf-qthres 32 --superres-mode 3 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'SuperRes_%s_test' :                [['--superres-mode'],[0,2,4],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 11 --input-depth 10 -n 1 -w 1920 -h 1080 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --superres-mode 2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'c_comparison' :                    [[],[],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm c -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'avx2_comparison' :                 [[],[],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'avx512_comparison' :               [[],[],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1  -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'loop_filter_%s_test' :             [['--enable-dlf'],[1],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --enable-dlf 0 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],

    'non-lp_comparison_test' :          [[],[],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 0 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'qp_test' :                         [[],[],-1,[],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 8 -n 1 -w 1920 -h 1080 --fps-num 30 --fps-denom 1 -q 9 --lp 1 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'sc_test' :                         [[],[],-1,[],'sc_test_set',\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 6 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'junk_encoding_test' :              [[],[],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 380 -h 150 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'lp_comparison_test' :              [[],[],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'mobisode_test' :                   [[],[],-1,[8],'mobisode_test_set',\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 8 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --enable-tpl-la 1 --keyint 59 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'recon_test' :                      [[],[],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --asm avx2 -o bitstreams/recon_M13_output_Q63.yuv --lp 1 --keyint 119 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin && rm bitstreams/recon_M13_output_Q63.yuv)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'sse4_2_comparison' :               [[],[],-1,[],MAIN_CLIP_SET,\
                                        '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm sse4_2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'FilmGrainDenoiseOff_test_%s' :     [['--film-grain'],['1-50'],2,[6,8,10],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 8 --input-depth 10 -n 1 -w 1920 -h 1080 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --film-grain 10 FILMGRAINDENOISEOFF -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin) > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'FilmGrain10bit_test_%s' :          [['--film-grain'],[10],-1,[],'filmgrain10bit_clips',\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 8 --input-depth 10 -n 1 -w 1920 -h 1080 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --film-grain 10 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin) > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'SpecifiedSocket_test_%s' :         [['--ss'],[1,-1],-1,[],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 10 -n 1 -w 1920 -h 1080 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --ss 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'scd_test_%s' :                     [['--scd'],[],-1,[],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --scd 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'RecodeLoopLevel_test_%s' :         [['--recode-loop'],[1,2],-1,[],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --recode-loop 1 --lp 1 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],

    'FAIL_RecodeLoopLevel_test_%s' :    [['--recode-loop'],['5-10000000'],2,[12],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --recode-loop 1 --lp 1 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'PredStructure_test_%s' :           [['--pred-struct'],[1],-1,[],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --pred-struct 0 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'PinSocket_test_%s' :               [['--pin'],[0],-1,[],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 10 -n 1 -w 1920 -h 1080 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --pin 0 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'MinQpAllowed_test_QP%s' :          [['--min-qp'],['16-62'],2,[],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --min-qp 43 --lp 1 --asm avx2 --rc 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'FAIL_MinQpAllowed_test_QP%s' :     [['--min-qp'],['63-800'],2,[12],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --min-qp 43 --lp 1 --asm avx2 --rc 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'MaxBitrate_test_VBR_rate_%s' :     [['--mbr'],['1-10000'],2,[],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --lp 1 --asm avx2 --mbr 2727071 --rc 1 FRAMES300 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'MaxBitrate_test_VBR_1080p_rate_%s' :     [['--mbr'],[10000],-1,[],'1080p_clipset',\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --lp 1 --asm avx2 --mbr 2727071 --rc 1 FRAMES300 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'MaxBitrate_test_VBR_360p_rate_%s' :     [['--mbr'],[1000],-1,[],'360p_clipset',\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --lp 1 --asm avx2 --mbr 2727071 --rc 1 FRAMES300 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'MaxBitrate_test_CRF_rate_%s' :     [['--mbr'],['1-10000'],2,[],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --mbr 2815040 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'LookAheadDistance_test_%s' :       [['--lookahead'],['0-120'],2,[],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --lookahead 69 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'FAIL_LookAheadDistance_test_%s' :   [['--lookahead'],['121-150'],2,[12],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --lookahead 69 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'Injector_test_%s' :                [['--inj-frm-rt'],['1-240'],2,[],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --inj 1 --inj-frm-rt 231 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'FAIL_Injector_test_%s' :          [['--inj-frm-rt'],['241-300'],2,[12],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --inj 1 --inj-frm-rt 231 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'HighDynamicRangeInput_test_%s' :   [['--enable-hdr'],[1],-1,[],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 10 -n 1 -w 1920 -h 1080 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --enable-hdr 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'fps_test_%s' :                     [['--fps'],['1-60'],2,[],'sc_test_set',\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --fps 33 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'FAIL_fps_test_%s' :                [['--fps'],['241-400'],2,[12],'sc_test_set',\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --fps 33 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'FixedQIndexOffset_test_set_%s' :   [[],[],-1,[],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --hierarchical-levels 3 --use-fixed-qindex-offsets 1 %s -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin) > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'FAIL_FixedQIndexOffset_test_set' :   [[],[],-1,[12],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --hierarchical-levels 3 --use-fixed-qindex-offsets 1 %s -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin) > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'BufferedInput_test_%s' :           [['--nb'],['1-60'],2,[],'bufferInput_clipset',\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --nb 39 -n 60 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'FAIL_BufferedInput_test_%s' :      [['--nb'],['60-4294967296'],2,[12],'bufferInput_clipset',\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --nb 39 -n 60 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'AdaptiveQuantization_test_%s' :    [['--aq-mode'],[0,1],-1,[],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --aq-mode 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
    'AdaptiveQuantization_tile_test_%s' :    [['--aq-mode', '--tile-rows', 'tile-columns'],[1],-1,[],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --aq-mode 1 --tile-rows 1 --tile-columns 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                        ],
# We dont have a 400 clipset yet
   # 'EncoderColorFormat_test_yuv_400' : [['--color-format'],[0],[],-1,[],'400_pixel_fmt_set',\
                                        # '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --color-format 0 --lp 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                       # ],
    'EncoderColorFormat_test_yuv_422_%s' :  [['--color-format'],[2],-1,[],'422_pixel_fmt_set',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --color-format 2 --lp 1 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'EncoderColorFormat_test_yuv_444_%s' :  [['--color-format'],[3],-1,[],'444_pixel_fmt_set',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --color-format 3 --lp 1 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'Profile_test_444_%s' :                 [['--profile'],[1],-1,[],'444_pixel_fmt_set',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --profile 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'Profile_test_422_%s' :                 [['--profile'],[2],-1,[],'422_pixel_fmt_set',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --profile 2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'ContentLight_test_%s' :                [[],[],-1,[8,10],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 %s -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'MasteringDisplay_test_set_%s' :        [[],[],-1,[],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 %s -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'ClientBufferSize_test_%s' :            [['--buf-sz'],['20-10000'],2,[],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 12 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --lp 1 --asm avx2 --buf-sz 2757819766150327125 --rc 2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'FAIL_ClientBufferSize_test_%s' :            [['--buf-sz'],['4294967296-4295967296'],2,[12],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 12 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --lp 1 --asm avx2 --buf-sz 2757819766150327125 --pred-struct 1 --rc 2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'ClientOptimalBufferSize_test_%s' :     [['--buf-optimal-sz'],['20-10000'],1,[],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 12 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --lp 1 --asm avx2 --buf-optimal-sz 6751172717159641070 --pred-struct 1 --rc 2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'FAIL_ClientOptimalBufferSize_test_%s' :     [['--buf-optimal-sz'],['4294967296-4295967296'],1,[12],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 12 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --lp 1 --asm avx2 --buf-optimal-sz 6751172717159641070 --pred-struct 1 --rc 2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'ClientInitialBufferSize_test_%s' :      [['--buf-initial-sz'],['20-10000'],1,[],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 12 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --lp 1 --asm avx2 --buf-initial-sz 5933371435525747271 --pred-struct 1 --rc 2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'FAIL_ClientInitialBufferSize_test_%s' :  [['--buf-initial-sz'],['4294967296-4295967296'],1,[12],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 12 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --lp 1 --asm avx2 --buf-initial-sz 5933371435525747271 --rc 2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'BitstreamLevel_test_%s' :               [['--level'],[2.0,2.1,2.2,2.3,3.0,3.1,3.2,3.3,4.0,4.1,4.2,4.3,5.0,5.1,5.2,5.3,6.0,6.1,6.2,6.3,7.0,7.1,7.2,7.3],2,[],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --level 2.3 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'FAIL_BitstreamLevel_test_%s' :         [['--level'],[7.4,10.1,30.2,40.7,50.3,92.5,104.2,120.0],2,[12],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --level 2.3 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'CBR_VBR_Bias_test_%s' :                 [['--bias-pct'],['0-100'],1,[],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --bias-pct 38 --lp 1 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'FAIL_CBR_VBR_Bias_test_%s' :           [['--bias-pct'],['101-10000000'],1,[12],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --bias-pct 38 --lp 1 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'MaxSectionPct_test_%s' :                [['--maxsection-pct'],['0-100'],2,[],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --maxsection-pct 6 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'FAIL_MaxSectionPct_test_%s' :                [['--maxsection-pct'],['4294967296-42959672960'],2,[12],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --maxsection-pct 6 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'MinSectionPct_test_%s' :                [['--minsection-pct'],['0-100'],2,[],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --minsection-pct 15 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'FAIL_MinSectionPct_test_%s' :          [['--minsection-pct'],['4294967296-42959672960'],2,[12],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --minsection-pct 15 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'CRFMode_test_%s' :                      [['--crf'],['1-63'],2,[],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 12 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --crf 7 --lp 1 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'FAIL_CRFMode_test_%s' :                [['--crf'],['64-120000'],2,[12],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 12 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --crf 7 --lp 1 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'MultiPass_test_%s' :                    [[],[],-1,[],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --rc 1 --tbr 7500 --lp 1 --asm avx2 --pass 1  -i /folder/clip.yuv  --stats bitstreams/svt_M9_clip_Q9.stat -b bitstreams/svt_M9_clip_Q9.bin && \
./SvtAv1EncApp --preset 9 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --rc 1 --tbr 7500 --lp 1 --asm avx2 --pass 2  -i /folder/clip.yuv  --stats bitstreams/svt_M9_clip_Q9.stat -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
                                            
   'OvershootPct_test%s' :                  [['--overshoot-pct'],['8-20'],2,[],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 13 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25000 --fps-denom 1000 --tbr 1000 FRAMES300 --rc 1 --lp 1 --overshoot-pct 12 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'FAIL_OvershootPct_test%s' :            [['--overshoot-pct'],['101-120000'],2,[12],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 13 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25000 --fps-denom 1000 --tbr 1000 FRAMES300 --rc 1 --lp 1 --overshoot-pct 12 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'UndershootPct_test%s' :                 [['--undershoot-pct'],['5-100'],2,[],'undershoot_clipset',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 13 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25000 --fps-denom 1000 --tbr 1000 --rc 1 --lp 1 --undershoot-pct 49 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'FAIL_UndershootPct_test%s' :           [['--undershoot-pct'],['101-120000'],2,[12],'undershoot_clipset',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 13 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25000 --fps-denom 1000 --tbr 1000 --rc 1 --lp 1 --undershoot-pct 49 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'tbr_abr_deviation_test' :              [[],[],-1,[8,10],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 12 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --lp 1 --asm avx2 FRAMES300 --rc 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'tbr_abr_deviation_1080p_VBR_test' :    [[],[],-1,[],"1080p_clipset",\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 12 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --lp 1 --asm avx2 FRAMES300 --rc 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'tbr_abr_deviation_360p_VBR_test' :     [[],[],-1,[],"360p_clipset",\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 12 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --lp 1 FRAMES300 --asm avx2 --rc 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'tbr_abr_deviation_1080p_LD_VBR_test' : [[],[],-1,[],"1080p_clipset",\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 12 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --lp 1 FRAMES300 --asm avx2 --rc 1 --pred-struct 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'tbr_abr_deviation_360p_LD_VBR_test' :  [[],[],-1,[],"360p_clipset",\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 12 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --lp 1 FRAMES300 --asm avx2 --rc 1 --pred-struct 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'tbr_abr_deviation_1080p_CBR_test' :    [[],[],-1,[],"1080p_clipset",\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 12 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --lp 1 FRAMES300 --asm avx2 --pred-struct 1 --rc 2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'tbr_abr_deviation_360p_CBR_test' :     [[],[],-1,[],"360p_clipset",\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 12 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --lp 1 FRAMES300 --asm avx2 --pred-struct 1 --rc 2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'high_res_test' :                       [[],[],-1,[8,9,10],'high_res_clipset',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 8 -n 1 -w 1920 -h 1080 --fps-num 30 --fps-denom 1 -q 9 --lp 1 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],

    '1lp-1p-10bit_r2r_test' :                [[],[],-1,lambda mode : [0,1,2,5,6,8,10] if mode == '1' else [5,6,8,10],'10bit',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 11 --passes 1 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --keyint 98 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv -b bitstreams/svt_M10_output_Q59.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   '1lp-1p-8bit_r2r_test' :                 [[],[],-1,lambda mode : [0,1,2,5,6,8,10] if mode == '1' else [5,6,8,10],'8bit',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 11 --passes 1 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --keyint 98 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv -b bitstreams/svt_M10_output_Q59.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'nonlp-1p-10bit_r2r_test' :              [[],[],-1,lambda mode : [0,1,2,5,6,8,10] if mode == '1' else [5,6,8,10],'10bit',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 10 --passes 1 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --keyint -1 --enable-tpl-la 1 -i /folder/clip.yuv -b bitstreams/svt_M10_output_Q59.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'nonlp-1p-8bit_r2r_test' :               [[],[],-1,lambda mode : [0,1,2,5,6,8,10] if mode == '1' else [5,6,8,10],'8bit',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 10 --passes 1 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --keyint -1 --enable-tpl-la 1 -i /folder/clip.yuv -b bitstreams/svt_M10_output_Q59.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'VBR-1lp-1p-8bit_r2r_test' :             [[],[],-1,lambda mode : [0,1,2,5,6,8,10] if mode == '1' else [5,6,8,10],'8bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --passes 1 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --rc 1 --tbr 1000 --keyint 8 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'VBR-1lp-1p-10bit_r2r_test' :            [[],[],-1,lambda mode : [0,1,2,5,6,8,10] if mode == '1' else [5,6,8,10],'10bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --passes 1 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --rc 1 --tbr 1000 --keyint 8 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'VBR-1lp-2p-8bit_r2r_test' :             [[],[],-1,lambda mode : [0,1,2,5,6,8] if mode == '1' else [5,6,8],'8bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 11 --passes 2 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --irefresh-type 2 --rc 1 --tbr 7500 --keyint 97 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv --stats bitstreams/svt_M4_output_TBR_1000Kbps.stat -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'VBR-1lp-2p-10bit_r2r_test' :            [[],[],-1,lambda mode : [0,1,2,5,6,8] if mode == '1' else [5,6,8],'10bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 11 --passes 2 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --irefresh-type 2 --rc 1 --tbr 7500 --keyint 97 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv --stats bitstreams/svt_M4_output_TBR_1000Kbps.stat -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   '1lp-2p-8bit_r2r_test' :                 [[],[],-1,lambda mode : [0,1,2,5,6,8,10] if mode == '1' else [5,6,8,10],'8bit',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --passes 2 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --irefresh-type 2 -q 47 --keyint 114 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv --stats bitstreams/svt_M4_output_TBR_1000Kbps.stat -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   '1lp-2p-10bit_r2r_test' :                [[],[],-1,lambda mode : [0,1,2,5,6,8,10] if mode == '1' else [5,6,8,10],'10bit',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --passes 2 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --irefresh-type 2 -q 47 --keyint 114 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv --stats bitstreams/svt_M4_output_TBR_1000Kbps.stat -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'CBR-1lp-1p-8bit_r2r_test' :             [[],[],-1,lambda mode : [0,1,2,5,6,8,10] if mode == '1' else [5,6,8,10],'8bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --passes 1 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --pred-struct 1 --rc 2 --tbr 1000 --keyint 8 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'CBR-1lp-1p-10bit_r2r_test' :            [[],[],-1,lambda mode : [0,1,2,5,6,8,10] if mode == '1' else [5,6,8,10],'10bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --passes 1 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1  --pred-struct 1 --rc 2 --tbr 1000 --keyint 8 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'CBR-1lp-2p-8bit_r2r_test' :             [[],[],-1,lambda mode : [0,1,2,5,6,8,10] if mode == '1' else [5,6,8,10],'8bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 11 --passes 2 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --irefresh-type 2 --rc 2 --tbr 7500 --keyint 97 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv --stats bitstreams/svt_M4_output_TBR_1000Kbps.stat -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'CBR-1lp-2p-10bit_r2r_test' :            [[],[],-1,lambda mode : [0,1,2,5,6,8,10] if mode == '1' else [5,6,8,10],'10bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 11 --passes 2 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --irefresh-type 2 --rc 2 --tbr 7500 --keyint 97 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv --stats bitstreams/svt_M4_output_TBR_1000Kbps.stat -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
                                            
                                            
   '1lp-1p-10bit-MR_r2r_test' :                [[],[],-1,lambda mode : [-1] if mode == '1' else [3],'10bit',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 11 --passes 1 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --keyint 98 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv -b bitstreams/svt_M10_output_Q59.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   '1lp-1p-8bit-MR_r2r_test' :                 [[],[],-1,lambda mode : [-1] if mode == '1' else [3],'8bit',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 11 --passes 1 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --keyint 98 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv -b bitstreams/svt_M10_output_Q59.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'nonlp-1p-10bit-MR_r2r_test' :              [[],[],-1,lambda mode : [-1] if mode == '1' else [3],'10bit',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 10 --passes 1 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --keyint -1 --enable-tpl-la 1 -i /folder/clip.yuv -b bitstreams/svt_M10_output_Q59.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'nonlp-1p-8bit-MR_r2r_test' :               [[],[],-1,lambda mode : [-1] if mode == '1' else [3],'8bit',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 10 --passes 1 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --keyint -1 --enable-tpl-la 1 -i /folder/clip.yuv -b bitstreams/svt_M10_output_Q59.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'VBR-1lp-1p-8bit-MR_r2r_test' :             [[],[],-1,lambda mode : [-1] if mode == '1' else [3],'8bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --passes 1 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --rc 1 --tbr 1000 --keyint 8 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'VBR-1lp-1p-10bit-MR_r2r_test' :            [[],[],-1,lambda mode : [-1] if mode == '1' else [3],'10bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --passes 1 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --rc 1 --tbr 1000 --keyint 8 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'VBR-1lp-2p-8bit-MR_r2r_test' :             [[],[],-1,lambda mode : [-1] if mode == '1' else [3],'8bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 11 --passes 2 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --irefresh-type 2 --rc 1 --tbr 7500 --keyint 97 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv --stats bitstreams/svt_M4_output_TBR_1000Kbps.stat -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'VBR-1lp-2p-10bit-MR_r2r_test' :            [[],[],-1,lambda mode : [-1] if mode == '1' else [3],'10bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 11 --passes 2 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --irefresh-type 2 --rc 1 --tbr 7500 --keyint 97 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv --stats bitstreams/svt_M4_output_TBR_1000Kbps.stat -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   '1lp-2p-8bit-MR_r2r_test' :                 [[],[],-1,lambda mode : [-1] if mode == '1' else [3],'8bit',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --passes 2 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --irefresh-type 2 -q 47 --keyint 114 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv --stats bitstreams/svt_M4_output_TBR_1000Kbps.stat -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   '1lp-2p-10bit-MR_r2r_test' :                [[],[],-1,lambda mode : [-1] if mode == '1' else [3],'10bit',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --passes 2 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --irefresh-type 2 -q 47 --keyint 114 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv --stats bitstreams/svt_M4_output_TBR_1000Kbps.stat -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'CBR-1lp-1p-8bit-MR_r2r_test' :             [[],[],-1,lambda mode : [-1] if mode == '1' else [3],'8bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --passes 1 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --pred-struct 1 --rc 2 --tbr 1000 --keyint 8 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'CBR-1lp-1p-10bit-MR_r2r_test' :            [[],[],-1,lambda mode : [-1] if mode == '1' else [3],'10bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --passes 1 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --pred-struct 1 --rc 2 --tbr 1000 --keyint 8 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'CBR-1lp-2p-8bit-MR_r2r_test' :             [[],[],-1,lambda mode : [-1] if mode == '1' else [3],'8bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 11 --passes 2 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --pred-struct 1 --irefresh-type 2 --rc 2 --tbr 7500 --keyint 97 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv --stats bitstreams/svt_M4_output_TBR_1000Kbps.stat -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'CBR-1lp-2p-10bit-MR_r2r_test' :            [[],[],-1,lambda mode : [-1] if mode == '1' else [3],'10bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 11 --passes 2 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --pred-struct 1 --irefresh-type 2 --rc 2 --tbr 7500 --keyint 97 --enable-tpl-la 1 --lp 1 -i /folder/clip.yuv --stats bitstreams/svt_M4_output_TBR_1000Kbps.stat -b bitstreams/svt_M4_output_TBR_1000Kbps.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
   'CBR_ClientBufferSize_test_%s' :         [['--buf-sz'],[1000],-1,[],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 12 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --lp 1 --asm avx2 --buf-sz 2757819766150327125  --pred-struct 1 --rc 2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'resize_mode_0_r2r_test' :                [[],[],-1,[],'8bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 6 --keyint -1 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --resize-mode 0 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'resize_mode_1_r2r_test' :                [[],[],-1,[],'8bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 6 --keyint -1 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --resize-mode 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'resize_mode_2_r2r_test' :                [[],[],-1,[],'8bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 6 --keyint -1 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --resize-mode 2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'resize_mode_3_r2r_test' :                [[],[],-1,[],'8bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 6 --keyint -1 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --resize-mode 3 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'resize_mode_4_r2r_test' :                [[],[],-1,[],'8bit_VBR',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 6 --keyint -1 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --resize-mode 4 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'FAIL_resize_mode_test_%s' :            [['--resize-mode'],['5-500'],1,[12],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 6 --keyint -1 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --resize-mode 0 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'SuperRes_memory_test' :                [[],[],-1,[12],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 6 --keyint 20 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 --asm avx2 --rc 1 --tbr 1000 --lp 1 --superres-mode 1  -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'Issue1939_OvershootPct_test' :         [[],[],-1,[10],'issue1939',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 6 --keyint 155 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 --asm avx2 --rc 1 --tbr 200 --irefresh-type 2 --enable-tpl-la 1 --lp 0 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'Issue1959_OvershootPct_test' :         [[],[],-1,[10],'1080p_clipset',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 6 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 --asm avx2 --rc 2 --tbr 1000 --lp 1 --pred-struct 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    '1838_Hang_Test' :                      [[],[],-1,[],'hang_test_clips',\
                                            '''(/usr/bin/time --verbose ./SvtAv1EncApp  --preset 12 -q 20 --lp 1 --scd 1 --keyint 240  -i  /folder/clip.yuv  -b  bitstreams/svt_M9_clip_Q9.bin )  > bitstreams/svt_M9_clip_Q9.txt 2>&1 ''',\
                                            ],
    'gop_64_Encoder_Hang_Issue1708' :       [[],[],-1,[],'4ss_clips_for_hang_check',\
                                            '''(/usr/bin/time --verbose ./SvtAv1EncApp --preset 3 -q 20 --irefresh-type 2 --lp 1 --scd 0 -n 128 --enable-tpl-la 1 --keyint 63 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1 ''',\
                                            ],
    'rc_on_hang_check_HL4' :                [[],[],-1,[],'4ss_clips_for_hang_check',\
                                            '''(/usr/bin/time --verbose ./SvtAv1EncApp --preset 4 --tbr 2500 --frames 120 --lp 1 --hierarchical-levels 4 --keyint 47 --rc 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'MaxQpAllowed_test_QP%s' :              [['--max-qp'],['16-62'],2,[],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --max-qp 43 --lp 1 --asm avx2 --rc 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'FAIL_MaxQpAllowed_test_QP%s' :         [['--max-qp'],['63-800'],2,[12],MAIN_CLIP_SET,\
                                         '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --tbr 1000 --max-qp 43 --lp 1 --asm avx2 --rc 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'recon_compare' :                       [[],[],-1,[],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --asm avx2 --lp 1 --keyint 119 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'MBR_on_CRF_compare' :                  [[],[],-1,[],"360p_clipset",\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 --mbr 5000000 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'MBR_off_CRF_compare' :                  [[],[],-1,[],"360p_clipset",\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 -q 9 --lp 1 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],

    'CrowdRun_MBR_deviation_test' :         [[],[],-1,[10],"capped_CRF_deviation_clipset",\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -n 1 -w 640 -h 360 --fps-num 25 --fps-denom 1 --crf 9 --lp 1 --mbr 10000 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'skip_30_frames_test' :                 [[],[],-1,[], "60f_clipset",\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -w 640 -h 360 --fps-num 25 --fps-denom 1 --asm avx2 --skip 30 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
                                            
    'skip_30_frames_compare' :              [[],[],-1,[], "skip_compare_ON",\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -w 640 -h 360 --fps-num 25 --fps-denom 1 --asm avx2 --skip 30 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'skip_30_frames_compare_ref' :          [[],[],-1,[], "skip_compare_OFF",\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -w 640 -h 360 --fps-num 25 --fps-denom 1 --asm avx2 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
                                
    'FAIL_skip_60_frames_test' :            [[],[],-1,[], "60f_clipset",\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 4 --input-depth 8 -w 640 -h 360 --fps-num 25 --fps-denom 1 --asm avx2 --skip 60 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
                                            
    'config_compare' :                      [[],[],-1,[],"60f_clipset",\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -i /folder/clip.yuv -c /home/CI_Script/scripts/config_params.cfg -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'config_test' :                         [[],[],-1,[],"60f_clipset",\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 --asm avx2 --lp 1 --tbr 10000 --rc 1 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'StartupMgSize_%s_test' :               [['--startup-mg-size'],[2,3,4],-1,lambda mode : [0,1,2,3,4,5,6,7] if mode == '1' else [4,5,6,7,8],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2  --startup-mg-size 0 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'TemporalFilteringStrength_%s_test' :               [['--tf-strength'],[0,2,4],-1,[],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2  --tf-strength 0 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'VarianceBoost_%s_test' :               [['--variance-boost-curve'],[1,2],-1,[],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2  --variance-boost-curve 0 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'LuminanceQpBias_%s_test' :               [['--luminance-qp-bias'],[25,50,100],-1,[],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2  --luminance-qp-bias 0 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'Sharpness_%s_test' :                   [['--sharpness'],[-7,7],-1,[],MAIN_CLIP_SET,\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2  --sharpness 0 -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'all_intra_test' :                     [[],[],-1,[],'all_intra',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --keyint 1  -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],
    'still_image_test' :                   [[],[],-1,[],'still_image',\
                                            '''(/usr/bin/time --verbose   ./SvtAv1EncApp --preset 9 --input-depth 10 -n 1 -w 1280 -h 720 --fps-num 60 --fps-denom 1 -q 9 --lp 1 --asm avx2 --avif 1  -i /folder/clip.yuv -b bitstreams/svt_M9_clip_Q9.bin)  > bitstreams/svt_M9_clip_Q9.txt 2>&1''',\
                                            ],                                                                                                                                                                                                                                                                        
    }
    
'''
Generic FEATURES_COMMAND_REPOSITORY Format
[[<0>"--xxx"<0>],[<1>"x-xx"<1>],"<2>x<2>",[<3>x<3>],"<4>xx_xx_xx<4>",\
"<5>(/xx/xx/xx ./xxx --xx x --xx x --xx xxx) > xx/xx.xxx 2>&1 <5>",\
]

<0>: token to change
<1>: valid_range
<2>: Number of randomized Parameters | -1: Randomization OFF
<3>: Optional preset override
<4>: Test SET
<5>: sample_command

'''




def main():
    commands_with_errors = dict()
    tbr_abr_deviation_log = dict()
    r2r_command_log = dict()
    psnr_log = dict()
    allowable_percent_deviation = 20

    r2r_log = dict()
    decode_logs = list()
    
    '''
    Test Execution

    This function executes the test workflow, including encoding and decoding commands, error checking, and test result collection.
    It performs the following steps:
    1. Sleeps for 60 seconds.
    2. Checks if `USE_os.getcwd()_FOR_OUTPUT` flag is set and updates the path to the hard-coded bitstreams folder accordingly.
    3. Parses command-line arguments to retrieve the feature to test, debug mode flag, parameters, and mode.
    4. Sets file permissions using the `execute_command_helper` function.
    5. Sets the path to the local bitstreams folder.
    6. If the test is a "config_compare" test, writes the configuration parameters to the test folder.
    7. Retrieves test information from the features repository, including tokens to change, valid parameter range, randomize values flag, preset override, main clip set, and sample command.
    8. Determines the values to test based on the valid parameter range and randomize values flag.
    9. Sets the "r2r_mode" flag based on whether the test includes 'r2r_test'.
    10. If debug mode is enabled, modifies the test name accordingly.
    11. Retrieves the encoding and decoding commands based on the provided parameters.
    12. If in "r2r_mode", creates the run folders for r2r.
    13. Randomizes intraperiod QP values in the encoding commands if in "r2r_mode".
    14. Writes the encoding and decoding commands to files for execution using the old parallel method.
    15. Executes the encoding commands in parallel using the `run_parallel` function.
    16. Checks for bad decodes in the specified source directory.
    17. Executes the decoding and metric commands in parallel using the `execute_parallel_commands` function.
    18. Copies the bitstream output files from the source directory to the hard-coded directory.
    19. Prints debug information.

    '''

    # Step 1: Sleep for 60 seconds
    if CI_MODE:
        time.sleep(60)
    os.system('./SvtAv1EncApp --version')    
    # Step 2: Update path to hard-coded bitstreams folder if USE_os.getcwd()_FOR_OUTPUT flag is set
    if not CI_MODE:
        TEST_SETTINGS['hard_coded_bitstreams'] = os.path.join(os.getcwd(), 'bitstreams')
    
    # Step 3: Parse command-line arguments
    test_name, debug, parameters, mode, cpu_use_divisor = parse_command_line()
    if parameters:
        INSERT_SPECIAL_PARAMETERS.append(parameters)
    # Step 4: Set file permissions using execute_command_helper function
    execute_command_helper(('chmod 770 -R *', os.getcwd()))

    # Step 5: Set path to local bitstreams folder
    bitstream_folder = os.path.join(os.getcwd(), 'bitstreams')

    # Step 6: Write configuration parameters to the test folder if the test is a "config_compare" test
    if "config_compare" in test_name:
        write_config_params()

    # Step 7: Retrieve test information from the features repository
    tokens_to_change, valid_parameter_range, randomize_values, preset_override, main_clip_set, sample_command = get_feature_settings(test_name, mode, debug, cpu_use_divisor)
    print('Running with {} parallel processes'.format(TEST_SETTINGS['number_of_encoding_processes']))
    # print('folder to backup to {}'.format(TEST_SETTINGS['hard_coded_bitstreams']))
    print('Testing presets: {}'.format(TEST_SETTINGS['presets']))
    # Step 8: Determine values to test based on valid parameter range and randomize values flag
    if valid_parameter_range:
        values_to_test = get_values_to_test(valid_parameter_range, randomize_values)
    else:
        values_to_test = []

    # Step 9: Set "r2r_mode" flag based on whether the test includes 'r2r_test'
    r2r_mode = 'r2r_test' in test_name

    # Step 10: Modify test name if debug mode is enabled or there are special parameters
    if debug == '1':
        test_name = test_name + "_debug"
    if parameters and "fast-decode" in parameters:
        test_name = test_name + "_fast_decode"
    elif parameters and "pred-struct" in parameters:
        test_name = test_name + "_low_delay"

    # Step 11: Retrieve encoding and decoding commands
    encoding_commands, decoding_commands = get_commands(values_to_test, test_name, sample_command, tokens_to_change, r2r_mode)

    # Step 12: Create run folders for r2r if in "r2r_mode"
    if r2r_mode:
        create_r2r_run_folders()
        # Step 13: Randomize intraperiod QP values in encoding commands if in "r2r_mode"
        encoding_commands = randomize_intraperiod_qp(encoding_commands)


    # Step 14: Write encoding and decoding commands to files for execution using old parallel method
    encode_commands_file = write_commands_to_file('encode-{}'.format(test_name), encoding_commands)
    decode_commands_file = write_commands_to_file('decode-{}'.format(test_name), decoding_commands)

    # Step 15: Execute encoding commands in parallel
    run_parallel(TEST_SETTINGS['number_of_encoding_processes'], encode_commands_file, test_name)

    # Step 16: Check for bad decodes in the specified source directory
    check_bad_decode(test_name,bitstream_folder)

    # Step 17: Execute decoding and metric commands in parallel
    TEST_SETTINGS['number_of_encoding_processes'] = TEST_SETTINGS['number_of_encoding_processes'] // 12    
    if TEST_SETTINGS['number_of_encoding_processes'] == 0:
        TEST_SETTINGS['number_of_encoding_processes'] = 1
    execute_parallel_commands(int(TEST_SETTINGS['number_of_encoding_processes']), decoding_commands, os.getcwd())

    # Step 18: Copy bitstream output files from source directory to hard-coded directory if its a comparison test
    if test_name in COMPARISON_TESTS.values():
        test_path = os.path.join(bitstream_folder, test_name)
        destination_path = os.path.join(TEST_SETTINGS['hard_coded_bitstreams'],test_name)
        if not os.path.isdir(destination_path):
            os.mkdir(destination_path)
        copy_tree(test_path,destination_path)

    # Step 19: Print debug information
    print('Encoding_command: {}'.format(encoding_commands[0]))
    # print('r2r_mode', r2r_mode)
    # print('encode_commands_file', encode_commands_file)



    '''Test Collection
    20. Performs test collection steps, including error checking, deviation analysis, and PSNR check.
    21. Writes the deviation log.
    22. Determines the overall test result based on the collected data and error logs.
    23. Saves logs if possible.
    24. Exits with an error code if the test did not pass, otherwise prints a success message.
    25. Sets file permissions for the hard-coded bitstreams folder.
    '''

    # Step 20: Perform test collection steps
    print('\n%s TEST RESULTS %s\n' % ('*' * 5, '*' * 5))
    print('Testing Feature: %s' % test_name)

    # Step 21: Perform MD5 difference check if test is the second piece of a comparison test
    mod_test_folder = os.path.join(bitstream_folder, test_name)
    ref_test_folder = get_ref_test_folder(test_name)
    if ref_test_folder:
        r2r_log, r2r_command_log = check_for_md5_differences([mod_test_folder, ref_test_folder])

    # Step 22: Get feature folders and loop through them
    test_name = test_name.split('%s')[0]  # Get root of feature name
    feature_folders = get_feature_folders(bitstream_folder)
    print('collecting {}'.format(test_name))
    for feature_folder in feature_folders:
        if not is_valid_feature_folder(test_name, feature_folder,debug):
            continue
        feature_logs, feature_txts, feature_bins, decode_md5 = get_feature_files(feature_folder)
        valid_files = is_valid_encoding_files(test_name, feature_folder, feature_logs, feature_txts, feature_bins)
        if not valid_files and 'FAIL' in test_name: 
            print('Test Passed Successfully!')
            print('\n\n------------------------------------------------------------------\n\n')        
            sys.exit(0)
        elif not valid_files:
            print('Test Failed')
            sys.exit(-1)
            
        # Step 23: Check encoding and metric logs for indications of crashes
        print('\n\nChecking {} For Crashes\n\n'.format(feature_folder))
        commands_with_errors_curr = check_for_crashes(feature_logs, feature_txts, feature_folder)
        commands_with_errors.update(commands_with_errors_curr)

        # Step 24: Put features through their own collection processes as needed
        if 'r2r_test' in test_name:
            r2r_log, r2r_command_log_curr = check_for_md5_differences([feature_folder])
            r2r_command_log.update(r2r_command_log_curr)

        if is_deviation_test(test_name):
            deviation_dict = collect_allowable_deviation_data(feature_txts)
            tbr_abr_deviation_log.update(get_deviation_data(deviation_dict))

        if is_psnr_check_applicable(test_name):
            psnr_log.update(collect_psnr_data(feature_folder))

    # Step 25: Write deviation log
    write_deviation_log(test_name, tbr_abr_deviation_log)

    # Step 26: Determine overall test result based on collected data and error logs
    test_passed = pass_fail_feature(r2r_log, r2r_command_log, tbr_abr_deviation_log, psnr_log,
                                    commands_with_errors, decode_logs)

    try:
        # Step 27: Save logs if possible
        save_logs(bitstream_folder)
    except Exception as e:
        print("Logs were not successfully copied due to the following error: {}".format(e))

    # Step 28: Exit with error code if test did not pass, otherwise print success message
    if "FAIL" in test_name:
        test_passed = not test_passed

    if not test_passed:
        sys.exit(-1)
    else:
        print('Test Passed Successfully!')
        print('\n\n------------------------------------------------------------------\n\n')

    # Step 29: Set file permissions for the hard-coded bitstreams folder
    execute_command_helper(('chmod 770 -R *', TEST_SETTINGS['hard_coded_bitstreams']))


def parse_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--test-name', help='Feature to test')
    parser.add_argument('-d', '--debug', help='Debug Mode')    
    parser.add_argument('-p', '--parameters', help='Add special parameters')
    parser.add_argument('-m', '--mode', help='0:Nightly | 1: Weekend')
    parser.add_argument('-n', '--cpu_use_divisor', help='Divides machine cores')
    
    args = parser.parse_args()
    return args.test_name, args.debug, args.parameters, args.mode, args.cpu_use_divisor



def save_logs(bitstream_folder):

    DATE = str(date.today())  # Get the current date
    
    if date.today().hour < 12:
        # If the current hour is before 12 PM, consider the tests as part of the previous day
        DATE = date.today() - timedelta(days=1)
    log_folder = os.path.join(TEST_SETTINGS['hard_coded_logs'], DATE)

    if not os.path.isdir(log_folder):
        os.makedirs(log_folder)

    for test in os.listdir(bitstream_folder):
        dest = os.path.join(log_folder, test)
        source = os.path.join(bitstream_folder, test)
        if not os.path.exists(dest):
            os.makedirs(dest)
        if not os.path.isdir(source):
            continue
        if "r2r_test" in source:
            for folder in os.listdir(source):
                if not os.path.isdir(os.path.join(source, folder)):
                    continue
                sub_dest = os.path.join(dest, folder)
                if not os.path.exists(sub_dest):
                    os.makedirs(sub_dest)
                sub_source = os.path.join(source, folder)
                for file in os.listdir(sub_source):
                    if file.endswith((".txt", ".log", ".md5log")):
                            log = os.path.join(sub_source, file)
                            shutil.copy(log, sub_dest)
        else:
            for file in os.listdir(source):
                if file.endswith((".txt", ".log", ".md5log")):
                        log = os.path.join(source, file)
                        shutil.copy(log, dest)

                    
def write_config_params():
    config_params_file = '/home/CI_Script/scripts/config_params.cfg'
    with open(config_params_file, 'w') as config_params:
        config_params.write("RateControlMode: 1\n")
        config_params.write("TargetBitRate  : 10000\n")
        config_params.write("Asm			: avx2\n")
        config_params.write("LevelOfParallelism			: 					1\n")


def get_feature_settings(test_name, mode, debug, cpu_use_divisor):
    tokens_to_change, valid_parameter_range, randomize_values, preset_override, main_clip_set, sample_command = FEATURES_COMMAND_REPOSITORY[test_name]

    QP_test_QPs = [10,20,23,26,32,37,43,48,51,57,63]
    RateControl_tests_TBRs = [1000,2000,4000,6000,8000]

    '''Gather all of the clip locations of those specified in the clip set dictionary'''
    TEST_SETTINGS['clip_list'] = find_test_set_clips_on_machine(test_name,main_clip_set)
    
    if cpu_use_divisor:
        TEST_SETTINGS['number_of_encoding_processes'] = int(cpu_use_divisor)
    
    '''Change the QP test values for certain features'''
    if test_name == 'qp_test':
        TEST_SETTINGS['qp_values'] = QP_test_QPs
    elif 'r2r_test' in test_name:
        TEST_SETTINGS['qp_values'] = random.sample(range(45,63), 2)
    elif 'CrowdRun' in test_name:
        TEST_SETTINGS['qp_values'] = [40]
        
    '''Change the TBR test values for certain features'''
    if test_name == 'RateControl_%s_test':
        TEST_SETTINGS['tbr_values'] = RateControl_tests_TBRs
    elif 'tbr_abr_deviation_1080p' in test_name:
        TEST_SETTINGS['tbr_values'] = random.sample(range(1000,10000), 2)
    elif 'tbr_abr_deviation_360p' in test_name:
        TEST_SETTINGS['tbr_values'] = random.sample(range(500,1000), 2)
    elif test_name == 'MaxBitrate_test_VBR_1080p_rate_%s':
        tbr_mbr_values = random.sample(range(1002,10000), 1)
        valid_parameter_range = tbr_mbr_values 
        TEST_SETTINGS['tbr_values'] = random.sample(range(1000,tbr_mbr_values[0]), 2)
    elif test_name == 'MaxBitrate_test_VBR_360p_rate_%s':
        tbr_mbr_values = random.sample(range(502,1000), 1)
        valid_parameter_range = tbr_mbr_values 
        TEST_SETTINGS['tbr_values'] = random.sample(range(500,tbr_mbr_values[0]), 2)
    elif test_name == 'Issue1939_OvershootPct_test':
        TEST_SETTINGS['tbr_values'] = [200]
    elif test_name == 'Issue1959_OvershootPct_test':
        TEST_SETTINGS['tbr_values'] = [3000]
    elif test_name == 'rc_on_hang_check_HL4':
        TEST_SETTINGS['tbr_values'] = [2500]
    elif 'config' in test_name:
        TEST_SETTINGS['tbr_values'] = [10000]
    elif 'high_res_test' in test_name:
        TEST_SETTINGS['number_of_encoding_processes'] = 4
        
    '''Change the parallel jobs values for certain features'''
    if 'nonlp' in test_name:
        TEST_SETTINGS['number_of_encoding_processes'] = int(multiprocessing.cpu_count() // 16)
        if TEST_SETTINGS['number_of_encoding_processes'] == 0:
            TEST_SETTINGS['number_of_encoding_processes'] = 1
    elif '1lp' in test_name and 'r2r_test' in test_name:
        if not cpu_use_divisor:
            cpu_use_divisor = 1
        TEST_SETTINGS['number_of_encoding_processes'] = multiprocessing.cpu_count() // int(cpu_use_divisor)

    if debug == '1':
        preset_override = [12]
    
    if "pred-struct" in INSERT_SPECIAL_PARAMETERS:
        preset_override = [8, 9, 10, 11, 12, 13]

    if "fast-decode" in INSERT_SPECIAL_PARAMETERS:
        if "CBR" in test_name:
            preset_override = [8, 10]
        else:
            preset_override = [1, 2, 4, 6, 8, 10]

    
    'Override the presets if its the weekend test'
    if mode == '1' and not USE_TEST_SETTINGS_PRESETS_FOR_ALL:
        TEST_SETTINGS['presets'] = TEST_SETTINGS['weekend_presets']

    '''Override the presets to those specified in the FEATURES_COMMAND_REPO'''
    if preset_override and not USE_TEST_SETTINGS_PRESETS_FOR_ALL:
        TEST_SETTINGS['presets'] = preset_override

    if callable(TEST_SETTINGS['presets']):
        TEST_SETTINGS['presets'] = TEST_SETTINGS['presets'](mode)
        
    return tokens_to_change, valid_parameter_range, randomize_values, preset_override, main_clip_set, sample_command


def write_commands_to_file(test_name, encoding_commands):
    run_cmds_file = "run-{}.txt".format(test_name)
    with open(run_cmds_file, 'w') as parallel_run_files:
        for cmd in encoding_commands:
            parallel_run_files.writelines(cmd + "\n")
    return run_cmds_file            


'''Search stream folder for all clips specified in the test set'''
def find_test_set_clips_on_machine(test_name,test_set):
    
    if 'r2r_test' in test_name:
        found_clips, clips_to_find = look_up_r2r_clips(test_set) 
    else:
        
        if test_set in TEST_SETS:
            clips_to_find = [x['name'] for x in TEST_SETS[test_set]]
          
        else:
            print("Clipset not in TEST_SETS, defaulting to test_set_seq_table")
            clips_to_find = clips_to_find = [x['name'] for x in TEST_SETS['test_set_seq_table']]
        '''we shall store all the file names in this list'''
        clip_list = []
        found_clips = []
        for root, dirs, files in os.walk(TEST_SETTINGS['stream_dir']):
            for file in files:
                clip_list.append(os.path.join(root,file))

        for clip_to_find in clips_to_find:
            for clip in clip_list:
                if clip_to_find == clip.split('/')[-1][:-4]:
                    found_clips.append(clip)
                    break

    if len(clips_to_find) != len(found_clips):
        number_of_missing_clips = len(clips_to_find) - len(found_clips)
        missing_clips = [clip for clip in clips_to_find if clip not in found_clips]
        print('WARNING: Could not find %s clips: %s' % (number_of_missing_clips, missing_clips))
        if number_of_missing_clips >= len(clips_to_find)/2:
            print('ERROR: Missing 50%+ of clips')
            sys.exit(-1)
        
    '''Sort by complexity'''
    found_clips = sorted(found_clips, key=lambda x: os.stat(x).st_size, reverse=True)
    
    #Function below does not support 444 or 422 or 400 pixel format
    if test_set == "444_pixel_fmt_set" or test_set == "422_pixel_fmt_set":
        pass
    else:
        found_clips = sorted(found_clips, key=lambda x: get_fps(x), reverse=True)

    found_clips = sorted(found_clips, key=lambda x: x.lower())

    return found_clips


def look_up_r2r_clips(test_set):
    r2r_stream_location = os.path.join(TEST_SETTINGS['stream_dir'], TEST_SETTINGS['r2r_stream_folder'])
    config_stream_location = os.path.join(r2r_stream_location, test_set)
    found_clips = []
    for root, dirs, files in os.walk(config_stream_location):
        for file in files:
            found_clips.append(os.path.join(root, file))
    clips_to_find = []

    for clip_path in found_clips:
        clip = clip_path.split(os.sep)[-1]
        clips_to_find.append(clip)
    
    return found_clips,clips_to_find


def get_values_to_test(valid_parameter_range, randomize_values):
    values_to_test = []            
    try:
        '''Check to see if the list is an "element by element" or "range style" ex:["1-10"]''' 
        float(valid_parameter_range[0])
        if randomize_values != -1:
            values_to_test = random.sample(valid_parameter_range, randomize_values)
        else:
            values_to_test = valid_parameter_range
    except:
        '''Range Style case'''
        print(valid_parameter_range)
        '''Account for negative left range values and get left and right range bounds'''
        if valid_parameter_range[0][0] == '-':
            left_boundary = int(valid_parameter_range[0][1:].split('-')[0]) * -1
            right_boundary = int(valid_parameter_range[0][1:].split('-')[1])
        
        
        else:
            left_boundary = int(valid_parameter_range[0].split('-')[0])
            right_boundary = int(valid_parameter_range[0].split('-')[1])
        
        
        if randomize_values != -1:
            test_amount = randomize_values
            for test_num in range(test_amount):
                random_valid_value = random.randint(left_boundary, right_boundary)
                values_to_test.append(random_valid_value)
        else:
            for value in range(left_boundary, right_boundary + 1):
                values_to_test.append(value)
                
    return values_to_test
 

def get_commands(values_to_test,test_name, sample_command, tokens_to_change,r2r_mode = False ):
    mod_sample_command = sample_command
    tokens = re.findall(TOKEN_PATTERN, sample_command)
    temp_name = test_name.split("_debug")[0]
    if "debug" in test_name:
        special_preset = 12
    else:
        special_preset = 8
    '''special_preset_value_range_run runs special value range for a given preset and a normal value range for all other presets'''
    if temp_name == 'ColorPrimariesTest_%s':
        encoding_commands, decoding_commands = special_preset_value_range_run(special_preset, [1,2,3,4,5,6,7,8,9,10,11,12,22], [1,7,22], sample_command, test_name, tokens,tokens_to_change)
    elif temp_name == 'ColorRangeTest_%s':
        encoding_commands, decoding_commands = special_preset_value_range_run(special_preset, [0], [1], sample_command, test_name, tokens,tokens_to_change)
    elif temp_name == 'MatrixCoefficientsTest_%s':
        encoding_commands, decoding_commands = special_preset_value_range_run(special_preset, [1,2,3,4,5,6,7,8,9,10,11,12,13,14], [7,14], sample_command, test_name, tokens,tokens_to_change)
    elif temp_name == 'TransferCharacteristicsTest_%s':
        encoding_commands, decoding_commands = special_preset_value_range_run(special_preset, [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22], [0,11,22], sample_command, test_name, tokens,tokens_to_change)

    elif 'FixedQIndexOffset_test_set' in temp_name:
        
        KeyFrameQIndexOffset = "%s" % random.randint(-64, 63)
        KeyFrameChromaQIndexOffset = "%s" % random.randint(-64, 63)
        
        if 'FAIL' in temp_name:
            bad_range = [-257,-350,-1000,256,300,1000]
            KeyFrameQIndexOffset = "%s" % random.choice(bad_range)
            KeyFrameChromaQIndexOffset = "%s" % random.choice(bad_range)
        
        QIndexOffset = "[%s,%s,%s,%s]" % (random.randint(-64, 63), random.randint(-64, 63), random.randint(-64, 63), random.randint(-64, 63))
        ChromaQIndexOffset = "[%s,%s,%s,%s]" % (random.randint(-64, 63), random.randint(-64, 63), random.randint(-64, 63), random.randint(-64, 63))

        master_string = '--chroma-qindex-offsets %s --qindex-offsets %s --key-frame-chroma-qindex-offset %s --key-frame-qindex-offset %s' % (ChromaQIndexOffset, QIndexOffset, KeyFrameChromaQIndexOffset, KeyFrameQIndexOffset)
        mod_sample_command = mod_sample_command % master_string
        
        encoding_commands, decoding_commands = generate_feature_commands(values_to_test, mod_sample_command, test_name, tokens,tokens_to_change)            
    elif temp_name == 'MasteringDisplay_test_set_%s':
        master_good_master_string = '--mastering-display "G(%s,%s)B(%s,%s)R(%s,%s)WP(%s,%s)L(%s,%s)"'%(random.uniform(0.0, 1.0),
                                                                                              random.uniform(0.0, 1.0),                                                                         
                                                                                              random.uniform(0.0, 1.0),
                                                                                              random.uniform(0.0, 1.0),                                                                         
                                                                                              random.uniform(0.0, 1.0),
                                                                                              random.uniform(0.0, 1.0),                                                                         
                                                                                              random.uniform(0.0, 1.0),
                                                                                              random.uniform(0.0, 1.0),                                                            
                                                                                              random.uniform(0.0, 1.0),
                                                                                              random.uniform(0.0, 1.0),
                                                                                                )
        good_master_string = master_good_master_string
        mod_sample_command = mod_sample_command % good_master_string

        encoding_commands, decoding_commands = generate_feature_commands(values_to_test, mod_sample_command, test_name, tokens,tokens_to_change)            
    elif temp_name == 'ContentLight_test_%s':
        good_master_string = '--content-light %s,%s'%(random.randint(0, 65535),random.randint(0, 65535))
        mod_sample_command = mod_sample_command % good_master_string

        encoding_commands, decoding_commands = generate_feature_commands(values_to_test, mod_sample_command, test_name, tokens,tokens_to_change)

    else:
        encoding_commands, decoding_commands = generate_feature_commands(values_to_test, sample_command, test_name, tokens,tokens_to_change)
    return encoding_commands, decoding_commands


def special_preset_value_range_run(special_preset, special_values, normal_values, sample_command, test_name, tokens,tokens_to_change):
    all_post_processed_encoding_command_list = []
    all_post_processed_decoding_command_list = []
    
    default_presets = TEST_SETTINGS['presets']
    if special_preset in TEST_SETTINGS['presets']:
        values_to_test=special_values
        TEST_SETTINGS['presets'] = [special_preset]
        
        post_processed_encoding_command_list, post_processed_decoding_command_list = generate_feature_commands(values_to_test, sample_command, test_name, tokens,tokens_to_change)
        
        all_post_processed_encoding_command_list.extend(post_processed_encoding_command_list)
        all_post_processed_decoding_command_list.extend(post_processed_decoding_command_list)

    values_to_test=normal_values
    TEST_SETTINGS['presets'] = default_presets
    
    if special_preset in TEST_SETTINGS['presets']:
        TEST_SETTINGS['presets'].remove(special_preset)
    else:
        TEST_SETTINGS['presets'] = default_presets
        
    if TEST_SETTINGS['presets']:
        post_processed_encoding_command_list, post_processed_decoding_command_list = generate_feature_commands(values_to_test, sample_command, test_name, tokens,tokens_to_change)
        all_post_processed_encoding_command_list.extend(post_processed_encoding_command_list)
        all_post_processed_decoding_command_list.extend(post_processed_decoding_command_list)
        
    return all_post_processed_encoding_command_list, all_post_processed_decoding_command_list


def insert_new_parameters(token):
    sub_string_first_half = token.rpartition('-i')[0] 
    sub_string_second_half = token.rpartition('-i')[2]

    for param in INSERT_SPECIAL_PARAMETERS:
        sub_string_first_half += param + " "

    sample_command = sub_string_first_half + "-i" + sub_string_second_half
    return sample_command


def insert_parameters_to_specific_tests(token, token_to_add):
    sub_string_first_half = token.rpartition('-i')[0] 
    sub_string_second_half = token.rpartition('-i')[2]

    for param in token_to_add:
        sub_string_first_half += param + " "

    sample_command = sub_string_first_half + "-i" + sub_string_second_half
    return sample_command


def generate_feature_commands(values_to_test, sample_command, test_name, tokens,tokens_to_change):
    all_processed_encoding_commands = []
    all_processed_decoding_commands = []
    
    default_sample_command = sample_command
    
    if values_to_test:
        for value in values_to_test:
            '''Modify the sample command for features that require special considerations'''
            mod_sample_command = sample_command

            for token in tokens:
                for token_to_change in tokens_to_change:
                    if token_to_change in token:
                        token_variable = token.split(' ')[0]
                        token_with_new_value = ' %s %s ' % (token_variable, value)
                        mod_sample_command = mod_sample_command.replace(token,token_with_new_value)

            if INSERT_SPECIAL_PARAMETERS:
                mod_sample_command = insert_new_parameters(mod_sample_command)

            processed_encoding_commands, processed_decoding_commands = generate_encoding_and_decoding_commands(mod_sample_command, test_name % value)
            all_processed_encoding_commands.extend(processed_encoding_commands)
            all_processed_decoding_commands.extend(processed_decoding_commands)
            
    else:
        '''Modify the sample command for features that require special considerations'''
        mod_sample_command = sample_command

        if INSERT_SPECIAL_PARAMETERS:
            mod_sample_command = insert_new_parameters(mod_sample_command)

        processed_encoding_commands, processed_decoding_commands = generate_encoding_and_decoding_commands(mod_sample_command, test_name)

        all_processed_encoding_commands.extend(processed_encoding_commands)
        all_processed_decoding_commands.extend(processed_decoding_commands)
        
    
    return all_processed_encoding_commands, all_processed_decoding_commands


def generate_encoding_and_decoding_commands(sample_command, test_name):
    '''Ability to switch between features mode in case we decide to creat one script to rule them all'''
    '''Not needed if we are doing script per task'''
    TEST_SETTINGS['features'] = 1
    TEST_SETTINGS['feature_test'] = test_name

    '''Create the test folder for the encodings in bitstreams'''
    create_feature_folder(TEST_SETTINGS['feature_test'])

    '''Generate the encoding commands'''
    processed_encoding_command_list, rc_values, rc_identifier, encoder = process_sample_command(sample_command)
    post_processed_encoding_command_list = post_process(processed_encoding_command_list)

    # print('TEST_SETTINGS["feature_test"] {}'.format(TEST_SETTINGS['feature_test']))

    '''Only generate metric commands for non-r2r tests given that r2r tests go through seperate decoding process'''    
    if 'r2r_test' not in TEST_SETTINGS['feature_test']:
        processed_decoding_command_list, _, _, _ = process_sample_command(DECODING_COMMAND_REPOSITORY['features_ffmpeg_psnr'],rc_values,rc_identifier)
        post_processed_decoding_command_list = post_process(processed_decoding_command_list) 

    elif 'resize' not in TEST_SETTINGS['feature_test']:
        processed_decoding_command_list, _, _, _ = process_sample_command(DECODING_COMMAND_REPOSITORY['4_decoder_test'],rc_values,rc_identifier)
        post_processed_decoding_command_list = post_process(processed_decoding_command_list)

    else:
        post_processed_decoding_command_list = []
            
    return post_processed_encoding_command_list, post_processed_decoding_command_list

   
'''Core Sample Command processing functions'''
def process_sample_command(sample_command,rc_values=[],rc_selector=-1):
    processed_command_list = []

    tokens = re.findall(TOKEN_PATTERN, sample_command)

    for preset in TEST_SETTINGS['presets']:
        for clip in TEST_SETTINGS['clip_list']:
            clip_name = os.path.split(clip)[1]
            
            if clip.endswith('yuv') and not yuv_library_found:
                continue
            elif clip.endswith('yuv') and yuv_library_found:
                width, height, width_x_height, fps_numerator, fps_denominator, bit_depth, number_of_frames, fps_ratio, fps_decimal, vvenc_pixel_format, pixel_format = get_yuv_params(clip)
                rawvideo = 'rawvideo'

            elif clip.endswith('y4m'):   ### TEST_SETTINGS['encoder'] != 'svt' and TEST_SETTINGS['intra_period'] == -1:
                width, height, framerate,number_of_frames = read_y4m_header(clip)
                if 'BufferedInput_test' in TEST_SETTINGS['feature_test']:
                    intra_period = number_of_frames + 1
                else:
                    intra_period = TEST_SETTINGS['intra_period']


                                
            '''Reduces presets and number of frames for long/4k clips'''
            skip,number_of_frames_divider = control_clip_flow(clip_name,preset, width, height)

            if number_of_frames_divider is not None:
                number_of_frames = int(number_of_frames/number_of_frames_divider)
                
            if skip:
                continue

            ##Intraperiod is disabled right now
            ## INTRA 
            if TEST_SETTINGS['encoder'] != 'svt' and TEST_SETTINGS['intra_period'] == -1:
                intra_period = number_of_frames + 1
            else:
                intra_period = TEST_SETTINGS['intra_period']
            
            # if TEST_SETTINGS['downscale_commands']:
                # input_file = 'resized_clips/%s' % (clip_name)
            # else:
            input_file = clip#os.path.join(LAB_STREAM_DIR,clip_name).replace('\\','/')
            
            '''If there are no supplied rc values, implies that we are on the TEST_SETTINGS['encoder'] iteration and must identify rc characteristics'''
            if rc_selector == -1:
                '''if any of the relevant qp tokens are found in the command, assign the rc values to the qp list. Else do tbr list'''
                if any(re.split(r'\=?\s?',token.strip())[0].strip('-') in DYNAMIC_TOKENS['qp_values'] for token in tokens):
                    rc_identifier = 'Q%s'
                    qp_values = TEST_SETTINGS['qp_values']
                    rc_values = qp_values
                else:
                    rc_identifier = 'TBR_%sKbps'
                    tbr_values = TEST_SETTINGS['tbr_values']
                    rc_values = tbr_values
            else:
                rc_identifier = rc_selector

            for rc_value in rc_values:
                processed_command = sample_command

                '''assigned the list element for use in dynamic token loop eval'''
                qp_values = rc_value
                tbr_values = rc_value
                                    
                '''sub in the new file descriptors'''
                #account for two pass
                processed_command = re.sub(CRF_ENCODED_FILE_PATTERN,'%s_M%s_%s_%s' % (TEST_SETTINGS['encoder'], preset, clip_name[:-4], rc_identifier%rc_value), processed_command)
                processed_command = re.sub(VBR_ENCODED_FILE_PATTERN,'%s_M%s_%s_%s' % (TEST_SETTINGS['encoder'], preset, clip_name[:-4], rc_identifier%rc_value), processed_command)
                
                '''Replace the input file in the case of no encoded file types'''
                for file_path in re.findall(FILE_PATH_PATTERN, processed_command):
                    if re.search(CRF_ENCODED_FILE_PATTERN, file_path) or re.search(VBR_ENCODED_FILE_PATTERN, file_path):
                        continue
                    else:
                        if 'dav1d' in processed_command and 'md5log' not in file_path:
                            processed_command = processed_command.replace(file_path, '/dev/shm/bitstreams/{}_{}_{}_{}'.format(TEST_SETTINGS['encoder'], preset, rc_identifier%rc_value,clip_name))#, processed_command)
                        elif 'md5log' in file_path:
                            processed_command = re.sub(CRF_ENCODED_FILE_PATTERN,'%s_M%s_%s_%s' % (TEST_SETTINGS['encoder'], preset, clip_name[:-4], rc_identifier%rc_value), processed_command).replace('.y4m','.md5log').replace('.yuv','.md5log')
                            processed_command = re.sub(VBR_ENCODED_FILE_PATTERN,'%s_M%s_%s_%s' % (TEST_SETTINGS['encoder'], preset, clip_name[:-4], rc_identifier%rc_value), processed_command).replace('.y4m','.md5log').replace('.yuv','.md5log')
                        elif 'config' in file_path:
                            continue
                        else:
                            processed_command = processed_command.replace(file_path, input_file)#, processed_command)
                        
                for token in tokens:
                    parameter_joiner = [x for x in re.findall(r'\s*\=?', token) if x != ''][0]

                    '''split token by space and get rid of any empty list elements'''
                    refined_token = [x for x in re.split(r'\=?\s?',token) if x != '']

                    '''define the token into its variable and value'''
                    token_variable = refined_token[0]

                    '''Map and fill the core dynamic tokens, preset, rc value, input, output file'''
                    for dynamic_token in DYNAMIC_TOKENS:
                        if token_variable.strip('-') in DYNAMIC_TOKENS[dynamic_token]:
                            processed_command = processed_command.replace(token,'%s%s%s '%(token_variable, parameter_joiner, eval(dynamic_token))) 

                    '''Find which yuv parameters are included in the sample command and fill/remove them depending if they are yuv clips or not'''
                    for yuv_token in YUV_TOKENS:
                        if token_variable.strip('-') in YUV_TOKENS[yuv_token]:
                            if ('BufferedInput_test' in TEST_SETTINGS['feature_test'] and token_variable.strip('-') == 'n') or (clip.endswith('yuv') and not (refined_token[-1].strip() == 'null')):   processed_command = processed_command.replace(token,'%s%s%s '%(token_variable,parameter_joiner,eval(yuv_token)))
                            elif clip.endswith('y4m') and not (refined_token[-1].strip() == 'null') and ('dav1d' not in processed_command): processed_command = processed_command.replace(token, '')
                
                # to prevent -n value being replaced with the frame amount of the clip instead of the specified one for the test
                if "FRAMES300" in processed_command:
                    processed_command = processed_command.replace("FRAMES300", "-n 300")
                 
                # to bypass --film-grain-denoise value being replaced with --film-grain random values
                if "FILMGRAINDENOISEOFF" in processed_command:
                    processed_command = processed_command.replace("FILMGRAINDENOISEOFF", "--film-grain-denoise 0")
                processed_command_list.append(processed_command)

    return processed_command_list, rc_values, rc_identifier, TEST_SETTINGS['encoder']

def post_process(processed_command_list,default_number_of_runs=0,split_runs=0):
    post_processed_command_list = []
    
    for processed_command in processed_command_list:
        if 'r2r_test' in TEST_SETTINGS['feature_test']:
            preset_for_command = int(re.search(r'_M(-?\d+)_',processed_command).group(1),)#int(re.search(r'--preset (\d*)', processed_command).group(1))#int(re.findall(r'--preset \d*',processed_command)[0].split(" ")[1])

        folders_to_replace = set()
        default_processed_command = processed_command
        joiner = [x for x in re.findall(r'\\?/?', processed_command) if x != ''][0]
        
        '''get the output file paths and replace the head of it with appropriate format bitstreams/run etc...'''
        for file_path in re.findall(FILE_PATH_PATTERN, processed_command):
            '''output file path'''
            if re.search(CRF_ENCODED_FILE_PATTERN, file_path) or re.search(VBR_ENCODED_FILE_PATTERN, file_path): 
                root_folder_portion = joiner.join(re.split(r'\\?/?',file_path)[0:-1])
                folders_to_replace.add(root_folder_portion)
                
        '''Replace all output folders with a PLACE_HOLDER to be replaced in the next section'''
        for folder_to_replace in folders_to_replace:
            post_processed_command = default_processed_command.replace(folder_to_replace, 'PLACE_HOLDER')
            default_processed_command = post_processed_command

        '''Replace the PLACE_HOLDER with the appropriate output folder type'''
        if TEST_SETTINGS['features']:
            if 'r2r_test' in TEST_SETTINGS['feature_test']:
                for run in range(1,TEST_SETTINGS['number_of_r2r_runs']+1):
                    '''ADD CHECK FOR PRESET, THEN REDUCE RUNS FROM THERE'''
                    if TEST_SETTINGS['preset_threshold_to_reduce'] > preset_for_command:
                        if run > TEST_SETTINGS['reduced_number_of_r2r_runs']:
                            break
                        
                    feature_folder = 'bitstreams/%s/run%s'%(TEST_SETTINGS['feature_test'],run)
                    if 'dav1d' in default_processed_command:
                        post_processed_command_list.append(default_processed_command.replace('PLACE_HOLDER', feature_folder).replace('.y4m','%s.y4m'%run).replace('.yuv','%s.yuv'%run))         
                    else:
                        post_processed_command_list.append(default_processed_command.replace('PLACE_HOLDER', feature_folder))         
                    
            else:
                feature_folder = 'bitstreams/'+TEST_SETTINGS['feature_test']
                post_processed_command_list.append(default_processed_command.replace('PLACE_HOLDER', feature_folder))
            
    return post_processed_command_list


def randomize_intraperiod_qp(input_encoding_command_list):
    post_processed_encoding_command_list = []
    intraperiod_map = {}
    intra_period_tokens = ['-intra-period','--kf-min-dist','--kf-max-dist','--keyint','--min-keyint','--intraperiod']
    
    for index, command in enumerate(input_encoding_command_list):
        tokens = re.findall(TOKEN_PATTERN, command)
        for token in tokens:  
            token_variable = token.strip().split(' ')[0].strip()
            if token_variable in intra_period_tokens:
                crf_encoding_name = re.search(CRF_ENCODED_FILE_PATTERN, command)
                
                if crf_encoding_name:
                    encoding_name = crf_encoding_name.group(0)
                else:
                    vbr_encoding_name = re.search(VBR_ENCODED_FILE_PATTERN, command)
                    if vbr_encoding_name:
                        encoding_name = vbr_encoding_name.group(0)
                    else:
                        print('CRITICAL ERROR: Neither CRF nor VBR format found')
                        sys.exit(-1)

                if encoding_name in intraperiod_map:
                    intra_period = intraperiod_map[encoding_name]
                else:
                    '''Generate a random intraperiod in a balanced manner'''
                    if random.randint(1,2) % 2 == 0: 
                        intra_period = random.randint(18,120)
                    else: ## INTRA
                        if '--rc' in command:#rc_found:
                            if '.yuv' in command:
                                fps_numerator = int(re.search(r"--fps-num\s*(\d+)", command).group(1))
                                fps_denominator = int(re.search(r"--fps-denom\s*(\d+)", command).group(1))
                                intra_period = int(fps_numerator / fps_denominator + 1)
                            else:
                                intra_period = 120
                        else:
                            intra_period = -1
                    '''Assign the new intraperiod to the encoding'''
                    intraperiod_map[encoding_name] = intra_period

                new_token = ' %s %s ' % (token_variable, intra_period)
                post_processed_encoding_command_list.append(command.replace(token, new_token))

    return post_processed_encoding_command_list


'''r2r alterations'''
def control_clip_flow(clip,preset,width,height):
    clips_to_reduce_frames = ['Cactus_10bit_1920x1080_50Hz_P420.yuv']
    if '4096x2160' in clip and preset<8:
        skip = True
        number_of_frames_divider=None
    elif clip in clips_to_reduce_frames and preset in [1,2]:
        skip = False
        number_of_frames_divider = 3
    elif clip in clips_to_reduce_frames and preset in [-1,0]:
        skip = False
        number_of_frames_divider = 5
    else:
        skip = False
        number_of_frames_divider = None

    #Skip High resoltions for mR M0
    if str(preset) == '-1' and int(height) > 480:
        skip = True
    if str(preset) == '0' and int(height) > 720:
        skip = True           

    return skip,number_of_frames_divider


def create_feature_folder(feature):
    bitstream_folder = os.path.join(os.getcwd(),'bitstreams')
    feature_folder = os.path.join(bitstream_folder,feature)
    if not os.path.exists(bitstream_folder):
        os.mkdir(bitstream_folder)
    if not os.path.exists(feature_folder):
        os.mkdir(feature_folder)

        
def create_r2r_run_folders():
    number_of_runs = TEST_SETTINGS['number_of_r2r_runs']
    bitstreams_folder = 'bitstreams/'+TEST_SETTINGS['feature_test']
    if not os.path.exists(bitstreams_folder):
        os.mkdir(bitstreams_folder)
    for run in range(1,number_of_runs+1):
        if not os.path.exists('%s/run%s'%(bitstreams_folder,run)):
            os.mkdir('%s/run%s'%(bitstreams_folder,run))


def run_parallel(num_pool, run_cmds_file, test_name, encoder_exec_name='svt'):
    if encoder_exec_name == 'aomenc':
        cmd = '/bin/bash -c \'(/usr/bin/time --verbose parallel -j {} < {} ) > time_enc_{}.log 2>&1 \' &'.format(num_pool, run_cmds_file, test_name)
    else:
        cmd = "/bin/bash -c \'(/usr/bin/time --verbose parallel -j {} < {} ) &> time_enc_{}.log\' &".format(num_pool, run_cmds_file, test_name)
    
    execute_command_helper((cmd, os.getcwd()))


''' Check for bad decode bitstream '''
def check_bad_decode(test_name, bitstreams_folder, num_pool=18):
    file_list = []
    for root, _, files in os.walk(bitstreams_folder):
        for file in files:
            if ('debug' in test_name and 'debug' in root) or ('debug' not in test_name and 'debug' not in root) and test_name.split('%s')[0] in root and file.endswith('bin') and 'bad_decoded' not in root:
                file_list.append(os.path.join(root,file))
    Pooler = Pool(processes=num_pool)
    bad_decodes = Pooler.map(run_check_bad_decode_parallel, file_list)
    Pooler.close()
    Pooler.join()
    
    bad_decodes = [x for x in bad_decodes if x != None]
    
    if bad_decodes:
        print('Bad Decodes Found,',bad_decodes)
        move_bad_decode(bad_decodes, test_name)
        sys.exit(-1)
    # else:
    #     print("No_Bad_Decode")
    

def run_check_bad_decode_parallel(file):
    cmd = "/home/CI_Script/scripts/tools/ffmpeg -nostdin -y -i {} -f null -".format(file)
    
    decode_errors = parse_log_errors(cmd.split())
    if decode_errors:
        return file

	
def parse_log_errors(cmd):
    pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)	
    while pipe.stderr:
        stderror = pipe.stderr.readline() #= take in line from log file
        '''Checks the error feed for the bitstreams corruption error that produces massive logs'''
        '''If the infinite ffmpeg loops are detected, kill the pipe'''
        if not stderror:
            break
        elif "Error parsing OBU data" in str(stderror):
            pipe.kill()
            return True
    pipe.wait()

    return False


def move_bad_decode(bad_decode_list, test_name):
    bad_decode_path = os.path.join(os.getcwd(), "bitstreams", "bad_decoded_bitstreams_{}".format(test_name))
    if not os.path.isdir(bad_decode_path):
        os.mkdir(bad_decode_path)

    unique_identifier = 0
    '''copying / moving bad bitstreams'''
    for bad_file_path in bad_decode_list:
        if not bad_file_path:
            continue

        bad_file_name = bad_file_path.split("/")[-1]
        if not os.path.exists(os.path.join(bad_decode_path, bad_file_name)):
            try:
                bad_file_output_files = glob.glob(bad_file_path.replace('.bin','.*'))
                # print(bad_file_output_files)
                for file_path in bad_file_output_files:
                    file_name = file_path.split("/")[-1]
                    shutil.move(os.path.join(file_path), os.path.join(bad_decode_path, file_name))

            except:
                pass
        else: ## if file already exists, make unique identifier and copy it over
            try:
                shutil.move(os.path.join(bad_file_path, bad_file_name), \
                            os.path.join(bad_decode_path).replace('.bin', "_" + str(unique_identifier) + '.bin') ) 
                bad_text_file = str(bad_file_path).replace('.bin', '.txt')
                shutil.move(os.path.join(bad_text_file), \
                            os.path.join(bad_decode_path, bad_file_name.replace('.txt', "_" + str(unique_identifier) + '.txt')))
                unique_identifier += 1
            except:
                pass


def get_ref_test_folder(test_name):
    ref_test_folder = None
    # Set reference test folder based on test_name

    if test_name in COMPARISON_TESTS:
        ref_test_folder = os.path.join(TEST_SETTINGS['hard_coded_bitstreams'], COMPARISON_TESTS[test_name])

    return ref_test_folder

def get_feature_folders(bitstreams_folder):
    feature_folders = glob.glob('%s/*' % bitstreams_folder)
    return feature_folders

def is_valid_feature_folder(test_name, feature_folder,debug):
    feature = os.path.split(feature_folder)[-1]

    if test_name != feature and 'r2r_test' in test_name:
        return False
    elif test_name not in feature:
        return False
    elif 'FAIL' in feature and 'FAIL' not in test_name:
        return False
    elif 'debug' in feature and not debug:
        return False
    if 'bad_decode' in feature_folder:
        return False

    return True

def get_feature_files(feature_folder):
    feature_logs = []
    feature_txts = []
    feature_bins = []
    decode_md5 = []

    for root, dirs, files in os.walk(feature_folder):
        for file in files:
            if file.endswith('log'):
                feature_logs.append(os.path.join(root, file))
            if file.endswith('txt'):
                feature_txts.append(os.path.join(root, file))
            if file.endswith('bin'):
                feature_bins.append(os.path.join(root, file))
            if file.endswith('md5log'):
                decode_md5.append(os.path.join(root, file))

    return feature_logs, feature_txts, feature_bins, decode_md5


def is_valid_encoding_files(test_name, feature_folder, feature_logs, feature_txts, feature_bins):
    if 'r2r_test' not in test_name:
        if not feature_bins:
            print('Error. No bitstreams generated for %s' % (feature_folder))
            return False
        if len(feature_logs) != len(feature_txts) and len(feature_txts) != len(feature_bins):
            print('Error. Mismatch in number of bins (%s) encode logs (%s) and/or metric_logs (%s)' % (
                len(feature_bins), len(feature_txts), len(feature_logs)))
            return False

    return True

def is_deviation_test(test_name):
    deviation_tests = ['tbr_abr_deviation', 'OvershootPct_test', 'UndershootPct_test', 'MaxBitrate_test_VBR_rate',
                       'CrowdRun']
    for test in deviation_tests:
        if test in test_name:
            return True
    return False

def is_psnr_check_applicable(test_name):
    return test_name not in PSNR_CHECK_EXCLUSION and (
                "debug" not in test_name or all(test not in test_name for test in PSNR_CHECK_EXCLUSION))

def write_deviation_log(test_name, tbr_abr_deviation_log):
    with open("{}_deviation.log".format(test_name), "w") as deviation_log:
        deviation_log.write('TBR and ABR Deviation Found In : \n')
        label = "Bitstream name \t Deviation \t Allowable Deviation \n"
        deviation_log.write(label)
        for key, value in tbr_abr_deviation_log.items():
            deviation_log.write(key.ljust(80) + "\t" + value[0] + "\t" + str(value[1]) + "\n")




def check_4_decoder_md5(decode_md5):
    decoder_log = dict()
    decoder_map = {0: 'svt',
    1 : 'ffmpeg',
    2: 'dav1d',
    3: 'aom'}
    for md5_file in decode_md5:
        md5_mismatch = []
        with open(md5_file) as file:
            content = file.readlines()[::-1]
            md5_hash = None
            for index, line in enumerate(content):
                md5_hash = line.split(' ')[0]

                if not md5_hash:
                    md5_hash = line.split(' ')[0]
                elif md5_hash != line.split(' ')[0]:
                    passed = False
                    md5_mismatch.append(decoder_map[index])
            if md5_mismatch:
                decoder_log[md5_file] = md5_mismatch
    return decoder_log
                  
def check_for_md5_differences(input_folders):
    if 'bad_decode' in input_folders[0]:
        return '',''
    if len(input_folders) == 1:
        sub_folders = glob.glob('%s/*/'%input_folders[0])
    else:
        input_folder1 = input_folders[0]
        input_folder2 = input_folders[1]
        
    hash_lists=[]
    commands_with_r2r = dict()
    r2r_log = dict()
    r2r_command_log = dict()
    r2r_streams = dict()
    r2r = dict()
    '''For r2r test case, get a hash list for each run folder and add it to the hash_lists list'''
    if 'r2r_test' in TEST_SETTINGS['feature_test']:
        for root,dirs,files in os.walk(input_folders[0]):
            for file in files:
                if file.endswith('bin'):
                    if file not in r2r_streams:
                        r2r_streams[file] = [os.path.join(root,file)]
                    else:
                        r2r_streams[file].append(os.path.join(root,file))
        for r2r_stream in r2r_streams:
            streams = r2r_streams[r2r_stream]
            stream_hashes = [[hash,stream] for stream in streams for hash in get_hash(stream)]
            streams = [stream[1] for stream in stream_hashes]
            hashes = [hash[0] for hash in stream_hashes]
          
            r2r = list(set(hashes))
            # print('\n\n%s\n\n',r2r)
            if len(r2r) > 1:
                for r2r_hash in r2r:
                    r2r_index = hashes.index(r2r_hash)
                    r2r_bin = streams[r2r_index]
                    r2r_filename = os.path.split(r2r_bin)[-1]
                    if r2r_filename in r2r_log:  r2r_log[r2r_filename] +=1
                    else:                   r2r_log[r2r_filename] = 1

                    '''Create dictionary with r2r command'''
                    r2r_command = get_r2r_command('%s.txt'%r2r_bin[:-4])
                    if r2r_command:
                         r2r_command_log[r2r_filename] = r2r_command
                    else:
                        print("ERROR: This file has resulted in a crashed | %s"%(r2r_filename))     
                                            
    else:
        hash_lists.append([[hash,input_file] for input_file in glob.glob('%s/*.bin'%input_folder1) for hash in get_hash(input_file)])
        hash_lists.append([[hash,input_file] for input_file in glob.glob('%s/*.bin'%input_folder2) for hash in get_hash(input_file)])
    
   
        for index_1, hash_list_pair_1 in enumerate(hash_lists):
            for index_2, hash_list_pair_2 in enumerate(hash_lists):
                r2r_list = compare_r2r_hash_lists(hash_list_pair_1,hash_list_pair_2)
                for r2r in r2r_list:
                    '''create dictionary with the file path'''
                    r2r_bin = os.path.split(r2r)[-1]
                    if r2r_bin in r2r_log:  r2r_log[r2r_bin] +=1
                    else:                   r2r_log[r2r_bin] = 1

                    '''Create dictionary with r2r command'''
                    r2r_command = get_r2r_command('%s.txt'%r2r[:-4])
                    if r2r_command:
                         r2r_command_log[r2r_bin] = r2r_command
                    else:
                        print("ERROR: This file has resulted in a crashed | %s"%(r2r_bin))     

            break   
    
    return r2r_log, r2r_command_log


def get_hash(input_file):
    # txt = input_file.split(".")[0] + ".txt"
    # with open(txt, "r") as text:
        # text = text.read()
        # if "Command terminated by signal 11" in text:
            # return ["Error"]
            
    hash_md5 = hashlib.md5()
    
    with open(input_file, "rb") as file:
        for chunk in iter(lambda: file.read(4096), b""):
            hash_md5.update(chunk)
            
    return [hash_md5.hexdigest()]


def compare_r2r_hash_lists(hash_list_1,hash_list_2):
    r2r_list=[]
    pass_presets = ['M8', 'M9','M10','M11','M12', 'M13']

    if hash_list_1 and hash_list_2 and 'skip_30_frames_compare' in hash_list_1[0][1]:
        hash_list_1  = sorted(hash_list_1,key=lambda x: x[1])
        hash_list_2  = sorted(hash_list_2,key=lambda x: x[1])

    for hash_1, hash_2 in zip(hash_list_1,hash_list_2):
        # if hash_1[0] == 'Error' or hash_2[0] == 'Error':
            # continue
        
        # passes test when bitstream mismatch is present in presets >= 9 for the recon_compare test
        if 'recon_compare' in hash_1[1] and any(preset in hash_1[1] for preset in pass_presets):
            continue 
         
        if str(hash_1[0]) != str(hash_2[0]):
            bin_with_r2r = hash_1[1]
            r2r_list.append(bin_with_r2r)
    
    return r2r_list



def get_r2r_command(input_file):
    with open(input_file) as txt:
        txt_content = txt.read()
        command_line = re.search(r'Command being timed: \"(.*?)\"',txt_content)
    if command_line:
        command = command_line.group(1)
        return command
    else:
        return False

def collect_psnr_data(file):
    psnr_result = dict()
    psnr_log_file_path = glob.glob(os.path.join(file,'*.log'))
    for log_files in psnr_log_file_path:
        with open(log_files,"r") as file:
            content = file.read()
            try:
                val = float(re.search(r"PSNR y:(\d+\.?\d+)", content).group(1))
                if val < 18: 
                    psnr_result[str(os.path.basename(log_files))] = val
            except AttributeError:
                print('ERROR: PSNR_Y value not found in %s' % (log_files))
                continue
    return psnr_result

def get_deviation_data(feature_dict):
    deviation_found = dict()
    for key, allowable_percent_deviation in feature_dict.items():
            try:
                with open(key,"r") as file:
                    content = file.read()
                if "CrowdRun" not in key:
                    tbr_value = float(re.search(r"--tbr\s(\d+)", content).group(1))
                abr_value = float(re.search(r"(\d+\.\d+)\skbps", content).group(1))
                allowable_percent_deviation = float(allowable_percent_deviation)
                path = os.path.basename(key)
                path = path.split(".txt")[0]
                path += "_" + str(allowable_percent_deviation)
                if "MaxBitrate" in key:
                    mbr_value = float(re.search(r"--mbr\s(\d+)", content).group(1))
                    greater_than =  (1 + allowable_percent_deviation / 100) * mbr_value
                    if abr_value > greater_than:                    
                        deviation_percentage = (abr_value - mbr_value)/mbr_value * 100
                        deviation_found[path] = ('%s%%'%round(deviation_percentage,2),'%s%%'%round(greater_than,2))
                elif "OvershootPct" in key:
                    greater_than =  (1 + allowable_percent_deviation / 100) * tbr_value
                    if abr_value > greater_than:                    
                        deviation_percentage = (abr_value - tbr_value)/tbr_value * 100
                        deviation_found[path] = ('%s%%'%round(deviation_percentage,2),'%s%%'%round(allowable_percent_deviation,2))
                elif "UndershootPct" in key:
                    less_than =  (1 - allowable_percent_deviation / 100) * tbr_value
                    if abr_value < less_than:                    
                        deviation_percentage = (abr_value - tbr_value)/tbr_value * 100
                        deviation_found[path] = ('%s%%'%round(deviation_percentage,2),'%s%%'%round(-1 * allowable_percent_deviation,2))
                elif "CrowdRun" in key:
                    greater_than = (1 + allowable_percent_deviation / 100) * 10000
                    if abr_value > greater_than:
                        deviation_percentage = (abr_value - 10000)/10000 * 100
                        deviation_found[path] = ('%s%%'%round(deviation_percentage,2),'%s%%'%round(-1 * allowable_percent_deviation,2))                        

                else:
                    percentage =  allowable_percent_deviation / 100 * tbr_value
                    greater_than = percentage + tbr_value
                    less_than = tbr_value - int(0.5 * tbr_value)
                    if abr_value < less_than or abr_value > greater_than:                    
                        deviation_percentage = (abr_value - tbr_value)/tbr_value * 100
                        deviation_found[path] = ('%s%%'%round(deviation_percentage,2),'+/-%s%%'%round(allowable_percent_deviation,2))

            except AttributeError:
                path = os.path.basename(key)
                deviation_found[path] = "ERROR: This file has crashed"
                continue
            except OSError:
                path = os.path.basename(key)
                deviation_found[path] = "ERROR: Incorrect file or file path provided"
 
    return deviation_found


def check_for_crashes(feature_logs, feature_txts,feature_folder):
    commands_with_errors = dict()

    for feature_log in feature_logs:
        with open(feature_log) as log:
            log_content = log.read()
            for error_pattern in ERROR_PATTERNS:
                if error_pattern in log_content:
                    error = error_pattern
                    commands_with_errors[feature_log] = error
           
    for feature_txt in feature_txts:
        error = None
        with open (feature_txt, 'r') as txt:
            txt_content = txt.read()
            
            command_line = re.search(r'Command being timed: \"(.*?)\"',txt_content)
            if command_line:
                command = command_line.group(1)
            else:
                command = "Command could not be found"
                        
            '''Check the encoding txt log for specific error cases'''
            if "SvtMalloc[error]" in txt_content:
                error = "Memory leak while encoding {}, command: {}\n".format(feature_txt, command)
                commands_with_errors[feature_txt] = error
            elif "killed" in txt_content:
                error = "Encoding {} killed by OS with commmand line {}\n".format(feature_txt,command)
                commands_with_errors[feature_txt] = error
            elif "segmentation fault" in txt_content:
                error = "Encoding {} caused a segmentation fault with command line {}\n".format(feature_txt, command)
                commands_with_errors[feature_txt] = error
            elif "core dumped" in txt_content:
                error = "Encoding {} core dumped with command line {}\n".format(feature_txt, command)
                commands_with_errors[feature_txt] = error
            elif "unprocessed token" in txt_content:
                error = "Encoding {} did not start because unprocessed token found in command line {}\n".format(feature_txt,command)
                commands_with_errors[feature_txt] = error
            elif "Command terminated by signal 11" in txt_content:
                error = "Encoding {} did not start because signal 11 found in encode log {}\n".format(feature_txt,command)
                commands_with_errors[feature_txt] = error                  
            elif 'SUMMARY ---------------------------------' not in txt_content:
                error = "Encoding {} did not start for an unknown reason\n".format(feature_txt)
                commands_with_errors[feature_txt] = error
            elif 'skip_30_frames_test' in feature_txt:
                txt.seek(0)
                lines = txt.readlines()

                for i,line in enumerate(lines):
                    if('Total Frames' in line):
                        encoded_frames = int(lines[i+1].split('\t')[0])

                if(encoded_frames != 30):
                    error = "Error while encoding {}: incorrect total frames {} found in encode log {}\n".format(command, encoded_frames, feature_txt)
                    commands_with_errors[feature_txt] = error
        if error:
            folder = os.path.split(feature_folder)[1]
            abs_path =  os.path.split(feature_folder)[0]
            bad_decode_streams = os.path.join(abs_path,'bad_decoded_bitstreams_%s'%folder)
            print('moving %s'%('%s.bin'%feature_txt[:-4]))
            
            if os.path.isfile('%s.bin'%feature_txt[:-4]):
                try:
                    shutil.move('%s.bin'%feature_txt[:-4],bad_decode_streams)
                except shutil.Error:
                    os.remove('%s.bin'%feature_txt[:-4])
   
    return commands_with_errors


def pass_fail_feature(r2r_log,r2r_command_log, tbr_abr_deviation_log, psnr_log, commands_with_errors,decode_logs):
    passed = True

    for r2r_bin in r2r_log:
        passed = False
        print('R2R Found: %s | %s | [%s/%s]' % (os.path.split(r2r_bin)[-1],r2r_command_log[r2r_bin],r2r_log[r2r_bin],TEST_SETTINGS['number_of_r2r_runs']))
    for decode_bin in decode_logs:
        passed = False
        print('Decode Mismatch Found: %s | %s' % (os.path.split(decode_bin)[-1],str(decode_logs[decode_bin])))

    if tbr_abr_deviation_log:
        passed = False
        print('TBR and ABR Deviation Found In :')
        label = ("Bitstream name \t Deviation \t Allowable Deviation")
        print(label)
        for key, value in tbr_abr_deviation_log.items():
            print(key.ljust(80) + "\t" + value[0] + "\t" + str(value[1]))
        print('----------------\n     FAILED\n----------------\n')
     
    if psnr_log:
        print("\nThe following clips have a PSNR_Y Average less than {} :\n\n".format(18))
        passed = False
        for key, value in psnr_log.items():
            print('%s : %s' %  (key.ljust(80), value))
        print('----------------\n     FAILED\n----------------\n')

    for key, generic_command in commands_with_errors.items():
            passed = False
            print('----------------\nFAILED: %s | %s'%(generic_command,key))

    return passed

def collect_allowable_deviation_data(feature_txts):
    feature_dict = dict()

    for path in feature_txts:
        folder_name = path.split(os.sep)[-2]
        if "RateControl" in path or "tbr_abr_deviation" in path or "Issue19" in path:
            for special_case in ['tbr_abr_deviation_1080p_LD_VBR_test','tbr_abr_deviation_360p_LD_VBR_test','tbr_abr_deviation_1080p_CBR_test','tbr_abr_deviation_360p_CBR_test']:
                if special_case in path:
                    feature_dict[path] = 15
                    return feature_dict
            # base case, if path is not in special case
            feature_dict[path] = 50
        
        elif "MaxBitrate" in path:
            feature_dict[path] = 3
        elif "CrowdRun" in path:
            feature_dict[path] = 50
        elif 'Undershoot' in path:
            feature_dict[path] = 50
        else:
            if "debug" in path:
                feature_dict[path] = float(folder_name.split('_test')[-1].split('_debug')[0]) + 5
            else:
                feature_dict[path] = float(folder_name.split('_test')[-1]) + 5

            
    return feature_dict

###Dependency Functions###


'''Two functions to extract clip info from its y4m header'''
def read_y4m_header_helper(readByte,buffer):
    if sys.version_info[0] == 3:
        if (readByte == b'\n' or readByte == b' '):
            clip_parameter = buffer
            buffer = b""
            return clip_parameter, buffer
        else:
            buffer += readByte
            return -1, buffer
    else:
        if (readByte == '\n' or readByte==' '):
            clip_parameter = buffer
            buffer = ""
            return clip_parameter, buffer
        else:
            buffer += readByte
            return -1, buffer

        
def read_y4m_header(clip):
    if sys.version_info[0] == 3:
        header_delimiters = {b"W":'width',b"H":'height',b"F":'frame_ratio',b"I":'interlacing',b"A":'pixel_aspect_ratio',b"C":'bit_depth'}
    else:
        header_delimiters = {"W":'width',"H":'height',"F":'frame_ratio',"I":'interlacing',"A":'pixel_aspect_ratio',"C":'bit_depth'}
        
    y4m_params = {'width':            -1,
                  'height':           -1,
                  'frame_ratio':      -1,
                  'framerate':        -1,
                  'number_of_frames':  1,
                  'bit_depth':        -1
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
                while 1:
                    readByte = f.read(1)
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
            if b'10' in y4m_params['bit_depth']:
                frame_length = int(float(2)*float(int(y4m_params['width']) * int(y4m_params['height']) * float(3) / 2))
                y4m_params['bit_depth'] = '10bit'
            else:
                frame_length = int(int(y4m_params['width']) * int(y4m_params['height']) * float(3) / 2)
                y4m_params['bit_depth'] = '8bit'
        else:
            frame_ratio_pieces = y4m_params['frame_ratio'].split(":")
            if '10' in y4m_params['bit_depth']:
                frame_length = int(float(2)*float(int(y4m_params['width']) * int(y4m_params['height']) * float(3) / 2))
                y4m_params['bit_depth'] = '10bit'
            else:
                frame_length = int(int(y4m_params['width']) * int(y4m_params['height']) * float(3) / 2)
                y4m_params['bit_depth'] = '8bit'

        y4m_params['framerate'] = float(frame_ratio_pieces[0]) / float(frame_ratio_pieces[1])
        
        while f.tell() < os.path.getsize(clip):
            readByte = f.read(1)
            if binascii.hexlify(readByte) == b'0a':
                f.seek(frame_length,1)
                buff = binascii.hexlify(f.read(5))
                if buff == b'4652414d45':
                    y4m_params['number_of_frames'] += 1
                 
    return y4m_params['width'], y4m_params['height'], y4m_params['framerate'], y4m_params['number_of_frames']


'''
Two functions to execute the encoding and metric command lists
NOTE: Need to pass in a tuple of cmd and work_dir
'''    
def execute_command_helper(inputs):
    cmd, work_dir = inputs
    pipe = subprocess.Popen(cmd, shell=True, cwd=work_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, error = pipe.communicate()
    pipe.wait()


def execute_parallel_commands(number_of_processes, command_list, execution_directory):
    command_lines = [command.strip() for command in command_list]
    execution_directory_list = [execution_directory for i in enumerate(command_lines)]
    inputs = zip(command_lines, execution_directory_list)
    
    Pooler = multiprocessing.Pool(processes=number_of_processes, maxtasksperchild=30)

    Pooler.map(execute_command_helper, inputs)
    Pooler.close()
    Pooler.join()


'''functions to get clip info'''
def get_fps(clip):
    if (".yuv" in clip and yuv_library_found):
        seq_table_index = get_seq_table_loc(seq_list, clip)
        if seq_table_index < 0:
            return 0
        fps = float(seq_list[seq_table_index]["fps_num"]) / seq_list[seq_table_index]["fps_denom"]
        return fps
    elif (".y4m" in clip):

        _, _, framerate,number_of_frames = read_y4m_header(clip)
        return framerate
    else:
        return 0

    
def get_seq_table_loc(seq_table, clipname):
    for i in range(len(seq_table)):
        if seq_table[i]["name"] == clipname[:-4]:
            return i
    return -1


def get_yuv_params(clip):
    clip_name = os.path.split(clip)[1]
    seq_table_index = get_seq_table_loc(seq_list, clip_name)

    bit_depth = seq_list[seq_table_index]['bitdepth']
    ten_bit_format = seq_list[seq_table_index]['unpacked']
    width = seq_list[seq_table_index]['width']
    height = seq_list[seq_table_index]['height']
    width_x_height = '%sx%s' % (width,height)
    fps_numerator = seq_list[seq_table_index]['fps_num']
    fps_denominator = seq_list[seq_table_index]['fps_denom']
    
    if (bit_depth == 8):
        number_of_frames = (int)(os.path.getsize(clip)/(width*height+(width*height/2)))
        pixel_format='yuv420p'
        vvenc_pixel_format='yuv420'
    elif (bit_depth == 10):
        pixel_format='yuv420p10le'
        vvenc_pixel_format='yuv42010'#Not sure what the real one is
        if ten_bit_format == 2:
            number_of_frames = (int)(((float)(os.path.getsize(clip))/(width*height+(width*height/2)))/1.25)
        else:
            number_of_frames = (int)(((os.path.getsize(clip))/(width*height+(width*height/2)))/2)
            
    return width, height, width_x_height, int(fps_numerator), fps_denominator, bit_depth, number_of_frames, '%s/%s'%(fps_numerator,fps_denominator), float(float(fps_numerator)/float(fps_denominator)),vvenc_pixel_format, pixel_format

try:
    from yuv_library import getyuvlist
    seq_list = getyuvlist()
    yuv_library_found = 1
except ImportError:
    print("WARNING yuv_library not found, only generating commands for y4m files.")
    seq_list = []
    yuv_library_found = 0


CRF_ENCODED_FILE_PATTERN = r'\w+_M-?\d+_\S+?_Q\d+'
VBR_ENCODED_FILE_PATTERN = r'\w+_M-?\d+_\S+?_TBR_\d+Kbps'
TOKEN_PATTERN = r'[-a-zA-Z_/\\:]+\=?\s*\S+\s+'
FILE_PATH_PATTERN = r'[a-zA-Z_/\\0-9-\.]+\w+\.[a-zA-Z]\w+'
RESOLUTION_PATTERN = r"\d+x\d+"



DYNAMIC_TOKENS = {'preset' : ['preset','enc-mode','cpu-used'],
                  'qp_values': ['q', 'qp', 'cq-level','crf'],
                  'tbr_values' : ['tbr'],
                  #'intra_period' : ['intra-period','kf-min-dist','kf-max-dist','min-keyint','keyint']
}


YUV_TOKENS = {'width' : ['w','width'],
              'height' : ['h','height'],
              'width_x_height':['s','size','s:v','input-res'],
              'rawvideo':['f'],
              'bit_depth' : ['bit-depth','input-bit-depth', 'internal-bitdepth','b','input-depth'],
              'pixel_format' : ['pix_fmt'],
              'vvenc_pixel_format' : ['format'],
              'fps_numerator' : ['fps-num'],
              'fps_denominator' : ['fps-denom'],
              'fps_ratio' : ['fps'],
              'fps_decimal':['framerate'],
              'number_of_frames' : ['n']
}


DECODING_COMMAND_REPOSITORY = {
    
    'ffmpeg'                 : '''/home/CI_Script/scripts/tools/ffmpeg -r 25 -i good_bitstreams/svt_M7_shields_640x360_60f_Q48.bin -s 640x360 -f rawvideo -pix_fmt yuv420p -r 25 -i /home/user/stream/weekend_run_set/8bit/shields_640x360_60f.yuv -lavfi "ssim=stats_file=good_bitstreams/svt_M7_shields_640x360_60f_Q48.ssim;[0:v][1:v]psnr=stats_file=good_bitstreams/svt_M7_shields_640x360_60f_Q48.psnr" -f null -  > good_bitstreams/svt_M7_shields_640x360_60f_Q48.log 2>&1''',

    'ffmpeg-spie'            : '''/home/CI_Script/scripts/tools/ffmpeg -y -nostdin  -r 25 -i bitstreams/svt_M8_aspen_1920x1080to1280x720_lanc_60f_Q55.bin -f rawvideo -r 25 -pix_fmt yuv420p -s:v 1920x1080 -i resized_clips/aspen_1920x1080_60f.yuv -lavfi 'scale2ref=flags=lanczos+accurate_rnd+print_info:threads=1 [scaled][ref];[scaled] split=3 [scaled1][scaled2][scaled3]; [scaled1][1:v]ssim=stats_file=bitstreams/svt_M8_aspen_1920x1080to1280x720_lanc_60f_Q55.ssim;[scaled2][1:v]psnr=stats_file=bitstreams/svt_M8_aspen_1920x1080to1280x720_lanc_60f_Q55.psnr;[scaled3][1:v]libvmaf=model_path=/home/CI_Script/scripts/tools/model/vmaf_v0.6.1.pkl:log_path=bitstreams/svt_M8_aspen_1920x1080to1280x720_lanc_60f_Q55.vmaf' -map "[ref]" -f null - > bitstreams/svt_M8_aspen_1920x1080to1280x720_lanc_60f_Q55.log 2>&1''',

    'ffmpeg-vmaf'            : r'''/home/CI_Script/scripts/tools/ffmpeg -y -nostdin  -r 25 -i bitstreams/svt_M12_thaloundeskmtg360p_60f_640x360__Q20.bin -s 640x360 -f rawvideo -pix_fmt yuv420p -r 25 -i resized_clips/thaloundeskmtg360p_60f_640x360_.yuv -lavfi '[0:v][1:v]libvmaf=model=version=vmaf_v0.6.1\\:name=vmaf|version=vmaf_v0.6.1neg\\:name=vmaf_neg:feature=name=psnr\\:reduced_hbd_peak=true\\:enable_apsnr=true\\:min_sse=0.5|name=float_ssim\\:enable_db=true\\:clip_db=true:log_path=bitstreams/svt_M12_thaloundeskmtg360p_60f_640x360__Q20.xml:log_fmt=xml' -threads 1 -f null -  > bitstreams/svt_M12_thaloundeskmtg360p_60f_640x360__Q20.log 2>&1''',

    #'ffmpeg-vmaf'        : '''(/home/CI_Script/scripts/tools/ffmpeg -i bitstreams/svt_M1_AOV5_1920x1080_60_8bit_420_Q23.bin -i resized_clips/AOV5_1920x1080_60_8bit_420.y4m -lavfi "scale2ref=flags=lanczos+accurate_rnd+full_chroma_int:sws_dither=none:param0=5 [scaled][ref]" -map "[ref]" -f null - -map "[scaled]"  -strict -1 -pix_fmt yuv420p /dev/shmbitstreams/svt_M1_AOV5_1920x1080_60_8bit_420_Q23.y4m && /home/CI_Script/scripts/tools/vmaf --reference resized_clips/AOV5_1920x1080_60_8bit_420.y4m --distorted /dev/shm/bitstreams/svt_M1_AOV5_1920x1080_60_8bit_420_Q23.y4m --aom_ctc v1.0 --output bitstreams/svt_M1_AOV5_1920x1080_60_8bit_420_Q23.xml && rm bitstreams/svt_M1_AOV5_1920x1080_60_8bit_420_Q23.y4m)> bitstreams/svt_M1_AOV5_1920x1080_60_8bit_420_Q23_vmaf.log 2>&1''',

    'vvenc_ffmpeg_vmaf_exe'  : '''(./vvdecapp -b bitstreams/vvenc_M4_AOV5_1920x1080_60_8bit_420_Q19.bin -o /dev/shm/bitstreams/vvenc_M4_AOV5_1920x1080_60_8bit_420_Q19.yuv -t 1 && /home/Weekend_Script/scripts/tools/vmaf --reference resized_clips/AOV5_1920x1080_60_8bit_420.yuv --distorted /dev/shm/bitstreams/vvenc_M4_AOV5_1920x1080_60_8bit_420_Q19.yuv -w 1920 -h 1080 -p 420 --aom_ctc v1.0 -b 8 -o bitstreams/vvenc_M4_AOV5_1920x1080_60_8bit_420_Q19.xml && rm /dev/shm/bitstreams/vvenc_M4_AOV5_1920x1080_60_8bit_420_Q19.yuv) > bitstreams/vvenc_M4_AOV5_1920x1080_60_8bit_420_Q19.log 2>&1 ''',
    
    'features_ffmpeg' : '''/home/CI_Script/scripts/tools/ffmpeg -nostdin -r 25 -i /home/user/Weekend_automation/features/20220119_masterbitstreams/RestorationFilter_test/svt_M13_DOTA2_60f_420_10bit_Q63.bin -s 1920x1080 -f rawvideo -pix_fmt yuv420p10le -r 25 -i /feature_testing/DOTA2_60f_420_10bit.yuv -lavfi "ssim=stats_file=/home/user/Weekend_automation/features/20220119_masterbitstreams/RestorationFilter_test/svt_M13_DOTA2_60f_420_10bit_Q63.ssim;[0:v][1:v]psnr=stats_file=/home/user/Weekend_automation/features/20220119_masterbitstreams/RestorationFilter_test/svt_M13_DOTA2_60f_420_10bit_Q63.psnr" -f null -  > /home/user/Weekend_automation/features/20220119_masterbitstreams/RestorationFilter_test/svt_M13_DOTA2_60f_420_10bit_Q63.log 2>&1''',

    'features_ffmpeg_psnr' : '''(/usr/bin/time --verbose /home/CI_Script/scripts/tools/ffmpeg -nostdin -r 25 -i bitstreams/svt_M13_input_clip_Q63.bin -s 1920x1080 -f rawvideo -pix_fmt yuv420p10le -r 25 -i feature_testing/DOTA2_60f_420_10bit.yuv -lavfi "psnr=stats_file=bitstreams/svt_M13_input_clip_Q63.psnr" -f null - ) > bitstreams/svt_M13_input_clip_Q63.log 2>&1''',
    '4_decoder_test' : '''(/home/CI_Script/scripts/tools/aomdec bitstreams/svt_M7_clip_Q48.bin --rawvideo -o clip_aom_dec.yuv && md5sum clip_aom_dec.yuv > bitstreams/svt_M7_clip_Q48.md5log && rm -rf clip_aom_dec.yuv && /home/CI_Script/scripts/tools/dav1d -i bitstreams/svt_M7_clip_Q48.bin --muxer yuv -o clip_dav1d.yuv && md5sum clip_dav1d.yuv >> bitstreams/svt_M7_clip_Q48.md5log && rm -rf clip_dav1d.yuv && /home/CI_Script/scripts/tools/ffmpeg -i bitstreams/svt_M7_clip_Q48.bin -strict -1 -f rawvideo  clip_ffmpeg.yuv && md5sum clip_ffmpeg.yuv >> bitstreams/svt_M7_clip_Q48.md5log && rm -rf clip_ffmpeg.yuv && ./SvtAv1DecApp -i bitstreams/svt_M7_clip_Q48.bin -o clip_svt.yuv && md5sum clip_svt.yuv >> bitstreams/svt_M7_clip_Q48.md5log && rm -rf clip_svt.yuv) > bitstreams/svt_M7_clip_Q48.log 2>&1 '''
}


TEST_SETS = {
                'test_set_seq_table': [
                    #1080p
                    {'name':'DOTA2_60f_420_10bit'},
                    {'name':'Netflix_FoodMarket_1920x1080_60fps_8bit_420_60f_10bit'},
                    {'name':'rush_hour_1080p25_60f'},
                    {'name':'life_1080p30_60f'},
                    #720p
                    {'name':'Netflix_BarScene_1280x720_60fps_true_10bit_420_60f'},
                    {'name':'vidyo4_720p_60fps_60f_10bit'},
                    {'name':'Netflix_RollerCoaster_1280x720_60fps_8bit_420_60f'},
                    {'name':'KristenAndSara_1280x720_60f'},
                    #360p
                    {'name':'red_kayak_360p_60f_10bit'},
                    {'name':'shields_640x360_60f_10bit'},
                    {'name':'blue_sky_360p_60f'},
                    {'name':'thaloundeskmtg360p_60f'},
                    #hard clips
                    {'name':'TelevisionClip_1080P-0604_horizontal_clip_0_k_2'},

                    ],
                '1080p_clipset': [
                    #1080p
                    {'name':'DOTA2_60f_420_10bit'},
                    {'name':'Netflix_FoodMarket_1920x1080_60fps_8bit_420_60f_10bit'},
                    {'name':'rush_hour_1080p25_60f'},
                    {'name':'life_1080p30_60f'},
                    {'name':'TelevisionClip_1080P-0604_horizontal_clip_0_k_2'},
                    ],
                '360p_clipset': [
                    #360p
                    {'name':'red_kayak_360p_60f_10bit'},
                    {'name':'shields_640x360_60f_10bit'},
                    {'name':'blue_sky_360p_60f'},
                    {'name':'thaloundeskmtg360p_60f'}, 
                    ],
                'undershoot_clipset': [
                    #1080p
                    {'name':'DOTA2_60f_420_10bit'},
                    {'name':'Netflix_FoodMarket_1920x1080_60fps_8bit_420_60f_10bit'},
                    {'name':'rush_hour_1080p25_60f'},
                    {'name':'life_1080p30_60f'},
                    #720p
                    {'name':'vidyo4_720p_60fps_60f_10bit'},
                    {'name':'Netflix_RollerCoaster_1280x720_60fps_8bit_420_60f'},
                    {'name':'KristenAndSara_1280x720_60f'},
                    #360p
                    {'name':'red_kayak_360p_60f_10bit'},
                    {'name':'shields_640x360_60f_10bit'},
                    {'name':'blue_sky_360p_60f'},
                    {'name':'thaloundeskmtg360p_60f'},
                    {'name':'TelevisionClip_1080P-0604_horizontal_clip_0_k_2'},

                    ],
                'bufferInput_clipset': [
                    #1080p
                    {'name':'DOTA2_60f_420_10bit'},
                    {'name':'Netflix_FoodMarket_1920x1080_60fps_8bit_420_60f_10bit'},
                  #  {'name':'rush_hour_1080p25_60f'},
                  #  {'name':'life_1080p30_60f'},
                    #720p
                    {'name':'Netflix_BarScene_1280x720_60fps_true_10bit_420_60f'},
                    {'name':'vidyo4_720p_60fps_60f_10bit'},
                  #  {'name':'Netflix_RollerCoaster_1280x720_60fps_8bit_420_60f'},
                   # {'name':'KristenAndSara_1280x720_60f'},
                    #360p
                    {'name':'red_kayak_360p_60f_10bit'},
                    {'name':'shields_640x360_60f_10bit'},
                   # {'name':'blue_sky_360p_60f'},
                   # {'name':'thaloundeskmtg360p_60f'},
                    ],
                '4ss_clips_for_hang_check': [
                    #1080p
                    {'name':'Wheat_1920x1080'},
                    {'name':'Skater227_1920x1080_30fps_8bit'},
                    ],
                'long_clip_set': [
                    {'name':"Wheat_1920x1080"},
                    {'name':"Skater227_1920x1080_30fps_8bit"},
                    # {'name':"Netflix_Narrator_1920x1080_10bit_60Hz_P420"},
                    # {'name':"Netflix_RitualDance_1920x1080_10bit_60Hz_P420"}
                    ],
                'partyScene_test_set': [
                    {'name': "PartyScene_832x480_50"}
                    ],
                'mobisode_test_set': [
                    {'name':'Mobisode2_832x480_30'}
                    ],
                'filmgrain10bit_clips': [
                    {'name':'DOTA2_60f_420_10bit'},
                    {'name':'Netflix_BarScene_1280x720_60fps_true_10bit_420_60f'},
                    {'name':'Netflix_FoodMarket_1920x1080_60fps_8bit_420_60f_10bit'},
                    {'name':'red_kayak_360p_60f_10bit'},
                    {'name':'shields_640x360_60f_10bit'},
                    {'name':'vidyo4_720p_60fps_60f_10bit'}
                    ],
                'sc_test_set': [
                    {'name':'BigBuckBunnyStudio_1920x1080_60p_8byuv420'},
                    {'name':'KristenAndSaraScreen_1920x1080_60p_8byuv420p'},
                    {'name':'MobileDeviceScreenSharing'},
                    {'name':'MobileDeviceScreenSharing_1078x2220_15fps'},
                    {'name':'MobileDeviceScreenSharing_1080p'},
                    {'name':'MobileDeviceScreenSharing_1080p_2'},
                    {'name':'SceneComposition_1'},
                    {'name':'SceneComposition_1920x1080_15fps'},
                    {'name':'SceneComposition_2'},
                    {'name':'SceneComposition_3'},
                    {'name':'Slides1_1920x1080_30fps_8bit_420'},
                    {'name':'Slides2_1920x1080_30fps_8bit_420'},
                    {'name':'Spreadsheet_1920x1080_30fps_8bit_420'},
                    {'name':'wikipedia_420'},
                    {'name':'wikipedia_420_10bit'}
                    ],
                '444_pixel_fmt_set' : [
                    {'name' : '444p_Slides1_1920x1080_30fps_8bit_420'},
                    {'name' : '444p_Vlog_1080P-1f0a_horizontal_clip_0_k_10'},
                    {'name' : '444p_Chimera_DCI4k2398p_HDR_P3PQ_1920x1080_15_154x186'},
                    {'name' : '444p_Spreadsheet_1920x1080_30fps_8bit_420'},
                    {'name' : '444p_Sports_1080P-6710_horizontal_clip_0_k_1'},
                    {'name' : '444p_Vertical_Frog_24p_1080x1920'},
                    {'name' : '444p_Wheat_1920x1080'},
                    {'name' : '444p_VerticalVideo_480P-419c'},
                    {'name' : '444p_Sports_1080P-76a2_horizontal_clip_1_k_3'},
                    {'name' : '444p_MobileDeviceScreenSharing_1080p'},
                    {'name' : '444p_Meridian_UHD4k5994_HDR_P3PQ_1920x1080_2_188x678'},
                    {'name' : '444p_SceneComposition_2'},
                    {'name' : '444p_VerticalVideo_360P-579c'},
                    {'name' : '444p_TelevisionClip_1080P-0604_horizontal_clip_0_k_2'},
                    {'name' : '444p_Skater227_1920x1080_30fps_8bit'},
                    {'name' : '444p_VerticalVideo_720P-44de'},
                    {'name' : '444p_Vlog_1080P-75b0_horizontal_clip_0_k_7'},
                    {'name' : '444p_Vertical_DJ_1080x1920_24p'},
                    {'name' : '444p_TelevisionClip_1080P-63e6_horizontal_clip_2_k_2'},
                    {'name' : '444p_CosmosLaundromat_2k24p_HDR_P3PQ_23_456x398'},
                    ],

                '422_pixel_fmt_set' : [
                    {'name' : '422p_SceneComposition_2'},
                    {'name' : '422p_Sports_1080P-76a2_horizontal_clip_1_k_3'},
                    {'name' : '422p_Vlog_1080P-75b0_horizontal_clip_0_k_7'},
                    {'name' : '422p_TelevisionClip_1080P-0604_horizontal_clip_0_k_2'},
                    {'name' : '422p_TelevisionClip_1080P-63e6_horizontal_clip_2_k_2'},
                    {'name' : '422p_Skater227_1920x1080_30fps_8bit'},
                    {'name' : '422p_Vlog_1080P-1f0a_horizontal_clip_0_k_10'},
                    {'name' : '422p_Chimera_DCI4k2398p_HDR_P3PQ_1920x1080_15_154x186'},
                    {'name' : '422p_CosmosLaundromat_2k24p_HDR_P3PQ_23_456x398'},
                    {'name' : '422p_Meridian_UHD4k5994_HDR_P3PQ_1920x1080_2_188x678'},
                    {'name' : '422p_Wheat_1920x1080'},
                    {'name' : '422p_Sports_1080P-6710_horizontal_clip_0_k_1'},
                    {'name' : '422p_Vertical_Frog_24p_1080x1920'},
                    {'name' : '422p_VerticalVideo_480P-419c'},
                    {'name' : '422p_MobileDeviceScreenSharing_1080p'},
                    {'name' : '422p_Spreadsheet_1920x1080_30fps_8bit_420'},
                    {'name' : '422p_Vertical_DJ_1080x1920_24p'},
                    {'name' : '422p_VerticalVideo_360P-579c'},
                    {'name' : '422p_VerticalVideo_720P-44de'},
                    {'name' : '422p_Slides1_1920x1080_30fps_8bit_420'},
                    ],
                'high_res_clipset' : [
                    {'name' : 'Chimera_DCI4k2398p_HDR_P3PQ_1920x1080_0_7680x4320'},
                    {'name' : 'Chimera_DCI4k2398p_HDR_P3PQ_1920x1080_0_16384x8704'},
                    {'name' : 'Chimera_DCI4k2398p_HDR_P3PQ_1920x1080_0_4096x2160'},
                    {'name' : 'CosmosLaundromat_2k24p_HDR_P3PQ_5_7680x4320'},
                    {'name' : 'CosmosLaundromat_2k24p_HDR_P3PQ_5_7680x4320'},
                    ],
                'issue1939': [
                    {'name':'red_kayak_360p_60f_10bit'},
                    {'name':'shields_640x360_60f_10bit'},
                    {'name':'Netflix_BarScene_640x360_lanc_8bit_60Hz_P420'}, ## Issue 1939
                    ],
                'capped_CRF_deviation_clipset' : [
                    {'name' : 'crowd_run_1080p50_8bit'},
                    ],
                'hang_test_clips' : [
                    {'name' : 'issue1838_test'},
                    ],
                '60f_clipset': [
                    #1080p
                    {'name':'DOTA2_60f_420_10bit'},
                    {'name':'Netflix_FoodMarket_1920x1080_60fps_8bit_420_60f_10bit'},
                    {'name':'rush_hour_1080p25_60f'},
                    {'name':'life_1080p30_60f'},
                    #720p
                    {'name':'Netflix_BarScene_1280x720_60fps_true_10bit_420_60f'},
                    {'name':'vidyo4_720p_60fps_60f_10bit'},
                    {'name':'Netflix_RollerCoaster_1280x720_60fps_8bit_420_60f'},
                    {'name':'KristenAndSara_1280x720_60f'},
                    #360p
                    {'name':'red_kayak_360p_60f_10bit'},
                    {'name':'shields_640x360_60f_10bit'},
                    {'name':'blue_sky_360p_60f'},
                    {'name':'thaloundeskmtg360p_60f'},
                    ],
                'skip_compare_ON': [
                    {'name':'life_1080p_60f'},
                    ],
                'skip_compare_OFF': [
                    {'name':'life1080p30_end_30f'},
                    #{'name':'life1080p30_beg_30f'},
                    ],
                'all_intra': [
                    {'name':'BlueSky_360p25'},
                    {'name':'ControlledBurn_1280x720p30_420'},
                    {'name':'DrivingPOV_1280x720p_5994_10bit_420'},
                    {'name':'FourPeople_480x270_60'},
                    {'name':'Johnny_1280x720_60'},
                    {'name':'KristenAndSara_1280x720_60'},
                    {'name':'ParkJoy_480x270_50'},

                    ],
                'still_image': [
                    {'name':'Butterfly'},
                    {'name':'Agapanthus_Postbloom2'},
                    {'name':'animals_00'},
                    {'name':'animals_03'},
                    {'name':'animals_09'},
                    {'name':'buildings_03'},
                    {'name':'Berlin-Fernsehturm'},
                    {'name':'Big_Easy_chair'},
                    {'name':'Berlin-Fernsehturm'},
                    {'name':'buildings_02'},

                    ],                                        
            }


ERROR_PATTERNS = ["failed to allocate compressed data buffer",
              "failed to read full temporal unit",
              "failed to read frame size",
              "failed to read full frame",
              "failed to read proper y4m frame delimiter",
              "failed to allocate system of equations of size",
              "failed to init",
              "failed to init equation system for block_size",
              "failed to alloc a or at_a_inv or block_size",
              "failed to allocate memory for block of size",
              "failed to allocate noise state for channel",
              "can't add memory entry",
              "you have memory leak or you need increase mem_entry_size",
              "something wrong. you freed a unallocated memory",
              "not enough memory for memory profile",
              "leaked at",
              "cdf error, frame_idx_r",
              "unhandled quarter_pel_refinement_method",
              "no center selected",
              "bug, too many frames in undisplayed queue",
              "bug, no frame in undisplayed queue",
              "unable to allocate temp values of size",
              "unable to allocate copy of A",
              "failed to init lut",
              "invalid noise param: lag",
              "invalid noise param: lag",
              "failed to allocate noise state for channel",
              "invalid shape",
              "unable to allocate buffer of size",
              "not enough flat blocks to update noise estimate",
              "adding block observation failed",
              "solving latest noise equation system failed",
              "solving latest noise strength failed",
              "solving combined noise equation system failed",
              "solving combined noise strength failed",
              "unable to init flat block finder",
              "unable to realloc buffers",
              "unable to denoise image",
              "unable to get grain parameters",
              "unsupported block size",
              'Error',
              'Error instance 1',
              'Segmentation fault (core dumped)',
              'double free or corruption (out)',
              'Aborted (core dumped)'
]


if __name__ == '__main__':
    
    main()
