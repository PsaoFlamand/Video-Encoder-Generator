import os
import subprocess
import re
import glob
import csv
import smtplib
import math
import sys
import shutil
import argparse
import datetime
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.message import Message

EMAIL_SENDER = 'AutoSender@intel.com'
EMAIL_RECIPIENTS = []


def mr_configurations():
    KEYINT = {'zip' : -1,
          '1 second' : '1s',
          '2 second' : '2s',
          '3 second' : '3s',
          }

    PRESETS = {
    'fast'  : [12, 13],
    'medium' : [4, 8, 12],
    'standard' : [4, 6, 8, 10, 12],
    'aom_tracking':[3, 5, 7, 9],
    'svt_tracking':[0],
        }

    CLIPSET = {
    'obj_1_fast_8bit'  : 'obj-1-fast_8bit_y4m',
    'obj_1_fast_10bit' : 'obj-1-fast_10bit_y4m',
    'aom_test_clips' : 'aom_performance_testing'
        }
    
    MR_TESTS = {
    'svt_CRF_1lp_1p_8bit'    : ['svt_CRF_1lp_1p_MR', CLIPSET['obj_1_fast_8bit'], PRESETS['standard'], KEYINT['zip']],
    'svt_CRF_1lp_1p_10bit'   : ['svt_CRF_1lp_1p_MR', CLIPSET['obj_1_fast_10bit'],  PRESETS['standard'], KEYINT['zip']],

    'svt_CRF_1lp_2p_8bit'    : ['svt_CRF_1lp_2p_MR', CLIPSET['obj_1_fast_8bit'], PRESETS['standard'], KEYINT['zip']],
    'svt_CRF_1lp_2p_10bit'   : ['svt_CRF_1lp_2p_MR', CLIPSET['obj_1_fast_10bit'], PRESETS['standard'], KEYINT['zip']],

    'svt_CRF_nonlp_1p_8bit'  : ['svt_CRF_nonlp_1p_MR', CLIPSET['obj_1_fast_8bit'], PRESETS['standard'], KEYINT['zip']],
    'svt_CRF_nonlp_1p_10bit' : ['svt_CRF_nonlp_1p_MR', CLIPSET['obj_1_fast_10bit'], PRESETS['standard'], KEYINT['zip']],

    'svt_CRF_nonlp_2p_8bit'  : ['svt_CRF_nonlp_2p_MR', CLIPSET['obj_1_fast_8bit'], PRESETS['standard'], KEYINT['zip']],
    'svt_CRF_nonlp_2p_10bit' : ['svt_CRF_nonlp_2p_MR', CLIPSET['obj_1_fast_10bit'], PRESETS['standard'], KEYINT['zip']],

    'svt_VBR_1lp_1p_8bit'    : ['svt_VBR_1lp_1p_MR', CLIPSET['obj_1_fast_8bit'], PRESETS['standard'], KEYINT['zip']],
    'svt_VBR_1lp_1p_10bit'   : ['svt_VBR_1lp_1p_MR', CLIPSET['obj_1_fast_10bit'], PRESETS['standard'], KEYINT['zip']],

    'svt_VBR_1lp_2p_8bit'    : ['svt_VBR_1lp_2p_MR', CLIPSET['obj_1_fast_8bit'], PRESETS['standard'], KEYINT['zip']],
    'svt_VBR_1lp_2p_10bit'   : ['svt_VBR_1lp_2p_MR', CLIPSET['obj_1_fast_10bit'], PRESETS['standard'], KEYINT['zip']],
    
    'aom_performance_tracking' : ['aom_test', CLIPSET['aom_test_clips'], PRESETS['aom_tracking'], KEYINT['zip']],
    'svt_performance_tracking' : ['svt_test', CLIPSET['aom_test_clips'], PRESETS['svt_tracking'], KEYINT['zip']],

    }
    
    return MR_TESTS


def main():
    script_mode = 1 # 0: MR testing | 1: Performance Tracking

    # MR Settings
    configurations_to_test = ['svt_CRF_1lp_1p_8bit']
    mr_number = "2117"
    mr_url = "https://gitlab.com/AOMediaCodec/SVT-AV1.git"

    # Performance Tracking Settings
    performance_tracking_urls = ['https://aomedia.googlesource.com/aom', 'https://git.ffmpeg.org/ffmpeg.git','https://gitlab.com/AOMediaCodec/SVT-AV1.git']

    if script_mode == 0:
        for test_name in configurations_to_test:
            test_mod_ref(test_name, mr_number, '', mr_url)
    elif script_mode == 1:
        performance_tracking(performance_tracking_urls)


