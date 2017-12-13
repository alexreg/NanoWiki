# This code has been adapted from <http://flask.pocoo.org/snippets/95/>.

from flask import Response, abort, g, request
from functools import wraps
from werkzeug import ETagResponseMixin
from werkzeug.exceptions import HTTPException

class NotModified(HTTPException):
	code = 304
	description = "Not Modified"

def etag_request(func):
	@wraps(func)
	def wrapper(*args, **kwargs):
		g.condtnl_etags_start = True
		return func(*args, **kwargs)
	return wrapper

@wraps(ETagResponseMixin.set_etag)
def _new_set_etag(self, etag, weak = False):
	# Only check the first time; when called the second time, the etag is being modified.
	if hasattr(g, "condtnl_etags_start") and g.condtnl_etags_start:
		if request.method in ("PUT", "DELETE", "PATCH"):
			if not request.if_match:
				raise PreconditionRequired()
			if etag not in request.if_match:
				raise PreconditionFailed()
		elif request.method == "GET" and (request.if_none_match and etag in request.if_none_match):
			raise NotModified()
		g.condtnl_etags_start = False
	_old_set_etag(self, etag, weak)

_old_set_etag = ETagResponseMixin.set_etag
ETagResponseMixin.set_etag = _new_set_etag
