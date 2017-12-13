from datetime import datetime
from flask import Flask, Response, abort, request
from flask_etags import etag_request
from flask_restful import Api, Resource
import flask_restful_patch
from functools import wraps
import hashlib
import json
from marshmallow import Schema, ValidationError, fields
import os
import pickle
from werkzeug.exceptions import BadRequest, HTTPException, InternalServerError, NotFound
from wikistore import DocumentInfo, DocumentRevision, DocumentRevisionInfo, WikiStore, WikiStoreError, WikiStoreErrorType

datetime_format = "%Y-%m-%d %H:%M:%S"

def _create_etag(data):
	return hashlib.sha1(pickle.dumps(data)).hexdigest()

def _parse_json(func):
	@wraps(func)
	def wrapper(self, *args, **kwargs):
		json_data = request.get_json()
		if not json_data:
			raise BadRequest(description = "No JSON input data was given.")
		try:
			return func(self, *args, **kwargs, json_data = json_data)
		except ValidationError as e:
			raise ValidationHttpError(e) from e
	return wrapper

def _validate_title(title):
	if not title:
		raise ValidationError("No title was given", "title")
	else:
		if len(title) > 50:
			raise ValidationError("The given title is too long", "title")

class DocumentInfoSchema(Schema):
	title = fields.Str()
	last_modified_time = fields.DateTime(format = datetime_format)

class DocumentRevisionInfoSchema(Schema):
	revision = fields.Str()
	created_time = fields.DateTime(format = datetime_format)

class DocumentRevisionSchema(DocumentRevisionInfoSchema):
	content = fields.Str(required = True)

class ValidationHttpError(BadRequest):
	description = "The input JSON data was not valid."
	
	def __init__(self, e):
		super().__init__()
		data = {
			"message": e.args[0],
			"validation": e.messages,
		}

class WikiStoreHttpError(HTTPException):
	code = 500
	description = "An error occurred accessing the wiki store."
	
	def __init__(self, e):
		super().__init__()
		if e.type == WikiStoreErrorType.DOCUMENT_NOT_FOUND or e.type == WikiStoreErrorType.DOCUMENT_REVISION_NOT_FOUND:
			self.code = 404
		self.data = {
			"message": e.args[0],
			"type": e.type.name,
		}
		if hasattr(e, "title"):
			self.data["documentTitle"] = e.title
		if hasattr(e, "revision"):
			self.data["documentRevision"] = e.revision

class WikiResource(Resource):
	method_decorators = {
		"*": [],
		"put": [_parse_json],
		"post": [_parse_json],
	}
	
	def __init__(self, *, wiki_store):
		self.wiki_store = wiki_store
		
		self.doc_info_schema = DocumentInfoSchema(strict = True)
		self.doc_rev_info_schema = DocumentRevisionInfoSchema(strict = False)
		self.doc_rev_schema = DocumentRevisionSchema(strict = True)
	
	@etag_request
	def get(self, title = None, revision = None):
		if title is None:
			output, last_modified_time = self.wiki_store.list_docs()
			response = self.doc_info_schema.dump(output, many = True).data
		else:
			_validate_title(title)
			if revision is None:
				output, last_modified_time = self.wiki_store.list_doc_revs(title)
				response = self.doc_rev_info_schema.dump(output, many = True).data
			else:
				output = self.wiki_store.get_doc_rev(title, revision)
				last_modified_time = output.created_time
				response = self.doc_rev_schema.dump(output).data
		
		return api.make_response(response, 200, etag = last_modified_time)
	
	def delete(self, title):
		_validate_title(title)
		self.wiki_store.delete_doc(title)
		
		return api.make_response({}, 204)
	
	def post(self, title, *, json_data):
		_validate_title(title)
		data = self.doc_rev_schema.load(json_data).data
		created = False
		if not self.wiki_store.doc_exists(title):
			created = True
			last_modified_time = self.wiki_store.create_doc(title)
		output = self.wiki_store.create_doc_rev(title, data["content"])
		
		return api.make_response(self.doc_rev_info_schema.dump(output).data, 201 if created else 200, etag = output.created_time)

class WikiApi(Api):
	def __init__(self, *args, **kwargs):
		kwargs["default_mediatype"] = None
		super().__init__(*args, **kwargs)
	
	def handle_error(self, e):
		if isinstance(e, HTTPException):
			pass
		elif isinstance(e, WikiStoreError):
			e = WikiStoreHttpError(e)
		else:
			e = InternalServerError()
		return super().handle_error(e)
	
	def make_response(self, data, *args, etag = None, etag_weak = False, **kwargs):
		response = super().make_response(data, *args, **kwargs)
		if etag:
			response.set_etag(_create_etag(etag), weak = etag_weak)
		return response

app = Flask(__name__)
api = WikiApi(app, catch_all_404s = True)
wiki_store = WikiStore(os.getenv("NANOWIKI_WIKI_PATH", "wiki-store"))

api.add_resource(
	WikiResource,
	"/documents",
	"/documents/<string:title>",
	"/documents/<string:title>/<string:revision>",
	resource_class_kwargs = {
		"wiki_store": wiki_store
	},
)

if __name__ == "__main__":
	app.run(debug = True)
