import sqlite3
from thefuzz import process
from thefuzz import fuzz
import os
from googletrans import Translator
import re
import zlib, hashlib
from fastcrc import crc8, crc16, crc32, crc64
import itertools
import operator

DB_FILE_PATH = "./es-manage-app/src/games_meta.db"

def contains_digit(s):
    return bool(re.search(r'\s\d|\sII\s|\sIII\s|\sIV\s|\sV\s', s)) and not bool(re.search(r'[1]', s))

def remove_one(s):
    if ' 1' == s[-2:]:
        s = s.replace(' 1','')

    elif ' 1 ' in s:
        s = s.replace(' 1 ',' ')
    return s

def trans_num(path):
    if ' 5' in path:
        path = path.replace(' 5', ' V')

    elif ' 8' in path:
        path = path.replace(' 8', ' VIII')

    elif ' 7' in path:
        path = path.replace(' 7',' VII')

    elif ' 6' in path:
        path = path.replace(' 6', ' VI')

    elif ' 4' in path:
        path = path.replace(' 4', ' IV')

    elif ' 3' in path:
        path = path.replace(' 3', ' III')

    elif ' 2' in path:
        path = path.replace(' 2', ' II')

    elif ' 5' in path:
        path = path.replace(' 5', ' V')

    elif ' VIII' in path:
        path = path.replace(' VIII', ' 8')

    elif ' VII' in path:
        path = path.replace(' VII', ' 7')

    elif ' VI' in path:
        path = path.replace(' VI', ' 6')

    elif ' IV' in path:
        path = path.replace(' IV', ' 4')

    elif 'III' in path:
        path = path.replace(' III', '3')

    elif 'II' in path:
        path = path.replace(' II', '2')

    return path


def makeSeqList(base_str, list1, list2):
    results = [base_str]
    list1.sort()
    list2.sort()
    # 각 리스트의 조합 생성
    for r in range(1, len(list1) + 1):
        for combo1 in itertools.combinations(list1, r):
            results.append((base_str,)+combo1)

    for r in range(1, len(list2) + 1):
        for combo2 in itertools.combinations(list2, r):
            results.append((base_str,)+combo2)

    # 두 리스트의 모든 조합을 결합하여 추가
    for r1 in range(1, len(list1) + 1):
        for combo1 in itertools.combinations(list1, r1):
            for r2 in range(1, len(list2) + 1):
                for combo2 in itertools.combinations(list2, r2):
                    results.append((base_str,)+combo1 + combo2)
    
    return results

# def makeSeqList(input_list):
#     results = []
#     for r in range(1, len(input_list) + 1):
#         for combo in itertools.combinations(input_list, r):
#             results.append(combo)
#     return results

def subString(text):
    text = text.replace(':','-')
    # pattern = re.compile(r'-\s*([^-\r\n]+?)(?:\s*\([^)]*\))?\s*(?=-|$)', re.IGNORECASE)
    # pattern = re.compile(r'\s-\s*([^-\r\n]+?)(?:\s*\([^)]*\))?\s*(?=\s-|\s*\([^)]*\)|$)', re.IGNORECASE)
    pattern = re.compile(r'\s-\s*([^\r\n]+?)(?:\s*\([^)]*\))?\s*(?=\s-|\s*\([^)]*\)|$)', re.IGNORECASE)

    matches = pattern.findall(text)
    results = [f"- {match.strip()}" for match in matches]
    new_text = text
    for r in results:
        new_text = new_text.replace(r, '')
    new_text = new_text.strip()
    return new_text, [r[2:] for r in results]


def _normString(text):
    text = remove_extension(text)
    sub_string = subString(text)
    src_string = sub_string[0]
    sub_list = sub_string[1]
    pattern1 = '(\([^)]+\)|(\[+[^)]+\]))'
    result = re.findall(pattern1, src_string)
    find_r_list = []
    for find_r in result:
        find_r_list.append(find_r[0].replace('(','').replace(')','').replace('[','').replace(']',''))
        src_string = src_string.replace(find_r[0],'')
    n_text = space_number(src_string.strip())
    return n_text, sub_list, find_r_list

