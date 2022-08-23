from flask import Flask, request, json
from flask_restful import reqparse, Resource, Api
from flask_cors import CORS
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
import json
from datetime import datetime
import configparser

config = configparser.ConfigParser()
config.read('project.ini')

app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
api = Api(app)

es = Elasticsearch(
    cloud_id=config['ELASTIC']['cloud_id'],
    basic_auth=(config['ELASTIC']['user'], config['ELASTIC']['password'])
)

# es = Elasticsearch("http://localhost:9200")

API_KEY = "600b6db6a2d4f50b17bef02d950dfc51c4bc1b391b18cfa3ddf334bab7fa06bf"

transform_model = SentenceTransformer('all-MiniLM-L12-v2')


def format_record(data):
    temp = data[0].split('_')
    name = (temp[0] + ' ' + temp[1]).title()
    version = temp[2]
    record = {'name': name, 'version': version, 'count': data[1]}
    return record


# formatting the indices to a list of dictionaries
# sample
'''
    [
        lok_sabha: [
            {  name: 'Lok Sabha', version: '1', count: '10' },
            {  name: 'Lok Sabha', version: '2', count: '10' },
        ],
        rajya_sabha: [
            {  name: 'Rajya Sabha', version: '1', count: '10' },
            {  name: 'Rajya Sabha', version: '2', count: '10' },
        ]
    ]
'''


def format_records(data):
    lok_sabha = list(filter(lambda x: x.startswith("lok_sabha"), data))
    rajya_sabha = list(filter(lambda x: x.startswith("rajya_sabha"), data))

    lok_sabha = list(map(lambda x: x.split(), lok_sabha))
    rajya_sabha = list(map(lambda x: x.split(), rajya_sabha))

    lok_sabha_records = list(map(lambda x: format_record(x), lok_sabha))
    rajya_sabha_records = list(map(lambda x: format_record(x), rajya_sabha))

    records = {'lok_sabha': lok_sabha_records, 'rajya_sabha': rajya_sabha_records}

    return records


@app.route('/get/indices')
def get_indices():
    data = es.cat.indices(h="index", s="index").split()
    response = app.response_class(
        response=json.dumps(data),
        status=200,
        mimetype='application/json'
    )
    return response


@app.route('/get/indices_with_count')
def get_indices_with_count():
    data = es.cat.indices(h="index,docs.count", s="index").split("\n")
    indices = format_records(data)
    response = app.response_class(
        response=json.dumps(indices),
        status=200,
        mimetype='application/json'
    )
    return response


@app.route('/get/mp/records', methods=['GET'])
def get_mp():
    args = request.args
    index = args.get("index", default="lok_sabha_*, rajya_sabha_*")
    mp_id = args.get("mp_id")
    data = es.search(index=index, body={
        "query": {
            "match": {
                "mp_id": mp_id
            }
        }
    }, source=["question", "answer", "mp", "ministry", "answered_on", "starred/unstarred", "qno",
               "styled_answer", "mp_id", "ministry_id", "subject"])
    response = app.response_class(
        response=json.dumps(data),
        status=200,
        mimetype='application/json'
    )
    return response


@app.route('/get/question/<index>/<id>', methods=['GET'])
def get_question(id, index):
    data = es.get(index=index, id=id,
                  source=["question", "answer", "mp", "ministry", "answered_on", "starred/unstarred", "qno",
                          "styled_answer", "mp_id", "ministry_id", "subject"]
                  )
    response = app.response_class(
        response=json.dumps(data.body),
        status=200,
        mimetype='application/json'
    )
    return response


@app.route('/get/questions/unanswered/<index>', methods=['GET'])
def get_questions_unanswered(index):
    data = es.search(index=index,
                     source=["question",
                             "answer",
                             "subject",
                             "mp",
                             "ministry",
                             "asked_on",
                             "starred/unstarred",
                             "qno",
                             "styled_answer"],
                     query={
                         "bool": {
                             "must_not": [
                                 {
                                     "exists": {
                                         "field": "answer"
                                     }
                                 }
                             ]
                         }
                     })
    response = app.response_class(
        response=json.dumps(data.body),
        status=200,
        mimetype='application/json'
    )
    return response


