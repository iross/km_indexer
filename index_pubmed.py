from urllib.request import urlretrieve
import datetime
from dateutil.parser import parse
import sys, os, io
import subprocess
import argparse
from elasticsearch import Elasticsearch, helpers
from xml.etree import ElementTree as ET
import glob
import re
import time
import ftplib
import psycopg2
import psycopg2.extras
import urllib.request as urllib
import pickle

EXPAND_ABBREVIATIONS = True if os.environ['EXPAND_ABBREVIATIONS'] == '1' else False

es = Elasticsearch(['es01:9200'])

def parse_cover_date(coverDate):
    """
    Attempt to parse a cover date string into a datetime object. This uses
    the dateutil parser, in order to try and match any date formats.
    Args:
        coverDate (str): Cover date (in string format) of a publication.
    Returns: publication_date (dict): {"month" : xx, "year":  yyyy}
    """
    year_pattern = re.compile("\d{4}")
    coverDate = coverDate.replace("Available on ", "").replace("Available online ", "")
    if coverDate == "":
        return None
    try:
        parsed = parse(coverDate, default=None)
    except (ValueError, TypeError): # couldn't parse date -- maybe it's "February-March xxxx"
        try:
            parsed = parse(coverDate.split(u'\u2013')[-1], default=None)
        except (ValueError, TypeError): # still couldn't parse date -- look for a year
            year = year_pattern.search(coverDate)
            if year is not None:
                parsed = datetime.datetime(int(year.group(0)), 1, 1)
            else:
                return None
    # ensure that
    publication_date = {}
    publication_date["year"] = parsed.year
    # check to make sure that the month looks like it was in the original string and wasn't a default from the parser.
    month = datetime.datetime.strftime(datetime.datetime(1900, parsed.month, 1), "%b") # set fake date so that pre-20th century articles don't break strftime
    # also check the case that the coverdate is in %m format (e.g. 06 instead of June)
    month_m = datetime.datetime.strftime(datetime.datetime(1900, parsed.month, 1), "%m") # set fake date so that pre-20th century articles don't break strftime
    if month.lower() in coverDate.lower() or month_m in coverDate:
        publication_date["month"] = parsed.month
        #else there's no month in the coverdate string, so don't set it.

    return publication_date

def update_mapping(index_name, type_name):
       """
       Define the ES mappings.

       NOTE: ES will set these automatically when a document is indexed, so we
       only need to define custom fields OR fields we want to strictly type.

       """
       mapping = {
                   "properties": {
                       "abstract": {
                           "type": "text",
                           "fields": {
                               "english": {
                                   "type": "text",
                                   "analyzer": "english"
                                   }
                               },
                           "copy_to": [
                               "abstract_and_title"
                               ]
                           },
                       "abstract_and_title": {
                           "type": "text",
                           "fields": {
                               "english": {
                                   "type": "text",
                                   "analyzer": "english"
                                   }
                               }
                           },
                       "abstract_long_form": {
                           "type": "text",
                           "fields": {
                               "english": {
                                   "type": "text",
                                   "analyzer": "english"
                                   }
                               }
                           },
                       "chemicalname": {
                           "type": "text"
                           },
                       "chemicalui": {
                           "type": "text"
                           },
                       "content_url": {
                           "type": "text"
                           },
                       "coverDate": {
                               "type": "text",
                               },
                       "coverdate": {
                               "type": "alias",
                               "path" : "coverDate"
                               },
                       "issue": {
                           "type": "text"
                           },
                       "meshdescriptorname": {
                           "type": "text"
                           },
                       "meshdescriptorui": {
                           "type": "text"
                           },
                       "meshqualifiername": {
                           "type": "text"
                           },
                       "meshqualifierui": {
                               "type": "text"
                               },
                       "PMID" : {
                               "type" : "text"
                               },
                       "pmid": {
                               "type": "alias",
                               "path" : "PMID"
                               },
                       "publication_date": {
                               "properties": {
                                   "month": {
                                       "type": "long"
                                       },
                                   "year": {
                                       "type": "long"
                                       }
                                   }
                               },
                       "time": {
                               "type": "date",
                               "format": "strict_date_optional_time||epoch_millis"
                               },
                       "title": {
                               "type": "text",
                               "copy_to": [
                                   "abstract_and_title"
                                   ]
                               },
                       "vol": {
                               "type": "text"
                               }
                       }
       }
       es.indices.close(index=index_name)
       es.indices.put_mapping(body=mapping, index=index_name, timeout="30s")
       es.indices.open(index=index_name)
       return 0

