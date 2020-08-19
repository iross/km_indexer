# KM Indexer

This workflow aims to convert MEDLINE/PubMed citation records into an indexed,
text-searchable Elasticsearch database. This can be done on a subset of the
available data, for search logic testing within the context of a KinderMiner
application.

It can be run on the annual baseline files and/or the MEDLINE-provided daily
updates, by providing either the `bulk` or `update` argument when invoking the 
`index_pubmed.py` script.

The indexed Elasticsearch data is persisted by storing the data in a local
directory mounted into the running image.

Port `9200` on the local host is forwarded to the running Elasticsearch image.

Documents use the PMID as the `_id` primary key.


## Usage
Basic usage requires [docker](https://www.docker.com) and [docker compose](https://docs.docker.com/compose/). Create a local directory for
the Elasticsearch data and run + build the docker images:

```
mkdir es_data
# If you want to use abbreviation expansion, then you'll also need to mkdir allie_data as well
docker-compose up --build
```
Now you can run ES queries against on the host machine: `curl -X GET http://localhost:9200/pubmed_abstracts/_count`

### 'bulk' option
Running the `index_pubmed.py` script with the `bulk` option will download + index
the dumps provided in the MEDLINE Annual Baseline
(`https://www.nlm.nih.gov/databases/download/pubmed_medline.html`)
There are two optional parameters, `n_min` and `n_max`, which are the minimum
and maximum file number to process. By default, only the first file is fetched
and processed.

### Update files
It is also possible to ingest the daily update files provided by MEDLINE
(`ftp://ftp.ncbi.nlm.nih.gov/pubmed/updatefiles/`). **BY DEFAULT, ALL UPDATE
FILES WILL BE APPLIED IN THIS MODE**

## Abbreviation expansion
Abberviation expansion is done via the ALLIE (http://allie.dbcls.jp) database.
By default, abbrevations are kept as-is from PubMed, but by changing the setting in `.env`
to 

```
EXPAND_ABBREVIATIONS=1
```

The ALLIE database will be downloaded and installed into a postgres table. As the PubMed abstracts are ingested, this database is queried and any abbreviations found within the abstract are replaced with the long form, and the result is stored within the `abstract_long_form` field.

Which version has been downloaded is tracked in the postgres database. The latest version will be installed if it is detected that it is newer than what is stored locally.

## Notes
- The intended use is for testing of query logic, and the JVM options set for
  Elasticsearch are set with this in mind.
- There is rudimentary checkpointing applied when running in the update files
  mode, but is non-persistent across image restarts. This means that if you
  need to restart the image, the data within Elasticsearch will still be there,
  but the update files will all be redownloaded and updated.
- `docker-compose up --build` will bring up both the required backend services (Elasticsearch and postgres), along with the ingestion script.
  - It is possible to selectively bring up service by providing their name (`es01`, `postgres`, or `ingest_elastic`). For example, if you've already ingested data and are only interested in querying Elasticsearch, `docker-compose up es01` will bring up only the Elasticsearch services.
  - Full documentation of the docker-compose command is [here](https://docs.docker.com/compose/reference/overview/).