@app.route('/get/questions/<user_type>/unanswered/<index>/<id>', methods=['GET'])
def get_user_unanswered_questions(user_type, index, id):
    data = es.search(index=index,
                     source=["question",
                             "answer",
                             "subject",
                             "mp",
                             "ministry",
                             "asked_on",
                             "starred/unstarred",
                             "qno",
                             "styled_answer"],
                     query={
                         "bool": {
                             "must_not": [
                                 {
                                     "exists": {
                                         "field": "answer"
                                     }
                                 }
                             ],
                             "must": [
                                 {
                                     "match": {
                                         f"{user_type}_id": id
                                     }
                                 }
                             ]
                         }
                     })
    response = app.response_class(
        response=json.dumps(data.body),
        status=200,
        mimetype='application/json'
    )
    return response


class IndexManager(Resource):
    def __init__(self) -> None:
        super().__init__()
        self.createArgs = reqparse.RequestParser()
        self.createArgs.add_argument('SECRET_KEY', type=str, required=True, help='Secret Key is required')
        self.createArgs.add_argument('sabha', required=True, type=str, help='Sabha cannot be blank!')
        self.createArgs.add_argument('version', required=True, type=str, help='Version cannot be blank!')

    def post(self):
        args = self.createArgs.parse_args()

        # Validate secret key
        if args['SECRET_KEY'] != API_KEY:
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*',
                         'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps({'status': 'error', 'message': "Invalid secret key"}),
                status=200,
                mimetype='application/json'
            )
            return response

        sabha = args['sabha']
        version = args['version']
        index = sabha + "_" + version
        try:
            exists = es.indices.exists(index='user')
            if not exists:
                create = es.indices.create(index=index, body={
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
                                "index": True
                            },
                            "answer": {
                                "type": "text",
                                "index": True,
                            },
                            "answer_styled": {
                                "type": "text",
                                "index": False,
                            },
                            "asked_on": {
                                "type": "date",
                                "format": "dd.MM.yyyy"
                            },
                            "mp_id": {
                                "type": "text",
                                "index": True
                            },
                            "ministry_id": {
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
                             'Access-Control-Allow-Origin': '*',
                             'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                             'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                    response=json.dumps(
                        {'status': 'success', 'message': "Index created successfully"}),
                    status=200,
                    mimetype='application/json'
                )
                return response
            else:
                response = app.response_class(
                    headers={'Content-Type': 'application/json',
                             'Access-Control-Allow-Origin': '*',
                             'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                             'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                    response=json.dumps({'status': 'error', 'message': 'Index already exists'}),
                    status=200,
                    mimetype='application/json'
                )
                return response
        except Exception as e:
            print(e)
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*',
                         'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps({'status': 'error', 'message': "Error creating index"}),
                status=500,
                mimetype='application/json'
            )
            return response

    def delete(self):
        args = self.createArgs.parse_args()
        if args['SECRET_KEY'] != API_KEY:
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*',
                         'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps({'status': 'error', 'message': "Invalid secret key"}),
                status=403,
                mimetype='application/json'
            )
            return response
        sabha = args['sabha']
        version = args['version']
        index = sabha + "_" + version
        try:
            res = es.indices.delete(index=index, ignore=[400, 404])
            if 'error' in res:
                response = app.response_class(
                    headers={'Content-Type': 'application/json',
                             'Access-Control-Allow-Origin': '*',
                             'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                             'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                    response=json.dumps({'status': 'error', 'message': res}),
                    status=400,
                    mimetype='application/json'
                )
            else:
                response = app.response_class(
                    headers={'Content-Type': 'application/json',
                             'Access-Control-Allow-Origin': '*',
                             'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                             'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                    response=json.dumps({'status': 'success', 'message': 'Index deleted successfully'}),
                    status=200,
                    mimetype='application/json'
                )
            return response
        except Exception as e:
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*',
                         'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps({'status': 'error', 'message': "internal server error"}),
                status=400,
                mimetype='application/json'
            )
            return response


# Unique MP questions in a sabha
class MpManager(Resource):
    def __init__(self) -> None:
        super().__init__()
        self.mpArgs = reqparse.RequestParser()
        self.mpArgs.add_argument('index', required=True, type=str, help='Index cannot be blank!')

    def post(self):
        args = self.mpArgs.parse_args()
        index = args['index'].strip().split(",")

        try:
            body = {
                "size": 0,
                "aggs": {
                    "distinct_mps": {
                        "terms": {
                            "field": "mp.raw",
                            "size": 1000
                        }
                    }
                },
                "_source": ["mp"]
            }
            mps = es.search(index=index, body=body)
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*',
                         'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps(mps.body['aggregations']['distinct_mps']['buckets']),
                status=200,
                mimetype='application/json'
            )
            return response

        except Exception as e:
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*',
                         'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps({'status': 'error', 'message': e}),
                status=500,
                mimetype='application/json'
            )
            return response