def performance_tracking(git_urls):
    while 1:
        for url in git_urls:
            print('checking {}'.format(url))

            encoder_name = url.split('/')[-1].split('.')[0]
            enc_path = os.path.join(os.getcwd(),encoder_name)

            # Clone the repo if it doesn't exist
            call('git clone {} {}'.format(url, encoder_name))

            # Get the different commit types, and latest commit message
            previous_commit, list_of_tags, latest_commits = get_commit_details(enc_path)

            # Get the highest numbere revision from the list of tags
            previous_largest_tag = find_largest_tag(list_of_tags)
            
            # Update the repo folder
            call('git pull', enc_path)
            if 'aom' in url:
                call('git fetch origin main', enc_path)
            else:
                call('git fetch origin master', enc_path)
                
            call('git checkout FETCH_HEAD', enc_path)
            
            commits_to_check_cmd = 'git rev-list --ancestry-path {}..HEAD --abbrev-commit --reverse'.format(previous_commit)
            print(commits_to_check_cmd)
            commits_to_check = call(commits_to_check_cmd, enc_path)

            current_commit, list_of_tags, latest_commits = get_commit_details(enc_path)

            # Get the latest largest tag
            largest_tag = find_largest_tag(list_of_tags)
        
            evaluate_commits(url, enc_path, commits_to_check, largest_tag, previous_largest_tag, current_commit, previous_commit)

        print('waiting one hour before checking again')

        time.sleep(3600)


def test_mod_ref(test_name, mod_commit, ref_commit, git_url, test_ref=True):
    if len(mod_commit) == 4:
        is_mr_test = True
        mr_number = mod_commit
        mod_commit, ref_commit, source_branch = find_ref_mod_hashes(mr_number)
        folder_name = 'MR{}'.format(mr_number)
    else:
        is_mr_test = False
        folder_name = '{}_{}_vs_{}'.format(test_name,mod_commit[:5],ref_commit[:5])
        
    print("REF: %s, MOD: %s" % (ref_commit, mod_commit))

    parent_folder, test_folder = create_folder(folder_name, is_mr_test, test_name)
    
    configurations_to_test = get_configurations_to_test(test_name)
    
    print("================ Running {} on commit {}================".format(configurations_to_test, mod_commit))

    copy_files_to_test_folder(test_folder)
    
    if is_mr_test:
        generate_and_execute_commands(configurations_to_test, test_folder, mr_number, ref_commit, test_ref)
        result_files = get_result_files(mod_commit, ref_commit, test_folder)
    else:
        generate_and_execute_commands(configurations_to_test, test_folder, mod_commit, ref_commit, test_ref)
        result_files = get_result_files(mod_commit, ref_commit, parent_folder)

    results = get_comparisons(result_files, mod_commit, ref_commit)
    
    html = generate_html(results)
    send_email(html, mod_commit, ref_commit)
    
    print("================ script completed ================")


def evaluate_commits(url, enc_path, commits_to_check, largest_tag, previous_largest_tag, current_commit, previous_commit):
    print('These are the Commits since the last check',commits_to_check)
    if 'aom' in url:
        for commit in commits_to_check:
            '''Check to see if the given commit is a perfomance commit and should therefore be testsed'''
            is_performance_change, previous_commit, commit_message = check_message_for_perfomance_changes(enc_path, commit)

            if is_performance_change:
                test_mod_ref('aom_performance_tracking', commit, previous_commit, url)
                
    elif 'ffmpeg' in url:
        largest_tag_hash_cmd = 'git rev-list -n 1 {}'.format(largest_tag)
        largest_tag_hash = call(largest_tag_hash_cmd, enc_path)[0]
        
        previous_largest_tag_hash_cmd = 'git rev-list -n 1 {}'.format(previous_largest_tag)
        previous_largest_tag_hash = call(previous_largest_tag_hash_cmd, enc_path)[0]

        git_diff_cmd = 'git diff {} {} -- ./libavcodec/libsvtav1.c'
        git_diff = call(git_diff_cmd, enc_path)

        if git_diff:
            send_ffmpeg_email(largest_tag, previous_largest_tag, git_diff)
            
    elif 'svt' in url.lower():
        week_number = datetime.datetime.today().weekday()
        if week_number == 0 and current_commit != previous_commit:
            test_mod_ref('svt_performance_tracking', current_commit, previous_commit, url, False)


def find_largest_tag(list_of_tags):
    refined_tag = [x for x in list_of_tags if (len(x) > 2 and x[1].isdigit())]
    sorted_tag = sorted(refined_tag, key=lambda x: x[1])
    if sorted_tag:
        return sorted_tag[-1]
    else:
        return 


def get_commit_details(enc_path):
    latest_commits = call('git rev-parse --short=8 HEAD', enc_path)
    latest_commit = latest_commits[0]
    
    list_of_tags = [x.split('/')[-1] for x in call("git ls-remote --tags origin", enc_path) if ('{' not in x and 'dev' not in x and 'v' not in x)]
    
    return latest_commit, list_of_tags, latest_commits


def check_message_for_perfomance_changes(enc_path, commit):
    commit_message_cmd = 'git show --pretty=format:"%ad%n%n%s%n%n%b" -s "{}"'.format(commit)
    commit_message = call(commit_message_cmd, enc_path)
    
    previous_commit_cmd = 'git log --pretty=format:"%h" -n 2 {}'.format(commit)
    previous_commit = call(previous_commit_cmd, enc_path)[-1]

    performance_key_words = ["stats_changed", "performance", "speedup", "bdrate", "bd-rate"]
    
    for message_line in commit_message:
        for key_word in performance_key_words:
            if key_word in message_line.lower():
                return True, previous_commit, commit_message
        
    return False, previous_commit, commit_message