def normString(text):
    text = remove_extension(text)
    pattern1 = '(\([^)]+\)|(\[+[^)]+\]))'
    result = re.findall(pattern1, text)
    find_r_list = []
    for find_r in result:
        find_r_list.append(find_r[0].replace('(','').replace(')','').replace('[','').replace(']',''))
        text = text.replace(find_r[0],'')
    n_text = space_number(text.strip())
    sub_string = subString(n_text)
    src_string = sub_string[0]
    sub_list = sub_string[1]

    return src_string, sub_list, find_r_list

def remove_extension(filename):
    # os.path.splitext()를 사용하여 파일명과 확장자를 분리
    basename, _ = os.path.splitext(filename)
    return basename

def removeBucket(t_str):
    pattern = '(\([^)]+\)|(\[+[^)]+\]))'
    # pattern = '(\s\([^)]+\))'
    result = re.findall(pattern, t_str)
    for find_r in result:
        t_str = t_str.replace(find_r[0],'')
    return t_str.strip()

def space_number(src):
    pattern = '([가-힣a-zA-Z][0-9])'
    result = re.findall(pattern, src)
    for d in result:
        src = src.replace(d, d[0]+' '+d[1])
    return src

# def mix_ratio(src, tgt):

#     src = space_number(src)
#     r1 = fuzz.token_sort_ratio(src, tgt)
#     # r2 = fuzz.ratio(src, tgt)

    return r1

def mix_ratio(src, choices, limit=1):
    src = space_number(src)

    r1 = process.extract(src, choices, scorer=fuzz.token_sort_ratio, limit=1000)
    r2 = process.extract(src, choices, scorer=fuzz.WRatio, limit=1000)
    # r3 = process.extract(src, choices, scorer=fuzz.ratio, limit=1000)

    sc_dict = {}
    for (k, v) in set(r1):
        sc_dict[k] = v/2

    for (k, v) in set(r2):
        if k in sc_dict:
            sc_dict[k] += v/2
        else:
            sc_dict[k] = v/2

    if len(sc_dict) == 0:
        return (0, 0)
    data = list(sc_dict.items())
    data.sort(key=lambda x : x[1], reverse=True)
    if limit == 1:
        return data[0]
    else:
        return data[:limit]


def check_kor(text):
    p = re.compile('[ㄱ-힣]')
    r = p.search(text)
    if r is None:
        return False
    else:
        return True

def get_hash(file_path):

    f = open(file_path, 'rb')
    data = f.read()
    f.close()    
    return {'crc':hex(zlib.crc32(data))[2:], 'md5':hashlib.md5(data).hexdigest()}

def get_crc(file_path):
    # buffersize = 1024*1024*1024
    buffersize = 65536
    with open(file_path, 'rb') as afile:
        buffr = afile.read(buffersize)
        crcvalue = 0
        while len(buffr) > 0:
            # print(crcvalue)
            crcvalue = zlib.crc32(buffr, crcvalue)
            b_buffr = buffr
            buffr = afile.read(buffersize)    
    
    return hex(crcvalue)[2:]