# Answers to a question
class AnswerManager(Resource):
    def __init__(self) -> None:
        super().__init__()
        self.answerArgs = reqparse.RequestParser()
        self.answerArgs.add_argument('index', required=True, type=str, help='Index cannot be blank!')
        self.answerArgs.add_argument('id', required=True, type=str, help='Id cannot be blank!')
        self.answerArgs.add_argument('answer', required=True, type=str, help='Answer cannot be blank!')
        self.answerArgs.add_argument('answer_styled', required=True, type=str, help='Styled answer cannot be blank!')
        self.answerArgs.add_argument('SECRET_KEY', type=str, required=True, help='Secret Key is required')

    def post(self):
        args = self.answerArgs.parse_args()
        if args['SECRET_KEY'] != API_KEY:
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*',
                         'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps({'status': 'error', 'message': "Invalid secret key"}),
                status=403,
                mimetype='application/json'
            )
            return response
        index = args['index']
        Id = args['id']
        answer = args['answer']
        answer_styled = args['answer_styled']
        try:
            res = es.update(index=index, id=Id, doc={
                "answer": answer,
                "answer_styled": answer_styled
            })
            if 'error' in res:
                response = app.response_class(
                    headers={'Content-Type': 'application/json',
                             'Access-Control-Allow-Origin': '*',
                             'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                             'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                    response=json.dumps({'status': 'error', 'message': res}),
                    status=400,
                    mimetype='application/json'
                )
            else:
                response = app.response_class(
                    headers={'Content-Type': 'application/json',
                             'Access-Control-Allow-Origin': '*',
                             'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                             'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                    response=json.dumps({'status': 'success', 'message': 'Answer updated successfully'}),
                    status=200,
                    mimetype='application/json'
                )
            return response
        except Exception as e:
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*',
                         'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps({'status': 'error', 'message': e}),
                status=500,
                mimetype='application/json'
            )
            return response


class QuestionManager(Resource):
    def __init__(self) -> None:
        super().__init__()
        self.questionUploadArgs = reqparse.RequestParser()
        self.questionUploadArgs.add_argument('SECRET_KEY', required=True, type=str, help='Secret key cannot be blank!')
        self.questionUploadArgs.add_argument('question', required=True, type=str, help='Question cannot be blank!')
        self.questionUploadArgs.add_argument('mp', required=True, type=str, help='MP cannot be blank!')
        self.questionUploadArgs.add_argument('ministry', required=True, type=str, help='Ministry cannot be blank!')
        self.questionUploadArgs.add_argument('subject', required=True, type=str, help='Subject cannot be blank!')
        self.questionUploadArgs.add_argument('starred/unstarred', required=True, type=str,
                                             help='Starred cannot be blank!')
        self.questionUploadArgs.add_argument('sabha', required=True, type=str, help='Sabha cannot be blank!')
        self.questionUploadArgs.add_argument('version', required=True, type=str, help='Version cannot be blank!')
        self.questionUploadArgs.add_argument('answer', type=str)
        self.questionUploadArgs.add_argument('mp_id', required=True, type=str, help='MP ID cannot be blank!')
        self.questionUploadArgs.add_argument('ministry_id', required=True, type=str,
                                             help='Ministry ID cannot be blank!')

    def post(self):
        args = self.questionUploadArgs.parse_args()
        print(args)

        # validate secret key
        if args['SECRET_KEY'] != API_KEY:
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*',
                         'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps({'status': 'error', 'message': 'Invalid secret key'}),
                status=200,
                mimetype='application/json'
            )
            return response

        question = args['question']
        mp = args['mp']
        ministry = args['ministry']
        subject = args['subject']
        starred = args['starred/unstarred']
        sabha = args['sabha']
        version = args['version']
        mp_id = args['mp_id']
        ministry_id = args['ministry_id']
        index = sabha + "_" + str(version)
        try:
            exists = es.indices.exists(index=index)
            if not exists:
                print(exists)
                response = app.response_class(
                    headers={'Content-Type': 'application/json',
                             'Access-Control-Allow-Origin': '*',
                             'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                             'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                    response=json.dumps({'status': 'error', 'message': "Index does not exist"}),
                    status=400,
                    mimetype='application/json'
                )
                return response
            else:
                sentence_embeddings = transform_model.encode([question])
                count = es.count(index=index)['count']
                asked_on = datetime.now().strftime('%d.%m.%Y')
                data = {
                    "qno": count + 1,
                    "starred/unstarred": starred,
                    "mp": mp,
                    "ministry": ministry,
                    "subject": subject,
                    "question": question,
                    "asked_on": asked_on,
                    "mp_id": mp_id,
                    "ministry_id": ministry_id,
                    "question_vector": sentence_embeddings[0].tolist(),

                }
                res = es.index(index=index, document=data)
                print(res)
                response = app.response_class(
                    headers={'Content-Type': 'application/json',
                             'Access-Control-Allow-Origin': '*',
                             'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                             'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                    response=json.dumps(
                        {'status': 'success', 'message': 'Question added successfully', 'res': res.body}),
                    status=200,
                    mimetype='application/json'
                )
                return response

        except Exception as e:
            print(e)
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*',
                         'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps({'status': 'error', 'message': 'Internal server error'}),
                status=200,
                mimetype='application/json'
            )
            return response


class SimilarQuestionList(Resource):
    def __init__(self) -> None:
        super().__init__()
        self.searchArgs = reqparse.RequestParser()
        self.searchArgs.add_argument('question', required=True, type=str, help='Question cannot be blank!')
        self.searchArgs.add_argument('index', required=True, type=str, help='Index cannot be blank!')
        self.searchArgs.add_argument('size', required=True, type=int, help='Size cannot be blank!')
        self.searchArgs.add_argument('min_score', required=True, type=float, help='Min score cannot be blank!')
        self.searchArgs.add_argument('from_date', type=str)
        self.searchArgs.add_argument('to_date', type=str)
        self.searchArgs.add_argument('mp', type=str)
        self.searchArgs.add_argument('ministry', type=str)

    def post(self):
        args = self.searchArgs.parse_args()
        index = args['index'].split(',')

        if not index:
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*',
                         'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps({'error': 'Either of lok_sabha or rajya_sabha must be present'}),
                status=400,
                mimetype='application/json'
            )
            return response
        else:
            try:
                sentence_embeddings = transform_model.encode([args["question"]])
                filters = list()
                date_filter = dict()
                if args['from_date'] is not None:
                    date_filter['gte'] = args['from_date']
                if args['to_date'] is not None:
                    date_filter['lte'] = args['to_date']
                if date_filter != {}:
                    filters.append({"range": {"answered_on": date_filter}})
                if args['mp'] is not None:
                    filters.append({"term": {"mp.raw": args['mp']}})
                if args['ministry'] is not None:
                    filters.append({"term": {"ministry": args['ministry']}})

                res = es.knn_search(index=index,
                                    knn={
                                        "field": "question_vector",
                                        "query_vector": sentence_embeddings[0].tolist(),
                                        "k": args['size'],
                                        "num_candidates": 100
                                    },
                                    source=["qno", "answered_on", "subject", "question", "answer", "mp", "ministry",
                                            "starred/unstarred"],
                                    filter=filters)
                response = app.response_class(
                    response=json.dumps(res.body),
                    headers={'Content-Type': 'application/json',
                             'Access-Control-Allow-Origin': '*',
                             'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                             'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                    status=200,
                    mimetype='application/json'
                )
                return response
            except Exception as e:
                print(e)
                response = app.response_class(
                    response=json.dumps({'status': 'error', 'message': "Internal server error"}),
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
                         'Access-Control-Allow-Origin': '*',
                         'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps(res.body),
                status=200,
                mimetype='application/json'
            )
            return response
        except Exception as e:
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*',
                         'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps({'status': 'error', 'message': "Search engine down"}),
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
                         'Access-Control-Allow-Origin': '*',
                         'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps(res.body),
                status=200,
                mimetype='application/json'
            )
            return response
        except Exception as e:
            response = app.response_class(
                headers={'Content-Type': 'application/json',
                         'Access-Control-Allow-Origin': '*',
                         'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                         'Access-Control-Allow-Headers': 'Content-Type, Authorization, Content-Length, X-Requested-With'},
                response=json.dumps({'status': 'error', 'message': "Internal server error"}),
                status=500,
                mimetype='application/json'
            )
            return response


api.add_resource(SimilarQuestionList, '/search')
api.add_resource(IndexManager, '/index')
api.add_resource(Suggestions, '/suggest')
api.add_resource(Recents, "/recents")
api.add_resource(QuestionManager, "/question")
api.add_resource(MpManager, "/mp")
api.add_resource(AnswerManager, "/answer")

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)
