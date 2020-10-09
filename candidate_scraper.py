import os
import requests
import re
import json
import csv
from bs4 import BeautifulSoup

def get_parsed_html(url):
    try:
        page = requests.get(url)
        return BeautifulSoup(page.content,'html.parser')
    except:
        print('Unable to connect to {}'.format(url))
        return BeatifulSoup('','html.parser')

def cleanup_url(url):
    #remove location tags
    url =   url.split('#')[0]
    #remove query parameters
    url = url.split('?')[0]
    return url.strip('/')

def get_state_elections_info():
    # Parses the Ballotpedia page for all state legislature elections to get pages for individual states
    # Runs instances of CandidateTable for each state legislature
    # Outputs list of ordered pairs:(url, state)

    ballotpedia_page = 'https://ballotpedia.org/State_legislative_elections,_2020'
    states = ["Alabama","Alaska","Arizona","Arkansas","California","Colorado",
              "Connecticut","Delaware","Florida","Georgia","Hawaii","Idaho","Illinois",
              "Indiana","Iowa","Kansas","Kentucky","Louisiana","Maine","Maryland",
              "Massachusetts","Michigan","Minnesota","Mississippi","Missouri","Montana",
              "Nebraska","Nevada","New Hampshire","New Jersey","New Mexico","New York",
              "North Carolina","North Dakota","Ohio","Oklahoma","Oregon","Pennsylvania",
              "Rhode Island","South Carolina","South Dakota","Tennessee","Texas","Utah",
              "Vermont","Virginia","Washington","West Virginia","Wisconsin","Wyoming"]

    html = get_parsed_html(ballotpedia_page)
    state_elections_info = set()
    for state in states:
        tags = html.find_all('a',href=re.compile('{}.*elections,_2020'.format(state)))
        links = [requests.compat.urljoin(ballotpedia_page,tag.attrs['href']) for tag in tags]
        for link in links:
            link = cleanup_url(link)
            state_elections_info.add((link,state))
    return state_elections_info

class CandidateTable:
    # Finds candidate table from a Ballotpedia page.
    # Extracts candidate and candidate Ballotpedia page from table.
    # Saves candidate details into a json file with file_name extracted from Ballotpedia page url.

    def __init__(self,url,state,overwrite=False):
        self.ballotpedia_page = url
        self.state = state
        self.party = 'Democratic'
        self.overwrite = overwrite
        self.output_dicts = []

        html = get_parsed_html(self.ballotpedia_page)

        self.election, self.file_name = self.get_election_and_file_name()
        if self.overwrite and not os.path.isfile(self.file_name):
            print('Skipping. File {} already found'.format(self.file_name))
            return
        self.primary_date = self.get_primary_date()
        if self.get_table():
            self.party_index = self.get_party_index()
            self.district_rows = self.get_district_rows()
            for district_row in self.district_rows:
                self.add_candidates_from_row(district_row)
        else:
            print('Candidate table not found')

    def get_election_and_file_name(self):
        #Assumes ballotpedia url format  '../{state}_{legislature}_elections,_2020'
        page = self.ballotpedia_page.split('/')[-1]
        election = page.split('_')[:-2]
        election = ' '.join(election)
        file_name = 'candidates_{}.json'.format('_'.join(election))
        return election, file_name

    def get_primary_date(self):
        tag = self.html.find('b',string='Primary')
        date = tag.find_next('a',title='State legislative elections, 2020').string
        if date:
            return date
        else:
            return ''

    def get_table(self):
        tables = self.html.find_all(class_="wikitable sortable collapsible jquery-tablesorter candidateListTablePartisan")
        #check correct table is found
        for table in tables:
            if table.find('td',string=re.compile('{}.*primary'.format(self.state),re.IGNORECASE)):
                self.table = table
                return True

        return False

    def get_party_index(self):
        party_row = self.table.find('td',string=re.compile('Democrat')).parent
        for ind, entry in enumerate(party_row.find_all('td')):
            if entry.find(string=re.compile('Democrat')):
                break
        return ind

    def get_district_rows(self):
        district_rows = []
        for district in self.table.find_all('td',string=re.compile('District*')):
            district_rows.append(district.parent)
        return district_rows

    def add_candidates_from_row(self,district_row):
        # Assumes all candidates are hyperlinked to a ballotpedia page
        entries = district_row.find_all('td')
        district = entries[0].string
        party_entry = entries[self.party_index]
        for link in party_entry.find_all('a'):
            ballotpedia_page = link.attrs['href']
            name = link.string
            incumbent_bool = self.get_incumbent_bool(link)
            candidate = Candidate(name,ballotpedia_page,incumbent_bool,district,self.election,self.primary_date)
            self.output(candidate)
            print(candidate.to_dict())

    def get_incumbent_bool(self,link):
        # Searches for '(i)' in next element. If present, candidate is an incumbent
        next_elem_generator = link.next_elements
        next(next_elem_generator)
        elem = next(next_elem_generator)
        if elem.string:
            return bool(re.search('\(i\)',elem.string))
        else:
            return False

    def output(self,candidate):
        if candidate.keyword_dict:
            self.output_dicts.append(candidate.to_dict())
            with open(self.file_name,'w') as file:
                json.dump(self.output_dicts,file,indent=4)