class MatchingRoms:

    def __init__(self, roms_path, system_name) -> None:
        self.translator = Translator()
        self.con = sqlite3.connect(DB_FILE_PATH)
        self.roms_path = roms_path
        self.system_name = system_name
        self.fuzz_data = {}
        self.fuzz_data2 = {}
        self.read_fuzz_data()


    def read_fuzz_data(self):
        cur = self.con.cursor()
        tb_name = 'games_'+self.system_name
        
        r = cur.execute(f"SELECT * from {tb_name}")
        for line in r:
            game_name = line[1]
            self.fuzz_data2[game_name] = line[0]
            game_name = game_name.replace(' : ',' ')
            game_name = game_name.replace(' ','')
            self.fuzz_data[game_name] = line[0]
        
    def get_roms_info(self, rom_id):
        cur = self.con.cursor()
        tb_name = 'roms_'+self.system_name
        
        r = cur.execute(f"SELECT * from {tb_name} WHERE id = '{str(rom_id)}'")
        r = r.fetchone()
        return r[2]

    def check_file_hash(self, file_name, is_force_check=False):
        selected_game_roms_info = {}
        if self.roms_path == None:
            return selected_game_roms_info
        file_full_path = self.roms_path+'\\'+file_name
        if os.path.isfile(file_full_path):
            if os.path.getsize(file_full_path) <= 1024 * 1024 * 30:
                r_hash = get_hash(file_full_path)
                crc_val = r_hash['crc']
                md5_val = r_hash['md5']

                cur = self.con.cursor()
                tb_name = 'roms_'+self.system_name
                r = cur.execute(f"SELECT * from {tb_name} WHERE rom_md5 = '{str(md5_val)}' or rom_crc = '{str(crc_val)}'")
                r = r.fetchone()
                if r != None:
                    selected_game_roms_info[r[8]] = [r]
                return selected_game_roms_info

            elif is_force_check:
                crc_val = get_crc(file_full_path)
                cur = self.con.cursor()
                tb_name = 'roms_'+self.system_name
                r = cur.execute(f"SELECT * from {tb_name} WHERE  rom_crc = '{str(crc_val)}'")
                r = r.fetchone()
                if r != None:
                    selected_game_roms_info[r[8]] = [r]
                return selected_game_roms_info

            else:
                return selected_game_roms_info
        else:
            return selected_game_roms_info

        # is_name_kor = False
        # if check_kor(file_name):
        #     is_name_kor = True
        #     translation = self.translator.translate(file_name, dest='en')
        #     translated_text = translation.text
        #     translated_file_name = translated_text
        #     target_db_data = self.rom_file_name_kor
        # else:
        #     target_db_data = self.rom_file_name

    def read_local_files(self, local_path=None, is_exclude_xml = True):

        if local_path == None:
            roms_path = self.roms_path
        else:
            roms_path = local_path
        if is_exclude_xml:
            rm_extension = ('.txt', '.xml', '.dat', '.mp3', '.mp4', '.bak', '.htm', '.pdf', '.png', '.jpg', '.gif', '.bmp', '.exe', '.bat' ,'edia')
        else:
            rm_extension = ('.txt', '.dat', '.mp3', '.mp4', '.bak', '.htm', '.pdf', '.png', '.jpg', '.gif', '.bmp', '.exe', '.bat' ,'edia')

        for data_name in os.listdir(roms_path):
            if os.path.isfile(roms_path+'\\'+data_name) and not data_name[-4:] in rm_extension:
                o_file_name = data_name
            elif os.path.isdir(roms_path+'\\'+data_name):
                o_file_name = data_name
            else:
                continue
            yield o_file_name

    def local_name(self, file_name):
        yield file_name

    def searchDB(self, system_name, base_title, sub_title_list): # base_title 과 sub_title이 game_name 또는 filename 또는 src_name에 모두 존재할때
        tb_name = 'roms_'+system_name

        cur = self.con.cursor()

        insert_q1 = f'game_name like "{base_title}%"'
        for sub_title in sub_title_list:
            insert_q1 += f' and game_name like "%{sub_title}%"'

        insert_q2 = f'filename like "{base_title}%"'
        for sub_title in sub_title_list:
            insert_q2 += f' and filename like "%{sub_title}%"'

        insert_q3 = f'src_name like "{base_title}%"'
        for sub_title in sub_title_list:
            insert_q3 += f' and src_name like "%{sub_title}%"'


        insert_sql = f"SELECT * FROM {tb_name} WHERE ({insert_q1}) or ({insert_q2}) or ({insert_q3})"
        # print(insert_sql)
        r = cur.execute(insert_sql)
        data_list = []
        selected_game_roms_info = {}
        for line in r:
            game_id = line[8]
            selected_game_roms_info.setdefault(game_id,[]).append(line)

        return selected_game_roms_info,insert_sql

    def searchDB2(self, system_name, base_title, sub_title_list): # base_title 과 sub_title를 토큰(띄어쓰기 기준)으로 나눴을 때 토큰이 game_name 또는 filename 또는 src_name에 모두 존재할때
        tb_name = 'roms_'+system_name

        cur = self.con.cursor()

        if '_' in base_title:
            base_title = base_title.replace('_',' ')

        base_title_token_list = base_title.split(' ')

        add_bucket_str_list = []
        last_region_check = base_title_token_list[-1].lower()
        # if last_region_check in ['kor','korea','korean', 'kr']:
        #     add_bucket_str_list = ['Korea']


        last_region_check = base_title_token_list[-1].lower()
        if last_region_check in ['kor','korea','korean', 'kr']:
            add_bucket_str_list = ['Korea']
            base_title_token_list.pop()
        elif last_region_check in ['jp', 'jap', 'japan']:
            add_bucket_str_list = ['Japan']
            base_title_token_list.pop()
        elif last_region_check in ['eur', 'europe']:
            add_bucket_str_list = ['Europe']
            base_title_token_list.pop()


        insert_q1 = f'game_name like "%{base_title_token_list[0]}%"'
        insert_q2 = f'filename like "%{base_title_token_list[0]}%"'
        insert_q3 = f'src_name like "%{base_title_token_list[0]}%"'       

        if len(base_title_token_list[0]) <= 3:
            insert_q1 = f'game_name like "{base_title_token_list[0]}%"'
            insert_q2 = f'filename like "{base_title_token_list[0]}%"'
            insert_q3 = f'src_name like "{base_title_token_list[0]}%"'

        for base_title_token in base_title_token_list[1:]:
            insert_q1 += f' and game_name like "%{base_title_token}%"'
        for sub_title in sub_title_list:
            insert_q1 += f' and game_name like "%{sub_title}%"'

        for base_title_token in base_title_token_list[1:]:
            insert_q2 += f' and filename like "%{base_title_token}%"'
        for sub_title in sub_title_list:
            insert_q2 += f' and filename like "%{sub_title}%"'

        for base_title_token in base_title_token_list[1:]:
            insert_q3 += f' and src_name like "%{base_title_token}%"'
        for sub_title in sub_title_list:
            insert_q3 += f' and src_name like "%{sub_title}%"'


        insert_sql = f"SELECT * FROM {tb_name} WHERE ({insert_q1}) or ({insert_q2}) or ({insert_q3})"
        # print(insert_sql)
        r = cur.execute(insert_sql)
        selected_game_roms_info = {}
        for line in r:
            game_id = line[8]
            selected_game_roms_info.setdefault(game_id,[]).append(line)

        return selected_game_roms_info, add_bucket_str_list, insert_sql

    def searchDB3(self, system_name, base_title): # base_title token이 game_name에 포함되어 있는 경우만
        tb_name = 'roms_'+system_name

        cur = self.con.cursor()

        if '_' in base_title:
            base_title = base_title.replace('_',' ')

        insert_q1 = f'game_name like "%{base_title}%"'

        if len(base_title) <= 3:
            insert_q1 = f'game_name like "{base_title[0]}%"'


        insert_sql = f"SELECT * FROM {tb_name} WHERE ({insert_q1})"
        # print(insert_sql)
        r = cur.execute(insert_sql)
        selected_game_roms_info = {}
        for line in r:
            game_id = line[8]
            selected_game_roms_info.setdefault(game_id,[]).append(line)

        return selected_game_roms_info, insert_sql


    def searchDB4(self, system_name, base_title, sub_title_list): # base_title token이 game_name에 포함되어 있는 경우만
        tb_name = 'roms_'+system_name


        cur = self.con.cursor()
        ori_base_title = base_title
        if '_' in base_title:
            base_title = base_title.replace('_',' ')
        
        base_title = base_title+''.join(sub_title_list)
        base_title = base_title.replace(' ','')
        selected_game_roms_info = {}

        r1 = mix_ratio(base_title, self.fuzz_data.keys())
        r2 = mix_ratio(ori_base_title, self.fuzz_data2.keys())

        if r2[1] >= r1[1]:
            r = r2
            fuzz_data = self.fuzz_data2
        else:
            r = r1
            fuzz_data = self.fuzz_data

        cr_val = 60
        print('!!!!!!!! :',r[1])
        if system_name in ['dos']:
            cr_val = 90
        if r[1] >= cr_val:
            game_id = fuzz_data[r[0]]
        else:
            return selected_game_roms_info

        insert_sql = f"SELECT * FROM {tb_name} WHERE game_id = {game_id}"

        r = cur.execute(insert_sql)
        for line in r:
            game_id = line[8]
            selected_game_roms_info.setdefault(game_id,[]).append(line)

        return selected_game_roms_info

    def checkRegion(self, base_title, bucket_str_list, selected_game_roms_info):
        if (bucket_str_list) == 0:
            return selected_game_roms_info
        bucket_str_list = set([i.lower() for i in bucket_str_list])


        new_selected_game_roms_info = {}
        for game_id in selected_game_roms_info:
            for game_info in selected_game_roms_info[game_id]:
                rom_name = game_info[2]
                src_name = game_info[1]
                if rom_name != None:
                    rom_name = rom_name.lower()
                else:
                    continue
                for bucket_str in bucket_str_list:
                    if bucket_str in rom_name:
                        new_selected_game_roms_info.setdefault(game_id, set([])).add(game_info)
                        break
        
        for k in new_selected_game_roms_info:
            new_selected_game_roms_info[k] = list(new_selected_game_roms_info[k])
        
        if len(new_selected_game_roms_info) == 0:
            return selected_game_roms_info
        
        return new_selected_game_roms_info

    def getGameRoms(self, selected_game_info, is_result_roms=True):
        selected_games = set([])
        selected_roms = set([])
        for game_id in selected_game_info:
            rom_data_list = selected_game_info[game_id]
            for rom_data in rom_data_list:
                rom_name = rom_data[2]
                game_name = rom_data[9]
                selected_games.add(game_name)
                selected_roms.add(rom_name)
        if is_result_roms == False:
            return selected_roms, selected_games
        return selected_games, selected_roms
    
    def closeMatching(self, base_title, sub_title_list, selected_game_roms_info): #후보 game_name이 2개 이상일 때, input_name과 fuzz가 가장 가까운걸로
        if '_' in base_title:
            base_title = base_title.replace('_',' ')
        
        base_title = base_title+''.join(sub_title_list)
        base_title = base_title.replace(' ','')

        new_selected_game_roms_info = {}

        recomm_list = {}
        for game_id in selected_game_roms_info:
            game_info = selected_game_roms_info[game_id][0]
            game_name = game_info[9]
            recomm_list[game_name] = game_id
        
        r = mix_ratio(base_title, recomm_list.keys())
        selected_game_id = recomm_list[r[0]]
        new_selected_game_roms_info[selected_game_id] = selected_game_roms_info[selected_game_id]
        return new_selected_game_roms_info

    def run(self, test=None, other_path=False, is_print_all=True, is_result_roms=False): # test는 그냥 경로가 아닌 이름만 써서 테스트 할 경우, other_path는 xml파일 제외 여부정도,
        no_search = False
        if test != None:
            iterator = self.local_name(test)
        else:
            if other_path:
                iterator = self.read_local_files(is_exclude_xml=False)
            else:
                iterator = self.read_local_files()


        for o_file_name in iterator:
            selected_game_roms_info = self.check_file_hash(o_file_name)
            if len(selected_game_roms_info) != 0:
                game_name_list, rom_name_list = self.getGameRoms(selected_game_roms_info, is_result_roms)
                if is_print_all:
                    print(o_file_name,'||', rom_name_list, 'hash')
                continue

            base_title, sub_title_list, bucket_str_list = normString(o_file_name)
            selected_game_roms_info, insert_sql = self.searchDB(self.system_name, base_title, sub_title_list)
            # print(insert_sql)            
            if len(selected_game_roms_info) == 0: # 쿼리 후보 대상이 하나도 없다면.. 
                ori_base_title = base_title
                base_title = trans_num(remove_one(base_title)) # base_title의 문자를 약간 조작 (숫자 변경 등)
                selected_game_roms_info, insert_sql = self.searchDB(self.system_name, base_title, sub_title_list)

                if len(selected_game_roms_info) == 0: # 이 file은 쿼리 로 후보 자체를 찾을 수 없음.. (계속)
                    base_title = ori_base_title
                    selected_game_roms_info, add_bucket_str_list, insert_sql = self.searchDB2(self.system_name, base_title, sub_title_list)
                    bucket_str_list = list(set(bucket_str_list + add_bucket_str_list))

                    if len(selected_game_roms_info) == 0: #이 file은 쿼리 로 후보 자체를 찾을 수 없음.. (계속)
                        # print(insert_sql)
                        base_title = trans_num(remove_one(base_title))
                        selected_game_roms_info, add_bucket_str_list, insert_sql = self.searchDB2(self.system_name, base_title, sub_title_list)

                        if len(selected_game_roms_info) == 0: #이 file은 쿼리 로 후보 자체를 찾을 수 없음.. (계속)
                            base_title = ori_base_title
                            selected_game_roms_info, insert_sql = self.searchDB3(self.system_name, base_title)
                            # print(insert_sql)

                            if len(selected_game_roms_info) == 0: #이 file은 쿼리 로 후보 자체를 찾을 수 없음.. (계속)
                                selected_game_roms_info = self.check_file_hash(o_file_name, is_force_check=True)
                                if len(selected_game_roms_info) != 0:
                                    game_name_list, rom_name_list = self.getGameRoms(selected_game_roms_info, is_result_roms)
                                    if is_print_all:
                                        print(o_file_name,'||', rom_name_list, 'hash')
                                else:
                                    selected_game_roms_info = self.searchDB4(self.system_name, base_title, sub_title_list)
                                    if len(selected_game_roms_info) == 0:
                                        print(o_file_name, 'NOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOON')
                                        no_search = True
                                        # return base_title                          
                                        continue
                                        

            if len(selected_game_roms_info) == 1: # 쿼리 후보 대상이 1개라면 해당 game 선택 (끝)
                selected_game_roms_info = self.checkRegion(base_title, bucket_str_list, selected_game_roms_info)                
                game_name_list, rom_name_list = self.getGameRoms(selected_game_roms_info, is_result_roms)
                if is_print_all:
                    print(o_file_name,'||',rom_name_list, '1')

            else: # 쿼리 후보 대상이 2개 이상이라면
                if base_title in selected_game_roms_info: #기본 제목이 game_name 목록과 완전 동일 이라면 해당 게임 선택 (끝)
                    selected_game_roms_info = self.checkRegion(base_title, bucket_str_list, selected_game_roms_info)
                    game_name_list, rom_name_list = self.getGameRoms(selected_game_roms_info, is_result_roms)
                    if is_print_all:
                        print(o_file_name,'||',rom_name_list, '11')
                    continue


                if not contains_digit(base_title):  #기본 제목에 숫자가 없는 title 이라면 (쿼리 후보에 숫자가 있는 것도 같이 뽑히겠지)

                    removed_game_id_list = set([])
                    for game_id in selected_game_roms_info:
                        game_info_list = selected_game_roms_info[game_id]
                        for game_info in game_info_list:
                            game_name = game_info[9]
                            if contains_digit(game_name): # 숫자가 있는 game_name은 제외
                                removed_game_id_list.add(game_id)

                    if len(selected_game_roms_info) > len(removed_game_id_list):
                        for game_id in removed_game_id_list: #후보 game_name 목록 중에서
                                selected_game_roms_info.pop(game_id)

                    if len(selected_game_roms_info) == 1: #위에 제외 후 1개만 남았다면 그녁석을 선택 (끝)
                        selected_game_roms_info = self.checkRegion(base_title, bucket_str_list, selected_game_roms_info)
                        game_name_list, rom_name_list = self.getGameRoms(selected_game_roms_info, is_result_roms)
                        if is_print_all:
                            print(o_file_name,'||',rom_name_list, '4')

                    else: # 위에 제외 후에도 2개 이상이라면 일단 2개 이상 이면 후보 중 가장 src_name 과 유사한 걸로 뽑음 (끝)
                        selected_game_roms_info = self.closeMatching(base_title, sub_title_list, selected_game_roms_info)
                        selected_game_roms_info = self.checkRegion(base_title, bucket_str_list, selected_game_roms_info)
                        game_name_list, rom_name_list = self.getGameRoms(selected_game_roms_info, is_result_roms)
                        if is_print_all:
                            print(o_file_name,'||',rom_name_list, '5')

                else: # 기본 제목에 숫자가 있는 타이틀 이라면.(숫자도 반드시 반영 되었겠지).. 이경우는 현재 2개 이상으로 냅둠 (계속)
                    selected_game_roms_info = self.closeMatching(base_title, sub_title_list, selected_game_roms_info)
                    selected_game_roms_info = self.checkRegion(base_title, bucket_str_list, selected_game_roms_info)
                    game_name_list, rom_name_list = self.getGameRoms(selected_game_roms_info, is_result_roms)
                    if is_print_all:
                        print(o_file_name,'||',rom_name_list, '2')

        return no_search, base_title




    
