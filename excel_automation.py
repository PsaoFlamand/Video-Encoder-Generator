import glob
import xlwings as xw
import os
import re
import time
import sys

# Changeable Settings Start
save = 1
'''path variables'''
result_directory = os.path.join(os.getcwd(), 'results')
result_files = glob.glob('%s/*.txt' % result_directory)

'''Excel Variables'''
wb = xw.Book('CVH_Comparison_template.xlsm')


app = xw.apps.active

# Changeable Settings End

master_sheet = wb.sheets['Classical_Master']
master_cvh_sheet = wb.sheets['CVH_Master']

summary_sheet = wb.sheets['Summary']
all_data_sheet = wb.sheets['All_Data']
summary_sheet.autofit()
# Result Variables
BDR_HEADER = list()
SYSTEM_HEADER = list()

BDR_RESULTS = []
SYSTEM_RESULTS = []

grouped_encoders = dict()

auto_compare = 0

def main():
    global BDR_HEADER, SYSTEM_HEADER, BDR_RESULTS, SYSTEM_RESULTS
##    check_if_latest_version()
    t = time.time()
    
    cvh_comparison = None
    '''Check the validity of results files'''
    #valid_results, reason = verify_result_file_integrity(result_files)

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

    '''Search for the next available line to insert new results and data'''
    data_range = uniform_search(all_data_sheet)
    summary_range = uniform_search(summary_sheet)

    print('summary_range', summary_range)
    print('data_range', data_range)

    '''Populate all data page with result files found in results folder'''
    set_data(result_files, data_range)

    '''Get encoder names from all data page'''
    encoder_names_from_all_data = all_data_sheet.range("B:B").value
    sequence_names_from_all_data = all_data_sheet.range("E:E").value
    qp_values_from_all_data = all_data_sheet.range("F:F").value
    squashed_encoder_list = sorted([x for x in set(encoder_names_from_all_data) if x is not None])

    if auto_compare:
        selections = auto_comparison_selector(squashed_encoder_list)
    else:
        '''Get user input on which Comparison they'd like to perform'''
        selections = get_comparison_type_selection(squashed_encoder_list)

    for comparison_selection, enc_selections in selections:
        '''Build the lists of selected mod and ref root encoder names'''
        mod_encoders, ref_encoders = get_ref_mod_encoder_names(enc_selections, comparison_selection)

        '''Check if there exists relevant cvh data in the all data page, offer the option if true'''
        cvh_comparison, mod_metrics, ref_metrics = check_cvh_comparison_options(squashed_encoder_list, mod_encoders, ref_encoders)

        '''Get the number of cvh points and QPs for the encoders that are being compared'''
        number_of_cvh_points, number_of_qps = get_number_of_points(mod_metrics, ref_metrics, encoder_names_from_all_data, sequence_names_from_all_data,
                                                                   mod_encoders, ref_encoders, qp_values_from_all_data, cvh_comparison)

        bdr_table_length = get_bdr_table_length(encoder_names_from_all_data, mod_encoders)
        print('bdr_table_length',bdr_table_length)
        #bdr_table_length = 6000
        if str(cvh_comparison) == '2':
            adjust_excel_metric_formulas(master_cvh_sheet)
        adjust_excel_metric_formulas(master_sheet)

        '''Adjust the excel bdr tables according to the found number of points above'''
        if str(cvh_comparison) == '2':
        
            adjust_excel_cvh(number_of_cvh_points, bdr_table_length, cvh_comparison, master_cvh_sheet)
        adjust_excel_cvh(number_of_qps, bdr_table_length, cvh_comparison, master_sheet)

        wb.macro('Refresh_Data')()

        '''Perform the comparisons'''
        perform_comparisons(mod_encoders, ref_encoders, mod_metrics, ref_metrics, cvh_comparison, comparison_selection)

        '''Write the generated results to the summary page'''
        set_results(summary_range, cvh_comparison, mod_metrics)
        BDR_HEADER = list()
        SYSTEM_HEADER = list()

        BDR_RESULTS = []
        SYSTEM_RESULTS = []
        summary_range = uniform_search(summary_sheet)

    
    '''Format the summary table'''
    colour_deviations()
    format_columns()
    
    '''Save the resuts and export as HTML table'''
    summary_sheet.autofit()
    if save:
        wb.save('results.xlsm')
    print(time.time() - t)    
        
    #wb.macro('Export')()
##    app.kill()


