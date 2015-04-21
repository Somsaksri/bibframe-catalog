__author__ = "Jeremy Nelson"

import io
import mimetypes
import requests
from flask import abort, jsonify, render_template, request
from flask import send_file
from .forms import BasicSearch
from . import app, datastore_url, es_search, __version__, datastore_url, PREFIX

COVER_ART_SPARQL = """{}
PREFIX fedora: <http://fedora.info/definitions/v4/repository#>
SELECT DISTINCT ?cover
WHERE {{{{
   ?cover fedora:uuid "{{}}"^^<http://www.w3.org/2001/XMLSchema#string>
}}}}""".format(PREFIX)

@app.route('/search', methods=['POST', 'GET'])
def search():
    """Search view for the application"""
    search_type = request.form.get('search_type', 'kw')
    phrase = request.form.get('phrase')
    if search_type.startswith("kw"):
        result = es_search.search(q=phrase, index='bibframe', doc_type='Instance', size=5)
    else:
        result = es_search.search(
            q=phrase,
            index='bibframe',
            doc_type='Work',
            size=5)
    for hit in result.get('hits').get('hits'):
        for key, value in hit['_source'].items():
            if key.startswith('fcrepo:uuid'):
                continue
            for i,row in enumerate(value):
                if es_search.exists(id=row, index='bibframe'):
                    hit['_source'][key][i] = es_search.get_source(id=row, index='bibframe')

    return render_template(
        'results.html', 
         search_type=search_type, 
         basic_search=BasicSearch(),
         result=result, 
         phrase=phrase)
    #return jsonify(result)
    #return "{} phrase={}".format(search_type, phrase)

@app.route("/CoverArt/<uuid>.<ext>", defaults={"ext": "jpg"})
def cover(uuid, ext):
    sparql = COVER_ART_SPARQL.format(uuid)
    cover_uri_result = requests.post(
        "{}/triplestore".format(datastore_url),
        data={"sparql": sparql})
    if cover_uri_result.status_code < 400:
         results = cover_uri_result.json()['results']
         image_url = results['bindings'][0]['cover']['value'].split("/fcr:metadata")[0] 
         get_image_result = requests.get(image_url)
         raw_image = get_image_result.content
         file_name = '{}.{}'.format(uuid, ext)
         return send_file(io.BytesIO(raw_image),
                          attachment_filename=file_name,
                          mimetype=mimetypes.guess_type(file_name)[0])
    print(cover_uri_result.status_code)
    abort(500)

@app.route("/<entity>/<uuid>", defaults={"ext": "html"})
@app.route("/<entity>/<uuid>.<ext>", 
           defaults={"entity": "Work", 
                     "ext": "html"})
def detail(entity, uuid, ext):
    if es_search.exists(id=uuid, index='bibframe', doc_type=entity):
        resource = dict()
        result = es_search.get_source(id=uuid, index='bibframe')
        resource.update(result)
        if entity.lower().startswith("work"):
            sparql = """SELECT DISTINCT ?instance
WHERE {{{{
  ?instance  bf:instanceOf <{}> . 
}}}}""".format(result['fcrepo:hasLocation'][0])
                    
        return render_template(
            'detail.html',
            entity=resource,
            version=__version__)
    abort(404)

##@app.route("/<entity>/<uuid>.<ext>")
##@app.route("/<uuid>.<ext>", defaults={"entity": "Work", "ext": "html"})
##@app.route("/<uuid>", defaults={"entity": None})
##def resource(uuid, entity, ext='html'):
##    """Detailed view for a single resource
##
##    Args:
##        uuid: Fedora UUID also used as ID in Elastic Search index
##    """
##    if es_search.exists(id=uuid, index='bibframe'):
##        result = es_search.get_source(id=uuid, index='bibframe')
##        for key, value in result.items():
##            if key.startswith('fcrepo:uuid'):
##                continue
##            for i,row in enumerate(value):
##                if es_search.exists(id=row, index='bibframe'):
##                    result[key][i] = es_search.get_source(id=row, index='bibframe')
##        #fedora_url = result.get('fcrepo:hasLocation')[0]
##        #fedora_graph = rdflib.Graph().parse(fedora_url)
##        related = es_search.search(q=uuid, index='bibframe')
##        if ext.startswith('json'):
##            #return fedora_graph.serialize(format='json-ld', indent=2).decode()
##            return jsonify(result)
##        return render_template(
##            'detail.html',
##            entity=result,
##            #graph=fedora_graph,
##            related=related,
##            version=__version__
##        )
##    abort(404)


@app.route("/")
def index():
    """Default view for the application"""
    return render_template(
        "index.html",
        #repository=repository,
        search=es_search,
        basic_search=BasicSearch(),
        version=__version__)