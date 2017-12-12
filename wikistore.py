from datetime import datetime
from enum import Enum, auto
import fcntl
from functools import wraps
from pathlib import Path
import shutil
import uuid

def _get_mtime(stat):
	return datetime.fromtimestamp(stat.st_mtime)

def check_doc_exists(path):
	if not path.exists():
		raise WikiStoreError(WikiStoreErrorType.DOCUMENT_NOT_FOUND, path.name)
	return path

def check_doc_rev_exists(path):
	if not path.exists():
		raise WikiStoreError(WikiStoreErrorType.DOCUMENT_REVISION_NOT_FOUND, path.parent.name, path.name)
	return path

class WikiStoreErrorType(Enum):
	DOCUMENT_NOT_FOUND = auto()
	DOCUMENT_REVISION_NOT_FOUND = auto()

class WikiStoreError(Exception):
	def __init__(self, type, *args):
		if not isinstance(type, WikiStoreErrorType):
			raise ValueError("`type` does not have type `WikiStoreErrorType`")
		self.type = type
		
		if type == WikiStoreErrorType.DOCUMENT_NOT_FOUND:
			self.title = args[0]
			message = "The document '{}' was not found".format(self.title)
		elif type == WikiStoreErrorType.DOCUMENT_REVISION_NOT_FOUND:
			self.title = args[0]
			self.revision = args[1]
			message = "The revision '{}' in the document '{}' was not found".format(self.revision, self.title)
		else:
			message = "Unknown"
		
		super().__init__(message)

class DocumentInfo:
	def __init__(self, title, last_modified_time = None):
		self.title = title
		self.last_modified_time = last_modified_time

class DocumentRevisionInfo:
	def __init__(self, revision, created_time):
		self.revision = revision
		self.created_time = created_time

class DocumentRevision(DocumentRevisionInfo):
	def __init__(self, revision, created_time, content):
		super().__init__(revision, created_time)
		self.content = content

class WikiStore:
	def __init__(self, path):
		self.path = path if isinstance(path, Path) else Path(path)
		
		self.path.mkdir(parents = True, exist_ok = True)
	
	def list_docs(self):
		for child in self.path.iterdir():
			if child.is_dir:
				stat = child.stat()
				yield DocumentInfo(child.name, _get_mtime(stat))
	
	def create_doc(self, title):
		(self.path / title).mkdir()
	
	def delete_doc(self, title):
		shutil.rmtree(check_doc_exists(self.path / title))
	
	def doc_exists(self, title):
		return (self.path / title).exists()
	
	def get_doc_info(self, title):
		stat = check_doc_exists(self.path / title).stat()
		return DocumentInfo(title, _get_mtime(stat))
	
	def list_doc_revs(self, title):
		for child in check_doc_exists(self.path / title).iterdir():
			if child.is_file():
				stat = child.stat()
				yield DocumentRevisionInfo(child.name, _get_mtime(stat))
	
	def get_doc_rev(self, title, revision = "latest"):
		check_doc_exists(self.path / title)
		
		def get_latest_revision():
			return max((self.path / title).iterdir(), key = lambda c: _get_mtime(c.stat()))
		
		path = get_latest_revision() if revision == "latest" else self.path / title / revision
		stat = check_doc_rev_exists(path).stat()
		with path.open('r') as file:
			return DocumentRevision(path.name, _get_mtime(stat), file.read())
	
	def create_doc_rev(self, title, content):
		check_doc_exists(self.path / title)
		revision = str(uuid.uuid4())
		with (self.path / title / revision).open('x') as file:
			file.write(content)
		return revision
