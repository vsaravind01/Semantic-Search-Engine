from flask import Flask, json
from flask_restful import reqparse, Resource, Api
from flask_cors import CORS
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
import json
import requests

app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
api = Api(app)

es = Elasticsearch([{'host': 'localhost', 'port': 9200, 'scheme': 'http'}])

transform_model = SentenceTransformer('all-MiniLM-L12-v2')


class IndexManager(Resource):
    def __init__(self) -> None:
        super().__init__()
        self.createArgs = reqparse.RequestParser()
        self.createArgs.add_argument('sabha', required=True, type=str, help='Sabha cannot be blank!')
        self.createArgs.add_argument('version', required=True, type=str, help='Version cannot be blank!')

    def post(self):
        args = self.createArgs.parse_args()
        sabha = args['sabha']
        version = args['version']
        index = sabha+"_"+version
        try:
            res = requests.get(f'http://localhost:9200/{index}')
            if not (index in res.json()):
                create = requests.put(f'http://localhost:9200/{index}', json={
                    "settings": {
                        "index": {
                            "number_of_shards": 3,
                            "number_of_replicas": 2
                        }
                    },
                    "mappings": {
                        "properties": {
                            "qno": {
                                "type": "keyword",
                                "index": True
                            },
                            "starred/unstarred": {
                                "type": "keyword"
                            },
                            "subject": {
                                "type": "completion"
                            },
                            "mp": {
                                "type": "text",
                                "fields": {
                                    "raw": {
                                        "type": "keyword",
                                        "index": True

                                    }
                                }
                            },
                            "ministry": {
                                "type": "keyword",
                                "index": True
                            },
                            "question": {
                                "type": "text",
                                "index": False
                            },
                            "answer": {
                                "type": "text",
                                "index": True
                            },
                            "answered_on": {
                                "type": "date",
                                "format": "dd.MM.yyyy"
                            },
                            "question_vector": {
                                "type": "dense_vector",
                                "dims": 384,
                                "index": True,
                                "similarity": "cosine"
                            }
                        }
                    }
                })
                response = app.response_class(
                    headers={'Content-Type': 'application/json',
                             'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                             'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                    response=json.dumps({'status': 'success', 'message': "Index created successfully"}),
                    status=200,
                    mimetype='application/json'
                )
                return response
            else:
                response = app.response_class(
                    headers={'Content-Type': 'application/json',
                             'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                             'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                    response=json.dumps({'status': 'error', 'message': 'Index already exists'}),
                    status=200,
                    mimetype='application/json'
                )
                return response
        except Exception as e:
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps({'status': 'error', 'message': e}),
                status=500,
                mimetype='application/json'
            )

    def delete(self):
        args = self.createArgs.parse_args()
        sabha = args['sabha']
        version = args['version']
        index = sabha+"_"+version
        try:
            res = requests.delete(f'http://localhost:9200/{index}')
            if ('error' in res.json()):
                response = app.response_class(
                    headers={'Content-Type': 'application/json',
                             'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                             'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                    response=json.dumps({'status': 'error', 'message': res.json()}),
                    status=200,
                    mimetype='application/json'
                )
            else:
                response = app.response_class(
                    headers={'Content-Type': 'application/json',
                             'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                             'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                    response=json.dumps({'status': 'success', 'message': 'Index deleted successfully'}),
                    status=200,
                    mimetype='application/json'
                )
            return response
        except Exception as e:
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps({'status': 'error', 'message': res.json()}),
                status=200,
                mimetype='application/json'
            )
            return response


class QuestionManager(Resource):
    def __init__(self) -> None:
        super().__init__()
        self.questionArgs = reqparse.RequestParser()
        self.questionArgs.add_argument('question', required=True, type=str, help='Question cannot be blank!')
        self.questionArgs.add_argument('mp', required=True, type=str, help='MP cannot be blank!')
        self.questionArgs.add_argument('ministry', required=True, type=str, help='Ministry cannot be blank!')
        self.questionArgs.add_argument('subject', required=True, type=str, help='Subject cannot be blank!')
        self.questionArgs.add_argument('qno', type=str, help='Qno cannot be blank!')
        self.questionArgs.add_argument('starred/unstarred', required=True, type=bool, help='Starred cannot be blank!')
        self.questionArgs.add_argument('answered_on', required=True, type=str, help='Answered on cannot be blank!')
        self.questionArgs.add_argument('sabha', required=True, type=str, help='Sabha cannot be blank!')
        self.questionArgs.add_argument('version', required=True, type=str, help='Version cannot be blank!')
        self.questionArgs.add_argument('answer', type=str, help='Answer cannot be blank!')

    def post(self):
        args = self.questionArgs.parse_args()
        question = args['question']
        mp = args['mp']
        ministry = args['ministry']
        subject = args['subject']
        qno = args['qno']
        starred = args['starred/unstarred']
        answered_on = args['answered_on']
        sabha = args['sabha']
        version = args['version']
        answer = args['answer']
        index = sabha+"_"+version
        try:
            res = requests.get(f'http://localhost:9200/{index}')
            if ('error' in res.json()):
                response = app.response_class(
                    headers={'Content-Type': 'application/json',
                             'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                             'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                    response=json.dumps({'status': 'error', 'message': res.json()}),
                    status=200,
                    mimetype='application/json'
                )
                return response
            else:
                sentence_embeddings = transform_model.encode([args["question"]])
                res = requests.post(f'http://localhost:9200/{index}', json={
                    "question": question,
                    "mp": mp,
                    "ministry": ministry,
                    "subject": subject,
                    "qno": qno,
                    "starred/unstarred": starred,
                    "answered_on": answered_on,
                    "question_vector": sentence_embeddings.tolist()
                })
                response = app.response_class(
                    headers={'Content-Type': 'application/json',
                             'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                             'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                    response=json.dumps({'status': 'success', 'message': 'Question added successfully'}),
                    status=200,
                    mimetype='application/json'
                )
                return response

        except Exception as e:
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps({'status': 'success', 'message': 'Internal server error'}),
                status=200,
                mimetype='application/json'
            )
            return response


class SimilarQuestionList(Resource):
    def __init__(self) -> None:
        super().__init__()
        self.searchArgs = reqparse.RequestParser()
        self.searchArgs.add_argument('question', required=True, type=str, help='Question cannot be blank!')
        self.searchArgs.add_argument('lok_sabha', type=int)
        self.searchArgs.add_argument('rajya_sabha', type=int)
        self.searchArgs.add_argument('size', required=True, type=int, help='Size cannot be blank!')
        self.searchArgs.add_argument('min_score', required=True,  type=float, help='Min score cannot be blank!')

    def post(self):
        args = self.searchArgs.parse_args()
        index = []
        if args['lok_sabha'] is not None:
            index.append("lok_sabha_"+str(args['lok_sabha']))
        if args['rajya_sabha'] is not None:
            index.append("rajya_sabha_"+str(args['rajya_sabha']))

        if index == []:
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps({'error': 'Either of lok_sabha or rajya_sabha must be present'}),
                status=400,
                mimetype='application/json'
            )
            return response
        else:
            try:
                sentence_embeddings = transform_model.encode([args["question"]])
                res = es.knn_search(index="lok_sabha_17_test", knn={
                    "field": "question_vector",
                    "query_vector": sentence_embeddings[0].tolist(),
                    "k": args['size'],
                    "num_candidates": 100
                }, source=["qno", "answered_on", "subject", "question", "answer", "mp", "ministry", "starred/unstarred"])
                response = app.response_class(
                    response=json.dumps(res.body),
                    headers={'Content-Type': 'application/json',
                             'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                             'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                    status=200,
                    mimetype='application/json'
                )
                return response
            except Exception as e:
                response = app.response_class(
                    response=json.dumps({'status': 'error', 'message': e}),
                    status=500,
                    mimetype='application/json'
                )
                return response


class Suggestions(Resource):
    def __init__(self) -> None:
        super().__init__()
        self.suggestArgs = reqparse.RequestParser()
        self.suggestArgs.add_argument('index', required=True, type=str, help='Index cannot be blank!')
        self.suggestArgs.add_argument('query', required=True, type=str, help='Query cannot be blank!')
        self.suggestArgs.add_argument('size', required=True, type=int, help='Size cannot be blank!')

    def post(self):
        args = self.suggestArgs.parse_args()
        suggest_dictionary = {"subject_suggestions": {
            'text': args['query'],
            'completion': {
                'field': 'subject',
                'size': args['size']
            }
        }}
        query_dictionary = {
            'sort': [
                {
                    "answered_on": {
                        "order": "desc"
                    }
                }
            ],
            'suggest': suggest_dictionary,
            "_source": False
        }
        try:
            res = es.search(index=args['index'], body=query_dictionary)
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps(res.body),
                status=200,
                mimetype='application/json'
            )
            return response
        except Exception as e:
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response="""{'status': 'error', 'message': "Search engine down"}""",
                status=500,
                mimetype='application/json'
            )
            return response


class Recents(Resource):
    def __init__(self) -> None:
        super().__init__()
        self.recentsArgs = reqparse.RequestParser()
        self.recentsArgs.add_argument('index', required=True, type=str, help='Index cannot be blank!')

    def post(self):
        args = self.recentsArgs.parse_args()
        query = {
            "query": {
                "match_all": {}
            },
            "size": 10,
            "sort": [
                {
                    "answered_on": {
                        "order": "desc"
                    }
                }
            ],
            "_source": ["subject"]
        }
        try:
            res = es.search(index=args['index'], body=query)
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps(res.body),
                status=200,
                mimetype='application/json'
            )
            return response
        except Exception as e:
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps({'status': 'error', 'message': e}),
                status=500,
                mimetype='application/json'
            )
            return response


api.add_resource(SimilarQuestionList, '/search')
api.add_resource(IndexManager, '/index')
api.add_resource(Suggestions, '/suggest')
api.add_resource(Recents, "/recents")
api.add_resource(QuestionManager, "/question")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