def auto_comparison_selector(squashed_encoder_list):
    ref_selection = None
    grouped_encoders, valid_selections = get_grouped_encoders(squashed_encoder_list)            

    '''Get paired encoder selections'''
    for index,grouped_encoder in enumerate(grouped_encoders):
        if 'av1' in grouped_encoder.lower() and 'svt' not in grouped_encoder.lower():
            ref_selection = '{}_{}'.format(grouped_encoder,grouped_encoders[grouped_encoder][0])

    if ref_selection:
        paired_encoders_1 = get_paired_encoders(squashed_encoder_list,grouped_encoders,ref_selection,'1')

    paired_encoders_2 = get_paired_encoders(squashed_encoder_list,grouped_encoders,None)

    pair_selections_1 = [str(x) for x in range(len(paired_encoders_1))]
    pair_selections_2 = [str(x) for x in range(len(paired_encoders_2))]

    enc_selections_1 = get_enc_selections(paired_encoders_1,pair_selections_1)
    enc_selections_2 = get_enc_selections(paired_encoders_2,pair_selections_2)

    print('Auto comparisons the following pairs\n')
    print('enc_selections_1',enc_selections_1)
    print('\nenc_selections_2',enc_selections_2)
    print('\n')
    if ref_selection:
        enc_selections = [['1',enc_selections_1],['2',enc_selections_2]]
    else:
        enc_selections = [['2',enc_selections_2]]
        
    return enc_selections

    
def colour_deviations():
    table = summary_sheet.used_range
    for column in table.columns:
        try:
            if "PSNR" in column[0].value or "SSIM" in column[0].value or "VMAF" in column[0].value:
                for cell in column[1:]:
                    if cell.value > 0 or cell.value < 0:
                        cell.color = (255, 0, 0)
        except:
            pass

  
def format_columns():
    table = summary_sheet.used_range
    not_percent = ['Mod Sum Encode Cycles', 'Ref Sum Encode Cycles', 'Mod Sum Decode Cycles', 'Ref Sum Decode Cycles', 'Slope', 'SSIM Slope', 'VMAF-NEG Slope', 'AVG Slope', 'New AVG Slope']
    for column in table.columns:
        if column[0].value in not_percent:
            column.number_format = 'General'


def get_bdr_table_length(encoder_names_from_all_data, mod_encoders):
    bdr_table_length = 0

    for mod_encoder_names in mod_encoders:
        number_of_occurences = encoder_names_from_all_data.count(
            mod_encoder_names[0])
        bdr_table_length = max(bdr_table_length, number_of_occurences)

    return bdr_table_length


def adjust_excel_metric_formulas(sheet):
    system_metrics_formula = list()
    mod_sys_formula = [
        '=$B$28',
        '=SUM($Q$32:$Q$1048576)/1000',
        '=SUM($R$32:$R$1048576)/1000',
        '=MAX($S$32:$S$1048576)/1000',
        '=MAX($P$32:$P$1048576)',
        '=SUM($T$32:$T$1048576)/1000',
        '=SUM($U$32:$U$1048576)/1000',
        '=BA20+BB20',
        '=BE20+BF20']
    ref_sys_formula = [
        '=$AA$28',
        '=SUM($AP$32:$AP$1048576)/1000',
        '=SUM($AQ$32:$AQ$1048576)/1000',
        '=MAX($AR$32:$AR$1048576)/1000',
        '=MAX($AO$32:$AO$1048576)',
        '=SUM($AS$32:$AS$1048576)/1000',
        '=SUM($AT$32:$AT$1048576)/1000',
        '=BA21+BB21',
        '=BE21+BF21']
    system_metrics_formula.append(mod_sys_formula)
    system_metrics_formula.append(ref_sys_formula)

    sheet.range('AZ20').value = system_metrics_formula


def get_system_results(mod_encoder_name, ref_encoder_name, sheet):
    global SYSTEM_HEADER
    headers = sheet.range('AZ5:BS5').value
    system_results = sheet.range('AZ6:BS6').value

    if not SYSTEM_HEADER:
        SYSTEM_HEADER = [None] * len(system_results)

    for index, system_result in enumerate(system_results):
        if system_result is not None:
            SYSTEM_HEADER[index] = headers[index]

    system_result = [x for x in system_results if x is not None]

    SYSTEM_RESULTS.append(system_result)


def get_bdr_results(sheet):
    global BDR_HEADER
    headers = sheet.range('AZ2:BS2').value
    bdr_results = sheet.range('AZ3:BS3').value

    if not BDR_HEADER:
        BDR_HEADER = [None] * len(bdr_results)

    for index, temp_cvh_result in enumerate(bdr_results):
        if temp_cvh_result is not None and temp_cvh_result != 1.0:
            BDR_HEADER[index] = headers[index]

    bdr_result = [x for x in bdr_results if (x != 1.0 and x is not None)]
    BDR_RESULTS.append(bdr_result)