class Helper():
    def __init__(self):
        self.conn = psycopg2.connect("dbname=%s user=%s password=%s host=%s port=%s" % \
                    ("kinderminer", "kinderminer", "supersecretpassword", "km_postgres", "5432"))
        self.cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def get_metadata_from_xml(self, filepath):
        """
        """
        metadata = {}

        parser = ET.iterparse(filepath)

        for event, element in parser:
            # element is a whole element
            if element.tag == 'PubmedArticle':
                temp = {}

                for _id in element.findall('./PubmedData/ArticleIdList/ArticleId'):
                    if _id.attrib['IdType'] == "pubmed":
                        temp['PMID'] = _id.text
                    elif _id.attrib['IdType'] == "doi":
                        temp["doi"] = _id.text

                title = element.findall('.//ArticleTitle')
                if len(title) > 0: temp['title'] = title[0].text

                abstract = element.findall('.//AbstractText')
                temp['abstract'] = "\n".join(i.text if i.text is not None else "" for i in abstract)
                try:
                    authors = []
                    for author in element.findall('.//Author'):
                        author_str = ""
                        if author.find("LastName") is not None:
                            author_str += "%s" % author.find("LastName").text
                        if author.find("ForeName") is not None:
                            author_str += ', %s' % author.find("ForeName").text
                        authors.append(author_str)
                    temp["authors"] = "; ".join(i for i in authors)
                except:
                    print("Exception!")
                    print(sys.exc_info())
                    continue

                temp["meshDescriptorUI"] = []
                temp["meshDescriptorName"] = []
                temp["meshQualifierUI"] = []
                temp["meshQualifierName"] = []
                for mesh in element.findall('.//MeshHeading'):
                    dmesh = mesh.find("DescriptorName")
                    ui = dmesh.attrib['UI'] if "UI" in dmesh.attrib else None
                    temp["meshDescriptorUI"].append(ui)
                    temp["meshDescriptorName"].append(dmesh.text)
                    qualifierUIs = []
                    qualifierNames = []
                    for qmesh in mesh.findall("QualifierName"):
                        qualifierUIs.append(qmesh.attrib['UI'] if "UI" in dmesh.attrib else None)
                        qualifierNames.append(qmesh.text)
                    temp["meshQualifierUI"].append(';'.join(qualifierUIs))
                    temp["meshQualifierName"].append(';'.join(qualifierNames))


                temp["chemicalUI"] = []
                temp["chemicalName"] = []
                for chem in element.findall('.//Chemical'):
                    chem = chem.find("NameOfSubstance")
                    ui = chem.attrib['UI'] if "UI" in chem.attrib else None
                    temp["chemicalUI"].append(ui)
                    temp["chemicalName"].append(chem.text)

                temp["publicationTypeUI"] = []
                temp["publicationType"] = []
                for pubtype in element.findall('.//PublicationType'):
                    ui = pubtype.attrib['UI'] if "UI" in pubtype.attrib else None
                    temp["publicationTypeUI"].append(ui)
                    temp["publicationType"].append(pubtype.text)

                jinfo = element.find(".//JournalIssue")
                try:
                    temp['vol'] = jinfo.find("Volume").text
                except: pass
                try:
                    temp['issue'] = jinfo.find("Issue").text
                except: pass


                coverDate = ""
                try:
                    coverDate += jinfo.find("PubDate").find("Month").text
                except: pass
                try:
                    coverDate += " " + jinfo.find("PubDate").find("Year").text
                except: pass
                if coverDate == "":
                    coverDate = jinfo.find("PubDate").find("MedlineDate").text
                temp["coverDate"] = coverDate
                temp["publication_date"] = parse_cover_date(temp["coverDate"])

                try:
                    pagerange = element.find(".//MedlinePgn").text
                    pagerange = pagerange.split(",")[0]
                    if "-" in pagerange:
                        startPage, endPage = pagerange.split("-")
                        if len(str(endPage)) < len(str(startPage)):
                            length_diff = len(str(startPage)) - len(str(endPage))
                            endPage = str(startPage)[:length_diff] + str(endPage)
                    else:
                        startPage, endPage = [pagerange]*2
                except:
                    startPage, endPage = [""]*2
                temp["startingPage"] = startPage
                temp["endingPage"] = endPage

                try:
                    temp["pubname"] = element.find(".//Journal/Title").text
                except: pass

                temp["metadata_update"] = datetime.datetime.now()

                if EXPAND_ABBREVIATIONS:
                    self.cur.execute("SELECT DISTINCT(short_form, long_form), short_form, long_form FROM alice_abbreviations WHERE pubmed_id=%(pmid)s",
                            {"pmid" : temp["PMID"]})
                    for abbr in self.cur:
                        temp["abstract_long_form"] = temp["abstract"].replace(abbr['short_form'], abbr['long_form'])

                temp['time'] = [datetime.datetime.now()]

                element.clear()
                metadata[temp["PMID"]] = temp
        return metadata


    def store_targets(self):
        """
        Stores the articles currently in the queue to the 'fetchables' table in the fetching database.

        Returns: 0 if successful.
        """

        try:
            actions = []
            while len(self.queue) > 0:
                URL, doc = self.queue.popitem()
                actions.append({
                    '_id' : doc['PMID'],
                    '_index' : 'pubmed_abstracts',
                    '_source': doc
                    })
                if len(actions) == 1000:
                    helpers.bulk(es, actions)
                    actions = []
            helpers.bulk(es, actions)
            return 0
        except:
            print("Error in writing documents to Elasticsearch")
            print(sys.exc_info())
            return 1

    def bulk(self, min_n = 1, max_n = 1):
        """
        """
        conn = psycopg2.connect("dbname=%s user=%s password=%s host=%s port=%s" % \
                    ("kinderminer", "kinderminer", "supersecretpassword", "km_postgres", "5432"))
        cur = conn.cursor()

        print(f"Indexing annual dump files {min_n} to {max_n}.")
        for n in range(min_n, max_n + 1):
            target_file = "pubmed20n%04d.xml.gz" % n
            cur.execute("SELECT 1 FROM pubmed_ingested WHERE filename=%(target_file)s;", {"target_file" : target_file})
            check = cur.fetchone()
            if check is not None:
                print(f"Already ingested {target_file}! Skipping.")
                continue
            print(f"Getting {target_file}")
            urlretrieve('ftp://ftp.ncbi.nlm.nih.gov/pubmed/baseline/%s' % target_file, target_file)
            subprocess.call(["gunzip", target_file])
            self.queue = self.get_metadata_from_xml(target_file.replace(".gz", ""))
            self.store_targets()
            subprocess.call(["rm", target_file.replace(".gz", "")])
            cur.execute("INSERT INTO pubmed_ingested (filename) VALUES (%(target_file)s)", {"target_file": target_file})
            conn.commit()

    def update(self):
        """
        ...

        TODO: The checkpointing here is not useful when running inside a transient docker container.
        """
        # get daily updates
        if os.path.exists("pubmed_updates_applied.p"):
            updates_applied = pickle.load(open("pubmed_updates_applied.p"))
        else:
            updates_applied = set()
        ftp = ftplib.FTP("ftp.ncbi.nlm.nih.gov")
        ftp.login()
        ftp.cwd('pubmed')
        ftp.cwd('updatefiles')
        temp = ftp.nlst()
        update_files = set([i for i in temp if i.endswith("xml.gz")])
        for update_file in update_files - updates_applied:
            self.log.info("Working on update file %s" % update_file)
            urllib.urlretrieve('ftp://ftp.ncbi.nlm.nih.gov/pubmed/updatefiles/%s' % update_file, update_file)
            subprocess.call(["gunzip", update_file])
            self.queue = self.get_metadata_from_xml(update_file.replace(".gz", ""))
            self.store_targets()
            subprocess.call(["rm", update_file.replace(".gz", "")])
            updates_applied.add(update_file)
            pickle.dump(updates_applied, open("pubmed_updates_applied.p", "w"))

