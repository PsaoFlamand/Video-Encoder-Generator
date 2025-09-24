'''-------------------------------------------------------------------Get BDR Comparison Pairs-------------------------------------------------------------------------------'''
import os
import glob
import csv
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.message import Message
import math
import smtplib

EMAIL_SENDER = 'AutoSender@intel.com'
EMAIL_RECIPIENTS = []



def main():
    results_dir = ''
    result_files = glob.glob('{}/*.txt'.format(results_dir))
    result_files = []
    for root, dirs, files in os.walk(results_dir):
        for file in files:
            if file.endswith(".txt") and "result" in file:
                file_path = os.path.join(root, file)
                print(file_path)
                result_files.append(file_path)
    print('result_files',result_files)
    results = get_comparisons(result_files)
    html = generate_html(results)
    send_email(html)

    
def get_comparisons(result_files, mod_hash=None, ref_hash=None):
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
    
    cvh_comparison = None
    '''Check the validity of results files'''
##    valid_results, reason = verify_result_file_integrity(result_files)
##
##    if valid_results:
##        print('Results Integrity Check PASSED...')
##    else:
##        print('Results Integrity Check FAILED...')
##        print(reason)
##
##        response = None
##        while response not in ['1', '0']:
##            response = str(input('Do you wish to continue? (1,0) -> '))
##            if response == '1':
##                break
##            elif response == '0':
##                return
##

    auto_compare = False
    if auto_compare:
        selections = auto_comparison_selector(encoders)
    else:
        '''Get user input on which Comparison they'd like to perform'''
        selections = get_comparison_type_selection(encoders)
    print('selections',selections)
   # selections = auto_comparison_selector(encoders, mod_hash, ref_hash)

    for (encoder_pair, presets) in selections:
        ref, mod = encoder_pair.split('|')

        sorted_presets = sorted(presets, key=lambda x: int(x.split('M')[-1]))
        
        '''puts data from result txt into a large dictionary'''
        bdr_data, system_data = process_data(result_files)

        '''generates a dictionary of bdrate values'''
        detailed_bdr_results = get_detailed_bdr_results(mod, ref, presets, bdr_data)

        '''generates a dictionary of system speed, memory values'''
        system_results = get_system_results(mod, ref, presets, system_data)

        '''# generates overall summary of metrics by preset, per metric'''
        averaged_bdr_results = get_averaged_bdr_results(detailed_bdr_results, presets) 

        for bdr_result, system_result in zip(averaged_bdr_results, system_results):
            results.append([system_result[0], ' ', system_result[1]] + bdr_result + system_result[2:])

    return results


def get_squashed_encoders(result_files):
    encoders = set()
    
    for result_file in result_files:
        with open(result_file) as file:
            content = file.readlines()[1:]
            # x = x.strip('\n')
            encoders.update(x.strip('\n').split('\t')[1] for x in content if (x.strip('\n') and x.strip('\n').split('\t')[1]))
    return list(encoders)

def get_comparison_type_selection(squashed_encoder_list):
    print('\n(1) : n0,n1,n2... vs n0 \n(2) : n0,n1,n2... vs n0,n1,n2...')
    comparison_selection = None
    ref_selection = None
    while comparison_selection != '1' and comparison_selection != '2':
        comparison_selection = str(input('Select the which comparison type to perform -> '))

        if comparison_selection.strip() not in ['1', '2']:
            print('Bad Choice, Try again...')

    '''Group encoders based on presets'''
    grouped_encoders = get_grouped_encoders(squashed_encoder_list,comparison_selection)            
    print('grouped_encoders',grouped_encoders)
    
    '''Get paired encoder selections'''
    
    if comparison_selection == '1':
        ref_selection = int(input('Select the reference encoder to use -> '))
        ref_selection = squashed_encoder_list[ref_selection]

    paired_encoders = get_paired_encoders(squashed_encoder_list, grouped_encoders, ref_selection, comparison_selection)
    
    for index, pair in enumerate(paired_encoders):
        print('\n({0}) : {1} | {2}'.format(index, pair, paired_encoders[pair]))

    pair_selection = str(input('Select the pair to compare (Specify multiple selections by seperating with , ex: 1,2,3 | -1: Select all) -> '))

    if pair_selection == '-1':
        pair_selections = [str(i) for i in range(len(paired_encoders))]
    else:
        pair_selections = pair_selection.split(',')        

    enc_selections = get_enc_selections(paired_encoders,pair_selections)    

    return enc_selections#[[comparison_selection, enc_selections]]

