
import json
import os
import requests
import pprint
from bs4 import BeautifulSoup
from threading import Thread
import sqlite3
import random
from thefuzz import process
from thefuzz import fuzz
import re
import xml.etree.ElementTree as ET
from main_new import MatchingRoms, normString, remove_extension

SYSTEM_INFO_FILE_PATH = "./es-manage-app/src/info.json"
DB_FILE_PATH = "./es-manage-app/src/games_meta.db"
ROMS_XML_BASE_PATH = r'E:\Emul\Full_Roms_assets'
ROMS_TABLE_SCHEMA = "(id text, src_name text, filename text, filename_kor text, rom_size integer, rom_crc text, rom_md5 text, rom_sha1 text, game_id integer, game_name text, alt integer, beta integer, demo integer, langs text, langs_short text, regions text, regions_short text)"
GAMES_TABLE_SCHEMA = "(id text, name text, name_kor text, desc text, desc_kor text, genre text, releasedate text, developer text, players text)"
RETROARCH_META_PATH = r"E:\Emul\Full_Roms_meta"
TENTACLE_ROM_META_PATH = "./es-manage-app/src/tentacle_meta"



def cleansingText(inputText):
    if inputText == None:
        return None
    r = BeautifulSoup(inputText, 'lxml').text
    # for rpr in ['<br>','<BR>','<p>','<P>','</p>','</P>']:
    #     r = r.replace(rpr,' ')
    return r

def removeBucket(t_str):
    pattern = '(\([^)]+\)|(\[+[^)]+\]))'
    # pattern = '(\s\([^)]+\))'
    result = re.findall(pattern, t_str)
    for find_r in result:
        t_str = t_str.replace(find_r[0],'')
    return t_str.strip()

def mix_ratio(src, choices, limit=1):
    r1 = process.extract(src, choices, scorer=fuzz.token_sort_ratio, limit=1000)
    r2 = process.extract(src, choices, scorer=fuzz.WRatio, limit=1000)
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