def send_ffmpeg_email(tag, previous_tag, diffs):
    print('we have reached the mailing room')    

    message_str = 'Hi Team, \n We have detected a change in the ffmpeg svt file between {} and {}.\n\n Please see below for the diff.\n\n\n {}\n\nThanks, \n\nffmpeg-tracker'.format(tag, previous_tag, '\n'.join(list(diffs)))
    
    message = MIMEMultipart("alternative", None, [MIMEText(message_str)])
    sender = 'Auto_Tag_sender@intel.com'
    
    message['From'] = EMAIL_SENDER
    message['To'] = ", ".join(EMAIL_RECIPIENTS)
    message['Subject'] = 'FFMPEG svt file results'
    
    print('Sending Results...')
    s = smtplib.SMTP('smtp.intel.com',25)
    s.sendmail(sender, EMAIL_RECIPIENTS, message.as_string())
    s.quit()
    print('Results Sent!')


''' MOD vs REF Engine'''

def find_ref_mod_hashes(mr_number):
    # URL of the GitLab repository
    GITLAB_URL = "https://gitlab.com/AOMediaCodec/SVT-AV1.git"

    # Extract project ID and MR ID from GitLab URL
    project_id = GITLAB_URL.split("/")[-2] + '%2F' + GITLAB_URL.split("/")[-1].split('.')[0]

    # API endpoint for getting MR information
    mr_endpoint = "https://gitlab.com/api/v4/projects/{}/merge_requests/{}".format(project_id, mr_number)

    # Make API request to get MR information
    try:
        merge_pipe = subprocess.Popen('curl -x http://proxy.sc.intel.com:911 -Ls -k  {}'.format(mr_endpoint), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
    except:
        merge_pipe = subprocess.Popen('curl -Ls -k  {}'.format(mr_endpoint), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE )
    
    merge_commit_list = merge_pipe.communicate()[0]

    mod_hash = re.findall(r'"sha":"(.*?)"',str(merge_commit_list))[0]
    ref_hash = re.findall(r'{"base_sha":"(.*?)"', str(merge_commit_list))[0]
    source_branch_name = re.findall(r'"source_branch":"(.*?)"', str(merge_commit_list))[0]

    return mod_hash, ref_hash, source_branch_name


def get_result_files(mod_commit,ref_commit, folder):
    result_files = []
    for root, _, files in os.walk(folder):
        for file in files:
            if '_result' in file and ((mod_commit[:5] in file or ref_commit[:5] in file) or (mod_commit[:5] in os.path.split(root)[-1] or ref_commit[:5] in os.path.split(root)[-1]) ):
                result_files.append(os.path.join(root, file))

    return result_files


def create_folder(folder_name, is_mr_test, test_name):
    # Create MR folder
    if is_mr_test:
        parent = 'MRs'
    else:
        parent = test_name
    parent_folder = os.path.join(os.getcwd(),parent)
    child_folder = os.path.join(parent_folder, folder_name)
    if not os.path.isdir(parent_folder):
        os.mkdir(parent_folder)
    if not os.path.isdir(child_folder):
        os.mkdir(child_folder)

    return parent_folder, child_folder


def get_configurations_to_test(test_name):
    # Get configurations to test
    if not test_name:
        configurations_to_test = CONFIGURATIONS_TO_TEST
    else:
        configurations_to_test = [test_name]

    return configurations_to_test


def copy_files_to_test_folder(test_folder):
    # Copy necessary files to MR folder
    mr_tools_folder = os.path.join(test_folder,'tools')
    
    if not os.path.isdir(mr_tools_folder):
        os.mkdir(mr_tools_folder)

    for file in glob.glob('{}/*'.format(os.path.join(os.getcwd(), 'tools'))):
        shutil.copy(file, mr_tools_folder)
    for file in glob.glob('{}/*.py'.format(os.getcwd())):
        shutil.copy(file, test_folder)        


def generate_and_execute_commands(configurations_to_test, test_folder, mod_commit, ref_commit, test_ref):
    result_files = list()

    for configuration in configurations_to_test:    
        test_name, stream_dir, presets, keyint = mr_configurations()[configuration]
        presets = ",".join(str(i) for i in presets)
        stream_dir = find_stream_folder(stream_dir)

        mod_pygen = "python PyGenerateCommands.py --test-name {} --stream {} --presets {} --intraperiod {} --commit {}".format(test_name, stream_dir, presets, keyint, mod_commit)
        
        ref_pygen = "python PyGenerateCommands.py --test-name {} --stream {} --presets {} --intraperiod {} --commit {}".format(test_name, stream_dir, presets, keyint, ref_commit)

        print('running {}'.format(mod_pygen))
        call(mod_pygen, test_folder)
        if test_ref:
            print('running {}'.format(ref_pygen))
            call(ref_pygen, test_folder)


def find_stream_folder(stream_dir):
    for root, _, files in os.walk('/home/'):
        if stream_dir in root:
            return root


'''-------------------------------------------------------------------Get BDR Comparison Pairs-------------------------------------------------------------------------------'''

def get_comparisons(result_files, mod_hash, ref_hash):
    """
    Compare the results in the given result files for the given mod encoder hash.

    Args:
        result_files (list of str): A list of result file paths.
        mod_hash (str): The hash of the mod encoder.

    Returns:
        list of list of str: A list of comparison results.
    """    
    results = []

    encoders = get_squashed_encoders(result_files)
    
    selections = auto_comparison_selector(encoders, mod_hash, ref_hash)

    for (encoder_pair, presets) in selections:
        ref, mod = encoder_pair.split('|')

        sorted_presets = sorted(presets, key=lambda x: int(x.split('M')[-1]))
        
        '''puts data from result txt into a large dictionary'''
        bdr_data, system_data, clips = process_data(result_files)

        '''generates a dictionary of bdrate values'''
        detailed_bdr_results = get_detailed_bdr_results(mod, ref, presets, bdr_data,clips)

        '''generates a dictionary of system speed, memory values'''
        system_results = get_system_results(mod, ref, presets, system_data)

        '''# generates overall summary of metrics by preset, per metric'''
        averaged_bdr_results = get_averaged_bdr_results(detailed_bdr_results, presets,clips) 

        for bdr_result, system_result in zip(averaged_bdr_results, system_results):
            results.append([system_result[0], ' ', system_result[1]] + bdr_result + system_result[2:])

    return results


def get_squashed_encoders(result_files):
    encoders = set()
    
    for result_file in result_files:
        with open(result_file) as file:
            content = file.readlines()[1:]
            encoders.update(x.split('\t')[1] for x in content if x.split('\t')[1])
    return encoders


def auto_comparison_selector(encoder_list, mod_hash,ref_hash):
    # Step 1: Group encoders by type
    encoder_groups = get_grouped_encoders(encoder_list)
    
    # Step 2: Select a reference encoder
    ref_selection = None
    for encoder in encoder_groups:
        if 'av1' in encoder.lower() and 'svt' not in encoder.lower() or 'libaom' in encoder.lower():
            ref_selection = '{}_{}'.format(encoder, encoder_groups[encoder][0])
    
    # Step 3: Get paired encoder selections
    if ref_selection:
        paired_encoders_1 = get_paired_encoders(mod_hash,ref_hash, encoder_list, encoder_groups, ref_selection, '1')
        paired_encoders_1 = dict((k, v) for k, v in paired_encoders_1.iteritems() if k.split('|')[1] not in k.split('|')[0])
        enc_selections_1 = get_enc_selections(paired_encoders_1, [str(x) for x in range(len(paired_encoders_1))])
    else:
        enc_selections_1 = []
    
    paired_encoders_2 = get_paired_encoders(mod_hash,ref_hash, encoder_list, encoder_groups, None)
    enc_selections_2 = get_enc_selections(paired_encoders_2, [str(x) for x in range(len(paired_encoders_2))])
    
##    return  enc_selections_1 + enc_selections_2
    return  enc_selections_2


def get_grouped_encoders(squashed_encoder_list, comparison_selection=None):
    grouped_encoders = {}
    for enc_name in squashed_encoder_list:
        if enc_name[-1].isdigit():
            enc_parts = enc_name.split('_')
            enc_group = '_'.join(enc_parts[:-1])
            enc_preset = enc_parts[-1]

            if enc_group not in grouped_encoders:
                grouped_encoders[enc_group] = [enc_preset]
            else:
                grouped_encoders[enc_group].append(enc_preset)

            if comparison_selection == '1':
                index = squashed_encoder_list.index(enc_name)
                print('({0}) -> {1}'.format(index, enc_name))
    return grouped_encoders


def get_paired_encoders(mod_hash,ref_hash, squashed_encoder_list, grouped_encoders, ref_selection=None, comparison_selection=None):
    """
    Returns a dictionary of paired encoders and their common presets.
    
    Args:
        mod_hash (str): The hash of the mod encoder.
        squashed_encoder_list (list of str): A list of encoder names in squashed format.
        grouped_encoders (dict): A dictionary of encoder groups and their presets.
        ref_selection (str, optional): The reference encoder selection. Defaults to None.
        comparison_selection (str, optional): The comparison selection. Defaults to None.
    
    Returns:
        dict: A dictionary of paired encoders and their common presets.
    """
    paired_encoders = {}

    if comparison_selection == '1':
        ref_encoder = ref_selection
        
        for mod_encoder, mod_presets in grouped_encoders.items():
            if mod_encoder != ref_encoder:
                pair_id = '{0}|{1}'.format(ref_encoder, mod_encoder)
                paired_encoders[pair_id] = sorted(mod_presets, key=lambda x: int(x.replace('M', '')))
    else:
        for ref_encoder, ref_presets in grouped_encoders.items():
                for mod_encoder, mod_presets in grouped_encoders.items():
                    if ref_hash[:5] in ref_encoder or mod_hash[:5] in mod_encoder:
                        if mod_encoder != ref_encoder:
                            common_presets = list(set(ref_presets).intersection(mod_presets))
                            if common_presets:
                                pair_id = '|'.join([ref_encoder, mod_encoder])
                                paired_encoders[pair_id] = sorted(common_presets, key=lambda x: int(x.replace('M', '')))
    
    return paired_encoders


def get_enc_selections(paired_encoders, pair_selections):
    if not paired_encoders:
        return []

    enc_selections = []

    for pair_selection in pair_selections:
        try:
            index = int(pair_selection.strip())
            pair = list(paired_encoders.items())[index]
            enc_selections.append(pair)
        except ValueError:
            print('Invalid Selection, Retry?')
            enc_selections = []
            break

    return enc_selections


def process_data(files):
    """
    Loop through all files in the results folder and process the data.

    Args:
        files (list): A list of file paths.

    Returns:
        A tuple of three dictionaries:
        - A dictionary with BDR data.
        - A dictionary with system data.
        - A set of all clips.
    """
    bdr_data = {}
    cvh_data = {}
    system_data = {}
    all_clips = set()
    
    for file in files:
        if "convex" not in file:
            for metric in SYS_METRICS:
                data, clips = process_data_helper(file, metric, system_data)
                all_clips.update(clips)

            for metric in METRICS:
                data, clips = process_data_helper(file, metric, bdr_data)

        else:
            metric_name = os.path.split(file)[-1].split("_c")[0]
            data, clips = process_data_helper(file, metric_name, cvh_data)
            all_clips.update(clips)

    return (cvh_data, system_data, all_clips) if cvh_data else (bdr_data, system_data, all_clips)


def process_data_helper(file, metric_name, data):
    last_line_number = len(open(file).readlines()) - 2
    clips = set()

    '''Open result File'''
    with open(file, mode='r') as csv_file:
        content = list(csv.DictReader(csv_file, delimiter='\t'))
        rates = []
        metrics = []
        preset_pattern = re.compile(r'M\d\d?')
        
        for index, row in enumerate(content):
            if not row['ENC_NAME']:
                continue

            encoder_name = re.search(r'(.+?)(?=_M\d)', row['ENC_NAME']).group()

            row['INPUT_SEQUENCE'] = re.sub(r'_lanc', '', row['INPUT_SEQUENCE'])
            resolution_search = re.search(r'(\d+x\d+)to(\d+x\d+)', row['INPUT_SEQUENCE'])
            
            if resolution_search:
                row['INPUT_SEQUENCE'] = re.sub(r'\d+x\d+to\d+x\d+', resolution_search.group(2), row['INPUT_SEQUENCE'])

            preset = re.search(r'M\d\d?', row['ENC_NAME']).group()

            data.setdefault(encoder_name, {}).setdefault(metric_name, {}).setdefault(preset, {})

            '''Accumulate data'''
            if metric_name in SYS_METRICS:
                if row[metric_name].strip() and row[metric_name] != 'n/a':
                    metric = float(row[metric_name])
                    metrics.append(metric)
                else:
                    metrics.append(0)
            else:
                try:
                    if row['FILE_SIZE'].strip() and row[metric_name].strip() and row['FILE_SIZE'] != 'n/a' and row[metric_name] != 'n/a':
                        metric = float(row[metric_name])
                        if metric == 0:
                            continue
                        
                        rate = float(row['FILE_SIZE'])
                        rates.append(rate)
                        metrics.append(metric)
                except:
                    print('ERROR IN :')
                    print('row',row)

            if index == len(content) - 1:
                next_sequence = None
            else:
                next_sequence = '_'.join(content[index+1]['INPUT_SEQUENCE'].split('_')[:-1])
            
            row['INPUT_SEQUENCE'] = '_'.join(row['INPUT_SEQUENCE'].split('_')[:-1])
            clips.add(row['INPUT_SEQUENCE'])

            '''Populate the MegaDict entries accordingly after each shift in sequence naming'''                
            if (row['INPUT_SEQUENCE'] != next_sequence) or (index == last_line_number):
                '''Initialize the third layer of MegaDict'''
                if row['INPUT_SEQUENCE'] not in data[encoder_name][metric_name][preset]:
                    if metric_name in SYS_METRICS:
                        data[encoder_name][metric_name][preset][row['INPUT_SEQUENCE']] = [metrics]
                    else:
                        data[encoder_name][metric_name][preset][row['INPUT_SEQUENCE']] = [rates,metrics]
                else:
                    if metric_name in SYS_METRICS:
                        '''System Results'''
                        data[encoder_name][metric_name][preset][row['INPUT_SEQUENCE']].append(metrics)
                    else:
                        '''BDR Results'''
                        data[encoder_name][metric_name][preset][row['INPUT_SEQUENCE']].append(rates)
                        data[encoder_name][metric_name][preset][row['INPUT_SEQUENCE']].append(metrics)

                rates = list()
                metrics = list()


    return data, clips


def get_detailed_bdr_results(mod, ref, presets, bdr_data, clips):
    bdr_results = {}
    preset_search = re.search(r'_(M\d+)', ref)

    all_clips = sorted(clips)
        
    for metric in METRICS:
        bdr_results[metric] = {}
        for preset in presets:
            ref_preset = preset_search.group(1) if preset_search else preset
            ref = ref.split(preset_search.group(0))[0] if preset_search else ref
                
            bdr_results[metric][preset] = {}
            for clip in all_clips:
                ref_data = bdr_data[ref][metric][ref_preset][clip]
                mod_data = bdr_data[mod][metric][preset][clip]
                if ref_data[0] and mod_data[1]:
                    bdrate = bdRateExtend(ref_data[0], ref_data[1], mod_data[0], mod_data[1], 'None', False)
                    bdr_results[metric][preset][clip] = bdrate
                    
    return bdr_results


def get_system_results(mod_name, ref_name, presets, system_data):
    preset_search = re.search(r'_(M\d+)', ref_name)
    system_results = []
    for preset in presets:
        absolute_max_memory_deviation = 0

        ref_preset = preset_search.group(1) if preset_search else preset
        mod = system_data[mod_name]
        ref = system_data[ref_name.split(preset_search.group(0))[0] if preset_search else ref_name]

        result_mod_name = '{mod_name}_{preset}'.format(**vars())
        result_ref_name = '{}_{}'.format(ref_name.split(preset_search.group(0))[0] if preset_search else ref_name,ref_preset)

        total_mod_encode_cycles = sum(sum(mod['ENCODE_USER_TIME'][preset][clip][0]) + sum(mod['ENCODE_SYS_TIME'][preset][clip][0]) for clip in mod['ENCODE_USER_TIME'][preset].keys()) / 1000
        total_ref_encode_cycles = sum(sum(ref['ENCODE_USER_TIME'][ref_preset][clip][0]) + sum(ref['ENCODE_SYS_TIME'][ref_preset][clip][0]) for clip in mod['ENCODE_USER_TIME'][preset].keys()) / 1000
        total_mod_decode_cycles = sum(sum(mod['DECODE_USER_TIME'][preset][clip][0]) + sum(mod['DECODE_SYS_TIME'][preset][clip][0]) for clip in mod['DECODE_USER_TIME'][preset].keys()) / 1000
        total_ref_decode_cycles = sum(sum(ref['DECODE_USER_TIME'][ref_preset][clip][0]) + sum(ref['DECODE_SYS_TIME'][ref_preset][clip][0]) for clip in mod['DECODE_USER_TIME'][preset].keys()) / 1000

        
        for clip in mod['ENCODE_USER_TIME'][preset].keys():
            mem_dev = (max(mod['MAX_MEMORY'][preset][clip][0]) / max(ref['MAX_MEMORY'][ref_preset][clip][0])) - 1
            if abs(mem_dev) > abs(absolute_max_memory_deviation):
                absolute_max_memory_deviation = mem_dev
                
            
        max_mem_mod = max(max(mod['MAX_MEMORY'][preset][clip][0]) for clip in mod['ENCODE_USER_TIME'][preset].keys())
        max_mem_ref = max(max(ref['MAX_MEMORY'][ref_preset][clip][0]) for clip in mod['ENCODE_USER_TIME'][preset].keys())

        overall_encode_speed_deviation = total_ref_encode_cycles / total_mod_encode_cycles - 1 if total_mod_encode_cycles else "n/a"
        overall_decode_speed_deviation = total_ref_decode_cycles / total_mod_decode_cycles - 1 if total_mod_decode_cycles else "n/a"
        max_mem_dev = max_mem_mod / max_mem_ref - 1 if max_mem_ref else "n/a"
        total_mod_decode_cycles = total_mod_decode_cycles if total_mod_decode_cycles else 'n/a'
        total_ref_decode_cycles = total_ref_decode_cycles if total_ref_decode_cycles else 'n/a'
        system_results.append([
            result_mod_name,
            result_ref_name,
            total_mod_encode_cycles,
            total_ref_encode_cycles,
            total_mod_decode_cycles,
            total_ref_decode_cycles ,
            overall_encode_speed_deviation,
            overall_decode_speed_deviation,
            max_mem_dev,
            absolute_max_memory_deviation
        ])

    return system_results


def get_averaged_bdr_results(detailed_bdr_results,presets,clips):
    all_clips = sorted(list(clips))

    averaged_bdr_results = []

    for preset in presets:
        results = []
        line = '{}: '.format(preset)
        average_metrics = 0

        for metric in METRICS:
            metric_value = 0
            if not detailed_bdr_results[metric][preset]:
                results.append('n/a')
                continue
            for clip in all_clips:
                metric_value += detailed_bdr_results[metric][preset][clip]

            metric_value = metric_value/len(all_clips)

            if metric != 'VMAF_NEG':
                average_metrics += metric_value

            results.append(metric_value)

        average_metrics = average_metrics/3
        results.append(average_metrics)

        averaged_bdr_results.append(results)

    return averaged_bdr_results


'''-------------------------------------------------------------------CVH Macro-------------------------------------------------------------------------------'''


def bdRateExtend(rateA, distA, rateB, distB, bMode, bRange):
    # type: (list[float], list[float], list[float], list[float], str, bool) -> float
    minPSNRA = float(min(distA))
    maxPSNRA = float(max(distA))
    minPSNRB = float(min(distB))
    maxPSNRB = float(max(distB))

    minMinPSNR = min(minPSNRA, minPSNRB)
    maxMinPSNR = max(minPSNRA, minPSNRB)
    minMaxPSNR = min(maxPSNRA, maxPSNRB)
    maxMaxPSNR = max(maxPSNRA, maxPSNRB)

    minPSNR = minMinPSNR
    maxPSNR = minMaxPSNR

    if bRange:
        if (minPSNRA > maxPSNRB or minPSNRB > maxPSNRA):
            bdRate = 0
        else:
            bdRate = (maxPSNR - maxMinPSNR) / (maxPSNRA - minPSNRA)
            
        if (maxPSNRB < maxPSNRA):
            bdRate = -1 * bdRate

        return bdRate

    if (bMode == "LowAlways"):
        minPSNR = minMinPSNR
        maxPSNR = minMaxPSNR
    elif (bMode == "HighAlways"):
        minPSNR = maxMinPSNR
        maxPSNR = maxMaxPSNR
    elif (bMode == "BothAlways"):
        minPSNR = minMinPSNR
        maxPSNR = maxMaxPSNR
    elif (bMode == "None" or not (minPSNRA > maxPSNRB or minPSNRB > maxPSNRA)):
        if (minPSNRA > maxPSNRB):
            return 1
        if (minPSNRB > maxPSNRA):
            return -1
        minPSNR = maxMinPSNR
        maxPSNR = minMaxPSNR
    elif (bMode == "Low"):
        minPSNR = minMinPSNR
        maxPSNR = minMaxPSNR
    elif (bMode == "High"):
        minPSNR = maxMinPSNR
        maxPSNR = maxMaxPSNR
    elif (bMode == "Both"):
        minPSNR = minMinPSNR
        maxPSNR = maxMaxPSNR

    vA = bdRIntEnh(rateA, distA, minPSNR, maxPSNR)
    vB = bdRIntEnh(rateB, distB, minPSNR, maxPSNR)
    avg = (vB - vA) / (maxPSNR - minPSNR)

    bdRate = pow(10, avg) - 1
    return bdRate

#  Enhanced BD Rate computation method that performs extrapolation instead of
#  Computing BDRate within the "common interval, when and only when there is no PSNR overlap.


def bdRIntEnh(rate, dist, low, high, distMin=0, distMax=1E+99):
    # type: (list[float], list[float], float, float, int, int) -> float
    elements = len(rate)

    log_rate = [0] * (elements + 3)
    log_dist = [0] * (elements + 3)

    rate, dist, log_rate, log_dist, elements = addValues(
        rate, dist, log_rate, log_dist, elements)

    # Remove duplicates and sort data
    log_rate = sorted(set(log_rate))
    log_dist = sorted(set(log_dist))

    log_rate.append(0)
    log_rate.append(0)
    log_dist.append(0)
    log_dist.append(0)

    # If plots do not overlap, extend range
    # Extrapolate towards the minimum if needed
    if (log_dist[1] > low):
        for i in range(1, elements):
            log_rate[elements + 2 - i] = log_rate[elements + 1 - i]
            log_dist[elements + 2 - i] = log_dist[elements + 1 - i]

        elements = elements + 1
        log_dist[1] = low
        log_rate[1] = log_rate[2] + (low - log_dist[2]) * \
            (log_rate[2] - log_rate[3]) / (log_dist[2] - log_dist[3])

    # Extrapolate towards the maximum if needed
    if (log_dist[elements] < high):
        log_dist[elements + 1] = high
        log_rate[elements + 1] = log_rate[elements] + (high - log_dist[elements]) * (
            log_rate[elements] - log_rate[elements - 1]) / (log_dist[elements] - log_dist[elements - 1])
        elements = elements + 1

    result = intCurve(log_dist, log_rate, low, high,
                         elements, distMin, distMax)

    return result


def addValues(rate, dist, log_rate, log_dist, elements):
    # type: (list[float], list[float], list[float], list[float], int) -> tuple[list[float], list[float], list[float], list[float], int]
    i = 1
    for j in range(elements, 0, -1):
        # Add elements only if they are not empty
        if (len(rate) != 0 and len(dist) != 0 and rate[j-1] > 0 and dist[j-1] > 0):
            log_rate[i] = math.log(rate[j-1], 10)
            log_dist[i] = dist[j-1]
            i += 1
    elements = i - 1

    return rate, dist, log_rate, log_dist, elements


def pchipend(h1, h2, del1, del2):
    # type: (float, float, float, float) -> float
    D = ((2 * h1 + h2) * del1 - h1 * del2) / (h1 + h2)
    if (D * del1 < 0):
        D = 0
    elif ((del1 * del2 < 0) and (abs(D) > abs(3 * del1))):
        D = 3 * del1

    return D


def intCurve(xArr, yArr, low, high, elements,  distMin=0, distMax=1E+99):
    # type: (list[float], list[float], float, float, int, int, int) -> float

    H = [0] * (elements + 3)
    delta = [0] * (elements + 3)

    for i in range(1, elements):
        H[i] = xArr[i + 1] - xArr[i]
        delta[i] = (yArr[i + 1] - yArr[i]) / H[i]

    D = [0] * (elements + 3)

    D[1] = pchipend(H[1], H[2], delta[1], delta[2])

    for i in range(2, elements):
        D[i] = (3 * H[i - 1] + 3 * H[i]) / ((2 * H[i] + H[i - 1]) /
                                            delta[i - 1] + (H[i] + 2 * H[i - 1]) / delta[i])

    D[elements] = pchipend(H[elements - 1], H[elements - 2],
                           delta[elements - 1], delta[elements - 2])
    C = [0] * (elements + 3)
    B = [0] * (elements + 3)

    for i in range(1, elements):
        C[i] = (3 * delta[i] - 2 * D[i] - D[i + 1]) / H[i]
        B[i] = (D[i] - 2 * delta[i] + D[i + 1]) / (H[i] * H[i])

    result = 0
    #    Compute rate for the extrapolated region if needed
    s0 = xArr[1]
    s1 = xArr[2]

    for i in range(1, elements):
        s0 = xArr[i]
        s1 = xArr[i + 1]

        #  clip s0 to valid range
        s0 = max(s0, low, distMin)
        s0 = min(s0, high, distMax)

        #  clip s1 to valid range
        s1 = max(s1, low, distMin)
        s1 = min(s1, high, distMax)

        s0 = s0 - xArr[i]
        s1 = s1 - xArr[i]

        if (s1 > s0):
            result = result + (s1 - s0) * yArr[i]
            result = result + (s1 * s1 - s0 * s0) * D[i] / 2
            result = result + (s1 * s1 * s1 - s0 * s0 * s0) * C[i] / 3
            result = result + (s1 * s1 * s1 * s1 - s0 *
                               s0 * s0 * s0) * B[i] / 4

    return result

'''-------------------------------------------------------------------Result Evaluation-------------------------------------------------------------------------------'''


def generate_html(results):
    '''sort results'''
    for index in range(len(results)):
        results[index][0] = re.sub(r'_\d+-\d+-\d+','',results[index][0])
        results[index][1] = re.sub(r'_\d+-\d+-\d+','',results[index][1])
        
    sorted_results = sorted([x for x in results], key=lambda x: ('_'.join(x[1].split('_')[:-1]),'_'.join(x[0].split('_')[:-1]), int(x[0].split('_')[-1][1:])))

    headers = ['MOD','vs.','REF',
              'PSNR Y','SSIM Y','VMAF Y',
              'VMAF-NEG Y','AVG PSNR/SSIM/VMAF',
              'Mod Sum Encode Cycles','Ref Sum Encode Cycles',
              'Mod Sum Decode Cycles','Ref Sum Decode Cycles',
              'Encode Cycles Speed Dev YUV', 'Decode Cycles Speed Dev YUV',
              'Max Value Memory Deviation ALL', 'Abs Max Clip Memory Deviation ALL']

    headers = [header for value, header in zip(sorted_results[0], headers) if value != 'n/a']        

    html_table = ""
    html_table += "<table border='1'>"
    html_table += "<tr>"

    # Add column headers with green background
    for header in headers:
        html_table += "<th style='background-color:lightgreen'> %s </th>" % (header)

    html_table += "</tr>"

    # Add table rows
    for row in sorted_results:
        html_table += "<tr>"
        for cell in row:
            if cell == 'n/a':
                continue
            # Check if the cell value is a float
            if isinstance(cell, float) and -100 <= cell <= 100:
                cell_percentage = cell * 100
                if cell_percentage != 0:
                    html_table += "<td style='background-color:red'>%.2f%%</td>" % cell_percentage
                else:
                    html_table += "<td>%.0f%%</td>" % cell_percentage
            else:
                html_table += "<td>%s</td>" % cell
        html_table += "</tr>"

    html_table += "</table>"

    return html_table


def send_email(html,mod_hash,ref_hash):
    print('we have reached the mailing room')    

    message = MIMEMultipart("alternative", None, [MIMEText(html,'html')])
    sender = EMAIL_SENDER
    message['From'] = 'Auto_Tag_sender@intel.com'
    message['To'] = ", ".join(EMAIL_RECIPIENTS)
    message['Subject'] = '{} vs {} Results'.format(mod_hash[:5], ref_hash[:5])
    
    print('Sending Results...')
    s = smtplib.SMTP('smtp.intel.com',25)
    s.sendmail(sender, EMAIL_RECIPIENTS, message.as_string())
    s.quit()
    print('Results Sent!')


def call(command, work_dir=os.getcwd()):
    pipe = subprocess.Popen(command, shell=True, cwd=work_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = pipe.communicate()
    pipe.wait()
    try:
        return str(output.decode("utf-8")).splitlines()
    except:
        return str(output).splitlines()

#gLOBAL VARS


METRICS = ['PSNR_Y', 'SSIM_Y', 'VMAF', 'VMAF_NEG']
SYS_METRICS = ['ENCODE_USER_TIME', 'ENCODE_SYS_TIME', 'DECODE_USER_TIME', 'DECODE_SYS_TIME', 'MAX_MEMORY']
clips = set()



if __name__ == "__main__":
    main()
