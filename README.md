# Semantic-Search-Engine

Search Engine for the Parliament Connect. Tools and technologies used - Elasticsearch, SentenceTransformers, Flask and FPDF.

We use the sentence transformer model to encode all the parliament questions/answers and store in the Elasticsearch index as dense vectors.
These records are then matched with the encoded query with `knn_search`.

The search engine makes use of the sentence transformers model 
[all-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L12-v2) 
finetuned from [microsoft/MiniLM-L12-H384-uncased](https://huggingface.co/microsoft/MiniLM-L12-H384-uncased).

|Model Name          |Performance Sentence Embeddings (14 Datasets)  |Performance Semantic Search (6 Datasets)  |Avg. Performance  |Speed (sentences / second on V100 GPU)  |Model Size  |
|:------------------:|:---------------------------------------------:|:----------------------------------------:|:----------------:|:-----:|:----------:|
|all-MiniLM-L12-v2   |68.70                                          |50.82                                     |59.76             |7500   |120 MB      |


The search engine is deployed in an AWS EC2 instance (t3.micro). The model is chosen to provide efficient performance even under CPU only conditions.