class SSRomsMeta:

    def __init__(self, system_name):
        self.con = sqlite3.connect(DB_FILE_PATH)
        self.base_url = "https://api.screenscraper.fr/api2/jeuInfos.php"
        json_fp = open(SYSTEM_INFO_FILE_PATH)
        self.system_info = json.load(json_fp)['system_info']
        for sys_obj in self.system_info:
            sys_name = sys_obj['name_esde']
            if system_name == sys_name:
                sys_id = sys_obj['scrapper_system_id']
                ra_system_name = sys_obj['name']
        self.system_name = system_name
        self.ra_system_name = ra_system_name

        self.sys_id = str(sys_id)
        self.rom_name_set = {}
        self.run_bucket = set([])
        self.pre_read_file = {}

        self.md5_to_rom_id = {}
        self.crc_to_rom_id = {}

        self.roms_meta = {} #key : rom_id
        self.games_meta ={} #key : jeu_id

        self.tot_search_num = 0
        self.get_num = 0
        self.api_call_num = 0

        self.stop_call_api = False

        print(self.system_name)
        self.preLoadTable()

    def preLoadTable(self):
        cur = self.con.cursor()
        tb_name_game = 'games_'+self.system_name
        tb_name_rom = 'roms_'+self.system_name

        r = cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tb_name_game}'")
        r = r.fetchone()
        if r == None:
            return 0
        else:
            if r[0] == tb_name_game:
                pass
            else:
                return 0

        r0 = cur.execute(f"SELECT * FROM {tb_name_game};")
        for line in r0:
            self.games_meta[line[0]] = line
        

        r1 = cur.execute(f"SELECT * FROM {tb_name_rom};")
        for line in r1:
            self.roms_meta[line[0]] = line
            self.rom_name_set.setdefault(remove_extension(line[2]), set([])).add(line[0])
            if line[5] != None:
                self.crc_to_rom_id[line[5].lower()] = line[0]
            if line[6] != None:
                self.md5_to_rom_id[line[6].lower()] = line[0]
            if line[1] != None:
                for f_name in line[1].split(';;'):
                    self.pre_read_file.setdefault(f_name, set([])).add(line[0])
                    
    def jsonParsing(self, result_data, s_file_name, ra_rom_meta_set=None):
        jeu_id = result_data['response']['jeu']['id']
        tmp_name_dict = {}
        for data in result_data['response']['jeu']['noms']:
            tmp_name_dict[data['region']] = data['text']
        game_name = None
        if "jp" in tmp_name_dict:
            game_name = tmp_name_dict['jp']
        elif "us" in tmp_name_dict:
            game_name = tmp_name_dict['us']
        else:
            game_name = tmp_name_dict['ss']
        release_date = None
        if 'dates' in result_data['response']['jeu']:
            release_date = sorted(result_data['response']['jeu']['dates'], key=lambda x: x['text'])[0]['text'] 
        
        developer = None
        if 'developpeur' in result_data['response']['jeu']:
            developer = result_data['response']['jeu']['developpeur']['text']

        desciption = None
        if 'synopsis' in result_data['response']['jeu']:
            for data in result_data['response']['jeu']['synopsis']:
                if data['langue'] == 'en':
                    desciption = cleansingText(data['text'])
                    break

        genre = None
        if 'genres' in result_data['response']['jeu']:
            for data in result_data['response']['jeu']['genres'][0]['noms']:
                if data['langue'] == 'en':
                    genre = data['text']
                    break
        players = None
        if 'joueurs' in result_data['response']['jeu']:
            players = result_data['response']['jeu']['joueurs']['text']    

        s_rom_id_list = []
        if 'rom' in result_data['response']['jeu']:
            s_rom_id = int(result_data['response']['jeu']['rom']['id'])
            s_rom_id_list = [s_rom_id]

        roms_data = result_data['response']['jeu']['roms']

        self.games_meta[jeu_id] = (jeu_id, game_name, None, desciption, None, genre, release_date, developer, players)
        tmp_roms_file_name_set = set([])
        check_crc = False
        alt, beta, demo, langs, langs_short, regions, regions_short = None, None, None, None, None, None, None
        for rom_data in roms_data:
            alt = int(rom_data['alt'])
            beta = int(rom_data['beta'])
            demo = int(rom_data['demo'])

            langs = None
            langs_short = None
            regions = None
            regions_short = None

            if 'langues' in rom_data:
                langs = ",".join(rom_data['langues']['langues_en'])
                langs_short = ",".join(rom_data['langues']['langues_shortname'])

            if 'regions' in rom_data:
                regions = ",".join(rom_data['regions']['regions_en'])
                regions_short = ",".join(rom_data['regions']['regions_shortname'])


            rom_id = int(rom_data['id'])
            rom_crc = rom_data['romcrc']
            if rom_crc == '':
                rom_crc = None
            if rom_crc != None:
                self.crc_to_rom_id[rom_crc.lower()] = rom_id
                if rom_crc.lower() == check_crc:
                    check_crc = True
            rom_md5 = rom_data['rommd5']
            if rom_md5 == '':
                rom_md5 = None
            if rom_md5 != None:
                self.md5_to_rom_id[rom_md5.lower()] = rom_id
            rom_sha1 = rom_data['romsha1']
            if rom_sha1 == '':
                rom_sha1 = None
            rom_size = int(rom_data['romsize'])
            if rom_size == '':
                rom_size = None
            rom_filename = rom_data['romfilename']
            tmp_roms_file_name_set.add(remove_extension(rom_filename))
            # if s_file_name in rom_filename[:-4]:
            #     s_rom_id = rom_id
            # self.rom_name_set[rom_filename[:-4]] = rom_id
            self.rom_name_set.setdefault(remove_extension(rom_filename), set([])).add(rom_id)
            if rom_id in self.roms_meta:
                continue
            self.roms_meta[rom_id] = (rom_id, None, rom_filename, None, rom_size, rom_crc, rom_md5, rom_sha1, jeu_id, game_name, alt, beta, demo, langs, langs_short, regions, regions_short)
        
        mr = mix_ratio(s_file_name, tmp_roms_file_name_set)
        if mr[1] >= 80:
            s_rom_id_list = list(self.rom_name_set[mr[0]])
            from_info = self.roms_meta[s_rom_id_list[0]]
            alt, beta, demo, langs, langs_short, regions, regions_short = from_info[10], from_info[11], from_info[12], from_info[13], from_info[14], from_info[15], from_info[16],
            if check_crc == False and ra_rom_meta_set != None:
                for rom_meta in ra_rom_meta_set:
                    from_rom_crc = rom_meta[3]
                    self.roms_meta['ra_'+from_rom_crc] = ('ra_'+from_rom_crc,  rom_meta[0],  rom_meta[1], None,  rom_meta[2],  rom_meta[3],  rom_meta[4],  rom_meta[5], jeu_id, game_name, alt, beta, demo, langs, langs_short, regions, regions_short)
        else:
            if ra_rom_meta_set != None:
                for rom_meta in ra_rom_meta_set:
                    from_rom_crc = rom_meta[3]
                    self.roms_meta['ra_'+from_rom_crc] = ('ra_'+from_rom_crc,  rom_meta[0],  rom_meta[1], None,  rom_meta[2],  rom_meta[3],  rom_meta[4],  rom_meta[5], jeu_id, game_name, None, None, None, None, None, None, None)

        return s_rom_id_list

    def update_src(self, file_name, s_rom_id):
        tmp_data = list(self.roms_meta[s_rom_id])
        if tmp_data[1] == None:
            tmp_data[1] = file_name
        else:
            tmp_split_data = set(tmp_data[1].split(';;'))
            tmp_split_data.add(file_name)
            tmp_data[1] = ";;".join(tmp_split_data)
        self.roms_meta[s_rom_id] = tuple(tmp_data)

    def call_api(self, file_name, rom_meta=None):
        if self.stop_call_api:
            self.run_bucket.remove(file_name)
            return 0

        param = {"devid":"evegood", "devpassword":"yPoo9XlnDCG", "output":"json", "ssid":"evegood", 'sspassword':"1132dudwls", "systemeid":self.sys_id, "romtype":"rom", "romnom":file_name}
        try:
            resp = requests.get(self.base_url, params=param, timeout=30)
        except requests.exceptions.Timeout as e:
            print('Timeout Error : ',file_name)
            self.run_bucket.remove(file_name)
            return 0
        if resp.status_code == 200:
            json_data = json.loads(resp.text)
        else:
            if 'Erreur : Jeu non trouvée !' in resp.text or 'Erreur : Rom/Iso/Dossier non trouvée !' in resp.text:
                if not ' - ' in file_name:
                    self.run_bucket.remove(file_name)
                    print('Error : ', resp.text, '::',file_name)
                    return 0
                self.api_call_num += 1
                r_file_name = file_name.split(' - ')[0].strip()
                param = {"devid":"evegood", "devpassword":"yPoo9XlnDCG", "output":"json", "ssid":"evegood", 'sspassword':"1132dudwls", "systemeid":self.sys_id, "romtype":"rom", "romnom":r_file_name}
                try:
                    resp = requests.get(self.base_url, params=param, timeout=30)
                except requests.exceptions.Timeout as e:
                    print('Timeout Error : ',file_name)
                    self.run_bucket.remove(file_name)
                    return 0
                if resp.status_code == 200:
                    json_data = json.loads(resp.text)
                else:
                    self.run_bucket.remove(file_name)
                    print('Error : ', resp.text, '::',file_name)
                    return 0
            elif "Votre quota de scrape est dépassé pour aujourd'hui" in resp.text or 'Faite du tri dans vos fichiers roms et repassez demain' in resp.text:
                self.stop_call_api = True
                self.run_bucket.remove(file_name)
                print('ERROR : qurter limit, stop call process')
                return 0

            else:
                self.run_bucket.remove(file_name)
                print('Error : ', resp.text, '::',file_name)
                return 0
        s_rom_id_list = self.jsonParsing(json_data, file_name, rom_meta)
        for s_rom_id in s_rom_id_list:
            self.update_src(file_name, s_rom_id)
        
        self.run_bucket.remove(file_name)

    def insertTable(self):
        # x = list(self.games_meta.values())
        # print(x)
        cur = self.con.cursor()
        tb_name_game = 'games_'+self.system_name
        tb_name_rom = 'roms_'+self.system_name
        try:
            cur.execute(f"DROP TABLE {tb_name_game}")
        except:
            pass
        try:
            cur.execute(f"CREATE TABLE {tb_name_game}{GAMES_TABLE_SCHEMA};")
        except:
            pass
        game_v = '('+','.join(['?']*len(GAMES_TABLE_SCHEMA.split(',')))+')'
        cur.executemany(f'INSERT INTO {tb_name_game} VALUES{game_v};', list(self.games_meta.values()))
        self.con.commit()

        try:
            cur.execute(f"DROP TABLE {tb_name_rom}")
        except:
            pass
        try:
            cur.execute(f"CREATE TABLE {tb_name_rom}{ROMS_TABLE_SCHEMA};")
        except:
            pass
        rom_v = '('+','.join(['?']*len(ROMS_TABLE_SCHEMA.split(',')))+')'
        cur.executemany(f'INSERT INTO {tb_name_rom} VALUES{rom_v};', list(self.roms_meta.values()))
        self.con.commit()



    def makeDBTable(self, data_name=None):

        xml_files_path = ROMS_XML_BASE_PATH+'\\'+self.system_name+'\\'+'textual'
        r = os.listdir(xml_files_path)
        name_set = {}
        for file_name in r:
            if file_name[-4:] != '.xml':
                continue
            base_title, sub_title_list, bucket_str_list = normString(file_name)
            if len(sub_title_list) > 0:
                base_name =  base_title + ' - '.join(sub_title_list)           
            else:
                base_name = base_title
            ori_file_name = remove_extension(file_name)
            name_set.setdefault(base_name, set([])).add(ori_file_name)
        
        if data_name != None:
            name_set = {}
            base_title, sub_title_list, bucket_str_list = normString(data_name)
            if len(sub_title_list) > 0:
                base_name =  base_title + ' - '+' '.join(sub_title_list)           
            else:
                base_name = base_title
            ori_file_name = remove_extension(data_name)
            name_set.setdefault(base_name, set([])).add(ori_file_name)

        th_list = []
        self.tot_search_num = len(name_set)
        # name_set = list(name_set)
        # random.shuffle(name_set)
        while len(name_set)!=0:

            while True:
                if self.stop_call_api:
                    break

                if len(self.run_bucket) <= 10:
                    break

            (base_name, src_roms_name_set) = name_set.popitem()

            self.get_num += 1
            match_rom_name_set = set([])
            for file_name in src_roms_name_set:
                if file_name in self.pre_read_file:
                    print(self.get_num, '/', self.tot_search_num, '('+str(self.api_call_num)+')', len(name_set), len(self.run_bucket))
                    match_rom_name_set.add(file_name)

            for nm in match_rom_name_set:
                if nm in src_roms_name_set:
                    src_roms_name_set.remove(nm)

            for file_name in src_roms_name_set:
                if file_name in self.rom_name_set:
                    s_rom_list = self.rom_name_set[file_name]
                    for s_rom in s_rom_list:
                        self.update_src(file_name, s_rom)                
                    print(self.get_num, '/', self.tot_search_num, '('+str(self.api_call_num)+')', len(name_set), len(self.run_bucket))
                    match_rom_name_set.add(file_name)

            for nm in match_rom_name_set:
                if nm in src_roms_name_set:
                    src_roms_name_set.remove(nm)

            for file_name in src_roms_name_set:
                mr = mix_ratio(file_name, tuple(self.rom_name_set.keys()))
                if mr[1] >= 98:
                    print('no call api :',file_name, mr[0])
                    s_rom_list = self.rom_name_set[mr[0]]
                    for s_rom in s_rom_list:
                        self.update_src(file_name, s_rom)
                    print(self.get_num, '/', self.tot_search_num, '('+str(self.api_call_num)+')', len(name_set), len(self.run_bucket))
                    match_rom_name_set.add(file_name)
         
            if len(match_rom_name_set) > 0 :
                continue

            if self.stop_call_api:
                break
            self.run_bucket.add(base_name)        
            self.api_call_num += 1
            t1 = Thread(target=self.call_api, args=(base_name,))
            t1.start()            
            th_list.append(t1)
    
            print(self.get_num, '/', self.tot_search_num, '('+str(self.api_call_num)+')', len(name_set), len(self.run_bucket))
            

        print('process join')
        for th in th_list:
            th.join()

        # self.after_merge_ra_meta()
        self.insertTable()


    def ra_parsing(self, total_str):
        pattern = 'game\s*\(([^()]*(?:\([^\)]*\)[^()]*)*)\)'

        name_pattern = 'name\s+"([^"]*)"\n'
        rom_pattern = '\srom\s*\(([^()]*(?:\([^\)]*\)[^()]*)*)\)'
        rom_name_pattern = 'name\s+"([^"]*)"'
        rom_size_pattern = 'size\s+([^\s]*)\s'
        rom_crc_pattern = 'crc\s+([^\s]*)\s'
        rom_md5_pattern = 'md5\s+([^\s]*)\s'
        rom_sha1_pattern = 'sha1\s+([^\s]*)\s'


        data_list = []
        result = re.findall(pattern, total_str)
        for line1 in result:
            try:
                line1 = line1 + ' )'
                name = re.findall(name_pattern, line1)[0]
                rom_str = re.findall(rom_pattern, line1)[0]
                rom_name = re.findall(rom_name_pattern, rom_str)[0]
                rom_size = re.findall(rom_size_pattern, rom_str)
            except:
                continue
            if rom_size == []:
                rom_size = None
            else:
                rom_size = int(rom_size[0])        
            rom_crc = re.findall(rom_crc_pattern, rom_str)
            if rom_crc == []:
                rom_crc = None
            else:
                rom_crc = rom_crc[0]

            rom_md5 = re.findall(rom_md5_pattern, rom_str)
            if rom_md5 == []:
                rom_md5 = None
            else:
                rom_md5 = rom_md5[0]

            rom_sha1 = re.findall(rom_sha1_pattern, rom_str)
            if rom_sha1 == []:
                rom_sha1 = None
            else:
                rom_sha1 = rom_sha1[0]        

            yield (name, rom_name, rom_size, rom_crc, rom_md5, rom_sha1)

    def check_data(self):
        file_list = []
        xml_files_path = ROMS_XML_BASE_PATH+'\\'+self.system_name+'\\'+'textual'
        r = os.listdir(xml_files_path)
        name_set = set([])
        for file_name in r:
            if file_name[-4:] != '.xml':
                continue
            name_set.add(remove_extension(file_name))        

        for file_name in os.listdir(RETROARCH_META_PATH):
            if file_name == self.ra_system_name+".dat":
                file_list.append(RETROARCH_META_PATH+'\\'+file_name)
                break
        
        for file_name in os.listdir(RETROARCH_META_PATH+'\\'+'no-intro'):
            if file_name == self.ra_system_name+".dat":
                file_list.append(RETROARCH_META_PATH+'\\'+'no-intro'+'\\'+file_name)
                break

        for file_name in os.listdir(RETROARCH_META_PATH+'\\'+'redump'):
            if file_name == self.ra_system_name+".dat":
                file_list.append(RETROARCH_META_PATH+'\\'+'redump'+'\\'+file_name)
                break

        for file_name in os.listdir(RETROARCH_META_PATH+'\\'+'tosec'):
            if file_name == self.ra_system_name+".dat":
                file_list.append(RETROARCH_META_PATH+'\\'+'tosec'+'\\'+file_name)
                break
        
        ra_meta_set = set([])
        for f_path in file_list:
            fp = open(f_path)
            try:
                data = fp.read()
            except UnicodeDecodeError:
                fp = open(f_path, encoding='utf-8')
                data = fp.read()
            for line in self.ra_parsing(data):
                ra_meta_set.add(line[0])

        name_set.update(ra_meta_set)

        mr = MatchingRoms(None, self.system_name)
        try_name_data = set([])
        for f_name in name_set:
            r, base_title = mr.run(f_name, is_print_all=False)
            if r:
                try_name_data.add(base_title)          

        for f_name in try_name_data:
            print(f_name)
        print(len(try_name_data))
        
    def after_merge_ra_meta(self):
        file_list = []
        self.get_num = 0
        for file_name in os.listdir(RETROARCH_META_PATH):
            if file_name == self.ra_system_name+".dat":
                file_list.append(RETROARCH_META_PATH+'\\'+file_name)
                break
        
        for file_name in os.listdir(RETROARCH_META_PATH+'\\'+'no-intro'):
            if file_name == self.ra_system_name+".dat":
                file_list.append(RETROARCH_META_PATH+'\\'+'no-intro'+'\\'+file_name)
                break

        for file_name in os.listdir(RETROARCH_META_PATH+'\\'+'redump'):
            if file_name == self.ra_system_name+".dat":
                file_list.append(RETROARCH_META_PATH+'\\'+'redump'+'\\'+file_name)
                break

        for file_name in os.listdir(RETROARCH_META_PATH+'\\'+'tosec'):
            if file_name == self.ra_system_name+".dat":
                file_list.append(RETROARCH_META_PATH+'\\'+'tosec'+'\\'+file_name)
                break
        
        ra_meta_set = {}
        for f_path in file_list:
            fp = open(f_path)
            try:
                data = fp.read()
            except UnicodeDecodeError:
                fp = open(f_path, encoding='utf-8')
                data = fp.read()
            for line in self.ra_parsing(data): #(name, rom_name, rom_size, rom_crc, rom_md5, rom_sha1)
                src_name = line[0]
                rom_name = line[1]
                base_title, sub_title_list, bucket_str_list = normString(src_name)
                if len(sub_title_list) > 0:
                    base_name =  base_title +' - '.join(sub_title_list)           
                else:
                    base_name = base_title

                ra_meta_set.setdefault(base_name, set([])).add(line)

                # ra_meta_set.add(line)
        self.tot_search_num = len(ra_meta_set)
        # ra_meta_set = list(ra_meta_set)
        # random.shuffle(ra_meta_set)
        th_list = []

        while len(ra_meta_set)!=0:

            while True:
                if len(self.run_bucket) <= 10:
                    break

            self.get_num += 1
            (base_name, ra_rom_meta_set) = ra_meta_set.popitem()

            match_data = set([])

            for ra_rom_meta in ra_rom_meta_set:

                ra_src_name = ra_rom_meta[0]
                ra_rom_crc = ra_rom_meta[3]
                if ra_rom_crc != None:
                    ra_rom_crc = ra_rom_crc.lower()
                    if ra_rom_crc in self.crc_to_rom_id:
                        s_rom_id = self.crc_to_rom_id[ra_rom_crc]
                        self.update_src(ra_src_name, s_rom_id)
                        match_data.add(ra_rom_meta)

                    elif ra_rom_crc in self.roms_meta:
                        match_data.add(ra_rom_meta)

            for data in match_data:
                if data in ra_rom_meta_set:
                    ra_rom_meta_set.remove(data)

            for ra_rom_meta in ra_rom_meta_set:
                ra_src_name = ra_rom_meta[0]
                ra_rom_md5 = ra_rom_meta[4]
                if  ra_rom_md5 != None:
                    ra_rom_md5 = ra_rom_md5.lower()
                    if ra_rom_md5 in self.md5_to_rom_id:
                        s_rom_id = self.md5_to_rom_id[ra_rom_md5]
                        self.update_src(ra_src_name, s_rom_id)
                        match_data.add(ra_rom_meta)

            for data in match_data:
                if data in ra_rom_meta_set:
                    ra_rom_meta_set.remove(data)
                
            for ra_rom_meta in ra_rom_meta_set:
                ra_src_name = ra_rom_meta[0]
                ra_file_name = ra_rom_meta[1]
                ra_rom_size = ra_rom_meta[2]
                ra_rom_crc = ra_rom_meta[3]
                if ra_rom_crc != None:
                    ra_rom_crc = ra_rom_crc.lower()
                ra_rom_md5 = ra_rom_meta[4]
                if  ra_rom_md5 != None:
                    ra_rom_md5 = ra_rom_md5.lower()
                ra_rom_sha1 = ra_rom_meta[5]
                if  ra_rom_sha1 != None:
                    ra_rom_sha1 = ra_rom_sha1.lower()

                file_name = ra_src_name
                if file_name in self.pre_read_file:
                    from_rom_id_set = self.pre_read_file[file_name]
                    from_rom_id = random.choice(tuple(from_rom_id_set))
                    from_rom_info = self.roms_meta[from_rom_id]
                    jeu_id = from_rom_info[8]
                    game_name = from_rom_info[9]
                    rom_id = 'ra_'+ra_rom_crc
                    self.roms_meta[rom_id] = (rom_id, file_name, ra_file_name, None, ra_rom_size, ra_rom_crc, ra_rom_md5, ra_rom_sha1, jeu_id, game_name, from_rom_info[10], from_rom_info[11], from_rom_info[12], from_rom_info[13], from_rom_info[14], from_rom_info[15], from_rom_info[16])
                    print(self.get_num, '/', self.tot_search_num, '('+str(self.api_call_num)+')', len(self.run_bucket))
                    match_data.add(ra_rom_meta)

                else:
                    mr = mix_ratio(file_name, tuple(self.pre_read_file.keys()))
                    if mr[1] >= 94:
                        print('no call api :',file_name, mr[0])
                        s_rom_list = list(self.pre_read_file[mr[0]])
                        for s_rom in s_rom_list:
                            self.update_src(file_name, s_rom)
                        from_rom_info = self.roms_meta[s_rom_list[0]]
                        jeu_id = from_rom_info[8]
                        game_name = from_rom_info[9]
                        rom_id = 'ra_'+ra_rom_crc
                        self.roms_meta[rom_id] = (rom_id, file_name, ra_file_name, None, ra_rom_size, ra_rom_crc, ra_rom_md5, ra_rom_sha1, jeu_id, game_name, from_rom_info[10], from_rom_info[11], from_rom_info[12], from_rom_info[13], from_rom_info[14], from_rom_info[15], from_rom_info[16])
                        print(self.get_num, '/', self.tot_search_num, '('+str(self.api_call_num)+')', len(self.run_bucket))
                        match_data.add(ra_rom_meta)

            for data in match_data:
                if data in ra_rom_meta_set:
                    ra_rom_meta_set.remove(data)
                
            for ra_rom_meta in ra_rom_meta_set:
                ra_src_name = ra_rom_meta[0]
                ra_file_name = ra_rom_meta[1]
                ra_rom_size = ra_rom_meta[2]
                ra_rom_crc = ra_rom_meta[3]
                if ra_rom_crc != None:
                    ra_rom_crc = ra_rom_crc.lower()
                ra_rom_md5 = ra_rom_meta[4]
                if  ra_rom_md5 != None:
                    ra_rom_md5 = ra_rom_md5.lower()
                ra_rom_sha1 = ra_rom_meta[5]
                if  ra_rom_sha1 != None:
                    ra_rom_sha1 = ra_rom_sha1.lower()

                file_name = ra_src_name

                if file_name in self.rom_name_set:
                    s_rom_list = list(self.rom_name_set[file_name])
                    for s_rom in s_rom_list:
                        self.update_src(file_name, s_rom)
                    from_rom_info = self.roms_meta[s_rom_list[0]]
                    jeu_id = from_rom_info[8]
                    game_name = from_rom_info[9]
                    rom_id = 'ra_'+ra_rom_crc
                    self.roms_meta[rom_id] = (rom_id, file_name, ra_file_name, None, ra_rom_size, ra_rom_crc, ra_rom_md5, ra_rom_sha1, jeu_id, game_name, from_rom_info[10], from_rom_info[11], from_rom_info[12], from_rom_info[13], from_rom_info[14], from_rom_info[15], from_rom_info[16])
                    print(self.get_num, '/', self.tot_search_num, '('+str(self.api_call_num)+')', len(self.run_bucket))
                    match_data.add(ra_rom_meta)
                else:
                    
                    mr = mix_ratio(file_name, tuple(self.rom_name_set.keys()))
                    if mr[1] >= 94:
                        print('no call api :',file_name, mr[0])
                        s_rom_list = list(self.rom_name_set[mr[0]])
                        for s_rom in s_rom_list:
                            self.update_src(file_name, s_rom)
                        from_rom_info = self.roms_meta[s_rom_list[0]]
                        jeu_id = from_rom_info[8]
                        game_name = from_rom_info[9]
                        rom_id = 'ra_'+ra_rom_crc
                        self.roms_meta[rom_id] = (rom_id, file_name, ra_file_name, None, ra_rom_size, ra_rom_crc, ra_rom_md5, ra_rom_sha1, jeu_id, game_name, from_rom_info[10], from_rom_info[11], from_rom_info[12], from_rom_info[13], from_rom_info[14], from_rom_info[15], from_rom_info[16])
                        print(self.get_num, '/', self.tot_search_num, '('+str(self.api_call_num)+')', len(self.run_bucket))
                        match_data.add(ra_rom_meta)

            if len(match_data) > 0 :
                continue

            for data in match_data:
                if data in ra_rom_meta_set:
                    ra_rom_meta_set.remove(data)


            self.run_bucket.add(base_name)        
            self.api_call_num += 1
            t1 = Thread(target=self.call_api, args=(base_name, ra_rom_meta_set))
            t1.start()            
            th_list.append(t1)
    
            print(self.get_num, '/', self.tot_search_num, '('+str(self.api_call_num)+')', len(self.run_bucket))
            
        for th in th_list:
            th.join()

        print('process join')
        self.insertTable()


    def addTentacleMetaAndFillName(self):
        cur = self.con.cursor()
        tb_name = 'roms_'+self.system_name
        xml_file_path = TENTACLE_ROM_META_PATH+'/'+self.system_name+'.xml'
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        result = {}
        for child in root.findall('game'):
            path = child.find('path').text
            path = path[2:-4]
            title = child.find('name').text
            cur.execute(f'UPDATE {tb_name} SET filename_kor = "{title}" WHERE filename LIKE "%{path}.%"')
        self.con.commit()