def auto_comparison_selector(squashed_encoder_list, mod_hash,ref_hash):
    # Step 1: Group encoders by type
    encoder_groups = get_grouped_encoders(squashed_encoder_list)
    
    # Step 2: Select a reference encoder
    ref_selection = None
    for encoder in encoder_groups:
        if 'av1' in encoder.lower() and 'svt' not in encoder.lower() or 'libaom' in encoder.lower():
            ref_selection = '{}_{}'.format(encoder, encoder_groups[encoder][0])
    
    # Step 3: Get paired encoder selections
    if ref_selection:
        paired_encoders_1 = get_paired_encoders(mod_hash,ref_hash, squashed_encoder_list, encoder_groups, ref_selection, '1')
        paired_encoders_1 = dict((k, v) for k, v in paired_encoders_1.iteritems() if k.split('|')[1] not in k.split('|')[0])
        enc_selections_1 = get_enc_selections(paired_encoders_1, [str(x) for x in range(len(paired_encoders_1))])
    else:
        enc_selections_1 = []
    
    paired_encoders_2 = get_paired_encoders(mod_hash,ref_hash, squashed_encoder_list, encoder_groups, None)
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


def  get_paired_encoders(squashed_encoder_list, grouped_encoders,   ref_selection=None, comparison_selection=None, mod_hash=None, ref_hash=None):
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
    # print('grouped_encoders',grouped_encoders)
    if comparison_selection == '1':
        ref_encoder = ref_selection
        
        for mod_encoder, mod_presets in grouped_encoders.items():
            if mod_encoder != ref_encoder:
                pair_id = '{0}|{1}'.format(ref_encoder, mod_encoder)
                paired_encoders[pair_id] = sorted(mod_presets, key=lambda x: int(x.replace('M', '')))
    else:
        for ref_encoder, ref_presets in grouped_encoders.items():
                for mod_encoder, mod_presets in grouped_encoders.items():
                    if ref_hash and ref_hash[:5] not in ref_encoder and  mod_hash[:5] not in mod_encoder:
                        continue
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
    '''Loop through all files in results folder'''
    bdr_data = dict()
    system_data = dict()
    is_cvh_comparison = False
    
    for file in files:
        if 'convex' in file:
            is_cvh_comparison = True
            
    for file in files:
        '''Split the results between cvh and non-cvh'''
        if is_cvh_comparison:
            # if "convex" not in file:
            if "convex" not in file:
                '''Loop through all the system metrics. Speed, mem etc...'''
                for sys_metric in SYS_METRICS:
                    metric_name = sys_metric
                    process_data_helper(file, metric_name, system_data)
            else:
                '''If CVH file, target the metric specified in the file name'''
                # print('file',file)
                metric_name = os.path.split(file)[-1].split("_c")[0]
                process_data_helper(file, metric_name, bdr_data)
        else:
                '''Loop through all the system metrics. Speed, mem etc...'''
                for sys_metric in SYS_METRICS:
                    metric_name = sys_metric
                    process_data_helper(file, metric_name, system_data)
                for metric_name in METRICS:
                    process_data_helper(file, metric_name, bdr_data)                    
    with open('new_bdr_data.txt','w') as bug:
        bug.write(str(bdr_data))
        
    with open('new_system_data.txt','w') as bug:
        bug.write(str(system_data))
        
    with open('new_clips.txt','w') as bug:
        bug.write(str(clips))

        
    return bdr_data, system_data
clips = {}