def test2():
    file = r'G:\ROMs\ps2\Jin Samguk Mussang 5 Special (Korea).iso'
    print(os.path.getsize(file))
    r = get_crc(file)
    print(r)

def test3():
    system_name = 'ps2'
    con = sqlite3.connect(DB_FILE_PATH)
    cur = con.cursor()
    tb_name = 'games_'+system_name
    
    r = cur.execute(f"SELECT * from {tb_name}")
    n = 0
    game_name_set = set([])
    for line in r:
        game_name = line[1]
        game_name = game_name.replace(' : ',' ')
        game_name = game_name.replace(' ','')
        game_name_set.add(game_name)
        rom_file_name = line[2]
    
    r = mix_ratio('Disgaia', game_name_set)
    print(r)

def test4():

    text1 = "A-mazing Tater (Atlus)[tr es]"
    text2 = "Tantei Jinguji Saburo - Innocent Black (Japan).iso"
    print(normString(text1))
    print(normString(text2))

def test5():
    base_str = 'kkk'
    a = ['x','y']
    b = ['a','b']
    print(makeSeqList(base_str,a,b))

def test6():
    a = 'viewtiful '
    b = 'To Heart 2'
    r = fuzz.WRatio(a,b)
    r2 = mix_ratio(a, [b])
    r3 = fuzz.ratio(a,b)
    print(r, r2, r3)