def test2():

    pattern = 'game\s*\(([^()]*(?:\([^\)]*\)[^()]*)*)\)'

    name_pattern = 'name\s+"([^"]*)"\n'
    rom_pattern = 'rom\s*\(([^()]*(?:\([^\)]*\)[^()]*)*)\)'
    rom_name_pattern = 'name\s+"([^"]*)"'
    rom_size_pattern = 'size\s+([^\s]*)\s'
    rom_crc_pattern = 'crc\s+([^\s]*)\s'
    rom_md5_pattern = 'md5\s+([^\s]*)\s'
    rom_sha1_pattern = 'sha1\s+([^\s]*)\s'

    data_list = []
    result = re.findall(pattern, a)
    for line1 in result:
        name = re.findall(name_pattern, line1)[0]
        rom_str = re.findall(rom_pattern, line1)[0]
        rom_name = re.findall(rom_name_pattern, rom_str)[0]
        rom_size = re.findall(rom_size_pattern, rom_str)
        if rom_size == []:
            rom_size = None
        else:
            rom_size = rom_size[0]        
        rom_crc = re.findall(rom_crc_pattern, rom_str)
        if rom_crc == []:
            rom_crc = None
        else:
            rom_crc = rom_crc[0]

        rom_md5 = re.findall(rom_md5_pattern, rom_str)
        if rom_md5 == []:
            rom_md5 = None
        else:
            rom_md5 = rom_md5[0]

        rom_sha1 = re.findall(rom_sha1_pattern, rom_str)
        if rom_sha1 == []:
            rom_sha1 = None
        else:
            rom_sha1 = rom_sha1[0]        

        print(name, rom_name, rom_size, rom_crc, rom_md5, rom_sha1)
    

def test():
    system_name = 'famicom'
    ss= SSRomsMeta(system_name)
    # ss.makeDBTable()
    # ss.after_merge_ra_meta()
    # ss.check_data()
    ss.addTentacleMetaAndFillName()


if __name__ == "__main__":
    # t = 'Ninja Remix (Europe)[aa] '
    # print(removeBucket(t))
    test()