def download_allie():
    psql_fetching_conn = psycopg2.connect("dbname=%s user=%s password=%s host=%s port=%s" % \
                ("kinderminer", "kinderminer", "supersecretpassword", "km_postgres", "5432"))
    cur = psql_fetching_conn.cursor()

    cur.execute("SELECT md5 FROM alice_versions ORDER BY id DESC;")
    try:
        stored_ver = cur.fetchone()[0]
    except:
        stored_ver = None

    update_md5 = 'alice_output_latest.md5'
    latest_md5, latest_filename = io.BytesIO(urllib.urlopen('ftp://ftp.dbcls.jp/allie/alice_output/%s' % update_md5).read()).read().split()
    latest_md5 = latest_md5.decode('utf-8')
    latest_filename = latest_filename.decode('utf-8')

    if latest_md5 == stored_ver:
        print("Latest ALLIE abbreviations already loaded! Skipping.")
        return 0
    else:
        print(f"Downloading ALLIE abbreviation expansion database ({latest_filename})...")

    urllib.urlretrieve('ftp://ftp.dbcls.jp/allie/alice_output/%s' % latest_filename, latest_filename)
    print("Abbreviations file downloaded. Unzipping and splitting into chunks...")
    try:
        gunzip = subprocess.Popen(["gunzip", '-c',  latest_filename], stdout=subprocess.PIPE)
        split = subprocess.Popen(['split', '-l', '1000000', '-', 'allie_'], stdin=gunzip.stdout)
        gunzip.stdout.close()
        _, _ = split.communicate()
    except:
        print("Unzipping failed!")
        sys.exit(1)
    n_inserted = 0
    to_insert = glob.glob("allie_*")
    print("Copying abbreviations into database.")
    for abbrev_file in to_insert:
        subprocess.call(["sed", "s/\\\\/\\\\\\\\/g", "-i", abbrev_file])

        try:
            with open(abbrev_file) as fin:
                cur.copy_from(fin, "alice_abbreviations")
                psql_fetching_conn.commit()
            subprocess.call(["rm", abbrev_file])
            n_inserted+=1
            print(f"Copied {n_inserted} of {len(to_insert)} abbreviation files into database...")
        except:
            print("Error copying %s" % abbrev_file)
            print(sys.exc_info())
            psql_fetching_conn.commit()
            subprocess.call(["rm", abbrev_file])
    cur.execute("INSERT INTO alice_versions (md5, filename) VALUES (%s, %s)", (latest_md5, latest_filename))
    psql_fetching_conn.commit()
    return 0

def main():
    parser = argparse.ArgumentParser(
        description="Utility for indexing PubMed abstracts into Elasticsearch to make them full-text searchable."
        )
    parser.add_argument('operation', default='bulk', type=str, help='Operation to perform -- either "bulk" (for bulk ingest of annual dump) or "update" to process all daily updates.')
    parser.add_argument('--n_min', default=1, type=int, help='Minimum file number to process.')
    parser.add_argument('--n_max', default=1, type=int, help='Maximum file number to process.')

    if EXPAND_ABBREVIATIONS:
        download_allie()

    if not es.indices.exists("pubmed_abstracts"):
        es.indices.create("pubmed_abstracts")
        print("Waiting for ok status...")
        es.cluster.health(wait_for_status="yellow")
        update_mapping("pubmed_abstracts", "abstract")
    downloads = Helper()
    downloads.es = es
    arguments = parser.parse_args()
    if arguments.operation == 'bulk':
        downloads.bulk(arguments.n_min, arguments.n_max)
    elif arguments.operation == 'update':
        downloads.update()
    else:
        print("Invalid operation specified!")
        sys.exit(1)
#
if __name__ == '__main__':
    main()