def process_data_helper(file, metric_name, data):
    last_line_number = len(open(file).readlines()) - 2
    '''Open result File'''
    with open(file, mode='r') as csv_file:
        content = list(csv.DictReader(csv_file, delimiter='\t'))
        rates = []
        metrics = []
        preset_pattern = re.compile(r'M\d\d?')
        
        for index, row in enumerate(content):
            if not row['ENC_NAME']:
                continue

            encoder_name = re.search(r'(.+?)(?=_M-?\d)', row['ENC_NAME']).group()

            row['INPUT_SEQUENCE'] = row['INPUT_SEQUENCE'].replace(r'_lanc', '')
            resolution_search = re.search(r'(\d+x\d+)to(\d+x\d+)', row['INPUT_SEQUENCE'])
            
            if resolution_search:
                row['INPUT_SEQUENCE'] = re.sub(r'_\d+x\d+to\d+x\d+', '', row['INPUT_SEQUENCE'])
            row['INPUT_SEQUENCE'] = re.sub(r'_\d+x\d+', '', row['INPUT_SEQUENCE'])

            preset = re.search(r'M-?\d\d?', row['ENC_NAME']).group()

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
                next_sequence = content[index+1]['INPUT_SEQUENCE']#'_'.join(content[index+1]['INPUT_SEQUENCE'].split('_')[:-1])
                if resolution_search:
                    next_sequence = re.sub(r'_\d+x\d+to\d+x\d+', '', next_sequence)
                next_sequence = re.sub(r'_\d+x\d+', '', next_sequence).replace(r'_lanc', '')          
           
            #row['INPUT_SEQUENCE'] = '_'.join(row['INPUT_SEQUENCE'].split('_')[:-1])

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
                        # print(row['INPUT_SEQUENCE'], next_sequence)
                        data[encoder_name][metric_name][preset][row['INPUT_SEQUENCE']][0].extend(metrics)
                        
                    else:
                        '''BDR Results'''
                        
                        data[encoder_name][metric_name][preset][row['INPUT_SEQUENCE']].append(rates)
                        data[encoder_name][metric_name][preset][row['INPUT_SEQUENCE']].append(metrics)

                rates = list()
                metrics = list()

    # print('data',data)
    return data


def get_detailed_bdr_results(mod, ref, presets, bdr_data):
    bdr_results = {}
    preset_search = re.search(r'_(M-?\d+)', ref)

    all_clips = sorted(clips)
        
    for metric in METRICS:
        bdr_results[metric] = {}
        for preset in presets:
            ref_preset = preset_search.group(1) if preset_search else preset
            ref = ref.split(preset_search.group(0))[0] if preset_search else ref
                
            bdr_results[metric][preset] = {}
            for clip in all_clips:

##                print('ref',ref)
##                print('metric',metric)
##                print('ref_preset',ref_preset)
##                print('clip',clip)
                with open('bug.txt','w') as bug:
                    bug.write(str(bdr_data[ref][metric][ref_preset]).replace(']],','\n'))                
##                print('bdr_data[ref]',ref,bdr_data[ref])
##                print('bdr_data[metric]',metric,bdr_data[ref][metric])
##                print('bdr_data[ref_preset]',ref_preset,bdr_data[ref][metric][ref_preset])
##                print('bdr_data[clip]',clip,bdr_data[ref][metric][ref_preset][clip])
                ref_data = bdr_data[ref][metric][ref_preset][clip]
                with open('bug2.txt','w') as bug:
                    bug.write(str(bdr_data).replace(']],','\n'))                
                
                mod_data = bdr_data[mod][metric][preset][clip]

                if ref_data[0] == mod_data[0] and ref_data[1] == mod_data[1]:
                    bdrate = 0
                    bdr_results[metric][preset][clip] = bdrate
                else:
                    if ref_data[0] and mod_data[1]:
                        # print('\n\n')
                        # print(ref_data[0], ref_data[1], mod_data[0], mod_data[1])
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


def get_averaged_bdr_results(detailed_bdr_results,presets):
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
##    print('(h1 + h2)',(h1 + h2))
##    print('h1',h1)
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

    with open('results.html','w') as output:
        output.write(html_table)
    return html_table


def send_email(html,mod_hash='',ref_hash=''):
    print('we have reached the mailing room')    

    message = MIMEMultipart("alternative", None, [MIMEText(html,'html')])
    sender = EMAIL_SENDER
    message['From'] = 'Auto_Tag_sender@intel.com'
    message['To'] = ", ".join(EMAIL_RECIPIENTS)
    message['Subject'] = 'Results'#'{} vs {} Results'.format(mod_hash[:5], ref_hash[:5])
    
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


METRICS = ['PSNR_Y', 'SSIM_Y', 'VMAF']
SYS_METRICS = ['ENCODE_USER_TIME', 'ENCODE_SYS_TIME', 'DECODE_USER_TIME', 'DECODE_SYS_TIME', 'MAX_MEMORY']
clips = set()



if __name__ == "__main__":
    main()
