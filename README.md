```
mkdir es_data
docker-compose up --build
```

Now you can run ES queries against on the host machine: `curl -X GET http://localhost:9200/pubmed_abstracts/_count`