def set_encoder_names(mod_encoder_name, ref_encoder_name, sheet):
    print('\nmod_encoder_name', mod_encoder_name)
    print('ref_encoder_names', ref_encoder_name)
    sheet.range('B28').value = ref_encoder_name
    sheet.range('AA28').value = mod_encoder_name


def adjust_excel_cvh(bdr_points, stop_point, cvh_comparison, sheet):
    bdr_table = list()
    system_table = list()

    bdr_form = '''=IFERROR(@bdRateExtend($%s%s:$%s%s,%s%s:%s%s,$%s%s:$%s%s,%s%s:%s%s),"N/A")'''
    bdr_average_form = '''=IFERROR((BC{bdr_low}+BG{bdr_low}+BK{bdr_low})/3,"n/a")'''
    speed_dev_form = '''=IFERROR((SUM(Q{system_low}:Q{system_high})+SUM(R{system_low}:R{system_high}))/(SUM(AP{system_low}:AP{system_high})+SUM(AQ{system_low}:AQ{system_high}))-1,"N/A")'''
    memory_dev_form = '''=IFERROR((MAX(AO{system_low}:AO{system_high})/MAX(P{system_low}:P{system_high}))-1,"0")'''
    starting_row = 32
    bdr_low = starting_row
    system_low = starting_row
    print('bdr_points',bdr_points)
    for point_num in range(stop_point):
        if point_num % (bdr_points) == 0:
            bdr_high = point_num + starting_row + bdr_points - 1
            bdr_table.extend([[bdr_form % ('E', bdr_low, 'E', bdr_high, 'F', bdr_low, 'F', bdr_high, 'AD', bdr_low, 'AD', bdr_high, 'AE', bdr_low, 'AE', bdr_high),
                               bdr_form % ('E', bdr_low, 'E', bdr_high, 'G', bdr_low, 'G', bdr_high, 'AD', bdr_low, 'AD', bdr_high, 'AF', bdr_low, 'AF', bdr_high),
                               bdr_form % ('E', bdr_low, 'E', bdr_high, 'H', bdr_low, 'H', bdr_high, 'AD', bdr_low, 'AD', bdr_high, 'AG', bdr_low, 'AG', bdr_high),
                               bdr_form % ('E', bdr_low, 'E', bdr_high, 'I', bdr_low, 'I', bdr_high, 'AD', bdr_low, 'AD', bdr_high, 'AH', bdr_low, 'AH', bdr_high),
                               bdr_form % ('E', bdr_low, 'E', bdr_high, 'J', bdr_low, 'J', bdr_high, 'AD', bdr_low, 'AD', bdr_high, 'AI', bdr_low, 'AI', bdr_high),
                               bdr_form % ('E', bdr_low, 'E', bdr_high, 'K', bdr_low, 'K', bdr_high, 'AD', bdr_low, 'AD', bdr_high, 'AJ', bdr_low, 'AJ', bdr_high),
                               bdr_form % ('E', bdr_low, 'E', bdr_high, 'L', bdr_low, 'L', bdr_high, 'AD', bdr_low, 'AD', bdr_high, 'AK', bdr_low, 'AK', bdr_high),
                               bdr_form % ('E', bdr_low, 'E', bdr_high, 'M', bdr_low, 'M', bdr_high, 'AD', bdr_low, 'AD', bdr_high, 'AL', bdr_low, 'AL', bdr_high),
                               bdr_form % ('E', bdr_low, 'E', bdr_high, 'N', bdr_low, 'N', bdr_high, 'AD', bdr_low, 'AD', bdr_high, 'AM', bdr_low, 'AM', bdr_high),
                               bdr_form % ('E', bdr_low, 'E', bdr_high, 'O', bdr_low, 'O', bdr_high, 'AD', bdr_low, 'AD', bdr_high, 'AN', bdr_low, 'AN', bdr_high),
                               bdr_average_form.format(**vars())
                               ]])
            bdr_low = bdr_high + 1
        else:
            bdr_table.extend([['', '', '', '', '', '', '', '', '', '', '']])

        if point_num % bdr_points == 0:
            system_high = point_num + starting_row + bdr_points - 1

            system_table.extend([[speed_dev_form.format(**vars()),
                                  memory_dev_form.format(**vars())]])
            system_low = system_high + 1
        else:
            system_table.extend([['', '']])

    sheet.range('BC32').value = bdr_table
    sheet.range('BN32').value = system_table
    sheet.range('BC32:BN12044').number_format = '0%'
    #sheet.range('BN32:BN12044').number_format = 'Percentage'



