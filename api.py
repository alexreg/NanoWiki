from datetime import datetime
from flask import Flask, Response, make_response, request
import flask_etags
from flask_restful import Api, Resource
import flask_restful_patch
from functools import wraps
import hashlib
from marshmallow import Schema, ValidationError, fields
import os
import pickle
import traceback
from wikistore import DocumentInfo, DocumentRevision, DocumentRevisionInfo, WikiStore, WikiStoreError, WikiStoreErrorType

datetime_format = "%Y-%m-%d %H:%M:%S"

def err_no_json_input():
	return {
		"message": "No JSON input was given.",
	}, 400

def err_validation(error):
	return {
		"message": "The input JSON data was not valid.",
		"details": error.messages,
	}, 422

def err_wikistore(error):
	return {
		"message": "An error occurred accessing the wiki store: {}".format(error),
		"type": error.type.name,
	}, 404 if error.type == WikiStoreErrorType.DOCUMENT_NOT_FOUND else 500

def err_general(error):
	return {
		"message": "An error occurred processing the request: {}".format(error),
	}, 500

def handle_errors(func):
	@wraps(func)
	def wrapper(self, *args, **kwargs):
		try:
			return func(self, *args, **kwargs)
		except Exception as e:
			if app.debug:
				traceback.print_exc()
			if isinstance(e, WikiStoreError):
				return err_wikistore(e)
			return err_general(e)
	return wrapper

def parse_json(func):
	@wraps(func)
	def wrapper(self, *args, **kwargs):
		json_data = request.get_json()
		if not json_data:
			return err_no_json_input()
		try:
			return func(self, *args, **kwargs, json_data = json_data)
		except ValidationError as e:
			if app.debug:
				traceback.print_exc()
			return err_validation(e)
	return wrapper

def validate_title(title):
	if not title:
		raise ValidationError("No title was given", "title")
	else:
		if len(title) > 50:
			raise ValidationError("The given title is too long", "title")

def create_etag(data):
	return hashlib.sha1(pickle.dumps(data)).hexdigest()

class DocumentInfoSchema(Schema):
	title = fields.Str()
	last_modified_time = fields.DateTime(format = datetime_format)

class DocumentRevisionInfoSchema(Schema):
	revision = fields.Str()
	created_time = fields.DateTime(format = datetime_format)

class DocumentRevisionSchema(DocumentRevisionInfoSchema):
	content = fields.Str(required = True)

class Wiki(Resource):
	method_decorators = {
		"*": [handle_errors],
		"put": [parse_json],
		"post": [parse_json],
	}
	
	def __init__(self, *, wiki_store):
		self.wiki_store = wiki_store
		
		self.doc_info_schema = DocumentInfoSchema(strict = True)
		self.doc_rev_info_schema = DocumentRevisionInfoSchema(strict = False)
		self.doc_rev_schema = DocumentRevisionSchema(strict = True)
	
	def get(self, title = None, revision = None):
		if title is None:
			output, last_modified_time = self.wiki_store.list_docs()
			response = self.doc_info_schema.dump(output, many = True).data
		else:
			validate_title(title)
			if revision is None:
				output, last_modified_time = self.wiki_store.list_doc_revs(title)
				response = self.doc_rev_info_schema.dump(output, many = True).data
			else:
				output = self.wiki_store.get_doc_rev(title, revision)
				last_modified_time = output.created_time
				response = self.doc_rev_schema.dump(output).data
		
		return response, 200, {
			"ETag": create_etag(last_modified_time),
		}
	
	def delete(self, title):
		validate_title(title)
		self.wiki_store.delete_doc(title)
		return {}, 204
	
	def post(self, title, *, json_data):
		validate_title(title)
		data = self.doc_rev_schema.load(json_data).data
		created = False
		if not self.wiki_store.doc_exists(title):
			created = True
			last_modified_time = self.wiki_store.create_doc(title)
		output = self.wiki_store.create_doc_rev(title, data["content"])
		
		return self.doc_rev_info_schema.dump(output), 201 if created else 204, {
			"ETag": create_etag(output.created_time),
		}

app = Flask(__name__)
api = Api(app, catch_all_404s = True)

wiki_store = WikiStore(os.getenv("NANOWIKI_WIKI_PATH", "wiki.store"))

api.add_resource(
	Wiki,
	"/documents",
	"/documents/<string:title>",
	"/documents/<string:title>/<string:revision>",
	resource_class_kwargs = {
		"wiki_store": wiki_store
	},
)

if __name__ == "__main__":
	app.run(debug = True)
