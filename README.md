# NanoWiki

A minimal implementation of a wiki system with a REST API, written in Python 3.

## Installing

To install dependencies, run:

```sh
pip3 install -r requirements.txt
```

## Running

To start the development server, run:

```sh
./run-devel
```

The location of the wiki store on the filesystem can be configured using the `NANOWIKI_WIKI_PATH` environment variable.

## Postman Tests

[Postman](https://www.getpostman.com) tests can be found in the `postman/` directory.

## API

The API follows the REST standard, and includes the following endpoints. All data is exchanged using the JSON format.

* `GET /documents`
  
  Returns information about all documents in the wiki.
  
* `GET /documents/{title}`
  
  Returns all revisions of the document with title `{title}`.
  
* `GET /documents/{title}/{revision}`
  
  Returns the revision with ID `{revision}` of the document with title `{title}`. If `{revision}` is `latest`, then it returns the most recent revision.
  
* `DELETE /documents/{title}`
  
  Deletes the document with title `{title}`.
  
* `POST /documents/{title}`
  
  ```json
  {
      "content": "{content}"
  }
  ```
  
  Creates a document with title `{title}`, or a new revision of the existing document with that title. Updates the content of the document to `{content}`.
