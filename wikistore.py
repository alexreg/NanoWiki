from contextlib import contextmanager
from datetime import datetime
from enum import Enum, auto
import fcntl
from functools import wraps
from pathlib import Path
import shutil
import uuid

def _get_mtime(stat):
	return datetime.fromtimestamp(stat.st_mtime)

def _check_doc_exists(path):
	if not path.exists():
		raise WikiStoreError(WikiStoreErrorType.DOCUMENT_NOT_FOUND, path.name)
	return path

def _check_doc_rev_exists(path):
	if not path.exists():
		raise WikiStoreError(WikiStoreErrorType.DOCUMENT_REVISION_NOT_FOUND, path.parent.name, path.name)
	return path

def _check_doc_not_exists(path):
	if path.exists():
		raise WikiStoreError(WikiStoreErrorType.DOCUMENT_ALREADY_EXISTS, path.name)
	return path

# If `mode` is 's', then a shared lock is used.
# If `mode` is `x`, then an exclusive lock is used.
@contextmanager
def _lock_file(file, mode):
	should_close = False
	if hasattr(file, "fileno"):
		pass
	elif isinstance(file, Path):
		should_close = True
		path = file.with_name(file.name + ".lock")
		file = path.open('w')
	else:
		raise ValueError("`file` has invlaid type {}".format(type(file)))
	
	if mode == 's':
		op = fcntl.LOCK_SH
	elif mode == 'x':
		op = fcntl.LOCK_EX
	else:
		raise ValueError("Invalid lock mode '{}'".format(mode))
	
	try:
		fcntl.flock(file, op)
		yield file
	finally:
		fcntl.flock(file, fcntl.LOCK_UN)
		if should_close:
			file.close()
			path.unlink()

class WikiStoreErrorType(Enum):
	DOCUMENT_NOT_FOUND = auto()
	DOCUMENT_REVISION_NOT_FOUND = auto()
	DOCUMENT_ALREADY_EXISTS = auto()

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
		elif type == WikiStoreErrorType.DOCUMENT_ALREADY_EXISTS:
			self.title = args[0]
			message = "The document '{}' already exists".format(self.title)
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
		with _lock_file(self.path, 'x'):
			_check_doc_not_exists(self.path / title).mkdir()
	
	def delete_doc(self, title):
		with _lock_file(self.path, 'x'):
			shutil.rmtree(_check_doc_exists(self.path / title))
	
	def doc_exists(self, title):
		return (self.path / title).exists()
	
	def get_doc_info(self, title):
		path = self.path / title
		with _lock_file(path, 's'):
			stat = _check_doc_exists(path).stat()
			return DocumentInfo(title, _get_mtime(stat))
	
	def list_doc_revs(self, title):
		path = self.path / title
		with _lock_file(path, 's'):
			for child in _check_doc_exists(path).iterdir():
				if child.is_file():
					stat = child.stat()
					yield DocumentRevisionInfo(child.name, _get_mtime(stat))
	
	def get_doc_rev(self, title, revision = "latest"):
		path = self.path / title
		with _lock_file(path, 's'):
			_check_doc_exists(self.path / title)
			
			def get_latest_revision():
				return max((self.path / title).iterdir(), key = lambda c: _get_mtime(c.stat()))
			
			path = get_latest_revision() if revision == "latest" else self.path / title / revision
			stat = _check_doc_rev_exists(path).stat()
			with path.open('r') as file:
				return DocumentRevision(path.name, _get_mtime(stat), file.read())
	
	def create_doc_rev(self, title, content):
		path = self.path / title
		with _lock_file(path, 'x'):
			_check_doc_exists(self.path / title)
			revision = str(uuid.uuid4())
			with (self.path / title / revision).open('x') as file:
				file.write(content)
			return revision
