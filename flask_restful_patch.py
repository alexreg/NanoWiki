from collections import Mapping
from flask import Response, request
from flask_restful import Resource, Api
from flask_restful.utils import OrderedDict

# Version of `Resource.dispatch_request` method that fixes behaviour of `method_decorators` attribute, per <https://github.com/flask-restful/flask-restful/issues/585>.
def dispatch_request(self, *args, **kwargs):
	meth = getattr(type(self), request.method.lower(), None)
	if meth is None and request.method == "HEAD":
		meth = getattr(type(self), "get", None)
	assert meth is not None, "Unimplemented method %r" % request.method
	
	if isinstance(self.method_decorators, Mapping):
		decorators = self.method_decorators.get("*", []) + self.method_decorators.get(request.method.lower(), [])
	else:
		decorators = self.method_decorators
	
	for decorator in decorators:
		meth = decorator(meth)
	
	resp = meth(self, *args, **kwargs)
	
	if isinstance(resp, Response):
		return resp
	
	representations = self.representations or OrderedDict()
	
	mediatype = request.accept_mimetypes.best_match(representations, default = None)
	if mediatype in representations:
		data, code, headers = unpack(resp)
		resp = representations[mediatype](data, code, headers)
		resp.headers["Content-Type"] = mediatype
		return resp
	
	return resp

# Monkey-patch `Resource` class.
Resource.dispatch_request = dispatch_request