def test_nlp():
    import spacy
    roms_path = r'G:\ROMs\ps2'
    system_name = 'ps2'

    nlp = spacy.load('en_core_web_trf')
    for data_name in os.listdir(roms_path):
        if os.path.isfile(roms_path+'\\'+data_name) and not data_name[-4:] in ('.txt', '.xml', '.dat', '.mp3', '.mp4', '.bak', '.htm', '.pdf', '.png', '.jpg', '.gif', '.bmp', '.exe', '.bat' ,'edia'):
            o_file_name = data_name
        elif os.path.isdir(roms_path+'\\'+data_name):
            o_file_name = data_name
        else:
            continue
        # print(o_file_name)
    # text = 
    
        base_title, sub_title_list, bucket_str_list = normString(space_number(o_file_name))
        r_nlp1 = nlp(base_title)
        t_list = []
        for token in r_nlp1:
            t_list.append((token, token.tag_))
        for sub_title in sub_title_list:
            r_nlp2 = nlp(sub_title)
            for token in r_nlp2:
                t_list.append((token, token.tag_))

        print(o_file_name, t_list, bucket_str_list)

def test():
    rom_path = r'G:\ROMs\ps2'
    # rom_path = r'E:\Emul\Full_Roms_assets\ps2\textual'
    system_name = 'ps2'
    mr = MatchingRoms(rom_path, system_name)
    # r = mr.get_roms_info(1025140)
    # print(r)
    # for line in mr.choice_list:
    #     print(line)
    mr.run(other_path=False)

if __name__ == "__main__":
    test4()