'''Code retrieved from https://stackoverflow.com/questions/2130016/splitting-a-list-into-n-parts-of-approximately-equal-length'''


def segment_list(list_target, segments):
    k, m = divmod(len(list_target), segments)
    return list((list_target[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(segments)))


def segment_metrics(results, number_of_segments, number_of_presets):
    segmented_list = segment_list(results, number_of_segments)
    vertically_merged_list = [x[3] for tup in zip(*segmented_list) for x in list(tup)]

    final_metric_list = segment_list(vertically_merged_list, number_of_presets)
    return final_metric_list


def set_results(summary_range, cvh_comparison, mod_metrics):
    global BDR_HEADER
    global SYSTEM_HEADER

    result_set = list()
         
    sorted_system_results = sorted([x for x in SYSTEM_RESULTS], key=lambda x: (x[0].split('_')[0], int(x[0].split('_')[-1][1:])))

    BDR_HEADER = [x for x in BDR_HEADER if x is not None]
    SYSTEM_HEADER = [x for x in SYSTEM_HEADER if x is not None]
    header = BDR_HEADER + SYSTEM_HEADER

    if cvh_comparison == '2':
        print('BDR_RESULTS',BDR_RESULTS)
        print('\n')
        sorted_bdr_results = sorted([x for x in BDR_RESULTS], key=lambda x: (re.findall(r'.*?_M-?\d+_([PSVpsv][SMsm][NIAnia].*)', x[0])[-1], x[0].split('_')[0], int(re.findall(r'_M(-?\d+)', x[0])[-1])))
        print('sorted_bdr_results',sorted_bdr_results)
        if mod_metrics:
            segmented_metrics = segment_metrics(sorted_bdr_results, len(mod_metrics), len(sorted_system_results))

        for metric_results, system_results in zip(segmented_metrics, sorted_system_results):
            '''For the case where vmaf-neg is being calculated, exclude it from the average calculation'''
            if len(metric_results) >= 4:
                average_bdr = sum(metric_results[:3]) / len(metric_results[:3])
            else:
                average_bdr = sum(metric_results) / len(metric_results)
            result_set.append(system_results[:3] + metric_results + [average_bdr] + system_results[3:])
    else:
        sorted_bdr_results = sorted([x for x in BDR_RESULTS], key=lambda x: (x[0].split('_')[0], int(x[0].split('_')[-1][1:])))


        for metric_results, system_results in zip(sorted_bdr_results, sorted_system_results):
            result_set.append(metric_results + system_results[3:])
    #print('result_set',result_set)
    sorted_result_set = sorted([x for x in result_set], key=lambda x: (re.findall(r'(.*?)_M-?\d+', x[0])[-1], int(x[0].split('_')[-1][1:]), x[2].split('_')[0]))
    sorted_result_set.insert(0, header)

    print('\n')
    print(sorted_result_set)
    print('\n')
    print('chr(len(header) - 1 + 97)',chr(len(header) - 1 + 97))

    summary_sheet.range('A%s' % str(summary_range)).value = sorted_result_set

    if (len(header) - 1 + 97) > 122:
        end_bound = 'A{}'.format(chr(len(header) - 1 + 97 - 26))
    else:
        end_bound = chr(len(header) - 1 + 97)

    print('end_bound',end_bound)
    header_range = summary_sheet.range('A%s:%s%s' % (str(summary_range), end_bound, str(summary_range)))

    header_range = header_range.expand('right')
    header_range.color = (112, 173, 71)
    header_range.api.Font.Color = 0xFFFFFF
    header_range.api.Font.Bold = True
    header_range.api.Font.Size = 11

    id_column_range = summary_sheet.range('A%s' % str(summary_range + 1)).expand('down')
    id_column_range.color = (198, 224, 180)

    data_ex_headers_range = summary_sheet.range('A%s' % str(summary_range)).expand('table')

    for border_id in range(7, 13):
        data_ex_headers_range.api.Borders(border_id).Weight = 2
        data_ex_headers_range.api.Borders(border_id).LineStyle = 1
        data_ex_headers_range.api.Borders(border_id).Color = 0x000000


def uniform_search(sheet):
    complete_column = sheet.range('B:B').value
    for i in range(len(complete_column) - 1, -1, -1):
        if complete_column[i] is not None:
            return i + 3
    return 1


def chunk_data(all_data):
    for i in range(0, len(all_data), 100000):
        yield all_data[i:i + 100000]


def perform_comparisons(mod_encoders, ref_encoders, mod_metrics, ref_metrics, cvh_comparison, comparison_selection):
    for mod_encoder_names, ref_encoder_names in zip(mod_encoders, ref_encoders):
        if comparison_selection == '1':
            for mod_encoder_name in mod_encoder_names:
                if mod_encoder_name == ref_encoder_names[0]:
                    continue
                set_encoder_names(mod_encoder_name, ref_encoder_names[0], master_sheet)
                get_system_results(mod_encoder_name, ref_encoder_names, master_sheet)

                if cvh_comparison == '2':
                    for mod_metric, ref_metric in zip(mod_metrics, ref_metrics):
                        set_encoder_names(mod_metric % mod_encoder_name, ref_metric % ref_encoder_names[0], master_cvh_sheet)
                        get_bdr_results(master_cvh_sheet)
                else:
                    get_bdr_results(master_sheet)
        else:
            for mod_encoder_name, ref_encoder_name in zip(mod_encoder_names, ref_encoder_names):
                if mod_encoder_name == ref_encoder_name:
                    continue
                set_encoder_names(mod_encoder_name, ref_encoder_name, master_sheet)
                get_system_results(mod_encoder_name, ref_encoder_name, master_sheet)

                if cvh_comparison == '2':
                    for mod_metric, ref_metric in zip(mod_metrics, ref_metrics):
                        set_encoder_names(mod_metric % mod_encoder_name, ref_metric % ref_encoder_name, master_cvh_sheet)
                        get_bdr_results(master_cvh_sheet)
                else:
                    get_bdr_results(master_sheet)


def get_ref_mod_encoder_names(enc_selections, comparison_selection):
    ref_encoders = list()
    mod_encoders = list()
    for enc_selection in enc_selections:
        mod_name = enc_selection[0].split('|')[1]
        presets = enc_selection[1]
        mod_encoder_names = ['{}_{}'.format(mod_name, preset) for preset in presets]
        ref_encoder_names = enc_selection[0].split('|')[0]

        if comparison_selection == '2':
            ref_encoder_names = ['{}_{}'.format(ref_encoder_names, preset) for preset in presets]
        else:
            ref_encoder_names = [ref_encoder_names]

        print('ref_encoder_names: ', ref_encoder_names)
        print('mod_encoder_names: ', mod_encoder_names)

        ref_encoders.append(ref_encoder_names)
        mod_encoders.append(mod_encoder_names)

    return mod_encoders, ref_encoders


def check_cvh_comparison_options(squashed_encoder_list, mod_encoders, ref_encoders):
    valid_cvh = list()
    for mod_encoder_names, ref_encoder_names in zip(mod_encoders, ref_encoders):
        mod_cvh_options = list()
        ref_cvh_options = list()
        ref_metrics = set()
        mod_metrics = set()
        for enc_name in squashed_encoder_list[1:]:
            if not enc_name[-1].isdigit():
                if re.search('(.*?_M-?\\d+)_[PSVpsv][SMsm][NIAnia]', enc_name):
                    enc_root = re.search('(.*?_M-?\\d+)_[PSVpsv][SMsm][NIAnia]', enc_name).group(1)
                else:
                    continue

                if enc_root in mod_encoder_names:
                    mod_cvh_options.append(enc_name)

                if enc_root in ref_encoder_names:
                    ref_cvh_options.append(enc_name)

        for mod_cvh_option in mod_cvh_options:
            print('mod_cvh_option',mod_cvh_option)
            metric_part = re.search(r'.*?_M-?\d+_([PSVpsv][SMsm][NIAnia].*)', mod_cvh_option).group(1)
            mod_metrics.add('%s_{}'.format(metric_part))

        for ref_cvh_option in ref_cvh_options:
            print('ref_cvh_option',ref_cvh_option)
            metric_part = re.search(r'.*?_M-?\d+_([PSVpsv][SMsm][NIAnia].*)', ref_cvh_option).group(1)
            ref_metrics.add('%s_{}'.format(metric_part))
        ref_metrics = sorted(list(ref_metrics))
        mod_metrics = sorted(list(mod_metrics))

        if mod_metrics and ref_metrics and len(
                mod_metrics) == len(ref_metrics):
            valid_cvh.append(True)
        else:
            valid_cvh.append(False)

    print('ref_metrics', ref_metrics)
    print('mod_metrics', mod_metrics)

    if False not in valid_cvh:
        if auto_compare:
            cvh_comparison='2'
        else:
            
            print('The option to do CVH comparisons are available.\nSelect comparison Type.\n(1): Face to Face\n(2): Convex Hull')
            cvh_comparison = str(input('Select Option -> '))
    else:
        cvh_comparison = 0

    return cvh_comparison, mod_metrics, ref_metrics


def get_qp_cvh_points(encoder_names_from_all_data, sequence_names_from_all_data, encoder_name, qp_values_from_all_data):
    initial_sequence_name = None
    cvh_qps = list()

    for encoder_name_from_all_data, sequence_name, cvh_qp in zip(encoder_names_from_all_data, sequence_names_from_all_data, qp_values_from_all_data):
        if encoder_name_from_all_data == encoder_name:
            if initial_sequence_name and sequence_name != initial_sequence_name:
                break
            initial_sequence_name = sequence_name
            cvh_qps.append(cvh_qp)

    return cvh_qps


def get_number_of_points(mod_metrics, ref_metrics, encoder_names_from_all_data, sequence_names_from_all_data, mod_encoders, ref_encoders, qp_values_from_all_data, cvh_comparison):
    overall_number_of_cvh_points = set()
    overall_number_of_qps = set()

    for mod_encoder_names, ref_encoder_names in zip(mod_encoders, ref_encoders):
        mod_qps = get_qp_cvh_points(encoder_names_from_all_data, sequence_names_from_all_data, mod_encoder_names[0], qp_values_from_all_data)
        ref_qps = get_qp_cvh_points(encoder_names_from_all_data, sequence_names_from_all_data, ref_encoder_names[0], qp_values_from_all_data)

        if mod_metrics and ref_metrics:
            mod_cvh = get_qp_cvh_points(encoder_names_from_all_data, sequence_names_from_all_data, mod_metrics[0] % mod_encoder_names[0], qp_values_from_all_data)
            ref_cvh = get_qp_cvh_points(encoder_names_from_all_data, sequence_names_from_all_data, ref_metrics[0] % ref_encoder_names[0], qp_values_from_all_data)

        if cvh_comparison == '2' and len(mod_cvh) == len(ref_cvh):
            number_of_cvh_points = len(mod_cvh)
        elif cvh_comparison == '2' and len(mod_cvh) != len(ref_cvh):
            print('mod_cvh', mod_cvh)
            print('ref_cvh', ref_cvh)
            print('[CRITICAL ERROR]: The cvh values are not matching.')
            number_of_cvh_points = len(mod_cvh)
        else:
            number_of_cvh_points = 0

        if mod_qps == ref_qps:
            number_of_qps = len(mod_qps)
        else:
            print('mod_qps', mod_qps)
            print('ref_qps', ref_qps)
            print('[CRITICAL ERROR]: The QPs are not matching.')
            number_of_qps = len(mod_qps)

        overall_number_of_cvh_points.add(number_of_cvh_points)
        overall_number_of_qps.add(number_of_qps)

        print('number_of_cvh_points', number_of_cvh_points)
        print('number_of_qps', number_of_qps)

    if len(overall_number_of_cvh_points) > 1:
        print('[CRITICAL] your batch selection have differing numebrs of CVH points')
        #sys.exit()

    if len(overall_number_of_qps) > 1:
        print('[CRITICAL] your batch selection have differing numebrs of QPs')
        #sys.exit()
    print('number_of_cvh_points',number_of_cvh_points)
    print('number_of_qps',number_of_qps)
    return number_of_cvh_points, number_of_qps

def get_grouped_encoders(squashed_encoder_list,comparison_selection = None):
    valid_selections = []
    for index, enc_name in enumerate(squashed_encoder_list):
        if enc_name[-1].isdigit():
            enc_group = '_'.join(enc_name.split('_')[0:-1])
            enc_preset = enc_name.split('_')[-1]

            if enc_group not in grouped_encoders:
                grouped_encoders[enc_group] = [enc_preset]
            else:
                grouped_encoders[enc_group].append(enc_preset)

            if comparison_selection == '1':
                print('({0}) -> {1}'.format(index, enc_name))
                valid_selections.append(index)
    return grouped_encoders, valid_selections


def get_paired_encoders(squashed_encoder_list,grouped_encoders,ref_selection=None,comparison_selection =None):
    paired_encoders = dict()
    if comparison_selection == '1':
        if auto_compare:
            ref_enc = ref_selection
        else:
            ref_enc = squashed_encoder_list[ref_selection]

        for mod_enc in grouped_encoders:
            if mod_enc != ref_enc:
                mod_presets = grouped_encoders[mod_enc]
                print('\n')
                print('ref_enc',ref_enc)
                print('mod_enc',mod_enc)
                print('\n')

                pair_id = '{0}|{1}'.format(ref_enc, mod_enc)
                paired_encoders[pair_id] = sorted(mod_presets, key=lambda x: int(x.replace('M', '')))
    else:
        for ref_enc in grouped_encoders:
            for mod_enc in grouped_encoders:
                if mod_enc != ref_enc:
                    ref_presets = grouped_encoders[ref_enc]
                    mod_presets = grouped_encoders[mod_enc]

                    common_presets = [preset for preset in ref_presets if preset in mod_presets]
                    if common_presets:
                        pair_id = '|'.join('{0}|{1}'.format(ref_enc, mod_enc).split('|'))
                        print('pair_id', pair_id)
                        paired_encoders[pair_id] = common_presets
                        pair_id = '|'.join('{1}|{0}'.format(ref_enc, mod_enc).split('|'))
                        paired_encoders[pair_id] = common_presets

    return paired_encoders

def get_enc_selections(paired_encoders,pair_selections):
    while True:
        valid = False
        enc_selections = list()

        pairs = list(paired_encoders.items())

        '''Final pair selection'''

        for pair_selection in pair_selections:

            if pair_selection.strip().isdigit() == False or int(pair_selection) >= len(pairs) or int(pair_selection) < 0:
                print('Invalid Selection, Retry?')
                valid = False
                break
            else:
                enc_selections.append(pairs[int(pair_selection.strip())])
                print(enc_selections)
                valid = True
        if valid:
            break
    return enc_selections


def get_comparison_type_selection(squashed_encoder_list):
    print('\n(1) : n0,n1,n2... vs n0 \n(2) : n0,n1,n2... vs n0,n1,n2...')
    comparison_selection = None
    ref_selection = None
    while comparison_selection != '1' and comparison_selection != '2':
        comparison_selection = str(input('Select the which comparison type to perform -> '))

        if comparison_selection.strip() not in ['1', '2']:
            print('Bad Choice, Try again...')

    '''Group encoders based on presets'''
    grouped_encoders, valid_selections = get_grouped_encoders(squashed_encoder_list,comparison_selection)            

    '''Get paired encoder selections'''
    if comparison_selection == '1':    
        while 1:
            ref_selection = int(input('Select the reference encoder to use -> '))
            if ref_selection in valid_selections:
                break
            else:
                print('Invalid selection, Try again')
    paired_encoders = get_paired_encoders(squashed_encoder_list,grouped_encoders,ref_selection,comparison_selection)

    for index, pair in enumerate(paired_encoders):
        print('\n({0}) : {1} | {2}'.format(index, pair, paired_encoders[pair]))

    pair_selection = str(input('Select the pair to compare (Specify multiple selections by seperating with , ex: 1,2,3 | -1: Select all) -> '))

    if pair_selection == '-1':
        pair_selections = [str(i) for i in range(len(paired_encoders))]
    else:
        pair_selections = pair_selection.split(',')        

    enc_selections = get_enc_selections(paired_encoders,pair_selections)    

    return [[comparison_selection, enc_selections]]


def match_result_columns_to_excel(content, excel_headers):
    result_headers = [x.strip('\n') for x in content[0].split('\t')]
    content = [x.split('\t') for x in content if x != '\n' and x != '']

    excel_headers = [x for x in excel_headers if x is not None]
    content_tracker = dict()

    for index, content_column in enumerate(zip(*content)):
        content_tracker[result_headers[index]] = content_column

    new_header = list()

    for excel_header in excel_headers:
        found = False
        for result_header in result_headers:
            excel_header = excel_header.replace('(ms)', '')
            result_header = result_header.replace('(ms)', '')

            for index in range(len(result_header)):
                window = result_header[index:index + 4]

                if window.lower() in excel_header.lower() and (len(window) > 3 or len(window) == len(excel_header)):
                    if result_header not in result_headers:
                        result_header += '(ms)'

                    new_header.append(result_header)
                    result_headers.remove(result_header)
                    found = True
                    break
            if found:
                break
        if not found:
            new_header.append('n/a')

    new_content = list()

##    print('content_tracker',content_tracker)
    for result_header in new_header:
        if result_header == 'n/a':
            content_column = ['n/a'] * len(content)
        else:
            content_column = content_tracker[result_header]
        new_content.append(content_column)

    content = list(zip(*new_content))

    return content


def set_data(result_files, data_range):
    encoder_names_from_all_data = all_data_sheet.range("B:B").value
    excel_headers = all_data_sheet.range("A1:ZZ1").value

    squashed_encoder_list = sorted([x for x in set(encoder_names_from_all_data) if x is not None])

    all_data = []

    for result_file in result_files:
        mod_encoder_names = get_encoder_names([result_file], 1)

        if all([x not in squashed_encoder_list for x in mod_encoder_names]):
            print('result_file',result_file)
            if 'convex_hull' in result_file:
                with open(result_file) as cvh_result_file:
                    cvh_content = cvh_result_file.readlines()

                   # cvh_content = match_result_columns_to_excel(cvh_content, excel_headers)

                    for qp_overwrite, line in enumerate(cvh_content):
                        line = [x.replace('\n', '') for x in line.split('\t')]
                        if len(line) > 5 and line[5].strip().isdigit():
                            line[5] = str(qp_overwrite)
                            line[-1] = line[-1].replace('\n', '')

                            all_data.append(line)
            else:
                with open(result_file) as full_result_file:
                    full_result_content = full_result_file.readlines()

                   # full_result_content = match_result_columns_to_excel(full_result_content, excel_headers)

                    for line in full_result_content:
                        line = [x.replace('\n', '') for x in line.split('\t')]
##                        print('len(line)',len(line))
##                        print('line[5].strip()',line[5].strip())
                        if len(line) > 5 and line[5].strip().isdigit():
                            line[-1] = line[-1].replace('\n', '')
                            all_data.append(line)
        else:
            print('{} found in all data page, skipping data insertion...\n'.format(mod_encoder_names))

    for index, data in enumerate(chunk_data(all_data)):
        cell = 'A{}'.format(data_range + (index * 100000) + index)
##        for i in data:
##            print(len(i))
        all_data_sheet.range(cell).value = data


def verify_result_file_integrity(result_files):
    '''Adding the total number of cvh points to a set, there should be one single value in the set given that all cvh results have same number of points'''
    cvh_points = set()
    qps = list()
    valid_result = True
    reason = None
    for result_file in result_files:
        empty_lines = 0
        if 'convex_hull' in result_file:
            seq_names = set()
            for index, x in enumerate(open(result_file)):
                line_split = x.split('\t')

                if len(line_split) > 5 and line_split[5].strip().isdigit():
                    seq_name = line_split[4]
                    seq_names.add(seq_name)

                    if len(seq_names) > 1:
                        number_of_cvh_points = index - empty_lines
                        cvh_points.add(number_of_cvh_points)
                        break
                else:
                    empty_lines += 1
        else:
            temp_qps = list()
            for index, x in enumerate(open(result_file)):
                line_split = x.split('\t')
                qp = line_split[5].strip()

                if len(line_split) > 5 and qp.isdigit():
                    if qp in temp_qps:
                        if not qps:
                            qps = temp_qps
                        elif sorted(temp_qps) != sorted(qps):
                            valid_result = False
                            reason = 'The number of QPs are not uniform, missing QP? {} vs {}'.format(str(sorted(qps)), str(sorted(temp_qps)))

                        temp_qps = list()
                        temp_qps.append(qp)
                    else:
                        if temp_qps and qp < temp_qps[-1]:
                            valid_result = False
                            reason = 'The number of QPs are not uniform, missing QP? {} vs {}'.format(str(sorted(qps)), str(sorted(temp_qps)))
                        temp_qps.append(qp)

    if len(cvh_points) > 1:
        valid_result = False
        reason = 'The number of convex hull points are not uniform, {}'.format(str(cvh_points))
    return valid_result, reason


def get_encoder_names(result_files, convex=0):
    encoder_names = []
    for result_file in result_files:
        if ('convex_hull' not in result_file and not convex) or (convex):
            with open(result_file, 'r') as result:
                for index, encoder_name in enumerate(result.readlines()):
                    if index > 0 and encoder_name != "\n":
                        encoder_names.append(encoder_name.split('\t')[1])
    return sorted(list(set(encoder_names)))

def check_if_latest_version():
    try:
        # For Python 3.0 and later
        from urllib.request import urlopen
    except ImportError:
        # Fall back to Python 2's urllib2
        from urllib2 import urlopen
    
    start = r'# Changeable Settings Start'
    end = r'# Changeable Settings End'
    git_url = 'https://gitlab.com/AOMediaCodec/aom-testing/-/raw/master/svt-av1-testing-scripts/Upgrade_scripts_WIP/PyExcelCompare.py'
    response = urlopen(git_url)
    reference_script = str(response.read())

    with open(os.path.basename(__file__)) as current_script:
        script_content = current_script.read()
        mod_upper = script_content.split(start)[0]
        mod_lower = script_content.split(end)[-1]
        
    ref_upper = reference_script.split(start)[0]
    ref_lower = reference_script.split(end)[-1]
        
    if mod_upper == ref_upper and mod_lower == ref_lower:
        print("[PASS] Script is the latest version")
    else:
        print("[WARNING] There is a newer version available that may contain important bug fixes")

if __name__ == '__main__':

    main()

