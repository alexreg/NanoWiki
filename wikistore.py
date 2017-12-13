from contextlib import contextmanager
from datetime import datetime
from diff import ApplyPatchError, DeserializePatchError, apply_patch, create_patch
from enum import Enum, auto
import fcntl
from functools import wraps
import os
from pathlib import Path
import shutil
import uuid

def _get_mtime(file):
	if hasattr(file, "stat"):
		stat = file.stat()
	elif hasattr(file, "fileno"):
		stat = os.stat(file.fileno())
	else:
		stat = file
	return datetime.fromtimestamp(stat.st_mtime)

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
		raise ValueError("`file` has invalid type {}".format(type(file)))
	
	if mode == 's':
		op = fcntl.LOCK_SH
	elif mode == 'x':
		op = fcntl.LOCK_EX
	else:
		raise ValueError("Invalid lock mode '{}'".format(mode))
	
	try:
		fcntl.flock(file, op)
		yield
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
	@staticmethod
	def _check_doc_exists(path):
		if not path.exists():
			raise WikiStoreError(WikiStoreErrorType.DOCUMENT_NOT_FOUND, path.name)
		return path
	
	@staticmethod
	def _check_doc_rev_exists(path):
		if not path.exists():
			raise WikiStoreError(WikiStoreErrorType.DOCUMENT_REVISION_NOT_FOUND, path.parent.name, path.name)
		return path
	
	@staticmethod
	def _check_doc_not_exists(path):
		if path.exists():
			raise WikiStoreError(WikiStoreErrorType.DOCUMENT_ALREADY_EXISTS, path.name)
		return path
	
	@staticmethod
	def _get_doc_rev(doc_path, revision = "latest"):
		revision == "latest" or __class__._check_doc_rev_exists(doc_path / revision)
		
		all_revisions = sorted(doc_path.iterdir(), key = lambda e: _get_mtime(e.stat()))
		content = None
		rev_path = None
		for path in all_revisions:
			rev_path = path
			patch = path.read_text()
			content = apply_patch(content, patch) if content else patch
			if path.name == revision:
				break
		
		if rev_path is None:
			return None
		return DocumentRevision(rev_path.name, _get_mtime(rev_path), content)
	
	def __init__(self, path):
		self.path = path if isinstance(path, Path) else Path(path)
		self.path.mkdir(parents = True, exist_ok = True)
	
	def list_docs(self):
		with _lock_file(self.path, 's'):
			def _list_docs():
				for doc_path in self.path.iterdir():
					if doc_path.is_dir():
						yield DocumentInfo(doc_path.name, _get_mtime(doc_path.stat()))
			
			return _list_docs(), _get_mtime(self.path)
	
	def create_doc(self, title):
		with _lock_file(self.path, 'x'):
			path = self.path / title
			__class__._check_doc_not_exists(path).mkdir()
			return _get_mtime(self.path)
	
	def delete_doc(self, title):
		with _lock_file(self.path, 'x'):
			shutil.rmtree(__class__._check_doc_exists(self.path / title))
	
	def doc_exists(self, title):
		return (self.path / title).exists()
	
	def get_doc_info(self, title):
		path = self.path / title
		with _lock_file(path, 's'):
			__class__._check_doc_exists(path)
			return DocumentInfo(title, _get_mtime(path))
	
	def list_doc_revs(self, title):
		doc_path = self.path / title
		with _lock_file(doc_path, 's'):
			__class__._check_doc_exists(doc_path)
			
			def _list_doc_revs():
				all_revisions = sorted(doc_path.iterdir(), key = lambda e: _get_mtime(e.stat()))
				for path in all_revisions:
					if path.is_file():
						yield DocumentRevisionInfo(path.name, _get_mtime(path))
			
			return _list_doc_revs(), _get_mtime(doc_path)
	
	def get_doc_rev(self, title, revision = "latest"):
		doc_path = self.path / title
		with _lock_file(doc_path, 's'):
			__class__._check_doc_exists(doc_path)
			return __class__._get_doc_rev(doc_path, revision = revision)
	
	def create_doc_rev(self, title, content):
		doc_path = self.path / title
		with _lock_file(doc_path, 'x'):
			__class__._check_doc_exists(doc_path)
			revision = str(uuid.uuid4())
			latest_rev = __class__._get_doc_rev(doc_path, revision = "latest")
			with (doc_path / revision).open('x') as file:
				file.write(create_patch(latest_rev.content if latest_rev else "", content) if latest_rev else content)
				return DocumentRevisionInfo(revision, _get_mtime(file))