class Candidate:
    # Collects info for a candidate
    # Gets websites from candidate Ballotpedia page
    # Runs instance of WebSearcher

    def __init__(self,name,ballotpedia_page,incumbent_bool,district,election,primary_date):
        self.name = name
        self.ballotpedia_page = ballotpedia_page
        self.incumbent_bool = incumbent_bool
        self.district = district
        self.election = election
        self.primary_date = primary_date

        self.keyword_dict = defaultdict(list)
        self.searched_websites = []

        self.search_urls()

    def search_urls(self):
        self.urls, self.url_types = self.get_website_urls()
        for url, url_type in zip(self.urls,self.url_types):
            if re.search('website', url_type, re.IGNORECASE):
                self.searched_websites.append(url)
                web_searcher = WebsiteSearcher(url,self.keyword_dict)
                self.keyword_dict = web_searcher.keyword_dict

    def get_website_urls(self):
        url = self.ballotpedia_page
        html = get_parsed_html(url)
        contact_div = soup.find('div', string= 'Contact')
        if contact_div:
            divs = contact_div.find_all_next('div',class_='widget-row value-only white')
            links = [div.find('a') for div in divs]
            urls = [link.attrs['href'] for link in links]
            url_types = [link.string for link in links]
            return urls, url_types
        else:
            return [], []

    def to_dict(self):
        out_dict = {'name':self.name, 'is_incumbent':self.incumbent_bool,
                   'district':self.district, 'election': self.election, 'primary_date': self.primary_date,
                   'websites':self.searched_websites, 'keyword_dict':self.keyword_dict, 'ballotpedia':self.ballotpedia_page}
        return out_dict


class WebsiteSearcher:
    # Scrapes websites and sub-websites (with same start as input url) and searches for keywords in regex_dict.
    # For each keyword hit on a webpage, it adds that webpage to the keyword's list

    regex_dict = {'DSA': re.compile('democratic socialis[t,m]',re.IGNORECASE),
                  'GND':re.compile('Green New Deal',re.IGNORECASE),
                  'M4A':re.compile('Medicare.For.All', re.IGNORECASE),
                  'single-payer':re.compile('single.payer',re.IGNORECASE),
                  'Bernie':re.compile('Bernie Sanders'),
                  'AOC':re.compile('Ocasio.Cortez'),
                  'sunrise':re.compile('sunrise movement',re.IGNORECASE),
                  'our revolution':re.compile('Our Revolution'),
                  'Mod_Security':re.compile(r'Mod\_Security'),
                  }

    max_number_searched = 100  #max number of pages searched for each domain.

    def __init__(self,url,keyword_dict):
        url = url.strip('/')
        self.init_url = url
        self.keyword_dict = keyword_dict

        self.unsearched_urls = {url}
        self.searched_urls = set()
        self.number_searched = 0 #counts number of pages searched.

        while self.unsearched_urls and self.number_searched < self.max_number_searched:
            self.search_page()
            print(list(self.keyword_dict.keys()))

    def compare_url_to_init(self,url):
        init_url = self.init_url.split('/')
        url_start = url.split('/')[:len(init_url)]
        return '/'.join(url_start) == '/'.join(init_url):

    def search_page(self):
        url = self.unsearched_urls.pop(0)
        print(url)
        self.searched_urls.append(url)
        self.number_searched += 1

        html = get_parsed_html(url)

        self.scan_for_hits(html,url)
        links = self.scan_for_links(html,url)
        self.add_links_to_unsearched(links)

    def scan_for_hits(self,html,url):
        regex_dict = self.regex_dict
        for keyword in list(regex_dict.keys()):
            rgx = regex_dict[keyword]
            match = html.find(string=rgx)
            if match:
                new_list = self.keyword_dict[keyword] + [url]
                self.keyword_dict[keyword] = new_list

    def scan_for_links(self,html,url):
        link_tags = html.find_all('a')
        links = set()
        for tag in link_tags:
            href = tag.attrs.get('href',None)
            if href is None:
                continue
            else:
                if html.find('base'):  #search for base url for relative paths
                    base = html.find('base').attrs.get('href','')
                    if len(base)==0:
                        base = url
                else:
                    base = url
                try:
                    link = requests.compat.urljoin(base,href) #join relative path. If href full path, then outputs href
                except:
                    link = href
                link = cleanup_url(link)
                if self.compare_url_to_init(link):
                    links.add(link)
        return links

    def add_links_to_unsearched(self,links):
        for link in links:
            if link not in self.searched_urls:
                self.unsearched_urls.add(link)


