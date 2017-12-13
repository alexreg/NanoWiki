import json

class ApplyPatchError(Exception):
	pass

class DeserializePatchError(Exception):
	pass

def create_patch(old, new):
	'''
	Returns a Patch object.
	The Patch object _can_ be written to a file.

	Args:
		old (str): The old text
		new (str): The new text

	Returns:
		Patch(str): the patch object
	'''
	return json.dumps({
		'old': old,
		'new': new
	})

def apply_patch(txt, _patch):
	'''
	Return string where patch has been applied to old text

	Args:
		txt (str): The string to have patch applied to it.
		param2 (Patch): The patch object.

	Returns:
		str: If the patch is successful, then returns the applied string.

	Excepts:
		ApplyPatchError: if the patch is invalid
	'''
	try:
		patch = json.loads(_patch)
	except Exception:
		raise DeserializePatchError('Patch could not be deserialized')

	if patch.get('old') == txt:
		return patch.get('new')
	else:
		raise ApplyPatchError('Patch could not be applied')
