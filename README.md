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
Basic usage requires docker and docker compose. Create a local directory for
the Elasticsearch data and run + build the docker images:

```
mkdir es_data
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

## Caveats
- The intended use is for testing of query logic, and the JVM options set for
  Elasticsearch are set with this in mind.
- There is rudimentary checkpointing applied when running in the update files
  mode, but is non-persistent across image restarts. This means that if you
  need to restart the image, the data within Elasticsearch will still be there,
  but the update files will all be redownloaded and updated.