class CandidateScorer:
    # Adds scores to output jsons

    score_dict = {'DSA': 3,
                  'GND':10,
                  'M4A':10,
                  'single-payer':10,
                  'Bernie':3,
                  'socialist':6,
                  'socialism':6,
                  'progressive':1,
                  'sunrise':10,
                  'our revolution':10,
                  'Mod_Security':-1
                  }

    def __init__(self,file_names):
        for file_name in file_names:
            with open(file_name,'r') as file:
                self.candidates_list = json.load(file)

            self.score_candidates_and_sort()
            self.output_json(file_name)

    def score_candidates_and_sort(self):
        candidates_list = self.candidates_list
        score_list = []
        for candidate_dict in candidates_list:
            score = self.get_score(candidate_dict['keyword_dict'])
            score_list.append(score)
            candidate_dict['score'] = score

        self.sorted_candidates_list = sorted(candidates_list,key=lambda x:x['score'])[::-1]

    def get_score(self,keyword_dict):
        score = sum([self.score_dict[keyword] for keyword in keyword_dict.keys()])
        return score

    def output_json(self,file_name):
        with open(file_name,'w') as file:
            json.dump(self.sorted_candidates_list,file, indent=4)


class AllCandidatesToCSV:
    #Gathers candidates from file_names. Combines, sorts, and outputs to json and csv.
    def __init__(self,file_names,output_file_prefix):
        self.candidates_list = []
        self.output_file_prefix = output_file_prefix
        for file_name in file_names:
            if file_name.strip('.json')==output_file_prefix:
                continue
            with open(file_name,'r') as file:
                self.candidates_list.extend(json.load(file))

        self.sort_candidates()
        self.output_to_json()
        self.output_to_csv()

    def sort_candidates(self):
        self.candidates_list.sort(key=lambda x: x['score'],reverse=True)

    def output_to_json(self):
        with open(self.output_file_prefix+'.json','w') as file:
            json.dump(self.candidates_list,file,indent=4)

    def output_to_csv(self):
        with open(self.output_file_prefix+'.csv','w') as file:
            fieldnames = ['name','score','keywords','election','district',
                          'primary_date','incumbent','ballotpedia','websites']
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            writer.writeheader()
            for candidate_dict in self.candidates_list:
                row_dict = self.get_candidate_csv_row(candidate_dict)
                writer.writerow(row_dict)

    def get_candidate_csv_row(self,candidate_dict):
        row_dict = {}
        row_dict['name'] = candidate_dict.get('name','')
        row_dict['score'] = candidate_dict.get('score','')
        row_dict['election'] = candidate_dict.get('election','')
        row_dict['district'] = candidate_dict.get('district','')
        row_dict['primary_date'] = candidate_dict.get('primary_date','')
        row_dict['incumbent'] = candidate_dict.get('is_incumbent')
        row_dict['ballotpedia'] = candidate_dict.get('ballotpedia','')
        row_dict['websites'] = '\n'.join(candidate_dict.get('websites',''))
        keyword_list =  list(candidate_dict.get('keyword_dict',{}).keys())
        row_dict['keywords'] = '\n'.join(keyword_list)
        return row_dict
